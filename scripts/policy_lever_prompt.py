#!/usr/bin/env python3
"""성장 정책 대안 프롬프트 — 서비스업·제조업에서 정책으로 키울 수 있는 분야의 대안을 AI(Claude·Gemini)에게 쓰게 하는 프롬프트를 만든다
(운영자 지시 2026-10-05: '관광·외국 유학생 유치 등 서비스업 정책 대안을 제시하는 프롬프트, 제조업도 마찬가지로').

프롬프트 = 고정 지시문(역할·규칙·논증 형식·출력 형식) + [자료] 블록. [자료]는 성장 계산기(/growth/)와 같은 계산
(scripts/growth_commentary.py facts: 2015→2024, 출발 1.15%, 25개 부문 비중·입지계수·연평균 성장·전국·상위 3개 시도)과
사이트에 받아 둔 자료(외지인 관광소비, DART 연구개발비·미래 산업 공시, 식약처 의료기기 생산)에서 자동으로 채운다.
없는 자료(외국인 유학생·외국인 환자·MICE 개최 실적 등)는 '자료 없음 — 조사 항목'으로 적어, AI 가 숫자를 지어내지 않게 한다.

사용: python3 scripts/policy_lever_prompt.py --area service|mfg [--out 파일]   (기본 출력: docs/prompts/policy_levers_<area>.md)
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import growth_commentary as G  # noqa: E402

COMMON_RULES = """## 지켜야 할 규칙(어기면 그 대안은 쓰지 않는다)
1. 읽는 사람은 대구시·구청 공무원이다. 운영자는 현직 지방공무원이므로 **정책 평가·비판, 기관 입장으로 읽힐 표현, 비공개 자료 인용을 쓰지 않는다.** 대구시·정부가 지금 하는 사업이 잘됐다·부족하다를 판단하지 않는다.
2. 숫자는 아래 [자료]에 있는 값, 또는 출처(기관·자료명·연도·URL)를 적은 공개 자료의 값만 쓴다. 출처 없는 숫자, 추정 효과, '○배 증가' 같은 목표치를 지어내지 않는다. 필요한 값이 없으면 "N 은 조사 뒤 정함"이라고 쓴다.
3. GRDP 기여는 계산기와 같은 식으로만 계산한다: 업종 기여(%p) = 그 업종 비중(%) ÷ 100 × 추세보다 더한 성장(%p). 금액(억 원) = 그 업종 부가가치(억 원) × 추세보다 더한 성장 ÷ 100. 새 지출로 만드는 효과 = 지출액 × 0.415(대구 부가가치유발계수, 수입품 제외 후) ÷ 명목 GRDP. 이 식 밖의 '파급 효과'는 더하지 않는다.
4. '상위 3개 시도'는 17개 시도 가운데 그 업종 성장률이 높았던 세 곳의 평균인 비교 기준이다. 순위·평가로 쓰지 않는다.
5. 정부 대상 항목은 '정부 건의'라고 쓰지 않고 대구가 신청·추진하는 수단(특구 특례·규제자유특구·시범사업 응모·국비 공모 참여·조례 개정 등)으로 쓴다.
6. 공장등록 키워드 집계는 '품목 등록 기업 수'일 뿐이다. 기업 역량·수요의 근거로 쓰지 않는다. 특정 기업을 이름으로 부각하지 않는다(공시 자료도 집계로만).
7. 전제가 확인되지 않으면 정책 제안이 아니라 '조사 제안' 1개로 쓴다.
8. 문체는 개조식 명사형 종결('…함', '…필요'). 과장 형용사(획기적·혁신적·대폭) 금지."""

FORMAT = """## 출력 형식(마크다운)
### 0. 한눈에(3줄)
- 이 분야 묶음의 지금 비중·성장·추세, 대안을 모두 이뤘을 때 계산상 GRDP 기여(%p)와 금액(억 원) 합.

