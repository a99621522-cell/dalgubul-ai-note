#!/usr/bin/env python3
"""DART 재무 — 대구 본사 공시 기업의 최근 3개 사업연도 주요 계정 → scripts/data/company_financials.csv
(운영자 지시 2026-10-05: DART 에서 대구 본사 기업의 최근 3년 경영 정보를 받아 사이트에 보여 줄 것)

1) 대상 찾기(--discover, 기본 켬): OpenDART 공시검색(list.json)에서 최근 3년 사업보고서(A001)를 낸 회사를 모두 모으고,
   캐시(scripts/state/dart_corp.json)에 없는 회사만 기업개황(company.json)으로 본사 주소를 받아 '대구광역시' 여부를 판정한다.
   캐시에는 회사명·본사 시군구·상장 구분·종목코드·업종코드(KSIC)만 둔다(대표자·전화 등은 저장하지 않는다).
2) 재무: 단일회사 주요계정(fnlttSinglAcnt), 사업보고서(11011), 연결 우선·없으면 개별. 매출액·영업이익·당기순이익·자산총계·부채총계·자본총계.
공시 수치와 접수번호 링크만 기록한다(값을 만들거나 비율·순위를 계산하지 않는다). API 실패는 로그 후 건너뛰고, 못 받은 기업·연도는 기존 행을 남긴다.
키: DART_KEY. 하루 호출 한도(2만 건) 안에서 돌도록 기업개황 조회는 --max-lookups(기본 6000)까지만.

사용: python3 scripts/collect_dart_fin.py [--years 3] [--no-discover] [--max-lookups 6000]
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / "state" / "dart_corp.json"
OUT = ROOT / "scripts" / "data" / "company_financials.csv"
API = "https://opendart.fss.or.kr/api"
UA = {"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"}
REGION_WORDS = ("대구광역시", "대구시")
CORP_CLS = {"Y": "유가증권", "K": "코스닥", "N": "코넥스", "E": "기타"}
# 계정 이름(공시마다 조금씩 다르다) → 열
ACCOUNTS = [
    ("revenue", ("매출액", "수익(매출액)", "영업수익")),
    ("operating_income", ("영업이익", "영업이익(손실)")),
    ("net_income", ("당기순이익", "당기순이익(손실)", "당기순손익")),
    ("total_assets", ("자산총계",)),
    ("total_liabilities", ("부채총계",)),
    ("total_equity", ("자본총계",)),
]
COLS = ["corp_code", "name", "year", "fs", "revenue", "operating_income", "net_income", "total_assets", "total_liabilities",
        "total_equity", "unit", "rcept_no", "source_url", "as_of", "corp_cls", "stock_code", "induty_code", "region"]
KEY = os.environ.get("DART_KEY", "").strip()
CALLS = [0]


def redact(e: object) -> str:
    return re.sub(r"crtfc_key=[^&\s]+", "crtfc_key=***", str(e))


def get(path: str, **params) -> dict | None:
    params["crtfc_key"] = KEY
    CALLS[0] += 1
    for attempt in (1, 2):
        try:
            r = requests.get(f"{API}/{path}", params=params, headers=UA, timeout=30)
            r.raise_for_status()
            j = r.json()
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                print(f"[dart_fin] {path} 실패: {redact(e)[:160]}")
                return None
            time.sleep(3)
    st = j.get("status")
    if st == "013":            # 조회 결과 없음
        return {"list": []}
    if st == "020":            # 사용 한도 초과
        print("[dart_fin] 사용 한도 초과(020) — 이번 실행은 여기서 멈춤")
        raise SystemExit(0)
    if st != "000":
        print(f"[dart_fin] {path} 오류 {st}: {j.get('message')}")
        return None
    return j


def windows(start: date, end: date):
    """공시검색은 회사 지정 없이 3개월까지만 — 90일씩 자른다."""
    s = start
    while s <= end:
        e = min(s + timedelta(days=89), end)
        yield s, e
        s = e + timedelta(days=1)


def annual_filers(years: int) -> dict[str, dict]:
    """최근 years 년 안에 사업보고서(A001)를 낸 회사 corp_code → {name, corp_cls, stock_code}"""
    out: dict[str, dict] = {}
    start = date(date.today().year - years, 1, 1)
    for s, e in windows(start, date.today()):
        page = 1
        while True:
            j = get("list.json", bgn_de=s.strftime("%Y%m%d"), end_de=e.strftime("%Y%m%d"), pblntf_detail_ty="A001",
                    page_no=page, page_count=100)
            if not j:
                break
            for r in j.get("list", []):
                if "사업보고서" in (r.get("report_nm") or ""):
                    out.setdefault(r["corp_code"], {"name": r.get("corp_name", ""), "corp_cls": r.get("corp_cls", ""),
                                                    "stock_code": (r.get("stock_code") or "").strip()})
            total = int(j.get("total_page") or 1)
            if page >= total:
                break
            page += 1
            time.sleep(0.15)
        print(f"[dart_fin] 사업보고서 {s}~{e}: 누적 회사 {len(out)}곳")
    return out


def classify(cache: dict, filers: dict[str, dict], max_lookups: int) -> None:
    n = 0
    for code, f in filers.items():
        hit = cache.get(code)
        if hit and "induty_code" in hit:     # 새 필드까지 채운 캐시
            hit.update({k: v for k, v in f.items() if v})
            continue
        if n >= max_lookups:
            continue
        j = get("company.json", corp_code=code)
        n += 1
        time.sleep(0.12)
        if not j:
            continue
        adres = " ".join((j.get("adres") or "").split())
        cache[code] = {"name": j.get("corp_name") or f["name"], "region": " ".join(adres.split()[:2]),
                       "daegu": any(w in adres for w in REGION_WORDS), "checked": date.today().isoformat(),
                       "corp_cls": j.get("corp_cls") or f["corp_cls"], "stock_code": (j.get("stock_code") or f["stock_code"] or "").strip(),
                       "induty_code": (j.get("induty_code") or "").strip()}
        if n % 200 == 0:
            print(f"[dart_fin] 기업개황 {n}건 조회 (대구 {sum(1 for v in cache.values() if v.get('daegu'))}곳)")
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    left = sum(1 for c in filers if "induty_code" not in cache.get(c, {}))
    print(f"[dart_fin] 기업개황 조회 {n}건, 아직 못 본 회사 {left}곳(다음 실행에)")


def to_num(s: str) -> str:
    s = (s or "").replace(",", "").strip()
    return s if s.lstrip("-").isdigit() else ""


def fin_rows(code: str, meta: dict, years: int) -> list[dict]:
    rows = []
    this_year = date.today().year
    for y in range(this_year - years, this_year):
        j = get("fnlttSinglAcnt.json", corp_code=code, bsns_year=y, reprt_code="11011")
        time.sleep(0.15)
        lst = (j or {}).get("list", [])
        for fs in ("CFS", "OFS"):  # 연결 우선
            sub = [x for x in lst if x.get("fs_div") == fs]
            if not sub:
                continue
            rec = {"corp_code": code, "name": meta["name"], "year": y, "fs": "연결" if fs == "CFS" else "개별", "unit": "원",
                   "rcept_no": sub[0].get("rcept_no", ""), "as_of": date.today().isoformat(),
                   "corp_cls": CORP_CLS.get(meta.get("corp_cls", ""), meta.get("corp_cls", "")), "stock_code": meta.get("stock_code", ""),
                   "induty_code": meta.get("induty_code", ""), "region": meta.get("region", "")}
            rec["source_url"] = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rec['rcept_no']}" if rec["rcept_no"] else ""
            for x in sub:
                nm = (x.get("account_nm") or "").strip()
                for col, names in ACCOUNTS:
                    if nm in names and not rec.get(col):
                        rec[col] = to_num(x.get("thstrm_amount", ""))
            rows.append({c: rec.get(c, "") for c in COLS})
            break
    return rows


def main(argv: list[str]) -> int:
    if not KEY:
        print("DART_KEY 없음")
        return 0
    years = int(argv[argv.index("--years") + 1]) if "--years" in argv else 3
    max_lookups = int(argv[argv.index("--max-lookups") + 1]) if "--max-lookups" in argv else 6000
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    if "--no-discover" not in argv:
        filers = annual_filers(years)
        if filers:
            classify(cache, filers, max_lookups)
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    corps = {c: v for c, v in cache.items() if v.get("daegu")}
    if not corps:
        print("대구 본사 공시 기업이 캐시에 없음")
        return 0
    print(f"[dart_fin] 대구 본사 공시 기업 {len(corps)}곳 — 재무 받기")
    rows = []
    for i, (code, meta) in enumerate(sorted(corps.items()), 1):
        got = fin_rows(code, meta, years)
        rows += got
        if i % 20 == 0:
            print(f"[dart_fin] {i}/{len(corps)}곳, 행 {len(rows)}")
    # 이번에 받지 못한 기업·연도(접속 실패 등)는 기존 행을 남긴다 — 2026-10-01: DART 접속이 모두 실패해 6행이 0행으로 지워졌다
    new_keys = {(r["corp_code"], str(r["year"])) for r in rows}
    old = list(csv.DictReader(open(OUT, encoding="utf-8"))) if OUT.exists() else []
    first = date.today().year - years
    kept = [r for r in old if (r.get("corp_code"), str(r.get("year"))) not in new_keys and int(r.get("year") or 0) >= first
            and r.get("corp_code") in corps]
    out = sorted(kept + rows, key=lambda r: (r["corp_code"], str(r["year"])))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    print(f"저장: {OUT.relative_to(ROOT)} ({len(out)}행 — 새로 받음 {len(rows)} · 기존 유지 {len(kept)}, 기업 {len({r['corp_code'] for r in out})}곳) · API 호출 {CALLS[0]}건")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
