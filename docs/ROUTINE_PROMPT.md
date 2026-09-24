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

## 월간 기업 DB 갱신 — 매월 3일 06:00
https://www.factoryon.go.kr/bbs/frtblRecsroomBbsList.do 에서 최신 월 "전국(개별,계획)입주업체현황" 과
"산단공관할단지내_입주업체리스트" 첨부를 내려받아 python3 scripts/import_factoryon.py <전국파일> <산단공파일> 을 실행한다.
변경 요약(신규 기업 수, 사라진 기업 수)을 커밋 메시지에 적고 푸시한다.

## 산업별 정책제안 리포트 — 격주 월요일 05:00
CLAUDE.md 원칙 준수. scripts/data/programs_*.csv, dalseong_companies.csv, match_daegu_national.csv,
최근 4주 측정 리포트(src/content/posts/ 태그 노출도·예산추적·공급망)를 읽고 시작한다.
docs/strategy/ 에 있는 산업별 전략 문서(대구 산업분야별 전략과 정책)를 기준 문서로 삼는다.

순환 산업(격주 1편, 이 순서로 반복): 1 미래모빌리티·자동차부품 → 2 로봇·피지컬AI(기계·금속가공) → 3 반도체·소부장
→ 4 전통제조 AX(섬유 포함) → 5 헬스케어·의료기기 → 6 AI·SW(ABB)·창업.
이번 회차 산업 = (이번 주 ISO 주 번호 ÷ 2) mod 6 (0이면 6). 지난 회차 같은 산업 리포트를 읽고 "그때 제안 중 무엇이 진행됐나"를 첫 절에 쓴다.

근거 수집(공개 자료만, 최근 8주): 글로벌(Reuters·Bloomberg·FT, 대표기업 IR, Gartner·McKinsey·BCG·Deloitte·IDC, SEMI·SIA·IFR·IEA,
해외 정부 발표) · 국내 연구(KEIT·KIAT·IITP·NIA·KISTEP·KIET·KDB·한국은행 지역경제보고서·국회예산정책처·대구정책연구원) ·
증권사 공개 리포트 · 정부·시 보도자료(산업부·과기부·중기부·국가AI전략위·대구시·대구TP·DIP·DMI) ·
내부 데이터(기업 사전: 해당 산업 기업 수·종사자·단지·규모 분포 — scripts/industry.py 로 계산, 사업 DB: 국비 사업·2026 예산·신규 여부, 대구시 매칭) ·
타 도시(광주·부산·창원·구미·울산 예산·공고·유치 실적).

리포트 구조(2,500~3,500자, 개조식+짧은 문단): frontmatter title("[정책제안] <산업>: <핵심 제안 한 줄>"), date, category: policy,
tags: [정책제안, <산업>], summary, description, faq 3개, draft: true, auto: true, sources: [{title,url,date}].
1 결론 먼저(제안 3개, 대상·수단·규모) → 2 지난 제안 점검(첫 회차 생략) → 3 현재 위치(기업 사전 숫자, 최근 8주 대구 신호) →
4 글로벌 변화와 대구 노출(사건 3~5개, "대구 기업 ○곳·○명 관련" 계산 근거) → 5 정부·타도시 움직임(국비 사업·시비 매칭·경쟁 도시 비교표 1개) →
6 연구기관·시장 시각(3~5편, 각 3줄, 다른 관점 포함) → 7 정책 제안(제안마다 문제·제안·근거·재원·대상 규모·지표; 시/정부 건의/기업·기관 구분, 특정 기업 지목·순위·평가 금지) →
8 반론(반대 근거 한 단락 + 틀릴 수 있는 이유 두 줄) → 9 출처(실제로 연 페이지만, 날짜순).

작성 규칙: 모든 문단에 숫자 하나 이상, 모든 숫자에 출처. "급성장·위기·획기적" 등 형용사 금지. 원문 수치·통화 그대로, 환산·추정 금지, 확인 안 되면 "미확인".
전략 문서와 어긋나는 제안이면 이유 명시(전략 문서 갱신 제안). 기업 사전 필터 결과는 실제 코드로 계산해 숫자와 조건을 함께 적는다.
페이지 원문을 열 수 없는 환경이면 검색 요지임을 글 첫머리와 각 수치에 표시한다.

저장: src/content/posts/YYYY-MM-DD-policy-<industry-slug>.md (draft:true), docs/strategy/proposals/<industry-slug>-YYYY-MM-DD.md 에 7절만.
커밋 "report: 정책제안 <산업> YYYY-MM-DD" 후 푸시. 완료 후 제목·제안 3줄·출처 수 출력.
산업 슬러그: mobility-auto-parts / robot-physical-ai / semiconductor / manufacturing-ax / healthcare / ai-sw-startup
