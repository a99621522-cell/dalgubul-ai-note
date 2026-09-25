#!/usr/bin/env python3
"""DART 재무 — 대구 본사 공시 기업(scripts/state/dart_corp.json 의 daegu=true)의 매출액·영업이익·당기순이익 → scripts/data/company_financials.csv

OpenDART 단일회사 주요계정 API(fnlttSinglAcnt): 사업보고서(11011) 연결 우선, 없으면 개별. 최근 3개 사업연도.
키: DART_KEY. 대구 기업 판정은 collect_dart.py 가 캐시에 쌓는다(이 스크립트는 캐시만 읽는다).
공시 수치와 접수번호 링크만 기록한다. 평가 없음. API 실패는 로그 후 건너뜀.

사용: python3 scripts/collect_dart_fin.py [--years 3]
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / "state" / "dart_corp.json"
OUT = ROOT / "scripts" / "data" / "company_financials.csv"
API = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
ACCOUNTS = {"매출액": "revenue", "영업이익": "operating_income", "당기순이익": "net_income"}
COLS = ["corp_code", "name", "year", "fs", "revenue", "operating_income", "net_income", "unit", "rcept_no", "source_url", "as_of"]


def fetch(key: str, corp_code: str, year: int) -> list[dict]:
    try:
        r = requests.get(API, params={"crtfc_key": key, "corp_code": corp_code, "bsns_year": year, "reprt_code": "11011"}, timeout=30)
        r.raise_for_status()
        j = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[dart_fin] {corp_code} {year} 실패: {e}")
        return []
    if j.get("status") != "000":
        return []
    return j.get("list", [])


def to_num(s: str) -> str:
    s = (s or "").replace(",", "").strip()
    return s if s.lstrip("-").isdigit() else ""


def main(argv: list[str]) -> int:
    key = os.environ.get("DART_KEY", "").strip()
    if not key:
        print("DART_KEY 없음")
        return 1
    years = int(argv[argv.index("--years") + 1]) if "--years" in argv else 3
    corps = {c: v for c, v in json.loads(CACHE.read_text(encoding="utf-8")).items() if v.get("daegu")} if CACHE.exists() else {}
    if not corps:
        print("대구 공시 기업 캐시가 비어 있음 (collect_dart.py 가 채운다)")
        return 1
    rows = []
    this_year = date.today().year
    for code, meta in corps.items():
        for y in range(this_year - years, this_year):
            lst = fetch(key, code, y)
            time.sleep(0.2)
            if not lst:
                continue
            for fs in ("CFS", "OFS"):  # 연결 우선
                sub = [x for x in lst if x.get("fs_div") == fs]
                if not sub:
                    continue
                rec = {"corp_code": code, "name": meta["name"], "year": y, "fs": "연결" if fs == "CFS" else "개별", "unit": "원",
                       "rcept_no": sub[0].get("rcept_no", ""), "as_of": date.today().isoformat()}
                rec["source_url"] = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rec['rcept_no']}" if rec["rcept_no"] else ""
                for x in sub:
                    k = ACCOUNTS.get((x.get("account_nm") or "").strip())
                    if k:
                        rec[k] = to_num(x.get("thstrm_amount", ""))
                rows.append({c: rec.get(c, "") for c in COLS})
                break
        print(f"[dart_fin] {meta['name']}: {sum(1 for r in rows if r['corp_code'] == code)}개 연도")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"저장: {OUT.relative_to(ROOT)} ({len(rows)}행, 기업 {len(corps)}곳)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
