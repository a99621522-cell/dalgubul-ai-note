# 다잇다 노트 — Claude Code 작업 지침 (구 달구벌 AI 노트)

대구 산업·기업 현황과 정책 근거를 정리하는 **공무원용** 자료 사이트(브랜드 '다잇다', 블로그 note.daitda.co.kr). 범위는 대구광역시 전체(9개 구·군). 산업별 통계·기업 사전·사업 예산·정책제안 리포트가 중심이고, 기업 지원사업 공고는 글로 쓰지 않고 데이터(data/notices)로만 남긴다(2026-09-25). 자동 수집한 초안(공시·보도자료·리포트)은 사람이 승인해 발행한다.
운영자는 현직 지방공무원이므로 **정책 평가·비판, 기관 입장으로 읽힐 표현, 비공개 자료 인용은 절대 넣지 않는다.**

## 구조

- `src/content/posts/*.md` — 글. 프론트매터 스키마는 `src/content.config.ts`. `draft: true` 면 미노출
- `src/pages/` — index(첫 화면), `dashboard/`(현황판: 입지·구군·단지·태그), `industry/`(산업 그룹 11개 목록·`[key]`·`compare`), `stats/[month]`(월간 통계표), `companies/`(기업 사전·카드), `support/`(지원받은 기업), `programs/`, `posts/`(글 목록)·`posts/[...id]`, `category/[cat]`, `rss.xml.ts`. 메뉴는 `src/nav.ts`
- `src/layouts/Base.astro` — 공통 레이아웃과 SEO 메타. `src/styles/global.css` — 전체 스타일
- `src/categories.ts` — 카테고리 3개: `economy` 기업 동향 / `grants` 공모·지원사업 / `policy` 산업 정책. AI 동향·공무원 AI 글은 이 사이트에서 다루지 않는다(별도 사이트 예정, 초안은 docs/archive-ai-notes)
- `scripts/collect.py` — 수집(기업마당 API · RSS · 게시판 스크랩 · inbox JSON) → 선별 → 중복제거 → 공고(grants)는 `data/notices/notices.csv` 에 사실만 기록(Gemini 없음) / 기업 동향·정책은 Gemini 요약 → SEO 메타 → 초안 저장
- `scripts/inbox/` — 외부 크롤러 에이전트 결과 JSON 투입구. 형식은 그 안의 README
- `scripts/collect_dart.py` — OpenDART 공시 중 대구 기업(본사 주소로 판정, `scripts/state/dart_corp.json` 캐시)의 확장 신호(신규시설투자·유상증자·공급계약 등)를 inbox JSON 으로. 공시 사실과 원문 링크만, 평가 없음. 설정은 `sources.yml` 의 `dart:`. 키는 `DART_KEY`
- `src/pages/companies/` — 기업 사전(목록 + 기업별 페이지 /companies/<id>/). 데이터는 `src/lib/csv.ts`가 빌드 때 CSV에서 읽음. `sector_group` 은 CSV 값이 아니라 항상 `config/industry_groups.yml` 규칙(11개)으로 다시 판정한다. 목록 필터: 단지·업종·구군·입지 유형·태그·지원 이력, URL 인자 complex/group/district/site/tag/support/q
- `src/pages/companies-index.json.ts` — 기업 사전 검색용 경량 색인(/companies-index.json). 목록 페이지는 처음 200곳만 HTML로 내보내고 검색·필터 때 이 색인을 받아 클라이언트에서 거른다. 필드를 바꾸면 `companies/index.astro`의 스크립트도 같이 고칠 것
- `src/lib/partners.ts` — 협업 후보(공급/수요/동종) 규칙 엔진: 업종코드+생산품으로 공정 단계 추정 → 단계 간 공급 관계표 → 같은 단지·구군 우선. '후보'라고만 표기, 거래 관계 단정 금지. 이후 Gemini 공정 분류·산업연관표로 정밀화
- `scripts/import_factoryon.py` — 팩토리온 월간 엑셀(전국 입주업체현황 + 선택: 산단공 리스트) → 기업·단지 CSV 갱신(id 유지). 사용법은 scripts/data/README.md
- `config/industry_groups.yml` — 산업 그룹 11개 규칙(KSIC 접두어+키워드). `scripts/industry.py`·`src/lib/industry.ts`가 읽음. 규칙은 파일에만
- `config/site_types.yml` — 입지 유형(수성알파시티·연구개발특구·지식산업센터·산업단지·개별입지)과 태그(창업·창경센터·연구소기업·벤처·이노비즈) 규칙. `scripts/sites.py`·`src/lib/sites.ts`
- `scripts/data/kic_buildings.csv` + `scripts/import_kic.py` — 대구 지식산업센터 건물 도로명주소 목록. 주소가 일치하면 건물명이 없어도 입지 유형이 지식산업센터. 전국지식산업센터현황(산단공) 파일을 넣으면 갱신
- `scripts/import_extra.py` — 산단 외 기업 목록(`scripts/data/extra/*.csv`, 형식은 그 README) → `extra_companies.csv`(id x0001~) + `company_tags.csv`. 팩토리온과 같은 기업이면 태그만
- `scripts/data/support_history.csv` + `scripts/import_support.py` — 지원사업 수혜 이력(NTIS 과제·대구시 보조금 공개·기관 선정 공고, 투입구 `scripts/data/support/`, 형식은 그 README). 기업 페이지 '지원사업 이력(최근 3년)', 통계 `support_3y`, 리포트 근거. 비공개 자료(정책자금 개별 내역) 금지
- `config/support_institutions.yml` + `scripts/institution_support.py` — 기업지원기관(대구TP·DIP·DMI·케이메디허브·창경센터·로봇산업진흥원·ETRI·생기원·경북대 등)이 주관·참여한 과제·보조사업의 기업을 대구 기업/역외 기업으로 나눠 `data/institutions/`(CSV·summary.json·README). 워크플로가 data/raw 의 포털 파일로 만든다. 기관·별칭 추가는 yml 에만
- `config/institution_boards.yml` + `scripts/scrape_institution_boards.py` — 기관 홈페이지 공고 게시판에서 '선정 기업 명단' 글을 찾아 지원 이력 투입 CSV(`scripts/data/support/inst_<key>.csv`)로. robots.txt 존중, 표·첨부(PDF·HWPX·XLSX·HWP)에서 기업명만. GitHub 러너에서는 대부분 기관 사이트가 접속 시간 초과라 국내 PC 에서 돌린 뒤 `import_support.py --replace-source '홈페이지 공고'`. 워크플로 `institution_boards.yml` 은 수동 실행만
- `scripts/collect_dart_fin.py` — DART 정기보고서 매출·영업이익·당기순이익(대구 공시 기업만, `DART_KEY`) → `scripts/data/company_financials.csv`. 기업 페이지 '재무(DART 공시)'
- `.github/workflows/fetch_public.yml` + `scripts/fetch_datago.py` — 공공데이터포털 파일데이터(지식산업센터현황 15117154, 국민연금 사업장 15083277)를 Actions 가 받아 처리·커밋. 이 세션 환경은 포털 접속이 막혀 있으므로 데이터 갱신은 이 워크플로로. `data/fetch_mode.txt`(mode|ids|pick)를 바꿔 푸시하면 실행. mode=search 면 ids 를 검색어로 보고 포털 파일데이터 번호만 출력
- `scripts/nps_to_extra.py` — 국민연금 대구 사업장 중 팩토리온에 없는 곳 → 산단 외 기업 후보(서비스업 제외) → `import_extra.py --replace-source 국민연금`
- `scripts/collect_nps.py` — 공공데이터포털 국민연금 가입 사업장 내역(오픈API 또는 내려받은 파일) → `data/nps/YYYYMM.csv` 대구만. 키 `DATA_GO_KR_KEY`, 주소는 `sources.yml` `nps:`. 이 세션 환경은 포털 접속 차단이라 `.github/workflows/nps.yml`(매월 6일)이나 로컬에서 실행
- `scripts/build_stats.py` — 월간 집계(팩토리온+산단 외 기업+국민연금 파일 있으면) → `data/stats/`. 전수 기준. 자료 없는 지표는 null
- `scripts/render_charts.py` — `data/stats` → `src/generated/charts/` 인라인 SVG(넓은 판·좁은 판)+표 JSON. `Chart.astro`가 읽음
- `scripts/write_monthly_report.py` — 월보 초안: `data/stats/monthly/YYYYMM.json` 의 값만 옮겨 `src/content/posts/YYYY-MM-DD-monthly-YYYYMM.md`(draft·auto, 표 6개·faq 3)로. `nps.yml` 이 매월 집계 뒤 실행. 발행은 `approve.py`
- `config/pledge_areas.yml` + `scripts/report_context.py` — 매주 공약 분야별 정책제안 리포트 루틴(docs/ROUTINE_PROMPT.md)의 분야 순환표와 근거 계산(기업 사전·사업 DB·대구시 매칭·최근 글). 리포트는 `draft: true`, 공약 이행 평가·점수화 금지
- `scripts/repair_factoryon.py` — 팩토리온 내려받기 파일이 엑셀에서 안 열릴 때. 첫 바이트로 실제 형식(진짜 xls·HTML 표·CSV·SpreadsheetML) 판정 → 옆에 `_정리.xlsx`(시트 1개, 헤더 고정, 자동 필터, 종사자 숫자·등록일 날짜). 원본은 건드리지 않음
- `scripts/data/` — 달성 산단·기업 기초 CSV. `dalseong_complexes.csv`는 첫 화면·대구 경제 페이지의 산단 카드(`IndustrialCard.astro`)가 빌드 때 읽고, `dalseong_companies.csv`의 기업명은 collect.py가 경제 키워드로 자동 추가
- `scripts/sources.yml` — 소스·키워드. 소스 추가는 코드가 아니라 여기서
- `scripts/approve.py` — 초안 승인. `scripts/state/seen.json` — 중복 방지
- `.github/workflows/collect.yml` — 매일 05:30 KST 자동 실행

