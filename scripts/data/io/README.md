# io — 산업연관표 기반 기업유치 후보 분석 입력·출력 (scripts/attract.py)

## 입력 (여기에 둔다, 파일명 자유 — 내용으로 판별)
1. 한국은행 산업연관표 **생산자가격 거래표(기본부문)** xlsx — 행 = 투입(공급) 부문, 열 = 산출(수요) 부문, 코드 50개 이상의 정방 블록. '총투입액' 행이 있으면 그 값을, 없으면 중간투입계+부가가치 항목 합을 총투입으로 쓴다
2. 부문분류표(기본부문 ↔ 한국표준산업분류) — 한국은행 공개 파일(ECOS `2020 상품부문분류표`·`2020 산업부문분류표`)에는 KSIC 대응 열이 없다. 그래서 `scripts/build_io_ksic_map.py` 가 기업 사전에 나온 KSIC 세세분류 627개를 상품 기본부문에 **자동 추정**으로 잇는다(`io_ksic_map_auto.xlsx`·`.csv`: KSIC 대분류→상품 중분류 허용표 + 접두어 규칙 254건 + 이름 겹침. 검토용 csv 에 방식·점수 표시). 공식 연계표(ISTANS 산업분류 연계표 등, 기본부문 코드 열 + `한국표준산업분류` 열)를 구하면 이 폴더에 넣고 `io_ksic_map_auto.xlsx` 를 지운다 — attract.py 가 헤더에 '표준산업'이 있는 표를 부문분류표로 쓴다
   - 거래표 내려받기: ECOS 통계검색 > 2.2 산업연관표 > 2.2.1 2020년 실측표 기준 > 2.2.1.1 파일 다운로드 > 2024 연장표 > 투입산출표 > 생산자가격 > 기본부문(2026-09-27 반영: `ecos_2024_연장표_투입산출표_생산자가격_기본부문.xlsx`, 380부문). 한국은행 홈페이지는 robots.txt 로 크롤러를 막아(존중) 워크플로로는 못 받고, ECOS Open API(`fetch_io_api.py`, ECOS_KEY)는 대·중분류만 준다
3. `scripts/data/dalseong_companies.csv` (대구, 팩토리온) — 자동
4. 팩토리온 **전국(개별,계획) 입주업체현황** xlsx (30만 공장, 저장소에 올리지 않는다) — 3단계 후보에만 필요. 두 가지 방법: (a) 국내 PC 에서 `--factoryon <파일>` 로 실행 (b) 파일을 GitHub 릴리스(Releases → Draft a new release, 태그 예: factoryon-2026-08)에 첨부하고 Actions 의 `attract.yml` 을 실행하면 러너가 받아 분석하고 결과만 커밋한다
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
- `gaps.csv` — cluster, rank, io_sector, io_name, demand_index(클러스터 대구 종사자 × 전국 투입계수 = 요구 규모 지수, 종사자 단위), demand_share, daegu_firms, daegu_workers, coverage(min(1, 대구 공급 부문 종사자 ÷ 요구 규모 지수); 1 = 채워진 고리), gap_score(demand_share × (1−coverage))
- `candidates.csv` — io_sector, io_name, cluster, company, region, workers, sites, first_registered, expansion_signal, size_fit, region_weight, expansion, gap_score, fit_score, matched_daegu_demand, incentive. 전수 나열, fit_score 순. 연락처·평가 없음
- `attract_brief.md` — 클러스터별 빈 고리 3·후보 10·관련 국비 사업 (투자유치 부서용 A4 2장)
- `summary.json` — 기준연도·매핑률·검증 결과·필터 조건 (사이트 /supply-chain/ 이 읽음)

## 원칙
전국 평균 투입계수의 한계와 기준연도를 모든 화면에 표시. 후보는 '조건 필터 결과'이지 추천이 아니다. 특정 기업 평가 문구·순위 표현·연락처 금지.
