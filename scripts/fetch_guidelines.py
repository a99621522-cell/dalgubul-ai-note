#!/usr/bin/env python3
"""사업 지침 창고 — config/guidelines.yml 의 법령·행정규칙·자치법규 본문을 국가법령정보센터 오픈API(law.go.kr/DRF)로 받아 data/guidelines/ 에 둔다.

예산요구서·결산서를 지침대로 작성·집행했는지 검토할 때 조문을 그대로 인용하기 위한 창고(운영자 지시 2026-09-27).
법령·고시·조례 본문은 공공저작물이라 본문 전체를 저장한다(gzip). 지침 내용에 대한 평가는 쓰지 않는다.

흐름: lawSearch.do(target=law|admrul|ordin, query=이름) → 현행 항목의 일련번호 → lawService.do(type=XML) → 조문 글자 추출
  → data/guidelines/<key>.txt.gz + index.json(이름·종류·소관·발령일·시행일·원문 링크·글자 수·상태).
OC(오픈API 아이디)는 환경변수 LAW_OC, 없으면 'test'(게스트, 2026-09-27 확인). 요청 사이 1초, 실패는 로그만.
이 세션 환경은 law.go.kr 접속이 막혀 있어 워크플로(.github/workflows/guidelines.yml)가 대신 돈다.

사용: python3 scripts/fetch_guidelines.py [--only key,key] [--dry-run]
      python3 scripts/fetch_guidelines.py --query 인건비 간접비      # 저장된 본문에서 낱말이 든 조문 찾기(검토표 작성 때)
      python3 scripts/fetch_guidelines.py --show <key> [--grep 낱말]  # 본문 보기
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "guidelines.yml"
OUT = ROOT / "data" / "guidelines"
INDEX = OUT / "index.json"
OC = os.environ.get("LAW_OC", "test").strip() or "test"
BASE = "https://www.law.go.kr/DRF"
UA = "Mozilla/5.0 daitda-note-bot/1.0 (+https://note.daitda.co.kr)"
TODAY = date.today().isoformat()
# 검색 결과에서 항목·일련번호·이름·현행 여부를 읽는 태그 (target 별). 이름은 공백을 뺀 뒤 비교한다.
FIELDS = {
    "admrul": {"item": "admrul", "id": "행정규칙일련번호", "name": "행정규칙명", "current": "현행연혁구분", "kind": "행정규칙종류", "issuer": "소관부처명", "date": "발령일자", "eff": "시행일자", "param": "ID",
               "public": "https://www.law.go.kr/LSW/admRulInfoP.do?admRulSeq={id}"},
    "law":    {"item": "law", "id": "법령일련번호", "name": "법령명한글", "current": "현행연혁코드", "kind": "법령구분명", "issuer": "소관부처명", "date": "공포일자", "eff": "시행일자", "param": "MST",
               "public": "https://www.law.go.kr/법령/{name}"},
    "ordin":  {"item": "law", "id": "자치법규일련번호", "name": "자치법규명", "current": "현행연혁구분", "kind": "자치법규종류", "issuer": "지자체기관명", "date": "공포일자", "eff": "시행일자", "param": "MST",
               "public": "https://www.law.go.kr/자치법규/{name}"},
}
CONTENT_TAGS = ("조문내용", "항내용", "호내용", "목내용", "부칙내용", "개정문내용", "제개정이유내용", "별표내용")


def norm(s: str) -> str:
    return re.sub(r"[\s·ㆍ,()\[\]「」『』]", "", s or "")


def get(url: str, params: dict, timeout: int = 40) -> requests.Response | None:
    try:
        r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=timeout)
        time.sleep(1)
        if r.status_code != 200:
            print(f"    HTTP {r.status_code} {url}")
            return None
        return r
    except Exception as e:  # noqa: BLE001
        print(f"    실패 {url}: {type(e).__name__} {str(e)[:80]}")
        return None


def first_text(el: ET.Element, tag: str) -> str:
    x = el.find(tag)
    return (x.text or "").strip() if x is not None else ""


def search(target: str, name: str) -> dict | None:
    """이름으로 검색해 현행 항목(이름이 정확히 같은 것 우선)을 돌려준다."""
    f = FIELDS[target]
    r = get(f"{BASE}/lawSearch.do", {"OC": OC, "target": target, "type": "XML", "query": name, "display": 20})
    if not r:
        return None
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        print(f"    XML 오류: {e}; 앞부분 {r.text[:120]!r}")
        return None
    if (root.findtext("resultCode") or "00") != "00":
        print(f"    결과 코드 {root.findtext('resultCode')} {root.findtext('resultMsg')}")
    items = []
    for it in root.iter(f["item"]):
        d = {k: first_text(it, t) for k, t in f.items() if k not in ("item", "param", "public")}
        d["_exact"] = norm(d.get("name", "")) == norm(name)
        d["_current"] = "현행" in (d.get("current") or "") or d.get("current") in ("", "010202", "현행")
        items.append(d)
    if not items:
        return None
    items.sort(key=lambda d: (not d["_exact"], not d["_current"], d.get("eff") or ""), reverse=False)
    hit = items[0]
    if not hit["_exact"]:
        print(f"    정확히 같은 이름 없음 → 가장 가까운 항목: {hit.get('name')} (검색 {len(items)}건)")
    return hit


def body(target: str, ident: str) -> tuple[str, dict]:
    """본문 XML → 조문 글자. (글자, 부가정보: 별표 제목 목록·조문 수)"""
    f = FIELDS[target]
    r = get(f"{BASE}/lawService.do", {"OC": OC, "target": target, f["param"]: ident, "type": "XML"}, timeout=60)
    if not r:
        return "", {}
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        print(f"    본문 XML 오류: {e}; 앞부분 {r.text[:120]!r}")
        return "", {}
    lines, seen, n_art = [], set(), 0
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag in CONTENT_TAGS or (tag.endswith("내용") and tag not in ("법령명약칭내용",)):
            t = re.sub(r"[ \t\r]+", " ", (el.text or "")).strip()
            if t and (tag, t) not in seen:
                seen.add((tag, t))
                lines.append(t)
                n_art += tag == "조문내용"
    annexes = [x.text.strip() for x in root.iter("별표제목") if x.text and x.text.strip()]
    text = "\n".join(lines)
    if not text:   # 태그 이름이 다르면 글자 전체를 이어 붙인다(다음에 태그를 맞춘다)
        text = "\n".join(t.strip() for t in root.itertext() if t and t.strip())
        print("    조문 태그를 못 찾아 글자 전체를 저장 — 태그 이름 확인 필요")
    return text, {"articles": n_art, "annexes": annexes[:40]}


def load_index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {"fetched": "", "items": {}}


def fetch(only: set[str], dry: bool) -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    idx = load_index()
    ok = fail = 0
    for g in cfg["guidelines"]:
        key = g["key"]
        if only and key not in only:
            continue
        src = g.get("source") or {}
        target, name = src.get("type"), src.get("name")
        print(f"[{key}] {g['name']} ({target})")
        if target not in FIELDS:
            print("    source.type 이 law|admrul|ordin 이 아니라 건너뜀(부처 첨부는 fetch_budget_docs 방식으로 따로)")
            continue
        hit = search(target, name)
        entry = {"key": key, "name": g["name"], "kind": g.get("kind", ""), "issuer": g.get("issuer", ""), "source": src, "applies": g.get("applies", {}),
                 "review": g.get("review", []), "fetched": TODAY, "status": "없음", "found": "", "id": "", "date": "", "eff": "", "url": "", "chars": 0}
        if not hit:
            print("    검색 결과 없음 — config/guidelines.yml 의 이름을 확인")
            idx["items"][key] = entry
            fail += 1
            continue
        f = FIELDS[target]
        entry.update({"found": hit.get("name", ""), "id": hit.get("id", ""), "date": hit.get("date", ""), "eff": hit.get("eff", ""), "found_kind": hit.get("kind", ""), "found_issuer": hit.get("issuer", ""),
                      "url": f["public"].format(id=hit.get("id", ""), name=norm(hit.get("name", "")) if target != "admrul" else "")})
        if dry:
            print(f"    → {hit.get('name')} · {hit.get('kind')} · {hit.get('issuer')} · 발령 {hit.get('date')} 시행 {hit.get('eff')} (dry-run)")
            entry["status"] = "검색만"
            idx["items"][key] = entry
            continue
        text, extra = body(target, hit.get("id", ""))
        if not text:
            entry["status"] = "본문 실패"
            idx["items"][key] = entry
            fail += 1
            continue
        with gzip.open(OUT / f"{key}.txt.gz", "wt", encoding="utf-8") as fh:
            fh.write(text)
        entry.update({"status": "OK", "chars": len(text), **extra})
        idx["items"][key] = entry
        ok += 1
        print(f"    → {hit.get('name')} · {hit.get('kind')} · 시행 {hit.get('eff')} · {len(text):,}자 · 조문 {extra.get('articles', 0)}개 · 별표 {len(extra.get('annexes', []))}개")
    idx["fetched"] = TODAY
    INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    write_summary(idx)
    print(f"완료: OK {ok} · 실패/없음 {fail} → {INDEX.relative_to(ROOT)}")
    return 0


def write_summary(idx: dict) -> None:
    L = ["# 사업 지침 창고 (data/guidelines)", "", f"받은 날짜: {idx.get('fetched', '')} · 출처: 국가법령정보센터 오픈API(law.go.kr/DRF). 본문은 `<key>.txt.gz`, 검색은 `python3 scripts/fetch_guidelines.py --query 낱말`.", "",
         "| key | 지침 | 종류 | 소관 | 시행일 | 상태 | 글자 | 검토 단계 | 원문 |", "|---|---|---|---|---|---|---|---|---|"]
    for k, e in sorted(idx.get("items", {}).items()):
        eff = e.get("eff", "")
        eff = f"{eff[:4]}-{eff[4:6]}-{eff[6:]}" if len(eff) == 8 else eff
        L.append(f"| {k} | {e.get('found') or e.get('name')} | {e.get('found_kind') or e.get('kind', '')} | {e.get('found_issuer') or e.get('issuer', '')} | {eff} | {e.get('status', '')} | {e.get('chars', 0):,} | {' · '.join(e.get('review', []))} | {e.get('url', '')} |")
    (OUT / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def read_text(key: str) -> str:
    p = OUT / f"{key}.txt.gz"
    return gzip.open(p, "rt", encoding="utf-8").read() if p.exists() else ""


def query(words: list[str]) -> int:
    """저장된 본문에서 낱말이 모두 든 조문(줄)을 지침별로 보여준다."""
    idx = load_index()
    pats = [re.compile(re.escape(w)) for w in words]
    for k, e in sorted(idx.get("items", {}).items()):
        hits = [ln for ln in read_text(k).split("\n") if all(p.search(ln) for p in pats)]
        if hits:
            print(f"\n[{k}] {e.get('found') or e.get('name')} (시행 {e.get('eff', '')}) — {len(hits)}줄")
            for ln in hits[:12]:
                print("  " + ln[:300])
    return 0


def main(argv: list[str]) -> int:
    if "--query" in argv:
        return query(argv[argv.index("--query") + 1:])
    if "--show" in argv:
        key = argv[argv.index("--show") + 1]
        txt = read_text(key)
        if "--grep" in argv:
            w = argv[argv.index("--grep") + 1]
            txt = "\n".join(ln for ln in txt.split("\n") if w in ln)
        print(txt[:20000])
        return 0
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else set()
    return fetch(only, "--dry-run" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
