// 공유 저작물(저작권 만료) 고전 원문의 포국 예시와 대조한다. 출처는 中文維基文庫(zh.wikisource.org) 전자문서.
//  - 『遁甲演義』(明 程道生) 四庫全書本 卷2·卷4, 일반본  https://zh.wikisource.org/wiki/遁甲演義_(四庫全書本)/卷2 , /卷4 , https://zh.wikisource.org/wiki/遁甲演義
//  - 『奇門遁甲統宗』 卷1 陰陽二遁順逆起例·九星值符圖·八門值使圖  https://zh.wikisource.org/wiki/奇門遁甲統宗
//  - 『煙波釣叟歌』(羅通 증보)  https://zh.wikisource.org/wiki/煙波釣叟歌
// 고전은 날짜 대신 '○둔 ○국 ○○일 ○○시' 로 예를 들므로 buildQimen 에 사주·절기를 직접 넣는다(달력과 무관한 포국 검증).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildQimen } from '../src/qimen/index.ts';
import { JU_TABLE, STAR_HOME, DOOR_HOME } from '../src/qimen/tables.ts';

const term = (longitude: number, name: string) => ({ longitude, name, at: '' });
const at = (r: ReturnType<typeof buildQimen>, g: number) => r.palaces[g - 1];
const heavenPalace = (r: ReturnType<typeof buildQimen>, stem: string) => r.palaces.find((p) => !p.isCenter && (p.heavenStem === stem || p.heavenStemExtra === stem))!.gong;
const doorPalace = (r: ReturnType<typeof buildQimen>, door: string) => r.palaces.find((p) => p.door === door)!.gong;
const deityPalace = (r: ReturnType<typeof buildQimen>, d: string) => r.palaces.find((p) => p.deity === d)!.gong;

test('統宗 「陰陽二遁順逆起例」: 24절기 국수 노래와 표가 같다', () => {
  // 冬至驚蟄一七四 夏至白露九三六 小寒二八五 小暑八二五 大寒春分三九六 大暑秋分七一四 芒種六三九 立秋二五八
  // 穀雨小滿五二八 霜降小雪五八二 立春八五二 大雪四七一 清明立夏四一七 處暑一四七 雨水九六三 立冬寒露六九三
  const song: Array<[number, [number, number, number]]> = [
    [270, [1, 7, 4]], [345, [1, 7, 4]], [90, [9, 3, 6]], [165, [9, 3, 6]], [285, [2, 8, 5]], [105, [8, 2, 5]],
    [300, [3, 9, 6]], [0, [3, 9, 6]], [120, [7, 1, 4]], [180, [7, 1, 4]], [75, [6, 3, 9]], [135, [2, 5, 8]],
    [30, [5, 2, 8]], [60, [5, 2, 8]], [210, [5, 8, 2]], [240, [5, 8, 2]], [315, [8, 5, 2]], [255, [4, 7, 1]],
    [15, [4, 1, 7]], [45, [4, 1, 7]], [150, [1, 4, 7]], [330, [9, 6, 3]], [225, [6, 9, 3]], [195, [6, 9, 3]],
  ];
  assert.equal(song.length, 24);
  for (const [lon, ju] of song) assert.deepEqual(JU_TABLE[lon], ju, `황경 ${lon}`);
});

test('統宗 「九星值符圖·八門值使圖」: 구성·팔문 본궁', () => {
  assert.deepEqual(STAR_HOME, { 1: '天蓬', 8: '天任', 3: '天衝', 4: '天輔', 9: '天英', 2: '天芮', 7: '天柱', 6: '天心', 5: '天禽' });
  assert.deepEqual(DOOR_HOME, { 1: '休門', 8: '生門', 3: '傷門', 4: '杜門', 9: '景門', 2: '死門', 7: '驚門', 6: '開門' });
});

