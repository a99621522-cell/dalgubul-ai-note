#!/usr/bin/env python3
"""대경권 연계성 — 대구 공장등록 기업과 같은 이름의 경북 등록공장(운영자 지시 2026-10-20 '대구경북 같이 진행해 … 위 3개 넣어').
대구: scripts/data/dalseong_companies.csv(팩토리온 공장등록), 경북: data/supply/gb_factories.csv(산단공 전국 등록공장, 경북만; 같은 이름·시군·생산품 행은 하나로).
회사 이름(법인 표기·'제N공장' 제거)이 같으면 '이름 일치'(상한 — 같은 이름의 다른 회사가 섞임), 그중 대구 쪽 생산품·업종과 경북 생산품에 같은 낱말이 있으면
'이름+생산품 일치'(보수적 값). 결과 data/dg_linkage/firms_gb_factories.csv · firms_summary.json. 거래·소유 관계를 단정하지 않는다."""
import csv, collections, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/dg_linkage"


def norm(s):
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사|유한책임회사|\(합\)|합자회사|\(재\)|\(사\)|농업회사법인|영농조합법인", "", s or "")
    s = re.sub(r"제\s*\d+\s*공장|\d+\s*공장|본사공장|공장$|\(.*?\)", "", s)
    return re.sub(r"[\s·.,\-]", "", s).upper()


STOP = set("제조 부품 제품 기타 및 외 등 가공 용 생산 산업 기계 장치 설비 관련 류 자동차 금속".split())
toks = lambda s: {t for t in re.split(r"[\s,/·()\[\]]+", s or "") if len(t) >= 2 and t not in STOP}


def main():
    D = list(csv.DictReader(open(ROOT / "scripts/data/dalseong_companies.csv", encoding="utf-8")))
    G, seen = [], set()
    for g in csv.DictReader(open(ROOT / "data/supply/gb_factories.csv", encoding="utf-8")):
        k = (g["name"], g["sigungu"], g["product"])
        if g["name"] and k not in seen:
            seen.add(k); G.append(g)
    dm = collections.defaultdict(list)
    for r in D:
        k = norm(r["name"])
        if len(k) >= 3:
            dm[k].append(r)
    rows, loose, strict = [], collections.defaultdict(list), collections.defaultdict(list)
    for g in G:
        k = norm(g["name"])
        if len(k) < 3 or k not in dm:
            continue
        loose[k].append(g)
        dt = set().union(*[toks(r["product"]) | toks(r["sector"]) for r in dm[k]])
        hit = bool(dt & toks(g["product"]))
        if hit:
            strict[k].append(g)
        rep = max(dm[k], key=lambda r: int(r["workers"] or 0))
        rows.append({"key": k, "daegu_id": rep["id"], "daegu_name": rep["name"], "daegu_district": rep["district"], "daegu_group": rep["sector_group"],
                     "daegu_product": rep["product"], "daegu_workers": rep["workers"], "gb_name": g["name"], "gb_sigungu": g["sigungu"],
                     "gb_complex": g["complex"], "gb_product": g["product"], "product_overlap": int(hit), "gb_as_of": g["as_of"]})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "firms_gb_factories.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    rep = lambda k: max(dm[k], key=lambda r: int(r["workers"] or 0))
    summ = {"daegu_names": len(dm), "gb_factories": len(G),
            "loose": {"firms": len(loose), "factories": sum(map(len, loose.values()))},
            "strict": {"firms": len(strict), "factories": sum(map(len, strict.values())),
                       "daegu_workers": sum(int(rep(k)["workers"] or 0) for k in strict),
                       "by_gb_sigungu": collections.Counter(g["sigungu"] for v in strict.values() for g in v).most_common(),
                       "by_group": collections.Counter(rep(k)["sector_group"] for k in strict).most_common(),
                       "by_daegu_district": collections.Counter(rep(k)["district"] for k in strict).most_common()},
            "loose_by_gb_sigungu": collections.Counter(g["sigungu"] for v in loose.values() for g in v).most_common(),
            "as_of": {"daegu": D[0].get("as_of", ""), "gb": G[0].get("as_of", "")}}
    (OUT / "firms_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
