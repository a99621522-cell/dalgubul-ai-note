# 달구벌 AI 노트 — 시스템 설계 (2026-09-21)

## 목적
대구·달성 기업이 "지금 받을 수 있는 지원"을 알 수 있게 한다. 부처 예산 → 대구시 매칭 → 수행기관 공고 → 기업, 4층을 한 DB로 잇는다.
블로그(정보 공개)와 앱(기업별 추천)이 같은 DB를 쓴다. 비영리, 공개 자료만, 평가·순위 없음.

## 4층 데이터
| 층 | 소스 | 주기 | 방식 |
|---|---|---|---|
| 1 국비 | 부처 사업설명자료(산업·중기·과기·국토·고용·행안), 열린재정 | 연 1회 | PDF 파서 `scripts/parse_budget.py`, 열린재정 API |
| 1 공고 | 기업마당 API, IRIS, K-Startup, 소상공인24, 고용24, 정책브리핑 RSS, 나라장터 API | 매일 | `collect.py` (Actions) |
| 2 시·군 | 대구시 예산서, 대구시·달성군 보도자료·고시공고, 시의회 | 연 1회 / 매일 | PDF 파서 / 게시판 스크랩 |
| 3 수행기관 | 대구 지역 기관 12곳 공고 게시판, 연 1회 통합안내서 | 주 1회 | Claude Code 루틴 → `scripts/inbox/*.json` |
| 4 기업 | 팩토리온(월), 벤처확인(월), DART·네이버뉴스(일), KIPRIS(월) | 월/일 | `import_factoryon.py`, `collect.py` |

전국 수행기관은 통합 창구 6곳(기업마당·IRIS·K-Startup·소상공인24·고용24·나라장터)으로 덮고, 직접 수집은 `scripts/data/institutions.yml`의 대구 기관만. 새 기관은 예산서 파서의 '수행기관' 필드에서 자동 제안.

## 자동화 층
- GitHub Actions (매일 05:30): `collect.py` — API·RSS·게시판 → 선별 → Gemini 요약·SEO·FAQ → `draft: true` 초안
- Claude Code 루틴 (주 1회 월요일): institutions.yml 게시판 순회, 첨부 PDF·HWP 본문 추출 → inbox JSON → 커밋. 깨진 소스는 커밋 메시지에 "구조 변경 의심" 표기
- 루틴 (월 1회): 팩토리온 최신 엑셀 내려받아 `import_factoryon.py`
- 루틴 (연 1회, 1~2월): 사업설명자료·대구시 예산서·기관 통합안내서 파싱
- 사람: 초안 승인(하루 5분), 깨진 소스 확인

## 사업 DB 스키마 (`scripts/data/programs.csv`, 파서 산출)
id, layer(national/city/agency), ministry, program_code, name, executor, budget_2025, budget_2026, funding(국/균/시/채), target(기업/대학/개인/지자체), conditions, region_scope, schedule, deadline, source_url, matched_city_item, matched_national_code, as_of

## 앱 MVP (블로그와 별도 화면, 같은 DB)
- 입력: 회사명(기업 DB 자동완성) 또는 업종·규모·필요(자금/인력/기술/판로/규제)
- 처리: 규칙 필터(지역·업종·규모·창업연차) → 임베딩 검색 → Gemini 요약 (원문 링크·마감 필수, "가능성 있음 — 공고 ○항 확인" 표현)
- 범위: 대구, 사업 300~500건, 질문 5종, 로그인·알림 없음
- 스택: Cloudflare Pages(화면) + Render(중계, Gemini 키 보관, 일일 상한) + SQLite/CSV DB
- 이후: 모의심사 앱과 연결(찾기 → 심사 → 수정 → 발표)

## 원칙 (CLAUDE.md와 동일)
공개 자료만 · 출처·기준일 표기 · 평가·비판 없음 · 전수 원칙 · 연락처·개인정보 미저장 · 약관 금지 사이트 제외 · 하루 1회 · 기업 애로 접수는 군 공식 창구(AI 정부 실험실 과제)로

## 순서
1. 저장소 GitHub 올리기 → Cloudflare 배포 → Actions 첫 실행 (사용자)
2. 사업설명자료·대구시 예산서 파서 → programs.csv (Claude)
3. institutions.yml 게시판 주소 확정 → 주간 루틴 등록 (루틴이 주소 탐색, 사용자가 등록 버튼)
4. IRIS·K-Startup·소상공인24·고용24 게시판 소스 추가 (Claude)
5. 네이버 뉴스·DART 키 발급 → 기업 페이지 타임라인 (사용자 키, Claude 코드)
6. 앱 MVP (Claude)