## 명령

```
npm run dev / npm run build           # Astro
pip install -r scripts/requirements.txt
python3 scripts/collect.py --dry-run  # 어떤 항목이 잡히는지만 (Gemini 호출 없음)
python3 scripts/collect_dart.py --dry-run  # DART 대구 확장신호 후보만 (DART_KEY 필요)
python3 scripts/collect.py            # 실제 초안 생성 (BIZINFO_KEY, GEMINI_KEY 필요)
python3 scripts/approve.py            # 초안 승인
```

## 기업 사전 원칙
- 전수 원칙: 팩토리온 목록의 모든 기업을 같은 형식으로. 특정 기업만 부각하는 코드·문구 금지
- 공개 자료만, 출처·기준일 항상 표기. 평가·순위·추천 표현 금지. 대표자 개인정보는 싣지 않음(원본 엑셀에도 넣지 않음)
- 기업 id는 URL이므로 바꾸지 않는다
- 개인 성명으로 보이는 공장명(한글 3자·성씨로 시작·상호 접미어 없음, 예: 대표자 이름으로 등록된 개인사업자)은 `src/lib/csv.ts`의 `looksLikePersonName`이 목록·페이지에서 뺀다. 공개 자료여도 개인정보 원칙이 전수 원칙보다 앞선다. 규칙을 넓힐 때는 4자 상호가 같이 빠지지 않는지 제외 건수를 확인할 것

