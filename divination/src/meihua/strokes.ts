// 글자 획수 기괘용 획수 표. 한글은 자모 획수를 더한다(아래 표는 한 가지 통용 방식이며 options.strokeTable 로 바꿀 수 있다).
// 한자는 표가 없으면 오류를 내고, 호출자가 strokeTable 로 강희자전 획수를 넘긴다.
const CHO = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'];
const JUNG = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ'];
const JONG = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'];

const JAMO: Record<string, number> = {
  ㄱ: 1, ㄴ: 1, ㄷ: 2, ㄹ: 3, ㅁ: 3, ㅂ: 4, ㅅ: 2, ㅇ: 1, ㅈ: 3, ㅊ: 4, ㅋ: 2, ㅌ: 3, ㅍ: 4, ㅎ: 3,
  ㄲ: 2, ㄸ: 4, ㅃ: 8, ㅆ: 4, ㅉ: 6,
  ㄳ: 3, ㄵ: 4, ㄶ: 4, ㄺ: 4, ㄻ: 6, ㄼ: 7, ㄽ: 5, ㄾ: 6, ㄿ: 7, ㅀ: 6, ㅄ: 6,
  ㅏ: 2, ㅐ: 3, ㅑ: 3, ㅒ: 4, ㅓ: 2, ㅔ: 3, ㅕ: 3, ㅖ: 4, ㅗ: 2, ㅘ: 4, ㅙ: 5, ㅚ: 3, ㅛ: 3,
  ㅜ: 2, ㅝ: 4, ㅞ: 5, ㅟ: 3, ㅠ: 3, ㅡ: 1, ㅢ: 2, ㅣ: 1,
};

export function strokesOfChar(ch: string, table?: Record<string, number>): number {
  if (table && ch in table) return table[ch];
  const code = ch.codePointAt(0)!;
  if (code >= 0xac00 && code <= 0xd7a3) {
    const i = code - 0xac00;
    const cho = CHO[Math.floor(i / 588)], jung = JUNG[Math.floor((i % 588) / 28)], jong = JONG[i % 28];
    return JAMO[cho] + JAMO[jung] + (jong ? JAMO[jong] : 0);
  }
  if (ch in JAMO) return JAMO[ch];
  if (/\d/.test(ch)) return Number(ch);
  if (/[A-Za-z]/.test(ch)) return 1; // 라틴 글자는 한 획으로 센다(선택 사항)
  throw new Error(`획수 표에 없는 글자: ${ch} (strokeTable 로 넘기세요)`);
}

export function strokesOfText(text: string, table?: Record<string, number>): number[] {
  return Array.from(text.replace(/\s+/g, '')).map((c) => strokesOfChar(c, table));
}