### 1. 대안 표
| 번호 | 분야(업종) | 대구 밖 수요/생산성 중 무엇을 늘리나 | 정책 수단(대구가 하는 일) | 겨냥 성장(추세보다 +%p) | 계산상 GRDP 기여(%p) | 금액(억 원) | 추적 지표(출처) |

### 2. 대안별 논증(대안마다)
- **목표**: 무엇을 얼마나(업종 성장률 +%p, 계산기 식)
- **진단**: 지금 값(비중·입지계수·연평균 성장·전국·상위 3개 시도, [자료]에서)
- **원인**: 왜 지금 이 수준인지 — 근거 출처가 있는 문장만
- **기제**: 정책 수단 → 어떤 수요·생산이 늘어 → 그 업종 부가가치로 잡히는 경로(돈이 대구 밖에서 들어오는지, 대구 안에서 옮겨 가는지 구분)
- **수단**: 대구가 할 수 있는 일(제도·사업 유형 이름까지). 국비·공모가 필요하면 그 이름과 '응모' 표현
- **기대효과**: 계산기 식으로 계산한 기여(%p)·금액. 계산식을 함께 적는다
- **한계·조사할 것**: 확인 안 된 전제, 필요한 자료(기관·자료명)

### 3. 묶음 합계와 계산기 연결
- 대안을 모두 이뤘을 때의 기여 합(%p)과 추세 1.15% 에 더한 성장률. 목표 3.0%·5.0%까지 남는 차이.
- 계산기(/growth/)에서 같은 값을 넣는 방법(어느 업종 칸에 몇 %).

### 4. 조사 항목
- [자료]에 없어 숫자를 비워 둔 항목과 받을 곳(기관·통계명)."""


def sector_rows():
    fx = G.facts()
    rep = json.loads((ROOT / "data/kosis/structure_report.json").read_text(encoding="utf-8"))
    y0, y1 = rep["years"]
    V = {}
    for r in csv.DictReader(open(ROOT / "data/kosis/grdp-sido-industry-all.csv", encoding="utf-8")):
        try:
            V[(r["ITM_NM"], r["C1_NM"], r["C2_NM"], int(r["PRD_DE"]))] = float(r["DT"])
        except ValueError:
            pass
    R = G.REGION
    tot = sum(V.get(("명목", R, k, y1), 0) for k, _ in G.LEAVES)
    ntot = sum(V.get(("명목", "전국", k, y1), 0) for k, _ in G.LEAVES)
    regions = {k[1] for k in V if k[1] != "전국"}

    def cagr(reg, k):
        a, b = V.get(("실질", reg, k, y0)), V.get(("실질", reg, k, y1))
        return ((b / a) ** (1 / (y1 - y0)) - 1) * 100 if a and b and a > 0 and b > 0 else None
    rows = []
    for k, nm in G.LEAVES:
        va = V.get(("명목", R, k, y1), 0)
        if va <= 0:
            continue
        s, ns = va / tot * 100, V.get(("명목", "전국", k, y1), 0) / ntot * 100
        cs = sorted([c for c in (cagr(x, k) for x in regions) if c is not None], reverse=True)
        avgc = sum(V.get(("실질기여도", R, k, y), 0) for y in range(y0 + 1, y1 + 1)) / (y1 - y0)
        rows.append({"k": k, "nm": nm, "s": s, "lq": s / ns if ns else 0, "g": cagr(R, k) or 0, "gn": cagr("전국", k), "t3": sum(cs[:3]) / 3,
                     "avgc": avgc, "va": va / 100, "mfg": k in G.MFG, "high": k in G.HIGH})
    return fx, rows, (y0, y1)


def table(rows) -> str:
    out = ["| 업종 | 비중(%) | 입지계수 | 대구 연평균 성장(%) | 전국(%) | 상위 3개 시도 평균(%) | 평균 기여(%p) | 부가가치(억 원) | +1%p 성장 때 GRDP 기여(%p)·금액(억 원) |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in sorted(rows, key=lambda r: -r["s"]):
        out.append(f"| {r['nm']}{' (고부가)' if r['high'] else ''} | {r['s']:.1f} | {r['lq']:.2f} | {r['g']:.1f} | {r['gn']:.1f} | {r['t3']:.1f} | {r['avgc']:.2f} | {r['va']:,.0f} | {r['s'] / 100:.3f} · {r['va'] / 100:,.0f} |")
    return "\n".join(out)


def tourism_block() -> str:
    p = ROOT / "data/tourism/datalab_spend.csv"
    if not p.exists():
        return "- 외지인 관광소비: 자료 없음"
    by = defaultdict(Counter)
    for r in csv.DictReader(open(p, encoding="utf-8")):
        if r["code"] == "27" and r["group"] == "외지인" and r["industry"] != "전체":
            by[r["ym"][:4]][r["industry"]] += float(r["amount_thousand_won"] or 0)
    full = sorted(by)[-2] if len(by) > 1 else sorted(by)[-1]
    c = by[full]
    t = sum(c.values())
    comp = " · ".join(f"{k} {v / t * 100:.1f}%" for k, v in c.most_common())
    return (f"- 대구 외지인 관광소비({full}년, 한국관광 데이터랩 신용카드 기반, 데이터랩은 총량보다 추세로 보라고 안내): {t / 1e9:.2f}조 원, 업종 구성 {comp}. "
            f"출처 https://datalab.visitkorea.or.kr/datalab/portal/loc/getAreaDataForm.do\n"
            f"- 외지인 관광소비가 10% 늘면 계산기 식으로 {t / 1e9 * 0.1:.2f}조 원 × 0.415 ÷ 명목 GRDP 74.5조 원 ≈ GRDP +{t / 1e9 * 0.1 * 0.415 / 74.5 * 100:.2f}%p.")


def service_data(fx, rows) -> str:
    svc = [r for r in rows if not r["mfg"]]
    return f"""[자료] — 성장 계산기(/growth/)와 같은 정의(산업구조지수 리포트 기준, 2015→2024년, 지역소득 25개 부문)