## 글 작성 원칙 (프롬프트·코드 수정 시 반드시 유지)

1. 원문에 없는 수치·날짜를 만들지 않는다. 불명확하면 "원문 확인 필요"
2. 원문 문장을 그대로 옮기지 않는다. 완전히 다시 쓴다. 인용은 15단어 이내, 소스당 1회
3. 모든 글에 출처(`source`, `sourceUrl`)를 남긴다. 보도자료는 공공누리 조건에 따라 출처 표시
4. 정책 평가·비판 없음. 사실과 대구 산업 접점만 정리
5. 자동 생성 글은 `auto: true` 로 표시하고 `draft: true` 로 저장. 승인 없이 노출하는 코드 변경 금지
6. 지원사업 공고는 글로 쓰지 않는다. `data/notices/notices.csv` 에 제목·기관·마감·링크만 남기고, 리포트는 그 데이터를 근거로 쓴다
7. 개인정보·내부 자료·로그인 뒤 자료는 수집 대상에 넣지 않는다
8. AI 답변 최적화(AEO): 모든 글은 `description`을 결론 먼저의 '핵심 문장'으로, 표로 정리할 수 있는 정보는 표로, 글마다 `faq` 3개(본문 근거만). 이미지는 캡션(figcaption) 필수. 글 페이지는 Article·FAQPage JSON-LD를 자동 출력한다
9. 게시판 스크랩·크롤러는 공공기관 사이트만, 하루 1회, robots.txt 존중. 약관상 수집 금지인 상업 사이트는 소스로 추가하지 않는다

## 코드 규칙

- Python: 표준 라이브러리 + requests/feedparser/pyyaml/beautifulsoup4 만. 새 의존성은 `scripts/requirements.txt` 에 추가
- 외부 API 실패는 예외로 죽이지 말고 로그 찍고 건너뛴다 (매일 무인 실행)
- 1회 실행 Gemini 호출 상한은 `sources.yml` 의 `max_per_run`. 상한 없이 루프 돌리지 않는다
- Astro: 컴포넌트는 `src/components/`. Tailwind 등 CSS 프레임워크 추가하지 않음. `global.css` 의 CSS 변수 사용
- 새 카테고리는 `src/categories.ts` 와 `content.config.ts` 의 enum, `collect.py` 의 `PROMPTS` 세 곳을 함께 수정

## 로드맵 (2026-09-22 기준)

브랜드: 다잇다(daitda.co.kr = 앱, note.daitda.co.kr = 블로그). 대구광역시 전체. 공개 자료만, 평가·순위 없음, 비영리.

