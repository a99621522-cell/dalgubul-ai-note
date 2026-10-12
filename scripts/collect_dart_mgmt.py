#!/usr/bin/env python3
"""DART 경영진 진단·방향 — 대구 본사 상장회사(유가증권·코스닥·코넥스)의 최근 사업보고서에서
'이사의 경영진단 및 분석의견'(회사 상황·향후 전망)과 '신규사업 등의 내용 및 전망'의 회사 공시 문구를 짧게 뽑는다
(운영자 지시 2026-10-12 '회사의 상황이나 향후 기업운영 방향, 신사업 진출 등 경영진의 방향을 넣어').

공시서류원본(document.xml)의 글자에서 절 제목을 찾아 그 아래 문장을 앞에서부터 220자 안으로 자른다. 이 사이트가 요약·해석하지 않는다(회사 문구 그대로, 출처 링크).
문구가 '해당사항 없음'·'기재하지 않음' 같은 생략 문구면 비운다. 이미 본 접수번호는 다시 받지 않는다(같은 회사의 새 사업보고서가 나오면 바꾼다).
→ data/dart/mgmt.csv. 키: DART_KEY. 사용: python3 scripts/collect_dart_mgmt.py [--probe 회사명]
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
OUT = ROOT / "data" / "dart" / "mgmt.csv"
API = "https://opendart.fss.or.kr/api"
UA = {"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"}
KEY = os.environ.get("DART_KEY", "").strip()
COLS = ["corp_code", "name", "report_year", "rcept_dt", "overview", "outlook", "new_biz", "rcept_no", "url"]
LISTED = ("Y", "K", "N")
MAXLEN = 220
SKIP = re.compile(r"^(해당\s*사항\s*(이|은)?\s*없|기재\s*(하지\s*)?(않|생략)|작성\s*(하지\s*)?(않|생략)|생략|없습니다|-$)")


def redact(e: object) -> str:
    return re.sub(r"crtfc_key=[^&\s]+", "crtfc_key=***", str(e))


def get(path: str, **params) -> dict | None:
    params["crtfc_key"] = KEY
    try:
        r = requests.get(f"{API}/{path}", params=params, headers=UA, timeout=30)
        r.raise_for_status()
        j = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[dart_mgmt] {path} 실패: {redact(e)[:160]}")
        return None
    st = j.get("status")
    if st == "013":
        return {"list": []}
    if st == "020":
        print("[dart_mgmt] 사용 한도 초과(020) — 여기서 멈춤")
        raise SystemExit(0)
    if st != "000":
        print(f"[dart_mgmt] {path} 오류 {st}: {j.get('message')}")
        return None
    return j


def doc_text(rcept_no: str) -> str:
    """사업보고서 본문 — zip 안 XML 중 가장 큰 것(본문)을 쓴다. 표 칸 경계는 공백으로."""
    try:
        r = requests.get(f"{API}/document.xml", params={"crtfc_key": KEY, "rcept_no": rcept_no}, headers=UA, timeout=90)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
    except Exception as e:  # noqa: BLE001
        print(f"[dart_mgmt] 원문 {rcept_no} 실패: {redact(e)[:120]}")
        return ""
    names = sorted(z.namelist(), key=lambda n: z.getinfo(n).file_size, reverse=True)
    raw = z.read(names[0]) if names else b""
    t = ""
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            t = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    t = re.sub(r"<(TITLE|title)[^>]*>", "\n§ ", t)          # 절 제목 앞에 표시
    t = re.sub(r"</?(P|p|TR|tr|BR|br)[^>]*>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&[a-z#0-9]+;", " ", t)
    t = re.sub(r"[ \t ]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def section(text: str, title_pat: str, end_pat: str = r"\n§ ") -> str:
    """'§ 제목' 다음부터 다음 '§' 앞까지(절 제목이 TITLE 태그가 아니면 줄 머리 글자로 찾는다)"""
    m = re.search(r"§\s*[^\n]*" + title_pat + r"[^\n]*\n", text)
    if not m:
        m = re.search(r"\n\s*(?:\d+\s*[.)]|[가-하]\s*[.)])?\s*" + title_pat + r"[^\n]{0,30}\n", text)
    if not m:
        return ""
    rest = text[m.end():]
    e = re.search(end_pat, rest)
    return rest[: e.start()] if e else rest[:20000]


def first_sentences(body: str, prefer: tuple[str, ...] = ()) -> str:
    """본문 줄 가운데 문장(…다./…음./…임.)으로 끝나는 줄을 앞에서부터 모아 MAXLEN 안으로. prefer 낱말이 든 소제목 아래를 먼저 본다."""
    lines = [ln.strip(" -·•○□▶■◆※") for ln in body.split("\n")]
    lines = [ln for ln in lines if ln]
    start = 0
    for w in prefer:
        for i, ln in enumerate(lines):
            if w in ln and len(ln) < 40:      # 소제목
                start = i + 1
                break
        else:
            continue
        break
    out = ""
    for ln in lines[start:]:
        if len(ln) < 15 or re.fullmatch(r"[\d,.\s()%△▲-]+", ln) or "단위" in ln[:10]:
            continue
        if not re.search(r"(다|음|임|함|됨)\s*\.?$", ln) and not re.search(r"[다음임함됨]\.", ln):
            continue
        if SKIP.search(ln):
            return ""
        out = (out + " " + ln).strip()
        if len(out) >= MAXLEN:
            break
    if len(out) > MAXLEN:
        cut = out[:MAXLEN]
        k = max(cut.rfind("다."), cut.rfind("음."), cut.rfind("임."))
        out = cut[: k + 2] if k > MAXLEN * 0.5 else cut.rstrip() + "…"
    return out


def extract(text: str, probe: bool) -> dict:
    mdna = section(text, r"이사의\s*경영진단\s*및\s*분석의견")
    if probe:
        print(f"   [경영진단 절 {len(mdna)}자] {mdna[:1500]!r}")
    newbiz = section(text, r"신규\s*사업\s*등의\s*내용\s*및\s*전망", r"\n§ |\n\s*(?:\d+\s*[.)]|[가-하]\s*[.)])\s*(조직도|사업부문|기타)")
    if not newbiz:
        newbiz = section(text, r"신규\s*사업")
    if probe:
        print(f"   [신규사업 {len(newbiz)}자] {newbiz[:800]!r}")
    return {
        "overview": first_sentences(mdna, ("개요", "경영진단의 개요", "회사의 현황", "재무상태")),
        "outlook": first_sentences(mdna, ("전망", "향후", "계획", "경영 방향", "경영방향")),
        "new_biz": first_sentences(newbiz),
    }


def main(argv: list[str]) -> int:
    if not KEY:
        print("DART_KEY 없음")
        return 0
    probe = argv[argv.index("--probe") + 1] if "--probe" in argv else ""
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    corps = {c: v for c, v in cache.items() if v.get("daegu") and v.get("corp_cls") in LISTED}
    if probe:
        corps = {c: v for c, v in corps.items() if probe in (v.get("name") or "")}
    old = {r["corp_code"]: r for r in csv.DictReader(open(OUT, encoding="utf-8"))} if OUT.exists() else {}
    bgn = (date.today() - timedelta(days=500)).strftime("%Y%m%d")
    end = date.today().strftime("%Y%m%d")
    rows, n_new = dict(old), 0
    for code, meta in sorted(corps.items()):
        j = get("list.json", corp_code=code, bgn_de=bgn, end_de=end, pblntf_detail_ty="A001", page_count=20)
        time.sleep(0.15)
        reps = [r for r in (j or {}).get("list", []) if "사업보고서" in (r.get("report_nm") or "")]
        if not reps:
            continue
        r = sorted(reps, key=lambda x: x["rcept_no"], reverse=True)[0]
        if not probe and old.get(code, {}).get("rcept_no") == r["rcept_no"]:
            continue
        text = doc_text(r["rcept_no"])
        time.sleep(0.3)
        if not text:
            continue
        if probe:
            print(f"== probe {meta.get('name')} {r['report_nm']} {r['rcept_no']} 본문 {len(text):,}자")
        ex = extract(text, bool(probe))
        y = re.search(r"\((\d{4})\.\d{2}\)", r.get("report_nm") or "")
        rows[code] = {"corp_code": code, "name": meta.get("name") or r.get("corp_name", ""), "report_year": y.group(1) if y else "",
                      "rcept_dt": r.get("rcept_dt", ""), **ex, "rcept_no": r["rcept_no"],
                      "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}"}
        n_new += 1
        if probe:
            print("   →", json.dumps({k: rows[code][k] for k in ("overview", "outlook", "new_biz")}, ensure_ascii=False))
    if probe:
        return 0
    out = [rows[c] for c in sorted(rows) if c in corps]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    filled = sum(1 for r in out if r["overview"] or r["outlook"] or r["new_biz"])
    print(f"저장: {OUT.relative_to(ROOT)} {len(out)}곳(문구 있음 {filled}곳, 새로 읽음 {n_new})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
