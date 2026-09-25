# 디자인·UI 전면 개편 + 산업별 월간 통계 — 작업 계획 (2026-09-24)

브리프: 공공서비스 톤(큰 글씨·여백·장식 없음), 첫 화면은 숫자와 산업별 표, 모바일 우선, Astro + 순수 CSS, 그래프는 빌드 시 인라인 SVG.
이 문서는 1단계(저장소 현황·계획)의 산출물이며, 진행하면서 갱신한다.

## 1. 저장소 현황 (있는 것 / 없는 것)

| 브리프가 전제한 것 | 저장소 실제 | 처리 |
|---|---|---|
| 매달 들어오는 국민연금 파일 | **없음.** 수집기도, 파일도, 언급도 없다 | 입력 규격을 정해 `data/nps/YYYYMM.csv` 로 받는다 (아래 3절, 확인 필요) |
| 고용 인원 = 국민연금 가입자수 | 팩토리온 `workers`(공장등록 신고값) 1개 시점(2026-08)만 있음. 10,034곳에 값, 합계 177,669명 | 국민연금 파일이 없는 달은 팩토리온 값으로 대체하고 화면에 "공장등록 신고값" 명시 |
| 24개월 시계열 | 시점 1개 | 과거 월 파일이 들어오면 소급. 없으면 1점짜리 그래프 대신 "자료 1개월" 표기 |
| `write_monthly_report.py` | **없음** | 새로 만든다(산업별 증감 절 포함). "숫자 검증 규칙"은 `monthly/YYYYMM.json` 에 있는 값만 쓴다는 규칙으로 정의 |
| `/dashboard` 현황판, "이전 설계" | **없음.** 유사물은 `IndustrialCard.astro`(구·군·단지 표) | 브리프 4-4 대로 새로 만든다 |
| 과제 선정 건수, DART 합산 매출, 인증 뱃지, 기업별 12개월 고용 추이 | 원천 없음. `scripts/state/dart_corp.json` 은 대구 DART 기업 주소 캐시뿐(재무 없음). NTIS·벤처확인 키·수집기 없음 | 통계 스키마에 자리(`null`)만 두고 화면은 "자료 없음"으로. 수집기는 별도 작업(수집 로직 불변 원칙) |
| 산업 그룹 | 팩토리온 `sector_group`(15개, '기타' 2,567곳) | `config/industry_groups.yml` 로 교체. 업종코드 11,174곳 전부 5자리 있음 → 미분류 0 |
| Pretendard 로컬 woff2 | CDN 링크 + Gowun Batang(제목, 구글폰트) | `public/fonts/` 에 가변 woff2 1개(약 2MB, OFL) 두고 `font-display: swap`. 제목 세리프·다크모드 제거 |

기존 URL(유지): `/`, `/companies/`, `/companies/<id>/`, `/companies-index.json`, `/programs/`, `/category/<cat>/`, `/posts/<id>/`, `/rss.xml`, `/404`.
수집 파이프라인(`collect.py`, `collect_dart.py`, `import_factoryon.py`, `collect.yml`)은 건드리지 않는다.

## 2. 데이터 흐름

```
scripts/data/dalseong_companies.csv  (팩토리온, 월 1회 import_factoryon.py — 기존)
data/nps/YYYYMM.csv                  (국민연금 사업장 가입현황 대구분 — 신규 입력, 규격은 3절)
config/industry_groups.yml           (산업 그룹 규칙 — 유일한 규칙 파일)
src/content/posts/*.md               (공모 마감 → '진행 중 공고 수')
        │
        ▼  python3 scripts/build_stats.py [--month 202609] [--backfill]
data/stats/monthly/YYYYMM.json       그 달 집계 (전체 / 산업 / 산단 / 구·군 × 지표, 산업×산단 교차표, 집계 대상 비율)
data/stats/timeseries.json           월별 시계열 (최소 24개월 보관, 축별 고용·기업 수)
data/stats/companies.json            기업 id → 산업 그룹, 매칭된 국민연금 고용, 12개월 고용 (기업 카드용)
data/stats/unclassified.csv          미분류 기업
        │
        ▼  python3 scripts/render_charts.py
src/generated/charts/*.svg           선 그래프·가로 막대 (Astro 가 빌드 때 fs 로 읽어 인라인)
src/generated/charts/*.json          같은 데이터의 표 (접힌 표용)
        │
        ▼  npm run build  (src/lib/stats.ts 가 data/stats/*.json 읽음, src/lib/industry.ts 가 yml 읽음)
```

