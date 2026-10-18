# divination — 매화역수·기문둔갑 계산 엔진

점술 앱의 **계산 엔진**(순수 함수, 외부 의존 없음)과 **해석 파이프라인**(Claude API 호출, `src/llm/`)을 담은 독립 TypeScript 패키지. 계산은 같은 입력이면 항상 같은 JSON 을 내고, 해석은 그 JSON 만 보고 쓴다.
이 저장소의 사이트(Astro, `../src`)와는 코드·빌드가 전혀 연결되어 있지 않다. 다른 저장소로 옮길 때는 이 폴더를 그대로 복사하면 된다.

```
npm install       # @anthropic-ai/sdk, zod (해석 파이프라인에만 필요. 계산 엔진은 의존성 없음)
npm test          # node --test (Node 22.18+ 는 .ts 를 바로 실행). 모델 호출은 가짜로 대체
npm run typecheck # tsc --noEmit (npx 로 typescript 를 받음)
npm run cli -- "이번 달 이직 제안을 받아들여도 될까요" [--at 2026-10-18T14:30+09:00] [--numbers 37,58] [--method both|meihua|qimen|auto] [--dry] [--json]
npm run serve     # http://localhost:8787  POST /api/divine, POST /api/cast, GET /health
```

해석 파이프라인은 `ANTHROPIC_API_KEY`(또는 `ant auth login` 프로필)가 있어야 돌고, 모델은 `DIVINATION_MODEL`(기본 `claude-opus-5-5`)로 바꾼다. `--dry` 와 `/api/cast` 는 계산만 하므로 키가 없어도 된다.

## 해석 파이프라인 (`src/llm/`)

```
질문 ─▶ 분류기(JSON) ─▶ 계산 엔진(코드) ─▶ 매화 해석가 ┐
                │                        기문 해석가 ┴▶ 종합 편집자 ─▶ 검수자(JSON) ─▶ 답
                └─ safety_flag = self_harm 이면 계산·해석 없이 위기 안내(109)만
```

- `prompts/*.md` 프롬프트 5개 + 위기 문구. 시스템 프롬프트는 캐시 표시(`cache_control`), 계산 JSON 은 사용자 메시지로 넣는다.
- `model.ts` `ModelCaller` 인터페이스와 실제 구현 `AnthropicCaller`. 분류기·검수자는 구조화 출력(`beta.messages.parse` + zod), 해석가·편집자는 마크다운. 모든 호출에 서버측 거절 대체(`fallbacks: "default"`)를 켰고, 그래도 `refusal` 이면 `RefusalError`. effort 는 분류·검수 low, 해석·종합 medium.
- `pipeline.ts` `runDivination(req, caller)`: 분류 → 계산 → 해석(병렬) → 종합(둘 다 있을 때만) → 검수. `method` 기본 `both`, `auto` 는 분류기가 고른 하나. 결과에 분류·괘·국·단계별 글·검수 변경 목록·토큰 사용량이 함께 온다. `castOnly()` 는 모델 없이 괘·국만.
- `cli.ts`, `server.ts` 진입점. 서버는 `node:http` 만 쓰고 입력을 길이·형식으로 거른다. 요청·결과를 저장하지 않는다.
- 테스트(`tests/llm.test.ts`)는 가짜 호출자로 단계 순서·안전 분기·종합 조건·검수 반영을 본다. 실제 모델 품질(같은 JSON 에 판단이 흔들리지 않는지)은 키가 있는 환경에서 `npm run cli -- ... --json` 을 여러 번 돌려 `## 한 줄 답` 을 비교한다.

## 쓰는 법

```ts
import { castMeihua, castQimen, castBoth } from './src/index.ts';

const m = castMeihua({ datetime: '2026-10-18T14:30:00+09:00' });                 // 연월일시 기괘
const n = castMeihua({ datetime: '...', material: { numbers: [37, 58] } });       // 숫자 기괘
const t = castMeihua({ datetime: '...', material: { text: '대구' } });            // 글자 획수 기괘
const q = castQimen({ datetime: '2026-10-18T14:30:00+09:00', matter: ['생문', '戊'], yearMing: '庚午' });
const both = castBoth({ datetime: '...', matter: ['생문'] });                     // 같은 시각으로 둘 다
```

옵션(`options`): `localSolar` `'none'|'longitude'|'longitude+eot'`(기본 none, 경도 보정은 `longitude` 필요, 기준 자오선 `standardMeridian` 기본 135), `ziHour` `'23'|'00'`(기본 23: 23시에 시진·일진이 함께 바뀜), `tzOffsetMin`(장소 표준시, 기본 540 = KST; 입력 문자열의 오프셋은 UT 변환에만 쓴다).

