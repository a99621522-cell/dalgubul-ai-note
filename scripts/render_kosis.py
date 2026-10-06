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


def num(v: str) -> float | int | None:
    try:
        f = float(v.replace(",", ""))
    except (ValueError, AttributeError):
        return None
    return int(f) if f.is_integer() and "." not in v else f


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

    # 5) 전국사업체조사 — 대구 산업 중분류별 사업체·종사자 + 종사자 기준 입지계수(자료·메타가 있을 때만)
    bc = [r for r in rows("biz-census-sido-industry-all") if r["C1_NM"] in ("대구", "대구광역시") and r["C3_NM"] in ("계", "")]
    mp = K / "biz-census-sido-industry-all.meta.json"
    if bc and mp.exists():
        codes = {}
        for it in json.loads(mp.read_text(encoding="utf-8")):
            if str(it.get("OBJ_ID_SN")) == "2" and (it["ITM_NM"] not in codes or len(it["ITM_ID"]) < len(codes[it["ITM_NM"]])):
                codes[it["ITM_NM"]] = it["ITM_ID"]
        y = max(r["PRD_DE"] for r in bc)
        v = defaultdict(dict)
        for r in bc:
            if r["PRD_DE"] == y and len(codes.get(r["C2_NM"], "")) in (1, 3):
                v[r["C2_NM"]][r["ITM_NM"]] = num(r["DT"])
        elq = {r["sector"]: r for r in (csv.DictReader(open(K / "structure_lq_employment.csv", encoding="utf-8")) if (K / "structure_lq_employment.csv").exists() else []) if r["region"] == "대구" and r["year"] == y}
        secs = sorted(v, key=lambda s: codes.get(s, ""))
        tables.append({"id": "census_daegu", "title": f"대구 산업 대·중분류별 사업체 수·종사자 수 ({y}년, 전국사업체조사)", "unit": "",
                       "columns": ["코드", "산업", "사업체 수(개)", "종사자 수(명)", "종사자 비중(%)", "전국 종사자 비중(%)", "입지계수(종사자 기준)"],
                       "rows": [[codes.get(s, ""), s, v[s].get("사업체수"), v[s].get("종사자수"), elq.get(f"{codes.get(s, '')} {s}".strip(), {}).get("share_pct", ""), elq.get(f"{codes.get(s, '')} {s}".strip(), {}).get("national_share_pct", ""), elq.get(f"{codes.get(s, '')} {s}".strip(), {}).get("lq", "")] for s in secs],
                       "source": src("biz-census-sido-industry-all") + ", 입지계수는 이 사이트 계산(중분류 종사자 기준)", "latest": y, "note": "사업체 구분 '계'. 대분류 행은 입지계수 없음(중분류만 계산)"})
        top = sorted([r for r in elq.values() if int(r["workers"]) >= 1000], key=lambda r: -float(r["lq"]))[:15]
        if top:
            rc.write("kosis", "lq-employment", rc.bar_chart, f"대구 산업 중분류 종사자 기준 입지계수 상위({y}년, 종사자 1,000명 이상)", [(r["sector"][3:], float(r["lq"])) for r in top], index=index, unit="", note="전국사업체조사 종사자 기준, 값 큰 순")

    # 6) 대구 연간 주요 지표 — 인구·고용·GRDP·수출(표마다 받은 연도만, 없는 칸은 빈칸)
    SIDO_END = ("광역시", "특별시", "특별자치시", "특별자치도", "도")
    pop, gu_pop = {}, defaultdict(dict)
    cur = None
    for r in rows("population-sido"):
        if r["ITM_NM"] != "총인구수":
            continue
        n = r["C1_NM"]
        if n.endswith(SIDO_END) and not n.endswith(("구", "군")):
            cur = n
        if cur == "대구광역시":
            if n == "대구광역시":
                pop[r["PRD_DE"]] = num(r["DT"])
            else:
                gu_pop[n][r["PRD_DE"]] = num(r["DT"])
    lfa = [r for r in rows("labor-force-sido-annual-all") if r["C1_NM"] == "대구광역시"]
    lfv = {(r["PRD_DE"], r["ITM_NM"]): num(r["DT"]) for r in lfa}
    gd = {(r["PRD_DE"], r["ITM_NM"]): num(r["DT"]) for r in rows("grdp-sido-industry") if r["C2_NM"] == "지역내총생산(시장가격)"}
    ex = {(r["PRD_DE"], r["ITM_NM"]): num(r["DT"]) for r in rows("export-region") if r["C1_NM"] == "대구" and r["C2_NM"] == "활동기업"}
    yrs = sorted({y for y in pop} | {y for y, _ in lfv} | {y for y, _ in gd} | {y for y, _ in ex})
    yrs = [y for y in yrs if y >= "2016"]
    if yrs:
        def growth(y):
            a, b = gd.get((y, "실질")), gd.get((str(int(y) - 1), "실질"))
            return round((a / b - 1) * 100, 1) + 0.0 if a and b else None
        tables.append({"id": "daegu_annual", "title": f"대구 연간 주요 지표 ({yrs[0]}~{yrs[-1]}년)", "unit": "",
                       "columns": ["연도", "주민등록인구(명)", "취업자(천명)", "고용률(%)", "실업률(%)", "지역내총생산 명목(억원)", "실질 성장률(%)", "수출입 활동기업(개)", "수출입 교역액(백만달러)"],
                       "rows": [[y, pop.get(y), lfv.get((y, "취업자")), lfv.get((y, "고용률")), lfv.get((y, "실업률")),
                                 round(gd[(y, "명목")] / 100) if gd.get((y, "명목")) else None, growth(y), ex.get((y, "업체수")), ex.get((y, "교역액"))] for y in reversed(yrs)],
                       "source": "; ".join(src(k) for k in ("population-sido", "labor-force-sido-annual-all", "grdp-sido-industry", "export-region")),
                       "latest": yrs[-1], "note": "실질 성장률은 실질 지역내총생산의 전년 대비 증감(이 사이트 계산). 수출입은 관세청 기업무역활동통계 활동기업 기준. 자료 없는 칸은 —"})
        py = [y for y in yrs if pop.get(y)]
        if py:
            rc.write("kosis", "population", rc.line_chart, "대구 주민등록인구(연말)", py, [("총인구", [pop[y] for y in py])], index=index, unit="명", note=short("population-sido"))
    if gu_pop:
        # 운영자 지시 2026-10-06 '2014·2025년이 아니라 현재로': 최신 연말 + 10년 전·5년 전·전년 + (월간 표를 받았으면) 최근 월. 2014 는 수집 시작 연도였을 뿐이라 뺐다
        gys = sorted({y for d in gu_pop.values() for y in d})
        y1 = gys[-1]; pick = [y for y in (str(int(y1) - 10), str(int(y1) - 5), str(int(y1) - 1)) if y in gys]
        gu_m, mlatest, cur_m = defaultdict(dict), "", None
        for r in rows("population-sigungu-monthly"):
            if r["ITM_NM"] != "총인구수":
                continue
            n = r["C1_NM"]
            if n.endswith(SIDO_END) and not n.endswith(("구", "군")):
                cur_m = n
            elif cur_m == "대구광역시" and n in gu_pop:
                gu_m[n][r["PRD_DE"]] = num(r["DT"])
        if gu_m:
            mlatest = max(m for d in gu_m.values() for m in d)
        mlabel = f"{mlatest[:4]}-{mlatest[4:6]}" if mlatest else ""
        cols = ["구·군"] + [f"{y}년(명)" for y in pick] + [f"{y1}년 연말(명)"] + ([f"{mlabel}(명)"] if mlatest else []) + [f"{pick[0]}→{y1} 증감(명)" if pick else "증감(명)"]
        def _row(g, d):
            base = d.get(pick[0]) if pick else None
            out = [g] + [d.get(y) for y in pick] + [d.get(y1)] + ([gu_m.get(g, {}).get(mlatest)] if mlatest else [])
            out.append((d[y1] - base) if d.get(y1) is not None and base is not None else None)
            return out
        tables.append({"id": "gu_population", "title": f"대구 구·군별 주민등록인구 (연말 {y1}년" + (f", 최근 {mlabel}" if mlatest else "") + ")", "unit": "명",
                       "columns": cols, "rows": [_row(g, d) for g, d in gu_pop.items()],
                       "source": src("population-sido") + (f"; {src('population-sigungu-monthly')}" if mlatest else ""), "latest": mlabel or y1,
                       "note": "연도 칸은 그해 12월 말 주민등록인구, " + (f"최근 월 칸은 {mlabel} 말. " if mlatest else "최근 월 값은 월간 표를 받은 뒤 붙는다. ") + "군위군은 2023년 7월 대구 편입(그 전 값은 경북 소속 때 값이 없을 수 있음)"})

    # 7) 대구 GRDP 경제활동별 — 실질 성장률·실질 기여도(최근 연도)
    g = rows("grdp-sido-industry")
    if g:
        y = max(r["PRD_DE"] for r in g); yp = str(int(y) - 1)
        val = {(r["PRD_DE"], r["ITM_NM"], r["C2_NM"]): num(r["DT"]) for r in g}
        secs = list(dict.fromkeys(r["C2_NM"] for r in g))
        def gr(sec):
            a, b = val.get((y, "실질", sec)), val.get((yp, "실질", sec))
            return round((a / b - 1) * 100, 1) + 0.0 if a and b else None
        tables.append({"id": "grdp_daegu", "title": f"대구 경제활동별 지역내총생산 ({y}년 잠정)", "unit": "",
                       "columns": ["경제활동", f"명목 {y}(억원)", f"실질 {y}(억원)", "실질 성장률(%)", "실질 기여도(%p)"],
                       "rows": [[sec, round(val[(y, "명목", sec)] / 100) if val.get((y, "명목", sec)) else None,
                                 round(val[(y, "실질", sec)] / 100) if val.get((y, "실질", sec)) else None, gr(sec), val.get((y, "실질기여도", sec))] for sec in secs],
                       "source": src("grdp-sido-industry"), "latest": y, "note": "실질은 2020년 기준 연쇄가격. 성장률은 실질의 전년 대비 증감(이 사이트 계산), 기여도는 KOSIS 값. 군위군은 2023년 7월 대구 편입 — 농림어업·광업처럼 규모가 작은 부문은 증감이 크게 나올 수 있음"})

    # 8) 관세청 기업무역활동통계 — 17개 시도 수출입 활동기업(최근 연도) + 대구 추이
    er, ei = rows("export-region"), rows("export-region-index")
    if er:
        y = max(r["PRD_DE"] for r in er)
        v = {(r["C1_NM"], r["C2_NM"], r["ITM_NM"]): num(r["DT"]) for r in er if r["PRD_DE"] == y}
        vi = {(r["C1_NM"], r["ITM_NM"]): num(r["DT"]) for r in ei if r["PRD_DE"] == y}
        regs = sorted({k[0] for k in v}, key=lambda s: -(v.get((s, "활동기업", "교역액")) or 0))
        tables.append({"id": "export17", "title": f"17개 시도 수출입 활동기업·교역액 ({y}년, 관세청 기업무역활동통계)", "unit": "",
                       "columns": ["시도", "활동기업(개)", "교역액(백만달러)", "진입기업(개)", "업체수 진입률(%)", "퇴출기업(개)", "업체수 퇴출률(%)", "기여율(%)", "기여도(%p)"],
                       "rows": [[s, v.get((s, "활동기업", "업체수")), v.get((s, "활동기업", "교역액")), v.get((s, "진입기업", "업체수")), v.get((s, "진입기업", "업체수 진입률")),
                                 v.get((s, "퇴출기업", "업체수")), v.get((s, "퇴출기업", "업체수 퇴출률")), vi.get((s, "기여율")), vi.get((s, "기여도"))] for s in regs],
                       "source": src("export-region") + "; " + src("export-region-index"), "latest": y, "note": "정렬은 교역액 크기순일 뿐. 기여율·기여도는 KOSIS 지역별 수출지표 값"})
        dy = sorted({r["PRD_DE"] for r in er if r["C1_NM"] == "대구"})
        dv = {(r["PRD_DE"], r["ITM_NM"]): num(r["DT"]) for r in er if r["C1_NM"] == "대구" and r["C2_NM"] == "활동기업"}
        rc.write("kosis", "export-daegu", rc.line_chart, "대구 수출입 활동기업 교역액(연간)", dy, [("교역액", [dv.get((yy, "교역액")) for yy in dy])], index=index, unit="백만달러", note=short("export-region"))

    # 9) 소매판매액지수 — 대구 업태별(불변, 2020=100)
    rs = [r for r in rows("retail-sales-index-sido") if r["C1_NM"] == "대구광역시"]
    if rs:
        ys = sorted({r["PRD_DE"] for r in rs})[-6:]
        kinds = list(dict.fromkeys(r["C2_NM"] for r in rs))
        kinds = ["총지수"] + [k for k in kinds if k != "총지수"]
        v = {(r["PRD_DE"], r["C2_NM"]): num(r["DT"]) for r in rs}
        tables.append({"id": "retail_daegu", "title": f"대구 업태별 소매판매액지수 ({ys[0]}~{ys[-1]}년, 불변지수 2020=100)", "unit": "",
                       "columns": ["업태"] + [f"{yy}년" for yy in ys], "rows": [[k] + [v.get((yy, k)) for yy in ys] for k in kinds],
                       "source": src("retail-sales-index-sido"), "latest": ys[-1], "note": "값 없음은 —(해당 업태가 대구에 없거나 비공개)"})

    # 10) 국내인구이동 — 대구 연령별 순이동(최근 연도)
    ma = [r for r in rows("migration-age-sido") if r["C1_NM"] == "대구광역시"]
    if ma:
        y = max(r["PRD_DE"] for r in ma)
        v = {(r["C2_NM"], r["C3_NM"]): num(r["DT"]) for r in ma if r["PRD_DE"] == y}
        ages = sorted({k[1] for k in v if k[1] and k[1][0].isdigit()}, key=lambda a: int(re.match(r"\d+", a).group()))
        rest = [a for a in dict.fromkeys(k[1] for k in v) if a not in ages]
        order = rest + ages
        tables.append({"id": "migration_age", "title": f"대구 연령별 순이동 ({y}년)", "unit": "명",
                       "columns": ["연령", "계(명)", "남자(명)", "여자(명)"], "rows": [[a, v.get(("계", a)), v.get(("남자", a)), v.get(("여자", a))] for a in order],
                       "source": src("migration-age-sido"), "latest": y, "note": "순이동 = 전입 − 전출. 음수는 전출이 많음"})

    # 11) 지역별고용조사 — 대구 제조업 중분류 취업자와 전국 대비 비중(최근 반기)
    ei2 = [r for r in rows("employed-industry-sido") if r["ITM_NM"].startswith("취업자")]
    if ei2:
        p = max(r["PRD_DE"] for r in ei2)
        dv = {r["C2_NM"].strip(): num(r["DT"]) for r in ei2 if r["PRD_DE"] == p and r["C1_NM"] == "대구광역시"}
        nv = {r["C2_NM"].strip(): num(r["DT"]) for r in ei2 if r["PRD_DE"] == p and r["C1_NM"] == "계"}
        mfg = [k for k in dict.fromkeys(r["C2_NM"].strip() for r in ei2) if ("제조업" in k and "(" not in k) or k == "산업용 기계 및 장비 수리업"]
        if mfg:
            tables.append({"id": "employed_mfg", "title": f"대구 제조업 중분류별 취업자 ({p[:4]}년 {'상' if p.endswith('01') else '하'}반기, 지역별고용조사)", "unit": "천명",
                           "columns": ["산업 중분류", "대구 취업자(천명)", "전국 취업자(천명)", "대구 비중(%)"],
                           "rows": [[k, dv.get(k), nv.get(k), round(dv[k] / nv[k] * 100, 1) if dv.get(k) and nv.get(k) else None] for k in mfg],
                           "source": src("employed-industry-sido"), "latest": p, "note": "표본조사 추정값(천명). '-' 는 —. 비중은 대구 ÷ 전국(이 사이트 계산)"})

    # 12) 전국사업체조사 — 대구 제조업 중분류 사업체·종사자 연도별(2020~)
    if bc and mp.exists():
        ys = sorted({r["PRD_DE"] for r in bc})
        v = {(r["PRD_DE"], r["C2_NM"], r["ITM_NM"]): num(r["DT"]) for r in bc}
        mf = sorted([s for s, c in codes.items() if len(c) == 3 and c[0] == "C"], key=lambda s: codes[s])
        mf = [s for s in mf if any(v.get((yy, s, "사업체수")) for yy in ys)]
        if mf:
            tables.append({"id": "census_mfg_years", "title": f"대구 제조업 중분류별 사업체·종사자 ({ys[0]}~{ys[-1]}년, 전국사업체조사)", "unit": "",
                           "columns": ["코드", "산업"] + [f"사업체 {yy}" for yy in ys] + [f"종사자 {yy}" for yy in ys],
                           "rows": [[codes[s], s] + [v.get((yy, s, "사업체수")) for yy in ys] + [v.get((yy, s, "종사자수")) for yy in ys] for s in mf],
                           "source": src("biz-census-sido-industry-all"), "latest": ys[-1], "note": "사업체 구분 '계'. 사업체 수(개)·종사자 수(명)"})

    # 13) 광업·제조업조사(10명 이상) — 대구 제조업 중분류별 사업체·출하액·생산액·부가가치
    mm = [r for r in rows("mining-mfg-survey-sido") if r["C1_NM"].startswith("대구")]
    if mm:
        ys = sorted({r["PRD_DE"] for r in mm})
        y1, y0 = ys[-1], ys[0]
        v = {(r["PRD_DE"], r["C2_NM"], r["ITM_NM"]): num(r["DT"]) for r in mm}
        secs = list(dict.fromkeys(r["C2_NM"] for r in mm))
        eok = lambda x: round(x / 100) if x is not None else None   # 백만원 → 억원
        def chg(sec, item):
            a, b = v.get((y1, sec, item)), v.get((y0, sec, item))
            return round((a / b - 1) * 100, 1) + 0.0 if a and b else None
        tables.append({"id": "mining_mfg_daegu", "title": f"대구 제조업 중분류별 출하액·부가가치 ({y1}년, 광업·제조업조사 10명 이상)", "unit": "",
                       "columns": ["산업", f"사업체 {y1}(개)", f"출하액 {y1}(억원)", f"생산액 {y1}(억원)", f"부가가치 {y1}(억원)", f"부가가치 {y0}(억원)", f"부가가치 증감 {y0}→{y1}(%)"],
                       "rows": [[sec, v.get((y1, sec, "사업체수")), eok(v.get((y1, sec, "출하액 계"))), eok(v.get((y1, sec, "생산액"))), eok(v.get((y1, sec, "부가가치"))),
                                 eok(v.get((y0, sec, "부가가치"))), chg(sec, "부가가치")] for sec in secs],
                       "source": src("mining-mfg-survey-sido"), "latest": y1, "note": "종사자 10명 이상 사업체. 원자료 백만원을 억원으로 반올림. 증감은 명목값 비교(이 사이트 계산). — 는 KOSIS 원자료 값 없음(사업체가 적어 비공개 처리된 칸 포함)"})
        mf = [sec for sec in secs if ("제조업" in sec and "(" not in sec and sec != "광업 및 제조업") or sec == "산업용 기계 및 장비 수리업"]   # 합계 행 제외
        top = sorted([(sec, eok(v.get((y1, sec, "부가가치")))) for sec in mf if v.get((y1, sec, "부가가치"))], key=lambda x: -x[1])[:12]
        if top:
            rc.write("kosis", "mfg-value-added", rc.bar_chart, f"대구 제조업 중분류별 부가가치({y1}년, 10명 이상, 억원)", top, index=index, unit="억원", note="광업·제조업조사, 값 큰 순 12개")
        tot = "제조업(10~34)"
        if any(v.get((yy, tot, "부가가치")) for yy in ys):
            rc.write("kosis", "mfg-total-years", rc.line_chart, "대구 제조업 출하액·부가가치(10명 이상)", ys,
                     [("출하액", [eok(v.get((yy, tot, "출하액 계"))) for yy in ys]), ("부가가치", [eok(v.get((yy, tot, "부가가치"))) for yy in ys])], index=index, unit="억원", note=short("mining-mfg-survey-sido"))

    # 14) 광업제조업동향조사 — 대구 업종별 생산·출하·재고지수(원지수, 2020=100), 최근 달과 전년 같은 달
    pi = [r for r in rows("mfg-production-index-industry") if r["C1_NM"].startswith("대구")]
    if pi:
        p1 = max(r["PRD_DE"] for r in pi); p0 = str(int(p1[:4]) - 1) + p1[4:]
        v = {(r["PRD_DE"], r["C2_NM"], r["ITM_NM"]): num(r["DT"]) for r in pi}
        inds = list(dict.fromkeys(r["C2_NM"] for r in pi))
        P, S, I = "생산지수(원지수)", "생산자제품 출하지수(원지수)", "생산자제품 재고지수(원지수)"
        def yoy(ind, item):
            a, b = v.get((p1, ind, item)), v.get((p0, ind, item))
            return round((a / b - 1) * 100, 1) + 0.0 if a and b else None
        tables.append({"id": "mfg_index_industry", "title": f"대구 업종별 광공업생산·출하·재고지수 ({ym(p1)}, 원지수 2020=100)", "unit": "",
                       "columns": ["업종", f"생산 {ym(p1)}", f"생산 {ym(p0)}", "생산 전년동월비(%)", f"출하 {ym(p1)}", "출하 전년동월비(%)", f"재고 {ym(p1)}", "재고 전년동월비(%)"],
                       "rows": [[ind, v.get((p1, ind, P)), v.get((p0, ind, P)), yoy(ind, P), v.get((p1, ind, S)), yoy(ind, S), v.get((p1, ind, I)), yoy(ind, I)] for ind in inds],
                       "source": src("mfg-production-index-industry"), "latest": p1, "note": "원지수 기준. 전년동월비는 같은 달 원지수 비교(이 사이트 계산). 월간 잠정치는 다음 달 공표 때 바뀔 수 있음"})
        months = sorted({r["PRD_DE"] for r in pi})[-24:]
        pick = ["기타 기계 및 장비 제조업", "자동차 및 트레일러 제조업", "금속 가공제품 제조업; 기계 및 가구 제외", "섬유제품 제조업; 의복 제외"]
        ser = [(n.split(" 제조업")[0].split(";")[0], [v.get((m, n, P)) for m in months]) for n in pick if any(v.get((m, n, P)) for m in months)]
        if ser:
            rc.write("kosis", "mfg-index-industry", rc.line_chart, "대구 주요 업종 생산지수(원지수, 2020=100)", [ym(m) for m in months], ser, index=index, unit="", note=short("mfg-production-index-industry"))

    (OUT / "index.json").write_text(json.dumps({"tables": tables, "charts": index.get("kosis", {}), "generated": __import__("datetime").date.today().isoformat()}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"표 {len(tables)}개, 그래프 {len(index.get('kosis', {}))}개 → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
