// 공통: 천간·지지·오행·생극·왕상휴수사. 모든 모듈이 이 표만 쓴다.

export type Element = '木' | '火' | '土' | '金' | '水';
export type Strength = '旺' | '相' | '休' | '囚' | '死';
/** A 가 B 에 대해 갖는 관계: 生(A→B 생), 克(A→B 극), 被生(B→A 생), 被克(B→A 극), 比和 */
export type Rel = '生' | '克' | '被生' | '被克' | '比和';

export const STEMS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'] as const;
export const BRANCHES = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'] as const;
export type Stem = (typeof STEMS)[number];
export type Branch = (typeof BRANCHES)[number];

export const STEM_ELEMENT: Record<Stem, Element> = {
  甲: '木', 乙: '木', 丙: '火', 丁: '火', 戊: '土', 己: '土', 庚: '金', 辛: '金', 壬: '水', 癸: '水',
};
export const BRANCH_ELEMENT: Record<Branch, Element> = {
  子: '水', 丑: '土', 寅: '木', 卯: '木', 辰: '土', 巳: '火', 午: '火', 未: '土', 申: '金', 酉: '金', 戌: '土', 亥: '水',
};

/** 지지 수(매화역수 연지수·시지수): 子1 … 亥12 */
export function branchNumber(b: Branch): number {
  return BRANCHES.indexOf(b) + 1;
}

/** 60갑자 index(0=甲子) → 간지 문자열 */
export function ganzhi(index: number): string {
  const i = ((index % 60) + 60) % 60;
  return STEMS[i % 10] + BRANCHES[i % 12];
}
export function stemOf(gz: string): Stem {
  return gz[0] as Stem;
}
export function branchOf(gz: string): Branch {
  return gz[1] as Branch;
}
export function stemIndex(s: Stem): number {
  return STEMS.indexOf(s);
}
export function branchIndex(b: Branch): number {
  return BRANCHES.indexOf(b);
}
/** 간지 → 60갑자 index */
export function ganzhiIndex(gz: string): number {
  const s = stemIndex(stemOf(gz));
  const b = branchIndex(branchOf(gz));
  for (let i = 0; i < 60; i++) if (i % 10 === s && i % 12 === b) return i;
  throw new Error(`잘못된 간지: ${gz}`);
}

const GEN: Record<Element, Element> = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' }; // 생
const OVC: Record<Element, Element> = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' }; // 극

export function generates(a: Element, b: Element): boolean {
  return GEN[a] === b;
}
export function overcomes(a: Element, b: Element): boolean {
  return OVC[a] === b;
}
/** a 가 b 에 대해 갖는 관계 */
export function relation(a: Element, b: Element): Rel {
  if (a === b) return '比和';
  if (generates(a, b)) return '生';
  if (overcomes(a, b)) return '克';
  if (generates(b, a)) return '被生';
  return '被克';
}

/** 월지로 계절 오행(당령) */
export function seasonElement(monthBranch: Branch): Element {
  switch (monthBranch) {
    case '寅': case '卯': return '木';
    case '巳': case '午': return '火';
    case '申': case '酉': return '金';
    case '亥': case '子': return '水';
    default: return '土'; // 辰戌丑未
  }
}

/** 왕상휴수사: 당령과 같으면 旺, 당령이 나를 생하면 相, 내가 당령을 생하면 休, 내가 당령을 극하면 囚, 당령이 나를 극하면 死 */
export function strength(me: Element, season: Element): Strength {
  if (me === season) return '旺';
  if (generates(season, me)) return '相';
  if (generates(me, season)) return '休';
  if (overcomes(me, season)) return '囚';
  return '死';
}

export const ELEMENT_KO: Record<Element, string> = { 木: '목', 火: '화', 土: '토', 金: '금', 水: '수' };
