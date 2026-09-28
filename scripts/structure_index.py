#!/usr/bin/env python3
"""시도별 산업구조 지표 — 입지계수(LQ)·산업집중도(HHI)·산업구조 변화속도(SCI)·특화산업 비중·GRDP 성장률·노동생산성.

자료: data/kosis/grdp-sido-industry-all.csv(지역소득, 시도·경제활동별 총부가가치, KOSIS DT_1C91, 17개 시도+전국, 2014~2024(2024 잠정))
      data/kosis/labor-force-sido-annual-all.csv(경제활동인구조사 연간 취업자, KOSIS DT_1DA7004S)
계산(표준 정의, 값은 그대로·평가 없음):
  - 부문: 지역소득 경제활동별 분류의 말단 24개 부문(합계·소계·순생산물세 제외). 비중 s_i = 부문 명목 총부가가치 / 24개 부문 합계
  - LQ(지역, 부문) = 지역 비중 / 전국 비중. 1 보다 크면 전국보다 그 부문의 비중이 높다
  - HHI(지역) = Σ (s_i × 100)^2 . 24개 부문이 같은 비중이면 417, 한 부문뿐이면 10,000
  - SCI(지역, 연도) = ½ Σ |s_i,t − s_i,t−1| (전산업). 고부가 SCI 는 전기·전자 및 정밀기기, 정보통신업, 금융 및 보험업 3개 부문만 같은 식으로.
    '연평균' 은 2015~2024 연도별 값의 평균
  - 특화산업 비중(지역, 연도) = LQ ≥ 1 인 부문의 비중 합(%)
  - 고착화(LQ 상관) = 2015년과 2024년 부문별 LQ 의 피어슨 상관계수
  - GRDP 실질 성장률 = 실질 지역내총생산(시장가격) 2015→2024 연평균(CAGR, %), 노동생산성 = 실질 총부가가치(기초가격) / 취업자(천명) 의 2015→2024 연평균 증가율(%)
출력: data/kosis/structure_index.csv(지역×연도 지표), data/kosis/structure_lq.csv(지역×부문×연도 비중·LQ),
      data/kosis/structure_lq_employment.csv(전국사업체조사 종사자 기준 지역×산업 중분류 LQ — 메타 파일이 있을 때), 화면에 대구 요약·17개 시도 표
사용: python3 scripts/structure_index.py [--region 대구광역시] [--json]
"""
import argparse, csv, json, math, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
K = ROOT / "data" / "kosis"
LEAVES = ["농업 임업 및 어업", "광업", "음식료품 및 담배제조업", "섬유 의복 및 가죽 제품 제조업", "목재종이인쇄 및 복제업", "석탄 및 석유 화학제품 제조업",
          "비금속광물 및 금속제품 제조업", "전기 전자 및 정밀기기 제조업", "기계 운송장비 및 기타 제품 제조업", "전기 가스 증기 및 공기 조절 공급업",
          "수도 하수 및 폐기물 처리 원료 재생업", "건설업", "도매 및 소매업", "운수 및 창고업", "숙박 및 음식점업", "정보통신업", "금융 및 보험업", "부동산업",
          "전문 과학 및 기술 서비스업", "사업시설 관리 사업 지원 및 임대 서비스업", "공공 행정 국방 및 사회보장 행정", "교육 서비스업",
          "보건업 및 사회복지 서비스업", "예술 스포츠 및 여가관련 서비스", "협회 및 단체 수리 및 기타 개인 서비스업"]
HIGH = ["전기 전자 및 정밀기기 제조업", "정보통신업", "금융 및 보험업"]
SHORT = {"농업 임업 및 어업": "농림어업", "음식료품 및 담배제조업": "음식료품·담배", "섬유 의복 및 가죽 제품 제조업": "섬유·의복·가죽", "목재종이인쇄 및 복제업": "목재·종이·인쇄",
         "석탄 및 석유 화학제품 제조업": "석탄·석유·화학", "비금속광물 및 금속제품 제조업": "비금속·금속", "전기 전자 및 정밀기기 제조업": "전기·전자·정밀기기",
         "기계 운송장비 및 기타 제품 제조업": "기계·운송장비·기타", "전기 가스 증기 및 공기 조절 공급업": "전기·가스", "수도 하수 및 폐기물 처리 원료 재생업": "수도·폐기물",
         "도매 및 소매업": "도소매", "운수 및 창고업": "운수·창고", "숙박 및 음식점업": "숙박·음식점", "전문 과학 및 기술 서비스업": "전문·과학·기술",
         "사업시설 관리 사업 지원 및 임대 서비스업": "사업시설·지원", "공공 행정 국방 및 사회보장 행정": "공공행정", "교육 서비스업": "교육", "보건업 및 사회복지 서비스업": "보건·사회복지",
         "예술 스포츠 및 여가관련 서비스": "예술·스포츠·여가", "협회 및 단체 수리 및 기타 개인 서비스업": "협회·수리·개인"}
