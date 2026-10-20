# 대경권 제조업·서비스업 연계성 갱신 (사이트와 분리)

2016-02 한국은행 대구경북본부 「대구경북지역의 제조업과 서비스업간 연계성 분석」의 분석 틀을 지금 공표된 통계로 다시 계산한 자료(운영자 지시 2026-10-20 '대구경북 같이 진행해'). 원 보고서의 정책 제언은 옮기지 않고 값·나눗셈만 싣는다. 사이트는 이 폴더를 읽지 않는다.

| 파일 | 만드는 곳 | 내용 |
|---|---|---|
| `io_*.csv`, `io_summary.json` | `scripts/dg_linkage_io.py` (워크플로 `dg_linkage.yml`, Drive 의 2020 지역산업연관표 엑셀) | 대구·경북·대경권 산업연관 네트워크(보정 생산유발계수 ≥ 0.03, 중앙성·공동체·최대 신장 나무), 지역 간 중간재·최종수요 거래, 생산유발 |
| `stats_*.csv`, `stats_summary.json` | `scripts/dg_linkage_stats.py` (data/kosis) | GRDP 비중·성장·1인당, 고용·생산성, 부가가치 구조, 사업체조사 입지계수·변이할당·비교우위·기술수준, 출하액 변이할당, 제조업 급여, 고령인구, 통근·통학(인구총조사 2020) |
| `firms_*` | `scripts/dg_linkage_firms.py` | 대구 기업 사전 ↔ 경북 등록공장 이름(+생산품) 일치 |
| `io_service_purchases.csv`, `io_daegu_service_sales.csv` | `scripts/dg_linkage_io.py` | 대구·경북 33부문이 서비스(G~T)를 산 지역(17개 시도·수입), 대구 서비스 부문이 판 지역·산업 종류 |
| `report/proposal1.md`, `report/*정책제언1*.hwpx` | `scripts/dg_linkage_p1.py` | 정책 제언 1 상세(대구 지식서비스–경북 첨단제조 거래 연결) |
| `report/` | `scripts/dg_linkage_report.py` | 보고서 md·그림, 공무원 양식 HWPX(`scratchpad` 의 md2hwpx 와 같은 hwpx_blocks 경로) |

주의: 산업연관표는 33부문(원 보고서 48부문), 사업체조사는 등록기반 2020~2024, 통근 OD 의 '남구·북구'는 행 순서로 대구/포항을 가른다.
