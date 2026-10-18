// 기문둔갑: 손으로 포국해 확인할 수 있는 단순 사례(양둔 1국·음둔 9국) + 국수 표 + 교과서 예제(미확인 todo)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildQimen, juOf } from '../src/qimen/index.ts';
import { castQimen } from '../src/index.ts';

const term = (longitude: number, name: string) => ({ longitude, name, at: '' });
const line = (r: ReturnType<typeof buildQimen>) => r.palaces.map((p) => `${p.gong}:${p.earthStem}/${p.heavenStem}${p.heavenStemExtra ?? ''}/${p.star}/${p.door}/${p.deity}`);

test('차보법 원·국수: 입춘 己卯일 상원 8국, 戊申일 중원 5국, 甲寅일 하원 2국', () => {
  assert.deepEqual(juOf(315, '己卯'), { dun: '陽', number: 8, yuan: '上', futou: '己卯' });
  assert.deepEqual(juOf(315, '戊申'), { dun: '陽', number: 5, yuan: '中', futou: '甲辰' });
  assert.deepEqual(juOf(315, '丁巳'), { dun: '陽', number: 2, yuan: '下', futou: '甲寅' });
  assert.equal(juOf(90, '甲子').number, 9); assert.equal(juOf(90, '甲子').dun, '陰');
  assert.equal(juOf(255, '甲午').number, 4); assert.equal(juOf(270, '甲午').number, 1);
});

test('양둔 1국 甲子시: 지반 戊1己2庚3辛4壬5癸6丁7丙8乙9, 伏吟, 팔신 순행', () => {
  const r = buildQimen({ pillars: { year: '甲辰', month: '丙子', day: '甲子', hour: '甲子' }, term: term(270, '동지') });
  assert.deepEqual(line(r), [
    '1:戊/戊/天蓬/休門/値符', '2:己/己壬/天芮/死門/玄武', '3:庚/庚/天衝/傷門/太陰', '4:辛/辛/天輔/杜門/六合',
    '5:壬/壬/天禽//', '6:癸/癸/天心/開門/九天', '7:丁/丁/天柱/驚門/九地', '8:丙/丙/天任/生門/螣蛇', '9:乙/乙/天英/景門/白虎',
  ]);
  assert.ok(r.formats.some((f) => f.name === '伏吟'));
  assert.deepEqual(r.kongwang, ['戌', '亥']); assert.equal(r.yima, '寅');
  assert.equal(r.palaces[5].isEmpty, true); assert.equal(r.palaces[7].isHorse, true);
});

test('양둔 1국 乙丑시: 치부 天蓬→9궁(反吟), 치사 休門→2궁, 천반·팔문·팔신 회전', () => {
  const r = buildQimen({ pillars: { year: '甲辰', month: '丙子', day: '甲子', hour: '乙丑' }, term: term(270, '동지'), matter: ['생문', '戊', '육합'] });
  assert.deepEqual(r.zhifu, { star: '天蓬', gong: 9 }); assert.deepEqual(r.zhishi, { door: '休門', gong: 2 });
  assert.deepEqual(line(r), [
    '1:戊/乙/天英/杜門/白虎', '2:己/丙/天任/休門/螣蛇', '3:庚/丁/天柱/死門/九地', '4:辛/癸/天心/驚門/九天',
    '5:壬/壬/天禽//', '6:癸/辛/天輔/傷門/六合', '7:丁/庚/天衝/生門/太陰', '8:丙/己壬/天芮/景門/玄武', '9:乙/戊/天蓬/開門/値符',
  ]);
  const names = r.formats.map((f) => `${f.name}${f.gong ?? ''}`);
  for (const n of ['反吟9', '三奇得使1', '三奇得使2', '三奇得門2', '六儀擊刑4', '門迫4']) assert.ok(names.includes(n), n);
  assert.deepEqual(r.yongshinPalaces.matter, [{ name: '생문', gong: 7 }, { name: '戊', gong: 9 }, { name: '육합', gong: 6 }]);
  assert.equal(r.yongshinPalaces.dayStem, 9); // 甲 → 戊 천반 9궁
  assert.equal(r.relations.dayVsHour, '被克'); // 離火(9) ← 坎水(1)
});