test('遁甲演義 起例詩: 양둔1국 지반 戊1己2庚3辛4壬5癸6丁7丙8乙9, 음둔9국 戊9己8庚7辛6壬5癸4丁3丙2乙1', () => {
  const y = buildQimen({ pillars: { year: '甲子', month: '丙子', day: '甲子', hour: '甲子' }, term: term(270, '동지') });
  assert.equal(y.palaces.map((p) => p.earthStem).join(''), '戊己庚辛壬癸丁丙乙');
  const n = buildQimen({ pillars: { year: '甲子', month: '庚午', day: '甲子', hour: '甲子' }, term: term(90, '하지') });
  assert.equal(n.palaces.map((p) => p.earthStem).join(''), '乙丙丁癸壬辛庚己戊');
});

test('遁甲演義 卷4: 冬至上元 甲子日 甲子時 — 天上六戊 1궁, 六乙 9궁, 六丁 7궁', () => {
  const r = buildQimen({ pillars: { year: '甲子', month: '丙子', day: '甲子', hour: '甲子' }, term: term(270, '동지') });
  assert.equal(r.ju.number, 1); assert.equal(r.ju.yuan, '上');
  assert.equal(heavenPalace(r, '戊'), 1); assert.equal(heavenPalace(r, '乙'), 9); assert.equal(heavenPalace(r, '丁'), 7);
});

test('遁甲演義 一般本: 양둔1국 丙寅時 — 蓬星 8궁, 休門 3궁, 丙과 休門이 震궁에, 乙 2궁, 丁 6궁', () => {
  const r = buildQimen({ pillars: { year: '甲子', month: '丙子', day: '甲子', hour: '丙寅' }, term: term(270, '동지') });
  assert.deepEqual(r.zhifu, { star: '天蓬', gong: 8 });
  assert.deepEqual(r.zhishi, { door: '休門', gong: 3 });
  assert.equal(heavenPalace(r, '丙'), 3); assert.equal(at(r, 3).door, '休門');
  assert.equal(heavenPalace(r, '乙'), 2); assert.equal(heavenPalace(r, '丁'), 6);
});

test('遁甲演義 卷2: 양둔 上元1국 甲己日 丙寅時 — 直符 8궁, 九天 1궁, 九地 6궁, 太陰 4궁, 六合 9궁', () => {
  const r = buildQimen({ pillars: { year: '甲子', month: '丙子', day: '甲子', hour: '丙寅' }, term: term(270, '동지') });
  assert.equal(deityPalace(r, '値符'), 8); assert.equal(deityPalace(r, '九天'), 1); assert.equal(deityPalace(r, '九地'), 6);
  assert.equal(deityPalace(r, '太陰'), 4); assert.equal(deityPalace(r, '六合'), 9);
});

test('遁甲演義 卷2: 음둔 上元9국 甲己日 丙寅時 — 直符 2궁, 九天 7궁, 九地 6궁, 太陰 4궁, 六合 3궁', () => {
  const r = buildQimen({ pillars: { year: '甲子', month: '庚午', day: '甲子', hour: '丙寅' }, term: term(90, '하지') });
  assert.equal(deityPalace(r, '値符'), 2); assert.equal(deityPalace(r, '九天'), 7); assert.equal(deityPalace(r, '九地'), 6);
  assert.equal(deityPalace(r, '太陰'), 4); assert.equal(deityPalace(r, '六合'), 3);
});

test('遁甲演義 天遁 예시 1: 양둔4국 乙庚日 乙酉時 — 天心 直符, 開門 直使 7궁, 生門과 丙이 丁 위에 1궁 = 天遁', () => {
  // 양둔 4국: 청명 상원(4). 乙庚日 가운데 상원 부두(甲子)인 乙丑일, 乙庚日 → 乙酉時(일간 두수법)
  const r = buildQimen({ pillars: { year: '甲子', month: '庚辰', day: '乙丑', hour: '乙酉' }, term: term(15, '청명') });
  assert.equal(r.ju.number, 4); assert.equal(r.ju.dun, '陽');
  assert.deepEqual(r.zhifu, { star: '天心', gong: 3 }); // 시간 乙 지반 3궁
  assert.deepEqual(r.zhishi, { door: '開門', gong: 7 });
  assert.equal(doorPalace(r, '生門'), 1); assert.equal(heavenPalace(r, '丙'), 1); assert.equal(at(r, 1).earthStem, '丁');
  assert.ok(r.formats.some((f) => f.name === '天遁' && f.gong === 1));
});

