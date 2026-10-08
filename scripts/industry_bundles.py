#!/usr/bin/env python3
"""대구 주력·미래 신산업 관련 업종(통계청 중분류) 표 → data/kosis/industry_bundles.json

운영자 지시 2026-10-08 '통계청 자료로 작성하는게 정확할 것 같은데': 연구 보고서의 대구 수치(세세분류 묶음 값, 공개 통계로
다시 만들 수 없음)는 쓰지 않고, 통계청 KOSIS 가 대구까지 공개하는 중분류 값만 쓴다. 산업 묶음은 대구정책연구원
「지역과 대학의 상생발전을 위한 전략 수립」(연구 2026-09)의 업종 코드 정의만 빌려(data/refs/… industry_codes)
묶음이 걸친 중분류를 고르는 데 쓴다 — 묶음 값이 아니라 그 묶음을 포함하는 중분류 전체의 값이다.

입력(모두 KOSIS, kosis.yml 이 갱신)
  data/kosis/mining-mfg-survey-sido.csv       광업·제조업조사 DT_1FS1104 (10인 이상) — 대구·전국, 사업체수·생산액·부가가치
  data/kosis/biz-census-sido-industry-all.csv 전국사업체조사 (1인 이상) — 17개 시도·전국, 사업체수·종사자수
  *.meta.json                                  중분류 코드 → 이름
덧셈·나눗셈(전국 대비 비중, 부가가치율)만, 평가·순위 없음.
"""
from __future__ import annotations
import csv, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
K = ROOT / "data/kosis"
REF = ROOT / "data/refs/dpi-2026-university-region-mutual-development.json"
OUT = K / "industry_bundles.json"
ROLE = {"전기·자율 모빌리티부품": "주력산업", "기계요소 소재부품": "주력산업", "디지털 의료기기": "주력산업"}

norm = lambda s: re.sub(r"[\s,;·ㆍ]", "", s or "")


def num(x: str):
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return None   # 'X'(비공개)·'-' 는 값 없음


def mid_names(meta: Path) -> dict[str, str]:
    """'C27' 같은 문자+2자리 분류 → 이름"""
    out = {}
    for x in json.loads(meta.read_text(encoding="utf-8")):
        i = x.get("ITM_ID", "")
        if x.get("OBJ_ID") != "ITEM" and re.fullmatch(r"[A-Z]\d\d", i):
            out[i[1:]] = x["ITM_NM"]
    return out


def table(path: Path, area: dict[str, str]) -> tuple[dict, list[str]]:
    """(지역, 연도, 정규화 산업 이름, 항목) → 값. area: CSV 지역 이름 → 'dg'|'nat'"""
    v: dict = {}
    years = set()
    for r in csv.DictReader(path.open(encoding="utf-8")):
        a = area.get(r["C1_NM"])
        if not a or (r.get("C3_NM") not in ("", "계", None)):
            continue
        v[(a, r["PRD_DE"], norm(r["C2_NM"]), r["ITM_NM"])] = num(r["DT"])
        years.add(r["PRD_DE"])
    return v, sorted(years)


def latest_with(v: dict, years: list[str], item: str) -> str | None:
    for y in reversed(years):
        if any(k[0] == "dg" and k[1] == y and k[3] == item for k in v) and any(k[0] == "nat" and k[1] == y and k[3] == item for k in v):
            return y
    return None


def main() -> None:
    ref = json.loads(REF.read_text(encoding="utf-8"))
    sv, sy = table(K / "mining-mfg-survey-sido.csv", {"대구광역시": "dg", "전국": "nat"})
    cv, cy = table(K / "biz-census-sido-industry-all.csv", {"대구": "dg", "전국": "nat"})
    s_year, c_year = latest_with(sv, sy, "생산액"), latest_with(cv, cy, "사업체수")
    names = {**mid_names(K / "biz-census-sido-industry-all.meta.json"), **mid_names(K / "mining-mfg-survey-sido.meta.json")}

    bundles, mids = [], {}
    for name, g in ref["industry_codes"].items():
        if not isinstance(g, dict):
            continue
        codes = [{"ksic": c["ksic"], "name": c["name"]} for c in g["codes"]]
        ms = sorted({c["ksic"][:2] for c in codes})
        bundles.append({"name": name, "role": ROLE.get(name, "미래 신산업"), "page": g.get("page"), "codes": codes, "mids": ms})
        for m in ms:
            mids.setdefault(m, []).append(name)

    def cell(v, a, y, n, item):
        return v.get((a, y, norm(n), item)) if y else None

    rows = []
    for m in sorted(mids):
        n = names.get(m, "")
        s = {it: {a: cell(sv, a, s_year, n, it) for a in ("dg", "nat")} for it in ("사업체수", "생산액", "부가가치")}
        c = {it: {a: cell(cv, a, c_year, n, it) for a in ("dg", "nat")} for it in ("사업체수", "종사자수")}
        in_survey = any(s[it]["nat"] is not None for it in s)
        rows.append({"code": m, "name": n, "bundles": mids[m], "manufacturing": in_survey,
                     "census": {"est": c["사업체수"], "emp": c["종사자수"]},
                     "survey": {"est": s["사업체수"], "prod": s["생산액"], "va": s["부가가치"]} if in_survey else None})
    tot_s = {it: {a: sv.get((a, s_year, norm("제조업(10~34)"), it)) for a in ("dg", "nat")} for it in ("사업체수", "생산액", "부가가치")}
    tot_c = {it: {a: cv.get((a, c_year, norm("제조업(10~34)"), it)) for a in ("dg", "nat")} for it in ("사업체수", "종사자수")}
    out = {
        "survey_year": int(s_year) if s_year else None, "census_year": int(c_year) if c_year else None,
        "definition": {"publisher": "대구정책연구원", "title": "지역과 대학의 상생발전을 위한 전략 수립", "series": "연구 2026-09", "published": ref.get("published")},
        "sources": [
            {"name": "광업·제조업조사 시도/산업분류별 주요 지표(10인 이상)", "tbl_id": "DT_1FS1104", "url": "https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1FS1104"},
            {"name": "전국사업체조사 시도·산업별 사업체수·종사자수", "tbl_id": json.loads((K / "biz-census-sido-industry-all.json").read_text(encoding="utf-8")).get("tbl_id", ""),
             "url": json.loads((K / "biz-census-sido-industry-all.json").read_text(encoding="utf-8")).get("source_url", "")},
        ],
        "mfg_total": {"census": {"est": tot_c["사업체수"], "emp": tot_c["종사자수"]}, "survey": {"est": tot_s["사업체수"], "prod": tot_s["생산액"], "va": tot_s["부가가치"]}},
        "rows": rows, "bundles": bundles,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"광업·제조업조사 {s_year} · 전국사업체조사 {c_year} · 중분류 {len(rows)}개 → {OUT.relative_to(ROOT)}")
    for r in rows:
        s = r["survey"]
        print(f"  {r['code']} {r['name']}: 사업체(1인+) {r['census']['est']} 생산액 {s and s['prod']} 묶음 {','.join(r['bundles'])}")


if __name__ == "__main__":
    main()
