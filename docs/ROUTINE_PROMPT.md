# Claude Code 루틴 프롬프트 (복사해서 등록)

## 주간 기관 공고 수집 — 매주 월요일 06:00
CLAUDE.md를 읽고 원칙을 지킨다. scripts/data/institutions.yml 의 institutions 를 순회한다.
blocked / unverified 항목은 건드리지 않는다. blocked 는 제공기관이 robots.txt 로 막았거나
서비스를 거둬들인 곳이므로 우회하지 않는다.
board_url 이 비어 있으면 home 에서 '사업공고/공지/모집' 게시판을 찾아 board_url 을 채우고 파일을 갱신한다.
새로 찾은 주소는 읽기 전에 그 호스트의 robots.txt 를 확인한다. 차단 경로면 수집하지 말고
institutions.yml 의 blocked 로 옮기고 reason 을 적는다.
각 기관 note 의 수집 방식 주의사항(JS 렌더링, POST 조회, javascript: 링크 등)을 먼저 읽는다.
대구테크노파크는 TLS 중간 인증서가 누락돼 있어 requests 로 받을 때 verify 에
scripts/data/ca-extra.pem 을 certifi 번들과 합쳐 넘겨야 한다.
각 게시판에서 지난 7일 새 공고를 읽어 scripts/inbox/weekly-YYYYMMDD.json 에 저장한다
(title, url, source=기관명, category, deadline(YYYY-MM-DD, 없으면 null), body=본문 300자 요약).
첨부 PDF/HWP/HWPX 가 있으면 열어 대상·규모·기간을 body 에 포함한다.
공공기관 사이트만, 개인정보 없는 글만, 기관당 요청 20건 이내.
0건인 기관이 있으면 커밋 메시지에 "[구조 변경 의심] 기관명" 을 적는다.
완료 후 "chore: 주간 기관 공고 수집 YYYY-MM-DD" 로 커밋·푸시한다.

## 주간 선정 공고 수집 (JS 게시판) — 매주 월요일 06:30
CLAUDE.md를 읽고 원칙을 지킨다. scripts/config/award_sources.yml 에서 status 가 js 인 기관만 순회한다
(대구시·대구TP·DMI·KIRIA·KTDI·KOTMI·DGDP·중진공·산단공 — requests 로는 빈 페이지라 브라우저로만 읽힌다).
blocked 기관은 robots.txt 가 막은 곳이므로 열지 않는다. 새 게시판 주소를 찾으면 그 호스트의 robots.txt 를 먼저 본다.
각 기관 공지·사업공고 게시판에서 제목에 선정·결과·확정·발표·명단이 들어간 지난 7일(첫 실행은 1년) 게시글을 열어
scripts/inbox/awards-YYYYMMDD.json 에 저장한다: [{"title","url","org"=기관명,"abbr"=약칭(yml 의 abbr),"date"(YYYY-MM-DD),"body"=본문 텍스트(첨부 PDF 본문 포함, HWP 는 생략)}]
기업명 추출은 하지 않는다(collect_awards_notices.py 가 Gemini 로 한다). 대표자·연락처는 body 에서 지운다.
기관당 20건 이내, 이미 scripts/state/seen_notices.json 에 있는 URL 은 건너뛴다.
완료 후 "chore: 주간 선정 공고 수집 YYYY-MM-DD" 로 커밋·푸시한다. 0건인 기관은 커밋 메시지에 "[구조 변경 의심] 기관명" 을 적는다.

## 월간 기업 DB 갱신 — 매월 3일 06:00
https://www.factoryon.go.kr/bbs/frtblRecsroomBbsList.do 에서 최신 월 "전국(개별,계획)입주업체현황" 과
"산단공관할단지내_입주업체리스트" 첨부를 내려받아 python3 scripts/import_factoryon.py <전국파일> <산단공파일> 을 실행한다.
변경 요약(신규 기업 수, 사라진 기업 수)을 커밋 메시지에 적고 푸시한다.
