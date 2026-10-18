// 24절기: 연도별 시각(UT 율리우스일) 계산과 캐시. 비교는 항상 시각 단위.
import { jdFromCivil, jdFromJde, jdeFromJd, solveSunLongitude } from './astro.ts';

export interface SolarTerm {
  /** 0=소한(285°) … 23=동지(270°). 민력 한 해(1~12월) 순서 */
  index: number;
  name: string;
  hanja: string;
  longitude: number;
  /** 節(월 경계)이면 true, 中氣면 false */
  isJie: boolean;
  /** UT 율리우스일 */
  jd: number;
}

/** 민력 한 해 순서: 소한부터 동지까지 */
export const TERM_DEFS: Array<[string, string, number]> = [
  ['소한', '小寒', 285], ['대한', '大寒', 300], ['입춘', '立春', 315], ['우수', '雨水', 330],
  ['경칩', '驚蟄', 345], ['춘분', '春分', 0], ['청명', '淸明', 15], ['곡우', '穀雨', 30],
  ['입하', '立夏', 45], ['소만', '小滿', 60], ['망종', '芒種', 75], ['하지', '夏至', 90],
  ['소서', '小暑', 105], ['대서', '大暑', 120], ['입추', '立秋', 135], ['처서', '處暑', 150],
  ['백로', '白露', 165], ['추분', '秋分', 180], ['한로', '寒露', 195], ['상강', '霜降', 210],
  ['입동', '立冬', 225], ['소설', '小雪', 240], ['대설', '大雪', 255], ['동지', '冬至', 270],
];

const cache = new Map<number, SolarTerm[]>();

/** 민력 year 에 드는 24절기(UT JD). 시각은 KST 로 바꿔 비교해도 순서가 같다 */
export function solarTerms(year: number): SolarTerm[] {
  const hit = cache.get(year);
  if (hit) return hit;
  if (year < 1890 || year > 2160) throw new Error(`지원 범위 밖 연도: ${year} (1900~2150)`);
  const jd0 = jdFromCivil(year, 1, 0);
  const out: SolarTerm[] = TERM_DEFS.map(([name, hanja, lon], index) => {
    // 춘분(0°) ≈ 3월 20일(연중 79일) 기준으로 어림한 뒤 뉴턴 반복
    let doy = (79 + (lon / 360) * 365.2422) % 365.2422;
    const guess = jdeFromJd(jd0 + doy);
    const jde = solveSunLongitude(lon, guess);
    return { index, name, hanja, longitude: lon, isJie: index % 2 === 0, jd: jdFromJde(jde) };
  });
  cache.set(year, out);
  return out;
}

/** 시각 jd(UT) 바로 앞(이하)의 節과 그 다음 節. 월주·국수 계산용 */
export function currentJie(jd: number): { jie: SolarTerm; next: SolarTerm } {
  const { y } = civilYearOf(jd);
  const all = [...solarTerms(y - 1), ...solarTerms(y), ...solarTerms(y + 1)].filter((t) => t.isJie);
  for (let i = all.length - 1; i >= 0; i--) {
    if (all[i].jd <= jd) return { jie: all[i], next: all[i + 1] };
  }
  throw new Error('절기 탐색 실패');
}

/** 시각 jd(UT) 바로 앞(이하)의 절기(節·中氣 모두). 기문 국수용 */
export function currentTerm(jd: number): { term: SolarTerm; next: SolarTerm } {
  const { y } = civilYearOf(jd);
  const all = [...solarTerms(y - 1), ...solarTerms(y), ...solarTerms(y + 1)];
  for (let i = all.length - 1; i >= 0; i--) {
    if (all[i].jd <= jd) return { term: all[i], next: all[i + 1] };
  }
  throw new Error('절기 탐색 실패');
}

function civilYearOf(jd: number): { y: number } {
  // KST 기준 연도 (연 경계 근처에서 앞뒤 연도를 모두 보므로 UT/KST 차이는 문제 없음)
  const Z = Math.floor(jd + 9 / 24 + 0.5);
  const alpha = Math.floor((Z - 1867216.25) / 36524.25);
  const A = Z + 1 + alpha - Math.floor(alpha / 4);
  const B = A + 1524;
  const C = Math.floor((B - 122.1) / 365.25);
  const D = Math.floor(365.25 * C);
  const E = Math.floor((B - D) / 30.6001);
  const m = E < 14 ? E - 1 : E - 13;
  return { y: m > 2 ? C - 4716 : C - 4715 };
}
