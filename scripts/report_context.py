#!/usr/bin/env python3
"""정책제안 리포트 근거 계산 — 이번 주 공약 분야를 고르고 기업 사전·사업 DB·대구시 매칭·최근 글에서 숫자를 코드로 센다.

사용:
  python3 scripts/report_context.py                 # 이번 주(ISO 주) 분야
  python3 scripts/report_context.py --area mobility # 특정 분야
  python3 scripts/report_context.py --week 39       # 특정 주
  python3 scripts/report_context.py --json          # JSON 출력 (리포트 작성용)

읽는 것: config/pledge_areas.yml, config/industry_groups.yml(industry.py), scripts/data/dalseong_companies.csv(+extra),
        scripts/data/programs_*.csv, match_daegu_national.csv, match_daegu_motie.csv, src/content/posts/*.md (최근 8주)
숫자만 낸다. 평가·순위 없음. 리포트는 여기 나온 값과 조건을 그대로 적는다.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from industry import classify  # noqa: E402
from sites import load_all_companies  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "pledge_areas.yml"
DATA = ROOT / "scripts" / "data"
POSTS = ROOT / "src" / "content" / "posts"
PROGRAM_FILES = ["programs_motie.csv", "programs_smba.csv", "programs_ai.csv"]
SIZE = [("1~9인", 1, 9), ("10~49인", 10, 49), ("50~299인", 50, 299), ("300인 이상", 300, 10**9)]


def cfg() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def pick_area(c: dict, week: int | None, key: str | None) -> tuple[dict, int]:
    areas = c["areas"]
    if key:
        return next(a for a in areas if a["key"] == key), week or date.today().isocalendar()[1]
    w = week or date.today().isocalendar()[1]
    step = 1 if c.get("cadence", "weekly") == "weekly" else 2
    return areas[((w - 1) // step) % len(areas)], w


def num(s: str) -> float:
    try:
        return float((s or "").replace(",", "")) or 0.0
    except ValueError:
        return 0.0


def companies_block(groups: list[str]) -> dict | None:
    if not groups:
        return None
    rows = load_all_companies()
    for r in rows:
        r["group"] = classify(r["sector_code"], r["sector"], r["product"])
    sel = [r for r in rows if r["group"] in groups]
    w = lambda rs: sum(int(r["workers"]) for r in rs if (r.get("workers") or "").isdigit())  # noqa: E731
    bands = Counter()
    for r in sel:
        if (r.get("workers") or "").isdigit():
            n = int(r["workers"])
            for b, lo, hi in SIZE:
                if lo <= n <= hi:
                    bands[b] += 1
                    break
        else:
            bands["값 없음"] += 1
    return {
        "groups": groups, "firms": len(sel), "employment": w(sel), "covered": sum(1 for r in sel if (r.get("workers") or "").isdigit()),
        "total_firms": len(rows), "total_employment": w(rows),
        "share_firms_pct": round(len(sel) / len(rows) * 100, 1), "share_employment_pct": round(w(sel) / w(rows) * 100, 1),
        "size_bands": dict(bands), "under_50": sum(1 for r in sel if (r.get("workers") or "").isdigit() and int(r["workers"]) < 50),
        "complexes": Counter(r["complex"] for r in sel).most_common(8),
        "districts": Counter(r["district"] for r in sel).most_common(),
        "site_types": Counter(r["site_type"] for r in sel).most_common(),
        "sub_sectors": Counter((r["sector_code"], r["sector"].split(" 외")[0]) for r in sel).most_common(10),
        "as_of": sel[0]["as_of"] if sel else "",
        "condition": f"config/industry_groups.yml 그룹 {groups} (팩토리온 + 산단 외 목록, 종사자는 공장등록 신고값)",
    }


def programs_block(keywords: list[str]) -> list[dict]:
    pat = re.compile("|".join(map(re.escape, keywords)), re.I)
    out, seen = [], set()
    for f in PROGRAM_FILES:
        p = DATA / f
        if not p.exists():
            continue
        for r in csv.DictReader(open(p, encoding="utf-8")):
            text = f"{r.get('name', '')} {r.get('purpose', '')[:300]} {r.get('beneficiary', '')}"
            if not r.get("name") or r["code"] in seen or not pat.search(text):
                continue
            seen.add(r["code"])
            out.append({"ministry": r["ministry"], "code": r["code"], "name": r["name"], "budget_2025": r.get("budget_2025", ""),
                        "budget_2026": r.get("budget_2026", ""), "new": r.get("new_or_continue", ""), "scope": r.get("region_scope", ""), "src": f})
    return sorted(out, key=lambda x: -num(x["budget_2026"]))


def city_match_block(keywords: list[str]) -> list[dict]:
    pat = re.compile("|".join(map(re.escape, keywords)), re.I)
    out = []
    for f in ("match_daegu_national.csv", "match_daegu_motie.csv"):
        p = DATA / f
        if not p.exists():
            continue
        for r in csv.DictReader(open(p, encoding="utf-8")):
            if pat.search(" ".join(r.values())):
                out.append({"file": f, **r})
    return out


def posts_block(keywords: list[str], weeks: int = 8) -> list[dict]:
    pat = re.compile("|".join(map(re.escape, keywords)), re.I)
    since = date.today() - timedelta(weeks=weeks)
    out = []
    for p in sorted(POSTS.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        fm = parts[1]
        m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", fm, re.M)
        if not m or date.fromisoformat(m.group(1)) < since:
            continue
        if not pat.search(text):
            continue
        g = lambda k: (re.search(rf"^{k}:\s*\"?(.*?)\"?\s*$", fm, re.M) or [None, ""])[1]  # noqa: E731
        out.append({"file": p.name, "date": m.group(1), "title": g("title"), "category": g("category"), "source": g("source"),
                    "deadline": g("deadline"), "draft": g("draft") == "true"})
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area")
    ap.add_argument("--week", type=int)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    c = cfg()
    area, week = pick_area(c, a.week, a.area)
    ctx = {
        "pledge_of": c.get("pledge_of", ""), "source_url": c.get("source_url", ""), "week": week, "area": area,
        "companies": companies_block(area.get("industry_groups", [])),
        "programs": programs_block(area.get("keywords", [])),
        "city_match": city_match_block(area.get("keywords", [])),
        "posts_8w": posts_block(area.get("keywords", [])),
    }
    if a.json:
        print(json.dumps(ctx, ensure_ascii=False, indent=1, default=str))
        return 0
    print(f"ISO {week}주 → 분야 [{area['key']}] {area['name']}  (공약: {c.get('pledge_of')})")
    print(f"공약 항목 {len(area.get('pledges') or [])}개: " + (" / ".join(area.get("pledges") or []) or "— 비어 있음, config/pledge_areas.yml 에 채울 것"))
    cb = ctx["companies"]
    if cb:
        print(f"\n[기업 사전 {cb['as_of']}] 기업 {cb['firms']:,}곳 · 고용 {cb['employment']:,}명(집계 대상 {cb['covered']:,}) · 대구 내 비중 기업 {cb['share_firms_pct']}% 고용 {cb['share_employment_pct']}%")
        print(f"  규모 {cb['size_bands']} · 50인 미만 {cb['under_50']:,}곳")
        print("  단지 " + ", ".join(f"{k} {v}" for k, v in cb["complexes"]))
        print("  입지 유형 " + ", ".join(f"{k} {v}" for k, v in cb["site_types"]))
        print("  세분류 " + ", ".join(f"{k[0]} {k[1][:18]} {v}" for k, v in cb["sub_sectors"][:6]))
        print(f"  조건: {cb['condition']}")
    else:
        print("\n[기업 사전] 연결 산업 그룹 없음 → 사업 DB·예산·공고 숫자만 사용")
    print(f"\n[사업 DB] 키워드 {area.get('keywords')} 일치 {len(ctx['programs'])}건 (2026 예산 순, 백만 원)")
    for p in ctx["programs"][:15]:
        print(f"  {p['ministry']} {p['code']} {p['name'][:40]} | 2025 {p['budget_2025']} → 2026 {p['budget_2026']} {p['new']} {p['scope']}")
    print(f"\n[대구시 매칭] {len(ctx['city_match'])}건")
    for m in ctx["city_match"][:10]:
        print(f"  {m.get('대구시 세부사업', '')[:36]} | 시 2026 {m.get('대구시 2026(천원)', '')}천원 | 국비 {m.get('코드', '')} {m.get('국비 2026(백만원)', m.get('산업부 2026(백만원)', ''))}백만원")
    print(f"\n[최근 8주 글] {len(ctx['posts_8w'])}건")
    for p in ctx["posts_8w"][:15]:
        print(f"  {p['date']} [{p['category']}] {p['title'][:60]}{' (마감 ' + p['deadline'] + ')' if p['deadline'] else ''}{' draft' if p['draft'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
