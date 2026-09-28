#!/usr/bin/env python3
"""산업구조지수 보고서 대구판 — 그림·표·수치 생성기 (운영자 지시 2026-09-28: 전북 산업구조 보고서를 1쪽씩 대구 현황으로, 표도 같게).

자료: data/kosis/grdp-sido-industry-all.csv(지역소득 시도·경제활동별 총부가가치, 명목·실질, 17개 시도+전국 2014~2024)
      data/kosis/labor-force-sido-annual-all.csv(경활 연간: 취업자·경제활동인구·15세이상인구)
      data/kosis/biz-census-sido-industry-all.csv(+meta, 전국사업체조사 종사자 2020~2023)
지표 정의는 scripts/structure_index.py(LQ·HHI·SCI·특화 비중·고부가 3부문). 값은 그대로, 평가 없음. 기관·작성자 명기 없음(계산 방식만 따름).
출력: public/figures/<ID>/figN.svg (scripts/figure.py), data/kosis/structure_report.json(본문에 옮길 수치), 화면에 표 마크다운
사용: python3 scripts/structure_report.py
"""
from __future__ import annotations
import csv, json, math, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure  # noqa: E402
from structure_index import LEAVES, HIGH, SHORT, REGION_SHORT, load, shares, cagr, pearson  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
K = ROOT / "data" / "kosis"
ID = "2026-09-30-policy-structure-daegu"
OUT = ROOT / "public" / "figures" / ID
Y0, Y1 = 2015, 2024
SRC = "국가데이터처 지역소득·경제활동인구조사(KOSIS), 다잇다 노트 시산"
MFG = ["음식료품 및 담배제조업", "섬유 의복 및 가죽 제품 제조업", "목재종이인쇄 및 복제업", "석탄 및 석유 화학제품 제조업", "비금속광물 및 금속제품 제조업",
       "전기 전자 및 정밀기기 제조업", "기계 운송장비 및 기타 제품 제조업"]
SVC = ["도매 및 소매업", "운수 및 창고업", "숙박 및 음식점업", "정보통신업", "금융 및 보험업", "부동산업", "전문 과학 및 기술 서비스업",
       "사업시설 관리 사업 지원 및 임대 서비스업", "공공 행정 국방 및 사회보장 행정", "교육 서비스업", "보건업 및 사회복지 서비스업",
       "예술 스포츠 및 여가관련 서비스", "협회 및 단체 수리 및 기타 개인 서비스업"]
UTIL = ["전기 가스 증기 및 공기 조절 공급업", "수도 하수 및 폐기물 처리 원료 재생업"]
METRO6 = ["부산", "대구", "인천", "광주", "대전", "울산"]
REGIONS17 = [r for r in REGION_SHORT.values() if r != "전국"]


