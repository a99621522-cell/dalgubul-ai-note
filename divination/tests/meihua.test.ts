// 매화역수: 달력과 무관하게 수(數)만으로 통과해야 하는 고전 사례 + 기괘 규칙
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { numbersFromTime, numbersFromNumbers, numbersFromText, buildCore } from '../src/meihua/index.ts';
import { castMeihua } from '../src/index.ts';

test('관매점: 辰年 12월 17일 申時 → 澤火革 初爻動, 호 天風姤, 변 澤山咸, 체 兌 용 離 用克體', () => {
  const n = numbersFromTime(5, 12, 17, 9);
  assert.deepEqual([n.upper, n.lower, n.moving, n.total], [2, 3, 1, 43]);
  const c = buildCore(n, '丑');
  assert.equal(c.benGua.hanja, '澤火革'); assert.equal(c.benGua.movingLine, 1);
  assert.equal(c.huGua.hanja, '天風姤'); assert.equal(c.bianGua.hanja, '澤山咸');
  assert.deepEqual(c.tiYong, { ti: 'upper', yong: 'lower', relation: '用克體' });
  assert.equal(c.bianToTi, '生體'); // 艮土 生 兌金
});

test('모란점: 巳年 3월 16일 卯時 → 天風姤 五爻動, 호 乾爲天, 변 火風鼎, 체 巽 용 乾 用克體', () => {
  const n = numbersFromTime(6, 3, 16, 4);
  assert.deepEqual([n.upper, n.lower, n.moving, n.total], [1, 5, 5, 29]);
  const c = buildCore(n, '辰');
  assert.equal(c.benGua.hanja, '天風姤'); assert.equal(c.benGua.movingLine, 5);
  assert.equal(c.huGua.hanja, '乾爲天'); assert.equal(c.bianGua.hanja, '火風鼎');
  assert.deepEqual(c.tiYong, { ti: 'lower', yong: 'upper', relation: '用克體' });
  assert.equal(c.bianToTi, '體生'); // 巽木 生 離火
});

test('나머지 0 은 8(괘)·6(효)', () => {
  const n = numbersFromTime(1, 1, 6, 8); // 8 → 상괘 8, 16 → 하괘 8, 16 mod 6 = 4
  assert.deepEqual([n.upper, n.lower, n.moving], [8, 8, 4]);
  const m = numbersFromNumbers([8, 16], 0);
  assert.deepEqual([m.upper, m.lower, m.moving], [8, 8, 6]);
});

test('숫자 기괘 규칙 1·2·3개', () => {
  assert.deepEqual((({ upper, lower, moving }) => [upper, lower, moving])(numbersFromNumbers([3758], 2)), [5, 2, 1]); // 37→5, 58→2, 3+7+5+8+2=25→1
  assert.deepEqual((({ upper, lower, moving }) => [upper, lower, moving])(numbersFromNumbers([3, 5], 1)), [3, 5, 3]);
  assert.deepEqual((({ upper, lower, moving }) => [upper, lower, moving])(numbersFromNumbers([9, 10, 13], 1)), [1, 2, 1]);
});

test('글자 획수 기괘(한글 자모 합)', () => {
  const n = numbersFromText('대구', 1); // 대 = ㄷ2+ㅐ3 = 5, 구 = ㄱ1+ㅜ2 = 3 → 상 5, 하 3, 동효 (5+3)=8 → 2 (字占은 시지수를 더하지 않음)
  assert.deepEqual([n.upper, n.lower, n.moving], [5, 3, 2]);
  assert.throws(() => numbersFromText('漢', 1));
  assert.equal(numbersFromText('漢', 1, { 漢: 14 }).upper, 6);
});

test('castMeihua: 호괘·변괘 효 구성이 본괘에서 파생된다', () => {
  const r = castMeihua({ datetime: '2026-10-18T14:30:00+09:00' });
  const l = r.benGua.lines;
  const bl = [...l]; bl[r.benGua.movingLine! - 1] ^= 1;
  assert.deepEqual(r.bianGua.lines, bl);
  const src = r.huFromBian ? bl : l; // 乾坤無互면 변괘에서 호괘
  assert.deepEqual(r.huGua.lines, [src[1], src[2], src[3], src[2], src[3], src[4]]);
  assert.ok(typeof r.numbers.yingqi.base === 'number');
  assert.equal(r.meta.method, 'time');
});
