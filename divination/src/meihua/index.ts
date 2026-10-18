// 매화역수 기괘·체용·호변괘. 입력은 수(數)이고, 시각→수 변환은 cast 가 한다.
import { relation, seasonElement, strength, branchOf, type Branch, type Element, type Rel, type Strength } from '../common/ganzhi.ts';
import { trigramByNumber, trigramByLines, hexagramName, type Trigram } from './trigrams.ts';
import { strokesOfText } from './strokes.ts';
import { objectTrigram, directionTrigram } from './images.ts';

export interface GuaOut {
  name: string; hanja: string;
  upper: { name: string; element: Element; number: number };
  lower: { name: string; element: Element; number: number };
  movingLine: 1 | 2 | 3 | 4 | 5 | 6 | null;
  /** 초효→상효 */
  lines: [number, number, number, number, number, number];
}
export type TiYongRelation = '用生體' | '體生用' | '體克用' | '用克體' | '比和';
/** 호괘·변괘가 체괘에 미치는 관계: 생체(길), 극체(흉), 체생(소모), 체극(소길), 비화 */
export type ToTi = '生體' | '克體' | '體生' | '體克' | '比和';

export interface MeihuaChart {
  meta: {
    castAt: string; tz: string; localSolar: string; ziHour: string; correctionMin: number; effectiveLocal: string;
    lunar: { year: number; month: number; day: number; leap: boolean };
    pillars: { year: string; month: string; day: string; hour: string };
    method: 'time' | 'number' | 'text' | 'object' | 'coins';
    rawMaterial: string | null;
    numberRule: string;
  };
  benGua: GuaOut; huGua: GuaOut; bianGua: GuaOut;
  tiYong: { ti: 'upper' | 'lower'; yong: 'upper' | 'lower'; relation: TiYongRelation };
  seasonStrength: { ti: Strength; yong: Strength };
  /** 호괘 상·하 각각이 체에 미치는 관계 */
  huToTi: { upper: ToTi; lower: ToTi }; bianToTi: ToTi;
  /** 체 자리의 호괘(體互)가 상·하 어느 쪽인지. 體互가 用互보다 중하다(『梅花易數』 體用互變之訣) */
  huRoles: { tiHu: 'upper' | 'lower'; yongHu: 'upper' | 'lower' };
  /** 본괘가 乾爲天·坤爲地면 호괘 대신 변괘의 호괘를 쓴다('乾坤無互 互其變卦') */
  huFromBian: boolean;
  numbers: {
    upper: number; lower: number; moving: number; total: number;
    /** 응기(克應) 기준 수 — 成卦之數(total). 立=그대로, 行=절반(빠름), 坐=두 배(늦음). 단위(일·월·년)는 사안의 멀고 가까움으로 정한다(占卜克應之訣) */
    yingqi: { base: number; fast: number; slow: number };
  };
}

export interface MeihuaNumbers { upper: number; lower: number; moving: number; total: number; rule: string }

function mod(n: number, m: number): number { const r = n % m; return r === 0 ? m : r; }

/** 연월일시 기괘: 연지수+음력월+음력일 → 상괘, +시지수 → 하괘·동효 */
export function numbersFromTime(yearBranchNum: number, lunarMonth: number, lunarDay: number, hourBranchNum: number): MeihuaNumbers {
  const a = yearBranchNum + lunarMonth + lunarDay;
  const b = a + hourBranchNum;
  return { upper: mod(a, 8), lower: mod(b, 8), moving: mod(b, 6), total: b, rule: '연월일시: 상괘=(연지수+월+일) mod 8, 하괘=(연지수+월+일+시지수) mod 8, 동효=(연지수+월+일+시지수) mod 6' };
}

/**
 * 숫자 기괘. 1개: 자릿수를 반으로(홀수면 앞이 한 자리 적게) 앞=상괘 뒤=하괘, 동효=전체 자릿수 합+시지수.
 * 2개: 앞=상괘 뒤=하괘, 동효=합+시지수. 3개 이상: 첫째 상괘, 둘째 하괘, 셋째 동효(시지수 더하지 않음).
 */
