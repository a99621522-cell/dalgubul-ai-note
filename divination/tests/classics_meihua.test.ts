// 『梅花易數』(邵雍 撰으로 전함, 공유 저작물) 卷一 「象數易理篇」의 점례·기괘 규칙과 대조. 中文維基文庫 https://zh.wikisource.org/wiki/梅花易數/卷一
// 날짜가 아니라 수(數)로 기괘하므로 numbersFrom* + buildCore 로 달력과 무관하게 검증한다.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { numbersFromTime, numbersFromNumbers, numbersFromText, buildCore } from '../src/meihua/index.ts';
import { TRIGRAMS } from '../src/meihua/trigrams.ts';
import { seasonElement, strength } from '../src/common/ganzhi.ts';

type Core = ReturnType<typeof buildCore>;
const hu = (c: Core) => `${c.huGua.upper.name}${c.huGua.lower.name}`;

test('周易卦數·卦以八除·爻以六除: 乾1兌2離3震4巽5坎6艮7坤8, 8의 배수는 坤, 6의 배수는 6효', () => {
  assert.equal(TRIGRAMS.map((t) => t.name).join(''), '乾兌離震巽坎艮坤');
  const n = numbersFromNumbers([16, 24], 0);
  assert.deepEqual([n.upper, n.lower, n.moving], [8, 8, 4]); // 40 mod 6 = 4
  const m = numbersFromNumbers([8, 10], 0); // 18 → 6효
  assert.equal(m.moving, 6);
});

test('卦氣旺·卦氣衰: 봄 震巽 旺·坤艮 衰, 여름 離 旺·乾兌 衰, 가을 乾兌 旺·震巽 衰, 겨울 坎 旺·離 衰, 辰戌丑未 坤艮 旺·坎 衰', () => {
  const chk = (branch: Parameters<typeof seasonElement>[0], wang: string[], shuai: string[]) => {
    const season = seasonElement(branch);
    for (const t of TRIGRAMS) {
      const st = strength(t.element, season);
      if (wang.includes(t.name)) assert.equal(st, '旺', `${branch} ${t.name}`);
      if (shuai.includes(t.name)) assert.equal(st, '死', `${branch} ${t.name}`);
    }
  };
  chk('寅', ['震', '巽'], ['坤', '艮']); chk('午', ['離'], ['乾', '兌']); chk('酉', ['乾', '兌'], ['震', '巽']);
  chk('子', ['坎'], ['離']); chk('辰', ['坤', '艮'], ['坎']);
});

test('觀梅占(年月日時): 辰年12月17日申時 → 澤火革 初爻, 변 咸, 호 乾巽, 兌金 체·離火 용 克體', () => {
  const c = buildCore(numbersFromTime(5, 12, 17, 9), '丑');
  assert.equal(c.benGua.hanja, '澤火革'); assert.equal(c.benGua.movingLine, 1);
  assert.equal(c.bianGua.hanja, '澤山咸'); assert.equal(hu(c), '乾巽');
  assert.deepEqual(c.tiYong, { ti: 'upper', yong: 'lower', relation: '用克體' });
  assert.equal(c.bianToTi, '生體'); // '幸變為艮土，兌金得生'
  assert.equal(c.huRoles.tiHu, 'upper'); // 體用互變之訣: 兌為體 → 上互(乾)가 體互
});

test('牡丹占(年月日時): 巳年3月16日卯時 → 天風姤 五爻, 변 鼎, 호 重乾, 巽木 체·乾金 용 克體', () => {
  const c = buildCore(numbersFromTime(6, 3, 16, 4), '辰');
  assert.equal(c.benGua.hanja, '天風姤'); assert.equal(c.benGua.movingLine, 5);
  assert.equal(c.bianGua.hanja, '火風鼎'); assert.equal(hu(c), '乾乾');
  assert.deepEqual(c.tiYong, { ti: 'lower', yong: 'upper', relation: '用克體' });
  assert.deepEqual(c.huToTi, { upper: '克體', lower: '克體' }); // '互卦又見重乾，克體之卦多矣'
});

test('鄰夜扣門借物占(聲音): 1聲 乾·5聲 巽, 酉時 → 1+5+10=16 → 天風姤 四爻, 변 巽爲風, 호 重乾', () => {
  const n = numbersFromNumbers([1, 5], 10);
  assert.deepEqual([n.upper, n.lower, n.moving, n.total], [1, 5, 4, 16]);
  const c = buildCore(n, '子');
  assert.equal(c.benGua.hanja, '天風姤'); assert.equal(c.benGua.movingLine, 4);
  assert.equal(c.bianGua.hanja, '巽爲風'); assert.equal(hu(c), '乾乾');
});

test('今日動靜如何(字占·平仄): 今日動=8 坤, 靜如何=5 巽, 8+5=13 → 地風升 初爻, 변 泰, 호 震兌 (시지수 없음)', () => {
  const n = numbersFromNumbers([8, 5, 13], 0); // 평측 수는 외부에서 세어 셋째 수로 동효 총수를 넘긴다
  const c = buildCore({ upper: 8, lower: 5, moving: 13 % 6 }, '子');
  assert.equal(n.upper, 8); assert.equal(c.benGua.hanja, '地風升'); assert.equal(c.benGua.movingLine, 1);
  assert.equal(c.bianGua.hanja, '地天泰'); assert.equal(hu(c), '震兌');
});

