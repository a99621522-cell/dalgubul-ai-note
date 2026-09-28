#!/usr/bin/env python3
"""KOSIS 통계표(data/kosis) + 산업구조지수(structure_index.csv) → 사이트용 표·그래프 (src/generated/kosis/).

- 표: index.json 의 tables[] (id·title·columns·rows·unit·source·latest·note). 페이지 /stats/kosis/ 가 그대로 표(table.data-table)로 그린다.
- 그래프: render_charts.py 의 line_chart·bar_chart 로 넓은 판(.svg)·좁은 판(.m.svg)·표(.json). index.json 의 charts{kind:{name:file}}.
- 자료가 없는 표는 건너뛴다(값을 만들지 않는다). 값은 KOSIS 그대로, 평가·순위 표현 없음(정렬은 값 크기순일 뿐).
사용: python3 scripts/render_kosis.py   (kosis.yml 이 수집 뒤 실행하고 커밋)
"""
import csv, json, re, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import render_charts as rc  # noqa: E402

K = ROOT / "data" / "kosis"
OUT = ROOT / "src" / "generated" / "kosis"
rc.OUT = OUT
_month_label = rc.month_label
rc.month_label = lambda m: m if "-" not in m else _month_label(m)     # 연도 라벨('2015')은 그대로
KOSIS = "https://kosis.kr/statHtml/statHtml.do?orgId={org}&tblId={tbl}"


def rows(key: str) -> list[dict]:
    p = K / f"{key}.csv"
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


