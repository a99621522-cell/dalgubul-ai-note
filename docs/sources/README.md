# docs/sources — 원문 보고서 보관

파서가 읽는 공개 보고서 원문. 기관이 홈페이지에 공개한 파일만 두고, 파일명은 `<기관>_<주제>_<발행연월>.pdf`.

| 파일 | 출처 | 발행 | 쓰는 곳 |
|---|---|---|---|
| bok_regional_io_2020.pdf | 한국은행 「2020년 지역산업연관표」(2026-06, 경제통계2국). 운영자 Drive DAITDA 폴더에서 `drive_file.yml` 로 받음 | 2026-06 | 대구 표 V-2-11(80쪽) → `scripts/data/bok_io_daegu_sectors.csv`(산출액·부가가치·부가가치율), 전체 계수는 `bok_io_daegu.json` |
| bok_supplychain_2026-07.pdf | 한국은행 「우리나라 주요 제조업 생산 및 공급망 지도」(2026), bok.or.kr 〉 조사·연구 〉 간행물 〉 기타. 저작권 한국은행, ISBN 979-11-5538-655-2 | 2026-07-27 | `scripts/parse_bok_map.py` → `scripts/data/bok_dependency.csv`·`bok_multipliers.csv`·`bok_region.csv` |

10MB 를 넘는 Drive 파일은 워크플로 `drive_file.yml`(파일 id·저장 경로 입력)로 러너가 받아 여기에 커밋한다.