워크플로: `collect.yml`(매일) → 변경 없음. 신규 `stats.yml`: `workflow_run`(국민연금 수집 완료 또는 `import_factoryon` 커밋) → build_stats → render_charts → 커밋 → `deploy.yml` 호출.

## 3. 국민연금 입력 규격 (확인 필요)

공공데이터포털 "국민연금공단_국민연금 가입 사업장 내역"(월별 CSV, 전국) 열을 그대로 쓴다고 가정한다.
`data/nps/YYYYMM.csv` (대구만 걸러 저장, cp949→utf-8): `사업장명, 사업자등록번호(앞 6자리), 사업장주소, 업종코드, 가입자수, 당월취득자수, 당월상실자수, 신규등록여부, 탈퇴여부(사업장탈퇴일)`.
팩토리온에는 사업자번호가 없으므로 매칭은 **정규화 회사명 + 구·군** 으로 한다((주)·㈜·공백·괄호 제거). 매칭률은 첫 파일에서 측정해 보고한다.
파일이 다른 출처·다른 열이면 `build_stats.py` 의 열 이름 표만 바꾸면 되게 만든다.

## 4. 새 파일 / 바꿀 파일 / 버릴 파일

새로: `config/industry_groups.yml`, `scripts/industry.py`, `scripts/build_stats.py`, `scripts/render_charts.py`, `scripts/write_monthly_report.py`,
`src/lib/industry.ts`, `src/lib/stats.ts`, `src/styles/tokens.css`, `public/fonts/Pretendard*.woff2`,
`src/components/{StatTiles,IndustryTable,Chart,DataTable,SiteNav,PageHead}.astro`,
`src/pages/industry/{index,[key],compare}.astro`, `src/pages/dashboard/{index,complex/[slug],district/[slug]}.astro`,
`src/pages/support/index.astro`, `src/pages/stats/[month].astro`, `src/pages/posts/index.astro`, `.github/workflows/stats.yml`.

바꿈: `Base.astro`(헤더 메뉴 5개, 푸터 출처·정정·갱신일, 폰트 로컬), `global.css`(tokens.css 위에 재작성), `index.astro`, `companies/index.astro`(산업 그룹 필터·표·정렬·50개 페이지), `companies/[id].astro`(숫자 3개·뱃지·미니 그래프), `companies-index.json.ts`(그룹 필드 `g` 를 산업 그룹으로), `programs/index.astro`(토큰 적용만), `posts/[...id].astro`(본문 720px), `category/[cat].astro`.

버림: `IndustrialCard.astro`(→ StatTiles + 현황판), Gowun Batang 링크, 다크모드 CSS, `DeadlineStrip.astro`(→ /support/ 표와 첫 화면 숫자로 흡수).