## 구조

```
src/common/ganzhi.ts      천간·지지·오행·생극·왕상휴수사
src/calendar/astro.ts     태양 시황경(VSOP87 축약, Meeus)·삭·ΔT·균시차
src/calendar/solarTerms.ts 24절기 시각(연도별 캐시)
src/calendar/lunar.ts     한국 음력(동지 든 달 = 11월, 두 동지 사이 13달이면 첫 무중월이 윤달, KST 일자)
src/calendar/time.ts      ISO 입력 → UT → 유효 지방시 → 시진·일자(자시 옵션)
src/calendar/pillars.ts   연(입춘)·월(節)·일(JDN)·시(두수법) 주
src/meihua/               선천괘수 기괘(연월일시·숫자·글자), 본·호·변괘, 체용, 왕쇠
src/qimen/                시가기문 전반 차보법 포국, 격국 판정표
src/index.ts              castMeihua / castQimen / castBoth
src/llm/                  해석 파이프라인(프롬프트·모델 호출·CLI·서버)
tests/                    달력(한국천문연구원 공표값)·고전 사례(관매점·모란점)·손 포국 사례·파이프라인(가짜 모델)
```

## 정한 것(유파·기준)

| 항목 | 값 | 바꾸는 곳 |
|---|---|---|
| 음력·절기 | 내장 천문 계산(표 없음). 절기 ±1분, 삭 ±1분 안팎 | `astro.ts` |
| 지원 연도 | 1900~2150 (ΔT 다항식 범위) | `solarTerms.ts` |
| 시간 보정 | 기본 없음. 옵션으로 경도·균시차 | `time.ts` |
| 자시 | 기본 23시에 일진 전환 | `time.ts` |
| 매화 괘수 | 乾1 兌2 離3 震4 巽5 坎6 艮7 坤8, 나머지 0→8·6 | `meihua/index.ts` |
| 매화 숫자 기괘 | 1개: 자릿수 반 갈라 앞/뒤, 2개: 앞/뒤, 3개: 셋째가 동효 | `numbersFromNumbers` |
| 글자 획수 | 한글 자모 획수 표 내장(한 가지 통용 방식), 한자는 `strokeTable` 로 | `meihua/strokes.ts` |
| 기문 유파 | 시가기문 · 전반(轉盤) · 차보법 · 중궁 기궁 坤2 · 팔신 8개(白虎·玄武) | `qimen/tables.ts` |
| 원(元) | 일주 부두(甲·己일) 지지: 子午卯酉 상, 辰戌丑未 중, 寅申巳亥 하 | `yuanOf` |
| 국수 표 | 양둔 동지 1·7·4 … 음둔 하지 9·3·6 … | `JU_TABLE` |
| 치사문 이동 | 순수 궁에서 시지까지 숫자 걸음(중궁 포함), 중궁 착지는 坤2 | `buildQimen` |
| 격국 | 吉 三奇得使·三奇得門·靑龍返首·飛鳥跌穴·玉女守門·天遁·地遁·人遁 / 凶 伏吟·反吟·五不遇時·刑格·白虎猖狂·螣蛇夭矯·太白入熒·熒入太白·靑龍逃走·朱雀投江·大格·小格·戰格·伏干格·飛干格·時格·三奇入墓·六儀擊刑·門迫 | `detectFormats` |

유파 차이가 있는 항목은 코드 주석에 ※ 로 적었다(丁 입묘 궁, 丁加癸 가 三奇得使와 朱雀投江에 동시에 걸리는 것 등). 같은 궁의 길·흉 격국은 모두 내보내고 판단은 해석가 프롬프트가 한다.

## 검증 상태

- 통과: 24절기 7건(한국천문연구원 공표 시각과 2분 안), 음력 10건(설날·추석·윤달 2020·2023·2025·2028), 일주 기준일(1900-01-01 甲戌, 2000-01-01 戊午), 입춘·자시·절기 경계, 관매점·모란점, 손으로 포국한 양둔 1국·음둔 9국 사례.
- 미확인(todo): 차보법 교과서 예제, 치윤법과의 차이표, 2033~2034년 윤달. 기대값은 사람이 책·공표값에서 옮긴 뒤 기록한다. 코드가 낸 값을 기대값으로 넣지 않는다.

## 출력 JSON

`MeihuaChart`·`QimenChart` 타입(`src/meihua/index.ts`, `src/qimen/index.ts`)이 해석가 프롬프트의 입력 스키마다. `formats` 에 없는 격국, `palaces` 에 없는 궁 정보는 해석가가 말하지 않도록 프롬프트에 적는다.