def save(spec: dict, name: str) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    svg = figure.RENDER[spec["type"]](spec)
    (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")
    return f"/figures/{ID}/{name}.svg"


def load_real_sectors():
    real = defaultdict(dict)   # (region, year) -> {sector or 집계: 실질}
    for r in csv.DictReader(open(K / "grdp-sido-industry-all.csv", encoding="utf-8")):
        if r["ITM_NM"] == "실질" and r["DT"] not in ("", "-"):
            real[(r["C1_NM"], int(r["PRD_DE"]))][r["C2_NM"]] = float(r["DT"])
    return real


def load_lf():
    lf = defaultdict(dict)   # (region, year) -> {item: value}
    for r in csv.DictReader(open(K / "labor-force-sido-annual-all.csv", encoding="utf-8")):
        if r["DT"] not in ("", "-"):
            lf[(r["C1_NM"], int(r["PRD_DE"]))][r["ITM_NM"]] = float(r["DT"])
    return lf


def census_lq_major():
    """전국사업체조사 종사자 기준 지역×대분류 LQ(2023)."""
    p, mp = K / "biz-census-sido-industry-all.csv", K / "biz-census-sido-industry-all.meta.json"
    codes = {}
    for it in json.loads(mp.read_text(encoding="utf-8")):
        if str(it.get("OBJ_ID_SN")) == "2" and len(it["ITM_ID"]) == 1 and it["ITM_ID"] != "0":
            codes[it["ITM_NM"]] = it["ITM_ID"]
    emp = defaultdict(dict)
    for r in csv.DictReader(open(p, encoding="utf-8")):
        if r["ITM_NM"] != "종사자수" or r["C3_NM"] not in ("계", "") or r["C2_NM"] not in codes:
            continue
        try:
            emp[(r["C1_NM"], int(r["PRD_DE"]))][r["C2_NM"]] = float(r["DT"])
        except ValueError:
            pass
    y = max(y for (_, y) in emp)
    nat = emp[("전국", y)]; ntot = sum(nat.values())
    secs = [s for s in codes if s in nat]
    lq = {}
    for (reg, yy), d in emp.items():
        if yy != y or reg == "전국":
            continue
        tot = sum(d.values())
        lq[reg] = {s: round((d.get(s, 0) / tot) / (nat[s] / ntot), 2) if nat.get(s) and tot else None for s in secs}
    return y, secs, lq, emp


def ols_fe(y: list[float], X: list[list[float]], groups: list[str], times: list[int]) -> tuple[list[float], list[float], float, int]:
    """패널 고정효과 OLS(지역·연도 더미) — 표준 라이브러리. 반환: 계수, 표준오차(통상), R², n. 가우스 소거."""
    gl, tl = sorted(set(groups)), sorted(set(times))
    rows = []
    for i in range(len(y)):
        row = list(X[i]) + [1.0 if groups[i] == g else 0.0 for g in gl[1:]] + [1.0 if times[i] == t else 0.0 for t in tl[1:]] + [1.0]
        rows.append(row)
    k = len(rows[0]); n = len(rows)
    XtX = [[sum(rows[i][a] * rows[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(rows[i][a] * y[i] for i in range(n)) for a in range(k)]
    # 역행렬(가우스-조던)
    A = [XtX[i][:] + [1.0 if i == j else 0.0 for j in range(k)] for i in range(k)]
    for c in range(k):
        piv = max(range(c, k), key=lambda r: abs(A[r][c]))
        A[c], A[piv] = A[piv], A[c]
        d = A[c][c] or 1e-12
        A[c] = [v / d for v in A[c]]
        for r in range(k):
            if r != c and A[r][c]:
                f = A[r][c]; A[r] = [rv - f * cv for rv, cv in zip(A[r], A[c])]
    inv = [row[k:] for row in A]
    beta = [sum(inv[a][b] * Xty[b] for b in range(k)) for a in range(k)]
    yhat = [sum(rows[i][a] * beta[a] for a in range(k)) for i in range(n)]
    ss_res = sum((y[i] - yhat[i]) ** 2 for i in range(n)); ym = sum(y) / n; ss_tot = sum((v - ym) ** 2 for v in y)
    dof = max(1, n - k); s2 = ss_res / dof
    se = [math.sqrt(max(0.0, s2 * inv[a][a])) for a in range(k)]
    return beta[:len(X[0])], se[:len(X[0])], (1 - ss_res / ss_tot if ss_tot else 0.0), n


def stars(b: float, se: float) -> str:
    t = abs(b / se) if se else 0
    return "***" if t > 2.58 else "**" if t > 1.96 else "*" if t > 1.645 else ""


def main() -> int:
    gva, real_tot, emp = load()
    real = load_real_sectors()
    lf = load_lf()
    for (reg, y) in list(emp):          # 경제활동인구조사는 전국이 '계'
        if reg == "계":
            emp[("전국", y)] = emp[(reg, y)]
    for (reg, y) in list(lf):
        if reg == "계":
            lf[("전국", y)] = lf[(reg, y)]
    R = {v: k for k, v in REGION_SHORT.items()}   # short -> full
    D = {}   # 본문 수치
    regs = [r for r in REGIONS17]
    # --- 지역별 지표 ---
    sh = {(r, y): shares(gva[(R[r], y)]) for r in regs + ["전국"] for y in range(2014, Y1 + 1) if gva.get((R[r], y))}
    lqv = {(r, y): {s: (sh[(r, y)][s] / sh[("전국", y)][s] if sh[("전국", y)][s] else None) for s in LEAVES} for (r, y) in sh if r != "전국"}
    hhi = {(r, y): sum((v * 100) ** 2 for v in sh[(r, y)].values()) for (r, y) in sh}
    sci = {(r, y): 0.5 * sum(abs(sh[(r, y)][s] - sh[(r, y - 1)][s]) for s in LEAVES) * 100 for (r, y) in sh if (r, y - 1) in sh}
    sci_h = {(r, y): 0.5 * sum(abs(sh[(r, y)][s] - sh[(r, y - 1)][s]) for s in HIGH) * 100 for (r, y) in sh if (r, y - 1) in sh}
    spec_share = {(r, y): sum(sh[(r, y)][s] for s in LEAVES if lqv[(r, y)][s] and lqv[(r, y)][s] >= 1) * 100 for (r, y) in lqv}
    high_share = {(r, y): sum(sh[(r, y)][s] for s in HIGH) * 100 for (r, y) in sh}
    g_grdp = {r: cagr(real_tot[(R[r], Y0, "지역내총생산(시장가격)")], real_tot[(R[r], Y1, "지역내총생산(시장가격)")], Y1 - Y0) for r in regs + ["전국"]}
    prod = {(r, y): real_tot[(R[r], y, "총부가가치(기초가격)")] / emp[(R[r], y)] for r in regs + ["전국"] for y in range(2014, Y1 + 1) if (R[r], y) in emp and (R[r], y, "총부가가치(기초가격)") in real_tot}
    g_prod = {r: cagr(prod[(r, Y0)], prod[(r, Y1)], Y1 - Y0) for r in regs + ["전국"] if (r, Y0) in prod and (r, Y1) in prod}
    g_high = {r: cagr(sum(real[(R[r], Y0)].get(s, 0) for s in HIGH), sum(real[(R[r], Y1)].get(s, 0) for s in HIGH), Y1 - Y0) for r in regs + ["전국"]}
    corr = {r: pearson([lqv[(r, Y0)][s] or 0 for s in LEAVES], [lqv[(r, Y1)][s] or 0 for s in LEAVES]) for r in regs}
    hhi_chg = {r: cagr(hhi[(r, Y0)], hhi[(r, Y1)], Y1 - Y0) for r in regs}
    sci_avg = {r: sum(sci[(r, y)] for y in range(Y0, Y1 + 1)) / (Y1 - Y0 + 1) for r in regs + ["전국"]}
    scih_avg = {r: sum(sci_h[(r, y)] for y in range(Y0, Y1 + 1)) / (Y1 - Y0 + 1) for r in regs + ["전국"]}
    pop_key = "15세이상인구"
    g_pop = {}
    for r in regs + ["전국"]:   # 세종처럼 2015년 값이 없는 지역은 첫 연도부터(기간을 줄여 연평균)
        ys_ = [y for y in range(Y0, Y1 + 1) if (R[r], y) in lf and pop_key in lf[(R[r], y)]]
        if len(ys_) >= 3:
            g_pop[r] = cagr(lf[(R[r], ys_[0])][pop_key], lf[(R[r], Y1)][pop_key], Y1 - ys_[0])
    D["pop_note"] = {r: min(y for y in range(Y0, Y1 + 1) if (R[r], y) in lf and pop_key in lf[(R[r], y)]) for r in regs if r in g_pop}
    avg = lambda d: sum(d[r] for r in regs if d.get(r) is not None) / len([r for r in regs if d.get(r) is not None])
    D["grdp_growth"] = {r: round(v, 2) for r, v in g_grdp.items()}
    D["prod_growth"] = {r: round(v, 2) for r, v in g_prod.items()}
    D["high_growth"] = {r: round(v, 2) for r, v in g_high.items()}
    D["lq_corr"] = {r: round(v, 3) for r, v in corr.items()}; D["lq_corr_avg"] = round(avg(corr), 3)
    D["hhi_2024"] = {r: round(hhi[(r, Y1)]) for r in regs}; D["hhi_avg"] = round(avg({r: hhi[(r, Y1)] for r in regs}))
    D["hhi_chg"] = {r: round(v, 2) for r, v in hhi_chg.items()}; D["hhi_chg_avg"] = round(avg(hhi_chg), 2)
    D["sci_avg"] = {r: round(v, 4) for r, v in sci_avg.items()}; D["sci_avg_all"] = round(avg(sci_avg), 4)
    D["scih_avg"] = {r: round(v, 4) for r, v in scih_avg.items()}; D["scih_avg_all"] = round(avg(scih_avg), 4)
    D["pop_growth"] = {r: round(v, 2) for r, v in g_pop.items()}
    D["daegu"] = {"hhi": {y: round(hhi[("대구", y)]) for y in range(2014, Y1 + 1)}, "sci": {y: round(sci[("대구", y)], 4) for y in range(Y0, Y1 + 1)},
                  "sci_nat": {y: round(sci[("전국", y)], 4) for y in range(Y0, Y1 + 1)}, "spec_share": {y: round(spec_share[("대구", y)], 1) for y in (Y0, Y1)},
                  "high_share": {y: round(high_share[("대구", y)], 1) for y in (Y0, Y1)}, "high_share_nat": {y: round(high_share[("전국", y)], 1) for y in (Y0, Y1)},
                  "lq_2024": {SHORT.get(s, s): round(lqv[("대구", Y1)][s], 2) for s in LEAVES}, "lq_2015": {SHORT.get(s, s): round(lqv[("대구", Y0)][s], 2) for s in LEAVES},
                  "share_2024": {SHORT.get(s, s): round(sh[("대구", Y1)][s] * 100, 1) for s in LEAVES}, "share_2015": {SHORT.get(s, s): round(sh[("대구", Y0)][s] * 100, 1) for s in LEAVES},
                  "rank_hhi": sorted(regs, key=lambda r: -hhi[(r, Y1)]).index("대구") + 1, "rank_sci": sorted(regs, key=lambda r: -sci_avg[r]).index("대구") + 1,
                  "rank_growth": sorted(regs, key=lambda r: -g_grdp[r]).index("대구") + 1, "rank_corr": sorted(regs, key=lambda r: -corr[r]).index("대구") + 1}
    D["metro6_avg"] = {"grdp": round(sum(g_grdp[r] for r in METRO6) / 6, 2), "prod": round(sum(g_prod[r] for r in METRO6) / 6, 2), "pop": round(sum(g_pop[r] for r in METRO6 if r in g_pop) / len([r for r in METRO6 if r in g_pop]), 2)}
    figs = {}
    # 요약-1 / 2-12: 성장률 vs 고착화
    pts = [{"label": r, "x": corr[r], "y": g_grdp[r], "highlight": r == "대구"} for r in regs]
    figs["s1"] = save({"type": "scatter", "title": "경제성장률과 산업구조 고착화 수준 간 관계", "xlabel": "2015년과 2024년 입지계수의 상관계수", "ylabel": "연평균 경제성장률(2015~24년, %)",
                       "points": pts, "xmean": avg(corr), "ymean": g_grdp["전국"], "xmean_label": "17개 시도 평균", "ymean_label": "전국", "xdec": 3, "source": SRC}, "s1")
    figs["s2"] = save({"type": "scatter", "title": "경제성장률과 산업집중도 변화율 간 관계", "xlabel": "산업집중도 연평균 변화율(2015~24년, %)", "ylabel": "연평균 경제성장률(%)",
                       "points": [{"label": r, "x": hhi_chg[r], "y": g_grdp[r], "highlight": r == "대구"} for r in regs], "xmean": avg(hhi_chg), "ymean": g_grdp["전국"],
                       "xmean_label": "17개 시도 평균", "ymean_label": "전국", "xdec": 2, "source": SRC}, "s2")
    order = sorted(regs, key=lambda r: -g_high[r])
    figs["1-1"] = save({"type": "hbar", "title": "지역별 첨단·지식기반 산업 성장률(실질, 2015~24년 연평균)", "unit": "%", "categories": order, "series": [{"name": "고부가 3부문", "values": [round(g_high[r], 1) for r in order]}], "source": SRC}, "fig1-1")
    order = sorted(regs, key=lambda r: -g_grdp[r])
    figs["1-2"] = save({"type": "hbar", "title": "지역별 연평균 경제성장률(실질 GRDP, 2015~24년)", "unit": "%", "categories": order + ["전국"], "series": [{"name": "성장률", "values": [round(g_grdp[r], 1) for r in order] + [round(g_grdp["전국"], 1)]}], "source": SRC}, "fig1-2")
    # 2-1 산업별 총부가가치 비중 (대구 vs 전국, 2024)
    grp = lambda s_: {"서비스업": sum(s_[x] for x in SVC) * 100, "제조업": sum(s_[x] for x in MFG) * 100, "건설업": s_["건설업"] * 100, "전기가스수도": sum(s_[x] for x in UTIL) * 100, "농림어업·광업": (s_["농업 임업 및 어업"] + s_["광업"]) * 100}
    gd, gn = grp(sh[("대구", Y1)]), grp(sh[("전국", Y1)])
    D["group_share"] = {"대구": {k: round(v, 1) for k, v in gd.items()}, "전국": {k: round(v, 1) for k, v in gn.items()}}
    figs["2-1"] = save({"type": "bar", "title": "산업별 총부가가치 비중(2024년)", "unit": "%", "categories": list(gd), "series": [{"name": "대구", "values": [round(v, 1) for v in gd.values()]}, {"name": "전국", "values": [round(v, 1) for v in gn.values()]}], "source": SRC}, "fig2-1")
    years = list(range(2014, Y1 + 1))
    figs["2-2"] = save({"type": "line", "title": "대구 산업별 명목 총부가가치 비중 추이", "unit": "%", "x": [str(y) for y in years],
                        "series": [{"name": "서비스업", "values": [round(grp(sh[("대구", y)])["서비스업"], 1) for y in years]}, {"name": "제조업", "values": [round(grp(sh[("대구", y)])["제조업"], 1) for y in years]}, {"name": "건설업", "values": [round(grp(sh[("대구", y)])["건설업"], 1) for y in years]}], "source": SRC}, "fig2-2")
    D["group_share_trend"] = {y: {k: round(v, 1) for k, v in grp(sh[("대구", y)]).items()} for y in (2014, Y0, 2020, Y1)}
    mfg_share = lambda y: {SHORT[s]: gva[(R["대구"], y)].get(s, 0) / sum(gva[(R["대구"], y)].get(x, 0) for x in MFG) * 100 for s in MFG}
    D["mfg_share"] = {y: {k: round(v, 1) for k, v in mfg_share(y).items()} for y in (Y0, Y1)}
    figs["2-3"] = save({"type": "bar", "title": "대구 제조업 내 업종별 부가가치 비중", "unit": "%", "categories": [SHORT[s] for s in MFG], "series": [{"name": f"{Y0}년", "values": [round(v, 1) for v in mfg_share(Y0).values()]}, {"name": f"{Y1}년", "values": [round(v, 1) for v in mfg_share(Y1).values()]}], "source": SRC}, "fig2-3")
    svc4 = {"도소매·숙박음식": ["도매 및 소매업", "숙박 및 음식점업"], "부동산업": ["부동산업"], "사업서비스": ["전문 과학 및 기술 서비스업", "사업시설 관리 사업 지원 및 임대 서비스업"], "보건·의료": ["보건업 및 사회복지 서비스업"]}
    svc_share = lambda y: {k: sum(gva[(R["대구"], y)].get(s, 0) for s in v) / sum(gva[(R["대구"], y)].get(x, 0) for x in SVC) * 100 for k, v in svc4.items()}
    D["svc_share"] = {y: {k: round(v, 1) for k, v in svc_share(y).items()} for y in (Y0, Y1)}
    figs["2-4"] = save({"type": "bar", "title": "대구 서비스업 내 업종별 부가가치 비중", "unit": "%", "categories": list(svc4), "series": [{"name": f"{Y0}년", "values": [round(v, 1) for v in svc_share(Y0).values()]}, {"name": f"{Y1}년", "values": [round(v, 1) for v in svc_share(Y1).values()]}], "source": SRC}, "fig2-4")
    # 2-7 종사자 비중(전국사업체조사 대분류, 대구 최신), 2-8 노동생산성 지수(총량, 2015=100) 대구·전국
    cy, csecs, clq, cemp = census_lq_major()
    dtot = sum(cemp[("대구", cy)].values())   # 전국사업체조사는 시도 이름이 짧다(대구·전국)
    cs = sorted(((s, cemp[("대구", cy)].get(s, 0) / dtot * 100) for s in csecs), key=lambda x: -x[1])
    D["census_year"] = cy; D["emp_share"] = {s: round(v, 1) for s, v in cs[:8]}
    figs["2-7"] = save({"type": "hbar", "title": f"대구 산업별 종사자 비중({cy}년, 전국사업체조사)", "unit": "%", "categories": [s.split("(")[0][:14] for s, _ in cs[:8]] + ["기타"], "series": [{"name": "비중", "values": [round(v, 1) for _, v in cs[:8]] + [round(100 - sum(v for _, v in cs[:8]), 1)]}], "source": "국가데이터처 전국사업체조사(KOSIS)"}, "fig2-7")
    pidx = lambda r: [round(prod[(r, y)] / prod[(r, Y0)] * 100, 1) for y in range(Y0, Y1 + 1)]
    D["prod_index"] = {"대구": dict(zip(range(Y0, Y1 + 1), pidx("대구"))), "전국": dict(zip(range(Y0, Y1 + 1), pidx("전국")))}
    figs["2-8"] = save({"type": "line", "title": "노동생산성 지수 추이(실질 총부가가치/취업자, 2015=100)", "unit": "", "x": [str(y) for y in range(Y0, Y1 + 1)], "series": [{"name": "대구", "values": pidx("대구")}, {"name": "전국", "values": pidx("전국")}], "source": SRC}, "fig2-8")
    # 2-9 / 2-10 히트맵
    figs["2-9"] = save({"type": "heatmap", "title": f"부가가치 기준 지역별 입지계수 히트맵({Y1}년)", "rows": regs, "cols": [SHORT.get(s, s) for s in LEAVES], "values": [[round(lqv[(r, Y1)][s] or 0, 2) for s in LEAVES] for r in regs], "vmin": 0.5, "vmax": 2.5, "highlight_row": "대구", "source": SRC}, "fig2-9")
    cshort = [s.split("(")[0][:9] for s in csecs]
    figs["2-10"] = save({"type": "heatmap", "title": f"종사자 기준 지역별 입지계수 히트맵({cy}년, 전국사업체조사)", "rows": regs, "cols": cshort, "values": [[clq.get(r, {}).get(s) or 0 for s in csecs] for r in regs], "vmin": 0.5, "vmax": 2.5, "highlight_row": "대구", "source": "국가데이터처 전국사업체조사(KOSIS), 다잇다 노트 시산"}, "fig2-10")
    D["emp_lq_daegu"] = {s.split("(")[0]: clq["대구"][s] for s in csecs}
    order = sorted(regs, key=lambda r: -corr[r])
    figs["2-11"] = save({"type": "hbar", "title": "과거 10년 간 지역별 특화산업 고착화 수준(2015·2024년 입지계수 상관계수)", "unit": "", "categories": order, "series": [{"name": "상관계수", "values": [round(corr[r], 3) for r in order]}], "source": SRC + f" · 17개 시도 평균 {avg(corr):.3f}"}, "fig2-11")
    # 2-13 대구 상·하위 특화산업, 표 2-1
    lq24 = sorted(((SHORT.get(s, s), lqv[("대구", Y1)][s], s) for s in LEAVES), key=lambda x: -x[1])
    top5, bot5 = lq24[:5], lq24[-5:]
    figs["2-13"] = save({"type": "hbar", "title": f"대구 상·하위 특화산업({Y1}년 부가가치 기준 입지계수)", "unit": "", "categories": [t[0] for t in top5] + ["…"] + [t[0] for t in bot5], "series": [{"name": "입지계수", "values": [round(t[1], 2) for t in top5] + [0] + [round(t[1], 2) for t in bot5]}], "source": SRC}, "fig2-13")
    D["table_2_1"] = [{"산업": t[0], "lq_2015": round(lqv[("대구", Y0)][t[2]], 1), "lq_2024": round(t[1], 1), "share_2015": round(sh[("대구", Y0)][t[2]] * 100, 1), "share_2024": round(sh[("대구", Y1)][t[2]] * 100, 1)} for t in top5]
    D["bottom5"] = [{"산업": t[0], "lq_2024": round(t[1], 2)} for t in bot5]
    # 2-14 HHI, 2-17 고집중 vs 저집중(15세 이상 인구 증가율), 2-19 SCI, 2-22 고부가 SCI 상·하위 노동생산성, 2-23, 2-24
    order = sorted(regs, key=lambda r: -hhi[(r, Y1)])
    figs["2-14"] = save({"type": "bar", "title": f"지역별 산업집중도(HHI, {Y1}년)", "unit": "", "categories": order, "series": [{"name": "HHI", "values": [round(hhi[(r, Y1)]) for r in order]}], "source": SRC + f" · 17개 시도 평균 {avg({r: hhi[(r, Y1)] for r in regs}):.0f}"}, "fig2-14")
    def split_groups(key: dict, val: dict, ns=(3, 5, 8)):
        rs = [r for r in regs if r in key and r in val]
        srt = sorted(rs, key=lambda r: -key[r]); m = sum(key[r] for r in rs) / len(rs)
        hi_all = [r for r in rs if key[r] >= m]; lo_all = [r for r in rs if key[r] < m]
        out = {"전국평균 대비": (sum(val[r] for r in hi_all) / len(hi_all), sum(val[r] for r in lo_all) / len(lo_all))}
        for n in ns:
            out[f"상하위 {n}개"] = (sum(val[r] for r in srt[:n]) / n, sum(val[r] for r in srt[-n:]) / n)
        return out
    g17 = split_groups(hhi_chg, g_pop)
    D["fig2_17"] = {k: [round(a, 2), round(b, 2)] for k, (a, b) in g17.items()}
    figs["2-17"] = save({"type": "bar", "title": "고집중 vs 저집중 지역 간 15세 이상 인구 증가율 차이(2015~24년 연평균)", "unit": "%", "categories": list(g17), "series": [{"name": "고집중(산업집중도 변화율 상위)", "values": [round(a, 2) for a, _ in g17.values()]}, {"name": "저집중", "values": [round(b, 2) for _, b in g17.values()]}], "source": SRC + " · 인구는 경제활동인구조사 15세 이상 인구"}, "fig2-17")
    order = sorted(regs, key=lambda r: -sci_avg[r])
    figs["2-19"] = save({"type": "bar", "title": "최근 시·도별 산업구조 변화속도(2015~24년 연평균 SCI, %p)", "unit": "%p", "categories": order, "series": [{"name": "SCI", "values": [round(sci_avg[r], 3) for r in order]}], "source": SRC + f" · 17개 시도 평균 {avg(sci_avg):.3f}"}, "fig2-19")
    figs["2-20"] = save({"type": "scatter", "title": "산업구조 변화속도와 경제성장률 간 관계", "xlabel": "2015~24년 연평균 산업구조 변화속도(SCI, %p)", "ylabel": "연평균 경제성장률(%)", "points": [{"label": r, "x": sci_avg[r], "y": g_grdp[r], "highlight": r == "대구"} for r in regs], "xmean": avg(sci_avg), "ymean": g_grdp["전국"], "xmean_label": "17개 시도 평균", "ymean_label": "전국", "xdec": 3, "source": SRC}, "fig2-20")
    figs["2-21"] = save({"type": "scatter", "title": "고부가산업으로의 구조 변화속도와 경제성장률 간 관계", "xlabel": "2015~24년 연평균 고부가 SCI(%p)", "ylabel": "연평균 경제성장률(%)", "points": [{"label": r, "x": scih_avg[r], "y": g_grdp[r], "highlight": r == "대구"} for r in regs], "xmean": avg(scih_avg), "ymean": g_grdp["전국"], "xmean_label": "17개 시도 평균", "ymean_label": "전국", "xdec": 4, "source": SRC}, "fig2-21")
    g22 = split_groups(scih_avg, g_prod)
    D["fig2_22"] = {k: [round(a, 2), round(b, 2)] for k, (a, b) in g22.items()}
    figs["2-22"] = save({"type": "bar", "title": "고부가 산업구조 변화속도 상·하위 지역의 노동생산성 성장률(2015~24년 연평균)", "unit": "%", "categories": list(g22), "series": [{"name": "상위", "values": [round(a, 2) for a, _ in g22.values()]}, {"name": "하위", "values": [round(b, 2) for _, b in g22.values()]}], "source": SRC + " · 노동생산성 = 실질 총부가가치/취업자(전산업)"}, "fig2-22")
    figs["2-23"] = save({"type": "line", "title": "대구 및 전국의 산업구조 변화속도(SCI, %p)", "unit": "%p", "x": [str(y) for y in range(Y0, Y1 + 1)], "series": [{"name": "전국", "values": [round(sci[("전국", y)], 3) for y in range(Y0, Y1 + 1)]}, {"name": "대구", "values": [round(sci[("대구", y)], 3) for y in range(Y0, Y1 + 1)]}], "source": SRC + f" · 평균 전국 {sci_avg['전국']:.3f}, 대구 {sci_avg['대구']:.3f}"}, "fig2-23")
    figs["2-24"] = save({"type": "bar", "title": "지역별 경제지표 격차(2015~24년 연평균 증가율)", "unit": "%", "categories": ["GRDP", "노동생산성", "15세 이상 인구"], "series": [{"name": "대구", "values": [round(g_grdp["대구"], 1), round(g_prod["대구"], 1), round(g_pop["대구"], 1)]}, {"name": "전국", "values": [round(g_grdp["전국"], 1), round(g_prod["전국"], 1), round(g_pop["전국"], 1)]}, {"name": "6개 광역시", "values": [D["metro6_avg"]["grdp"], D["metro6_avg"]["prod"], D["metro6_avg"]["pop"]]}], "source": SRC}, "fig2-24")
    # Ⅲ 패널 회귀(연간, 17개 시도 × 2016~2024): Δln Y 에 특화비중(t-1) / Δln HHI / SCI 각각, 통제: 경제활동인구 증가율, 지역·연도 고정효과
    D["panel"] = {}
    for dep_name, dep in (("GRDP", lambda r, y: math.log(real_tot[(R[r], y, "지역내총생산(시장가격)")])), ("노동생산성", lambda r, y: math.log(prod[(r, y)]))):
        res = {}
        for var, xf in (("특화산업 비중(t-1)", lambda r, y: spec_share[(r, y - 1)]), ("Δln(산업집중도)", lambda r, y: math.log(hhi[(r, y)]) - math.log(hhi[(r, y - 1)])), ("산업구조 변화속도", lambda r, y: sci[(r, y)])):
            ys, Xs, gs, ts = [], [], [], []
            for r in regs:
                for y in range(Y0 + 1, Y1 + 1):
                    try:
                        dy = dep(r, y) - dep(r, y - 1)
                        xr = [xf(r, y), math.log(lf[(R[r], y)]["경제활동인구"]) - math.log(lf[(R[r], y - 1)]["경제활동인구"])]
                    except KeyError:
                        continue
                    ys.append(dy); Xs.append(xr); gs.append(r); ts.append(y)
            b, se, r2, n = ols_fe(ys, Xs, gs, ts)
            res[var] = {"coef": round(b[0], 4), "se": round(se[0], 4), "stars": stars(b[0], se[0]), "r2": round(r2, 2), "n": n}
        D["panel"][dep_name] = res
    (K / "structure_report.json").write_text(json.dumps({"id": ID, "years": [Y0, Y1], "figures": figs, "data": D}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"그림 {len(figs)}개 → {OUT.relative_to(ROOT)} · 수치 → data/kosis/structure_report.json")
    print(json.dumps({k: D["daegu"][k] for k in ("hhi", "spec_share", "high_share", "rank_hhi", "rank_sci", "rank_growth", "rank_corr")}, ensure_ascii=False))
    print("성장률 대구/전국/6광역시:", D["grdp_growth"]["대구"], D["grdp_growth"]["전국"], D["metro6_avg"]); print("고착화 대구", D["lq_corr"]["대구"], "평균", D["lq_corr_avg"])
    print("HHI 대구", D["hhi_2024"]["대구"], "평균", D["hhi_avg"], "변화율", D["hhi_chg"]["대구"]); print("SCI 대구", D["sci_avg"]["대구"], "전국", D["sci_avg"]["전국"], "고부가", D["scih_avg"]["대구"], D["scih_avg"]["전국"])
    print("표 2-1", D["table_2_1"]); print("패널", json.dumps(D["panel"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
