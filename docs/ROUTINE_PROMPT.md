# Claude Code 루틴 프롬프트 (복사해서 등록)

## 주간 기관 공고 수집 — 매주 월요일 06:00
CLAUDE.md를 읽고 원칙을 지킨다. scripts/data/institutions.yml 의 institutions 를 순회한다.
board_url 이 비어 있으면 home 에서 '사업공고/공지/모집' 게시판을 찾아 board_url 을 채우고 파일을 갱신한다.
각 게시판에서 지난 7일 새 공고를 읽어 scripts/inbox/weekly-YYYYMMDD.json 에 저장한다
(title, url, source=기관명, category, deadline(YYYY-MM-DD, 없으면 null), body=본문 300자 요약).
첨부 PDF/HWP/HWPX 가 있으면 열어 대상·규모·기간을 body 에 포함한다.
공공기관 사이트만, 개인정보 없는 글만, 기관당 요청 20건 이내.
0건인 기관이 있으면 커밋 메시지에 "[구조 변경 의심] 기관명" 을 적는다.
완료 후 "chore: 주간 기관 공고 수집 YYYY-MM-DD" 로 커밋·푸시한다.

## 월간 기업 DB 갱신 — 매월 3일 06:00
https://www.factoryon.go.kr/bbs/frtblRecsroomBbsList.do 에서 최신 월 "전국(개별,계획)입주업체현황" 과
"산단공관할단지내_입주업체리스트" 첨부를 내려받아 python3 scripts/import_factoryon.py <전국파일> <산단공파일> 을 실행한다.
변경 요약(신규 기업 수, 사라진 기업 수)을 커밋 메시지에 적고 푸시한다.
