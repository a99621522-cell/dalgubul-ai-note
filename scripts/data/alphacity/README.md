# alphacity — 수성알파시티 기업현황 저장 페이지 투입구

alphacity.or.kr 입주현황 > 기업현황(boardList?type=1)을 브라우저에서 "웹페이지, 단일 파일(.mht)" 또는 HTML 로 저장해 여기에 둔다(쪽마다 1개, 32쪽이면 32개).
`python3 scripts/import_alphacity.py --import` 가 읽어 `scripts/data/extra/alphacity.csv` 로 만들고 기업 DB 에 반영한다.
저장 파일은 커밋하지 않는다(.gitignore). 네트워크가 되는 곳에서는 `--fetch` 로 전부 받을 수 있다(워크플로 alphacity.yml).
대표자 열은 읽지 않는다.
