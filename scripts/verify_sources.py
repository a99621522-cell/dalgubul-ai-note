#!/usr/bin/env python3
"""정책 브리프 출처 원문 대조 — sources 의 URL 을 실제로 열어 접속·제목·날짜를 확인한다(발행 문의 신뢰성 검사, 운영자 지시 2026-09-28).

  python3 scripts/verify_sources.py src/content/posts/2026-09-29-policy-robot-physical-ai.md [--min-ok 0.8]

출처마다 GET(20초) → HTTP 상태, <title>, 본문에서 출처 제목 낱말(4자 이상)·발행일(YYYY-MM-DD / YYYY.MM.DD / YYYY년 M월 D일) 발견 여부.
판정: 접속 200 이고 (제목 낱말 30% 이상 일치 또는 날짜 발견) 이면 ok. ok 비율이 --min-ok 이상이고 공식 자료(kind official/law/gov/report)가 모두 ok 이면 PASS.
결과는 data/source_checks/<id>.json 에 남긴다. 작성 세션 환경은 외부 접속이 막혀 있으므로 .github/workflows 에서 돌린다.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "source_checks"
UA = "Mozilla/5.0 (compatible; daitda-note/1.0; +https://note.daitda.co.kr)"


def parse_sources(fm: str) -> list[dict]:
    out = []
    for m in re.finditer(r"^\s*-\s*\{\s*title:\s*\"(.*?)\",\s*url:\s*\"(.*?)\"(?:,\s*date:\s*\"?([^\",}]*?)\"?)?(?:,\s*kind:\s*\"?(\w+)\"?)?\s*\}", fm, re.M):
        out.append({"title": m.group(1), "url": m.group(2), "date": (m.group(3) or "").strip(), "kind": (m.group(4) or "").strip()})
    return out


def date_forms(d: str) -> list[str]:
    m = re.match(r"(20\d\d)-(\d\d)(?:-(\d\d))?", d)
    if not m:
        return []
    y, mo, dd = m.group(1), m.group(2), m.group(3)
    forms = [f"{y}-{mo}", f"{y}.{mo}", f"{y}년 {int(mo)}월", f"{y}/{mo}"]
    if dd:
        forms = [f"{y}-{mo}-{dd}", f"{y}.{mo}.{dd}", f"{y}년 {int(mo)}월 {int(dd)}일", f"{y}{mo}{dd}", f"{y}/{mo}/{dd}"] + forms
    return forms


def tokens(title: str) -> list[str]:
    t = re.sub(r"[「」『』()（）\[\]\"'·,.:;!?…—-]", " ", title)
    return [w for w in t.split() if len(w) >= 4 and not re.fullmatch(r"\d+", w)]


def check(src: dict, sess: requests.Session) -> dict:
    rec = {**src, "status": None, "page_title": "", "title_match": 0.0, "date_found": False, "ok": False, "note": ""}
    try:
        r = sess.get(src["url"], headers={"User-Agent": UA, "Accept-Language": "ko,en;q=0.8,zh;q=0.6"}, timeout=(15, 20), allow_redirects=True)
        rec["status"] = r.status_code
        html = r.text[:400000]
    except Exception as e:  # noqa: BLE001
        rec["note"] = f"{type(e).__name__}"
        return rec
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    rec["page_title"] = re.sub(r"\s+", " ", m.group(1)).strip()[:120] if m else ""
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    toks = tokens(src["title"])
    hit = sum(1 for w in toks if w in text)
    rec["title_match"] = round(hit / len(toks), 2) if toks else 0.0
    rec["date_found"] = any(f in text for f in date_forms(src["date"]))
    rec["ok"] = rec["status"] == 200 and (rec["title_match"] >= 0.3 or rec["date_found"])
    if rec["status"] == 200 and not rec["ok"]:
        rec["note"] = "열리지만 제목·날짜를 본문에서 못 찾음(JS 렌더링·제목 표기 차이 가능) — 사람이 확인"
    return rec


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv if not a.startswith("--")]
    min_ok = float(argv[argv.index("--min-ok") + 1]) if "--min-ok" in argv else 0.8
    if not files:
        print(__doc__)
        return 2
    sess = requests.Session()
    rc = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        fm = text.split("---", 2)[1] if text.startswith("---") else ""
        srcs = parse_sources(fm)
        recs = []
        for s in srcs:
            rec = check(s, sess)
            recs.append(rec)
            print(f"  {'ok ' if rec['ok'] else 'NO '} [{rec['kind'] or '-':8}] {rec['status'] or rec['note']:>5} 제목일치 {rec['title_match']:.2f} 날짜 {'O' if rec['date_found'] else 'X'} | {rec['title'][:50]}")
            time.sleep(1)
        n_ok = sum(1 for r in recs if r["ok"])
        official = [r for r in recs if r["kind"] in ("official", "law", "gov", "report", "stat")]
        off_bad = [r for r in official if not r["ok"]]
        ratio = n_ok / len(recs) if recs else 0
        passed = bool(recs) and ratio >= min_ok and not off_bad
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{f.stem}.json").write_text(json.dumps({"file": str(f), "checked": date.today().isoformat(), "ok": n_ok, "total": len(recs), "ratio": round(ratio, 2),
                                                          "official_bad": [r["title"] for r in off_bad], "pass": passed, "sources": recs}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{'PASS' if passed else 'FAIL'}  {f.name}: 출처 {len(recs)}건 중 확인 {n_ok}건({ratio:.0%}), 공식 자료 미확인 {len(off_bad)}건 → data/source_checks/{f.stem}.json")
        if not passed:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
