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
제목이 선정 결과·최종 선정·합격자 발표·선정 기업 명단인 글은 본문·첨부 표에서 기업명만 뽑아
scripts/data/support/inst-YYYYMMDD.csv 에 저장한다(열: 기업명, 선정연도=게시일 연도, 지원기관=기관명, 사업명=공고 제목,
구분=기관, 지원유형=선정, 출처="기관명 홈페이지 공고", 출처URL, 기준일=게시일; 형식은 그 폴더 README).
기관·대학·병원은 넣지 않고 대표자·연락처는 읽지 않는다. 저장했으면 python3 scripts/import_support.py 를 실행해 support_history.csv 에 합친다.
공공기관 사이트만, 개인정보 없는 글만, 기관당 요청 20건 이내.
0건인 기관이 있으면 커밋 메시지에 "[구조 변경 의심] 기관명" 을 적는다.
완료 후 "chore: 주간 기관 공고 수집 YYYY-MM-DD" 로 커밋·푸시한다(선정 결과가 있으면 support_history.csv 도 함께).

## 월간 기업 DB 갱신 — 매월 3일 06:00
https://www.factoryon.go.kr/bbs/frtblRecsroomBbsList.do 에서 최신 월 "전국(개별,계획)입주업체현황" 과
"산단공관할단지내_입주업체리스트" 첨부를 내려받아 python3 scripts/import_factoryon.py <전국파일> <산단공파일> 을 실행한다.
변경 요약(신규 기업 수, 사라진 기업 수)을 커밋 메시지에 적고 푸시한다.

## 산업별 정책제안 리포트 — 평일 매일 05:00, 분야마다 주 1편 (Claude 루틴 "산업별 정책제안 리포트")
분야 10개 모두 매주 1편씩(주 10편). 평일에 2개 분야씩: 월 미래모빌리티·자동차부품, 로봇·피지컬AI / 화 반도체·소부장, 전통제조 AX / 수 헬스케어·의료기기, AI·SW·창업 / 목 기계, 자동차 / 금 섬유, 뿌리산업 (config/pledge_areas.yml weekday_plan). `python3 scripts/report_context.py` 가 오늘 분야를 모두 출력한다. 같은 기업군을 두 분야가 나눠 보는 경우(자동차 ↔ 미래모빌리티, 기계 ↔ 로봇·뿌리, 섬유 ↔ 전통제조 AX)는 각 분야의 `focus` 관점으로 쓴다. 지난 회차 같은 분야 = 1주 전.
CLAUDE.md 원칙 준수(정책 평가·비판, 기관 입장으로 읽힐 표현, 비공개 자료 인용 금지. 공약 이행 여부를 점수화·평가하지 않고 발표·예산·공고 사실만 적는다).
1. `python3 scripts/report_context.py` 를 실행해 이번 주 분야(config/pledge_areas.yml, ISO 주 번호로 순환)와 코드로 센 숫자를 받는다.
   기업 사전(연결 산업 그룹의 기업 수·고용·규모·단지·입지 유형), 사업 DB(키워드 일치 국비 사업·2026 예산·신규), 대구시 매칭,
   지원사업 수혜 이력(최근 3년 기업 수·기관별·사업별), 최근 8주 공고 데이터(data/notices, 타 기관 동향), 최근 8주 글이 나온다.
   분야에 산업 그룹이 없으면 태그·입지 유형(창업: 설립 7년 이내·창경센터 보육·벤처 태그)으로 세고, 그것도 없으면 사업 DB·예산·공고 숫자만 쓴다.