REGION_SHORT = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산",
                "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원", "충청북도": "충북", "충청남도": "충남", "전북특별자치도": "전북", "전라남도": "전남",
                "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주", "전국": "전국"}
Y0, Y1 = 2015, 2024


def load():
    gva = defaultdict(dict)      # (region, year) -> {sector: 명목}
    real = {}                    # (region, year, item) -> 실질
    for r in csv.DictReader(open(K / "grdp-sido-industry-all.csv", encoding="utf-8")):
        y, reg, sec, v = int(r["PRD_DE"]), r["C1_NM"], r["C2_NM"], r["DT"]
        if not v or v == "-":
            continue
        if r["ITM_NM"] == "명목" and sec in LEAVES:
            gva[(reg, y)][sec] = float(v)
        if r["ITM_NM"] == "실질" and sec in ("지역내총생산(시장가격)", "총부가가치(기초가격)"):
            real[(reg, y, sec)] = float(v)
    emp = {}
    for r in csv.DictReader(open(K / "labor-force-sido-annual-all.csv", encoding="utf-8")):
        if r["ITM_NM"] == "취업자" and r["DT"] not in ("", "-"):
            emp[(r["C1_NM"], int(r["PRD_DE"]))] = float(r["DT"])
    return gva, real, emp


def shares(d: dict) -> dict:
    tot = sum(d.get(s, 0.0) for s in LEAVES)
    return {s: d.get(s, 0.0) / tot for s in LEAVES} if tot else {}


def cagr(a: float, b: float, n: int) -> float | None:
    return ((b / a) ** (1 / n) - 1) * 100 if a and b and a > 0 and b > 0 else None


