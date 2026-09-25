#!/usr/bin/env python3
"""대구 주력산업 그룹 분류 — 규칙은 config/industry_groups.yml 에만 있고 이 모듈은 그 파일을 읽어 적용한다.
src/lib/industry.ts 가 같은 규칙을 같은 순서로 구현한다(둘의 결과가 같아야 한다).

사용:
  from industry import classify, groups            # classify(code, sector, product) -> 그룹 이름
  python3 scripts/industry.py                       # 기업 DB 전체 분포 출력 + data/stats/unclassified.csv 저장
  python3 scripts/industry.py --dump out.csv        # 기업 id,그룹 전체 저장 (TS 구현과 대조용)
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "industry_groups.yml"
COMPANIES = ROOT / "scripts" / "data" / "dalseong_companies.csv"
UNCLASSIFIED = ROOT / "data" / "stats" / "unclassified.csv"

_cfg: dict | None = None


def config() -> dict:
    global _cfg
    if _cfg is None:
        _cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        # 접두어 → 그룹 이름. 긴 접두어가 우선하도록 판정 때 길이순으로 본다
        prefixes: dict[str, str] = {}
        for g in _cfg["groups"]:
            for p in g.get("ksic", []):
                prefixes[str(p)] = g["name"]
        _cfg["_prefixes"] = prefixes
        _cfg["_keyword_first"] = tuple(str(p) for p in _cfg.get("keyword_first", []))
    return _cfg


def groups() -> list[dict]:
    """그룹 목록(우선순위 순). key(URL용 슬러그)·name."""
    return [{"key": g["key"], "name": g["name"]} for g in config()["groups"]]


def by_prefix(code: str) -> str | None:
    pre = config()["_prefixes"]
    code = (code or "").strip()
    for n in range(len(code), 0, -1):
        hit = pre.get(code[:n])
        if hit:
            return hit
    return None


def by_keyword(text: str) -> str | None:
    text = (text or "").replace(" ", "")
    for g in config()["groups"]:
        if any(k in text for k in g.get("keywords", [])):
            return g["name"]
    return None


def service_first(text: str) -> bool:
    """코드 없는 행: 서비스업 낱말이 있고 keep_service 낱말이 없으면 기타 서비스."""
    cfg = config()
    t = (text or "").replace(" ", "")
    if any(k.replace(" ", "") in t for k in cfg.get("keep_service", [])):
        return False
    return any(k.replace(" ", "") in t for k in cfg.get("service_patterns", []))


def classify(code: str, sector: str = "", product: str = "") -> str:
    cfg = config()
    code = (code or "").strip()
    text = f"{sector or ''} {product or ''}"
    if not code and service_first(text):
        return "기타 서비스"
    if code.startswith(cfg["_keyword_first"]):
        return by_keyword(text) or by_prefix(code) or cfg["unclassified"]
    return by_prefix(code) or by_keyword(text) or cfg["unclassified"]


def key_of(name: str) -> str | None:
    for g in config()["groups"]:
        if g["name"] == name:
            return g["key"]
    return None


def main(argv: list[str]) -> int:
    rows = list(csv.DictReader(open(COMPANIES, encoding="utf-8")))
    labeled = [(r, classify(r["sector_code"], r["sector"], r["product"])) for r in rows]

    if "--dump" in argv:
        out = Path(argv[argv.index("--dump") + 1])
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "group"])
            w.writerows((r["id"], g) for r, g in labeled)
        print(f"저장: {out} ({len(labeled)}행)")
        return 0

    unc = config()["unclassified"]
    dist = Counter(g for _, g in labeled)
    total = len(labeled)
    print(f"기업 {total:,}곳 → 산업 그룹 분포 (config/industry_groups.yml {config()['version']})")
    print(f"{'그룹':<12}{'기업 수':>8}{'비율':>8}   주요 업종코드(3자리, 기업 수)")
    for g in [x["name"] for x in config()["groups"]] + [unc]:
        n = dist.get(g, 0)
        codes = Counter(r["sector_code"][:3] for r, gg in labeled if gg == g).most_common(4)
        print(f"{g:<12}{n:>8,}{n / total:>8.1%}   " + ", ".join(f"{c}({k:,})" for c, k in codes))

    UNCLASSIFIED.parent.mkdir(parents=True, exist_ok=True)
    with open(UNCLASSIFIED, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "sector_code", "sector", "product"])
        for r, g in labeled:
            if g == unc:
                w.writerow([r["id"], r["name"], r["sector_code"], r["sector"], r["product"]])
    n_unc = dist.get(unc, 0)
    print(f"\n미분류 {n_unc:,}곳 ({n_unc / total:.1%}) → {UNCLASSIFIED.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
