# 다잇다 노트 — Claude Code 작업 지침 (구 달구벌 AI 노트)

대구 기업·지원사업·산업 정책을 다루는 개인 블로그(브랜드 '다잇다', 앱 daitda.co.kr / 블로그 note.daitda.co.kr). 범위는 대구광역시 전체(9개 구·군). 자동 수집한 초안을 사람이 승인해 발행한다.
운영자는 현직 지방공무원이므로 **정책 평가·비판, 기관 입장으로 읽힐 표현, 비공개 자료 인용은 절대 넣지 않는다.**

## 구조

- `src/content/posts/*.md` — 글. 프론트매터 스키마는 `src/content.config.ts`. `draft: true` 면 미노출
- `src/pages/` — index(첫 화면), `category/[cat]`, `posts/[...id]`, `rss.xml.ts`
- `src/layouts/Base.astro` — 공통 레이아웃과 SEO 메타. `src/styles/global.css` — 전체 스타일
- `src/categories.ts` — 카테고리 3개: `economy` 기업 동향 / `grants` 공모·지원사업 / `policy` 산업 정책. AI 동향·공무원 AI 글은 이 사이트에서 다루지 않는다(별도 사이트 예정, 초안은 docs/archive-ai-notes)
- `scripts/collect.py` — 수집(기업마당 API · RSS · 게시판 스크랩 · inbox JSON) → 선별 → 중복제거 → Gemini 요약 → SEO 메타 → 초안 저장
- `scripts/inbox/` — 외부 크롤러 에이전트 결과 JSON 투입구. 형식은 그 안의 README
- `src/pages/companies/` — 기업 사전(목록 + 기업별 페이지 /companies/<id>/). 데이터는 `src/lib/csv.ts`가 빌드 때 CSV에서 읽음
- `src/lib/partners.ts` — 협업 후보(공급/수요/동종) 규칙 엔진: 업종코드+생산품으로 공정 단계 추정 → 단계 간 공급 관계표 → 같은 단지·구군 우선. '후보'라고만 표기, 거래 관계 단정 금지. 이후 Gemini 공정 분류·산업연관표로 정밀화
- `scripts/import_factoryon.py` — 팩토리온 월간 엑셀(전국 입주업체현황 + 선택: 산단공 리스트) → 기업·단지 CSV 갱신(id 유지). 사용법은 scripts/data/README.md
- `scripts/data/` — 달성 산단·기업 기초 CSV. `dalseong_complexes.csv`는 첫 화면·대구 경제 페이지의 산단 카드(`IndustrialCard.astro`)가 빌드 때 읽고, `dalseong_companies.csv`의 기업명은 collect.py가 경제 키워드로 자동 추가
- `scripts/sources.yml` — 소스·키워드. 소스 추가는 코드가 아니라 여기서
- `scripts/approve.py` — 초안 승인. `scripts/state/seen.json` — 중복 방지
- `.github/workflows/collect.yml` — 매일 05:30 KST 자동 실행

## 명령

```
npm run dev / npm run build           # Astro
pip install -r scripts/requirements.txt
python3 scripts/collect.py --dry-run  # 어떤 항목이 잡히는지만 (Gemini 호출 없음)
python3 scripts/collect.py            # 실제 초안 생성 (BIZINFO_KEY, GEMINI_KEY 필요)
python3 scripts/approve.py            # 초안 승인
```

## 기업 사전 원칙
- 전수 원칙: 팩토리온 목록의 모든 기업을 같은 형식으로. 특정 기업만 부각하는 코드·문구 금지
- 공개 자료만, 출처·기준일 항상 표기. 평가·순위·추천 표현 금지. 대표자 개인정보는 싣지 않음(원본 엑셀에도 넣지 않음)
- 기업 id는 URL이므로 바꾸지 않는다

## 글 작성 원칙 (프롬프트·코드 수정 시 반드시 유지)

1. 원문에 없는 수치·날짜를 만들지 않는다. 불명확하면 "원문 확인 필요"
2. 원문 문장을 그대로 옮기지 않는다. 완전히 다시 쓴다. 인용은 15단어 이내, 소스당 1회
3. 모든 글에 출처(`source`, `sourceUrl`)를 남긴다. 보도자료는 공공누리 조건에 따라 출처 표시
4. 정책 평가·비판 없음. 사실과 대구 산업 접점만 정리
5. 자동 생성 글은 `auto: true` 로 표시하고 `draft: true` 로 저장. 승인 없이 노출하는 코드 변경 금지
6. 공모 글은 `deadline` 을 채운다. 첫 화면 마감 띠가 이 값을 쓴다
7. 개인정보·내부 자료·로그인 뒤 자료는 수집 대상에 넣지 않는다
8. AI 답변 최적화(AEO): 모든 글은 `description`을 결론 먼저의 '핵심 문장'으로, 표로 정리할 수 있는 정보는 표로, 글마다 `faq` 3개(본문 근거만). 이미지는 캡션(figcaption) 필수. 글 페이지는 Article·FAQPage JSON-LD를 자동 출력한다
9. 게시판 스크랩·크롤러는 공공기관 사이트만, 하루 1회, robots.txt 존중. 약관상 수집 금지인 상업 사이트는 소스로 추가하지 않는다

## 코드 규칙

- Python: 표준 라이브러리 + requests/feedparser/pyyaml/beautifulsoup4 만. 새 의존성은 `scripts/requirements.txt` 에 추가
- 외부 API 실패는 예외로 죽이지 말고 로그 찍고 건너뛴다 (매일 무인 실행)
- 1회 실행 Gemini 호출 상한은 `sources.yml` 의 `max_per_run`. 상한 없이 루프 돌리지 않는다
- Astro: 컴포넌트는 `src/components/`. Tailwind 등 CSS 프레임워크 추가하지 않음. `global.css` 의 CSS 변수 사용
- 새 카테고리는 `src/categories.ts` 와 `content.config.ts` 의 enum, `collect.py` 의 `PROMPTS` 세 곳을 함께 수정

## 로드맵

- 2주차: 예산서 파서(programs.csv), 기관 공고 루틴, 네이버 뉴스·DART 연결, 뉴스레터 모듈
- 3주차: 네이버 뉴스 API, DART 대구 상장사 공시, 대구시 보도자료 RSS, 워드프레스 복제 발행(선택)