- 대구 실질 GRDP 연평균 {fx['추세(연평균, %)']}%(전국 {fx['전국(%)']}%, 6개 광역시 {fx['6개 광역시 평균(%)']}%), 명목 GRDP {fx['명목 GRDP(조 원)']}조 원. 목표 3.0%·5.0%까지 차이 1.85%p·3.85%p.
- 2016~2024년 공표 실질기여도: 서비스업 합 1.19%p, 제조업 -0.03%p(GRDP 합 1.16%p).
- 대구 부가가치를 만든 최종수요: 대구 안 53.7% · 다른 지역 31.2% · 수출 15.1%(한국은행 「2020년 지역산업연관표」 62쪽). 대구 최종수요의 공급처: 대구 생산 64.7% · 다른 지역 이입 29.1% · 수입 6.2%(55쪽).

### 서비스·기타 업종(제조업 제외)
{table(svc)}

### 분야별로 받아 둔 자료
{tourism_block()}
- 의료기기(제조) 대구 생산은 제조업 프롬프트 [자료]에 있음. 보건·사회복지는 위 표(입지계수·성장).
- 외국인 유학생 수(대구 소재 대학): 자료 없음 — 조사 항목(교육부 「국내 고등교육기관 외국인 유학생 현황」, 대학알리미).
- 외국인 환자 수(대구): 자료 없음 — 조사 항목(한국보건산업진흥원 「외국인환자 유치실적」 지역별).
- 국제회의·MICE 개최 실적(대구): 자료 없음 — 조사 항목(한국관광공사 「MICE 산업통계」, 문화체육관광부).
- 다른 지역 환자 유입 비율: 자료 없음 — 조사 항목(국민건강보험공단 「지역별 의료이용통계」).

