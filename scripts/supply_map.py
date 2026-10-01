#!/usr/bin/env python3
"""대구·경북 품목 지도 — 누가 무엇을 만드는가(공장등록 생산품) × 특정국 의존 품목(한국은행 공급망 지도).

입력
  scripts/data/dalseong_companies.csv   대구 공장등록 기업(팩토리온 월간, 업종 코드 있음)
  data/supply/gb_factories.csv          경북 공장등록(공공데이터포털 15105482, import_gb_factories.py, 업종 코드 없음)
  scripts/data/bok_dependency.csv       한국은행 「우리나라 주요 제조업 생산 및 공급망 지도」(2026.7) 특정국 의존 품목
출력 data/supply/
  items.csv     품목별 대구·경북 '생산품 등록 기업' 수와 예(이름·구군/시군). 생산품 낱말 대조라 역량·거래가 아니다
  groups.csv    산업 그룹별 대구·경북 기업 수(경북은 생산품 낱말로 짐작한 그룹)
  areas.csv     구·군 / 시·군 × 산업 그룹 기업 수
  summary.json  기준일·합계·출처
평가·순위 없음, 값 그대로. 개인 성명으로 보이는 이름은 예시에 쓰지 않는다. 운영자 지시 2026-10-01(대구·경북 공급망 지도, 1안).
사용: python3 scripts/supply_map.py
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import industry  # noqa: E402
from import_gb_factories import looks_like_person  # noqa: E402
from parse_bok_map import keywords, hit  # noqa: E402

DATA = ROOT / "scripts" / "data"
OUT = ROOT / "data" / "supply"
TOK = re.compile(r"[\s,、/·∙ㆍ()\[\]]+")


def tokens(raw: str) -> tuple[str, set[str]]:
    return re.sub(r"\s+", "", raw or ""), {re.sub(r"[^가-힣A-Za-z0-9]", "", t) for t in TOK.split(raw or "")}


def load() -> tuple[list[dict], list[dict], str, str]:
    dg = []
    as_dg = ""
    for c in csv.DictReader(open(DATA / "dalseong_companies.csv", encoding="utf-8")):
        prod, toks = tokens(c.get("product", ""))
        dg.append({"name": "" if looks_like_person(c["name"]) else c["name"], "area": c.get("district", ""), "prod": prod, "toks": toks,
                   "group": industry.classify(c.get("sector_code", ""), c.get("sector", ""), c.get("product", ""))})
        as_dg = as_dg or c.get("as_of", "")
    gb, as_gb = [], ""
    p = OUT / "gb_factories.csv"
    if p.exists():
        for c in csv.DictReader(open(p, encoding="utf-8")):
            prod, toks = tokens(c.get("product", ""))
            gb.append({"name": c["name"], "area": c.get("sigungu", ""), "prod": prod, "toks": toks, "group": c.get("group", "")})
            as_gb = as_gb or c.get("as_of", "")
    return dg, gb, as_dg, as_gb


def main() -> int:
    dg, gb, as_dg, as_gb = load()
    OUT.mkdir(parents=True, exist_ok=True)
    dep = list(csv.DictReader(open(DATA / "bok_dependency.csv", encoding="utf-8")))
    items, seen = [], set()
    for r in dep:
        key = (r["industry"], r["item"])
        if key in seen:
            continue
        seen.add(key)
        kws = keywords(r["item"])
        hd = [c for c in dg if c["prod"] and hit(kws, c["prod"], c["toks"])]
        hg = [c for c in gb if c["prod"] and hit(kws, c["prod"], c["toks"])]
        status = "대구·경북" if hd and hg else "대구만" if hd else "경북만" if hg else "없음"
        ex = lambda hs: "; ".join(f"{c['name']}({c['area']})" for c in [c for c in hs if c["name"]][:3])
        items.append({"industry": r["industry"], "section": r["section"], "country": r["country"], "item": r["item"], "hs_code": r["hs_code"],
                      "amount_musd": r["amount_musd"], "share_pct": r["share_pct"], "keywords": " ".join(kws),
                      "daegu_n": len(hd), "gb_n": len(hg), "status": status, "daegu_ex": ex(hd), "gb_ex": ex(hg), "page": r["page"]})
    with open(OUT / "items.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(items[0].keys()))
        w.writeheader(); w.writerows(items)

    gd, gg = Counter(c["group"] for c in dg), Counter(c["group"] for c in gb)
    groups = [{"group": g, "daegu_n": gd.get(g, 0), "gb_n": gg.get(g, 0)} for g in sorted(set(gd) | set(gg), key=lambda g: -(gd.get(g, 0) + gg.get(g, 0)))]
    with open(OUT / "groups.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["group", "daegu_n", "gb_n"]); w.writeheader(); w.writerows(groups)

    areas = defaultdict(Counter)
    for sido, rows in (("대구", dg), ("경북", gb)):
        for c in rows:
            areas[(sido, c["area"] or "—")][c["group"]] += 1
    with open(OUT / "areas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sido", "area", "group", "n"]); w.writeheader()
        for (sido, area), cnt in sorted(areas.items(), key=lambda kv: (kv[0][0] != "대구", -sum(kv[1].values()))):
            for g, n in cnt.most_common():
                w.writerow({"sido": sido, "area": area, "group": g, "n": n})

    st = Counter(i["status"] for i in items)
    summary = {"as_of_daegu": as_dg, "as_of_gb": as_gb, "n_daegu": len(dg), "n_gb": len(gb), "items": len(items), "status": dict(st),
               "sources": {"daegu": "팩토리온 전국(개별·계획) 입주업체현황 월간 엑셀(한국산업단지공단)",
                           "gb": "한국산업단지공단_전국등록공장현황_등록공장현황자료(공공데이터포털 15105482)",
                           "gb_url": "https://www.data.go.kr/data/15105482/fileData.do",
                           "bok": "한국은행 「우리나라 주요 제조업 생산 및 공급망 지도」(2026.7)"}}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[supply] 대구 {len(dg):,}곳({as_dg}) · 경북 {len(gb):,}곳({as_gb or '없음'}) · 의존 품목 {len(items)}개 {dict(st)} → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
