#!/usr/bin/env python3
"""DART 미래 산업 관련 공시 — 대구 본사 공시 기업(scripts/state/dart_corp.json 의 daegu=true)의 최근 12개월 공시 가운데
투자·계약·지분·특허 같은 사업 확장 공시를 골라, 원문 글자에 미래 산업 낱말이 나오는 것만 data/dart/future.csv 로 (운영자 지시 2026-10-05).

1) 공시검색(list.json, 회사별): 제목에 EVENT_WORDS 가 든 공시만(정기보고서·지분 공시 제외).
2) 공시서류원본(document.xml): zip 안 XML 의 글자에서 FIELDS 낱말을 찾아 분야를 붙이고, 처음 나온 곳 앞뒤 짧은 구절(60자 안)을 근거로 남긴다.
   분야 낱말이 하나도 없으면 버린다. 이미 본 접수번호(csv 에 있는 것, scripts/state/dart_future_seen.json)는 다시 받지 않는다.
공시 사실·제목·링크와 근거 구절만 — 평가·전망 없음. DART 에는 회사 보도자료가 없다(공시만).
키: DART_KEY. 사용: python3 scripts/collect_dart_future.py [--months 12] [--max-docs 400]
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
SEEN = ROOT / "scripts" / "state" / "dart_future_seen.json"
OUT = ROOT / "data" / "dart" / "future.csv"
API = "https://opendart.fss.or.kr/api"
UA = {"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"}
KEY = os.environ.get("DART_KEY", "").strip()
COLS = ["rcept_dt", "corp_code", "name", "report_nm", "event", "fields", "keywords", "excerpt", "rcept_no", "url"]

# 사업 확장 공시(제목 낱말 → 구분)
EVENT_WORDS = [
    ("신규시설투자", "시설투자"), ("유형자산취득", "자산취득"), ("유형자산 취득", "자산취득"),
    ("타법인주식및출자증권취득", "지분취득"), ("타법인 주식 및 출자증권 취득", "지분취득"),
    ("단일판매ㆍ공급계약", "공급계약"), ("단일판매·공급계약", "공급계약"), ("공급계약", "공급계약"),
    ("특허권취득", "특허"), ("특허권 취득", "특허"), ("투자판단관련주요경영사항", "주요경영사항"), ("투자판단 관련 주요경영사항", "주요경영사항"),
    ("영업양수", "영업양수"), ("자산양수", "자산양수"), ("회사합병", "합병"), ("회사분할", "분할"), ("유상증자결정", "유상증자"),
    ("기술도입", "기술"), ("기술이전", "기술"), ("신규사업", "신규사업"),
]
# 미래 산업 분야 낱말(원문 글자에서 찾음). 영문 약어는 앞뒤가 영문자가 아닐 때만
FIELDS = {
    "반도체": ["반도체", "웨이퍼", "파운드리", "전력반도체", "SiC", "GaN", "HBM"],
    "2차전지": ["2차전지", "이차전지", "배터리", "전고체", "양극재", "음극재", "전해질", "분리막", "ESS"],
    "미래차·모빌리티": ["전기차", "전기자동차", "자율주행", "수소차", "전장부품", "UAM", "도심항공", "SDV", "모빌리티"],
    "로봇": ["로봇", "휴머노이드"],
    "AI·SW": ["인공지능", "AI", "데이터센터", "클라우드"],
    "수소·에너지": ["수소", "연료전지", "태양광", "풍력", "SMR", "소형모듈원전", "신재생"],
    "바이오·의료": ["바이오", "의료기기", "체외진단", "신약", "디지털헬스", "헬스케어"],
    "방산·항공우주": ["방위산업", "방산", "항공기", "우주", "위성", "드론"],
}
ABBR = re.compile(r"^[A-Za-z]+$")


def get_json(path: str, **params) -> dict | None:
    params["crtfc_key"] = KEY
    try:
        r = requests.get(f"{API}/{path}", params=params, headers=UA, timeout=30)
        r.raise_for_status()
        j = r.json()
    except Exception as e:  # noqa: BLE001
        msg = re.sub(r"crtfc_key=[^&\s]+", "crtfc_key=***", str(e))
        print(f"[dart_future] {path} 실패: {msg[:160]}")
        return None
    st = j.get("status")
    if st == "013":
        return {"list": []}
    if st == "020":
        print("[dart_future] 사용 한도 초과(020) — 여기서 멈춤")
        raise SystemExit(0)
    if st != "000":
        print(f"[dart_future] {path} 오류 {st}: {j.get('message')}")
        return None
    return j


def doc_text(rcept_no: str) -> str:
    try:
        r = requests.get(f"{API}/document.xml", params={"crtfc_key": KEY, "rcept_no": rcept_no}, headers=UA, timeout=60)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
    except Exception as e:  # noqa: BLE001
        print(f"[dart_future] 원문 {rcept_no} 실패: {str(e)[:120]}")
        return ""
    parts = []
    for n in z.namelist():
        raw = z.read(n)
        for enc in ("utf-8", "euc-kr", "cp949"):
            try:
                t = raw.decode(enc)
                break
            except UnicodeDecodeError:
                t = ""
        t = re.sub(r"<[^>]+>", " ", t)
        parts.append(re.sub(r"&[a-z#0-9]+;", " ", t))
    return re.sub(r"\s+", " ", " ".join(parts))


def find_fields(text: str) -> tuple[list[str], list[str], str]:
    fields, kws, first = [], [], None
    for f, words in FIELDS.items():
        for w in words:
            pat = rf"(?<![A-Za-z]){re.escape(w)}(?![A-Za-z])" if ABBR.match(w) else re.escape(w)
            m = re.search(pat, text)
            if m:
                if f not in fields:
                    fields.append(f)
                kws.append(w)
                if first is None or m.start() < first.start():
                    first = m
    excerpt = ""
    if first:
        s = max(0, first.start() - 25)
        excerpt = text[s: first.end() + 30].strip()
        excerpt = ("…" if s else "") + excerpt[:60] + "…"
    return fields, kws, excerpt


def event_of(title: str) -> str:
    for w, ev in EVENT_WORDS:
        if w in title:
            return ev
    return ""


def main(argv: list[str]) -> int:
    if not KEY:
        print("DART_KEY 없음")
        return 0
    months = int(argv[argv.index("--months") + 1]) if "--months" in argv else 12
    max_docs = int(argv[argv.index("--max-docs") + 1]) if "--max-docs" in argv else 400
    corps = {c: v for c, v in json.loads(CACHE.read_text(encoding="utf-8")).items() if v.get("daegu")} if CACHE.exists() else {}
    if not corps:
        print("대구 본사 공시 기업 캐시가 비어 있음(collect_dart_fin.py 가 채운다)")
        return 0
    old = list(csv.DictReader(open(OUT, encoding="utf-8"))) if OUT.exists() else []
    seen = set(json.loads(SEEN.read_text(encoding="utf-8"))) if SEEN.exists() else set()
    seen |= {r["rcept_no"] for r in old}
    bgn = (date.today() - timedelta(days=months * 31)).strftime("%Y%m%d")
    end = date.today().strftime("%Y%m%d")
    cand = []
    for code, meta in sorted(corps.items()):
        page = 1
        while True:
            j = get_json("list.json", corp_code=code, bgn_de=bgn, end_de=end, page_no=page, page_count=100)
            time.sleep(0.12)
            if not j:
                break
            for r in j.get("list", []):
                ev = event_of(r.get("report_nm") or "")
                if ev and "철회" not in r["report_nm"] and r["rcept_no"] not in seen:
                    cand.append((code, meta.get("name") or r.get("corp_name", ""), r, ev))
            if page >= int(j.get("total_page") or 1):
                break
            page += 1
    print(f"[dart_future] 대구 본사 {len(corps)}곳 · 새 확장 공시 후보 {len(cand)}건")
    new = []
    for i, (code, name, r, ev) in enumerate(cand[:max_docs], 1):
        text = doc_text(r["rcept_no"])
        time.sleep(0.2)
        seen.add(r["rcept_no"])
        if not text:
            seen.discard(r["rcept_no"])    # 원문을 못 받으면 다음에 다시
            continue
        fields, kws, excerpt = find_fields(text)
        if fields:
            new.append({"rcept_dt": r.get("rcept_dt", ""), "corp_code": code, "name": name, "report_nm": " ".join(r["report_nm"].split()),
                        "event": ev, "fields": "·".join(fields), "keywords": "·".join(dict.fromkeys(kws)), "excerpt": excerpt,
                        "rcept_no": r["rcept_no"], "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}"})
        if i % 50 == 0:
            print(f"[dart_future] 원문 {i}건 확인, 미래 산업 낱말 있음 {len(new)}건")
    cut = (date.today() - timedelta(days=months * 31)).strftime("%Y%m%d")
    rows = [r for r in old if r["rcept_dt"] >= cut] + new
    rows.sort(key=lambda r: (r["rcept_dt"], r["rcept_no"]), reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    SEEN.write_text(json.dumps(sorted(seen)) + "\n", encoding="utf-8")
    print(f"[dart_future] 새로 {len(new)}건 · 전체 {len(rows)}건 → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
