#!/usr/bin/env python3
"""DART 연구개발비·타법인 출자 현황 — 대구 본사 공시 기업(scripts/state/dart_corp.json 의 daegu=true) (운영자 지시 2026-10-05).

1) 출자 현황: OpenDART 사업보고서 주요정보 '타법인 출자 현황'(otrCprInvstmntSttus.json, 최근 사업연도 사업보고서)
   → scripts/data/company_investments.csv. 피출자 법인명·출자 목적·최초 취득일·기말 수량·지분율·장부가액(공시 표 단위 그대로)·피출자 법인 총자산·당기순손익.
2) 연구개발비: 사업보고서 원문(document.xml)의 '연구개발 활동' 표에서 '연구개발비용 (총)계' 행과 '매출액 대비 비율' 행을 읽어
   → scripts/data/company_rnd.csv (사업연도 3개 열: 당기·전기·전전기, 단위는 표 위 '단위' 글자로 원 환산). 표를 못 찾으면 그 회사는 건너뛴다(값을 만들지 않음).
3) 주요 제품(운영자 지시 2026-10-05: '자동차 부품' 같은 분야 말고 무엇을 만드는지): 사업보고서 원문 'II. 사업의 내용'의 '주요 제품(및 서비스)' 표에서
   사업부문·품목(제품)·용도·매출 비율 → scripts/data/company_products.csv. 표 글자 그대로(80자까지), 합계·소계 행은 뺀다.
대상 보고서는 scripts/data/company_employees.csv 의 회사별 최근 사업연도 접수번호. 공시 값과 링크만 — 평가·순위 없음. 키: DART_KEY.
사용: python3 scripts/collect_dart_extra.py [--only inv|rnd|prod] [--debug 회사명]
"""
from __future__ import annotations

import csv
import html
import io
import json
import os
import re
import sys
import time
import zipfile
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / "state" / "dart_corp.json"
EMP = ROOT / "scripts" / "data" / "company_employees.csv"
OUT_INV = ROOT / "scripts" / "data" / "company_investments.csv"
OUT_RND = ROOT / "scripts" / "data" / "company_rnd.csv"
API = "https://opendart.fss.or.kr/api"
UA = {"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"}
KEY = os.environ.get("DART_KEY", "").strip()
INV_COLS = ["corp_code", "name", "year", "inv_name", "purpose", "first_acq_date", "end_qty", "end_share_pct", "end_book_amount",
            "inv_total_assets", "inv_net_income", "rcept_no", "source_url", "as_of"]
OUT_PROD = ROOT / "scripts" / "data" / "company_products.csv"
PROD_COLS = ["corp_code", "name", "year", "segment", "product", "use", "share_pct", "rcept_no", "source_url", "as_of"]
RND_COLS = ["corp_code", "name", "report_year", "year", "rnd_won", "ratio_pct", "unit", "rcept_no", "source_url", "as_of"]


def redact(e: object) -> str:
    return re.sub(r"crtfc_key=[^&\s]+", "crtfc_key=***", str(e))


def get(path: str, **params) -> dict | None:
    params["crtfc_key"] = KEY
    try:
        r = requests.get(f"{API}/{path}", params=params, headers=UA, timeout=30)
        r.raise_for_status()
        j = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[dart_extra] {path} 실패: {redact(e)[:160]}")
        return None
    st = j.get("status")
    if st == "013":
        return {"list": []}
    if st == "020":
        print("[dart_extra] 사용 한도 초과(020) — 여기서 멈춤")
        raise SystemExit(0)
    if st != "000":
        print(f"[dart_extra] {path} 오류 {st}: {j.get('message')}")
        return None
    return j


