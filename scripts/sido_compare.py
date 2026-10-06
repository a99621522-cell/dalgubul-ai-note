#!/usr/bin/env python3
"""17개 시도 비교 표·그래프 (render_kosis.py 가 부른다) — 추세·비교·효과 보강 2단계(2026-10-06).

data/kosis 의 전 지역 표(area: [])에서 시도별 최근 값과 5년 전 값을 나란히 놓는다. 값은 KOSIS 그대로이고 나눗셈(비중·증감률)만 한다.
행 순서는 전국 → 행정 순서(서울·부산·대구·인천·광주·대전·울산·세종·경기·강원·충북·충남·전북·전남·경북·경남·제주)이지 순위가 아니다.
자료가 없는 표·열은 만들지 않는다. 대구만 받은 표(지역 1개)는 건너뛴다 — kosis_tables.yml 에서 area: [] 로 바꿔 받으면 다음 render 때 붙는다.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
K = ROOT / "data" / "kosis"

SIDO = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
NORM = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주", "대전광역시": "대전",
        "울산광역시": "울산", "세종특별자치시": "세종", "세종시": "세종", "경기도": "경기", "강원도": "강원", "강원특별자치도": "강원",
        "충청북도": "충북", "충청남도": "충남", "전라북도": "전북", "전북특별자치도": "전북", "전라남도": "전남", "경상북도": "경북",
        "경상남도": "경남", "제주특별자치도": "제주", "전국": "전국", "계": "전국", "전남광주통합특별시": "전남·광주(통합)"}
NOTE_ORDER = "행 순서는 전국·행정 순서(순위 아님). 대구 행은 그래프에서 진하게"


def rows(key: str) -> list[dict]:
    p = K / f"{key}.csv"
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


def num(v) -> float | int | None:
    try:
        t = str(v).replace(",", "")
        f = float(t)
    except (ValueError, TypeError):
        return None
    return int(f) if f.is_integer() and "." not in t else f


def norm(name: str) -> str | None:
    """시도 이름 → 짧은 이름. 시군구 등 시도가 아니면 None."""
    n = name.strip()
    if n in NORM:
        return NORM[n]
    return n if n in SIDO else None


def regions_in(rs: list[dict]) -> set[str]:
    return {x for x in (norm(r.get("C1_NM", "")) for r in rs) if x}


def ordered(present: set[str]) -> list[str]:
    extra = sorted(x for x in present if x not in SIDO and x != "전국")
    return (["전국"] if "전국" in present else []) + [s for s in SIDO if s in present] + extra


def table(rs: list[dict], year_of=lambda r: r["PRD_DE"], **match) -> dict[tuple[str, str], float | int]:
    """(시점, 시도) → 값. match 는 열 이름=값(ITM_NM='…', C2_NM='…')."""
    out: dict[tuple[str, str], float | int] = {}
    for r in rs:
        if any(r.get(k, "") != v for k, v in match.items()):
            continue
        reg = norm(r.get("C1_NM", ""))
        v = num(r.get("DT"))
        if reg and v is not None:
            out[(year_of(r), reg)] = v
    return out


def pct(a: float | None, b: float | None, digits: int = 1) -> float | None:
    """(a/b − 1)×100"""
    return round((a / b - 1) * 100, digits) if a is not None and b and b != 0 else None


def share(a: float | None, b: float | None, digits: int = 1) -> float | None:
    return round(a / b * 100, digits) if a is not None and b and b != 0 else None


def r1(v: float | None, digits: int = 1) -> float | None:
    return None if v is None else round(v, digits)


def years_of(d: dict[tuple[str, str], float]) -> list[str]:
    return sorted({y for y, _ in d})


def build(tables: list[dict], index: dict, rc, src) -> None:
    """tables 에 cmp_* 표를, index 에 cmp-* 그래프를 더한다. rc=render_charts, src=key→출처 문자열."""
    def write_bar(name: str, title: str, items: list[tuple[str, float | None]], unit: str, note: str) -> None:
        if sum(1 for _, v in items if v is not None) >= 2:
            rc.write("kosis", name, rc.bar_chart, title, items, index=index, unit=unit, note=note, highlight="대구")

    # ---- A. 경제 규모·성장·구조 (지역소득 + structure_index) ----
    g = rows("grdp-sido-industry-all")
    si = list(csv.DictReader(open(K / "structure_index.csv", encoding="utf-8"))) if (K / "structure_index.csv").exists() else []
    if g and len(regions_in(g)) > 1:
        nom = table(g, ITM_NM="명목", C2_NM="지역내총생산(시장가격)")
        real = table(g, ITM_NM="실질", C2_NM="지역내총생산(시장가격)")
        mfg = table(g, ITM_NM="명목", C2_NM="제조업")
        gva = table(g, ITM_NM="명목", C2_NM="총부가가치(기초가격)")
        ys = years_of(nom)
        if ys:
            y = ys[-1]; y0 = str(int(y) - 1)
            sidx = {(r["region"], r["year"]): r for r in si}
            syears = sorted({r["year"] for r in si if r.get("high_share_pct")})
            sy = syears[-1] if syears else y
            cagr_col = next((c for c in (si[0].keys() if si else []) if c.startswith("grdp_cagr_")), "")
            cagr_label = cagr_col.replace("grdp_cagr_", "").replace("_pct", "").replace("_", "→") if cagr_col else ""
            present = {r for (_, r) in nom}
            trs = []
            growth_items, high_items = [], []
            for reg in ordered(present):
                s = sidx.get((reg, sy)) or {}
                cagr = num(s.get(cagr_col)) if cagr_col else None
                high = num(s.get("high_share_pct")); hhi = num(s.get("hhi"))
                gr = pct(real.get((y, reg)), real.get((y0, reg)))
                trs.append([reg, r1(nom.get((y, reg), 0) / 1_000_000, 1) if (y, reg) in nom else None, gr, r1(cagr),
                            share(mfg.get((y, reg)), gva.get((y, reg))), r1(high), None if hhi is None else int(hhi)])
                if reg != "전국":
                    growth_items.append((reg, r1(cagr))); high_items.append((reg, r1(high)))
            tables.append({"id": "cmp_grdp", "title": f"17개 시도 지역내총생산·성장률·산업구조 ({y}년 잠정)", "unit": "",
                           "columns": ["시도", f"지역내총생산 {y}(조원, 명목)", f"실질 성장률 {y}(%)", f"연평균 실질 성장률 {cagr_label}(%)",
                                       f"제조업 비중 {y}(%, 명목 총부가가치 대비)", f"고부가 3부문 비중 {sy}(%)", f"산업집중도 {sy}"],
                           "rows": trs, "source": src("grdp-sido-industry-all") + "; 연평균 성장률·고부가 비중·산업집중도는 이 사이트 계산(scripts/structure_index.py)", "latest": y,
                           "note": NOTE_ORDER + ". 실질 성장률 = 실질 지역내총생산 전년 대비. 고부가 3부문 = 전기·전자·정밀기기, 정보통신, 금융·보험(한국은행 자료 정의)"})
            write_bar("cmp-growth", f"17개 시도 연평균 실질 성장률({cagr_label}, %)", growth_items, "%", "지역소득, 이 사이트 계산 · 행정 순서")
            write_bar("cmp-highshare", f"17개 시도 고부가 3부문 비중({sy}년, 명목 총부가가치 대비 %)", high_items, "%", "지역소득, 이 사이트 계산 · 행정 순서")

    # ---- B. 고용 (경제활동인구조사 연간) ----
    lf = rows("labor-force-sido-annual-all")
    if lf and len(regions_in(lf)) > 1:
        emp = table(lf, ITM_NM="취업자"); er = table(lf, ITM_NM="고용률"); er64 = table(lf, ITM_NM="15-64세 고용률"); ur = table(lf, ITM_NM="실업률")
        ys = years_of(emp)
        if ys:
            y = ys[-1]; y5 = str(int(y) - 5) if str(int(y) - 5) in ys else ys[0]
            present = {r for (yy, r) in emp if yy == y}
            trs, items = [], []
            for reg in ordered(present):
                ch = pct(emp.get((y, reg)), emp.get((y5, reg)))
                trs.append([reg, emp.get((y, reg)), emp.get((y5, reg)), ch, er.get((y, reg)), er64.get((y, reg)), ur.get((y, reg))])
                if reg != "전국":
                    items.append((reg, ch))
            tables.append({"id": "cmp_labor", "title": f"17개 시도 취업자·고용률·실업률 ({y}년, 경제활동인구조사)", "unit": "",
                           "columns": ["시도", f"취업자 {y}(천명)", f"취업자 {y5}(천명)", f"취업자 증감률 {y5}→{y}(%)", f"고용률 {y}(%)", f"15~64세 고용률 {y}(%)", f"실업률 {y}(%)"],
                           "rows": trs, "source": src("labor-force-sido-annual-all"), "latest": y,
                           "note": NOTE_ORDER + ". 행정구역이 바뀐 시도는 KOSIS 표기 그대로(통합 전 값은 통합 전 시도 행)"})
            write_bar("cmp-employed-change", f"17개 시도 취업자 증감률({y5}→{y}, %)", items, "%", "경제활동인구조사 · 행정 순서")

    # ---- C. 사업체·종사자 (전국사업체조사) ----
    bc = rows("biz-census-sido-industry-all")
    if bc and len(regions_in(bc)) > 1:
        est = table(bc, ITM_NM="사업체수", C2_NM="전체 산업", C3_NM="계"); wk = table(bc, ITM_NM="종사자수", C2_NM="전체 산업", C3_NM="계")
        wk_mfg = table(bc, ITM_NM="종사자수", C2_NM="제조업(10~34)", C3_NM="계")
        ys = years_of(est)
        if ys:
            y = ys[-1]; y0 = ys[0]
            present = {r for (yy, r) in est if yy == y}
            trs = [[reg, est.get((y, reg)), wk.get((y, reg)), pct(wk.get((y, reg)), wk.get((y0, reg))) if y0 != y else None, share(wk_mfg.get((y, reg)), wk.get((y, reg)))]
                   for reg in ordered(present)]
            tables.append({"id": "cmp_census", "title": f"17개 시도 사업체·종사자 ({y}년, 전국사업체조사)", "unit": "",
                           "columns": ["시도", f"사업체 수 {y}(개)", f"종사자 수 {y}(명)", f"종사자 증감률 {y0}→{y}(%)", f"제조업 종사자 비중 {y}(%)"],
                           "rows": trs, "source": src("biz-census-sido-industry-all"), "latest": y, "note": NOTE_ORDER})

    # ---- D. 기업 신생·소멸 (기업생멸행정통계, area: [] 로 받은 뒤) ----
    bb = rows("biz-birth-death-sido")
    if bb and len(regions_in(bb)) > 1:
        act = table(bb, ITM_NM="활동", C2_NM="전체", C3_NM="계"); br = table(bb, ITM_NM="신생률", C2_NM="전체", C3_NM="계"); dr = table(bb, ITM_NM="소멸률", C2_NM="전체", C3_NM="계")
        ys = years_of(br)
        if ys:
            y = ys[-1]; yd = (years_of(dr) or [y])[-1]
            present = {r for (yy, r) in br if yy == y}
            trs, items = [], []
            for reg in ordered(present):
                trs.append([reg, act.get((y, reg)), br.get((y, reg)), dr.get((yd, reg))])
                if reg != "전국":
                    items.append((reg, br.get((y, reg))))
            tables.append({"id": "cmp_birth", "title": f"17개 시도 활동기업·신생률·소멸률 ({y}년, 기업생멸행정통계)", "unit": "",
                           "columns": ["시도", f"활동기업 {y}(개)", f"신생률 {y}(%)", f"소멸률 {yd}(%)"], "rows": trs, "source": src("biz-birth-death-sido"), "latest": y,
                           "note": NOTE_ORDER + ". 소멸률은 확정이 1년 늦어 한 해 전 값"})
            write_bar("cmp-birth-rate", f"17개 시도 기업 신생률({y}년, %)", items, "%", "기업생멸행정통계 · 행정 순서")

    # ---- E. 수출입 활동기업 (관세청 기업무역활동통계) ----
    ex = rows("export-region")
    if ex and len(regions_in(ex)) > 1:
        n = table(ex, ITM_NM="업체수", C2_NM="활동기업"); amt = table(ex, ITM_NM="교역액", C2_NM="활동기업")
        ys = years_of(n)
        if ys:
            y = ys[-1]; y5 = str(int(y) - 5) if str(int(y) - 5) in ys else ys[0]
            present = {r for (yy, r) in n if yy == y}
            trs = [[reg, n.get((y, reg)), n.get((y5, reg)), amt.get((y, reg)), amt.get((y5, reg)), pct(amt.get((y, reg)), amt.get((y5, reg)))] for reg in ordered(present)]
            tables.append({"id": "cmp_export", "title": f"17개 시도 수출입 활동기업 수·교역액 ({y}년, 기업무역활동통계)", "unit": "",
                           "columns": ["시도", f"활동기업 {y}(개)", f"활동기업 {y5}(개)", f"교역액 {y}(백만달러)", f"교역액 {y5}(백만달러)", f"교역액 증감률 {y5}→{y}(%)"],
                           "rows": trs, "source": src("export-region"), "latest": y, "note": NOTE_ORDER})

    # ---- F. 인구 (주민등록) ----
    po = rows("population-sido")
    if po:
        pop = table(po, ITM_NM="총인구수")
        ys = years_of(pop)
        if ys and len({r for (_, r) in pop}) > 1:
            y = ys[-1]; y5 = str(int(y) - 5) if str(int(y) - 5) in ys else ys[0]
            present = {r for (yy, r) in pop if yy == y}
            trs, items = [], []
            for reg in ordered(present):
                ch = pct(pop.get((y, reg)), pop.get((y5, reg)), 2)
                trs.append([reg, pop.get((y, reg)), pop.get((y5, reg)), ch])
                if reg != "전국":
                    items.append((reg, ch))
            tables.append({"id": "cmp_population", "title": f"17개 시도 주민등록인구 ({y}년, 연말)", "unit": "명",
                           "columns": ["시도", f"총인구 {y}(명)", f"총인구 {y5}(명)", f"증감률 {y5}→{y}(%)"], "rows": trs, "source": src("population-sido"), "latest": y, "note": NOTE_ORDER})
            write_bar("cmp-pop-change", f"17개 시도 주민등록인구 증감률({y5}→{y}, %)", items, "%", "주민등록인구 · 행정 순서")

    # ---- G. 소매판매액지수 ----
    rt = rows("retail-sales-index-sido")
    if rt and len(regions_in(rt)) > 1:
        idx = table(rt, ITM_NM="불변지수", C2_NM="총지수")
        ys = years_of(idx)
        if ys:
            y = ys[-1]; y5 = str(int(y) - 5) if str(int(y) - 5) in ys else ys[0]
            present = {r for (yy, r) in idx if yy == y}
            trs = [[reg, idx.get((y, reg)), idx.get((y5, reg)), pct(idx.get((y, reg)), idx.get((y5, reg)))] for reg in ordered(present)]
            tables.append({"id": "cmp_retail", "title": f"17개 시도 소매판매액지수 ({y}년, 불변지수 2020=100)", "unit": "",
                           "columns": ["시도", f"총지수 {y}", f"총지수 {y5}", f"변화율 {y5}→{y}(%)"], "rows": trs, "source": src("retail-sales-index-sido"), "latest": y, "note": NOTE_ORDER})

    # ---- H. 월간 지표 최근 달 (대구만 받은 표는 열이 빠진다) ----
    cols, series, srcs, latest = ["시도"], [], [], []
    mp = rows("mfg-production-index-sido")
    if mp and len(regions_in(mp)) > 1:
        d = table(mp, ITM_NM="생산지수(원지수)", C2_NM="총지수")
        ms = years_of(d)
        if ms:
            m = ms[-1]; m12 = str(int(m) - 100)
            cols.append(f"광공업생산지수 전년동월비 {m[:4]}-{m[4:]}(%)"); series.append({reg: pct(d.get((m, reg)), d.get((m12, reg))) for (mm, reg) in d if mm == m}); srcs.append(src("mfg-production-index-sido")); latest.append(m)
    lfm = rows("labor-force-sido")
    if lfm and len(regions_in(lfm)) > 1:
        for itm in ("고용률", "실업률"):
            d = table(lfm, ITM_NM=itm); ms = years_of(d)
            if ms:
                m = ms[-1]; cols.append(f"{itm} {m[:4]}-{m[4:]}(%)"); series.append({reg: v for (mm, reg), v in d.items() if mm == m}); latest.append(m)
        srcs.append(src("labor-force-sido"))
    sv = rows("service-index-sido")
    if sv and len(regions_in(sv)) > 1:
        d = table(sv, ITM_NM="불변지수", C2_NM="총지수"); ms = years_of(d)
        if ms:
            m = ms[-1]; m4 = str(int(m) - 100)
            cols.append(f"서비스업생산지수 전년동기비 {m[:4]} {int(m[4:])}분기(%)" if len(m) == 6 and m[4] == "0" and int(m[4:]) <= 4 else f"서비스업생산지수 전년동기비 {m}(%)")
            series.append({reg: pct(d.get((m, reg)), d.get((m4, reg))) for (mm, reg) in d if mm == m}); srcs.append(src("service-index-sido")); latest.append(m)
    se = rows("self-employed-sido")
    if se and len(regions_in(se)) > 1:
        tot = table(se, ITM_NM="취업자", C2_NM="계"); selfemp = table(se, ITM_NM="취업자", C2_NM="*자영업자"); ms = years_of(tot)
        if ms:
            m = ms[-1]; cols.append(f"자영업자 비중 {m[:4]}-{m[4:]}(%)"); series.append({reg: share(selfemp.get((m, reg)), tot.get((m, reg))) for (mm, reg) in tot if mm == m}); srcs.append(src("self-employed-sido")); latest.append(m)
    mg = rows("migration-sido")
    if mg and len(regions_in(mg)) > 1:
        d = table(mg, ITM_NM="순이동"); ms = years_of(d)
        if ms:
            last12 = ms[-12:]
            agg: dict[str, float] = defaultdict(float); cnt: dict[str, int] = defaultdict(int)
            for (mm, reg), v in d.items():
                if mm in last12:
                    agg[reg] += v; cnt[reg] += 1
            cols.append(f"순이동 최근 12개월 합 {last12[0][:4]}-{last12[0][4:]}~{last12[-1][:4]}-{last12[-1][4:]}(명)")
            series.append({reg: int(v) for reg, v in agg.items() if cnt[reg] == len(last12)}); srcs.append(src("migration-sido")); latest.append(ms[-1])
    if series:
        present = set().union(*(set(s) for s in series))
        trs = [[reg] + [s.get(reg) for s in series] for reg in ordered(present)]
        tables.append({"id": "cmp_monthly", "title": "17개 시도 월간 지표 (최근 달)", "unit": "", "columns": cols, "rows": trs,
                       "source": "; ".join(dict.fromkeys(srcs)), "latest": max(latest) if latest else "",
                       "note": NOTE_ORDER + ". 전년동월비·비중은 같은 표 안 나눗셈. 표마다 최근 달이 다를 수 있음"})
