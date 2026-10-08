#!/usr/bin/env python3
"""산업 묶음(KSIC 세세분류 묶음)별 생산액·부가가치 비교표 → data/kosis/industry_bundles.json (운영자 지시 2026-10-08 '이 내용으로 산업 통계 페이지에 표로 넣어').

묶음 정의(업종 코드)와 대구 묶음 값은 대구정책연구원 「지역과 대학의 상생발전을 위한 전략 수립」(연구 2026-09) 표 4-4~4-12 —
data/refs/dpi-2026-university-region-mutual-development.json 의 industry_codes·key_figures 에서 옮겼다(아래 REPORT).
전국 값은 KOSIS 광업·제조업조사 DT_1FS1104(시도/산업분류별, 10인 이상) 2023년 전국 세세분류 칸을 같은 코드로 더한 값
(data/kosis/mining-mfg-survey-national-ksic5.csv). 대구는 KOSIS 에 중분류까지만 공개되므로 묶음이 걸친 중분류 합을 함께 둔다.
나눗셈·덧셈만, 평가 없음.

전국 세세분류 칸 갱신: kosis.yml 입력 probe='mining-mfg-survey-sido@00@C30310,…@연도' 로 돌린 로그를 받아
  python3 scripts/industry_bundles.py --from-log 로그파일 --year 2023
"""
from __future__ import annotations
import argparse, csv, json, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "data/refs/dpi-2026-university-region-mutual-development.json"
NAT = ROOT / "data/kosis/mining-mfg-survey-national-ksic5.csv"
SIDO = ROOT / "data/kosis/mining-mfg-survey-sido.csv"
META = ROOT / "data/kosis/mining-mfg-survey-sido.meta.json"
OUT = ROOT / "data/kosis/industry_bundles.json"
YEAR = "2023"

# 보고서 표의 대구 2023년 값(사업체·종사자 1인 이상 전국사업체조사, 생산액·부가가치 10인 이상 광업·제조업조사, 백만 원)과
# 보고서에 적힌 전국 2023년 생산액·부가가치(있는 묶음만). key 는 ref 의 industry_codes 이름.
REPORT = {
    "전기·자율 모빌리티부품": dict(table="표 4-4", role="주력산업", est=1110, emp=15319, prod=5714753, va=1760639, nat_prod=101649441),
    "기계요소 소재부품": dict(table="표 4-5", role="주력산업", est=4593, emp=24132, prod=8253874, va=1414013, nat_prod=114525589),
    "디지털 의료기기": dict(table="표 4-6", role="주력산업", est=1854, emp=8825, prod=715080, va=469919, nat_prod=11254689, nat_va=6174587),
    "미래모빌리티": dict(table="표 4-8", role="미래 신산업", est=2150, emp=26500, prod=13774167, va=2913078),
    "로봇": dict(table="표 4-9", role="미래 신산업", est=964, emp=7452, prod=3254564, va=1274380),
    "헬스케어": dict(table="표 4-10", role="미래 신산업", est=494, emp=3916, prod=595431, va=389487),
    "반도체": dict(table="표 4-11", role="미래 신산업", est=102, emp=1559, prod=344045, va=119505),
    "ABB": dict(table="표 4-12", role="미래 신산업", est=1791, emp=9686, prod=18545, va=10101),
}
SURVEY_OUT = ("58", "62", "63")   # 정보통신 서비스 — 광업·제조업조사 대상 아님


def from_log(path: str, year: str) -> None:
    rows = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"\[cell 00×C(\d{5}) (\d{4})\] (.*)", line)
        if not m or m.group(2) != year:
            continue
        code, _, rest = m.groups()
        vals, name = {}, ""
        for part in rest.split(" | "):
            mm = re.match(r"(?:\d+행: )?(.+?) (사업체수|생산액|부가가치)=([^개백]*)", part)
            if mm:
                name, vals[mm.group(2)] = mm.group(1).strip(), mm.group(3)
        if vals:
            rows.append({"year": year, "ksic": code, "name": name, "establishments": vals.get("사업체수", ""),
                         "production": vals.get("생산액", ""), "value_added": vals.get("부가가치", "")})
    old = [r for r in csv.DictReader(NAT.open(encoding="utf-8"))] if NAT.exists() else []
    keep = [r for r in old if r["year"] != year]
    with NAT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["year", "ksic", "name", "establishments", "production", "value_added"])
        w.writeheader(); w.writerows(sorted(keep + rows, key=lambda r: (r["year"], r["ksic"])))
    print(f"[log] {year} 전국 세세분류 {len(rows)}칸 → {NAT.relative_to(ROOT)}")