def meta(key: str) -> dict:
    p = K / f"{key}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def num(v: str) -> float | None:
    try:
        return float(v.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def ym(p: str) -> str:
    return f"{p[:4]}-{p[4:6]}"


def src(key: str) -> str:
    m = meta(key)
    return f"KOSIS {m.get('tbl_nm') or m.get('name', '')}, 조회 {m.get('fetched', '')}"


def short(key: str) -> str:
    """그래프 안 메모(짧게): 표 이름만"""
    m = meta(key)
    return f"KOSIS {m.get('tbl_nm') or m.get('name', '')}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        f.unlink()
    tables, index = [], {}

    # 1) 산업구조지표 17개 시도
    si = list(csv.DictReader(open(K / "structure_index.csv", encoding="utf-8"))) if (K / "structure_index.csv").exists() else []
    if si:
        y = max(r["year"] for r in si)
        last = sorted([r for r in si if r["year"] == y], key=lambda r: -float(r["hhi"]))
        tables.append({"id": "structure17", "title": f"17개 시도 산업구조 지표 ({y}년, 24개 부문)", "unit": "",
                       "columns": ["시도", "산업집중도(HHI)", "특화산업 비중(%)", "고부가 3부문 비중(%)", "변화속도(연평균 2015~24)", "고부가 변화속도", "입지계수 상관(2015 대 2024)", "GRDP 실질 연평균 성장(%)", "노동생산성 연평균 증가(%)"],
                       "rows": [[r["region"], r["hhi"], r["spec_share_pct"], r["high_share_pct"], r["sci_avg_2015_2024"], r["sci_high_avg_2015_2024"], r["lq_corr_2015_2024"], r["grdp_cagr_2015_2024_pct"], r["productivity_cagr_2015_2024_pct"]] for r in last],
                       "source": "KOSIS 지역소득(시도별 경제활동별 지역내총생산)·경제활동인구조사, scripts/structure_index.py 계산", "latest": y,
                       "note": "산업집중도는 부문 비중(%)의 제곱합, 변화속도는 부문 비중 변화 절댓값 합의 절반. 정의는 scripts/structure_index.py"})
        rc.write("kosis", "hhi17", rc.bar_chart, f"17개 시도 산업집중도(HHI, {y}년 잠정)", [(r["region"], int(r["hhi"])) for r in last], index=index, unit="", note="24개 부문, 값 큰 순")
    lq = list(csv.DictReader(open(K / "structure_lq.csv", encoding="utf-8"))) if (K / "structure_lq.csv").exists() else []
    if lq:
        y1 = max(r["year"] for r in lq); y0 = "2015"
        d1 = {r["sector"]: r for r in lq if r["region"] == "대구" and r["year"] == y1}
        d0 = {r["sector"]: r for r in lq if r["region"] == "대구" and r["year"] == y0}
        gva = {r["C2_NM"]: num(r["DT"]) for r in rows("grdp-sido-industry-all") if r["C1_NM"] == "대구광역시" and r["ITM_NM"] == "명목" and r["PRD_DE"] == y1}
        import structure_index as sx  # noqa: E402
        long = {v: k for k, v in sx.SHORT.items()}
        order = sorted(d1.values(), key=lambda r: -float(r["lq"] or 0))
        tables.append({"id": "daegu_sectors", "title": f"대구 부문별 총부가가치·비중·입지계수 ({y1}년 잠정)", "unit": "",
                       "columns": ["부문", f"총부가가치 {y1}(억원)", f"비중 {y1}(%)", f"비중 {y0}(%)", f"입지계수 {y1}", f"입지계수 {y0}", f"전국 비중 {y1}(%)"],
                       "rows": [[r["sector"], round((gva.get(long.get(r["sector"], r["sector"])) or 0) / 100), r["share_pct"], d0.get(r["sector"], {}).get("share_pct", ""), r["lq"], d0.get(r["sector"], {}).get("lq", ""), r["national_share_pct"]] for r in order],
                       "source": src("grdp-sido-industry-all") + ", 입지계수는 이 사이트 계산", "latest": y1, "note": "명목 기준. 입지계수 = 대구 비중 ÷ 전국 비중"})
        rc.write("kosis", "lq-daegu", rc.bar_chart, f"대구 부문별 입지계수({y1}년 잠정, 전국=1)", [(r["sector"], round(float(r["lq"]), 2)) for r in order], index=index, unit="", note="부가가치 기준, 값 큰 순")
        HIGH = ["전기·전자·정밀기기", "정보통신업", "금융 및 보험업"]
        years = sorted({r["year"] for r in lq if r["region"] == "대구"})
        dg = [round(sum(float(r["share_pct"]) for r in lq if r["region"] == "대구" and r["year"] == yy and r["sector"] in HIGH), 1) for yy in years]
        na = [round(sum(float(r["national_share_pct"]) for r in lq if r["region"] == "대구" and r["year"] == yy and r["sector"] in HIGH), 1) for yy in years]
        rc.write("kosis", "high-share", rc.line_chart, "고부가 3부문(전기·전자·정밀기기, 정보통신, 금융보험) 부가가치 비중", years, [("대구", dg), ("전국", na)], index=index, unit="%", note="명목 총부가가치 기준")

    # 2) 중소기업기본통계 — 대구 산업중분류 × 기업규모 (기업수·종사자수)
    a, b = rows("sme-stats-sido"), rows("sme-workers-sido")
    if a and b:
        y = max(r["PRD_DE"] for r in a)
        cnt = {(r["C1_NM"], r["C3_NM"]): num(r["DT"]) for r in a if r["C2_NM"] == "대구" and r["PRD_DE"] == y}
        wk = {(r["C1_NM"], r["C3_NM"]): num(r["DT"]) for r in b if r["C2_NM"] == "대구" and r["PRD_DE"] == y}
        secs = sorted({k[0] for k in cnt}, key=lambda s: (s != "전산업", s))
        tables.append({"id": "sme_daegu", "title": f"대구 산업중분류별 기업 수·종사자 수 ({y}년, 중소기업기본통계)", "unit": "",
                       "columns": ["산업중분류", "전체 기업(개)", "중소기업(개)", "소상공인(개)", "전체 종사자(명)", "중소기업 종사자(명)"],
                       "rows": [[s, cnt.get((s, "전체기업")), cnt.get((s, "중소기업")), cnt.get((s, "소상공인")), wk.get((s, "전체기업")), wk.get((s, "중소기업"))] for s in secs],
                       "source": src("sme-stats-sido") + "; " + src("sme-workers-sido"), "latest": y, "note": "영리법인·개인사업자 포함 행정통계. 값 없음은 빈칸"})

    # 3) 지역별고용조사 — 대구 구·군 × 산업 취업자
    e = [r for r in rows("regional-employment-sigungu") if r["C1_NM"].startswith("대구") and r["ITM_NM"].startswith("취업자")]
    if e:
        p = max(r["PRD_DE"] for r in e)
        inds = [i for i in dict.fromkeys(r["C2_NM"].strip() for r in e) if i]
        inds = ["계"] + [i for i in inds if i != "계"]
        gus = sorted({r["C1_NM"].replace("대구 ", "") for r in e})
        v = {(r["C1_NM"].replace("대구 ", ""), r["C2_NM"].strip()): num(r["DT"]) for r in e if r["PRD_DE"] == p}
        tables.append({"id": "employment_gu", "title": f"대구 구·군별·산업별 취업자 ({p[:4]}년 {'상' if p.endswith('01') else '하'}반기, 천명)", "unit": "천명",
                       "columns": ["구·군"] + inds, "rows": [[g] + [v.get((g, i)) for i in inds] for g in gus],
                       "source": src("regional-employment-sigungu"), "latest": p, "note": "지역별고용조사(반기). 산업은 대분류 묶음"})

    # 4) 경제활동인구 대구 월간, 광공업생산지수, 인구이동
    lf = [r for r in rows("labor-force-sido") if r["C1_NM"] == "대구광역시"]
    if lf:
        months = sorted({r["PRD_DE"] for r in lf})[-24:]
        get = lambda item: [next((num(r["DT"]) for r in lf if r["PRD_DE"] == m and r["ITM_NM"] == item), None) for m in months]
        rc.write("kosis", "employed", rc.line_chart, "대구 취업자(월간)", [ym(m) for m in months], [("취업자", get("취업자"))], index=index, unit="천명", note=short("labor-force-sido"))
        rc.write("kosis", "rates", rc.line_chart, "대구 고용률·실업률(월간)", [ym(m) for m in months], [("고용률", get("고용률")), ("실업률", get("실업률"))], index=index, unit="%", note=short("labor-force-sido"))
    mp = [r for r in rows("mfg-production-index-sido") if r["C1_NM"] == "대구광역시"]
    if mp:
        months = sorted({r["PRD_DE"] for r in mp})[-36:]
        rc.write("kosis", "mfg-index", rc.line_chart, "대구 광공업생산지수(원지수, 2020=100)", [ym(m) for m in months], [("총지수", [next((num(r["DT"]) for r in mp if r["PRD_DE"] == m), None) for m in months])], index=index, unit="", note=short("mfg-production-index-sido"))
    mg = [r for r in rows("migration-sido") if r["C1_NM"] == "대구광역시"]
    if mg:
        months = sorted({r["PRD_DE"] for r in mg})[-24:]
        get = lambda item: [next((num(r["DT"]) for r in mg if r["PRD_DE"] == m and r["ITM_NM"] == item), None) for m in months]
        rc.write("kosis", "migration", rc.line_chart, "대구 인구이동(월간)", [ym(m) for m in months], [("총전입", get("총전입")), ("총전출", get("총전출")), ("순이동", get("순이동"))], index=index, unit="명", note=short("migration-sido"))

    # 5) 전국사업체조사 — 대구 산업별 사업체·종사자(자료가 있을 때만)
    bc = [r for r in rows("biz-census-sido-industry-all") if r["C1_NM"] in ("대구", "대구광역시")]
    if bc:
        y = max(r["PRD_DE"] for r in bc)
        kinds = sorted({r["C3_NM"] for r in bc})
        tot = next((k for k in kinds if "전체" in k or k in ("계", "")), kinds[0])
        v = defaultdict(dict)
        for r in bc:
            if r["PRD_DE"] == y and r["C3_NM"] == tot:
                v[r["C2_NM"]][r["ITM_NM"]] = num(r["DT"])
        secs = [s for s in v if re.match(r"^[A-Z]|^전산업|^전체", s) or len(s) < 40][:120]
        tables.append({"id": "census_daegu", "title": f"대구 산업별 사업체 수·종사자 수 ({y}년, 전국사업체조사)", "unit": "",
                       "columns": ["산업", "사업체 수(개)", "종사자 수(명)"], "rows": [[s, v[s].get("사업체수"), v[s].get("종사자수")] for s in secs],
                       "source": src("biz-census-sido-industry-all"), "latest": y, "note": f"사업체 구분 '{tot}' 기준"})

    (OUT / "index.json").write_text(json.dumps({"tables": tables, "charts": index.get("kosis", {}), "generated": __import__("datetime").date.today().isoformat()}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"표 {len(tables)}개, 그래프 {len(index.get('kosis', {}))}개 → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
