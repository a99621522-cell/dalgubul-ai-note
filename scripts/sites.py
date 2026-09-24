#!/usr/bin/env python3
"""입지 유형·태그·산단 외 기업 목록 — 규칙은 config/site_types.yml 에만 있고 이 모듈이 적용한다.
src/lib/sites.ts 가 같은 규칙을 같은 순서로 구현한다.

- site_type(complex, address) → 유형 이름 (수성알파시티 / 연구개발특구 / 지식산업센터 / 산업단지 / 개별입지)
- load_all_companies() → 팩토리온 기업 + scripts/data/extra_companies.csv(산단 외 기업) 를 한 목록으로. 각 행에 site_type, tags 채움
- python3 scripts/sites.py → 유형별·태그별 분포 출력
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "site_types.yml"
DATA = ROOT / "scripts" / "data"
COMPANIES = DATA / "dalseong_companies.csv"
EXTRA = DATA / "extra_companies.csv"
TAGS = DATA / "company_tags.csv"

_cfg: dict | None = None


def config() -> dict:
    global _cfg
    if _cfg is None:
        _cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return _cfg


def site_types() -> list[dict]:
    return [{"key": t["key"], "name": t["name"]} for t in config()["types"]]


def site_type(complex_: str, address: str) -> str:
    cx = (complex_ or "").strip()
    addr = (address or "").replace(" ", "")
    for t in config()["types"]:
        if cx and cx in t.get("complexes", []):
            return t["name"]
        if any(p.replace(" ", "") in addr for p in t.get("address", [])):
            return t["name"]
        if t.get("rule") == "in_complex" and cx and cx not in ("개별입지", config()["outside_complex"]):
            return t["name"]
        if t.get("rule") == "default":
            return t["name"]
    return config()["types"][-1]["name"]


def tag_name(key: str) -> str:
    return config()["tags"].get(key, {}).get("name", key)


def is_startup(founded: str, as_of: str) -> bool:
    """founded(YYYY 또는 YYYY-MM…) 가 as_of 기준 7년 이내면 창업기업."""
    y = re.match(r"(\d{4})", founded or "")
    a = re.match(r"(\d{4})", as_of or "")
    return bool(y and a and int(a.group(1)) - int(y.group(1)) <= config()["startup_years"])


def load_tags() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    if TAGS.exists():
        for r in csv.DictReader(open(TAGS, encoding="utf-8")):
            if r.get("id") and r.get("tag"):
                out.setdefault(r["id"], set()).add(r["tag"])
    return out


def load_all_companies() -> list[dict]:
    """팩토리온 기업(모두) + 산단 외 기업. 열은 dalseong_companies.csv 와 같고 site_type, tags(집합), founded 가 추가된다."""
    rows = list(csv.DictReader(open(COMPANIES, encoding="utf-8")))
    for r in rows:
        r.setdefault("founded", "")
    if EXTRA.exists():
        for r in csv.DictReader(open(EXTRA, encoding="utf-8")):
            rows.append(r)
    tags = load_tags()
    for r in rows:
        r["site_type"] = site_type(r.get("complex", ""), r.get("address", ""))
        t = set(tags.get(r["id"], set()))
        for k in (r.get("tags") or "").split(";"):
            if k.strip():
                t.add(k.strip())
        if r.get("founded") and is_startup(r["founded"], r.get("as_of", "")):
            t.add("startup")
        r["tags"] = t
    return rows


def main() -> int:
    rows = load_all_companies()
    fo = sum(1 for r in rows if not r["id"].startswith("x"))
    print(f"기업 {len(rows):,}곳 (팩토리온 {fo:,} + 산단 외 목록 {len(rows) - fo:,})")
    print("\n입지 유형별")
    for name, n in Counter(r["site_type"] for r in rows).most_common():
        print(f"  {name:<10}{n:>8,}")
    tc = Counter(t for r in rows for t in r["tags"])
    print("\n태그별" + ("" if tc else " (없음 — scripts/data/extra/ 에 목록을 넣고 import_extra.py 실행)"))
    for k, n in tc.most_common():
        print(f"  {tag_name(k):<10}{n:>8,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
