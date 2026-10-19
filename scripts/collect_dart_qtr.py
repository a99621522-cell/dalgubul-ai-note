#!/usr/bin/env python3
"""DART 분기 실적 — 대구 본사 상장회사(유가증권·코스닥)의 분기별 매출액·영업이익·당기순이익과 실적 관련 공시
(운영자 지시 2026-10-12 '넣어, 실적 이유와 포워드 가이던스도 있어?').

1) 분기 실적 → scripts/data/company_financials_q.csv
   단일회사 주요계정(fnlttSinglAcnt)을 1분기(11013)·반기(11012)·3분기(11014)·사업보고서(11011)로 받는다. 연결 우선·없으면 개별.
   손익 계정의 thstrm_amount(당기 3개월)·thstrm_add_amount(당기 누적)·frmtrm_amount(전년 같은 분기)를 그대로 적고,
   4분기는 따로 공시되지 않으므로 '사업보고서 연간 − 3분기 누적'(같은 연결·개별 기준일 때만)으로 계산해 derived=1 로 표시한다.
   재무상태(자산·부채·자본총계)는 그 분기 말 값(thstrm_amount)과 같은 보고서의 비교 시점 값(frmtrm_amount — 분기·반기는 전기말,
   사업보고서는 전년말)을 *_prev 로 적는다(운영자 지시 2026-10-19 '상반기 재무제표 업데이트해').
   코넥스는 분기·반기보고서 제출 의무가 없어 대상에서 뺀다.
2) 실적 관련 공시 → data/dart/performance.csv
   공시검색(list.json, 회사별)에서 제목으로 ① 영업(잠정)실적 ② 매출액 또는 손익구조 30%(대규모법인 15%) 이상 변동 ③ 영업실적 등에 대한 전망을 골라
   공시서류원본(document.xml)에서 '변동 주요원인'·'전망' 항목 뒤 짧은 구절(120자 안)을 회사 공시 문구 그대로 남긴다. 평가·해석 없음.
공시 수치·문구와 접수번호 링크만. API 실패는 로그 후 건너뛰고 못 받은 회사·분기는 기존 행을 남긴다. 키: DART_KEY.

사용: python3 scripts/collect_dart_qtr.py [--quarters 6] [--months 15] [--probe 회사명]
  --probe: 그 회사의 주요계정 응답 원문 일부와 실적 공시 원문 글자 앞부분을 로그로만(저장 안 함) — 필드·문구 위치 확인용
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / "state" / "dart_corp.json"
OUT_Q = ROOT / "scripts" / "data" / "company_financials_q.csv"
OUT_P = ROOT / "data" / "dart" / "performance.csv"
API = "https://opendart.fss.or.kr/api"
UA = {"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"}
KEY = os.environ.get("DART_KEY", "").strip()
CALLS = [0]
LISTED = {"Y": "유가증권", "K": "코스닥"}
REPRT = {1: "11013", 2: "11012", 3: "11014", 4: "11011"}
QEND = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
DUE_DAYS = {1: 45, 2: 45, 3: 45, 4: 90}   # 분기·반기 45일, 사업보고서 90일(자본시장법 제159·160조)
ACCOUNTS = [
    ("revenue", ("매출액", "수익(매출액)", "영업수익")),
    ("operating_income", ("영업이익", "영업이익(손실)")),
    ("net_income", ("당기순이익", "당기순이익(손실)", "당기순손익")),
]
BS_ACCOUNTS = [
    ("total_assets", ("자산총계",)),
    ("total_liabilities", ("부채총계",)),
    ("total_equity", ("자본총계",)),
]
COLS_Q = ["corp_code", "name", "corp_cls", "stock_code", "year", "quarter", "fs",
          "revenue", "operating_income", "net_income",
          "revenue_cum", "operating_income_cum", "net_income_cum",
          "revenue_prev", "operating_income_prev", "net_income_prev",
          "total_assets", "total_liabilities", "total_equity",
          "total_assets_prev", "total_liabilities_prev", "total_equity_prev",
          "derived", "unit", "rcept_no", "source_url", "as_of"]
COLS_P = ["rcept_dt", "corp_code", "name", "kind", "report_nm", "excerpt", "rcept_no", "url"]
# 제목 → 구분. 정정 공시는 같은 회사·같은 구분의 최근 것만 남긴다
KINDS = [
    ("영업실적등에대한전망", "실적 전망"), ("영업실적 등에 대한 전망", "실적 전망"),
    ("매출액또는손익구조", "손익구조 변동"), ("매출액 또는 손익구조", "손익구조 변동"),
    ("영업(잠정)실적", "잠정실적"), ("영업(잠정) 실적", "잠정실적"),
]
# 원문에서 구절을 찾을 항목 이름(앞에서부터 처음 나오는 것)
REASON_KEYS = {
    "손익구조 변동": ["주요원인", "변동원인", "변동 원인"],
    "실적 전망": ["전망내용", "전망 내용", "예측내용", "예측치", "전망치", "전망"],
    "잠정실적": [],
}


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
                print(f"[dart_qtr] {path} 실패: {redact(e)[:160]}")
                return None
            time.sleep(3)
    st = j.get("status")
    if st == "013":
        return {"list": []}
    if st == "020":
        print("[dart_qtr] 사용 한도 초과(020) — 여기서 멈춤")
        raise SystemExit(0)
    if st != "000":
        print(f"[dart_qtr] {path} 오류 {st}: {j.get('message')}")
        return None
    return j


def doc_text(rcept_no: str) -> str:
    try:
        r = requests.get(f"{API}/document.xml", params={"crtfc_key": KEY, "rcept_no": rcept_no}, headers=UA, timeout=60)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
    except Exception as e:  # noqa: BLE001
        print(f"[dart_qtr] 원문 {rcept_no} 실패: {redact(e)[:120]}")
        return ""
    parts = []
    for n in z.namelist():
        raw = z.read(n)
        t = ""
        for enc in ("utf-8", "euc-kr", "cp949"):
            try:
                t = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        t = re.sub(r"<[^>]+>", " ", t)
        parts.append(re.sub(r"&[a-z#0-9]+;", " ", t))
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def to_num(s: str) -> str:
    s = (s or "").replace(",", "").strip()
    return s if s.lstrip("-").isdigit() else ""


def due(year: int, q: int) -> date:
    m, d = QEND[q]
    return date(year, m, d) + timedelta(days=DUE_DAYS[q])


def periods(n: int) -> list[tuple[int, int]]:
    """마감이 지난 최근 n개 분기(오래된 것부터)"""
    out, y, q = [], date.today().year, 4
    while len(out) < n and y >= date.today().year - 3:
        if due(y, q) <= date.today():
            out.append((y, q))
        q -= 1
        if q == 0:
            y, q = y - 1, 4
    return out[::-1]


def pick(lst: list[dict], fs: str) -> dict:
    """그 기준(CFS/OFS) 손익 계정 → {col: {amt, cum, prev}}"""
    got: dict[str, dict] = {}
    for x in lst:
        if x.get("fs_div") != fs:
            continue
        nm = (x.get("account_nm") or "").strip()
        for col, names in ACCOUNTS:
            if nm in names and col not in got:
                got[col] = {"amt": to_num(x.get("thstrm_amount", "")), "cum": to_num(x.get("thstrm_add_amount", "")),
                            "prev": to_num(x.get("frmtrm_amount", "")), "rcept_no": x.get("rcept_no", "")}
        for col, names in BS_ACCOUNTS:
            if nm in names and col not in got and x.get("sj_div") in ("BS", "", None):
                got[col] = {"amt": to_num(x.get("thstrm_amount", "")), "prev": to_num(x.get("frmtrm_amount", "")),
                            "rcept_no": x.get("rcept_no", "")}
    return got


def quarter_rows(code: str, meta: dict, pers: list[tuple[int, int]], probe: bool) -> list[dict]:
    raw: dict[tuple[int, int], list[dict]] = {}
    need = set(pers) | {(y, 3) for (y, q) in pers if q == 4}      # 4분기 계산에 3분기 누적이 필요
    for (y, q) in sorted(need):
        j = get("fnlttSinglAcnt.json", corp_code=code, bsns_year=y, reprt_code=REPRT[q])
        time.sleep(0.15)
        raw[(y, q)] = (j or {}).get("list", [])
        if probe and raw[(y, q)]:
            print(f"== probe {meta['name']} {y} {q}분기 ({REPRT[q]}) 응답 키: {sorted(raw[(y, q)][0].keys())}")
            for x in raw[(y, q)][:12]:
                print("   ", {k: x.get(k) for k in ("fs_div", "sj_div", "account_nm", "thstrm_nm", "thstrm_amount", "thstrm_add_amount", "frmtrm_amount", "frmtrm_add_amount")})
    rows = []
    for (y, q) in pers:
        lst = raw.get((y, q)) or []
        for fs in ("CFS", "OFS"):
            got = pick(lst, fs)
            if not got:
                continue
            rec = {"corp_code": code, "name": meta.get("name", ""), "corp_cls": LISTED.get(meta.get("corp_cls", ""), ""),
                   "stock_code": meta.get("stock_code", ""), "year": y, "quarter": q, "fs": "연결" if fs == "CFS" else "개별",
                   "unit": "원", "as_of": date.today().isoformat(), "derived": ""}
            rec["rcept_no"] = next((v["rcept_no"] for v in got.values() if v.get("rcept_no")), "")
            rec["source_url"] = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rec['rcept_no']}" if rec["rcept_no"] else ""
            for col, _ in BS_ACCOUNTS:
                rec[col] = got.get(col, {}).get("amt", "")
                rec[col + "_prev"] = got.get(col, {}).get("prev", "")
            if q < 4:
                for col, _ in ACCOUNTS:
                    v = got.get(col, {})
                    rec[col] = v.get("amt", "")
                    rec[col + "_cum"] = v.get("cum", "") or (v.get("amt", "") if q == 1 else "")
                    rec[col + "_prev"] = v.get("prev", "")
            else:
                q3 = pick(raw.get((y, 3)) or [], fs)
                ok = False
                for col, _ in ACCOUNTS:
                    a = got.get(col, {}).get("amt", "")
                    c3 = q3.get(col, {}).get("cum", "")
                    rec[col + "_cum"] = a                                 # 연간 = 4분기 누적
                    if a and c3:
                        rec[col] = str(int(a) - int(c3))
                        ok = True
                    else:
                        rec[col] = ""
                    rec[col + "_prev"] = ""                               # 전년 4분기는 전년 행에서
                rec["derived"] = "1" if ok else ""
            rows.append({c: rec.get(c, "") for c in COLS_Q})
            break
    return rows


def kind_of(title: str) -> str:
    t = title.replace(" ", "")
    for w, k in KINDS:
        if w.replace(" ", "") in t:
            return k
    return ""


def excerpt_of(kind: str, text: str) -> str:
    for key in REASON_KEYS.get(kind, []):
        m = re.search(re.escape(key), text)
        if m:
            s = text[m.end(): m.end() + 160].strip(" :-·)")
            s = re.split(r"\s(?:\d{1,2}\s*\.|※|\[)", s)[0].strip()      # 다음 항목 번호 앞에서 끊는다
            return (s[:120] + "…") if len(s) > 120 else s
    return ""


def perf_rows(code: str, meta: dict, months: int, seen: set, probe: bool, max_docs: list[int]) -> list[dict]:
    bgn = (date.today() - timedelta(days=months * 31)).strftime("%Y%m%d")
    end = date.today().strftime("%Y%m%d")
    out, page = [], 1
    while True:
        j = get("list.json", corp_code=code, bgn_de=bgn, end_de=end, page_no=page, page_count=100)
        time.sleep(0.12)
        if not j:
            break
        for r in j.get("list", []):
            k = kind_of(r.get("report_nm") or "")
            if not k or "철회" in r["report_nm"] or r["rcept_no"] in seen:
                continue
            ex = ""
            if REASON_KEYS.get(k) and max_docs[0] > 0:
                text = doc_text(r["rcept_no"])
                max_docs[0] -= 1
                time.sleep(0.2)
                ex = excerpt_of(k, text)
                if probe:
                    print(f"== probe 원문 {k} {r['rcept_dt']} {r['report_nm']}\n   {text[:900]}\n   → 구절: {ex}")
            out.append({"rcept_dt": r.get("rcept_dt", ""), "corp_code": code, "name": meta.get("name") or r.get("corp_name", ""),
                        "kind": k, "report_nm": " ".join((r.get("report_nm") or "").split()), "excerpt": ex,
                        "rcept_no": r["rcept_no"], "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}"})
        if page >= int(j.get("total_page") or 1):
            break
        page += 1
    return out


def main(argv: list[str]) -> int:
    if not KEY:
        print("DART_KEY 없음")
        return 0
    nq = int(argv[argv.index("--quarters") + 1]) if "--quarters" in argv else 6
    months = int(argv[argv.index("--months") + 1]) if "--months" in argv else 15
    probe = argv[argv.index("--probe") + 1] if "--probe" in argv else ""
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    corps = {c: v for c, v in cache.items() if v.get("daegu") and v.get("corp_cls") in LISTED}
    if probe:
        corps = {c: v for c, v in corps.items() if probe in (v.get("name") or "")}
    if not corps:
        print("대상 회사 없음(대구 본사 유가증권·코스닥, collect_dart_fin.py 캐시)")
        return 0
    pers = periods(nq)
    print(f"[dart_qtr] 대구 본사 상장 {len(corps)}곳 · 분기 {', '.join(f'{y}.{q}Q' for y, q in pers)}")
    qrows, prows = [], []
    old_p = list(csv.DictReader(open(OUT_P, encoding="utf-8"))) if OUT_P.exists() else []
    seen = {r["rcept_no"] for r in old_p}
    max_docs = [400]
    for i, (code, meta) in enumerate(sorted(corps.items()), 1):
        qrows += quarter_rows(code, meta, pers, bool(probe))
        prows += perf_rows(code, meta, months, seen, bool(probe), max_docs)
        if i % 10 == 0:
            print(f"[dart_qtr] {i}/{len(corps)}곳 · 분기 행 {len(qrows)} · 실적 공시 {len(prows)}")
    if probe:
        print(f"[dart_qtr] probe 끝 — 분기 행 {len(qrows)}, 실적 공시 {len(prows)}, API {CALLS[0]}건(저장 안 함)")
        for r in qrows:
            print("   ", {k: r[k] for k in ("year", "quarter", "fs", "revenue", "revenue_cum", "revenue_prev", "operating_income", "derived")})
        return 0
    # 분기: 이번에 받은 (회사, 연, 분기)는 바꾸고 나머지 기존 행은 남긴다(접속 실패 대비), 범위 밖 분기는 버린다
    keep_from = pers[0] if pers else (0, 0)
    new_keys = {(r["corp_code"], str(r["year"]), str(r["quarter"])) for r in qrows}
    old_q = list(csv.DictReader(open(OUT_Q, encoding="utf-8"))) if OUT_Q.exists() else []
    kept = [r for r in old_q if (r["corp_code"], r["year"], r["quarter"]) not in new_keys
            and (int(r["year"]), int(r["quarter"])) >= keep_from and r["corp_code"] in corps]
    out_q = sorted(kept + qrows, key=lambda r: (r["corp_code"], int(r["year"]), int(r["quarter"])))
    OUT_Q.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_Q, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS_Q, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_q)
    # 실적 공시: 기존 + 새 것, 기간 밖은 버리고 같은 회사·구분·같은 날 정정본은 최근 접수번호만
    cutoff = (date.today() - timedelta(days=months * 31)).strftime("%Y%m%d")
    allp = [r for r in old_p + prows if r["rcept_dt"] >= cutoff]
    best: dict[tuple, dict] = {}
    for r in allp:
        base = re.sub(r"^\[[^\]]+\]", "", r["report_nm"]).strip()
        k = (r["corp_code"], r["kind"], base, r["rcept_dt"][:6])
        if k not in best or r["rcept_no"] > best[k]["rcept_no"]:
            best[k] = r
    out_p = sorted(best.values(), key=lambda r: (r["rcept_dt"], r["rcept_no"]), reverse=True)
    OUT_P.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_P, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS_P, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_p)
    print(f"저장: {OUT_Q.relative_to(ROOT)} {len(out_q)}행(기업 {len({r['corp_code'] for r in out_q})}곳) · "
          f"{OUT_P.relative_to(ROOT)} {len(out_p)}건 · API {CALLS[0]}건")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
