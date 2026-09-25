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

## 산업별 정책제안 리포트 — 평일 04:53, 분야마다 주 1편 (Claude 루틴 "산업별 정책제안 리포트")

실행 구조(2026-09-26 확정): 루틴은 운영 세션을 깨우고, 운영 세션이 `create_session(source main, outcome_branch: claude/policy-reports)` 으로
작성 세션을 만든다. 루틴이 직접 만든 세션은 지정 브랜치가 없어 `git push` 가 승인 대기로 막히므로(시험 2회 확인) 이 구조를 쓴다.
작성 세션은 아래 프롬프트를 그대로 받는다. 푸시되면 `.github/workflows/publish_reports.yml` 이 main 에 병합 → 발행본 재검사(미달은 draft) → 배포한다.

### 작성 세션 프롬프트 (그대로 복사)

저장소 a99621522-cell/dalgubul-ai-note. 이 세션의 지정 브랜치는 `claude/policy-reports` 다: `git fetch origin main && git checkout -B claude/policy-reports origin/main` 으로 main 에서 새로 만든다. main 에는 직접 푸시하지 않는다. 끝에 `git push -u origin claude/policy-reports --force-with-lease` 로 푸시하면 워크플로 publish_reports.yml 이 main 에 병합·재검사·배포한다. 푸시가 거부되면 오류 메시지를 마지막 출력에 그대로 적는다.

CLAUDE.md 원칙을 지킨다(공무원용, 정책 평가·비판 없음, 공개 자료만, 특정 기업 지목·순위·평가 금지). 리포트는 운영자 지시(2026-09-25)로 **검사와 자기 검토를 통과하면 자동 발행(draft: false)** 한다. 너는 작성자이자 감수자다 — 품질이 기준에 못 미치면 발행하지 않는다.
**정책제안서이므로 예산을 참조하지 않는다: 예산액(국비·시비·지방비 금액), 사업코드(NNNN-NNN), 예산서·사업설명자료·세출예산·대구시 예산 매칭을 본문·제목·요약에 쓰지 않는다. 정부·시 사업은 사업명과 신규 여부, 기간만 쓴다. "재원" 항목은 없다.**