def num(x: str):
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return None


def build(year: str) -> None:
    ref = json.loads(REF.read_text(encoding="utf-8"))
    nat = {r["ksic"]: r for r in csv.DictReader(NAT.open(encoding="utf-8")) if r["year"] == year}
    meta = json.loads(META.read_text(encoding="utf-8"))
    mid = {x["ITM_ID"][1:]: x["ITM_NM"] for x in meta if x["OBJ_ID"] != "ITEM" and len(x["ITM_ID"]) == 3}
    norm = lambda s: re.sub(r"[\s,]", "", s)
    dg: dict[str, dict[str, float | None]] = {}
    for r in csv.DictReader(SIDO.open(encoding="utf-8")):
        if r["C1_NM"] == "대구광역시" and r["PRD_DE"] == year:
            dg.setdefault(norm(r["C2_NM"]), {})[r["ITM_NM"]] = num(r["DT"])
    groups = []
    for name, g in ref["industry_codes"].items():
        if not isinstance(g, dict) or name not in REPORT:
            continue
        rep = REPORT[name]
        codes, ns, missing, renamed = [], Counter(), [], []
        for c in g["codes"]:
            k = c["ksic"]
            row = nat.get(k)
            if k[:2] in SURVEY_OUT:
                codes.append({"ksic": k, "name": c["name"], "scope": "조사 대상 아님"}); continue
            if not row:
                missing.append(k); codes.append({"ksic": k, "name": c["name"], "scope": f"{year}년 표에 없는 코드"}); continue
            v = {it: num(row[it]) for it in ("establishments", "production", "value_added")}
            if norm(row["name"])[:5] != norm(c["name"])[:5]:
                renamed.append(k)
            codes.append({"ksic": k, "name": c["name"], "kosis_name": row["name"], **v})
            for it, x in v.items():
                if x is not None:
                    ns[it] += x
        mids = sorted({c["ksic"][:2] for c in g["codes"] if c["ksic"][:2] not in SURVEY_OUT})
        up = Counter()
        for m in mids:
            d = dg.get(norm(mid.get(m, "")), {})
            for it, key in (("establishments", "사업체수"), ("production", "생산액"), ("value_added", "부가가치")):
                if isinstance(d.get(key), float):
                    up[it] += d[key]
        exact = not missing and not renamed
        nat_prod = ns["production"] or None
        groups.append({
            "name": name, "table": rep["table"], "role": rep["role"],
            "codes_n": len(g["codes"]), "codes_stated": g.get("count_stated"),
            "survey_out_n": sum(1 for c in g["codes"] if c["ksic"][:2] in SURVEY_OUT),
            "report": {k: rep[k] for k in ("est", "emp", "prod", "va")},
            "report_national": {k: rep[k] for k in ("nat_prod", "nat_va") if k in rep},
            "national": {"establishments": ns["establishments"] or None, "production": nat_prod, "value_added": ns["value_added"] or None,
                         "exact": exact, "missing": missing, "renamed": renamed},
            "national_matches_report": (rep.get("nat_prod") == nat_prod) if "nat_prod" in rep else None,
            "daegu_mid": {"codes": mids, "names": [mid.get(m, "") for m in mids], **{k: up[k] or None for k in ("establishments", "production", "value_added")}},
            "codes": codes,
        })
    out = {
        "year": int(year),
        "generated_from": ["data/refs/dpi-2026-university-region-mutual-development.json", str(NAT.relative_to(ROOT)), str(SIDO.relative_to(ROOT))],
        "report": {"title": "지역과 대학의 상생발전을 위한 전략 수립", "publisher": "대구정책연구원", "series": "연구 2026-09", "published": ref.get("published")},
        "kosis": {"tbl_id": "DT_1FS1104", "name": "광업·제조업조사 시도/산업분류별 주요 지표(10인 이상)", "url": "https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1FS1104"},
        "groups": groups,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for g in groups:
        print(f"{g['name']}: 전국 {g['national']['production']} (보고서 {g['report_national'].get('nat_prod')}) 정확={g['national']['exact']} 누락={g['national']['missing']} 이름다름={g['national']['renamed']}")
    print(f"→ {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-log", default="")
    ap.add_argument("--year", default=YEAR)
    a = ap.parse_args()
    if a.from_log:
        from_log(a.from_log, a.year)
    build(a.year)