def latest_reports() -> dict[str, dict]:
    """회사별 최근 사업연도 사업보고서(직원 현황 파일의 접수번호)"""
    out: dict[str, dict] = {}
    for r in csv.DictReader(open(EMP, encoding="utf-8")):
        if r.get("rcept_no") and (r["corp_code"] not in out or r["year"] > out[r["corp_code"]]["year"]):
            out[r["corp_code"]] = {"name": r["name"], "year": r["year"], "rcept_no": r["rcept_no"]}
    return out


def clean(s) -> str:
    s = str(s or "").strip()
    return "" if s in ("-", "－") else s


def investments(reps: dict[str, dict]) -> None:
    rows, sample = [], 0
    for i, (code, rep) in enumerate(sorted(reps.items()), 1):
        j = get("otrCprInvstmntSttus.json", corp_code=code, bsns_year=rep["year"], reprt_code="11011")
        time.sleep(0.15)
        lst = (j or {}).get("list", [])
        if lst and sample < 2:
            print(f"[dart_extra] 출자 예시 {rep['name']}: {json.dumps(lst[:2], ensure_ascii=False)[:800]}")
            sample += 1
        for x in lst:
            nm = clean(x.get("inv_prm"))
            if not nm or re.fullmatch(r"(합\s*계|총\s*계|계|소\s*계)", nm):
                continue
            rows.append({"corp_code": code, "name": rep["name"], "year": rep["year"], "inv_name": nm, "purpose": clean(x.get("invstmnt_purps")),
                         "first_acq_date": clean(x.get("frst_acqs_de")), "end_qty": clean(x.get("trmend_blce_qy")),
                         "end_share_pct": clean(x.get("trmend_blce_qota_rt")), "end_book_amount": clean(x.get("trmend_blce_acntbk_amount")),
                         "inv_total_assets": clean(x.get("recent_bsns_year_fnnr_sttus_tot_assets")),
                         "inv_net_income": clean(x.get("recent_bsns_year_fnnr_sttus_thstrm_ntpf")),
                         "rcept_no": x.get("rcept_no", rep["rcept_no"]), "as_of": date.today().isoformat()})
            rows[-1]["source_url"] = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rows[-1]['rcept_no']}"
        if i % 20 == 0:
            print(f"[dart_extra] 출자 {i}/{len(reps)}곳, 행 {len(rows)}")
    if not rows:
        print("[dart_extra] 출자 행 없음 — 저장 안 함")
        return
    with open(OUT_INV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=INV_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["corp_code"], r["inv_name"])))
    print(f"[dart_extra] 출자 저장: {OUT_INV.relative_to(ROOT)} ({len(rows)}행, {len({r['corp_code'] for r in rows})}곳)")


# ---------- 연구개발비 ----------
UNIT = {"원": 1, "천원": 1_000, "백만원": 1_000_000, "억원": 100_000_000}


def doc_xml(rcept_no: str) -> str:
    try:
        r = requests.get(f"{API}/document.xml", params={"crtfc_key": KEY, "rcept_no": rcept_no}, headers=UA, timeout=90)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
    except Exception as e:  # noqa: BLE001
        print(f"[dart_extra] 원문 {rcept_no} 실패: {redact(e)[:120]}")
        return ""
    names = sorted(z.namelist(), key=lambda n: z.getinfo(n).file_size, reverse=True)
    raw = z.read(names[0]) if names else b""   # 본문은 가장 큰 파일(감사보고서·첨부보다 큼)
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return ""