### 완료
- 블로그 뼈대(Astro): 기업 사전 11,174곳 / 기업 동향 / 공모·지원사업 / 산업 정책
- 기업 DB: 팩토리온 월간 엑셀 → scripts/import_factoryon.py → dalseong_companies.csv(대구 전체)·dalseong_complexes.csv(단지 22)
- 협업 후보 찾기(규칙판): src/lib/partners.ts — 공정 단계 추정 → 공급/수요/동종 후보
- 수집기 collect.py: 기업마당 API·RSS·게시판 스크랩·inbox JSON → Gemini 요약·SEO·FAQ → draft 초안. GitHub Actions 매일 05:30
- 문서: docs/DESIGN.md, docs/ROUTINE_PROMPT.md, scripts/data/institutions.yml

### 1단계 — 배포·가동 (이번 주)
1. Cloudflare Pages 배포, 커스텀 도메인 note.daitda.co.kr, daitda.co.kr → 블로그 리다이렉트(앱 전까지)
2. GitHub Secrets: BIZINFO_KEY, GEMINI_KEY → Actions 첫 실행 확인
3. Claude Code 루틴 등록: 주간 기관 공고 수집, 월간 팩토리온 갱신 (docs/ROUTINE_PROMPT.md)

### 2단계 — 사업 DB (다잇다 본체 재료)
4. 예산서 파서 scripts/parse_budget.py: 부처 사업설명자료(산업부 확보, 중기부·과기부·국토부 추가 예정) + 대구시 세출예산 명세서(경제국·미래혁신성장실 확보) → scripts/data/programs.csv (layer, ministry, code, name, executor, budget_2025/2026, funding, target, conditions, schedule, source_url, matched_city_item)
5. 신규·증액 사업 목록 페이지 "올해 공고 예정 사업"
6. 통합 창구 게시판 소스 추가: IRIS, K-Startup, 소상공인24, 고용24 (sources.yml boards)
7. 뉴스레터: scripts/newsletter.py(지난 2주 승인 글 + 공모 마감표 → 이메일 HTML), /newsletter/ 아카이브, 스티비 구독 폼, 개인정보처리방침 페이지

### 3단계 — 다잇다 앱 MVP
8. 회사명(자동완성) 또는 업종·규모·필요 입력 → 규칙 필터 → 임베딩 검색 → Gemini 요약(원문 링크·마감 필수, "가능성 있음 — 공고 ○항 확인" 표현) → 사업 5개
9. 스택: Cloudflare Pages(화면) + Render(중계, Gemini 키·일일 상한) + programs.csv/companies.csv
10. 이후 모의심사 앱과 연결(찾기 → 심사 → 수정 → 발표 PPT)

### 4단계 — 기업 신호·연결 기능
11. 확장 신호 수집기: DART 신규시설투자 공시, 네이버 뉴스(증설·MOU·이전), 팩토리온 신규입주계약, 고용24 채용 급증, 벤처투자 공시, KIPRIS 특허 → 기업 타임라인 + "확장 신호 감지 목록"(신호만, 평가 없음)
12. 선정 기업 아카이브: 보도자료 선정기업 명단 → 기업 사전 지원사업 이력
13. 협업 후보 정밀화: Gemini 공정 분류 + 한국은행 산업연관표(KSIC→IO 부문 매핑)
14. 공급망 지도: 대구 클러스터별 공정 분포·빈 고리 → 전국 팩토리온 파일에서 보완 후보 업종·기업(조건 명시, 전수 나열)
15. 입찰 알림: 나라장터 API, 기업 업종·생산품 매칭
16. 정책·규제 변화 알림: 법령·고시·조례 RSS → 기업 언어 요약

### 5단계 — 인력·기술·입지
17. 인력 매칭 앞단: 고용24 채용 공고 + 대구RISE센터·대학 인력양성 과정 → 기업 페이지 배지·상자
18. 기업–교수 기술 연계: NTIS 과제 + KIPRIS 대학 특허 → 연구자 카드(공개 실적만, 산학협력단 창구 안내) → 임베딩 매칭
19. 산단 입지 정보: 팩토리온 분양·처분 공고, 산단공·도시공사 공고 → 단지별

### 별도(이 저장소 아님)
- AI 활용 진단(AEO): 모의심사 앱에 탭으로
- 공무원 AI·AI 동향 글: 별도 사이트(초안 docs/archive-ai-notes)
- 기업 애로·규제개선 접수: 군 공식 AI 정부 실험실 과제

### 필요한 키 (사용자 발급)
BIZINFO_KEY(있음), GEMINI_KEY(있음), NAVER_CLIENT_ID/SECRET, DART_KEY, WORK24_KEY(고용24), G2B_KEY(나라장터, data.go.kr), KIPRIS_KEY, NTIS_KEY
