# 달구벌 AI 노트 — Claude Code 작업 지침

대구 경제와 공무원 AI 활용을 다루는 개인 블로그. 자동 수집한 초안을 사람이 승인해 발행한다.
운영자는 현직 지방공무원이므로 **정책 평가·비판, 기관 입장으로 읽힐 표현, 비공개 자료 인용은 절대 넣지 않는다.**

## 구조

- `src/content/posts/*.md` — 글. 프론트매터 스키마는 `src/content.config.ts`. `draft: true` 면 미노출
- `src/pages/` — index(첫 화면), `category/[cat]`, `posts/[...id]`, `rss.xml.ts`
- `src/layouts/Base.astro` — 공통 레이아웃과 SEO 메타. `src/styles/global.css` — 전체 스타일
- `src/categories.ts` — 카테고리 4개: `economy` 대구 경제 / `grants` 공모·지원사업 / `ai-trends` AI 동향 / `gov-ai` 공무원 AI
- `scripts/collect.py` — 수집 → 선별 → 중복제거 → Gemini 요약 → SEO 메타 → 초안 저장
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

## 글 작성 원칙 (프롬프트·코드 수정 시 반드시 유지)

1. 원문에 없는 수치·날짜를 만들지 않는다. 불명확하면 "원문 확인 필요"
2. 원문 문장을 그대로 옮기지 않는다. 완전히 다시 쓴다. 인용은 15단어 이내, 소스당 1회
3. 모든 글에 출처(`source`, `sourceUrl`)를 남긴다. 보도자료는 공공누리 조건에 따라 출처 표시
4. 정책 평가·비판 없음. 사실과 대구 산업 접점만 정리
5. 자동 생성 글은 `auto: true` 로 표시하고 `draft: true` 로 저장. 승인 없이 노출하는 코드 변경 금지
6. 공모 글은 `deadline` 을 채운다. 첫 화면 마감 띠가 이 값을 쓴다
7. 개인정보·내부 자료·로그인 뒤 자료는 수집 대상에 넣지 않는다

## 코드 규칙

- Python: 표준 라이브러리 + requests/feedparser/pyyaml 만. 새 의존성은 `scripts/requirements.txt` 에 추가
- 외부 API 실패는 예외로 죽이지 말고 로그 찍고 건너뛴다 (매일 무인 실행)
- 1회 실행 Gemini 호출 상한은 `sources.yml` 의 `max_per_run`. 상한 없이 루프 돌리지 않는다
- Astro: 컴포넌트는 `src/components/`. Tailwind 등 CSS 프레임워크 추가하지 않음. `global.css` 의 CSS 변수 사용
- 새 카테고리는 `src/categories.ts` 와 `content.config.ts` 의 enum, `collect.py` 의 `PROMPTS` 세 곳을 함께 수정

## 로드맵

- 2주차: 승인 대시보드(Next.js 또는 Cloudflare Pages Functions), 조코딩 유튜브 자막·조코레터 이메일 수집 모듈, 주간 AI 다이제스트(월요일)
- 3주차: 네이버 뉴스 API, DART 대구 상장사 공시, 대구시 보도자료 RSS, 워드프레스 복제 발행(선택)