def cell_text(c: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()


def nums(cells: list[str]) -> list[float | None]:
    out = []
    for c in cells:
        t = c.replace(",", "").replace(" ", "")
        m = re.fullmatch(r"\(?(-?\d+(?:\.\d+)?)\)?%?", t)
        out.append(float(m.group(1)) * (-1 if t.startswith("(") else 1) if m else None)
    return out


def rnd_from_doc(xml: str, debug: bool = False) -> dict | None:
    """'연구개발' 이 나오는 곳 다음의 표 가운데 '연구개발비' 합계 행과 '매출액' 비율 행이 있는 첫 표"""
    starts = [m.start() for m in re.finditer(r"연구\s*개발\s*(활동|비용|실적)", xml)]
    for s in starts:
        seg = xml[s: s + 60000]
        for tm in re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", seg, flags=re.S | re.I):
            tbl = tm.group(1)
            rows = [[cell_text(c) for c in re.findall(r"<T[DHE][^>]*>(.*?)</T[DHE]>", tr, flags=re.S | re.I)]
                    for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", tbl, flags=re.S | re.I)]
            rows = [r for r in rows if any(r)]
            flat = " ".join(" ".join(r) for r in rows)
            if "연구개발" not in flat or "매출" not in flat:
                continue
            tot = next((r for r in rows if r and re.search(r"연구\s*개발\s*비\s*용?\s*(총\s*계|합\s*계|계)|연구\s*개발\s*비\s*용?\s*$|^\s*(합\s*계|총\s*계)\s*$", r[0])
                        and sum(v is not None for v in nums(r[1:])) >= 1), None)
            if not tot:   # 첫 칸이 '연구개발비용' + 둘째 칸이 '계' 인 모양
                tot = next((r for r in rows if len(r) > 2 and "연구개발" in r[0] and re.fullmatch(r"(총\s*계|합\s*계|계)", r[1])), None)
                if tot:
                    tot = [tot[0]] + tot[2:]
            ratio = next((r for r in rows if r and re.search(r"매출\s*액?\s*(대비|비율)|÷\s*당기\s*매출|매출액\s*×|비\s*율", " ".join(r[:2]))), None)
            if not tot:
                if debug:
                    print("   [표] 합계 행 없음:", [r[:4] for r in rows[:8]])
                continue
            before = xml[max(0, s): s + tm.start()][-3000:]
            um = re.findall(r"단위\s*[:：]?\s*(백만\s*원|천\s*원|억\s*원|원)", cell_text(before) + " " + flat[:300])
            unit = um[-1].replace(" ", "") if um else ""
            vals = [v for v in nums(tot[1:]) if v is not None][:3]
            rv = [v for v in nums(ratio[1:] if ratio else []) if v is not None][:3]
            hdr = " ".join(" ".join(r) for r in rows[:2])
            # 열 순서: 보통 당기 → 전기 → 전전기. 머리에 연도·기수가 커지는 순서면 거꾸로
            seq = [int(x) for x in re.findall(r"(20\d\d)\s*년", hdr)] or [int(x) for x in re.findall(r"제\s*(\d+)\s*기", hdr)]
            if len(seq) >= 2 and seq[0] < seq[-1]:
                vals, rv = vals[::-1], rv[::-1]
            if debug:
                print("   [표] 단위", unit, "합계", tot[:5], "비율", (ratio or [])[:5], "머리", hdr[:120])
            return {"unit": unit, "vals": vals, "ratios": rv, "hdr": hdr}
    return None


def rnd(reps: dict[str, dict], debug_name: str = "") -> None:
    rows, miss = [], []
    for i, (code, rep) in enumerate(sorted(reps.items()), 1):
        if debug_name and debug_name not in rep["name"]:
            continue
        xml = doc_xml(rep["rcept_no"])
        time.sleep(0.3)
        if not xml:
            miss.append(rep["name"])
            continue
        res = rnd_from_doc(xml, debug=bool(debug_name) or i <= 3)
        if not res or not res["vals"] or not res["unit"]:
            miss.append(rep["name"] + ("(단위 없음)" if res and not res["unit"] else ""))
            continue
        y = int(rep["year"])
        for k, v in enumerate(res["vals"]):
            rows.append({"corp_code": code, "name": rep["name"], "report_year": y, "year": y - k, "rnd_won": round(v * UNIT[res["unit"]]),
                         "ratio_pct": res["ratios"][k] if k < len(res["ratios"]) and res["ratios"][k] is not None and abs(res["ratios"][k]) < 100 else "",
                         "unit": res["unit"], "rcept_no": rep["rcept_no"], "source_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rep['rcept_no']}",
                         "as_of": date.today().isoformat()})
        if i % 20 == 0:
            print(f"[dart_extra] 연구개발 {i}/{len(reps)}곳, 찾음 {len({r['corp_code'] for r in rows})}곳")
    print(f"[dart_extra] 연구개발 표를 못 찾은 회사 {len(miss)}곳: {', '.join(miss[:40])}")
    if debug_name:
        print(json.dumps(rows, ensure_ascii=False, indent=1)[:2000])
        return
    if not rows:
        print("[dart_extra] 연구개발 행 없음 — 저장 안 함")
        return
    with open(OUT_RND, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RND_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["corp_code"], r["year"])))
    print(f"[dart_extra] 연구개발 저장: {OUT_RND.relative_to(ROOT)} ({len(rows)}행, {len({r['corp_code'] for r in rows})}곳)")