2. config/pledge_areas.yml 의 pledges(공약 항목 원문)와 pledge_of·source_url 을 읽는다. 비어 있으면 리포트 첫머리에 "공약 항목 미입력"이라 적고 분야 이름만으로 쓴다.
3. docs/strategy/ 의 전략 문서와 지난 회차 같은 분야 리포트(src/content/posts/*-policy-<key>.md)를 읽고 "그때 제안 중 무엇이 진행됐나"를 사실만으로 첫 절에 쓴다(첫 회차는 생략).

근거 수집(공개 자료만, 최근 8주): 글로벌(Reuters·Bloomberg·FT, 대표기업 IR, Gartner·McKinsey·BCG·Deloitte·IDC, SEMI·SIA·IFR·IEA, 해외 정부 발표) ·
국내 연구(KEIT·KIAT·IITP·NIA·KISTEP·KIET·KDB·한국은행 지역경제보고서·국회예산정책처·대구정책연구원) · 증권사 공개 리포트 ·
정부·시 보도자료(관계 부처·국가AI전략위·대구시·대구TP·DIP·DMI) · 타 도시(광주·부산·창원·구미·울산의 같은 분야 예산·공고·유치 실적).
기관 발간물은 먼저 data/research/(scripts/fetch_research.py 가 매주 받은 제목·링크·날짜·요약)에서 고른다 — report_context.py 가 키워드 일치 항목을 출력하고 `python3 scripts/fetch_research.py --query <키워드>` 로 더 찾는다. 여기서 나온 항목은 날짜·링크가 확인된 것이므로 sources 에 그대로 쓴다. 페이지 원문을 열 수 없는 환경이면 검색 요지임을 글 첫머리와 각 수치에 "요지"로 표시한다.

리포트 구조(2,500~3,500자, 개조식+짧은 문단): frontmatter title("[정책제안] <분야>: <핵심 제안 한 줄>"), date, category: policy,
tags: [정책제안, <분야>], summary, description(핵심 문장), faq 3개(본문 근거만), draft: true, auto: true, sources: [{title,url,date}].
1 결론 먼저(제안 3개, 각 문장에 대상·수단·규모) → 2 지난 제안 점검(첫 회차 생략) → 3 현재 위치(공약 항목 목록, 관련 기업 사전 숫자, 최근 8주 대구 신호) →
4 글로벌 변화와 대구 노출(사건 3~5개, "대구 기업 ○곳·○명 관련" 계산 근거) → 5 정부·타도시 움직임(국비 사업·시비 매칭·경쟁 도시 비교표 1개) →
6 연구기관·시장 시각(3~5편, 각 3줄, 다른 관점 포함) → 7 정책 제안(제안마다 문제·제안·근거·재원·대상 규모·지표. 시가 할 것 / 정부에 건의할 것 / 기업·기관이 할 것 구분.
어느 공약 항목과 이어지는지 명시. 특정 기업 지목·순위·평가 금지) → 8 반론(반대 근거 한 단락 + 틀릴 수 있는 이유 두 줄) → 9 출처(외부 출처는 frontmatter sources 에 넣으면 글 아래 "출처" 목록으로 자동 표시된다. 9절 본문에는 건수·확인 상태와 내부 근거 파일 이름을 적는다).

작성 규칙: 모든 문단에 숫자 하나 이상, 모든 숫자에 출처. "급성장·위기·획기적" 등 형용사 금지. 원문 수치·통화 그대로, 환산·추정 금지, 확인 안 되면 "미확인".
전략 문서와 어긋나는 제안이면 이유 명시(전략 문서 갱신 제안). 기업 사전 필터 결과는 report_context.py 값과 조건을 그대로 적는다.

저장: src/content/posts/YYYY-MM-DD-policy-<key>.md, docs/strategy/proposals/<key>-YYYY-MM-DD.md 에 7절만.
감수·발행(운영자 지시 2026-09-25, 자동 발행): `python3 scripts/review_report.py <파일>` 이 통과할 때까지 고친다(최대 3회). 이어서 자기 검토 — 모든 숫자가 출처와 맞는지, 검색 요지는 "요지" 표시가 있는지, 평가·비판·기관 입장 표현이 없는지, 특정 기업을 지목·순위화하지 않았는지, 지난주와 같은 제안을 되풀이하지 않았는지. 둘 다 통과하면 `draft: false` 로 바꿔 발행하고, 하나라도 못 넘으면 `draft: true` 로 두고 사유를 출력한다.
커밋 "report: 정책제안 <분야> YYYY-MM-DD" 후 푸시. 완료 후 제목·제안 3줄·출처 수 출력.
분야 10개(config/pledge_areas.yml 순서): mobility / robot-physical-ai / semiconductor / manufacturing-ax / healthcare / ai-sw-startup / machinery / automotive / textile / root
