#!/usr/bin/env python3
"""DART 감사보고서·사업보고서로 대구 비상장 외감 회사 재무와 전국 비교 자료를 모은다
(운영자 지시 2026-11-03 '대구 비상장 재무 현황표 조사해봐' → '전국과 비교하는 것도 구현해야지' → '진행해').

모드(하나씩, 하루 호출 한도 20,000회 안에서 나눠 돈다):
  --filings      공시검색 pblntf_ty=F(외부감사관련)를 3개월씩 받아 감사보고서를 낸 비상장 회사 목록
                 → scripts/state/dart_audit_filings.json.gz (회사 코드·이름·감사보고서 접수 목록)
  --daegu        목록 × 기업 사전 이름(법인 표기·공장 표시 뗌) → 기업개황(캐시 scripts/state/dart_audit_corp.json)
                 → 본사 '대구' 제조업(업종 10~34)의 최근 별도 감사보고서 → scripts/data/company_financials_audit.csv
  --listed       전국 유가증권·코스닥 제조업(기업개황 캐시 scripts/state/dart_corp.json) 단일회사 전체 재무제표(별도, 사업보고서)
                 → data/dart/national_listed.csv (대구 본사 회사 포함, region 칸으로 가름)
  --sample N     감사보고서 제출 비상장 회사에서 무작위(시드 고정) N곳 기업개황 → 제조업만 업종 묶음당 --cap 곳까지
                 최근 별도 감사보고서 → data/dart/national_audit_sample.csv + .json(표본 설계)
  --max-calls N  이번 실행 API 호출 상한(기본 9000). 넘으면 쓴 데까지 저장하고 멈춘다(다음 실행이 이어 받음)
  --reparse      이미 읽은 감사보고서도 다시 읽는다(판독 규칙을 고친 뒤)   --show N  처음 N 곳의 원문 줄을 로그로(대조용)

원칙: 공시 값 그대로(단위만 원으로), 못 읽은 계정은 비움, 추정 없음. 대표자·주주 이름은 읽지 않는다.
화면에는 회사 이름 목록·순위를 내지 않는다(scripts/audit_compare.py 가 묶음 통계만 만든다). 키: DART_KEY.
"""
from __future__ import annotations

import csv
import gzip
import json
import random
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_dart_notes as N  # noqa: E402  (get·doc_xml·clean·norm_name·fin_from_audit 재사용)
import industry  # noqa: E402

ROOT = N.ROOT
FILINGS = ROOT / "scripts" / "state" / "dart_audit_filings.json.gz"
CORP = ROOT / "scripts" / "state" / "dart_audit_corp.json"
LISTED_CACHE = ROOT / "scripts" / "state" / "dart_corp.json"
OUT_DG = ROOT / "scripts" / "data" / "company_financials_audit.csv"
OUT_NL = ROOT / "data" / "dart" / "national_listed.csv"
OUT_NS = ROOT / "data" / "dart" / "national_audit_sample.csv"
OUT_NS_META = ROOT / "data" / "dart" / "national_audit_sample.json"
SUMMARY = ROOT / "data" / "dart" / "audit_summary.json"

COLS = ["corp_code", "name", "region", "district", "ksic", "group", "fy", "basis", "fs", "report", "rcept_no",
        "sales", "sales_prev", "op", "op_prev", "net", "assets", "liab", "equity", "interest", "interest_src", "ocf", "read_at"]
MAXC = [9000]


def budget() -> bool:
    return N.CALLS[0] < MAXC[0]


def is_mfg(ksic: str) -> bool:
    k = (ksic or "")[:2]
    return k.isdigit() and 10 <= int(k) <= 34


def group_of(ksic: str) -> str:
    return industry.classify(ksic or "")


def fy_of(report_nm: str) -> str:
    m = re.search(r"\((\d{4})\.(\d{2})\)", report_nm or "")
    return m.group(1) if m else ""


def load_json(p: Path, default):
    if not p.exists():
        return default
    if p.suffix == ".gz":
        return json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if p.suffix == ".gz":
        p.write_bytes(gzip.compress(raw, mtime=0))
    else:
        p.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=0), encoding="utf-8")


def read_csv(p: Path) -> list[dict]:
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


