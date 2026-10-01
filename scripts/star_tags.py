#!/usr/bin/env python3
"""대구시 스타기업·Pre-스타기업·3030기업 명단 → 기업 사전 태그(company_tags.csv).

지원 이력(support_history.csv)에 이미 들어간 대구광역시 「스타기업·PRE-스타기업·3030기업 현황」(공공데이터포털 15130932)
행 가운데 기업 사전 id 가 잡힌 행만 태그로 옮긴다. 태그 key 는 config/site_types.yml 의 tags(star·prestar·k3030).
같은 출처의 기존 태그 행은 버리고 다시 쓴다(멱등). 이름이 기업 사전과 맞지 않은 기업은 태그 없이 /support/star/ 에 이름만.
사용: python3 scripts/star_tags.py   (fetch_public.yml 이 import_support.py 뒤에 실행)
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "scripts" / "data" / "support_history.csv"
TAGS = ROOT / "scripts" / "data" / "company_tags.csv"
DATASET = "15130932"
TAG_OF = {"스타기업": "star", "Pre-스타기업": "prestar", "3030기업": "k3030"}


def main() -> int:
    if not HIST.exists():
        print("support_history.csv 없음 — 건너뜀")
        return 0
    rows = [r for r in csv.DictReader(open(HIST, encoding="utf-8")) if DATASET in r.get("source_url", "")]
    new, miss = {}, 0
    for r in rows:
        tag = TAG_OF.get(r["program"].strip())
        if not tag:
            continue
        if not r["id"]:
            miss += 1
            continue
        new[(r["id"], tag)] = {"id": r["id"], "tag": tag, "source": r["source"], "as_of": r["as_of"]}
    src = {r["source"] for r in rows}
    old = list(csv.DictReader(open(TAGS, encoding="utf-8"))) if TAGS.exists() else []
    kept = [t for t in old if t.get("source", "") not in src]
    out = kept + sorted(new.values(), key=lambda t: (t["tag"], t["id"]))
    with open(TAGS, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "tag", "source", "as_of"])
        w.writeheader()
        w.writerows(out)
    by = {}
    for t in new.values():
        by[t["tag"]] = by.get(t["tag"], 0) + 1
    print(f"태그 {len(new)}건 {by} (기업 사전 이름 불일치 {miss}건은 태그 없음) → {TAGS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
