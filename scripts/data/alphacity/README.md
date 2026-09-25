# alphacity — 수성알파시티 기업현황 저장 페이지 투입구

alphacity.or.kr 입주현황 > 기업현황(boardList?type=1)을 브라우저에서 "웹페이지, 단일 파일(.mht)" 또는 HTML 로 저장해 여기에 둔다(쪽마다 1개, 32쪽이면 32개).
`python3 scripts/import_alphacity.py --import` 가 읽어 `scripts/data/extra/alphacity.csv` 로 만들고 기업 DB 에 반영한다.
저장 파일은 커밋하지 않는다(.gitignore). 네트워크가 되는 곳에서는 `--fetch` 로 전부 받을 수 있다(워크플로 alphacity.yml).
대표자 열은 읽지 않는다.

미국 GitHub 러너에서는 alphacity.or.kr 이 HTTP 403(해외 차단)이라 워크플로 `alphacity.yml` 은 수동 실행용이고, 실제 갱신은 국내 PC 에서 `--fetch --import` 또는 저장 페이지로 한다(2026-09-25 확인).
