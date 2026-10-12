# 다잇다 리디자인 v3 — 3단계 컴포넌트 명세(구현된 것 기준)

- 작성 2026-10-12 · 운영자 '진행해' · 앞 단계 `01-audit.md`·`02-ia-tokens.md`
- 원칙: 아이콘만으로 뜻을 전하지 않는다(글자 라벨 동반), 출처·기준일은 같은 시야, 평가·순위 표현 없음, 토큰만 참조

## 공통 틀

| 컴포넌트 | 위치 | 해부 | 상태·동작 | 접근성 |
|---|---|---|---|---|
| 유틸리티 바 | `Base.astro` `.util-bar`, `nav.ts` `UTIL_LINKS` | 왼쪽 출처 기관 4개 · 오른쪽 사이트 소개·통합 검색 | 1024px 이상만 보임 | `aria-label` 출처 기관 바로가기, 외부 링크 `rel=noopener` |
| 글로벌 메뉴(GNB) | `Base.astro` `.nav`, `nav.ts` `NAV_GROUPS` | 대메뉴 5개(묶음은 펼침 단추, 단일은 링크) | 펼침 하나만, Esc·바깥 클릭·포커스 이탈로 닫힘, 현재 묶음 밑줄 | `aria-expanded`·`aria-controls`·`aria-current` |
| 전체 메뉴 | `#site-drawer` | 묶음별 제목 + 링크, '더 보기' | 768px 미만 전체 화면 드로어, 이상은 헤더 아래 펼침 패널 | 열면 닫기 단추로 포커스, Esc 닫힘 |
| 위치 표시 줄 | `.loc-row` | 왼쪽 드롭다운 브레드크럼(`details.cr-dd`) · 오른쪽 페이지 행동 | 드롭다운 하나만 열림, 바깥 클릭·Esc 닫힘 | `nav aria-label=현재 위치`, 현재 단계 `aria-current` |
| 페이지 행동 | `.page-acts .pa-btn` | 링크 복사 · 인쇄(아이콘 + 글자) | 복사 뒤 '복사했습니다' 1.8초, 480px 미만은 글자를 화면에서만 숨김 | 글자가 접근 가능한 이름 |
| 제목 띠 | CSS `main .section-head:has(> h1)`·`.page-head`·`article.post > header` | 옅은 청색 면(화면 끝까지) · 제목 · 오른쪽 메타(기준·출처) | 인쇄 때 면 없음 | 제목 단계 h1 하나 |

## 첫 화면

| 컴포넌트 | 파일 | 내용 |
|---|---|---|
| 제목 띠·검색 | `HomeHero.astro` | 제목 · 한 줄 설명 · 검색창(자동완성 `data-typeahead`) · 인기 검색어 칩 |
| 주요 메뉴 | `QuickMenu.astro` | 8칸(2열 → 640px 이상 4열), 선 아이콘 + 이름 + 한 줄 설명·건수 |
| 게시판 2칸 | `HomeBoard.astro` | 리포트 5건(`REPORT_FILES` 순서) · 자료 갱신 현황(자료마다 기준·받은 날) |

## 자료 페이지

| 컴포넌트 | 파일 | 해부 | 비고 |
|---|---|---|---|
| 첨부 목록 | `AttachList.astro` | 굵은 위선 · 줄마다 형식 꼬리표(PDF/한글/Word) · 파일명 · 크기·쪽수 · 「내려받기 \| 열기」 | 열기는 PDF 만 |
| 리포트 상세 | `pages/policy/[slug].astro` | 제목 띠 · 요약 · 주제 칩 · 첨부 목록 · PDF 미리보기(`details.viewer`) · 다른 리포트 | 미리보기는 펼칠 때만 받음, 3MB 이하 데스크톱 기본 펼침 |
| 리포트 목록 | `pages/policy/index.astro` `.rlist` | 제목 링크 · 요약 · 날짜·주제 칩 · 형식별 내려받기 단추 | 768px 미만 단추 가로 배치 |
| 하위 탭 | `.sub-tabs`(전역) | 같은 묶음 안 페이지 이동 | `/listed/` 8개, `/support/` 4개 |
| 큰 목록 | `/support/`·`/sme/`·`/companies/` | 처음 N곳 HTML + 색인 JSON 을 받아 거름 | 결과 수 표시, '더 보기' |

## 데이터 색인 형식

- `/companies-index.json` v2: `{ v: 2, as_of, total, dict: {d,e,c,g,s,w,t,k,z}, rows: [[i,n,d,e,c,g,s,w,t,x,m,f,k,z]] }` — 2.9MB → 0.93MB(gzip 0.23MB). 되살림은 `src/scripts/companyIndex.ts`(검색·탐색), 기업 사전 목록은 인라인 `decodeIdx`(같은 식).
- `/support-index.json`: 지원받은 기업 행 배열(`lib/supportFirms.ts` `supportIndex`).

## 측정 기준선 → 현재(모바일 실험실 값, 같은 기계)

| 페이지 | 감사 때 | 지금 |
|---|---|---|
| 페이지마다 JS | 1,150KB | 약 26KB |
| `/listed/` 성능 | 42 | 97 |
| `/support/` 성능 | 38 | 89 |
| `/search/?q=로봇` 성능·결과 표시 | 73 · 19.1초 | 85 · 4.2초 |
| 검색 화면 밀림(CLS) | 0.41 | 0.016 |
| axe 위반(대표 9쪽 × 2폭) | 1쪽 4건 | 0 |

## 다음 후보

- 기업 상세 페이지 정보 순서를 기업 카드 출력과 맞추기(사실 카드 → 시계열 → 관계 → 출처)
- 통계 주제 페이지 '핵심 요약' 블록(맨 위 3~5개 사실 + 앵커)
- 인쇄 스타일시트 머리말·꼬리말(사이트명·URL·출력 일시)
