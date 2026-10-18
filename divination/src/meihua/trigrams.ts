// 팔괘·64괘 표. 선천괘수 乾1 兌2 離3 震4 巽5 坎6 艮7 坤8. 효는 아래(초효)부터 [1,1,1] 꼴(1=양).
import type { Element } from '../common/ganzhi.ts';

export type TrigramName = '乾' | '兌' | '離' | '震' | '巽' | '坎' | '艮' | '坤';
export interface Trigram { name: TrigramName; ko: string; element: Element; number: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8; lines: [0 | 1, 0 | 1, 0 | 1] }

export const TRIGRAMS: Trigram[] = [
  { name: '乾', ko: '건', element: '金', number: 1, lines: [1, 1, 1] },
  { name: '兌', ko: '태', element: '金', number: 2, lines: [1, 1, 0] },
  { name: '離', ko: '리', element: '火', number: 3, lines: [1, 0, 1] },
  { name: '震', ko: '진', element: '木', number: 4, lines: [1, 0, 0] },
  { name: '巽', ko: '손', element: '木', number: 5, lines: [0, 1, 1] },
  { name: '坎', ko: '감', element: '水', number: 6, lines: [0, 1, 0] },
  { name: '艮', ko: '간', element: '土', number: 7, lines: [0, 0, 1] },
  { name: '坤', ko: '곤', element: '土', number: 8, lines: [0, 0, 0] },
];

export function trigramByNumber(n: number): Trigram {
  const t = TRIGRAMS[((n - 1) % 8 + 8) % 8];
  return t;
}
export function trigramByLines(lines: [number, number, number]): Trigram {
  const t = TRIGRAMS.find((x) => x.lines[0] === lines[0] && x.lines[1] === lines[1] && x.lines[2] === lines[2]);
  if (!t) throw new Error('괘 효 오류');
  return t;
}

/** 64괘 이름 [상괘][하괘] 순서는 乾兌離震巽坎艮坤 */
const HEX_HANJA: string[][] = [
  ['乾爲天', '天澤履', '天火同人', '天雷无妄', '天風姤', '天水訟', '天山遯', '天地否'],
  ['澤天夬', '兌爲澤', '澤火革', '澤雷隨', '澤風大過', '澤水困', '澤山咸', '澤地萃'],
  ['火天大有', '火澤睽', '離爲火', '火雷噬嗑', '火風鼎', '火水未濟', '火山旅', '火地晉'],
  ['雷天大壯', '雷澤歸妹', '雷火豊', '震爲雷', '雷風恒', '雷水解', '雷山小過', '雷地豫'],
  ['風天小畜', '風澤中孚', '風火家人', '風雷益', '巽爲風', '風水渙', '風山漸', '風地觀'],
  ['水天需', '水澤節', '水火旣濟', '水雷屯', '水風井', '坎爲水', '水山蹇', '水地比'],
  ['山天大畜', '山澤損', '山火賁', '山雷頤', '山風蠱', '山水蒙', '艮爲山', '山地剝'],
  ['地天泰', '地澤臨', '地火明夷', '地雷復', '地風升', '地水師', '地山謙', '坤爲地'],
];
const HEX_KO: string[][] = [
  ['건위천', '천택리', '천화동인', '천뢰무망', '천풍구', '천수송', '천산돈', '천지비'],
  ['택천쾌', '태위택', '택화혁', '택뢰수', '택풍대과', '택수곤', '택산함', '택지췌'],
  ['화천대유', '화택규', '이위화', '화뢰서합', '화풍정', '화수미제', '화산려', '화지진'],
  ['뇌천대장', '뇌택귀매', '뇌화풍', '진위뢰', '뇌풍항', '뇌수해', '뇌산소과', '뇌지예'],
  ['풍천소축', '풍택중부', '풍화가인', '풍뢰익', '손위풍', '풍수환', '풍산점', '풍지관'],
  ['수천수', '수택절', '수화기제', '수뢰둔', '수풍정', '감위수', '수산건', '수지비'],
  ['산천대축', '산택손', '산화비', '산뢰이', '산풍고', '산수몽', '간위산', '산지박'],
  ['지천태', '지택림', '지화명이', '지뢰복', '지풍승', '지수사', '지산겸', '곤위지'],
];

export function hexagramName(upper: Trigram, lower: Trigram): { hanja: string; ko: string } {
  return { hanja: HEX_HANJA[upper.number - 1][lower.number - 1], ko: HEX_KO[upper.number - 1][lower.number - 1] };
}

/** 팔괘 물상(해석가 프롬프트의 표와 같은 범위만) */
export const TRIGRAM_IMAGES: Record<TrigramName, string[]> = {
  乾: ['하늘', '아버지', '윗사람', '관청', '금속', '둥근 것'],
  兌: ['연못', '소녀', '입', '구설', '기쁨', '음식'],
  離: ['불', '문서', '눈', '중녀', '전기', '밝음'],
  震: ['우레', '장남', '움직임', '놀람', '소리', '차량'],
  巽: ['바람', '장녀', '왕래', '이익', '소식', '나무'],
  坎: ['물', '중남', '험난', '도둑', '술', '숨김'],
  艮: ['산', '소남', '정지', '막힘', '건물', '문지방'],
  坤: ['땅', '어머니', '토지', '무리', '순종', '옷감'],
};
