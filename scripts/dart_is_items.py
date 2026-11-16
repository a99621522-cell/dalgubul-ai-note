#!/usr/bin/env python3
"""대구 본사 상장사 분기 손익계산서 전체 항목 → data/dart/is_items_<연도>q<n>.csv (운영자 지시 2026-11-16 '이유도 붙여').

분기보고서는 경영진단을 생략해 회사별 실적 증감 이유가 비어 있으므로, 공시 손익계산서의 항목(매출원가·판관비·금융손익·기타손익·
지분법·법인세·중단영업 등)을 3개월·누적, 당기·전년 같은 기간으로 받아 '공시 숫자로 본 증감 내역'을 만들 재료로 쓴다.
DART 단일회사 전체 재무제표(fnlttSinglAcntAll) — 연결(CFS) 먼저, 없으면 별도(OFS). 대상은 scripts/state/dart_corp.json 의
daegu·유가증권/코스닥. 값 그대로(원), 해석 없음. 사이트는 읽지 않는다. 키 DART_KEY.
사용: python3 scripts/dart_is_items.py [--year 2026] [--reprt 11014]   (11013 1분기·11012 반기·11014 3분기)
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_dart_future as F  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / "state" / "dart_corp.json"
COLS = ["corp_code", "name", "fs", "sj_div", "ord", "account_id", "account_nm", "thstrm_amount", "frmtrm_q_amount",
        "thstrm_add_amount", "frmtrm_add_amount", "rcept_no"]


def main(argv: list[str]) -> int:
    year = argv[argv.index("--year") + 1] if "--year" in argv else "2026"
    reprt = argv[argv.index("--reprt") + 1] if "--reprt" in argv else "11014"
    q = {"11013": 1, "11012": 2, "11014": 3, "11011": 4}[reprt]
    if not F.KEY:
        print("DART_KEY 없음")
        return 0
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    corps = {c: v for c, v in cache.items() if v.get("daegu") and v.get("corp_cls") in ("Y", "K")}
    rows, got = [], 0
    for code, v in sorted(corps.items(), key=lambda kv: kv[1].get("name") or ""):
        for fs in ("CFS", "OFS"):
            j = F.get_json("fnlttSinglAcntAll.json", corp_code=code, bsns_year=year, reprt_code=reprt, fs_div=fs) or {}
            time.sleep(0.2)
            lst = [x for x in j.get("list", []) if x.get("sj_div") in ("IS", "CIS")]
            if lst:
                got += 1
                for x in lst:
                    rows.append({"corp_code": code, "name": v.get("name"), "fs": "연결" if fs == "CFS" else "별도",
                                 **{k: (x.get(k) or "").strip() for k in COLS if k not in ("corp_code", "name", "fs")}})
                print(f"{v.get('name')}: {fs} 손익 항목 {len(lst)}개")
                break
        else:
            print(f"{v.get('name')}: 없음")
    out = ROOT / "data" / "dart" / f"is_items_{year}q{q}.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"저장 {out.relative_to(ROOT)} {len(rows)}행 · 회사 {got}/{len(corps)}곳")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