## 4-1. 산단 외 기업 (2026-09-25 추가 요청)
수성알파시티·연구개발특구·창조경제혁신센터 보육기업·지식산업센터 입주기업·창업기업 등 공장등록 밖 기업도 DB 에 넣는다.
- 규칙: `config/site_types.yml` (입지 유형 하나 + 태그 여러 개). 주소·단지명으로 자동 판정. 팩토리온 안에서도 알파시티 48·특구 130·지식산업센터 43곳이 바로 잡힘
- 투입: `scripts/data/extra/*.csv` → `import_extra.py` → `extra_companies.csv`(id x…) + `company_tags.csv`. 공개 목록 출처는 extra/README.md
- 통계: `by_site`(입지 유형별)·`by_tag`·`cross_site`(산업×입지) 축 추가, 그래프 `site-*`. 기업 사전 색인에 t(유형)·k(태그)
- 막힘: 이 환경은 공공 포털 접속이 차단돼 목록을 받지 못함. 사용자가 내려받아 두거나 네트워크 허용 루틴이 받는다
- 산단 밖 '모든' 고용 사업장의 바탕은 국민연금 사업장 파일(3절)이다

## 4-2. 공무원용 전환 (2026-09-25)
- 지원사업 공고는 글이 아니라 데이터(data/notices/notices.csv)로만. collect.py 의 Gemini 호출은 공시·보도자료 초안에만. 공고 글 38편은 draft 로 보관
- 메뉴: 현황 / 산업별 / 기업 사전 / 사업·예산(/programs/) / 글. `/support/` 페이지는 만들지 않는다. 첫 화면 4번째 타일 = 지원사업 수혜 기업(최근 3년)
- 지원 이력: scripts/data/support_history.csv (import_support.py, 투입구 scripts/data/support/). 기업 페이지 절 + 통계 support_3y + 리포트 근거.
  공개 자료: NTIS 과제(연구비), 대구시 지방보조금 공개(교부액), 기관 선정 공고(명단), DART 재무(상장·공시대상 매출). 정책자금 개별 내역은 비공개라 넣지 않는다
- 5단계 화면 순서: 산업별 → 현황판 → 기업 사전 → 카드 → 사업·예산 → 통계 → 글(리포트)

## 4-3. 공공데이터 반영 (2026-09-25, GitHub Actions fetch_public.yml)
- 세션 환경은 포털 접속이 막혀 있어 Actions 가 대신 받는다: data.go.kr 파일데이터는 페이지의 atchFileId 로 `/cmm/cmm/fileDownload.do` 에서 받는다(uddi 방식 selectFileDataDownload 는 HTML 만 준다)
- 받은 것: 전국지식산업센터현황(2025-06, 대구 건물 목록) · 국민연금 가입 사업장 내역 2026-07(대구 19,474행; 가입자 3인 이상 법인·10인 이상 개인만) · DART 재무(대구 공시 기업 2곳, 3개년)
- 국민연금 주소에는 건물번호가 없다 → 건물 단위(지식산업센터) 판정은 팩토리온 주소로만 가능. 시도코드 27 이면서 주소가 부산인 행이 있어 주소 문자열('대구광역시'/낱말 '대구')로 판정
- 팩토리온 11,174곳 중 국민연금 매칭 3,7xx곳(약 33%). 미매칭 대부분은 3인 미만·이름 불일치. 산단 외 기업 2,207곳 추가(서비스업 제외)
- 통계는 국민연금 달만(2026-07) 집계. 고용 = 가입자수, 집계 대상/전체 비율을 화면에 표시

## 5. 진행 순서와 확인 지점

1. 현황·계획(이 문서) ✔
2. `industry_groups.yml` + 분포 보고 ✔ → **확인 대기**
3. `build_stats.py` + `render_charts.py` → 전체 고용 추이 SVG ✔ (그래프는 넓은 판 .svg + 휴대폰 판 .m.svg 두 개씩, 표 .json). 통계는 전수 11,174곳 기준으로 확정
4. `tokens.css` + 공용 레이아웃 + 메인 → 390/1280 스크린샷 ✔ → **확인 대기**
5. 산업별 → 현황판 → 기업 사전 → 카드 → 지원사업 → 통계 → 글 (페이지마다 두 폭 스크린샷)
6. `stats.yml` 워크플로 연결
7. Lighthouse 모바일(성능·접근성) 보고, 접근성 90 미만이면 수정
