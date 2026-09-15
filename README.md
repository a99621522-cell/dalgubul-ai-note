# 달구벌 AI 노트

대구 경제와 공무원 AI 활용 기록. Astro 정적 사이트 + Python 수집기 + GitHub Actions.

## 구조

```
src/content/posts/   글(Markdown). draft: true 면 사이트에 안 나옴
src/pages/           첫 화면, 카테고리, 글 본문, RSS
scripts/collect.py   수집 → Gemini 요약 → 초안 저장
scripts/approve.py   초안 승인 도구
scripts/sources.yml  소스·키워드 설정 (여기만 고치면 됨)
scripts/state/       중복 방지용 seen.json (자동 생성)
.github/workflows/   매일 05:30 KST 자동 실행
```

카테고리: `economy` 대구 경제 / `grants` 공모·지원사업 / `ai-trends` AI 동향 / `gov-ai` 공무원 AI

## 처음 한 번 할 일

1. **키 발급 (2개)**
   - 기업마당: 공공데이터포털(data.go.kr)에서 "중소벤처기업부_기업마당 지원사업 정보" 활용신청 → 인증키
   - Gemini: aistudio.google.com → Get API key
2. **GitHub 저장소** 만들고 이 폴더를 push
3. GitHub → Settings → Secrets and variables → Actions 에 `BIZINFO_KEY`, `GEMINI_KEY` 등록
4. **Cloudflare Pages** → Create project → GitHub 저장소 연결
   - Build command: `npm run build`  /  Output directory: `dist`
   - 이후 push 때마다 자동 배포
5. Actions 탭에서 "매일 새벽 수집·초안 생성" → Run workflow 로 첫 수집 테스트

## 매일 하는 일 (5분)

```
git pull
python3 scripts/approve.py      # 초안 목록 보고 번호로 승인, d번호 로 삭제
git add -A && git commit -m "publish" && git push
```

승인된 글만 사이트에 나옵니다. 휴대폰에서 하려면 GitHub 앱에서 파일 열어 `draft: true` → `false` 로 바꿔도 됩니다. (2주차에 텔레그램 승인 봇 예정)

## 로컬 실행

```
npm install && npm run dev            # 사이트 미리보기 http://localhost:4321
pip install -r scripts/requirements.txt
BIZINFO_KEY=... GEMINI_KEY=... python3 scripts/collect.py --dry-run   # 어떤 글이 잡히는지만 확인
```

## 소스 추가

`scripts/sources.yml` 의 `rss:` 에 항목을 추가하면 끝. 대구시 보도자료 RSS 주소는 daegu.go.kr 에서 확인해 주석을 풀면 됩니다.

## 주의

- 기업마당 API 응답 필드명은 2026-09-15 실제 응답으로 확인·반영했습니다(`pblancNm`, `reqstBeginEndDe`="YYYY-MM-DD ~ YYYY-MM-DD", `bsnsSumryCn`은 HTML).
- korea.kr RSS 주소가 바뀌면 사이트 하단 RSS 메뉴에서 새 주소를 확인하세요.
- 보도자료는 공공누리 조건에 따라 출처를 표시합니다. 원문 문장 그대로 싣지 않도록 프롬프트에 고정돼 있습니다.
- 예시 글(`2026-09-13-example-grant.md`)은 첫 수집 후 삭제하세요.
