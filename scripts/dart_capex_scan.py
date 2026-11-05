#!/usr/bin/env python3
"""대구 본사 DART 공시 회사의 최근 3년 시설투자·자금조달 공시 목록 — 국민성장펀드 요건 대조 조사용(운영자 지시 2026-11-05).

대상: scripts/state/dart_corp.json(daegu=true)과 scripts/state/dart_audit_corp.json(본점 주소가 '대구')의 회사.
공시검색(list.json, 회사별, 최근 --months 개월)에서 제목이 신규시설투자·유형자산 취득·유상증자·전환사채·신주인수권부사채·
교환사채 결정인 공시만 data/dart/capex_scan.csv 로. 신규시설투자·유형자산 취득은 원문(document.xml)에서 투자 대상·금액·목적·
기간 줄을 짧게(200자 안) 옮긴다. 공시 사실·제목·링크만 — 평가 없음, 사이트는 읽지 않는다.
키: DART_KEY. 사용: python3 scripts/dart_capex_scan.py [--months 36]
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_dart_future as F  # noqa: E402  get_json·doc_text 재사용

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "dart" / "capex_scan.csv"
COLS = ["rcept_dt", "corp_code", "name", "district", "corp_cls", "report_nm", "kind", "detail", "rcept_no", "url"]
KINDS = [("신규시설투자", "신규시설투자"), ("유형자산취득", "유형자산 취득"), ("유형자산 취득", "유형자산 취득"), ("유형자산양수", "유형자산 취득"),
         ("유상증자결정", "유상증자"), ("전환사채권발행결정", "전환사채"), ("신주인수권부사채권발행결정", "신주인수권부사채"), ("교환사채권발행결정", "교환사채")]


def kind_of(t: str) -> str:
    t = t.replace(" ", "")
    for w, k in KINDS:
        if w in t:
            return k
    return ""


def detail_of(text: str) -> str:
    out = []
    for lab in ("투자구분", "투자대상", "투자금액", "자기자본대비", "투자목적", "투자기간", "취득자산", "취득금액", "취득목적"):
        m = re.search(lab + r"[^0-9가-힣A-Za-z]{0,6}(.{0,60}?)(?=\s*\d\.\s|\s*[가-힣]+\s*\(원\)|$)", text)
        if m and m.group(1).strip():
            out.append(f"{lab} {m.group(1).strip()}")
    return " · ".join(out)[:200]


def main(argv: list[str]) -> int:
    months = int(argv[argv.index("--months") + 1]) if "--months" in argv else 36
    if not F.KEY:
        print("DART_KEY 없음")
        return 0
    corps = {}
    for c, v in json.load(open(ROOT / "scripts/state/dart_corp.json", encoding="utf-8")).items():
        if v.get("daegu"):
            corps[c] = (v.get("name", ""), (v.get("region") or "").split(" ")[-1], v.get("corp_cls", ""))
    for c, v in json.load(open(ROOT / "scripts/state/dart_audit_corp.json", encoding="utf-8")).items():
        if (v.get("region") or "").startswith("대구") and c not in corps:
            corps[c] = (v.get("name", ""), v.get("district", ""), v.get("cls", ""))
    bgn = (date.today() - timedelta(days=months * 31)).strftime("%Y%m%d")
    end = date.today().strftime("%Y%m%d")
    print(f"대상 {len(corps)}곳, {bgn}~{end}")
    rows = []
    for i, (code, (name, dist, cls)) in enumerate(sorted(corps.items())):
        page = 1
        while True:
            j = F.get_json("list.json", corp_code=code, bgn_de=bgn, end_de=end, page_no=page, page_count=100)
            time.sleep(0.15)
            if not j:
                break
            for r in j.get("list", []):
                k = kind_of(r.get("report_nm", ""))
                if not k or "철회" in r["report_nm"]:
                    continue
                det = ""
                if k in ("신규시설투자", "유형자산 취득"):
                    det = detail_of(F.doc_text(r["rcept_no"]))
                    time.sleep(0.3)
                rows.append({"rcept_dt": r["rcept_dt"], "corp_code": code, "name": name, "district": dist, "corp_cls": cls,
                             "report_nm": " ".join(r["report_nm"].split()), "kind": k, "detail": det, "rcept_no": r["rcept_no"],
                             "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}"})
            if page >= int(j.get("total_page") or 1):
                break
            page += 1
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}곳, 공시 {len(rows)}건")
    rows.sort(key=lambda r: (r["name"], r["rcept_dt"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(f"저장 {OUT.relative_to(ROOT)} {len(rows)}건", Counter(r["kind"] for r in rows), f"회사 {len({r['corp_code'] for r in rows})}곳")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