test('음둔 9국 丙寅시: 지반 역포, 치사 景門 역행 2걸음 → 7궁, 팔신 역행', () => {
  const r = buildQimen({ pillars: { year: '甲辰', month: '庚午', day: '甲子', hour: '丙寅' }, term: term(90, '하지') });
  assert.equal(r.ju.number, 9); assert.equal(r.ju.dun, '陰');
  assert.deepEqual(r.zhifu, { star: '天英', gong: 2 }); assert.deepEqual(r.zhishi, { door: '景門', gong: 7 });
  assert.deepEqual(line(r), [
    '1:乙/辛/天心/驚門/玄武', '2:丙/戊/天英/杜門/値符', '3:丁/己/天任/休門/六合', '4:癸/丁/天衝/生門/太陰',
    '5:壬/壬/天禽//', '6:辛/庚/天柱/死門/九地', '7:庚/丙壬/天芮/景門/九天', '8:己/乙/天蓬/開門/白虎', '9:戊/癸/天輔/傷門/螣蛇',
  ]);
  const names = r.formats.map((f) => `${f.name}${f.gong ?? ''}`);
  for (const n of ['白虎猖狂1', '靑龍返首2', '熒入太白7', '地遁8', '三奇得門8']) assert.ok(names.includes(n), n);
});

test('순수 육의가 중궁이면 치부는 天禽, 坤2 에 기궁', () => {
  // 음둔 6국: 己 가 5궁. 甲戌순(癸未시) → 육의 己
  const r = buildQimen({ pillars: { year: '丙午', month: '戊戌', day: '乙丑', hour: '癸未' }, term: term(195, '한로') });
  assert.equal(r.zhifu.star, '天禽');
  assert.equal(r.palaces.find((p) => p.star === '天芮' && !p.isCenter)!.heavenStemExtra, '己');
});

test('五不遇時: 甲日 庚時', () => {
  const r = buildQimen({ pillars: { year: '甲辰', month: '丙子', day: '甲子', hour: '庚午' }, term: term(270, '동지') });
  assert.equal(r.wubuyushi, true);
  const r2 = buildQimen({ pillars: { year: '甲辰', month: '丙子', day: '甲子', hour: '辛未' }, term: term(270, '동지') });
  assert.equal(r2.wubuyushi, false);
});

test('castQimen: 절기 시각 1분 전·후에 국이 바뀐다 (2025 하지 06-21 11:42)', () => {
  const a = castQimen({ datetime: '2025-06-21T11:40+09:00' });
  const b = castQimen({ datetime: '2025-06-21T11:44+09:00' });
  assert.equal(a.ju.jieqi, '망종'); assert.equal(a.ju.dun, '陽');
  assert.equal(b.ju.jieqi, '하지'); assert.equal(b.ju.dun, '陰');
  assert.equal(a.pillars.day, b.pillars.day);
});

test('castQimen: 결과는 결정적이고 궁 9개·격국은 표에 있는 이름만', () => {
  const a = castQimen({ datetime: '2026-10-18T14:30:00+09:00', matter: ['생문'] });
  const b = castQimen({ datetime: '2026-10-18T14:30:00+09:00', matter: ['생문'] });
  assert.deepEqual(a, b);
  assert.equal(a.palaces.length, 9);
  const allowed = new Set(['伏吟', '反吟', '五不遇時', '三奇得使', '三奇得門', '靑龍返首', '飛鳥跌穴', '玉女守門', '天遁', '地遁', '人遁', '刑格', '白虎猖狂', '螣蛇夭矯', '太白入熒', '熒入太白', '靑龍逃走', '朱雀投江', '大格', '小格', '戰格', '伏干格', '飛干格', '時格', '三奇入墓', '六儀擊刑', '門迫']);
  for (const f of a.formats) assert.ok(allowed.has(f.name), f.name);
});

test.todo('미확인: 차보법 교과서 예제 3~5건(양력 일시·국수·치부·치사) — 사람이 책에서 옮긴 뒤 기대값 기록');
test.todo('미확인: 치윤법 유파 결과와의 차이 표 — 이번 판은 차보법만');