def pearson(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 3:
        return None
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x); syy = sum((b - my) ** 2 for b in y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return sxy / math.sqrt(sxx * syy) if sxx and syy else None


def employment_lq() -> list[dict]:
    """전국사업체조사(시도·산업 중분류·사업체구분 '계')의 종사자수로 지역×중분류 입지계수. 메타(biz-census-sido-industry-all.meta.json)의 코드로 중분류(A01 처럼 3자)만 쓴다."""
    p, mp = K / "biz-census-sido-industry-all.csv", K / "biz-census-sido-industry-all.meta.json"
    if not p.exists():
        return []
    codes = {}
    for it in (json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else []):
        if str(it.get("OBJ_ID_SN")) == "2" and (it["ITM_NM"] not in codes or len(it["ITM_ID"]) < len(codes[it["ITM_NM"]])):
            codes[it["ITM_NM"]] = it["ITM_ID"]
    emp = defaultdict(dict)   # (region, year) -> {sector: workers}
    for r in csv.DictReader(open(p, encoding="utf-8")):
        if r["ITM_NM"] != "종사자수" or r["C3_NM"] not in ("계", ""):
            continue
        sec = r["C2_NM"]
        if codes and len(codes.get(sec, "")) != 3:
            continue
        try:
            emp[(r["C1_NM"], int(r["PRD_DE"]))][sec] = float(r["DT"])   # 'X'(비밀보호)·'-' 는 뺀다
        except ValueError:
            continue
    out = []
    for (reg, y), d in emp.items():
        nat = emp.get(("전국", y))
        if reg == "전국" or not nat:
            continue
        tot, ntot = sum(d.values()), sum(nat.values())
        for sec, v in d.items():
            ns = nat.get(sec)
            if not tot or not ntot or not ns:
                continue
            out.append({"region": REGION_SHORT.get(reg, reg), "sector": f"{codes.get(sec, '')} {sec}".strip(), "year": y, "workers": int(v), "share_pct": round(v / tot * 100, 2),
                        "national_share_pct": round(ns / ntot * 100, 2), "lq": round((v / tot) / (ns / ntot), 2)})
    return sorted(out, key=lambda r: (r["region"], r["year"], r["sector"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="대구광역시")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    gva, real, emp = load()
    regions = sorted({reg for reg, y in gva if reg != "전국"})
    years = sorted({y for reg, y in gva if reg == "전국"})
    sh = {(reg, y): shares(gva[(reg, y)]) for reg, y in gva}
    lq_rows, idx_rows = [], []
    per = {}
    for reg in regions:
        lq = {}
        for y in years:
            s, n = sh.get((reg, y)), sh.get(("전국", y))
            if not s or not n:
                continue
            for sec in LEAVES:
                lq[(sec, y)] = s[sec] / n[sec] if n[sec] else None
                lq_rows.append({"region": REGION_SHORT.get(reg, reg), "sector": SHORT.get(sec, sec), "year": y, "share_pct": round(s[sec] * 100, 2),
                                "national_share_pct": round(n[sec] * 100, 2), "lq": round(lq[(sec, y)], 2) if lq[(sec, y)] is not None else ""})
        for y in years:
            s = sh.get((reg, y))
            if not s:
                continue
            hhi = sum((s[sec] * 100) ** 2 for sec in LEAVES)
            prev = sh.get((reg, y - 1))
            sci = 0.5 * sum(abs(s[sec] - prev[sec]) for sec in LEAVES) if prev else None
            sci_h = 0.5 * sum(abs(s[sec] - prev[sec]) for sec in HIGH) if prev else None
            spec = sum(s[sec] for sec in LEAVES if (lq.get((sec, y)) or 0) >= 1) * 100
            high = sum(s[sec] for sec in HIGH) * 100
            per[(reg, y)] = {"hhi": hhi, "sci": sci, "sci_high": sci_h, "spec_share": spec, "high_share": high}
        avg = lambda k: [per[(reg, y)][k] for y in range(Y0 + 1, Y1 + 1) if (reg, y) in per and per[(reg, y)][k] is not None]
        sci_avg = sum(avg("sci")) / len(avg("sci")) if avg("sci") else None
        scih_avg = sum(avg("sci_high")) / len(avg("sci_high")) if avg("sci_high") else None
        corr = pearson([lq[(sec, Y0)] or 0 for sec in LEAVES], [lq[(sec, Y1)] or 0 for sec in LEAVES]) if (reg, Y0) in sh and (reg, Y1) in sh else None
        g = cagr(real.get((reg, Y0, "지역내총생산(시장가격)")), real.get((reg, Y1, "지역내총생산(시장가격)")), Y1 - Y0)
        e0, e1 = emp.get((reg, Y0)), emp.get((reg, Y1))
        v0, v1 = real.get((reg, Y0, "총부가가치(기초가격)")), real.get((reg, Y1, "총부가가치(기초가격)"))
        prod = cagr(v0 / e0, v1 / e1, Y1 - Y0) if e0 and e1 and v0 and v1 else None
        hhi_g = cagr(per[(reg, Y0)]["hhi"], per[(reg, Y1)]["hhi"], Y1 - Y0) if (reg, Y0) in per and (reg, Y1) in per else None
        for y in years:
            if (reg, y) not in per:
                continue
            p = per[(reg, y)]
            idx_rows.append({"region": REGION_SHORT.get(reg, reg), "year": y, "hhi": round(p["hhi"]), "sci": round(p["sci"], 4) if p["sci"] is not None else "",
                             "sci_high": round(p["sci_high"], 4) if p["sci_high"] is not None else "", "spec_share_pct": round(p["spec_share"], 1), "high_share_pct": round(p["high_share"], 1),
                             "grdp_real_bil_won": round(real.get((reg, y, "지역내총생산(시장가격)"), 0) / 1000, 1), "employed_thousand": emp.get((reg, y), ""),
                             "sci_avg_2015_2024": round(sci_avg, 4) if y == Y1 and sci_avg is not None else "", "sci_high_avg_2015_2024": round(scih_avg, 4) if y == Y1 and scih_avg is not None else "",
                             "lq_corr_2015_2024": round(corr, 3) if y == Y1 and corr is not None else "", "grdp_cagr_2015_2024_pct": round(g, 2) if y == Y1 and g is not None else "",
                             "productivity_cagr_2015_2024_pct": round(prod, 2) if y == Y1 and prod is not None else "", "hhi_cagr_2015_2024_pct": round(hhi_g, 2) if y == Y1 and hhi_g is not None else ""})
    with open(K / "structure_lq.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(lq_rows[0].keys())); w.writeheader(); w.writerows(lq_rows)
    with open(K / "structure_index.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(idx_rows[0].keys())); w.writeheader(); w.writerows(idx_rows)
    elq = employment_lq()
    if elq:
        with open(K / "structure_lq_employment.csv", "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(elq[0].keys())); w.writeheader(); w.writerows(elq)
    last = [r for r in idx_rows if r["year"] == Y1]
    reg = REGION_SHORT.get(a.region, a.region)
    me = next(r for r in last if r["region"] == reg)
    nat = {k: sum(float(r[k]) for r in last if r[k] != "") / len([r for r in last if r[k] != ""]) for k in ("hhi", "sci_avg_2015_2024", "sci_high_avg_2015_2024", "spec_share_pct", "high_share_pct", "lq_corr_2015_2024", "grdp_cagr_2015_2024_pct", "productivity_cagr_2015_2024_pct")}
    rank = lambda k, desc=True: 1 + sorted([float(r[k]) for r in last if r[k] != ""], reverse=desc).index(float(me[k]))
    out = {"region": reg, "year": Y1, "me": me, "avg17": {k: round(v, 4) for k, v in nat.items()},
           "rank17": {k: rank(k) for k in ("hhi", "sci_avg_2015_2024", "sci_high_avg_2015_2024", "spec_share_pct", "high_share_pct", "lq_corr_2015_2024", "grdp_cagr_2015_2024_pct", "productivity_cagr_2015_2024_pct")},
           "lq_top": sorted([r for r in lq_rows if r["region"] == reg and r["year"] == Y1 and r["lq"] != ""], key=lambda r: -r["lq"])[:8],
           "lq_bottom": sorted([r for r in lq_rows if r["region"] == reg and r["year"] == Y1 and r["lq"] != ""], key=lambda r: r["lq"])[:6],
           "lq_2015": {r["sector"]: r["lq"] for r in lq_rows if r["region"] == reg and r["year"] == Y0},
           "share_2015": {r["sector"]: r["share_pct"] for r in lq_rows if r["region"] == reg and r["year"] == Y0},
           "table17": sorted(last, key=lambda r: -float(r["hhi"]))}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1)); return 0
    print(f"[{reg} {Y1}] HHI {me['hhi']}(17개 시도 중 {out['rank17']['hhi']}위, 평균 {nat['hhi']:.0f}) · 특화산업 비중 {me['spec_share_pct']}%({out['rank17']['spec_share_pct']}위) · 고부가 3부문 비중 {me['high_share_pct']}%({out['rank17']['high_share_pct']}위)")
    print(f"  SCI 연평균 {me['sci_avg_2015_2024']}({out['rank17']['sci_avg_2015_2024']}위, 평균 {nat['sci_avg_2015_2024']:.4f}) · 고부가 SCI {me['sci_high_avg_2015_2024']}({out['rank17']['sci_high_avg_2015_2024']}위, 평균 {nat['sci_high_avg_2015_2024']:.4f}) · LQ 상관 {me['lq_corr_2015_2024']}({out['rank17']['lq_corr_2015_2024']}위)")
    print(f"  GRDP 실질 CAGR {me['grdp_cagr_2015_2024_pct']}%({out['rank17']['grdp_cagr_2015_2024_pct']}위, 평균 {nat['grdp_cagr_2015_2024_pct']:.2f}) · 노동생산성 CAGR {me['productivity_cagr_2015_2024_pct']}%({out['rank17']['productivity_cagr_2015_2024_pct']}위, 평균 {nat['productivity_cagr_2015_2024_pct']:.2f})")
    print("  LQ 상위:", ", ".join(f"{r['sector']} {r['lq']}({r['share_pct']}%)" for r in out["lq_top"]))
    print("  LQ 하위:", ", ".join(f"{r['sector']} {r['lq']}({r['share_pct']}%)" for r in out["lq_bottom"]))
    print("\n| 시도 | HHI | 특화비중% | 고부가비중% | SCI | 고부가SCI | LQ상관 | GRDP CAGR% | 생산성 CAGR% |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in out["table17"]:
        print(f"| {r['region']} | {r['hhi']} | {r['spec_share_pct']} | {r['high_share_pct']} | {r['sci_avg_2015_2024']} | {r['sci_high_avg_2015_2024']} | {r['lq_corr_2015_2024']} | {r['grdp_cagr_2015_2024_pct']} | {r['productivity_cagr_2015_2024_pct']} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
