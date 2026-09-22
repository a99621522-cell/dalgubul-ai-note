# 다잇다 노트

예산부터 공고까지, 대구 기업을 위한 지원사업 연결 기록. Astro 정적 사이트 + Python 수집기 + GitHub Actions.

## 구조

```
src/content/posts/   글(Markdown). draft: true 면 사이트에 안 나옴
src/pages/           첫 화면, 카테고리, 글 본문, RSS
scripts/collect.py   수집 → Gemini 요약 → 초안 저장
scripts/approve.py   초안 승인 도구
scripts/sources.yml  소스·키워드 설정 (API·RSS·게시판 — 여기만 고치면 됨)
scripts/inbox/       외부 크롤러(Claude Code 크롤러 에이전트 등) 결과 JSON 넣는 곳
scripts/state/       중복 방지용 seen.json (자동 생성)
.github/workflows/   매일 05:30 KST 자동 실행
```

카테고리: `economy` 기업 동향 / `grants` 공모·지원사업 / `policy` 산업 정책 (+ 기업 사전 메뉴)

## 처음 한 번 할 일

1. **키 발급 (2개)**
   - 기업마당: 공공데이터포털이 아니라 **기업마당에서 직접 발급**합니다. https://www.bizinfo.go.kr/apiList.do → 통합회원 로그인 → "지원사업정보 API" 의 `사용신청` → 인증키가 화면 하단과 이메일로 옵니다. 붙여넣을 때 끝에 줄바꿈이 딸려 가지 않게 주의(코드에서 strip 하지만).
   - Gemini: aistudio.google.com → Get API key
2. **GitHub 저장소**에 올리기 — 웹 업로드는 폴더 구조가 깨지므로 **GitHub Desktop** 사용
   - GitHub Desktop 설치·로그인 → File → Clone repository → 내 저장소 선택 → Clone
   - Repository → Show in Explorer 로 폴더 열기 → 안의 파일 삭제(`.git`은 남김) → 이 zip 내용물 붙여넣기
   - Desktop 에서 Summary 입력 → Commit to main → Push origin
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

## 소스 추가 (세 가지 방법)

1. **RSS가 있는 곳**: `sources.yml` 의 `rss:` 에 항목 추가
2. **RSS 없는 게시판** (대구시·달성군·대구TP 등): `sources.yml` 의 `boards:` 에 목록 페이지 주소와 `link_pattern`(또는 CSS `item_selector`) 추가. `--dry-run` 으로 잡히는 제목을 확인하며 다듬기. 기본 3개는 주소 확인이 필요한 자리표시 상태
3. **크롤러 에이전트 연동**: 봇 차단·상세 페이지·복잡한 사이트는 Claude Code 웹 크롤러 에이전트로 수집해 `scripts/inbox/*.json` 으로 저장 → 다음 실행 때 자동 흡수. 형식은 `scripts/inbox/README.md`

원칙: 공공기관 사이트(공공누리)만, 하루 1회, 개인정보 없는 글만. 약관으로 수집을 막는 상업 사이트는 소스로 쓰지 않음.

## 주의

- 기업마당 API 응답 필드명은 2026-09-15 실제 응답으로 확인·반영했습니다(`pblancNm`, `reqstBeginEndDe`="YYYY-MM-DD ~ YYYY-MM-DD", `bsnsSumryCn`은 HTML).
- 정책브리핑(korea.kr) RSS는 2026-07-01 서비스가 중단돼 소스에서 뺐습니다(사유: 콘텐츠 저작권 등 권리 보호). 대체 스크래핑도 하지 않습니다. 소스 추가 전에는 robots.txt 와 이용조건을 먼저 확인하세요. 기관별 판정은 `scripts/data/institutions.yml` 의 `blocked` 참고.
- 보도자료는 공공누리 조건에 따라 출처를 표시합니다. 원문 문장 그대로 싣지 않도록 프롬프트에 고정돼 있습니다.