export function numbersFromNumbers(nums: number[], hourBranchNum: number): MeihuaNumbers {
  if (nums.length === 0 || nums.some((n) => !Number.isInteger(n) || n < 0)) throw new Error('0 이상의 정수가 필요합니다');
  if (nums.length === 1) {
    const s = String(nums[0]);
    if (s.length < 2) {
      // 한 자리 수: 그 수를 상괘·하괘 모두에 쓰고 동효는 수+시지수
      const n = nums[0];
      return { upper: mod(n, 8), lower: mod(n, 8), moving: mod(n + hourBranchNum, 6), total: n + hourBranchNum, rule: '숫자 1개(한 자리): 상괘=하괘=수, 동효=수+시지수' };
    }
    const cut = Math.floor(s.length / 2);
    const front = Number(s.slice(0, cut)), back = Number(s.slice(cut));
    const digitSum = Array.from(s).reduce((t, c) => t + Number(c), 0);
    return { upper: mod(front, 8), lower: mod(back, 8), moving: mod(digitSum + hourBranchNum, 6), total: digitSum + hourBranchNum, rule: '숫자 1개: 앞 자리=상괘, 뒤 자리=하괘, 동효=자릿수 합+시지수' };
  }
  if (nums.length === 2) {
    const total = nums[0] + nums[1] + hourBranchNum;
    return { upper: mod(nums[0], 8), lower: mod(nums[1], 8), moving: mod(total, 6), total, rule: '숫자 2개: 첫째=상괘, 둘째=하괘, 동효=합+시지수' };
  }
  return { upper: mod(nums[0], 8), lower: mod(nums[1], 8), moving: mod(nums[2], 6), total: nums[0] + nums[1] + nums[2], rule: '숫자 3개: 첫째=상괘, 둘째=하괘, 셋째=동효' };
}

/**
 * 글자 획수 기괘(『梅花易數』 卷一 字占): 글자 수가 짝수면 반으로, 홀수면 앞이 한 글자 적게 나눠 앞 획수 합=상괘, 뒤=하괘,
 * 동효=두 괘 획수 총합 mod 6 (시지수를 더하지 않는다 — '又合二卦總數取爻', 西林寺額占 7+8=15→3효).
 * 글자 1개는 원문이 좌우 획을 나누지만 여기서는 상·하괘를 같은 획수로 두고 동효만 총획으로 본다.
 */
export function numbersFromText(text: string, _hourBranchNum: number, table?: Record<string, number>): MeihuaNumbers {
  const strokes = strokesOfText(text, table);
  if (strokes.length === 0) throw new Error('글자가 없습니다');
  if (strokes.length === 1) {
    const n = strokes[0];
    return { upper: mod(n, 8), lower: mod(n, 8), moving: mod(n, 6), total: n, rule: '글자 1개: 상괘=하괘=획수, 동효=획수 (원문은 좌우 획 분리)' };
  }
  const cut = Math.floor(strokes.length / 2);
  const front = strokes.slice(0, cut).reduce((a, b) => a + b, 0);
  const back = strokes.slice(cut).reduce((a, b) => a + b, 0);
  const total = front + back;
  return { upper: mod(front, 8), lower: mod(back, 8), moving: mod(total, 6), total, rule: '글자 획수(字占): 앞 글자 획수 합=상괘, 뒤=하괘, 동효=총획(시지수 없음)' };
}

/**
 * 단법후천 기괘(『梅花易數』 物卦起例·占動物): 보인 사물(사람·동물·색)의 괘를 상괘, 그것이 있던/온 방위의 괘를 하괘로,
 * 두 괘수에 시지수를 더해 동효. 老人有憂色占(乾1 上·巽5 下·卯4 → 姤 四爻)이 이 법.
 */
export function numbersFromObject(object: string, direction: string, hourBranchNum: number): MeihuaNumbers & { upperHit: string; lowerHit: string } {
  const o = objectTrigram(object);
  if (!o) throw new Error(`물상 사전에 없는 낱말: ${object}`);
  const d = directionTrigram(direction) ?? objectTrigram(direction);
  if (!d) throw new Error(`방위(또는 하괘 낱말)를 알 수 없음: ${direction}`);
  const un = trigramNumber(o.trigram), ln = trigramNumber(d.trigram);
  const total = un + ln + hourBranchNum;
  return { upper: un, lower: ln, moving: mod(total, 6), total, rule: `단법후천: ${o.matched}=${o.trigram}(${un}) 상괘, ${d.matched}=${d.trigram}(${ln}) 하괘, 동효=(${un}+${ln}+시지수 ${hourBranchNum}) mod 6`, upperHit: o.matched, lowerHit: d.matched };
}
function trigramNumber(name: string): number { return ['乾', '兌', '離', '震', '巽', '坎', '艮', '坤'].indexOf(name) + 1; }

export type CoinLines = [0 | 1, 0 | 1, 0 | 1];
/**
 * 동전 기괘(물수점의 변형): 동전 3개를 던져 앞=양(1)·뒤=음(0)으로 효 셋(초효→상효)을 얻어 하괘, 다시 던져 상괘.
 * 동효는 『梅花易數』 물수점대로 (상괘수+하괘수+시지수) mod 6 — 체용을 위해 동효를 하나로 둔다(전통 척전법과 다름).
 */