### 이미 정리된 방향(같은 사이트 계산 결과, 평가 아님)
- 대구 밖 돈을 들여오는 서비스: 관광·MICE·의료(외국인·다른 지역 환자)·대학(유학생·다른 지역 학생)·역외로 파는 사업·전문 서비스.
- 대구 안에서 소비를 옮기기만 하는 수단(예: 지역화폐의 업종 간 이동분)은 GRDP 총량 효과가 작음 — 새로 생긴 지출·역외에서 돌아온 지출만 기여.
"""


def mfg_data(fx, rows) -> str:
    m = [r for r in rows if r["mfg"]]
    rnd = list(csv.DictReader(open(ROOT / "scripts/data/company_rnd.csv", encoding="utf-8"))) if (ROOT / "scripts/data/company_rnd.csv").exists() else []
    ly = max((r["year"] for r in rnd), default="")
    rnd_sum = sum(float(r["rnd_won"] or 0) for r in rnd if r["year"] == ly) / 1e8
    fut = list(csv.DictReader(open(ROOT / "data/dart/future.csv", encoding="utf-8"))) if (ROOT / "data/dart/future.csv").exists() else []
    fields = Counter(f for r in fut for f in r["fields"].split(", ") if f)
    dev = [r for r in csv.DictReader(open(ROOT / "data/mfds/device_region.csv", encoding="utf-8"))] if (ROOT / "data/mfds/device_region.csv").exists() else []
    dy = max((r["year"] for r in dev), default="")
    dg = next((r for r in dev if r["year"] == dy and r["scope"] == "전체" and r["kind"] == "생산" and r["region"] == "대구"), None)
    rep = json.loads((ROOT / "data/kosis/structure_report.json").read_text(encoding="utf-8"))["data"]
    ms = rep.get("mfg_share", {})
    return f"""[자료] — 성장 계산기(/growth/)와 같은 정의(산업구조지수 리포트 기준, 2015→2024년)
- 대구 실질 GRDP 연평균 {fx['추세(연평균, %)']}%(전국 {fx['전국(%)']}%), 명목 GRDP {fx['명목 GRDP(조 원)']}조 원. 제조업 비중 {fx['묶음 비중(%)']['제조업']}%(전국 28.6%), 2016~2024년 제조업 평균 기여 -0.03%p.
- 고부가 3부문 비중 {fx['고부가 3부문 비중(%)']}%(전국 {fx['전국 고부가 비중(%)']}%) — 제조업 가운데 고부가는 전기·전자·정밀기기. 산업집중도 {fx['산업집중도']}(17개 시도 평균 {fx['17개 시도 산업집중도 평균']}).
- 계산기 '제조업만' 길: 목표 3.0% 에 제조업 7개 업종이 추세보다 +8.7%p, 5.0% 에 +18.1%p 더 성장해야 함. '제조업 → 상위 3개 시도 수준' 시나리오 성장률 2.1%.
- 제조업 안 업종 구성(제조업 부가가치 = 100, 2015 → 2024): {', '.join(f"{k} {ms.get('2015', {}).get(k, '')}→{v}" for k, v in ms.get('2024', {}).items())}

### 제조업 7개 업종
{table(m)}

### 기업 공시·생산 자료(집계로만 쓴다)
- DART 대구 본사 공시 기업 연구개발비({ly}년, 사업보고서 '연구개발 활동' 표를 찾은 {len({r['corp_code'] for r in rnd if r['year'] == ly})}곳): 합계 약 {rnd_sum:,.0f}억 원.
- DART 미래 산업 관련 공시(최근 12개월, 원문에 낱말이 나온 시설투자·공급계약·지분·특허 공시 {len(fut)}건, 분야는 낱말 기준): {', '.join(f'{k} {v}건' for k, v in fields.most_common())}.
- 식약처 의료기기 생산(대구, {dy}년): {f"업체 {dg['firms']}곳, 생산 {float(dg['amount']) / 1e5:,.0f}억 원(전국 대비 {dg['amount_share']}%)" if dg else '자료 없음'}.
- 대구·경북 품목 지도(/supply-map/): 한국은행 특정국 의존 품목과 대구·경북 '생산품 등록 기업 수' — 역량·거래 근거가 아님.
- 업종별 생산·출하·재고지수(통계 › 제조업), 대구 본사 공시 기업 직원·재무(/companies/dart/)는 사이트에서 확인 가능.
- 자료 없음 — 조사 항목: 기업 간 거래(납품 관계), 업종별 설비투자액(대구), 업종별 수출(대구 MTI 품목은 /stats/trade/ 에 월별).
"""


def build(area: str) -> str:
    fx, rows, (y0, y1) = sector_rows()
    if area == "service":
        task = """# 역할과 과제