# ---------- 주요 제품 ----------
SKIP_ROW = re.compile(r"^(합\s*계|총\s*계|소\s*계|계|합계\s*\(.*\)|내부거래.*|연결조정.*|조정.*|단위.*|제\s*품|상\s*품|용\s*역|기\s*타|서비스|수출|내수|국내|해외"
                      r"|품\s*목.*|제\s*품\s*명|주\s*요\s*제\s*품.*|구\s*분|사\s*업\s*부\s*문|부\s*문|총\s*매\s*출.*|매출\s*총계|단순합계|차감.*|매출\s*액)$")
HEADERISH = re.compile(r"품\s*목|제\s*품\s*명|주\s*요\s*제\s*품|구체적\s*용도|^\s*구\s*분\s*$")


def good_product(prod_v: str, segv: str) -> bool:
    """표 머리가 두 줄이라 샌 머리 글자·합계·문장(설명 문단을 표로 짠 보고서)은 품목이 아니다"""
    t = prod_v.strip()
    if not t or SKIP_ROW.match(t) or HEADERISH.search(t) or SKIP_ROW.match(segv or "x"):
        return False
    if re.fullmatch(r"[\d,.\s%()-]+", t) or t.startswith("-") or t.endswith(".") or re.search(r"(습니다|입니다|있음|진행\s*중)", t):
        return False
    return len(t) <= 60   # 부문 이름과 같은 품목(도시가스/도시가스)은 그대로 둔다


def table_rows(tbl: str) -> list[list[str]]:
    """표를 격자로: rowspan 은 아래 행에 같은 글자를 채우고 colspan 은 옆 칸에 되풀이한다(사업부문·품목이 여러 행에 걸친 '주요 제품' 표, 2026-10-06)."""
    carry: dict[int, list] = {}
    rows = []
    for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", tbl, flags=re.S | re.I):
        out, col = [], 0
        for attrs, body in re.findall(r"<T[DHE]([^>]*)>(.*?)</T[DHE]>", tr, flags=re.S | re.I):
            while col in carry and carry[col][0] > 0:
                out.append(carry[col][1]); carry[col][0] -= 1; col += 1
            rs = int((re.search(r"rowspan\s*=\s*\"?(\d+)", attrs, re.I) or [0, "1"])[1] or 1)
            cs = int((re.search(r"colspan\s*=\s*\"?(\d+)", attrs, re.I) or [0, "1"])[1] or 1)
            text = cell_text(body)
            for _ in range(max(1, cs)):
                out.append(text)
                if rs > 1:
                    carry[col] = [rs - 1, text]
                col += 1
        while col in carry and carry[col][0] > 0:
            out.append(carry[col][1]); carry[col][0] -= 1; col += 1
        if any(out):
            rows.append(out)
    return rows


