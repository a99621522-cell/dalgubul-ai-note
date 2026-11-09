#!/usr/bin/env python3
"""전국 DART 공시 회사의 '시설자금' 조달 공시 — 공장 위치를 아직 공시하지 않은 증설 신호 조사용(운영자 지시 2026-11-09 '둘 다 해봐').

1) 공시검색(list.json, 회사 지정 없이 3개월씩)에서 주요사항보고(B) 유상증자·전환사채·신주인수권부사채 발행 결정과
   발행공시(C) 증권신고서(지분증권 — 상장 공모 포함)를 모은다.
2) 기업개황 업종 코드가 --ind 접두어인 회사만:
   - B: 구조화 API(piicDecsn·cvbdIsDecsn·bdwtIsDecsn)의 자금조달 목적별 금액에서 시설자금(fdpp_fclt)이 0보다 큰 건만
   - C: 원문의 '자금의 사용목적' 부분에 시설자금·공장·설비 낱말이 있는 건만
   원문에서 시설·공장 문장(최대 3개, 150자)과 그 부분에 나온 국내 시군구·해외 국가를 뽑는다.
3) 같은 회사가 data/dart/capex_national.csv 에 신규시설투자·유형자산 양수 공시가 있으면 표시(capex)한다 — 없으면 '위치 미공시' 후보.
결과 data/dart/funding_facility.csv. 공시 사실·제목·링크만 — 평가 없음, 사이트는 읽지 않는다. 사람 이름은 다루지 않는다.
키: DART_KEY. 사용: python3 scripts/dart_funding_facility.py [--months 18] [--ind 22,24,25,27,28,29,30]
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_dart_future as F  # noqa: E402
from dart_capex_national import ABROAD, CACHE, PLACE, windows  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "dart" / "funding_facility.csv"
CAPEX = ROOT / "data" / "dart" / "capex_national.csv"
COLS = ["rcept_dt", "corp_code", "name", "corp_cls", "induty", "hq", "report_nm", "kind", "fclt_eok", "total_eok",
        "facility_text", "places", "abroad", "capex", "rcept_no", "url"]
API = {"유상증자": "piicDecsn.json", "전환사채": "cvbdIsDecsn.json", "신주인수권부사채": "bdwtIsDecsn.json"}
FAC = re.compile(r"[^.。]{0,90}(?:시설자금|공장|생산라인|생산 라인|설비|부지|신축|증설|신설)[^.。]{0,90}")


def kind_of(t: str) -> str:
    t = t.replace(" ", "")
    if "철회" in t:
        return ""
    if "유상증자결정" in t:
        return "유상증자"
    if "전환사채권발행결정" in t:
        return "전환사채"
    if "신주인수권부사채권발행결정" in t:
        return "신주인수권부사채"
    if "증권신고서" in t and "지분증권" in t:
        return "증권신고서"
    return ""


def num(v) -> int:
    try:
        return int(str(v).replace(",", "").strip() or 0)
    except ValueError:
        return 0


def use_region(t: str) -> str:
    """원문에서 자금 사용 목적 부분(여러 번 나오면 이어 붙임, 각 6,000자)."""
    out = []
    for m in re.finditer(r"자금의\s?사용\s?목적|자금조달의\s?목적|자금사용\s?계획", t):
        out.append(t[m.start(): m.start() + 6000])
        if len(out) >= 4:
            break
    return " ".join(out) if out else t[:6000]


def main(argv: list[str]) -> int:
    months = int(argv[argv.index("--months") + 1]) if "--months" in argv else 18
    ind = tuple((argv[argv.index("--ind") + 1] if "--ind" in argv else "22,24,25,27,28,29,30").split(","))
    if not F.KEY:
        print("DART_KEY 없음")
        return 0
    cache = json.load(open(CACHE, encoding="utf-8")) if CACHE.exists() else {}
    capex = {}
    if CAPEX.exists():
        for r in csv.DictReader(open(CAPEX, encoding="utf-8")):
            capex.setdefault(r["corp_code"], []).append(f"{r['rcept_dt']} {r['kind']} {r['places'][:40]}".strip())
    hits = []
    for bgn, end in windows(months):
        for ty in ("B", "C"):
            page = 1
            while True:
                j = F.get_json("list.json", bgn_de=bgn, end_de=end, pblntf_ty=ty, page_no=page, page_count=100)
                time.sleep(0.12)
                if not j:
                    break
                for r in j.get("list", []):
                    k = kind_of(r.get("report_nm", ""))
                    if k:
                        hits.append((k, r))
                if page >= int(j.get("total_page") or 1):
                    break
                page += 1
        print(f"  {bgn}~{end}: 누적 {len(hits)}건")
    print(f"제목 일치 {len(hits)}건", Counter(k for k, _ in hits))
    rows, new, api_seen = [], 0, {}
    for k, r in hits:
        code = r["corp_code"]
        if code not in cache:
            inf = F.get_json("company.json", corp_code=code) or {}
            time.sleep(0.12)
            cache[code] = {x: inf.get(x, "") for x in ("corp_name", "stock_code", "corp_cls", "adres", "induty_code", "est_dt", "acc_mt")}
            new += 1
        c = cache[code]
        indc = c.get("induty_code") or ""
        if not indc.startswith(ind):
            continue
        fclt = tot = 0
        if k in API:
            key = (code, k)
            if key not in api_seen:
                j = F.get_json(API[k], corp_code=code, bgn_de=windows_start(months), end_de=today())
                time.sleep(0.15)
                api_seen[key] = (j or {}).get("list", [])
            for a in api_seen[key]:
                if a.get("rcept_no") == r["rcept_no"]:
                    fclt = num(a.get("fdpp_fclt"))
                    tot = sum(num(a.get(f)) for f in ("fdpp_fclt", "fdpp_bsninh", "fdpp_op", "fdpp_dtrp", "fdpp_ocsa", "fdpp_etc"))
            if fclt <= 0:
                continue
        t = F.doc_text(r["rcept_no"])
        time.sleep(0.3)
        reg = use_region(t) if k == "증권신고서" else t
        fac = [re.sub(r"\s+", " ", s).strip() for s in FAC.findall(reg)]
        fac = [s for s in dict.fromkeys(fac) if len(s) > 15][:3]
        if k == "증권신고서" and not any("시설" in s or "공장" in s for s in fac):
            continue
        rows.append({"rcept_dt": r["rcept_dt"], "corp_code": code, "name": r.get("corp_name", ""), "corp_cls": r.get("corp_cls", ""),
                     "induty": indc, "hq": " ".join((c.get("adres") or "").split()[:2]), "report_nm": " ".join(r["report_nm"].split()),
                     "kind": k, "fclt_eok": round(fclt / 1e8, 1) if fclt else "", "total_eok": round(tot / 1e8, 1) if tot else "",
                     "facility_text": " | ".join(s[:150] for s in fac),
                     "places": " / ".join(dict.fromkeys(re.sub(r"\s", "", p) for p in PLACE.findall(reg)))[:120],
                     "abroad": " / ".join(dict.fromkeys(ABROAD.findall(reg)))[:60],
                     "capex": " ; ".join(capex.get(code, [])[:3]), "rcept_no": r["rcept_no"],
                     "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}"})
    if new:
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    rows.sort(key=lambda x: (x["induty"][:2], x["name"], x["rcept_dt"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"저장 {OUT.relative_to(ROOT)} {len(rows)}건(기업개황 새로 {new}곳)", Counter(x["kind"] for x in rows))
    for x in rows:
        print(f"{x['rcept_dt']} | {x['name']} | {x['induty']} | {x['hq']} | {x['kind']} | 시설 {x['fclt_eok']}억/{x['total_eok']}억 | "
              f"{x['facility_text'][:160]} | {x['places'][:60]} | {x['abroad']} | capex:{'있음' if x['capex'] else '없음'}")
    return 0


def today() -> str:
    from datetime import date
    return date.today().strftime("%Y%m%d")


def windows_start(months: int) -> str:
    return next(iter(windows(months)))[0]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