너는 대구 산업 통계를 정리하는 공무원용 자료 사이트(다잇다)의 정책 분석가다.
대구 **서비스업 가운데 정책으로 성장을 키울 수 있는 분야**(예: 관광·MICE, 외국 유학생·다른 지역 학생 유치, 외국인·다른 지역 환자 유치(의료), 역외로 파는 사업·전문 서비스, 금융, 정보통신)에 대해, 아래 [자료]만 근거로 **정책 대안 4~6개**를 제시하라.
- 각 대안은 '대구 밖 수요를 들여오는가(관광객·유학생·환자·역외 고객)' 또는 '같은 인력으로 생산성을 높이는가' 가운데 무엇인지 밝힌다. 대구 안 소비를 옮기기만 하는 수단은 대안으로 쓰지 않는다.
- 입지계수가 1 이상인 특화 업종(보건·사회복지, 교육, 숙박·음식점, 부동산 등)과 고부가 업종(금융·보험, 정보통신)을 구분해 다룬다.
- 대안마다 계산기 식으로 GRDP 기여를 계산하고, 목표 3.0%·5.0%와의 차이 가운데 몇 %를 메우는지 적는다."""
        data = service_data(fx, rows)
    else:
        task = """# 역할과 과제
너는 대구 산업 통계를 정리하는 공무원용 자료 사이트(다잇다)의 정책 분석가다.
대구 **제조업 7개 업종**(음식료품·담배, 섬유·의복·가죽, 목재·종이·인쇄, 석탄·석유·화학, 비금속·금속, 전기·전자·정밀기기, 기계·운송장비·기타)에 대해, 아래 [자료]만 근거로 **정책 대안 4~6개**를 제시하라.
- 대안을 세 갈래로 나눈다: ① 감소 업종(섬유·비금속·금속 등)의 감소를 멈추거나 전환하는 대안 ② 주력 업종(기계·운송장비)의 생산성·품목 전환 대안 ③ 고부가 업종(전기·전자·정밀기기, 의료기기 포함)의 비중을 키우는 대안.
- 각 대안이 '대구 밖으로 파는 양(이출·수출)을 늘리는가', '대구 안 공급망(이입 대체)을 늘리는가', '생산성을 높이는가' 가운데 무엇인지 밝힌다.
- 대안마다 계산기 식으로 GRDP 기여와 고부가 3부문 비중 변화 방향을 적고, 목표 3.0%·5.0%와의 차이 가운데 몇 %를 메우는지 적는다."""
        data = mfg_data(fx, rows)
    return f"""{task}

{COMMON_RULES}

{FORMAT}

---
{data}
(자료 기준: 국가데이터처 지역소득(KOSIS) {y0}→{y1}년, 산업구조지수 리포트 계산값, 한국은행 2020 지역산업연관표, 사이트 수집 자료. 이 프롬프트는 scripts/policy_lever_prompt.py 가 만든 것이다.)
"""


def main(argv: list[str]) -> int:
    area = argv[argv.index("--area") + 1] if "--area" in argv else "service"
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else ROOT / "docs" / "prompts" / f"policy_levers_{area}.md"
    text = build(area)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"저장: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out} ({len(text):,}자)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