def products_from_doc(xml: str, debug: bool = False) -> list[dict]:
    """'주요 제품' 제목 다음의 표 가운데 머리에 품목·제품·품명이 있는 첫 표 → [{segment, product, use, share_pct}]"""
    starts = [m.start() for m in re.finditer(r"주요\s*(제품|상품|품목)", xml)]
    for st in starts[:12]:
        seg = xml[st: st + 40000]
        for tm in list(re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", seg, flags=re.S | re.I))[:3]:
            rows = table_rows(tm.group(1))
            if len(rows) < 2:
                continue
            hi = next((i for i, r in enumerate(rows[:3]) if any(re.search(r"품\s*목|제\s*품|품\s*명|상\s*품|주요\s*서비스", c) for c in r)), None)
            if hi is None:
                continue
            head = rows[hi]
            def col(pat, excl=None):
                return next((i for i, c in enumerate(head) if re.search(pat, c) and not (excl and re.search(excl, c))), None)
            pc = col(r"품\s*목|주요\s*제품|제\s*품\s*명?|품\s*명|상\s*품|주요\s*서비스", r"매출|비\s*율|비\s*중")
            if pc is None:
                continue
            sc = col(r"부\s*문|사업|구\s*분", r"매출")
            uc = col(r"용\s*도|내\s*용|설\s*명|특\s*징")
            rc = col(r"비\s*율|비\s*중|%")
            out, last_seg = [], ""
            for r in rows[hi + 1:]:
                segv = r[sc] if sc is not None and sc < len(r) else ""
                last_seg = segv or last_seg
                prod_v = r[pc] if pc < len(r) else ""
                if not good_product(prod_v, segv):
                    continue
                share = ""
                if rc is not None and rc < len(r):
                    v = nums([r[rc]])[0]
                    share = v if v is not None and 0 <= v <= 100 else ""
                out.append({"segment": last_seg[:60], "product": prod_v[:80], "use": (r[uc] if uc is not None and uc < len(r) else "")[:80], "share_pct": share})
            if debug:
                print("   [제품 표] 머리", head[:7], "→", [(o["segment"], o["product"], o["share_pct"]) for o in out[:6]])
            if out:
                return out[:20]
    return []


def products(reps: dict[str, dict], debug_name: str = "") -> None:
    rows, miss = [], []
    for i, (code, rep) in enumerate(sorted(reps.items()), 1):
        if debug_name and debug_name not in rep["name"]:
            continue
        xml = doc_xml(rep["rcept_no"])
        time.sleep(0.3)
        res = products_from_doc(xml, debug=bool(debug_name) or i <= 5) if xml else []
        if not res:
            miss.append(rep["name"])
            continue
        for o in res:
            rows.append({"corp_code": code, "name": rep["name"], "year": rep["year"], **o, "rcept_no": rep["rcept_no"],
                         "source_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rep['rcept_no']}", "as_of": date.today().isoformat()})
    print(f"[dart_extra] 주요 제품 표를 못 찾은 회사 {len(miss)}곳: {', '.join(miss[:40])}")
    if debug_name:
        print(json.dumps(rows, ensure_ascii=False, indent=1)[:3000])
        return
    if not rows:
        print("[dart_extra] 주요 제품 행 없음 — 저장 안 함")
        return
    with open(OUT_PROD, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PROD_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"[dart_extra] 주요 제품 저장: {OUT_PROD.relative_to(ROOT)} ({len(rows)}행, {len({r['corp_code'] for r in rows})}곳)")


def main(argv: list[str]) -> int:
    if not KEY:
        print("DART_KEY 없음")
        return 0
    only = argv[argv.index("--only") + 1] if "--only" in argv else ""
    dbg = argv[argv.index("--debug") + 1] if "--debug" in argv else ""
    reps = latest_reports()
    print(f"[dart_extra] 대상 {len(reps)}곳")
    if only in ("", "inv") and not dbg:
        investments(reps)
    if only in ("", "rnd") and not (dbg and only == "prod"):
        rnd(reps, dbg)
    if only in ("", "prod"):
        products(reps, dbg)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
