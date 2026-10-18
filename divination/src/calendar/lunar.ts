// 한국 음력(시헌력 규칙, KST 일자 기준): 동지가 든 달이 11월, 두 11월 사이에 13개 달이면 첫 무중월(中氣 없는 달)이 윤달.
// 날짜 비교는 KST 민력 일자(JDN)로 한다. 한국천문연구원 공표 음력과 대조한 값은 tests/ 에.
// 알려진 한계: 2033~2034년처럼 무중월이 둘 이상 생기는 해는 규칙 해석이 갈린다(한국천문연구원 공표값을 따로 확인).
import { jdFromJde, newMoonJde, approxNewMoonK, jdFromCivil } from './astro.ts';
import { solarTerms } from './solarTerms.ts';

export interface LunarDate { year: number; month: number; day: number; leap: boolean }

/** UT 율리우스일 → KST 민력 일자의 JDN(정수) */
export function kstDayNumber(jdUT: number): number {
  return Math.floor(jdUT + 9 / 24 + 0.5);
}
/** 민력 y-m-d(KST) → JDN */
export function dayNumberOf(y: number, m: number, d: number): number {
  return Math.floor(jdFromCivil(y, m, d) + 0.5);
}
export function civilOfDayNumber(jdn: number): { y: number; m: number; d: number } {
  const Z = jdn;
  const alpha = Math.floor((Z - 1867216.25) / 36524.25);
  const A = Z + 1 + alpha - Math.floor(alpha / 4);
  const B = A + 1524;
  const C = Math.floor((B - 122.1) / 365.25);
  const D = Math.floor(365.25 * C);
  const E = Math.floor((B - D) / 30.6001);
  const d = B - D - Math.floor(30.6001 * E);
  const m = E < 14 ? E - 1 : E - 13;
  const y = m > 2 ? C - 4716 : C - 4715;
  return { y, m, d };
}

interface LunarMonth { start: number; end: number; year: number; month: number; leap: boolean }

const suiteCache = new Map<number, LunarMonth[]>();

/** 민력 Y 년 동지가 든 11월부터 Y+1 년 동지 직전 달까지의 음력 달 목록 */
function suite(Y: number): LunarMonth[] {
  const hit = suiteCache.get(Y);
  if (hit) return hit;
  const ws0 = kstDayNumber(solarTerms(Y)[23].jd);
  const ws1 = kstDayNumber(solarTerms(Y + 1)[23].jd);
  // 삭 일자 목록: Y년 10월 ~ Y+2년 2월
  const moons: number[] = [];
  for (let k = approxNewMoonK(Y, 10) - 1; k <= approxNewMoonK(Y + 2, 2) + 1; k++) {
    moons.push(kstDayNumber(jdFromJde(newMoonJde(k))));
  }
  const idx0 = moons.findIndex((s, i) => s <= ws0 && moons[i + 1] > ws0);
  const idx1 = moons.findIndex((s, i) => s <= ws1 && moons[i + 1] > ws1);
  if (idx0 < 0 || idx1 < 0) throw new Error('동지가 든 달을 찾지 못함');
  const count = idx1 - idx0; // 11월(Y) 부터 11월(Y+1) 직전까지 달 수: 12 또는 13
  // 中氣 일자(KST): Y년·Y+1년·Y+2년
  const zhongqi: number[] = [];
  for (const yy of [Y, Y + 1, Y + 2]) for (const t of solarTerms(yy)) if (!t.isJie) zhongqi.push(kstDayNumber(t.jd));
  const out: LunarMonth[] = [];
  let leapUsed = false;
  let num = 11; // 첫 달은 11월
  for (let i = idx0; i < idx1; i++) {
    const start = moons[i], end = moons[i + 1];
    const hasZhongqi = zhongqi.some((z) => z >= start && z < end);
    let leap = false;
    if (count === 13 && !leapUsed && i > idx0 && !hasZhongqi) {
      leap = true; leapUsed = true;
    } else if (i > idx0) {
      num = num === 12 ? 1 : num + 1;
    }
    const year = num >= 11 ? Y : Y + 1;
    out.push({ start, end, year, month: num, leap });
  }
  suiteCache.set(Y, out);
  return out;
}

/** KST 민력 일자(JDN) → 음력 */
export function lunarFromDayNumber(jdn: number): LunarDate {
  const { y } = civilOfDayNumber(jdn);
  for (const Y of [y, y - 1]) {
    const s = suite(Y);
    if (jdn >= s[0].start && jdn < s[s.length - 1].end) {
      const m = s.find((mm) => jdn >= mm.start && jdn < mm.end)!;
      return { year: m.year, month: m.month, day: jdn - m.start + 1, leap: m.leap };
    }
  }
  throw new Error('음력 변환 실패');
}

export function lunarFromCivil(y: number, m: number, d: number): LunarDate {
  return lunarFromDayNumber(dayNumberOf(y, m, d));
}

/** 음력 → 민력(KST). 윤달 요청인데 그 해에 그 윤달이 없으면 오류 */
export function civilFromLunar(l: LunarDate): { y: number; m: number; d: number } {
  for (const Y of [l.year - 1, l.year]) {
    const s = suite(Y);
    const m = s.find((mm) => mm.year === l.year && mm.month === l.month && mm.leap === l.leap);
    if (m) {
      if (l.day < 1 || l.day > m.end - m.start) throw new Error('그 달에 없는 날');
      return civilOfDayNumber(m.start + l.day - 1);
    }
  }
  throw new Error(`음력 ${l.year}-${l.leap ? '윤' : ''}${l.month}-${l.day} 없음`);
}

/** 그 해의 윤달 번호(없으면 null) */
export function leapMonthOf(lunarYear: number): number | null {
  for (const Y of [lunarYear - 1, lunarYear]) {
    const m = suite(Y).find((mm) => mm.year === lunarYear && mm.leap);
    if (m) return m.month;
  }
  return null;
}
