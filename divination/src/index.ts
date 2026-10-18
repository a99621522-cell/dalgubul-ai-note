// 점술 계산 엔진 진입점. LLM 호출 없음. 같은 입력이면 같은 출력.
import { resolveTime, type TimeOptions, type ResolvedTime } from './calendar/time.ts';
import { pillarsOf } from './calendar/pillars.ts';
import { lunarFromDayNumber } from './calendar/lunar.ts';
import { currentTerm } from './calendar/solarTerms.ts';
import { civilFromJd } from './calendar/astro.ts';
import { branchNumber, branchOf, type Branch } from './common/ganzhi.ts';
import { numbersFromTime, numbersFromNumbers, numbersFromText, buildCore, type MeihuaChart } from './meihua/index.ts';
import { buildQimen, type QimenChart } from './qimen/index.ts';

export type { MeihuaChart } from './meihua/index.ts';
export type { QimenChart, Palace, Format } from './qimen/index.ts';
export type { TimeOptions } from './calendar/time.ts';
export { lunarFromCivil, civilFromLunar, leapMonthOf } from './calendar/lunar.ts';
export { solarTerms } from './calendar/solarTerms.ts';
export { pillarsOf } from './calendar/pillars.ts';
export { resolveTime } from './calendar/time.ts';

export interface CastInput {
  /** ISO 8601, 시간대 포함 권장(없으면 +09:00). 예: 2026-10-18T14:30:00+09:00 */
  datetime: string;
  longitude?: number;
  latitude?: number;
  options?: TimeOptions;
}

export interface MeihuaCastInput extends CastInput {
  /** 기괘 재료. 없으면 연월일시 기괘 */
  material?: { numbers?: number[]; text?: string; strokeTable?: Record<string, number> };
}

export interface QimenCastInput extends CastInput {
  /** 질문자 생년 간지(년명). 양력 생년만 알면 birthYear 로 */
  yearMing?: string | null;
  /** 사안 용신 이름(한글·한자). 예: ['생문','戊'] */
  matter?: string[];
}

function metaBase(t: ResolvedTime, input: CastInput) {
  const tz = `${t.tzOffsetMin >= 0 ? '+' : '-'}${String(Math.floor(Math.abs(t.tzOffsetMin) / 60)).padStart(2, '0')}:${String(Math.abs(t.tzOffsetMin) % 60).padStart(2, '0')}`;
  return {
    castAt: input.datetime, tz, localSolar: t.options.localSolar, ziHour: t.options.ziHour,
    correctionMin: Math.round(t.correctionMin * 10) / 10,
    effectiveLocal: `${t.local.y}-${String(t.local.m).padStart(2, '0')}-${String(t.local.d).padStart(2, '0')} ${String(t.local.hh).padStart(2, '0')}:${String(t.local.mm).padStart(2, '0')}`,
  };
}

export function castMeihua(input: MeihuaCastInput): MeihuaChart {
  const t = resolveTime(input.datetime, input.longitude, input.options);
  const pillars = pillarsOf(t);
  const lunar = lunarFromDayNumber(t.dayNumber);
  const hourNum = t.hourBranchIndex + 1;
  const yearNum = branchNumber(branchOf(pillars.year));
  let nums; let method: MeihuaChart['meta']['method'] = 'time'; let raw: string | null = null;
  if (input.material?.numbers && input.material.numbers.length) {
    nums = numbersFromNumbers(input.material.numbers, hourNum); method = 'number'; raw = input.material.numbers.join(',');
  } else if (input.material?.text) {
    nums = numbersFromText(input.material.text, hourNum, input.material.strokeTable); method = 'text'; raw = input.material.text;
  } else {
    nums = numbersFromTime(yearNum, lunar.month, lunar.day, hourNum);
  }
  const core = buildCore(nums, branchOf(pillars.month) as Branch);
  return {
    meta: { ...metaBase(t, input), lunar, pillars, method, rawMaterial: raw, numberRule: nums.rule },
    ...core,
    numbers: { upper: nums.upper, lower: nums.lower, moving: nums.moving, total: nums.total },
  };
}

export function castQimen(input: QimenCastInput): QimenChart {
  const t = resolveTime(input.datetime, input.longitude, input.options);
  const pillars = pillarsOf(t);
  const { term } = currentTerm(t.jdUT);
  const c = civilFromJd(term.jd + 9 / 24);
  const at = `${c.y}-${String(c.m).padStart(2, '0')}-${String(c.d).padStart(2, '0')} ${String(c.hh).padStart(2, '0')}:${String(c.mm).padStart(2, '0')} KST`;
  const body = buildQimen({ pillars, term: { longitude: term.longitude, name: term.name, at }, yearMing: input.yearMing ?? null, matter: input.matter });
  return {
    meta: { ...metaBase(t, input), school: { family: '時家', plate: '轉盤', method: '拆補', centerLodge: 2 } },
    ...body,
  };
}

/** 같은 시각으로 두 술법을 한 번에 */
export function castBoth(input: MeihuaCastInput & QimenCastInput): { meihua: MeihuaChart; qimen: QimenChart } {
  return { meihua: castMeihua(input), qimen: castQimen(input) };
}
