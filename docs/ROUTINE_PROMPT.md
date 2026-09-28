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
작성 세션은 아래 프롬프트를 그대로 받는다. 푸시되면 `.github/workflows/publish_reports.yml` 이 main 에 병합 → 브랜치에서 온 리포트마다 `review_report.py --gate` 를 돌려 FAIL 이면 `draft: true` 로 되돌림(운영자 지시 2026-09-28: 충분한 자료와 신뢰성이 있을 때만 발간) → 배포한다. 운영자는 `python3 scripts/approve.py` 로 초안을 직접 발행할 수도 있다.

### 작성 세션 프롬프트 (그대로 복사) — v3 정책 브리프(2026-09-29 부터)

저장소 a99621522-cell/dalgubul-ai-note. 이 세션의 지정 브랜치는 `claude/policy-reports` 다: `git fetch origin main && git checkout -B claude/policy-reports origin/main` 으로 main 에서 새로 만든다. main 에는 직접 푸시하지 않는다.
`.claude/agents/policy-brief.md` 의 지시를 그대로 따른다(에이전트 policy-brief 로 실행하거나, 그 파일 내용을 프롬프트로 삼는다): ① 분야 10개의 근거를 조사해 후보 주제 3개를 채점하고 7점 이상인 1개만 고른다(없으면 쓰지 않고 보고) ② 내부 자료와 WebSearch·WebFetch 로 충분히 조사해 조사 메모(docs/strategy/research/)를 만든 뒤 ③ 대구정책 브리프식 개조식(format: brief)으로 쓴다 ④ `python3 scripts/review_report.py --gate <파일>` 이 PASS 이고 자기 검토 5항목이 모두 예일 때만 `draft: false`, 아니면 초안으로 둔다(운영자 지시 2026-09-28: 충분한 자료와 신뢰성이 있을 때만 발간).
논리 규칙(운영자 지시 2026-09-28): 주장마다 근거 1개(근거 없는 주장은 쓰지 않음) / 제안 수치는 계산식·출처가 있을 때만, 없으면 "N 은 조사 뒤 정함" / 공장등록 키워드 집계는 '품목 등록 기업 수' 로만(역량·수요 근거 금지) / 원인 문장에도 출처 / 전제가 미확인이면 정책 제안이 아니라 '조사 제안' 1개만 / 제안은 근거가 받쳐 주는 만큼만 0~3개 / 출처 5건 이상, 그중 공식 자료 2건 이상 / 2,000~6,000자.
끝에 `npm run build` 를 통과시키고 한 커밋("brief: <제목> YYYY-MM-DD", 끝에 "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" 줄)으로 `git push -u origin claude/policy-reports --force-with-lease`. 워크플로 publish_reports.yml 이 main 에 병합하고 --gate 를 다시 돌려 FAIL 이면 draft 로 되돌린다. 마지막 출력에 고른 주제와 채점표, 검사 결과, 발행 여부와 사유, 출처 수, 확인 못 한 것을 적는다. 푸시가 거부되면 오류 메시지를 그대로 적는다.

(v2 인사이트 리포트 형식·v1 1~9절 형식은 2026-09-28 까지의 초안에만 남아 있다. 사양은 git 이력 참고. 2026-09-28 운영자 지적: 말투가 어색하고 논리가 맞지 않음 — 측정한 것과 주장이 다름, 확인 안 된 전제, 근거 없는 원인, 도출 없는 제안 수치, 잣대 혼용, 병목과 제안 불일치.)

## 참고자료 창고 갱신 — 매주 월 06:19 KST (Claude 루틴 "참고자료 창고 갱신", 운영 세션을 깨움)

운영 세션(Google Drive 커넥터가 붙어 있는 세션)에 다음 메시지가 온다. 자식 세션은 Drive 커넥터가 없고 지정 브랜치 없이는 푸시가 막히므로 운영 세션이 직접 한다.

```
참고자료 창고 갱신 시각이다. Google Drive 에서 폴더 「DAITDA」(id 1ugUlvYhcH4wsdUGentTTYCaMpl1yYB5t, search_files: parentId = '1ugUlvYhcH4wsdUGentTTYCaMpl1yYB5t')를 찾고, 그 안에서 지난 7일 안에 추가·수정된 파일을 찾는다(폴더가 없으면 list_recent_files 로 최근 7일 파일 중 보고서·통계로 보이는 것). 이미 data/refs/*.json 에 drive_id 가 있는 파일은 건너뛴다.
파일마다: 10MB 이하 PDF·HWP·HWPX·DOCX·XLSX 는 read_file_content 로 읽고 data/refs/README.md 형식으로 data/refs/<slug>.json 요약을 쓴다(작성자 문장, 수치는 쪽 번호와 함께, 평가 없음, 개인정보 없음). 공개 페이지(PRISM·기관 누리집)를 검색해 public_url 을 채운다. 10MB 초과·스캔본(글자 없음)·비공개로 보이는 파일은 read_status: skipped 와 사유만 적는다.
python3 scripts/refs.py --check 를 통과시킨 뒤 "refs: 참고자료 N건 요약 YYYY-MM-DD" 로 커밋, 지정 브랜치에 푸시, PR 을 열어 병합한다. 새 파일이 없으면 아무것도 하지 않는다. 끝나면 요약한 파일 제목과 건너뛴 파일(사유)을 사용자에게 알린다.
```
