// 사주(연·월·일·시주). 연주는 입춘 시각, 월주는 節 시각, 일주는 KST 일자(자시 옵션 반영), 시주는 일간 두수법.
import { ganzhi, ganzhiIndex, stemIndex, stemOf, type Branch, BRANCHES } from '../common/ganzhi.ts';
import { solarTerms, currentJie } from './solarTerms.ts';
import type { ResolvedTime } from './time.ts';

export interface Pillars { year: string; month: string; day: string; hour: string }

/** 입춘 기준 연주 */
export function yearPillar(jdUT: number): string {
  // KST 연도 어림: jd 를 KST 로 옮겨 연도 추정
  const kst = jdUT + 9 / 24;
  const Z = Math.floor(kst + 0.5);
  const alpha = Math.floor((Z - 1867216.25) / 36524.25);
  const A = Z + 1 + alpha - Math.floor(alpha / 4);
  const B = A + 1524;
  const C = Math.floor((B - 122.1) / 365.25);
  const D = Math.floor(365.25 * C);
  const E = Math.floor((B - D) / 30.6001);
  const m = E < 14 ? E - 1 : E - 13;
  let y = m > 2 ? C - 4716 : C - 4715;
  const lichun = solarTerms(y)[2].jd;
  if (jdUT < lichun) y -= 1;
  return ganzhi(((y - 4) % 60 + 60) % 60);
}

const JIE_BRANCH: Record<number, Branch> = { 315: '寅', 345: '卯', 15: '辰', 45: '巳', 75: '午', 105: '未', 135: '申', 165: '酉', 195: '戌', 225: '亥', 255: '子', 285: '丑' };
const MONTH_STEM_BASE = [2, 4, 6, 8, 0]; // 甲己→丙, 乙庚→戊, 丙辛→庚, 丁壬→壬, 戊癸→甲 (寅월 천간)

/** 節 기준 월주 */
export function monthPillar(jdUT: number, yearGz: string): string {
  const { jie } = currentJie(jdUT);
  const branch = JIE_BRANCH[jie.longitude];
  const order = (BRANCHES.indexOf(branch) - 2 + 12) % 12; // 寅=0
  const base = MONTH_STEM_BASE[stemIndex(stemOf(yearGz)) % 5];
  const stem = (base + order) % 10;
  return ganzhi(findGz(stem, BRANCHES.indexOf(branch)));
}

/** KST 일자(JDN) → 일주. 1900-01-01 = 甲戌, 2000-01-01 = 戊午 */
export function dayPillarFromDayNumber(jdn: number): string {
  return ganzhi(((jdn + 49) % 60 + 60) % 60);
}

const HOUR_STEM_BASE = [0, 2, 4, 6, 8]; // 甲己→甲子, 乙庚→丙子, 丙辛→戊子, 丁壬→庚子, 戊癸→壬子

export function hourPillar(dayGz: string, hourBranchIndex: number): string {
  const base = HOUR_STEM_BASE[stemIndex(stemOf(dayGz)) % 5];
  const stem = (base + hourBranchIndex) % 10;
  return ganzhi(findGz(stem, hourBranchIndex));
}

function findGz(stem: number, branch: number): number {
  for (let i = 0; i < 60; i++) if (i % 10 === stem && i % 12 === branch) return i;
  throw new Error('간지 조합 불가');
}

export function pillarsOf(t: ResolvedTime): Pillars {
  const year = yearPillar(t.jdUT);
  const month = monthPillar(t.jdUT, year);
  const day = dayPillarFromDayNumber(t.dayNumber);
  const hour = hourPillar(day, t.hourBranchIndex);
  return { year, month, day, hour };
}

export { ganzhiIndex };
