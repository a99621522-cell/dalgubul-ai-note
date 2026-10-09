#!/usr/bin/env python3
"""상위법령이 '조례로 정한다'고 맡겼는데 대구시·구군에 그 법령을 인용하는 자치법규가 없는 곳(위임 조례 미제정 후보) 찾기.

네트워크 없음. 입력
  data/ordinance/deleg_all.json.gz  — 현행 법령 전체의 '조례' 든 항·호(scripts/ordin/deleg_all.py, 러너)
  data/ordinance/lawrefs.json.gz    — 대구 자치법규가 인용한 법령(법령ID → 자치법규·조)
  data/ordinance/ordin/*.json.gz    — 대구 자치법규 전문(이름 대조용)
출력
  data/ordinance/unenacted.json     — 후보(법령·조·위임 문장·수준·없는 기관)
  docs/ordinance/unenacted_<날짜>.md

판정이 아니다: 위임 문장이 '조례로 정한다'(의무형)인 것만 고르고, '정할 수 있다'·'할 수 있다'(선택형)는 뺀다.
그래도 해당 사무가 없는 지자체(예: 하천·항만이 없는 곳)는 만들 필요가 없으므로 사람이 확인한다.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "ordinance"
ORGS = ["daegu", "jung", "dong", "seo", "nam", "buk", "suseong", "dalseo", "dalseong", "gunwi"]
GUGUN = ORGS[1:]
ORG_KO = {"daegu": "대구광역시", "jung": "중구", "dong": "동구", "seo": "서구", "nam": "남구", "buk": "북구",
          "suseong": "수성구", "dalseo": "달서구", "dalseong": "달성군", "gunwi": "군위군"}

# 다른 지역에만 적용되는 법령(이름) — 대구와 무관
OTHER_REGION = re.compile(r"제주|세종|새만금|강원|전북|전라|경상|충청|부산|인천|울산|광주|대전|경기|서울|수도권|평택|여수|동해|서해|접경|섬|도서|해양|어촌|항만|수산|어업|원자력발전소|방폐|탄광|폐광|댐\s*주변|주한미군|공여구역")
# 위임 주체 → 수준
SIDO = re.compile(r"(시ㆍ도|시·도|특별시ㆍ광역시|광역시ㆍ|광역시의|시ㆍ도지사가|시ㆍ도\s*및)")
SIGUNGU = re.compile(r"(시ㆍ군ㆍ구|시·군·구|자치구|시장ㆍ군수ㆍ구청장|시ㆍ군|구청장)")
ONLY_OTHER = re.compile(r"^(?!.*(시ㆍ도|시ㆍ군|지방자치단체|자치구|광역시)).*(특별자치도|특별자치시|도의\s*조례|시ㆍ군의\s*조례)")
MANDATORY = re.compile(r"조례로\s*정한다|조례로\s*정하여야\s*한다|조례로\s*정해야\s*한다|조례에서\s*정한다|조례로\s*(이를\s*)?정한다")
OPTIONAL = re.compile(r"조례로\s*(달리\s*)?정할\s*수\s*있|할\s*수\s*있다\.?$|할\s*수\s*있으며|있다\.\s*이\s*경우")


def jl(p: Path, d):
    if not p.exists():
        return d
    with (gzip.open(p, "rt", encoding="utf-8") if p.suffix == ".gz" else open(p, encoding="utf-8")) as f:
        return json.load(f)


def base_name(n: str) -> str:
    return re.sub(r"\s*(시행령|시행규칙)$", "", n).strip()


def core(n: str) -> str:
    """법령 이름의 핵심 낱말(자치법규 이름 대조용): '… 등에 관한 법률' 따위를 뗀다."""
    n = base_name(n)
    n = re.sub(r"(에\s*관한|의|을|를)?\s*(특별법|법률|법)$", "", n)
    n = re.sub(r"\s*(등|및)\s*$", "", n)
    return re.sub(r"\s+", "", n)


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
    laws = jl(D / "deleg_all.json.gz", {})
    if not laws:
        print("deleg_all.json.gz 없음 — 러너 실행(ordinance_deleg_all.yml) 뒤에 돌린다")
        return
    refs = jl(D / "lawrefs.json.gz", {})
    # 법령 묶음(법·시행령·시행규칙) 이름 → 인용한 기관 집합
    cited = defaultdict(set)
    for lid, r in refs.items():
        for x in r.get("refs") or []:
            cited[base_name(r["name"])].add(x["org"])
    names = defaultdict(list)  # 기관 → 자치법규 이름(공백 없앰)
    for f in (D / "ordin").glob("*.json.gz"):
        for x in jl(f, {}).get("items") or []:
            names[x["org"]].append(re.sub(r"\s+", "", x["name"]))

    out = []
    for mst, L in laws.items():
        if not L["units"] or OTHER_REGION.search(L["name"]):
            continue
        fam = base_name(L["name"])
        for a, t, x in L["units"]:
            s = x
            if not MANDATORY.search(s) or OPTIONAL.search(s):
                continue
            if ONLY_OTHER.search(s):
                continue
            lvl = "sido" if SIDO.search(s) and not SIGUNGU.search(s) else ("sigungu" if SIGUNGU.search(s) and not SIDO.search(s) else "any")
            targets = ["daegu"] if lvl == "sido" else (GUGUN if lvl == "sigungu" else ORGS)
            have = cited.get(fam, set())
            c = core(L["name"])
            byname = {o for o in ORGS if len(c) >= 2 and any(c in n for n in names[o])}
            if lvl == "any":
                miss = [] if (have | byname) else ORGS
            else:
                miss = [o for o in targets if o not in have and o not in byname]
            if not miss:
                continue
            out.append({"law": L["name"], "kind": L["kind"], "law_id": L["id"], "art": a, "title": t, "text": s,
                        "level": lvl, "missing": miss, "cited_any": sorted(have), "byname": sorted(byname)})
    # 같은 법령·조는 한 줄로
    seen, uniq = set(), []
    for r in out:
        k = (r["law"], r["art"], r["text"][:60])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    uniq.sort(key=lambda r: (r["level"], base_name(r["law"]), r["law"], r["art"]))
    (D / "unenacted.json").write_text(json.dumps({"built": day, "items": uniq}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    L = [f"# 위임 조례 미제정 후보 — 자동 목록 ({day}, 세션 대조 전)", "",
         "현행 법령 전체에서 '조례로 정한다'(의무형) 위임 문장을 뽑아, 대구시·구군 자치법규 가운데 그 법령(법·시행령·시행규칙 묶음)을 인용하거나 이름에 법령 핵심 낱말이 든 것이 없는 곳.",
         "선택형('정할 수 있다')·다른 지역 법령은 뺐다. 해당 사무가 없는 지자체는 만들 필요가 없으므로 사람이 확인한다.", "",
         f"후보 {len(uniq)}건 — 시·도 {sum(r['level']=='sido' for r in uniq)}, 시·군·구 {sum(r['level']=='sigungu' for r in uniq)}, 지방자치단체(구분 없음) {sum(r['level']=='any' for r in uniq)}", "",
         "| 수준 | 법령 | 조 | 위임 문장 | 없는 기관 | 이 법령을 인용한 기관 |", "|---|---|---|---|---|---|"]
    for r in uniq:
        lv = {"sido": "시·도", "sigungu": "시·군·구", "any": "구분 없음"}[r["level"]]
        miss = "전부" if len(r["missing"]) == len(ORGS) or (r["level"] == "sigungu" and len(r["missing"]) == len(GUGUN)) else ", ".join(ORG_KO[o] for o in r["missing"])
        ca = ", ".join(ORG_KO[o] for o in r["cited_any"]) or "-"
        L.append(f"| {lv} | {r['law']} | {r['art']}({r['title']}) | {r['text'][:160].replace('|', '｜')} | {miss} | {ca} |")
    p = ROOT / "docs" / "ordinance" / f"unenacted_scan_{day}.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(p, len(uniq))


if __name__ == "__main__":
    main()
