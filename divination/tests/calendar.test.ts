// 달력·간지 검증. 기대값은 한국천문연구원 공표값(절기 시각·음력)과 알려진 간지 기준일.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { solarTerms } from '../src/calendar/solarTerms.ts';
import { civilFromJd } from '../src/calendar/astro.ts';
import { lunarFromCivil, civilFromLunar, leapMonthOf } from '../src/calendar/lunar.ts';
import { resolveTime } from '../src/calendar/time.ts';
import { pillarsOf } from '../src/calendar/pillars.ts';

const kstMinutes = (jd: number) => { const c = civilFromJd(jd + 9 / 24); return { y: c.y, m: c.m, d: c.d, min: c.hh * 60 + c.mm + c.ss / 60 }; };
const termBy = (year: number, name: string) => solarTerms(year).find((t) => t.name === name)!;

test('24절기 시각이 한국천문연구원 공표값(KST)과 2분 안에 맞는다', () => {
  // [연도, 절기, 월, 일, 시, 분]
  const cases: Array<[number, string, number, number, number, number]> = [
    [2024, '입춘', 2, 4, 17, 27], [2024, '동지', 12, 21, 18, 21],
    [2025, '입춘', 2, 3, 23, 10], [2025, '하지', 6, 21, 11, 42], [2025, '동지', 12, 22, 0, 3],
    [2026, '입춘', 2, 4, 5, 2], [2000, '춘분', 3, 20, 16, 35],
  ];
  for (const [y, name, m, d, hh, mm] of cases) {
    const got = kstMinutes(termBy(y, name).jd);
    assert.equal(`${got.y}-${got.m}-${got.d}`, `${y}-${m}-${d}`, `${y} ${name} 날짜`);
    assert.ok(Math.abs(got.min - (hh * 60 + mm)) <= 2, `${y} ${name}: ${got.min.toFixed(1)} vs ${hh * 60 + mm}`);
  }
});

test('음력 변환: 설날·추석·윤달(한국천문연구원 음양력)', () => {
  const eq = (y: number, m: number, d: number, exp: { year: number; month: number; day: number; leap: boolean }) =>
    assert.deepEqual(lunarFromCivil(y, m, d), exp, `${y}-${m}-${d}`);
  eq(2024, 2, 10, { year: 2024, month: 1, day: 1, leap: false });
  eq(2025, 1, 29, { year: 2025, month: 1, day: 1, leap: false });
  eq(2026, 2, 17, { year: 2026, month: 1, day: 1, leap: false });
  eq(2024, 9, 17, { year: 2024, month: 8, day: 15, leap: false });
  eq(2025, 10, 6, { year: 2025, month: 8, day: 15, leap: false });
  eq(2026, 9, 25, { year: 2026, month: 8, day: 15, leap: false });
  eq(2025, 7, 25, { year: 2025, month: 6, day: 1, leap: true });   // 윤6월 초하루
  eq(2023, 3, 22, { year: 2023, month: 2, day: 1, leap: true });   // 윤2월 초하루
  eq(2020, 5, 23, { year: 2020, month: 4, day: 1, leap: true });   // 윤4월 초하루
  eq(2025, 1, 1, { year: 2024, month: 12, day: 2, leap: false });
  assert.equal(leapMonthOf(2025), 6);
  assert.equal(leapMonthOf(2024), null);
  assert.equal(leapMonthOf(2028), 5);
  assert.deepEqual(civilFromLunar({ year: 2025, month: 6, day: 1, leap: true }), { y: 2025, m: 7, d: 25 });
});

test('일주 기준일: 1900-01-01 甲戌, 2000-01-01 戊午', () => {
  assert.equal(pillarsOf(resolveTime('1900-01-01T12:00+09:00', undefined)).day, '甲戌');
  assert.equal(pillarsOf(resolveTime('2000-01-01T12:00+09:00', undefined)).day, '戊午');
});

test('사주: 2000-01-01 12:00 KST = 己卯年 丙子月 戊午日 戊午時', () => {
  assert.deepEqual(pillarsOf(resolveTime('2000-01-01T12:00+09:00', undefined)), { year: '己卯', month: '丙子', day: '戊午', hour: '戊午' });
});

test('입춘 시각 경계에서 연주·월주가 바뀐다 (2024-02-04 17:27)', () => {
  const before = pillarsOf(resolveTime('2024-02-04T17:26+09:00', undefined));
  const after = pillarsOf(resolveTime('2024-02-04T17:28+09:00', undefined));
  assert.equal(before.year, '癸卯'); assert.equal(before.month, '乙丑');
  assert.equal(after.year, '甲辰'); assert.equal(after.month, '丙寅');
  assert.equal(before.day, after.day);
});

test('자시 경계: ziHour=23 이면 23시에 일진이 바뀌고, 00 이면 0시에 바뀐다', () => {
  const a = pillarsOf(resolveTime('2026-10-18T22:59+09:00', undefined));
  const b = pillarsOf(resolveTime('2026-10-18T23:00+09:00', undefined));
  const c = pillarsOf(resolveTime('2026-10-18T23:00+09:00', undefined, { ziHour: '00' }));
  const d = pillarsOf(resolveTime('2026-10-19T00:00+09:00', undefined, { ziHour: '00' }));
  assert.equal(a.day, '乙丑'); assert.equal(a.hour, '丁亥');
  assert.equal(b.day, '丙寅'); assert.equal(b.hour, '戊子');
  assert.equal(c.day, '乙丑'); assert.equal(c.hour, '丙子');
  assert.equal(d.day, '丙寅'); assert.equal(d.hour, '戊子');
});

test('경도 보정: 서울(126.98E)은 표준시보다 약 32분 이르다', () => {
  const t = resolveTime('2026-10-18T13:10+09:00', 126.98, { localSolar: 'longitude' });
  assert.ok(Math.abs(t.correctionMin + 32.08) < 0.1);
  assert.equal(t.local.hh, 12); // 13:10 → 12:38 → 午시
  assert.equal(t.hourBranchIndex, 6);
});

test('시간대가 다른 입력도 같은 순간이면 같은 결과', () => {
  const a = pillarsOf(resolveTime('2026-10-18T14:30:00+09:00', undefined));
  const b = pillarsOf(resolveTime('2026-10-18T05:30:00Z', undefined));
  assert.deepEqual(a, b);
});

test.todo('미확인: 2033~2034 무중월 둘인 해의 윤달 — 한국천문연구원 공표값으로 확인 뒤 기대값 기록');
