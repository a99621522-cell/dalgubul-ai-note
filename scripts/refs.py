#!/usr/bin/env python3
"""참고자료 창고(data/refs/*.json) 검사·목록.
  python3 scripts/refs.py --check          # 형식 검사(필수 항목·areas 값·날짜·크기·개인정보 낱말)
  python3 scripts/refs.py --list [--area healthcare] [--query 낱말 ...]
report_context.py 가 같은 함수(load_refs, match_refs)로 분야별 항목을 출력한다."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "data" / "refs"
REQUIRED = ["slug", "file", "title", "publisher", "published", "areas", "summary", "added", "read_status"]
AREA_KEYS = {"mobility", "robot-physical-ai", "semiconductor", "manufacturing-ax", "healthcare", "ai-sw-startup", "machinery", "automotive", "textile", "root"}
PERSONAL = re.compile(r"(휴대폰|핸드폰|전화번호|이메일|e-mail|주민등록|@[a-z0-9.-]+\.[a-z]{2,})", re.I)
MAX_BYTES = 60_000


def load_refs() -> list[dict]:
    out = []
    if not REFS.exists():
        return out
    for f in sorted(REFS.glob("*.json")):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[refs] {f.name}: JSON 오류 {e}", file=sys.stderr)
            continue
        j["_file"] = f.name
        out.append(j)
    return sorted(out, key=lambda j: (j.get("published") or "", j.get("added") or ""), reverse=True)


def match_refs(refs: list[dict], area_key: str = "", keywords: list[str] | None = None) -> list[dict]:
    """분야 key 가 areas 에 있는 항목 먼저, 그다음 키워드가 제목·요약·키워드에 있는 항목."""
    kws = [k for k in (keywords or []) if k]
    first, rest = [], []
    for r in refs:
        if r.get("read_status") == "skipped":
            continue
        if area_key and area_key in (r.get("areas") or []):
            first.append(r)
        elif kws:
            hay = " ".join([r.get("title", ""), r.get("summary", ""), " ".join(r.get("keywords") or [])])
            if any(k in hay for k in kws):
                rest.append(r)
    return first + rest


def check() -> int:
    errs = 0
    for f in sorted(REFS.glob("*.json")):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"✗ {f.name}: JSON 오류 {e}"); errs += 1; continue
        miss = [k for k in REQUIRED if not j.get(k) and j.get(k) != []]
        if miss:
            print(f"✗ {f.name}: 필수 항목 없음 {miss}"); errs += 1
        if j.get("slug") and f.stem != j["slug"]:
            print(f"✗ {f.name}: slug 와 파일 이름이 다름 ({j['slug']})"); errs += 1
        bad = [a for a in (j.get("areas") or []) if a not in AREA_KEYS]
        if bad:
            print(f"✗ {f.name}: areas 값 오류 {bad}"); errs += 1
        if j.get("published") and not re.fullmatch(r"\d{4}(-\d{2}){1,2}", str(j["published"])):
            print(f"✗ {f.name}: published 는 YYYY-MM 또는 YYYY-MM-DD ({j['published']})"); errs += 1
        if j.get("read_status") not in ("full", "partial", "skipped"):
            print(f"✗ {f.name}: read_status 는 full|partial|skipped"); errs += 1
        if f.stat().st_size > MAX_BYTES:
            print(f"✗ {f.name}: {f.stat().st_size:,} bytes — 요약이 아니라 본문을 넣은 것 아닌지 확인(상한 {MAX_BYTES:,})"); errs += 1
        m = PERSONAL.search(json.dumps(j, ensure_ascii=False))
        if m:
            print(f"✗ {f.name}: 개인정보로 보이는 낱말 '{m.group(0)}'"); errs += 1
        if j.get("public_url") and not str(j["public_url"]).startswith("http"):
            print(f"✗ {f.name}: public_url 형식"); errs += 1
    n = len(list(REFS.glob("*.json")))
    print(f"{'통과' if not errs else '오류 ' + str(errs) + '건'} — 참고자료 {n}건")
    return 1 if errs else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--area", default="")
    ap.add_argument("--query", nargs="*", default=[])
    a = ap.parse_args(argv)
    if a.check:
        return check()
    refs = load_refs()
    rows = match_refs(refs, a.area, a.query) if (a.area or a.query) else refs
    for r in rows:
        print(f"{r.get('published')} [{r.get('publisher')}] {r.get('title')} ({r.get('pages', '?')}쪽, {r.get('read_status')}) areas={r.get('areas')} {r.get('public_url') or '(공개 URL 미확인)'}")
        print("   " + (r.get("summary") or "")[:220].replace("\n", " ") + "…")
    if not rows:
        print("참고자료 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
