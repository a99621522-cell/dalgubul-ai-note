# 통계청 KOSIS 통계표 (data/kosis)

`config/kosis_tables.yml` 의 표를 `scripts/fetch_kosis.py`(워크플로 `kosis.yml`, 매월 9일)가 KOSIS 공유서비스에서 받아 여기에 둔다.

- `<key>.csv` — 대구 행만(PRD_DE 기간, ITM_NM 항목, C1~C4_NM 분류, DT 값, UNIT_NM 단위). 값은 KOSIS 그대로.
- `<key>.json` — 표 이름·orgId·tblId·기간·최근 시점·단위·출처 URL(kosis.kr statHtml)·분야(areas).
- `summary.md` — 표별 최근 시점·행 수.

키는 KOSIS 인증키 하나(GitHub Secrets `KOSIS_KEY`). 표를 더 받으려면 yml 에 항목을 추가하고 tblId 를 적는다.
tblId 를 모르면 워크플로를 `discover=true` 로 돌려 로그의 후보 목록에서 고른다.
리포트 근거로 쓸 때는 `report_context.py` 의 "[통계청 KOSIS]" 항목(분야 areas 가 맞는 표의 최근 시점 값)을 보고, 출처는 json 의 source_url 을 쓴다.
공표 시차가 1~2년인 연간 통계는 리포트 검사기의 출처 최신성 규칙에서 '발표일' 기준으로 본다.