def write_csv(p: Path, rows) -> None:
    rows = list(rows.values()) if isinstance(rows, dict) else rows
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r.get("corp_code", ""), r.get("fy", "")))
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ── ① 감사보고서 제출 목록 ──
def filings(argv: list[str]) -> int:
    since = argv[argv.index("--since") + 1] if "--since" in argv else (date.today() - timedelta(days=700)).strftime("%Y%m%d")
    data = {"since": since, "corps": {}}
    d0 = date(int(since[:4]), int(since[4:6]), int(since[6:]))
    while d0 < date.today() and budget():
        d1 = min(d0 + timedelta(days=89), date.today())
        page, total = 1, 1
        while page <= total and budget():
            j = N.get("list.json", bgn_de=d0.strftime("%Y%m%d"), end_de=d1.strftime("%Y%m%d"), pblntf_ty="F", page_no=page, page_count=100) or {}
            total = int(j.get("total_page") or 0)
            for x in j.get("list", []):
                nm = re.sub(r"\s+", " ", x.get("report_nm") or "").strip()
                if "감사보고서" not in nm or (x.get("stock_code") or "").strip():
                    continue
                c = data["corps"].setdefault(x["corp_code"], {"n": x.get("corp_name"), "a": []})
                c["a"].append([x.get("rcept_dt"), nm, x.get("rcept_no")])
            page += 1
        print(f"[filings] {d0}~{d1} 누적 {len(data['corps'])}곳 (호출 {N.CALLS[0]})", flush=True)
        d0 = d1 + timedelta(days=1)
    for c in data["corps"].values():
        c["a"] = sorted({tuple(a) for a in c["a"]}, reverse=True)
    data["got"] = date.today().isoformat()
    save_json(FILINGS, data)
    print(f"[filings] 저장 {len(data['corps'])}곳 → {FILINGS.relative_to(ROOT)}")
    return 0


def pick_reports(aud: list, k: int = 2) -> list[tuple]:
    """최근 k 개 사업연도의 별도 감사보고서(같은 해는 늦은 접수 — 정정 반영). 별도가 없으면 연결."""
    sep = [a for a in aud if "연결" not in a[1] and "결합" not in a[1]]
    pool = sep or [a for a in aud if "결합" not in a[1]]
    by_fy: dict[str, tuple] = {}
    for a in pool:
        fy = fy_of(a[1])
        if fy and (fy not in by_fy or (a[0], a[2]) > (by_fy[fy][0], by_fy[fy][2])):
            by_fy[fy] = a
    return [by_fy[fy] for fy in sorted(by_fy, reverse=True)[:k]]


def merge(rows: dict, new: list[dict]) -> None:
    """(회사, 사업연도) 한 행 — 그 해 보고서의 당기 값이 다음 해 보고서의 전기 비교 값보다 먼저."""
    for r in new:
        key = (r["corp_code"], r["fy"])
        if key in rows and rows[key].get("basis") == "당기" and r["basis"] != "당기":
            continue
        rows[key] = r


def company(code: str, cache: dict) -> dict:
    if code in cache:
        return cache[code]
    inf = N.get("company.json", corp_code=code) or {}
    adr = inf.get("adres") or ""
    parts = adr.split()
    rec = {"name": inf.get("corp_name") or "", "region": parts[0] if parts else "", "district": parts[1] if len(parts) > 1 else "",
           "ksic": inf.get("induty_code") or "", "cls": inf.get("corp_cls") or "", "checked": date.today().isoformat()}
    if inf:
        cache[code] = rec
    return rec


SHOW = [0]   # --show N: 처음 N 곳의 원문 줄을 로그로(DART 원문 대조용)


def read_rows(code: str, info: dict, rep: tuple) -> list[dict]:
    """감사보고서 한 건 → 당기 행 + 전기 비교 행(사업연도 −1). 못 읽은 계정은 비움."""
    rd, rn, rno = rep
    xml = N.doc_xml(rno)
    if not xml:
        return []
    got, raw = N.fin_from_audit(xml)
    if SHOW[0] > 0:
        SHOW[0] -= 1
        print(f"CHECK\t{info.get('name')}\t{rn}\thttps://dart.fss.or.kr/dsaf001/main.do?rcpNo={rno}")
        for k, v in raw.items():
            print(f"CHECK\t{info.get('name')}\t{k}\t{v}")
    fy = fy_of(rn)
    base = {"corp_code": code, "name": info.get("name", ""), "region": info.get("region", ""), "district": info.get("district", ""),
            "ksic": info.get("ksic", ""), "group": group_of(info.get("ksic", "")), "fs": "연결" if "연결" in rn else "별도",
            "report": rn, "rcept_no": rno, "read_at": date.today().isoformat()}
    cur = {**base, "fy": fy, "basis": "당기"}
    prev = {**base, "fy": str(int(fy) - 1) if fy.isdigit() else "", "basis": "전기 비교"}
    for k in ("sales", "op", "net", "assets", "liab", "equity", "interest", "ocf"):
        if k in got:
            cur[k] = got[k][0]
            if got[k][1] is not None:
                prev[k] = got[k][1]
            if k in ("sales", "op"):
                cur[k + "_prev"] = got[k][1] if got[k][1] is not None else ""
    if "interest" in got:
        cur["interest_src"] = prev["interest_src"] = "손익계산서 이자비용"
    out = [cur]
    if prev["fy"] and any(k in prev for k in ("sales", "assets")):
        out.append(prev)
    return out


