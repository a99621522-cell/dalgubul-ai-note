# io — 산업연관표 기반 기업유치 후보 분석 입력·출력 (scripts/attract.py)

## 입력 (여기에 둔다, 파일명 자유 — 내용으로 판별)
1. 한국은행 산업연관표 **생산자가격 거래표(기본부문)** xlsx — 행 = 투입(공급) 부문, 열 = 산출(수요) 부문, 코드 50개 이상의 정방 블록. '총투입액' 행이 있으면 그 값을, 없으면 중간투입계+부가가치 항목 합을 총투입으로 쓴다
2. 한국은행 산업연관표 **부문분류표** xlsx — 기본부문 코드·명 열과 한국표준산업분류(KSIC) 코드 열(예: `10111, 10112~10119, 1013(일부)`). 기본부문 코드가 거래표와 다른 체계면 부문명으로 잇는다
   - 내려받기: ECOS(ecos.bok.or.kr) > 산업연관표 > 해당 연도(2023년 연장표 또는 2020년 기준년표)에서 손으로. `.github/workflows/io_tables.yml`(scripts/fetch_io_tables.py)로 자동 수집을 시도했으나 bok.or.kr 은 robots.txt 로 크롤러를 막고 있어(존중) 받지 못했다. 워크플로는 수동 실행만 남겨 둠
3. `scripts/data/dalseong_companies.csv` (대구, 팩토리온) — 자동
4. 팩토리온 **전국(개별,계획) 입주업체현황** xlsx (30만 공장, `scripts/data/raw/` 에 두고 `--factoryon` 으로 넘김. 저장소에 올리지 않는다) — 3단계 후보에만 필요
5. `scripts/data/programs_*.csv` — 투자유치 관련 국비 사업(지방투자촉진·기회발전특구·국내복귀 등 키워드) — 자동

## API 로 받기 (scripts/fetch_io_api.py, 워크플로 io_tables.yml)
- 한국은행 Open API: https://ecos.bok.or.kr/api/ 에서 회원가입 → 인증키 신청 → GitHub Secrets `ECOS_KEY`. 워크플로가 통계표 목록에서 '산업연관' 표를 찾아(`ecos_tables.json`) 생산자가격·기본부문 표를 받아 `ecos_<코드>_<연도>_*.xlsx` 로 둔다. 표 코드를 알면 `config/io_sources.yml` `api.ecos_stat` 에 적는다
- 공공데이터포털 한국은행_산업연관표(15059627): 활용신청 뒤 요청주소를 `api.datago_url` 에 적으면 `DATA_GO_KR_KEY` 로 전부 받아 `datago_*.csv` 로 저장하고 열 이름을 출력한다(응답 구조를 본 뒤 행렬 변환을 붙인다)
- 부문분류표(KSIC 연계)는 API 에 없으므로 ECOS 화면에서 xlsx 를 받아 여기에 넣는다

## 실행
```
python3 scripts/attract.py                                  # 1·2단계 (빈 고리)
python3 scripts/attract.py --factoryon "scripts/data/raw/(2026.08월말기준)_전국(개별,계획)입주업체현황.xlsx"   # + 3·4단계
python3 scripts/attract.py --transpose                       # 자동차부품 검증이 실패하면 행·열 방향 강제 전환
```
매달 팩토리온 갱신 뒤 `scripts/monthly.sh` 가 함께 돌린다.

## 출력
- `gaps.csv` — cluster, rank, io_sector, io_name, demand_index(클러스터 대구 종사자 × 투입계수), demand_share, daegu_firms, daegu_workers, coverage(대구 공급/요구, 클러스터 안 상위 10% 수준 = 1), gap_score(demand_share × (1−coverage))
- `candidates.csv` — io_sector, io_name, cluster, company, region, workers, sites, first_registered, expansion_signal, size_fit, region_weight, expansion, gap_score, fit_score, matched_daegu_demand, incentive. 전수 나열, fit_score 순. 연락처·평가 없음
- `attract_brief.md` — 클러스터별 빈 고리 3·후보 10·관련 국비 사업 (투자유치 부서용 A4 2장)
- `summary.json` — 기준연도·매핑률·검증 결과·필터 조건 (사이트 /supply-chain/ 이 읽음)

## 원칙
전국 평균 투입계수의 한계와 기준연도를 모든 화면에 표시. 후보는 '조건 필터 결과'이지 추천이 아니다. 특정 기업 평가 문구·순위 표현·연락처 금지.