분야 10개 모두 매주 1편씩(주 10편). 평일마다 2개 분야: 월 미래모빌리티·자동차부품 + 로봇·피지컬AI / 화 반도체·소부장 + 전통제조 AX(섬유 포함) / 수 헬스케어·의료기기 + AI·SW·창업 / 목 기계 + 자동차 / 금 섬유 + 뿌리산업 (config/pledge_areas.yml weekday_plan).
먼저 `python3 scripts/report_context.py` 를 실행한다(요일이 따로 지정돼 있으면 `--weekday N`). 분야 2개와 분야별 근거(기업 사전 숫자: 기업·고용·규모·단지·입지·세분류·sub_counts / 정부 사업: 사업명·부처·신규 여부 / 대구시가 함께 추진하는 사업명 / 지원 이력 3년 / 최근 8주 글 / 기관 발간물 최근 70일)가 차례로 나오므로 그 값을 그대로 쓴다. **분야 2개 각각에 대해 아래 사양의 리포트를 한 편씩 쓴다.** 같은 기업군을 두 분야가 나눠 보는 경우(자동차 ↔ 미래모빌리티·자동차부품, 기계 ↔ 로봇·뿌리산업, 섬유 ↔ 전통제조 AX)는 출력의 "관점:" 줄(focus)에 맞춰 쓴다. 지난 회차 같은 분야 = 1주 전 리포트(src/content/posts/*-policy-<key>*.md, 제안 요약 docs/strategy/proposals/<key>-*.md). 없으면 첫 회차다. 추가 필터가 필요하면 기업 사전(scripts/sites.py 의 load_all_companies, scripts/industry.py 의 classify)을 코드로 돌려 숫자와 조건을 함께 적는다.

근거의 우선순위
1. 기관 발간물 창고 data/research/ — report_context 출력의 "[기관 발간물]" 항목과 `python3 scripts/fetch_research.py --query <키워드1> <키워드2>` 로 찾는다. 날짜·링크가 확인된 것이므로 sources 에 그대로 넣고 본문에 "요지" 표시 없이 제목·날짜를 밝혀 인용한다(요약 300자 범위 안에서만 수치를 쓰고, 요약에 없는 수치는 만들지 않는다). data/research/summary.md 에 접속 결과표.
2. WebSearch — 창고에 없는 사건·수치를 보충한다. 외부 페이지 열기(WebFetch)가 막혀 있어 검색 결과 요지만 쓸 수 있으므로 그런 수치는 본문에 "요지"로 표시하고, sources 의 date 가 불명확하면 "미확인". 검색은 분야마다 최소 6회(글로벌·국내 연구·증권사·정부·대구시·타도시).
3. 내부 데이터(기업 사전·정부 사업명·대구시 사업명)는 report_context 값 그대로.
**최신성(운영자 지시 2026-09-26: 옛 자료로 정책 제안을 쓰지 않는다)**: 출처마다 발행일(YYYY-MM-DD, 적어도 YYYY-MM)을 확인해 적는다. 검색 결과에서 날짜를 확인할 수 없는 자료는 출처에 넣지 않고 그 수치도 쓰지 않는다("미확인" 날짜 금지). 리포트 날짜 기준 1년보다 오래된 자료는 쓰지 않는다(통계 기준연도가 오래된 실태조사·기본계획도 발행일이 1년 안일 때만). 출처의 60% 이상은 최근 120일 안 자료로 하고, 4·5절의 사건·정책은 최근 8주 안 것만 쓴다. 검사기(review_report.py)가 날짜 미확인·1년 초과를 오류로 본다.

감수·발행 절차(편마다)
1. 초안을 `draft: true` 로 저장한 뒤 `python3 scripts/review_report.py <파일>` 을 돌린다. 오류(✗)가 있으면 고치고 다시(최대 3회). 경고(△)도 가능하면 고친다. 본문 길이 2,500~3,500자를 지킨다(경고 대상).
2. 자기 검토: 모든 숫자가 report_context·data/research·sources 와 맞는가(만든 숫자·환산·추정 없음) / 검색 요지 수치마다 "요지" 표시 / 예산액·사업코드·예산서 인용 없음 / 정책 평가·비판, 기관 입장 표현, 특정 기업 지목·순위·추천 없음 / 7절 제안 3개가 서로 다른 주체(시 / 정부 건의 / 기업·기관)이고 다섯 항목이 숫자로 채워졌는가, 지난주 제안의 단순 반복이 아닌가 / 제목이 "[정책제안] <분야>: <핵심 제안 한 줄>", description 은 결론 먼저 한 문장.
3. 1·2 를 모두 통과하면 `draft: false`. 하나라도 못 넘으면 `draft: true` 로 두고 마지막 출력에 사유를 적는다.
4. 두 편을 다 처리한 뒤 `npm run build` 통과를 확인하고 한 커밋(메시지 "report: 정책제안 <산업1>·<산업2> YYYY-MM-DD", 끝에 "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" 줄)으로 만들어 푸시한다. 발행할 편이 없어도 초안은 푸시한다.

리포트 구조(2,500~3,500자, 개조식+짧은 문단, Markdown)
frontmatter: title("[정책제안] <산업>: <핵심 제안 한 줄>"), date, category: policy, tags: [정책제안, <산업>], summary, description, faq 3개, auto: true, sources: [{title,url,date}] (8건 이상 — 글 페이지 아래 "출처" 목록으로 자동 표시)
1 결론 먼저(제안 3개, 각 한 문장에 대상·수단·규모) → 2 지난 제안 점검(1주 전 리포트의 제안이 공고·시 발표·기관 사업에 반영됐는지 사실만, 첫 회차 생략, 변화 없으면 "변화 없음"과 확인 자료 이름·건수) → 3 현재 위치(기업 사전 숫자: 기업·고용·전국 비중·규모 분포·단지, 최근 8주 대구 신호) → 4 글로벌 변화와 대구 노출(사건 3~5개, 각각 "대구 기업 ○곳·○명이 직접 관련(계산 근거)") → 5 정부·타도시 움직임(정부 사업 사업명·신규 여부·일정, 대구시 추진 사업, 경쟁 도시 비교표 1개, 예산액 없이) → 6 연구기관·시장 시각(3~5편 요지 각 3줄, 다른 관점 포함, 기관 발간물 창고 우선) → 7 정책 제안("### 제안 N (시)" / "### 제안 N (정부 건의)" / "### 제안 N (기업·기관)", 제안마다 "- 문제:" "- 제안:" "- 근거:" "- 대상 규모:" "- 지표:" 다섯 항목을 숫자로, 대상 규모는 기업 사전 필터 결과 '○곳'과 조건) → 8 반론(반대 근거 한 단락 + 틀릴 수 있는 이유 두 줄) → 9 출처("외부 출처 N건은 이 글 아래 '출처' 목록에 링크로 있다", 확인 상태: 기관 발간물 N건 날짜·링크 확인 / 검색 요지 N건 원문 대조 필요, 내부 근거 파일 이름과 기업 사전 기준월).

작성 규칙: 모든 문단에 숫자 하나 이상, 모든 숫자에 출처. "급성장·위기·획기적" 등 형용사 금지. 원문 수치·통화 그대로, 환산·추정 금지, 확인 안 되면 "미확인". 예산액·사업코드·예산서 인용 금지. docs/strategy/ 전략 문서와 어긋나는 제안이면 이유 명시(전략 문서 갱신 제안).

저장: src/content/posts/YYYY-MM-DD-policy-<key>.md (key 는 config/pledge_areas.yml: mobility / robot-physical-ai / semiconductor / manufacturing-ax / healthcare / ai-sw-startup / machinery / automotive / textile / root), docs/strategy/proposals/<key>-YYYY-MM-DD.md 에 7절만. 완료 후 편마다 제목·제안 3줄·출처 수·발행 여부(발행/보류 사유)와 푸시 결과(성공 또는 오류 메시지 원문)를 출력한다.