test('西林寺牌額占(字畫): 西7 艮·林8 坤, 15 → 山地剝 三爻, 변 艮爲山, 호 重坤 / 林 10획이면 山澤損 五爻, 변 中孚, 호 坤震', () => {
  const n = numbersFromText('西林', 0, { 西: 7, 林: 8 });
  assert.deepEqual([n.upper, n.lower, n.moving, n.total], [7, 8, 3, 15]);
  const c = buildCore(n, '子');
  assert.equal(c.benGua.hanja, '山地剝'); assert.equal(c.benGua.movingLine, 3);
  assert.equal(c.bianGua.hanja, '艮爲山'); assert.equal(hu(c), '坤坤');
  const n2 = numbersFromText('西林', 0, { 西: 7, 林: 10 });
  const c2 = buildCore(n2, '子');
  assert.equal(c2.benGua.hanja, '山澤損'); assert.equal(c2.benGua.movingLine, 5);
  assert.equal(c2.bianGua.hanja, '風澤中孚'); assert.equal(hu(c2), '坤震');
  // '用互俱生體，為吉卦': 체 艮土(상괘, 5효동이라 용은 상괘… 원문은 艮을 체로 읽음) — 여기서는 괘 구성만 확인
});

test('老人有憂色占(端法後天): 乾1 上·巽5 下, 卯時4 → 10 → 天風姤 九四, 응기 10의 절반 5일(行則應速)', () => {
  const n = numbersFromNumbers([1, 5], 4);
  assert.deepEqual([n.upper, n.lower, n.moving, n.total], [1, 5, 4, 10]);
  const c = buildCore(n, '丑');
  assert.equal(c.benGua.hanja, '天風姤'); assert.equal(c.benGua.movingLine, 4);
  assert.deepEqual(c.tiYong, { ti: 'lower', yong: 'upper', relation: '用克體' }); // 巽木 체, 乾金 극
  assert.deepEqual(c.huToTi, { upper: '克體', lower: '克體' }); // 互卦又見重乾
  assert.equal(Math.ceil(n.total / 2), 5);
});

test('少年有喜色占: 艮7 上·離3 下, 午時7 → 17 → 山火賁 六五, 변 家人, 호 震坎, 離 체·互變俱生 → 17일', () => {
  const n = numbersFromNumbers([7, 3], 7);
  assert.deepEqual([n.moving, n.total], [5, 17]);
  const c = buildCore(n, '巳');
  assert.equal(c.benGua.hanja, '山火賁'); assert.equal(c.benGua.movingLine, 5);
  assert.equal(c.bianGua.hanja, '風火家人'); assert.equal(hu(c), '震坎');
  assert.equal(c.tiYong.ti, 'lower'); // 離為體
  // 원문 '互變俱生之': 상호괘 震木 生 離火, 변괘(용 자리) 巽木 生 離火. 하호괘 坎水는 克體이나 원문은 세지 않음
  assert.equal(c.huToTi.upper, '生體'); assert.equal(c.bianToTi, '生體'); assert.equal(c.huToTi.lower, '克體');
});

test('牛哀鳴占: 坤8 上·坎6 下, 午時7 → 21 → 地水師 三爻, 변 升, 호 坤震, 坤 체·互變俱克 → 21일', () => {
  const n = numbersFromNumbers([8, 6], 7);
  assert.deepEqual([n.moving, n.total], [3, 21]);
  const c = buildCore(n, '卯');
  assert.equal(c.benGua.hanja, '地水師'); assert.equal(c.benGua.movingLine, 3);
  assert.equal(c.bianGua.hanja, '地風升'); assert.equal(hu(c), '坤震');
  assert.equal(c.tiYong.ti, 'upper'); // 坤為體
  assert.equal(c.huToTi.lower, '克體'); assert.equal(c.bianToTi, '克體'); // 震木·巽木 克 坤土
});

test('雞悲鳴占: 巽5 上·乾1 下, 卯時4 → 10 → 風天小畜 六四, 변 乾爲天, 호 離兌, 乾金 체·離火 克', () => {
  const n = numbersFromNumbers([5, 1], 4);
  assert.deepEqual([n.moving, n.total], [4, 10]);
  const c = buildCore(n, '申');
  assert.equal(c.benGua.hanja, '風天小畜'); assert.equal(c.benGua.movingLine, 4);
  assert.equal(c.bianGua.hanja, '乾爲天'); assert.equal(hu(c), '離兌');
  assert.equal(c.tiYong.ti, 'lower'); assert.equal(c.huToTi.upper, '克體');
});

test('枯枝墜地占: 離3 上·兌2 下, 辰時5 → 10 → 火澤睽 九四, 변 損, 호 坎離, 兌金 체·離火 克', () => {
  const n = numbersFromNumbers([3, 2], 5);
  assert.deepEqual([n.moving, n.total], [4, 10]);
  const c = buildCore(n, '子');
  assert.equal(c.benGua.hanja, '火澤睽'); assert.equal(c.benGua.movingLine, 4);
  assert.equal(c.bianGua.hanja, '山澤損'); assert.equal(hu(c), '坎離');
  assert.equal(c.tiYong.ti, 'lower'); assert.equal(c.huToTi.lower, '克體');
});

test('互卦起例 「乾坤無互，互其變卦」: 본괘가 乾爲天이면 변괘의 호괘를 쓴다', () => {
  const c = buildCore({ upper: 1, lower: 1, moving: 2 }, '子'); // 乾爲天 二爻動 → 天火同人
  assert.equal(c.benGua.hanja, '乾爲天'); assert.equal(c.bianGua.hanja, '天火同人');
  assert.equal(c.huFromBian, true); assert.equal(hu(c), '乾巽'); // 同人의 호괘 乾·巽
  const d = buildCore({ upper: 1, lower: 2, moving: 1 }, '子');
  assert.equal(d.huFromBian, false);
});
