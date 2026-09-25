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
    off = int(c.get("week_offset", 1))
    return areas[((w - off) // step) % len(areas)], w


def num(s: str) -> float:
    try:
        return float((s or "").replace(",", "")) or 0.0
    except ValueError:
        return 0.0


def companies_block(groups: list[str], sub_counts: dict | None = None, tags: list[str] | None = None, site_types: list[str] | None = None, ksic: list[str] | None = None) -> dict | None:
    """분야 기업 = 산업 그룹 ∪ KSIC 접두어 ∪ 태그 ∪ 입지 유형 가운데 지정된 것. 아무것도 없으면 None (사업 DB·예산 숫자만 쓴다)."""
    if not (groups or tags or site_types or ksic):
        return None
    rows = load_all_companies()
    for r in rows:
        r["group"] = classify(r["sector_code"], r["sector"], r["product"])
    ks = tuple(str(k) for k in (ksic or []))
    sel = [r for r in rows if (groups and r["group"] in groups) or (ks and r["sector_code"].startswith(ks)) or (tags and r["tags"] & set(tags)) or (site_types and r["site_type"] in site_types)]
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
        "groups": groups, "ids": [r["id"] for r in sel], "firms": len(sel), "employment": w(sel), "covered": sum(1 for r in sel if (r.get("workers") or "").isdigit()),
        "total_firms": len(rows), "total_employment": w(rows),
        "share_firms_pct": round(len(sel) / len(rows) * 100, 1), "share_employment_pct": round(w(sel) / w(rows) * 100, 1),
        "size_bands": dict(bands), "under_50": sum(1 for r in sel if (r.get("workers") or "").isdigit() and int(r["workers"]) < 50),
        "complexes": Counter(r["complex"] for r in sel).most_common(8),
        "districts": Counter(r["district"] for r in sel).most_common(),
        "site_types": Counter(r["site_type"] for r in sel).most_common(),
        "sub_sectors": Counter((r["sector_code"], r["sector"].split(" 외")[0]) for r in sel).most_common(10),
        "sub_counts": {name: _sub_count(sel, spec, w) for name, spec in (sub_counts or {}).items()},
        "as_of": sel[0]["as_of"] if sel else "",
        "condition": " ∪ ".join(x for x in [f"산업 그룹 {groups}" if groups else "", f"KSIC {list(ks)}" if ks else "", f"태그 {tags}" if tags else "", f"입지 유형 {site_types}" if site_types else ""] if x)
                     + " (팩토리온 + 산단 외 목록, 종사자는 공장등록 신고값)",
        "tag_data_note": None if any(r["tags"] for r in rows) else "태그 자료 없음 — scripts/data/extra/ 목록·company_tags.csv 가 들어오면 채워짐",
    }


def _sub_count(sel: list[dict], spec: dict, w) -> dict:
    """분야 안에서 따로 세는 업종: ksic 접두어 목록 또는 업종명·생산품 키워드."""
    pre = tuple(str(x) for x in spec.get("ksic", []))
    kws = spec.get("keywords", [])
    tg = set(spec.get("tags", []))
    st = set(spec.get("site_types", []))
    hit = [r for r in sel if (pre and r["sector_code"].startswith(pre)) or (kws and any(k in f"{r['sector']} {r['product']}" for k in kws))
           or (tg and r["tags"] & tg) or (st and r["site_type"] in st)]
    cond = " ".join(x for x in [f"KSIC {list(pre)}" if pre else "", f"키워드 {kws}" if kws else "", f"태그 {sorted(tg)}" if tg else "", f"입지 {sorted(st)}" if st else ""] if x)
    return {"firms": len(hit), "employment": w(hit), "condition": cond}


def kw_pattern(keywords: list[str]) -> re.Pattern:
    """영문·숫자만인 키워드(AI, SDV, ABB)는 단어 단위·대소문자 그대로, 한글 키워드는 부분 일치."""
    parts = []
    for k in keywords:
        e = re.escape(k)
        parts.append(rf"(?<![A-Za-z0-9]){e}(?![A-Za-z0-9])" if re.fullmatch(r"[A-Za-z0-9 .\-]+", k) else e)
    return re.compile("|".join(parts))


def programs_block(keywords: list[str]) -> list[dict]:
    pat = kw_pattern(keywords)
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
    pat = kw_pattern(keywords)
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
    pat = kw_pattern(keywords)
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
        if not pat.search(text.replace("AI 초안", "")):
            continue
        g = lambda k: (re.search(rf"^{k}:\s*\"?(.*?)\"?\s*$", fm, re.M) or [None, ""])[1]  # noqa: E731
        out.append({"file": p.name, "date": m.group(1), "title": g("title"), "category": g("category"), "source": g("source"),
                    "deadline": g("deadline"), "draft": g("draft") == "true"})
    return out


NOTICES = ROOT / "data" / "notices" / "notices.csv"
SUPPORT = ROOT / "scripts" / "data" / "support_history.csv"


def notices_block(area_key: str, keywords: list[str], weeks: int = 8) -> list[dict]:
    """최근 8주 공고(data/notices/notices.csv, collect.py 가 사실만 기록). 분야 key 가 붙었거나 키워드가 제목에 있으면."""
    if not NOTICES.exists():
        return []
    pat = kw_pattern(keywords) if keywords else None
    since = (date.today() - timedelta(weeks=weeks)).isoformat()
    out = []
    for r in csv.DictReader(open(NOTICES, encoding="utf-8")):
        if r.get("collected", "") < since:
            continue
        if area_key in (r.get("areas") or "").split(";") or (pat and pat.search(r.get("title", ""))):
            out.append(r)
    return out


def support_block(company_ids: set[str], years: int = 3) -> dict:
    """분야 기업의 지원사업 수혜 이력(최근 n년): 기업 수·건수·기관별·사업별 상위."""
    if not SUPPORT.exists():
        return {"firms": 0, "records": 0, "by_funder": [], "by_program": []}
    y0 = date.today().year - years + 1
    recs = [r for r in csv.DictReader(open(SUPPORT, encoding="utf-8")) if r.get("id") in company_ids and (r.get("year") or "").isdigit() and int(r["year"]) >= y0]
    return {"firms": len({r["id"] for r in recs}), "records": len(recs),
            "by_funder": Counter(r["funder"] for r in recs).most_common(10), "by_program": Counter(r["program"] for r in recs).most_common(10)}


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
        "companies": companies_block(area.get("industry_groups", []), area.get("sub_counts"), area.get("tags"), area.get("site_types"), area.get("ksic")),
        "programs": programs_block(area.get("keywords", [])),
        "city_match": city_match_block(area.get("keywords", [])),
        "posts_8w": posts_block(area.get("keywords", [])),
        "notices_8w": notices_block(area["key"], area.get("keywords", [])),
    }
    ctx["support_3y"] = support_block(set(ctx["companies"]["ids"]) if ctx["companies"] else set())
    if a.json:
        print(json.dumps(ctx, ensure_ascii=False, indent=1, default=str))
        return 0
    print(f"ISO {week}주 → 분야 [{area['key']}] {area['name']}  (공약: {c.get('pledge_of')})")
    print(f"공약 항목 {len(area.get('pledges') or [])}개: " + (" / ".join(area.get("pledges") or []) or "— 비어 있음, config/pledge_areas.yml 에 채울 것"))
    if area.get("focus"):
        print(f"관점: {area['focus']}")
    cb = ctx["companies"]
    if cb:
        print(f"\n[기업 사전 {cb['as_of']}] 기업 {cb['firms']:,}곳 · 고용 {cb['employment']:,}명(집계 대상 {cb['covered']:,}) · 대구 내 비중 기업 {cb['share_firms_pct']}% 고용 {cb['share_employment_pct']}%")
        print(f"  규모 {cb['size_bands']} · 50인 미만 {cb['under_50']:,}곳")
        print("  단지 " + ", ".join(f"{k} {v}" for k, v in cb["complexes"]))
        print("  입지 유형 " + ", ".join(f"{k} {v}" for k, v in cb["site_types"]))
        print("  세분류 " + ", ".join(f"{k[0]} {k[1][:18]} {v}" for k, v in cb["sub_sectors"][:6]))
        for name, v in cb["sub_counts"].items():
            print(f"  ▸ {name}: {v['firms']:,}곳 · {v['employment']:,}명 ({v['condition']})")
        print(f"  조건: {cb['condition']}")
        if cb.get("tag_data_note"):
            print(f"  ※ {cb['tag_data_note']}")
    else:
        print("\n[기업 사전] 연결 산업 그룹·태그·입지 유형 없음 → 사업 DB·예산·공고 숫자만 사용")
    print(f"\n[사업 DB] 키워드 {area.get('keywords')} 일치 {len(ctx['programs'])}건 (2026 예산 순, 백만 원)")
    for p in ctx["programs"][:15]:
        print(f"  {p['ministry']} {p['code']} {p['name'][:40]} | 2025 {p['budget_2025']} → 2026 {p['budget_2026']} {p['new']} {p['scope']}")
    print(f"\n[대구시 매칭] {len(ctx['city_match'])}건")
    for m in ctx["city_match"][:10]:
        print(f"  {m.get('대구시 세부사업', '')[:36]} | 시 2026 {m.get('대구시 2026(천원)', '')}천원 | 국비 {m.get('코드', '')} {m.get('국비 2026(백만원)', m.get('산업부 2026(백만원)', ''))}백만원")
    sb = ctx["support_3y"]
    print(f"\n[지원사업 수혜 이력 최근 3년] 기업 {sb['firms']:,}곳 · {sb['records']:,}건" + ("" if sb["records"] else " (support_history.csv 비어 있음 — scripts/data/support/ 에 목록 투입)"))
    for k, v in sb["by_funder"][:6]:
        print(f"  {k}: {v}건")
    print(f"\n[최근 8주 공고(데이터)] {len(ctx['notices_8w'])}건")
    for n in ctx["notices_8w"][:10]:
        print(f"  {n['collected']} {n['scope']} {n['source'][:14]} | {n['title'][:56]}{' (마감 ' + n['deadline'] + ')' if n.get('deadline') else ''}")
    print(f"\n[최근 8주 글] {len(ctx['posts_8w'])}건")
    for p in ctx["posts_8w"][:15]:
        print(f"  {p['date']} [{p['category']}] {p['title'][:60]}{' (마감 ' + p['deadline'] + ')' if p['deadline'] else ''}{' draft' if p['draft'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