export function numbersFromCoins(lower: CoinLines, upper: CoinLines, hourBranchNum: number): MeihuaNumbers {
  for (const arr of [lower, upper]) if (arr.length !== 3 || arr.some((b) => b !== 0 && b !== 1)) throw new Error('동전 효는 0|1 세 개여야 합니다');
  const up = trigramNumber(trigramByLines(upper).name), lo = trigramNumber(trigramByLines(lower).name);
  const total = up + lo + hourBranchNum;
  return { upper: up, lower: lo, moving: mod(total, 6), total, rule: '동전 기괘: 앞=양 뒤=음, 하괘 3효 → 상괘 3효, 동효=(상괘수+하괘수+시지수) mod 6' };
}

function guaOut(upper: Trigram, lower: Trigram, movingLine: GuaOut['movingLine']): GuaOut {
  const n = hexagramName(upper, lower);
  return {
    name: n.ko, hanja: n.hanja,
    upper: { name: upper.name, element: upper.element, number: upper.number },
    lower: { name: lower.name, element: lower.element, number: lower.number },
    movingLine,
    lines: [...lower.lines, ...upper.lines] as GuaOut['lines'],
  };
}

export interface MeihuaCore {
  benGua: GuaOut; huGua: GuaOut; bianGua: GuaOut;
  tiYong: MeihuaChart['tiYong'];
  seasonStrength: MeihuaChart['seasonStrength'];
  huToTi: { upper: ToTi; lower: ToTi }; bianToTi: ToTi;
  huRoles: MeihuaChart['huRoles'];
  huFromBian: boolean;
}

function toTi(other: Element, ti: Element): ToTi {
  const r: Rel = relation(other, ti);
  return r === '生' ? '生體' : r === '克' ? '克體' : r === '被生' ? '體生' : r === '被克' ? '體克' : '比和';
}

/** 괘수(상·하·동효)와 월지로 본괘·호괘·변괘·체용·왕쇠를 만든다 */
export function buildCore(num: { upper: number; lower: number; moving: number }, monthBranch: Branch): MeihuaCore {
  const upper = trigramByNumber(num.upper);
  const lower = trigramByNumber(num.lower);
  const moving = num.moving as 1 | 2 | 3 | 4 | 5 | 6;
  const ben = guaOut(upper, lower, moving);
  const l = ben.lines;
  // 변괘: 동효 반전
  const bl = [...l] as GuaOut['lines'];
  bl[moving - 1] = bl[moving - 1] === 1 ? 0 : 1;
  const bian = guaOut(trigramByLines([bl[3], bl[4], bl[5]]), trigramByLines([bl[0], bl[1], bl[2]]), null);
  // 호괘: 2·3·4효 → 하호괘, 3·4·5효 → 상호괘. 본괘가 乾爲天·坤爲地면 변괘의 호괘('乾坤無互，互其變卦')
  const huFromBian = ben.hanja === '乾爲天' || ben.hanja === '坤爲地';
  const src = huFromBian ? bl : l;
  const huLower = trigramByLines([src[1], src[2], src[3]]);
  const huUpper = trigramByLines([src[2], src[3], src[4]]);
  const hu = guaOut(huUpper, huLower, null);
  // 체용: 동효가 있는 괘가 용
  const yongIsUpper = moving >= 4;
  const ti = yongIsUpper ? lower : upper;
  const yong = yongIsUpper ? upper : lower;
  const r = relation(yong.element, ti.element);
  const tiYongRel: TiYongRelation = r === '生' ? '用生體' : r === '克' ? '用克體' : r === '被生' ? '體生用' : r === '被克' ? '體克用' : '比和';
  const season = seasonElement(monthBranch);
  // 변괘에서 체는 그대로, 용 자리의 괘가 바뀐다 → 변괘의 용 자리 괘로 체에 대한 관계
  const bianYong = yongIsUpper ? bian.upper : bian.lower;
  return {
    benGua: ben, huGua: hu, bianGua: bian,
    tiYong: { ti: yongIsUpper ? 'lower' : 'upper', yong: yongIsUpper ? 'upper' : 'lower', relation: tiYongRel },
    seasonStrength: { ti: strength(ti.element, season), yong: strength(yong.element, season) },
    huToTi: { upper: toTi(hu.upper.element as Element, ti.element), lower: toTi(hu.lower.element as Element, ti.element) },
    bianToTi: toTi(bianYong.element as Element, ti.element),
    huRoles: yongIsUpper ? { tiHu: 'lower', yongHu: 'upper' } : { tiHu: 'upper', yongHu: 'lower' },
    huFromBian,
  };
}

export { branchOf };
