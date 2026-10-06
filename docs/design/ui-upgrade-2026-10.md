# 다잇다 디자인·UI 개선 — 감사·IA·토큰·구현 기록 (2026-10-06, docs/prompts/site_design_ui.md 실행)

## 1. 휴리스틱 감사(요약)

| 심각도 | 위치 | 문제(측정) | 휴리스틱·기준 | 조치 |
|---|---|---|---|---|
| Critical | 헤더(모바일 390px) | 1단 메뉴 10개가 3줄로 줄바꿈, 헤더 높이 약 190px(뷰포트의 22%) | 인지 부하·thumb zone, WCAG 1.4.10 | 묶음 4개(현황·통계 / 기업 / 사업·리포트 / 성장 계산기) + 데스크톱 펼침, 모바일 드로어(「메뉴」 라벨), 헤더 56px |
| Critical | 첫 화면 리포트 회전 카드 | 6초 자동 넘김(일시정지 버튼은 있음) | WCAG 2.2.2 일시정지·정지·숨김 | 자동 넘김을 기본 꺼짐으로, 누를 때만 시작 |
| Major | 첫 화면 | 섹션 9개가 같은 시각 무게, 핵심 행동(검색) 뒤에 '600건' 카운터만 CTA | 시각적 위계, F 패턴 | 검색 아래 진입 타일 3개(기업 찾기·통계 보기·사업 찾기, 건수 포함)로 바꿈 |
| Major | 기업 사전 필터 | 적용된 조건이 셀렉트 안에만 보이고 초기화·빈 상태 없음 | 시스템 상태 가시성, 사용자 통제 | 적용 필터 칩(× 로 하나씩 지움)·모두 지우기·결과 0 안내 |
| Major | 넓은 표(상장기업 25열 등) | 가로 스크롤 때 첫 열(회사명)이 사라짐, 숫자 폭 가변 | 데이터 밀도·식별 | 가로 스크롤 표의 첫 열 sticky, `tabular-nums`, 행 호버, 표 행간 1.4 |
| Minor | 토큰 | 브레이크포인트 혼재(600·720·760·1000), 상태색·모션 토큰 없음 | 일관성 | 토큰 v2: 브레이크포인트 sm480/md768/lg1024/xl1280 명시, 상태색(시스템 메시지 전용)·모션·표 밀도 토큰 |
| Minor | 목표 계산기 | `select#gs` 가 `section#gs` 와 id 중복 | 구현 오류 | `gassume` 으로 수정(이미 반영) |