def base_name(n: str) -> str:
    n = re.sub(r"\s*(제?\d+공장|\S*공장|\S*지점|\S*사업장|\S*연구소|\(\S*공장\))$", "", n or "")
    return N.norm_name(n)


# ── ② 대구 ──
def daegu(argv: list[str]) -> int:
    fl = load_json(FILINGS, {}).get("corps", {})
    if not fl:
        print("[daegu] 감사보고서 목록 없음 — 먼저 --filings")
        return 0
    cache = load_json(CORP, {})
    names = set()
    for f in ("dalseong_companies.csv", "extra_companies.csv"):
        for r in read_csv(ROOT / "scripts" / "data" / f):
            for k in (N.norm_name(r["name"]), base_name(r["name"])):
                if len(k) >= 2:
                    names.add(k)
    matched = [c for c, v in fl.items() if N.norm_name(v["n"]) in names]
    print(f"[daegu] 감사보고서 제출 비상장 {len(fl)}곳 중 기업 사전 이름 일치 {len(matched)}곳", flush=True)
    prev_rows = [] if "--reparse" in argv else [r for r in read_csv(OUT_DG) if r.get("basis")]   # basis 없는 옛 형식(한 해 한 줄)은 버리고 다시 읽는다
    done = {r["rcept_no"] for r in prev_rows if r.get("basis") == "당기"}
    rows = {(r["corp_code"], r["fy"]): r for r in prev_rows}
    k = int(argv[argv.index("--years") + 1]) if "--years" in argv else 2
    n_dg = n_mfg = 0
    try:
      for i, c in enumerate(matched):
          if not budget():
              print("[daegu] 호출 상한 — 여기까지 저장")
              break
          info = company(c, cache)
          if not info.get("region", "").startswith("대구"):
              continue
          n_dg += 1
          if not is_mfg(info.get("ksic", "")):
              continue
          n_mfg += 1
          for rep in pick_reports([tuple(a) for a in fl[c]["a"]], k):
              if rep[2] in done or not budget():
                  continue
              merge(rows, read_rows(c, info, rep))
          if i % 100 == 0:
              print(f"[daegu] {i}/{len(matched)} 대구 {n_dg} 제조 {n_mfg} 저장 {len(rows)} (호출 {N.CALLS[0]})", flush=True)
              save_json(CORP, cache)
    finally:
      save_json(CORP, cache)
      write_csv(OUT_DG, rows)
    summ = load_json(SUMMARY, {})
    summ.update({"daegu": {"filers": len(fl), "name_matched": len(matched), "daegu": n_dg, "daegu_mfg": n_mfg, "rows": len({c for c, _ in rows}),
                           "filings_since": load_json(FILINGS, {}).get("since"), "updated": date.today().isoformat()}})
    save_json(SUMMARY, summ)
    print(f"[daegu] 본사 대구 {n_dg}곳, 제조업 {n_mfg}곳, 재무 {len({c for c, _ in rows})}곳·{len(rows)}행(회사×사업연도) → {OUT_DG.relative_to(ROOT)} (호출 {N.CALLS[0]})")
    return 0


