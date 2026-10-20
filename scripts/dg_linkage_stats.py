"""대경권 제조업·서비스업 연계성 갱신 — 거시·산업구조(Ⅱ장)와 비교우위 산업(Ⅲ장) 표 계산.

2016년 한국은행 대구경북본부 「대구경북지역의 제조업과 서비스업간 연계성 분석」의 Ⅱ·Ⅲ장 표를
지금 공표된 KOSIS 값으로 다시 계산한다(운영자 지시 2026-10-20 '대구경북 같이 진행해').
값은 KOSIS 표 그대로 나누기·빼기만 하고, 평가 문장은 만들지 않는다.

입력(data/kosis, kosis.yml 이 받음):
  grdp-sido-industry-all     지역소득 경제활동별 GRDP(명목·실질), 17개 시도
  population-sido            주민등록 총인구
  labor-force-sido-annual-all 경제활동인구조사 연간(취업자·고용률)
  biz-census-sido-industry-all 전국사업체조사(등록기반) 시도·산업중분류 사업체·종사자, 2020~
  mining-mfg-survey-sido     광업·제조업조사 시도·중분류 출하액 등(10인 이상) — 경북 행이 있으면 매출 기준 변이할당
  mfg-emp-wage-sido          광업·제조업조사 종사자·급여액(있으면 1인당 급여)
  population-age-sido        고령인구비율(있으면)
  commute-sido               인구총조사 현거주지·근무지 취업인구(있으면)
출력: data/dg_linkage/stats_*.csv + stats_summary.json
"""
from __future__ import annotations

import csv
import json
from collections import OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
K = ROOT / "data" / "kosis"
OUT = ROOT / "data" / "dg_linkage"

SIDO_FULL = {"대구": "대구광역시", "경북": "경상북도", "전국": "전국"}


