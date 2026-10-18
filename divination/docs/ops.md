# 운영 체크리스트 — 매화·기문 점풀이 서버

## 1. 구성
- 프로세스 하나(`node src/llm/server.ts`), 상태는 메모리(요청 제한·캐시·집계). 재시작하면 비워진다. 인스턴스를 여러 개 띄우면 제한·캐시가 인스턴스별로 따로 센다(공유가 필요해지면 Redis 같은 저장소로 옮긴다).
- 저장하는 것: 없음. 선택 사용량 로그(`USAGE_LOG`)는 시각·종류·상태·토큰 수·소요 시간·안전 플래그·질문 유형만 적고 질문 본문·IP·결과를 적지 않는다.
- 키: `ANTHROPIC_API_KEY` 는 서버 환경 변수로만. 저장소·이미지·브라우저에 넣지 않는다.

## 2. 환경 변수
`.env.example` 참고. 처음에는 기본값으로 두고, 트래픽을 보고 `MAX_INFLIGHT`·`MAX_DIVINE_PER_DAY`·`RATE_DIVINE_*` 를 조정한다. 리버스 프록시(Cloudflare·nginx·플랫폼 로드밸런서) 뒤에서는 `TRUST_PROXY=1` 이어야 IP 별 제한이 맞게 센다. 화면을 다른 도메인에 둘 때만 `ALLOWED_ORIGIN` 을 그 origin 으로.

## 3. 배포
```
docker build -t daitda-divination .
docker run -d --name divination -p 8787:8787 \
  -e ANTHROPIC_API_KEY=... -e TRUST_PROXY=1 -e METRICS_TOKEN=... \
  --restart unless-stopped daitda-divination
curl -s localhost:8787/health
```
- 컨테이너 플랫폼(Fly.io, Render, Cloud Run, Railway 등)이면 Dockerfile 그대로 쓰고 `PORT` 는 플랫폼이 주는 값을 따른다. 헬스체크 경로 `/health`.
- HTTPS 는 플랫폼 또는 Cloudflare 가 끝낸다. 서버는 HTTP 만 듣는다.
- 이미지 빌드는 이 저장소의 CI 환경에서 확인하지 못했다(Docker 데몬 없음). 첫 배포 전에 로컬에서 한 번 빌드·실행해 `/health` 와 `/api/cast` 를 본다.

### Render (권장 경로, 저장소 루트 `render.yaml`)
1. Render 대시보드 → **New → Blueprint** → GitHub 저장소 `a99621522-cell/dalgubul-ai-note` 연결 → 브랜치 선택(이 작업 브랜치 또는 main 에 합친 뒤 main).
2. 서비스 `daitda-divination` 이 잡히면 **ANTHROPIC_API_KEY** 값을 입력(저장소에는 없음). `METRICS_TOKEN` 은 자동 생성된다.
3. Apply → 빌드(`npm ci --omit=dev`) → 시작(`node src/llm/server.ts`). 헬스체크 `/health` 가 200 이면 공개 주소 `https://daitda-divination.onrender.com` 이 열린다.
4. 열어서 「괘·국 보기」 → 「풀이 받기」 한 번. `/metrics` 는 헤더 `x-metrics-token: <METRICS_TOKEN>` 으로.
5. 커스텀 도메인은 서비스 Settings → Custom Domains 에서 추가하고 DNS 에 CNAME. Cloudflare 존(daitda.co.kr)을 쓰면 `divine.daitda.co.kr` 같은 하위 도메인을 CNAME 으로 걸면 된다.
- 플랜: `starter` 로 두었다. `free` 로 바꾸면 비용은 없지만 15분 유휴 뒤 잠들어 첫 응답이 50초쯤 걸리고 메모리 제한·캐시가 자주 비워진다.
- 환경 변수 값은 `render.yaml` 의 기본값(하루 300건, 동시 3건, IP 당 분당 6·하루 40건)이며 대시보드에서 언제든 바꾼다. 바꾸면 자동 재시작.
- Node 버전은 `NODE_VERSION=22.22.0` 과 `divination/.node-version` 두 곳에 같은 값.

## 4. 비용 어림 (풀이 1건, 두 술법, 검수 포함)
단계 5회 호출(분류·매화·기문·종합·검수). 입력은 시스템 프롬프트(캐시 대상) + 계산 JSON, 출력은 700~1,000자 풀이. 실제 토큰은 평가 스크립트(`src/llm/eval.ts`)로 재고 아래 표를 고친다.

| 항목 | 어림 |
|---|---|
| 입력 토큰 | 약 15,000~20,000 (프롬프트 캐시가 맞으면 그중 절반 이상이 캐시 읽기) |
| 출력 토큰 | 약 4,000~6,000 |
| 시간 | 20~60초 |

모델 단가는 변하므로 콘솔의 현재 단가에 위 토큰을 곱해 1건 비용을 구하고, `MAX_DIVINE_PER_DAY × 1건 비용` 을 하루 상한으로 둔다. 같은 질문·시각·재료는 캐시가 받아 모델을 부르지 않는다.

## 5. 보호 장치가 돌려주는 응답
| 상황 | 상태 | 머리글 |
|---|---|---|
| IP 분당·일별 한도 | 429 | retry-after |
| 서버 하루 상한 | 503 | retry-after 3600 |
| 동시 실행 초과 | 503 | retry-after 15 |
| 모델 거절(refusal) | 422 | stage |
| 입력 오류 | 400 | |
| 서버 오류 | 500 | requestId (로그와 대조) |

화면은 각 상태의 메시지를 그대로 보여 준다.

## 6. 관찰
- `GET /health`: ok·모델·동시 실행 수·캐시 크기. 외부 모니터는 이것만 본다.
- `GET /metrics` (헤더 `x-metrics-token`): 시작 시각, 건수(풀이·계산·캐시 적중·거절·오류·제한·혼잡), 토큰 합, 날짜별 풀이 수·토큰. 하루 한 번 보고 비용과 상한을 맞춘다.
- 로그: 500 만 `requestId` 와 함께 stderr. 질문 본문은 찍지 않는다.

## 7. 사고 대응
- 비용 급증: `MAX_DIVINE_PER_DAY` 를 낮추고 재시작. `/metrics` 의 날짜별 건수로 시각을 좁힌다.
- 키 유출 의심: 콘솔에서 키 폐기·재발급 → 환경 변수 교체 → 재시작. 저장소 이력에 키가 들어간 적이 없는지 확인.
- 모델 오류·지연: `ANTHROPIC_TIMEOUT_MS` 를 늘리기보다 `MAX_INFLIGHT` 를 낮춘다. 거절(422)이 잦은 질문 유형은 분류기·해석가 프롬프트의 안전 문구를 점검한다.
- 위기 응답: 자해 암시 분류는 모델을 더 부르지 않고 109 안내만 낸다. 이 경로가 깨지지 않았는지 배포마다 `tests/llm.test.ts` 로 확인한다.

## 8. 배포 전 점검
1. `npm test` 전부 통과, `npm run typecheck` 통과
2. 키가 들어간 환경에서 `node src/llm/eval.ts --runs 2` 로 방향 안정성·토큰 확인
3. `docker build` 성공, 컨테이너에서 `/health` 200
4. 화면 첫머리·바닥의 참고·오락용 고지와 109 안내가 보이는지
5. `/metrics` 에 토큰이 걸려 있는지, `USAGE_LOG` 경로가 쓰기 가능한지
