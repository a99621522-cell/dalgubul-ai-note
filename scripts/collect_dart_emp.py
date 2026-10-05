#!/usr/bin/env python3
"""DART 직원 현황 — 대구 본사 공시 기업(scripts/state/dart_corp.json 의 daegu=true)의 최근 3개 사업연도 사업보고서 '직원 등의 현황'
→ scripts/data/company_employees.csv (운영자 지시 2026-10-05).

OpenDART 사업보고서 주요정보 '직원 현황'(empSttus.json, 사업보고서 11011). 공시 행은 사업부문 × 성별로 나뉘어 있어
회사·연도마다 합계 행이 있으면 그 값을, 없으면 행을 더한다(직원 수·정규직·기간제·연간 급여 총액). 남녀는 성별 행을 더한다.
평균 근속연수·1인 평균 급여는 합계 행 값(없으면 공시 행 값을 직원 수로 가중한 값, avg_method=가중)으로. 개인 정보는 없다(회사 단위 집계).
공시 값과 접수번호 링크만 — 평가·순위 없음. 키: DART_KEY. 사용: python3 scripts/collect_dart_emp.py [--years 3]
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / "state" / "dart_corp.json"
OUT = ROOT / "scripts" / "data" / "company_employees.csv"
API = "https://opendart.fss.or.kr/api"
UA = {"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"}
KEY = os.environ.get("DART_KEY", "").strip()
COLS = ["corp_code", "name", "year", "employees", "regular", "contract", "male", "female", "avg_tenure", "salary_total", "avg_salary",
        "avg_method", "rows", "rcept_no", "source_url", "as_of"]


def num(s) -> float | None:
    s = re.sub(r"[,\s원명]", "", str(s or ""))
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def tenure(s) -> float | None:
    """'10.5', '10년 5개월', '10.5년' → 년(소수)"""
    t = str(s or "").replace(",", "").strip()
    m = re.match(r"^(\d+(?:\.\d+)?)\s*년?\s*(?:(\d+)\s*개월)?$", t)
    if not m:
        return None
    return float(m.group(1)) + (int(m.group(2)) / 12 if m.group(2) else 0)


def get(path: str, **params) -> dict | None:
    params["crtfc_key"] = KEY
    try:
        r = requests.get(f"{API}/{path}", params=params, headers=UA, timeout=30)
        r.raise_for_status()
        j = r.json()
    except Exception as e:  # noqa: BLE001
        msg = re.sub(r"crtfc_key=[^&\s]+", "crtfc_key=***", str(e))
        print(f"[dart_emp] {path} 실패: {msg[:160]}")
        return None
    st = j.get("status")
    if st == "013":
        return {"list": []}
    if st == "020":
        print("[dart_emp] 사용 한도 초과(020) — 여기서 멈춤")
        raise SystemExit(0)
    if st != "000":
        print(f"[dart_emp] {path} 오류 {st}: {j.get('message')}")
        return None
    return j


def is_total(x: dict) -> bool:
    return any(w in str(x.get(k, "")) for k in ("fo_bbm", "sexdstn") for w in ("합계", "총계", "합 계", "전체"))


def summarize(code: str, name: str, y: int, lst: list[dict]) -> dict | None:
    if not lst:
        return None
    tot = [x for x in lst if is_total(x)]
    parts = [x for x in lst if not is_total(x)]
    rec = {"corp_code": code, "name": name, "year": y, "rows": len(lst), "rcept_no": lst[0].get("rcept_no", ""), "as_of": date.today().isoformat()}
    rec["source_url"] = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rec['rcept_no']}" if rec["rcept_no"] else ""
    src = parts or lst
    S = lambda rows, k: sum(v for v in (num(x.get(k)) for x in rows) if v is not None)
    # 합계 행이 하나뿐이면(성별 합계·부문 합계가 겹치지 않을 때) 그 값을 쓴다
    t = tot[0] if len(tot) == 1 else None
    rec["employees"] = num(t.get("sm")) if t and num(t.get("sm")) else S(src, "sm")
    rec["regular"] = num(t.get("rgllbr_co")) if t and num(t.get("rgllbr_co")) is not None else S(src, "rgllbr_co")
    rec["contract"] = num(t.get("cnttk_co")) if t and num(t.get("cnttk_co")) is not None else S(src, "cnttk_co")
    sx = lambda w: sum(v for v in (num(x.get("sm")) for x in src if w in str(x.get("sexdstn", ""))) if v is not None)
    rec["male"], rec["female"] = sx("남"), sx("여")
    rec["salary_total"] = num(t.get("fyer_salary_totamt")) if t and num(t.get("fyer_salary_totamt")) else S(src, "fyer_salary_totamt")
    if t and num(t.get("jan_salary_am")):
        rec["avg_salary"], rec["avg_tenure"], rec["avg_method"] = num(t.get("jan_salary_am")), tenure(t.get("avrg_cnwk_sdytrn")), "합계 행"
    else:
        w = [(num(x.get("sm")) or 0, num(x.get("jan_salary_am")), tenure(x.get("avrg_cnwk_sdytrn"))) for x in src]
        ws = sum(a for a, b, _ in w if b is not None)
        rec["avg_salary"] = sum(a * b for a, b, _ in w if b is not None) / ws if ws else None
        wt = sum(a for a, _, c in w if c is not None)
        rec["avg_tenure"] = sum(a * c for a, _, c in w if c is not None) / wt if wt else None
        rec["avg_method"] = "가중"
    for k in ("avg_salary", "avg_tenure"):
        if isinstance(rec.get(k), float):
            rec[k] = round(rec[k], 2)
    for k in ("employees", "regular", "contract", "male", "female", "salary_total"):
        v = rec.get(k)
        rec[k] = int(v) if isinstance(v, float) and v.is_integer() else v
    return rec


def main(argv: list[str]) -> int:
    if not KEY:
        print("DART_KEY 없음")
        return 0
    years = int(argv[argv.index("--years") + 1]) if "--years" in argv else 3
    corps = {c: v for c, v in json.loads(CACHE.read_text(encoding="utf-8")).items() if v.get("daegu")} if CACHE.exists() else {}
    print(f"[dart_emp] 대구 본사 공시 기업 {len(corps)}곳")
    this = date.today().year
    rows, sample = [], 0
    for i, (code, meta) in enumerate(sorted(corps.items()), 1):
        for y in range(this - years, this):
            j = get("empSttus.json", corp_code=code, bsns_year=y, reprt_code="11011")
            time.sleep(0.15)
            lst = (j or {}).get("list", [])
            if lst and sample < 2:   # 첫 응답 두 개는 구조 확인용으로 찍는다(회사 집계라 개인 정보 없음)
                print(f"[dart_emp] 예시 {meta.get('name')} {y}: {json.dumps(lst[:3], ensure_ascii=False)[:900]}")
                sample += 1
            rec = summarize(code, meta.get("name", ""), y, lst)
            if rec:
                rows.append(rec)
        if i % 20 == 0:
            print(f"[dart_emp] {i}/{len(corps)}곳, 행 {len(rows)}")
    new_keys = {(r["corp_code"], str(r["year"])) for r in rows}
    old = list(csv.DictReader(open(OUT, encoding="utf-8"))) if OUT.exists() else []
    kept = [r for r in old if (r.get("corp_code"), str(r.get("year"))) not in new_keys and int(r.get("year") or 0) >= this - years and r.get("corp_code") in corps]
    out = sorted(kept + rows, key=lambda r: (r["corp_code"], str(r["year"])))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    print(f"저장: {OUT.relative_to(ROOT)} ({len(out)}행 — 새로 {len(rows)} · 기존 유지 {len(kept)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