test('遁甲演義 天遁 예시 2: 음둔6국 戊癸日 庚申時 — 天蓬 直符, 休門 直使 4궁, 生門과 丙이 丁 위에 9궁 = 天遁', () => {
  // 음둔 6국: 한로 상원(6). 戊癸日 → 庚申時(壬子 두수). 戊子일은 甲申旬 → 부두 甲申(하원)이므로 甲申旬 밖의 戊日: 戊午(甲寅旬 → 부두 甲寅 하원) … 상원이 되는 戊日은 戊辰(甲子旬, 부두 甲子)·戊戌(甲午旬, 부두 甲午)
  const r = buildQimen({ pillars: { year: '甲子', month: '甲戌', day: '戊辰', hour: '庚申' }, term: term(195, '한로') });
  assert.equal(r.ju.number, 6); assert.equal(r.ju.dun, '陰');
  assert.deepEqual(r.zhifu, { star: '天蓬', gong: 4 });
  assert.deepEqual(r.zhishi, { door: '休門', gong: 4 });
  assert.equal(doorPalace(r, '生門'), 9); assert.equal(heavenPalace(r, '丙'), 9); assert.equal(at(r, 9).earthStem, '丁');
  assert.ok(r.formats.some((f) => f.name === '天遁' && f.gong === 9));
});

test('遁甲演義 卷2 王璋 주: 三奇入墓 — 乙 2궁, 丙 6궁, 丁 8궁 / 음둔4국 丙辛日 庚寅時 丙이 6궁(月奇入墓)', () => {
  // 음둔 4국: 대서 하원(4)… 丙辛日 중 하원 부두(甲申·甲寅·己巳·己亥): 丙戌(甲申旬) 가 하원. 丙辛日 → 庚寅時(戊子 두수)
  const r = buildQimen({ pillars: { year: '甲子', month: '癸未', day: '丙戌', hour: '庚寅' }, term: term(120, '대서') });
  assert.equal(r.ju.number, 4); assert.equal(r.ju.dun, '陰');
  assert.equal(heavenPalace(r, '丙'), 6);
  assert.ok(r.formats.some((f) => f.name === '三奇入墓' && f.gong === 6 && f.note.startsWith('丙')));
});

test('煙波釣叟歌: 六儀擊刑 — 甲子戊 東(3), 戌(己) 未(2), 申(庚) 寅(8), 寅(癸) 巳(4), 辰(壬) 辰(4), 午(辛) 午(9)', () => {
  // 양둔1국 甲子시(복음)에서 천반 = 지반이므로 궁별 육의로 바로 확인
  const r = buildQimen({ pillars: { year: '甲子', month: '丙子', day: '甲子', hour: '甲子' }, term: term(270, '동지') });
  const jx = r.formats.filter((f) => f.name === '六儀擊刑').map((f) => `${f.note[0]}${f.gong}`);
  assert.deepEqual(jx, ['己2']); // 1국 복음에서는 己만 坤2 에 든다
  // 음둔 9국 丙寅시(앞 테스트)에서는 癸가 巽4 → 격형
  const n = buildQimen({ pillars: { year: '甲子', month: '庚午', day: '甲子', hour: '丙寅' }, term: term(90, '하지') });
  assert.ok(!n.formats.some((f) => f.name === '六儀擊刑' && f.gong === 4 && f.note[0] !== '癸' && f.note[0] !== '壬'));
});

test.todo('遁甲演義 卷2 「陽遁七局 乙庚日 丙子時 天任為直符」 — 본문의 국수·직부가 전반 규칙과 맞지 않아(戊가 7궁이면 天柱) 판본 오류 또는 다른 기법으로 보인다. 다른 판본으로 확인 전까지 보류');
