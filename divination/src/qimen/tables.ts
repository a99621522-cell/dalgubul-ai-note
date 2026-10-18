// 기문둔갑 고정표. 유파: 시가기문 · 전반(轉盤) · 차보법 · 중궁 기궁 坤2 · 팔신 8개(白虎·玄武)
import type { Element } from '../common/ganzhi.ts';

export const PALACES: Record<number, { trigram: string; ko: string; direction: string; element: Element }> = {
  1: { trigram: '坎', ko: '감', direction: '북', element: '水' },
  2: { trigram: '坤', ko: '곤', direction: '남서', element: '土' },
  3: { trigram: '震', ko: '진', direction: '동', element: '木' },
  4: { trigram: '巽', ko: '손', direction: '남동', element: '木' },
  5: { trigram: '中', ko: '중', direction: '중앙', element: '土' },
  6: { trigram: '乾', ko: '건', direction: '북서', element: '金' },
  7: { trigram: '兌', ko: '태', direction: '서', element: '金' },
  8: { trigram: '艮', ko: '간', direction: '북동', element: '土' },
  9: { trigram: '離', ko: '리', direction: '남', element: '火' },
};
/** 바깥 8궁 시계 방향(坎1 에서 시작) */
export const CW: number[] = [1, 8, 3, 4, 9, 2, 7, 6];
export const OPPOSITE: Record<number, number> = { 1: 9, 9: 1, 2: 8, 8: 2, 3: 7, 7: 3, 4: 6, 6: 4, 5: 5 };
export const CENTER_LODGE = 2;

export const STAR_HOME: Record<number, string> = { 1: '天蓬', 8: '天任', 3: '天衝', 4: '天輔', 9: '天英', 2: '天芮', 7: '天柱', 6: '天心', 5: '天禽' };
export const STAR_ELEMENT: Record<string, Element> = { 天蓬: '水', 天任: '土', 天衝: '木', 天輔: '木', 天英: '火', 天芮: '土', 天禽: '土', 天柱: '金', 天心: '金' };
export const DOOR_HOME: Record<number, string> = { 1: '休門', 8: '生門', 3: '傷門', 4: '杜門', 9: '景門', 2: '死門', 7: '驚門', 6: '開門' };
export const DOOR_ELEMENT: Record<string, Element> = { 休門: '水', 生門: '土', 傷門: '木', 杜門: '木', 景門: '火', 死門: '土', 驚門: '金', 開門: '金' };
export const DEITIES: string[] = ['値符', '螣蛇', '太陰', '六合', '白虎', '玄武', '九地', '九天'];
/** 지반 포국 순서 */
export const EARTH_ORDER: string[] = ['戊', '己', '庚', '辛', '壬', '癸', '丁', '丙', '乙'];
/** 순수 → 육의 */
export const XUN_YI: string[] = ['戊', '己', '庚', '辛', '壬', '癸']; // 甲子 甲戌 甲申 甲午 甲辰 甲寅
export const XUN_KONG: Array<[string, string]> = [['戌', '亥'], ['申', '酉'], ['午', '未'], ['辰', '巳'], ['寅', '卯'], ['子', '丑']];
export const BRANCH_PALACE: Record<string, number> = { 子: 1, 丑: 8, 寅: 8, 卯: 3, 辰: 4, 巳: 4, 午: 9, 未: 2, 申: 2, 酉: 7, 戌: 6, 亥: 6 };
export const HORSE_BRANCH: Record<string, string> = { 申: '寅', 子: '寅', 辰: '寅', 寅: '申', 午: '申', 戌: '申', 巳: '亥', 酉: '亥', 丑: '亥', 亥: '巳', 卯: '巳', 未: '巳' };

/** 절기(황경) → [상원, 중원, 하원] 국수 */
export const JU_TABLE: Record<number, [number, number, number]> = {
  270: [1, 7, 4], 285: [2, 8, 5], 300: [3, 9, 6], 315: [8, 5, 2], 330: [9, 6, 3], 345: [1, 7, 4],
  0: [3, 9, 6], 15: [4, 1, 7], 30: [5, 2, 8], 45: [4, 1, 7], 60: [5, 2, 8], 75: [6, 3, 9],
  90: [9, 3, 6], 105: [8, 2, 5], 120: [7, 1, 4], 135: [2, 5, 8], 150: [1, 4, 7], 165: [9, 3, 6],
  180: [7, 1, 4], 195: [6, 9, 3], 210: [5, 8, 2], 225: [6, 9, 3], 240: [5, 8, 2], 255: [4, 7, 1],
};
export function isYangDun(longitude: number): boolean {
  return longitude >= 270 || longitude < 90;
}

/** 이름 별칭(한글·한자) → 표준 이름 */
export const ALIASES: Record<string, string> = {
  휴문: '休門', 생문: '生門', 상문: '傷門', 두문: '杜門', 경문: '景門', 사문: '死門', 경문_驚: '驚門', 개문: '開門',
  천봉: '天蓬', 천임: '天任', 천충: '天衝', 천보: '天輔', 천영: '天英', 천예: '天芮', 천금: '天禽', 천주: '天柱', 천심: '天心',
  치부: '値符', 직부: '値符', 등사: '螣蛇', 태음: '太陰', 육합: '六合', 백호: '白虎', 현무: '玄武', 구지: '九地', 구천: '九天',
  값: '値符', 值符: '値符', 구진: '白虎', 주작: '玄武',
};