def rows(key: str) -> list[dict]:
    p = K / f"{key}.csv"
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def write(name: str, header: list[str], data: list[list]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in data:
            w.writerow([("" if v is None else (round(v, 4) if isinstance(v, float) else v)) for v in r])
    print(f"[stats] {name} {len(data)}행")


# ── Ⅱ-1 거시: GRDP 비중·성장률·1인당·고용 ─────────────────────────────
def macro(summary: dict) -> None:
    g = defaultdict(dict)   # (item, sido) -> {year: value} for 지역내총생산(시장가격)
    for r in rows("grdp-sido-industry-all"):
        if r["C2_NM"] == "지역내총생산(시장가격)":
            g[(r["ITM_NM"], r["C1_NM"])][int(r["PRD_DE"])] = num(r["DT"])
    sidos = sorted({s for (_, s) in g if s != "전국"})
    years = sorted(g[("명목", "전국")])
    y0, y1, y2 = years[0], (years[0] + years[-1]) // 2, years[-1]
    pop = defaultdict(dict)
    for r in rows("population-sido"):
        if r["ITM_NM"] == "총인구수" and not r["C2_NM"]:
            pop[r["C1_NM"]][int(r["PRD_DE"])] = num(r["DT"])
    out = []
    nat_real_inc = sum(g[("실질", s)][y2] - g[("실질", s)][y0] for s in sidos)
    for s in ["전국"] + sidos:
        nom, real = g[("명목", s)], g[("실질", s)]
        share = lambda y: nom[y] / sum(g[("명목", x)][y] for x in sidos) * 100
        cagr = lambda a, b: ((real[b] / real[a]) ** (1 / (b - a)) - 1) * 100
        pc = lambda y: nom[y] / pop[s][y] if pop[s].get(y) else None   # 백만 원/명
        contrib = (real[y2] - real[y0]) / nat_real_inc * 100 if s != "전국" else 100.0
        out.append([s, nom[y2], share(y0), share(y1), share(y2), cagr(y0, y1), cagr(y1, y2), cagr(y0, y2), contrib,
                    pc(y0), pc(y2), (pc(y2) / (g[("명목", "전국")][y2] / pop["전국"][y2]) * 100) if pc(y2) else None,
                    pop[s].get(y0), pop[s].get(y2)])
    write("stats_macro.csv", ["시도", f"명목GRDP_{y2}_백만원", f"명목비중_{y0}", f"명목비중_{y1}", f"명목비중_{y2}",
                              f"실질성장률_{y0}_{y1}", f"실질성장률_{y1}_{y2}", f"실질성장률_{y0}_{y2}", f"실질증가기여율_{y0}_{y2}",
                              f"1인당GRDP_{y0}_백만원", f"1인당GRDP_{y2}_백만원", f"1인당GRDP_{y2}_전국=100",
                              f"인구_{y0}", f"인구_{y2}"], out)
    summary["grdp_years"] = [y0, y1, y2]

    lf = defaultdict(dict)
    for r in rows("labor-force-sido-annual-all"):
        lf[(r["ITM_NM"], r["C1_NM"])][int(r["PRD_DE"])] = num(r["DT"])
    lyears = sorted(lf[("취업자", "계")])
    ly = [lyears[0], lyears[0] + 5, lyears[-1]]
    out = []
    for s in ["계", "대구광역시", "경상북도"]:
        out.append([s] + [lf[("취업자", s)].get(y) for y in ly] + [lf[("고용률", s)].get(y) for y in ly]
                   + [lf[("15-64세 고용률", s)].get(y) for y in ly] + [lf[("실업률", s)].get(y) for y in ly])
    write("stats_labor.csv", ["지역"] + [f"취업자_{y}_천명" for y in ly] + [f"고용률_{y}" for y in ly]
          + [f"15_64고용률_{y}" for y in ly] + [f"실업률_{y}" for y in ly], out)
    summary["labor_years"] = ly

    # 노동생산성 = 명목 GRDP ÷ 취업자(같은 해) — 원 보고서 <표 7> 의 정의(전국 = 100)
    out = []
    lp_nat = {y: g[("명목", "전국")][y] / (lf[("취업자", "계")][y] * 1000) for y in (y0, y1, y2) if lf[("취업자", "계")].get(y)}
    for s in ["대구광역시", "경상북도"]:
        rr = [s]
        for y in (y0, y1, y2):
            v = g[("명목", s)][y] / (lf[("취업자", s)][y] * 1000) if lf[("취업자", s)].get(y) else None
            rr += [v, v / lp_nat[y] * 100 if v and y in lp_nat else None]
        out.append(rr)
    out.append(["전국"] + sum([[lp_nat.get(y), 100.0] for y in (y0, y1, y2)], []))
    write("stats_productivity.csv", ["지역"] + sum([[f"노동생산성_{y}_백만원", f"전국=100_{y}"] for y in (y0, y1, y2)], []), out)

    age = defaultdict(dict)
    for r in rows("population-age-sido"):
        if r["ITM_NM"].startswith("고령인구비율"):
            age[r["C1_NM"]][int(r["PRD_DE"])] = num(r["DT"])
    if age:
        ay = sorted(age.get("전국", {}))
        pick = [y for y in (ay[0], ay[len(ay) // 2], ay[-1])] if ay else []
        write("stats_age.csv", ["지역"] + [f"고령인구비율_{y}" for y in pick],
              [[s] + [age[s].get(y) for y in pick] for s in ("전국", "대구광역시", "경상북도")])


# ── Ⅱ-2 산업구조: 부가가치 비중 ───────────────────────────────────────
VA_GROUP = OrderedDict([
    ("1차산업", ["농업 임업 및 어업", "광업"]),
    ("제조업", ["제조업"]),
    ("SOC", ["전기 가스 증기 및 공기 조절 공급업", "건설업"]),
    ("서비스업", ["서비스업"]),     # KOSIS '서비스업' 행 — 수도·하수·폐기물이 이 묶음에 들어 있다(합 = 총부가가치 확인)
])


def va_structure(summary: dict) -> None:
    v = defaultdict(dict)
    for r in rows("grdp-sido-industry-all"):
        if r["C1_NM"] in ("대구광역시", "경상북도", "전국") and r["ITM_NM"] in ("명목", "실질"):
            v[(r["ITM_NM"], r["C1_NM"], r["C2_NM"])][int(r["PRD_DE"])] = num(r["DT"])
    y0, y1, y2 = summary["grdp_years"]
    out, check = [], {}
    for s in ("대구광역시", "경상북도", "전국"):
        for grp, parts in VA_GROUP.items():
            rr = [s, grp]
            for it in ("명목", "실질"):
                for y in (y0, y1, y2):
                    tot = v[(it, s, "총부가가치(기초가격)")][y]
                    rr.append(sum(v[(it, s, p)][y] for p in parts) / tot * 100)
            out.append(rr)
        tot = v[("명목", s, "총부가가치(기초가격)")][y2]
        check[s] = round(sum(v[("명목", s, p)][y2] for ps in VA_GROUP.values() for p in ps) / tot * 100, 2)
    write("stats_va_share.csv", ["지역", "구분"] + [f"{it}_{y}" for it in ("명목", "실질") for y in (y0, y1, y2)], out)
    summary["va_group_sum_check_pct"] = check   # 명목 합이 100 이면 묶음이 총부가가치를 빠짐없이 나눈 것

    # 제조업 7개 업종(지역소득 분류)의 명목 비중
    mfg = ["음식료품 및 담배제조업", "섬유 의복 및 가죽 제품 제조업", "목재종이인쇄 및 복제업", "석탄 및 석유 화학제품 제조업",
           "비금속광물 및 금속제품 제조업", "전기 전자 및 정밀기기 제조업", "기계 운송장비 및 기타 제품 제조업"]
    svc = ["도매 및 소매업", "운수 및 창고업", "숙박 및 음식점업", "정보통신업", "금융 및 보험업", "부동산업",
           "전문 과학 및 기술 서비스업", "사업시설 관리 사업 지원 및 임대 서비스업", "공공 행정 국방 및 사회보장 행정",
           "교육 서비스업", "보건업 및 사회복지 서비스업", "예술 스포츠 및 여가관련 서비스", "협회 및 단체 수리 및 기타 개인 서비스업"]
    out = []
    for p in mfg + svc:
        rr = [p]
        for s in ("대구광역시", "경상북도", "전국"):
            for y in (y0, y2):
                rr.append(v[("명목", s, p)][y] / v[("명목", s, "총부가가치(기초가격)")][y] * 100)
        for s in ("대구광역시", "경상북도"):   # 부가가치 입지계수(최근 해)
            rr.append((v[("명목", s, p)][y2] / v[("명목", s, "총부가가치(기초가격)")][y2])
                      / (v[("명목", "전국", p)][y2] / v[("명목", "전국", "총부가가치(기초가격)")][y2]))
        out.append(rr)
    write("stats_va_detail.csv", ["업종"] + [f"{s}_{y}" for s in ("대구", "경북", "전국") for y in (y0, y2)] + [f"LQ_대구_{y2}", f"LQ_경북_{y2}"], out)


# ── 전국사업체조사: 대분류·중분류 구조, LQ, 변이할당 ────────────────────
TECH = {   # OECD 기술수준(원 보고서 각주 5의 구분을 KSIC 10차 중분류에 옮김; 기타 운송장비(31)는 항공·선박이 섞여 중고위로 둔다)
    "첨단기술": ["의료용 물질 및 의약품 제조업"],
    "ICT": ["전자 부품 컴퓨터 영상 음향 및 통신장비 제조업"],
    "중고위기술": ["화학 물질 및 화학제품 제조업; 의약품 제외", "의료 정밀 광학 기기 및 시계 제조업", "전기장비 제조업",
               "기타 기계 및 장비 제조업", "자동차 및 트레일러 제조업", "기타 운송장비 제조업"],
    "중저위기술": ["코크스 연탄 및 석유정제품 제조업", "고무 및 플라스틱제품 제조업", "비금속 광물제품 제조업", "1차 금속 제조업",
               "금속 가공제품 제조업; 기계 및 가구 제외", "기타 제품 제조업", "산업용 기계 및 장비 수리업"],
    "저위기술": ["식료품 제조업", "음료 제조업", "담배 제조업", "섬유제품 제조업; 의복 제외", "의복 의복 액세서리 및 모피제품 제조업",
             "가죽 가방 및 신발 제조업", "목재 및 나무제품 제조업; 가구 제외", "펄프 종이 및 종이제품 제조업", "인쇄 및 기록매체 복제업",
             "가구 제조업"],
}
BIG_GROUP = {"1차산업": ["농업 임업 및 어업(01~03)", "광업(05~08)"], "제조업": ["제조업(10~34)"],
             "SOC": ["전기 가스 증기 및 공기조절 공급업(35)", "건설업(41~42)"]}


def census(summary: dict) -> None:
    d = defaultdict(dict)   # (item, sido, name) -> {year: v}
    order: list[str] = []
    parent: dict[str, str] = {}
    cur = ""
    for r in rows("biz-census-sido-industry-all"):
        n = r["C2_NM"]
        if r["C1_NM"] == "전국" and r["ITM_NM"] == "종사자수" and r["PRD_DE"] == "2024":
            if n not in order:
                order.append(n)
                if "(" in n and n.endswith(")"):
                    cur = n
                elif n != "전체 산업":
                    parent[n] = cur
        d[(r["ITM_NM"], r["C1_NM"], n)][int(r["PRD_DE"])] = num(r["DT"])
    years = sorted(d[("종사자수", "전국", "전체 산업")])
    y0, y1 = years[0], years[-1]
    big = [n for n in order if "(" in n and n.endswith(")")]
    mids = [n for n in order if n in parent]
    # 대분류에 중분류가 하나뿐이고 이름이 같은 경우(부동산업 등)도 중분류로 남는다
    regions = ("대구", "경북", "전국")

    def val(item, s, n, y):
        return d[(item, s, n)].get(y) or 0.0

    # 대분류 묶음(1차·제조·SOC·서비스) 비중과 종사자 특화도
    out = []
    for s in ("대구", "경북"):
        for grp in ("1차산업", "제조업", "SOC", "서비스업"):
            parts = BIG_GROUP.get(grp) or [b for b in big if not any(b in v for v in BIG_GROUP.values())]
            rr = [s, grp]
            for item in ("사업체수", "종사자수"):
                for y in (y0, y1):
                    rr.append(sum(val(item, s, p, y) for p in parts) / val(item, s, "전체 산업", y) * 100)
            for y in (y0, y1):   # 종사자 특화도
                rs = sum(val("종사자수", s, p, y) for p in parts) / val("종사자수", s, "전체 산업", y)
                rn = sum(val("종사자수", "전국", p, y) for p in parts) / val("종사자수", "전국", "전체 산업", y)
                rr.append(rs / rn)
            inc_r = sum(val("종사자수", s, p, y1) - val("종사자수", s, p, y0) for p in parts)
            inc_t = val("종사자수", s, "전체 산업", y1) - val("종사자수", s, "전체 산업", y0)
            rr += [inc_r / inc_t * 100 if inc_t else None, inc_r]   # 고용 기여율(전체 증감이 작으면 100 을 크게 넘는다), 종사자 증감
            out.append(rr)
    write("stats_census_group.csv", ["지역", "구분", f"사업체비중_{y0}", f"사업체비중_{y1}", f"종사자비중_{y0}", f"종사자비중_{y1}",
                                     f"종사자특화도_{y0}", f"종사자특화도_{y1}", f"고용기여율_{y0}_{y1}", "종사자증감"], out)

    # 중분류 LQ(사업체·종사자, 최근 해) + 변이할당(종사자, y0→y1)
    gN = val("종사자수", "전국", "전체 산업", y1) / val("종사자수", "전국", "전체 산업", y0) - 1
    ss_rows, lq_rows = [], []
    adv = {"대구": [], "경북": []}
    for n in mids:
        rr = [parent[n], n]
        for s in ("대구", "경북"):
            for item in ("사업체수", "종사자수"):
                a, b = val(item, s, n, y1), val(item, "전국", n, y1)
                rr.append((a / val(item, s, "전체 산업", y1)) / (b / val(item, "전국", "전체 산업", y1)) if a and b else None)
            rr.append(val("종사자수", s, n, y1))
        lq_rows.append(rr)
        ssr = [parent[n], n]
        for s in ("대구", "경북"):
            E0, E1 = val("종사자수", s, n, y0), val("종사자수", s, n, y1)
            T0 = val("종사자수", s, "전체 산업", y0)
            gr = val("종사자수", s, "전체 산업", y1) / T0 - 1
            N0, N1 = val("종사자수", "전국", n, y0), val("종사자수", "전국", n, y1)
            if not E0 or not N0:
                ssr += [None] * 5
                continue
            gNi = N1 / N0 - 1
            gri = E1 / E0 - 1
            ns, im, rs, ds = E0 * gN, E0 * (gNi - gN), E0 * (gr - gN), E0 * (gri - gNi - (gr - gN))
            ssr += [x / T0 * 100 for x in (ns, im, rs, ds)] + [E1 - E0]
            lqb, lqe = rr[2 if s == "대구" else 5], rr[3 if s == "대구" else 6]
            if lqb and lqe and lqb >= 1 and lqe >= 1 and ds > 0:
                adv[s].append([parent[n], n, lqb, lqe, ds / T0 * 100, E1])
        ss_rows.append(ssr)
    write("stats_lq.csv", ["대분류", "중분류", f"대구_사업체LQ_{y1}", f"대구_종사자LQ_{y1}", f"대구_종사자_{y1}",
                           f"경북_사업체LQ_{y1}", f"경북_종사자LQ_{y1}", f"경북_종사자_{y1}"], lq_rows)
    write("stats_shiftshare.csv", ["대분류", "중분류"] + [f"{s}_{c}" for s in ("대구", "경북") for c in ("NS", "IM", "RS", "DS", "종사자증감")],
          ss_rows)
    for s in ("대구", "경북"):
        write(f"stats_advantage_{s}.csv", ["대분류", "중분류", "사업체LQ", "종사자LQ", "지역산업특화효과_고용_%p", f"종사자_{y1}"], adv[s])
    summary["census_years"] = [y0, y1]
    summary["advantage_count"] = {s: len(v) for s, v in adv.items()}
    summary["lq_ge1_count"] = {s: {"사업체": sum(1 for r in lq_rows if r[2 if s == "대구" else 5] and r[2 if s == "대구" else 5] >= 1),
                                   "종사자": sum(1 for r in lq_rows if r[3 if s == "대구" else 6] and r[3 if s == "대구" else 6] >= 1)}
                               for s in ("대구", "경북")}
    summary["ds_pos_count"] = {s: sum(1 for r in ss_rows if r[(5 if s == "대구" else 10)] and r[(5 if s == "대구" else 10)] > 0) for s in ("대구", "경북")}

    # OECD 기술수준별(제조업 종사자 안 비중, 전 산업 대비 특화도, 성장 기여율)
    out = []
    for s in ("대구", "경북"):
        mf0 = sum(val("종사자수", s, n, y0) for v in TECH.values() for n in v)
        mf1 = sum(val("종사자수", s, n, y1) for v in TECH.values() for n in v)
        for t, names in TECH.items():
            e0 = sum(val("종사자수", s, n, y0) for n in names)
            e1 = sum(val("종사자수", s, n, y1) for n in names)
            n0 = sum(val("종사자수", "전국", n, y0) for n in names)
            n1 = sum(val("종사자수", "전국", n, y1) for n in names)
            lq0 = (e0 / val("종사자수", s, "전체 산업", y0)) / (n0 / val("종사자수", "전국", "전체 산업", y0))
            lq1 = (e1 / val("종사자수", s, "전체 산업", y1)) / (n1 / val("종사자수", "전국", "전체 산업", y1))
            out.append([s, t, e0 / mf0 * 100, e1 / mf1 * 100, e1 / val("종사자수", s, "전체 산업", y1) * 100, lq0, lq1,
                        (e1 - e0) / (mf1 - mf0) * 100 if mf1 != mf0 else None, e1 - e0])
    write("stats_tech.csv", ["지역", "기술수준", f"제조업내비중_{y0}", f"제조업내비중_{y1}", f"전산업비중_{y1}", f"특화도_{y0}", f"특화도_{y1}",
                             f"제조업고용증감기여율_{y0}_{y1}", "종사자증감"], out)


# ── 광업·제조업조사: 출하액 변이할당(매출 기준) ─────────────────────────
def mfg_sales(summary: dict) -> None:
    d = defaultdict(dict)
    for r in rows("mining-mfg-survey-sido"):
        if r["ITM_NM"] in ("출하액 계", "부가가치"):
            d[(r["ITM_NM"], r["C1_NM"], r["C2_NM"])][int(r["PRD_DE"])] = num(r["DT"])
    if not any(k[1] == "경상북도" for k in d):
        print("[stats] 광업·제조업조사 경북 행 없음 — 매출 기준 변이할당 생략")
        return
    years = sorted(d[("출하액 계", "전국", "제조업(10~34)")]) or sorted(d[("출하액 계", "전국", "광업 및 제조업")])
    y0, y1 = years[0], years[-1]
    names = sorted({k[2] for k in d if k[1] == "전국" and k[2] not in ("광업 및 제조업",) and "(" not in k[2]})
    tot = "제조업(10~34)" if d[("출하액 계", "전국", "제조업(10~34)")] else "광업 및 제조업"
    out = []
    for n in names:
        rr = [n]
        for s in ("대구광역시", "경상북도"):
            E0, E1 = d[("출하액 계", s, n)].get(y0), d[("출하액 계", s, n)].get(y1)
            T0, T1 = d[("출하액 계", s, tot)][y0], d[("출하액 계", s, tot)][y1]
            N0, N1 = d[("출하액 계", "전국", n)].get(y0), d[("출하액 계", "전국", n)].get(y1)
            NT0, NT1 = d[("출하액 계", "전국", tot)][y0], d[("출하액 계", "전국", tot)][y1]
            if not (E0 and E1 and N0 and N1):
                rr += [None] * 4
                continue
            gN, gNi, gr, gri = NT1 / NT0 - 1, N1 / N0 - 1, T1 / T0 - 1, E1 / E0 - 1
            ds = E0 * (gri - gNi - (gr - gN))
            rr += [E1, (E1 / T1) / (N1 / NT1), ds / T0 * 100, (d[("부가가치", s, n)].get(y1) or 0) / E1 * 100]
        out.append(rr)
    write("stats_mfg_sales.csv", ["중분류"] + [f"{s}_{c}" for s in ("대구", "경북") for c in (f"출하액_{y1}_백만원", f"출하액LQ_{y1}",
                                                                                        f"출하DS_{y0}_{y1}_%p", f"부가가치율_{y1}")], out)
    summary["mfg_sales_years"] = [y0, y1]


def mfg_wage(summary: dict) -> None:
    d = defaultdict(dict)
    for r in rows("mfg-emp-wage-sido"):
        d[(r["ITM_NM"], r["C1_NM"], r["C2_NM"])][int(r["PRD_DE"])] = num(r["DT"])
    if not d:
        return
    years = sorted(d[("종사자수", "전국", "광업 및 제조업")])
    y1 = years[-1]
    out = []
    for s in ("전국", "대구광역시", "경상북도"):
        rr = [s]
        for y in (years[0], y1):
            w, e = d[("연간급여액", s, "제조업(10~34)")].get(y), d[("종사자수", s, "제조업(10~34)")].get(y)
            rr += [e, w / e if w and e else None]
        out.append(rr)
    write("stats_mfg_wage.csv", ["지역"] + sum([[f"제조업종사자_{y}", f"1인당급여_{y}_백만원"] for y in (years[0], y1)], []), out)


def commute(summary: dict) -> None:
    d = defaultdict(dict)
    for r in rows("commute-sido"):
        d[(r["ITM_NM"], r["C1_NM"], r["C2_NM"])][int(r["PRD_DE"])] = num(r["DT"])
    if not d:
        return
    years = sorted({y for v in d.values() for y in v})
    out = []
    for s in ("대구광역시", "경상북도"):
        for ind in sorted({k[2] for k in d if k[1] == s}):
            for y in years:
                a, b = d[("취업인구-현거주지", s, ind)].get(y), d[("취업인구-근무지", s, ind)].get(y)
                if a is not None and b is not None:
                    out.append([s, ind, y, a, b, b - a])
    write("stats_commute_net.csv", ["지역", "산업", "연도", "취업인구_현거주지", "취업인구_근무지", "근무지-거주지"], out)


def main() -> None:
    summary: dict = {}
    macro(summary)
    va_structure(summary)
    census(summary)
    mfg_sales(summary)
    mfg_wage(summary)
    commute(summary)
    (OUT / "stats_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