# ── ③ 전국 상장 ──
LISTED_ACC = {
    "sales": ([r"^(매출액|수익\(매출액\)|영업수익|매출)$"], ["ifrs-full_Revenue"]),
    "op": ([r"^영업이익(\(손실\))?$|^영업손익$|^영업손실$"], ["dart_OperatingIncomeLoss"]),
    "net": ([r"^당기순이익(\(손실\))?$|^당기순손익$"], ["ifrs-full_ProfitLoss"]),
    "assets": ([r"^자산총계$"], ["ifrs-full_Assets"]),
    "liab": ([r"^부채총계$"], ["ifrs-full_Liabilities"]),
    "equity": ([r"^자본총계$"], ["ifrs-full_Equity"]),
    "ocf": ([r"^영업활동(으로 ?인한 ?|으로부터의 ?)?현금흐름$"], ["ifrs-full_CashFlowsFromUsedInOperatingActivities"]),
}


def amt(v) -> int | None:
    v = (v or "").replace(",", "").strip()
    if not re.fullmatch(r"-?\d+", v):
        return None
    return int(v)


def listed(argv: list[str]) -> int:
    """--listed [--year 2025,2024]: 사업보고서 별도 전체 재무 — 한 번 부르면 당기·전기 두 해(전기 비교 행)가 나온다."""
    corps = load_json(LISTED_CACHE, {})
    years = (argv[argv.index("--year") + 1] if "--year" in argv else str(date.today().year - 1)).split(",")
    tgt = {c: v for c, v in corps.items() if v.get("corp_cls") in ("Y", "K") and is_mfg(v.get("induty_code", ""))}
    prev_rows = [r for r in read_csv(OUT_NL) if r.get("basis")]
    rows = {(r["corp_code"], r["fy"]): r for r in prev_rows}
    done = {(r["corp_code"], r["fy"]) for r in prev_rows if r.get("basis") == "당기"}
    print(f"[listed] 기업개황 캐시 {len(corps)}곳 중 유가증권·코스닥 제조업 {len(tgt)}곳, 사업연도 {years}", flush=True)
    try:
        for year in years:
            for i, (c, v) in enumerate(sorted(tgt.items())):
                if (c, year) in done:
                    continue
                if not budget():
                    print("[listed] 호출 상한 — 여기까지 저장")
                    break
                j = N.get("fnlttSinglAcntAll.json", corp_code=c, bsns_year=year, reprt_code="11011", fs_div="OFS") or {}
                items = j.get("list", [])
                if not items:
                    continue
                region = (v.get("region") or "").split()
                base = {"corp_code": c, "name": v.get("name", ""), "region": region[0] if region else "", "district": region[1] if len(region) > 1 else "",
                        "ksic": v.get("induty_code", ""), "group": group_of(v.get("induty_code", "")), "fs": "별도",
                        "report": f"사업보고서 ({year}.12)", "rcept_no": items[0].get("rcept_no", ""), "read_at": date.today().isoformat()}
                cur = {**base, "fy": year, "basis": "당기"}
                prv = {**base, "fy": str(int(year) - 1), "basis": "전기 비교"}
                for k, (pats, ids) in LISTED_ACC.items():
                    sj = ("BS",) if k in ("assets", "liab", "equity") else ("CF",) if k == "ocf" else ("IS", "CIS")
                    hit = next((x for x in items if x.get("sj_div") in sj and x.get("account_id") in ids), None) \
                        or next((x for x in items if x.get("sj_div") in sj and any(re.match(p, (x.get("account_nm") or "").replace(" ", "")) for p in pats)), None)
                    if hit:
                        cur[k] = amt(hit.get("thstrm_amount"))
                        pv = amt(hit.get("frmtrm_amount"))
                        if pv is not None:
                            prv[k] = pv
                        if k in ("sales", "op"):
                            cur[k + "_prev"] = pv if pv is not None else ""
                ie = next((x for x in items if x.get("sj_div") in ("IS", "CIS") and re.fullmatch(r"이자비용", (x.get("account_nm") or "").replace(" ", ""))), None)
                ip = next((x for x in items if x.get("sj_div") == "CF" and re.match(r"^이자(의)?지급", (x.get("account_nm") or "").replace(" ", ""))), None)
                for row, col in ((cur, "thstrm_amount"), (prv, "frmtrm_amount")):
                    if ie and amt(ie.get(col)) is not None:
                        row["interest"], row["interest_src"] = amt(ie.get(col)), "손익계산서 이자비용"
                    elif ip and amt(ip.get(col)) is not None:
                        row["interest"], row["interest_src"] = abs(amt(ip.get(col))), "현금흐름표 이자지급"
                merge(rows, [cur] + ([prv] if any(k in prv for k in ("sales", "assets")) else []))
                if i % 200 == 0:
                    print(f"[listed] {year} {i}/{len(tgt)} 행 {len(rows)} (호출 {N.CALLS[0]})", flush=True)
                    write_csv(OUT_NL, rows)
    finally:
        write_csv(OUT_NL, rows)
    summ = load_json(SUMMARY, {})
    summ["listed"] = {"years": years, "target": len(tgt), "firms": len({c for c, _ in rows}), "rows": len(rows), "updated": date.today().isoformat()}
    save_json(SUMMARY, summ)
    print(f"[listed] {len({c for c, _ in rows})}곳·{len(rows)}행 → {OUT_NL.relative_to(ROOT)} (호출 {N.CALLS[0]})")
    return 0


