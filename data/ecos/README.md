# 한국은행 ECOS 통계표 (data/ecos)

`config/ecos_tables.yml` 의 표를 `scripts/fetch_ecos.py`(워크플로 `ecos.yml`, 매월 10일)가 한국은행 경제통계시스템 오픈API 에서 받아 여기에 둔다.

- `<key>.csv` — 대구 항목 행만(TIME 시점, ITEM_NAME1~4 항목, DATA_VALUE 값, UNIT_NAME 단위). 값은 ECOS 그대로.
- `<key>.json` — 표 이름·통계표 코드·주기·기간·최근 시점·단위·출처 URL·분야(areas).
- `summary.md` — 표별 최근 시점·행 수.

키는 ECOS 인증키 하나(GitHub Secrets `ECOS_KEY`). 표를 더 받으려면 yml 에 항목을 추가하고 stat_code 를 적는다.
stat_code 를 모르면 워크플로를 `discover=true` 로 돌려 로그의 후보 목록(표 이름·코드·주기)에서 고르고, 코드를 적은 뒤 한 번 더 discover 로 '대구' 항목이 있는지 본다.
리포트 근거로 쓸 때는 `report_context.py` 의 "[한국은행 ECOS]" 항목을 보고, 출처는 json 의 source_url(ECOS 통계표 코드 포함)을 쓴다.
