# divination — 매화역수·기문둔갑 계산 엔진

점술 앱의 **계산** 부분만 담은 독립 TypeScript 패키지. LLM 호출이 없고 외부 의존성도 없다. 같은 입력이면 항상 같은 JSON 을 낸다. 해석(풀이 문장)은 이 JSON 을 받는 LLM 프롬프트의 몫이다.
이 저장소의 사이트(Astro, `../src`)와는 코드·빌드가 전혀 연결되어 있지 않다. 다른 저장소로 옮길 때는 이 폴더를 그대로 복사하면 된다.

```
npm test          # node --test (Node 22.18+ 는 .ts 를 바로 실행)
npm run typecheck # npx typescript 로 tsc --noEmit (네트워크 필요)
```

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
tests/                    달력(한국천문연구원 공표값)·고전 사례(관매점·모란점)·손 포국 사례
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