측정: 390px 헤더 높이 190px → 56px, 메뉴 2탭 → 드로어 1탭 + 항목 1탭, 대비(본문 #1a1a1a/흰 16.9:1, muted #595959 7.0:1, 링크 #1B4F9B 8.6:1, surface 위 muted 6.5:1) 모두 AA 통과.

## 2. 정보구조

```
다잇다
├─ 현황·통계: 현황판 /dashboard · 탐색 /explore · 산업별 /industry · 통계 /stats(주제 7)
├─ 기업: 기업 사전 /companies · 상장기업 /listed · 지원 기업 /support
├─ 사업·리포트: 사업·예산 /programs · 리포트 /policy
├─ 성장 계산기 /growth
└─ 통합 검색 /search · 전체 글 /posts
```
URL 은 바꾸지 않는다(검색 색인·링크 유지). 묶음은 `src/nav.ts` `NAV_GROUPS`, 평면 `NAV` 는 404·검색이 그대로 쓴다.

## 3. 토큰 v2 (`src/styles/tokens.css`)
- 타이포: 기존 단계 유지(18/16/14, 31.5/24/20, 42). 행간 토큰 분리 `--lh-tight 1.3`(제목) · `--lh-table 1.4`(표).
- 색: 시맨틱 별칭(`--color-text`, `--color-bg-subtle`, `--color-border`, `--color-accent`) + 상태색 4종(info/warn/error/ok — 시스템 메시지 전용, 평가·증감에 쓰지 않음). `.callout.{info|warn|error|ok}`.
- 간격·레이아웃: `--section-gap`, 브레이크포인트 4개(주석), 표 밀도 `.compact`(6px).
- 모션: `--ease`, `--dur-1 120ms`, `--dur-2 200ms`; `prefers-reduced-motion` 전역 유지.

## 4. 컴포넌트
- 글로벌 헤더: 묶음 버튼(`aria-expanded`, `aria-controls`, 현재 묶음 `aria-current="true"`), 패널은 클릭·키보드로 열고 Esc·바깥 클릭·포커스 이탈로 닫힘. 모바일 드로어(`#site-drawer`, 전체 화면, 닫기 버튼·Esc, 본문 스크롤 잠금).
- 데이터 테이블: `.scroll-x .data-table` 첫 열 sticky(배경·구분선), 머리 배경, 행 호버, `tabular-nums`, 숫자 열 `.n` 오른쪽 정렬(기존).
- 필터 툴바(기업 사전): 적용 칩 `button.chip-x`(aria-label '… 조건 지우기'), `모두 지우기`, 결과 수 `aria-live`, 빈 상태 `li.empty`.
- 첫 화면 진입 타일 `nav.entry > a.entry-tile`(제목·숫자·설명).
- 회전 카드: 자동 넘김 기본 꺼짐, 버튼 '자동 넘김 시작'.

## 5. 남은 일(다음 단계)
- 표의 모바일 카드 전환(stacked cards)과 열 숨김 우선순위 속성.
- 통합 검색 타입어헤드(기업·글·사업 그룹)와 최근 검색.
- 페이지 헤더 표준 템플릿(브레드크럼·기준일·출처 줄)을 모든 페이지에 적용.
- Lighthouse·axe 자동 측정 스크립트를 CI 에 추가.

## 6. 수용 기준 확인(2026-10-06, Playwright)
- 390px: 헤더 높이 ≤ 56px, 페이지 가로 스크롤 없음(첫 화면·기업 사전·상장기업·통계·성장 계산기).
- 1280px: 묶음 펼침 키보드 조작(Tab → Enter → 패널 링크 포커스 → Esc 닫힘).
- 회전 카드 자동 넘김 없음(초기 `aria-pressed="true"` 정지 상태).

## 7. 2차(2026-10-06, '다음 단계' 구현)
- **표 반응형**(`src/scripts/table_tools.ts` `responsive`): 머리 칸 `data-pri="2|3"` 열 우선순위(768/1024px 아래 숨김), 머리 한 줄·병합 없음·열 5개 이상인 표는 600px 아래에서 행마다 카드(`td::before` = 머리 글자, DOM 그대로라 복사·PDF 는 표), 「표로 보기」 토글, `data-stack="off|on"`.
- **자동완성**(`src/scripts/typeahead.ts`, `/typeahead.json`): 첫 화면·통합 검색 입력에 기업 5·글 3·부처 사업 3 + '전체 검색', ARIA combobox/listbox, 화살표·Enter·Esc, 최근 검색 8개(localStorage, × 로 지움). 순서는 시작 일치 → 포함, 가나다순(추천·순위 아님).
- **브레드크럼 표준**(`Base.astro` `crumb`·`nocrumb`): 홈 › 묶음 › 메뉴 › 현재. 수동 줄 16곳을 prop 으로 바꿈, 복잡한 2곳(기업 페이지·지침 검토기)은 `nocrumb` 으로 기존 줄 유지.
- **CI 감사**(`scripts/ui_audit.mjs`, `.github/workflows/ui_audit.yml`): axe(WCAG 2.x AA)+Lighthouse(모바일) 8개 페이지, axe 위반·가로 스크롤이면 실패, Job Summary·아티팩트. src 푸시 때 자동.