# ── ④ 전국 비상장 표본 ──
def sample(argv: list[str]) -> int:
    n = int(argv[argv.index("--sample") + 1])
    cap = int(argv[argv.index("--cap") + 1]) if "--cap" in argv else 150
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 20261103
    fl = load_json(FILINGS, {}).get("corps", {})
    if not fl:
        print("[sample] 감사보고서 목록 없음 — 먼저 --filings")
        return 0
    cache = load_json(CORP, {})
    pop = sorted(fl)
    random.seed(seed)
    order = random.sample(pop, len(pop))   # 시드 고정 순서 — 앞에서부터 n 곳을 본다(이어 받기 가능)
    prev_rows = [] if "--reparse" in argv else [r for r in read_csv(OUT_NS) if r.get("basis")]
    done = {r["rcept_no"] for r in prev_rows if r.get("basis") == "당기"}
    rows = {(r["corp_code"], r["fy"]): r for r in prev_rows}
    firms = {r["corp_code"]: r["group"] for r in prev_rows}
    k = int(argv[argv.index("--years") + 1]) if "--years" in argv else 2
    per: dict[str, int] = {}
    for g in firms.values():
        per[g] = per.get(g, 0) + 1
    seen = mfg = 0
    for c in order[:n]:
        if not budget():
            print("[sample] 호출 상한 — 여기까지 저장")
            break
        seen += 1
        info = company(c, cache)
        if not is_mfg(info.get("ksic", "")):
            continue
        mfg += 1
        g = group_of(info["ksic"])
        if c not in firms and per.get(g, 0) >= cap:
            continue
        got_any = False
        for rep in pick_reports([tuple(a) for a in fl[c]["a"]], k):
            if rep[2] in done or not budget():
                continue
            new = read_rows(c, info, rep)
            merge(rows, new)
            got_any = got_any or bool(new)
        if got_any and c not in firms:
            firms[c] = g
            per[g] = per.get(g, 0) + 1
        if seen % 200 == 0:
            print(f"[sample] {seen}/{n} 제조 {mfg} 저장 {len(firms)}곳 (호출 {N.CALLS[0]})", flush=True)
            save_json(CORP, cache)
            write_csv(OUT_NS, rows)
    save_json(CORP, cache)
    write_csv(OUT_NS, rows)
    meta = {"population": len(pop), "seed": seed, "looked": n, "cap_per_group": cap, "rows": len(firms), "years_per_firm": k, "per_group": per,
            "filings_since": load_json(FILINGS, {}).get("since"), "updated": date.today().isoformat(),
            "note": "감사보고서 제출 비상장 회사(대구 포함) 전체에서 시드 고정 무작위 순서로 앞 looked 곳의 기업개황을 보고 제조업(업종 10~34)만, 업종 묶음당 cap 곳까지"}
    save_json(OUT_NS_META, meta)
    print(f"[sample] {json.dumps(meta, ensure_ascii=False)}")
    return 0


def main(argv: list[str]) -> int:
    if not N.KEY:
        print("DART_KEY 없음")
        return 0
    if "--max-calls" in argv:
        MAXC[0] = int(argv[argv.index("--max-calls") + 1])
    if "--show" in argv:
        SHOW[0] = int(argv[argv.index("--show") + 1])
    t0 = time.time()
    try:
        if "--filings" in argv:
            filings(argv)
        if "--daegu" in argv:
            daegu(argv)
        if "--listed" in argv:
            listed(argv)
        if "--sample" in argv:
            sample(argv)
    except SystemExit:
        print("[audit] 사용 한도 — 멈춤")
    print(f"[audit] 끝 — API 호출 {N.CALLS[0]}회, {int(time.time() - t0)}초")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
