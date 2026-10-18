// 『遁甲演義』 卷2 여섯 遁·三詐·五假·天網四張 과 『梅花易數』 卷一 팔괘 물상·단법 기괘 검증
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildQimen } from '../src/qimen/index.ts';
import { ganzhi } from '../src/common/ganzhi.ts';
import { objectTrigram, directionTrigram } from '../src/meihua/images.ts';
import { numbersFromObject } from '../src/meihua/index.ts';
import { castMeihua } from '../src/index.ts';

const GOOD3 = ['開門', '休門', '生門'];

test('遁·詐·假·天網 판정은 각각의 원문 조건을 만족하고, 60시진×양음 18국 훑기에서 모두 한 번 이상 나온다', () => {
  const seen = new Set<string>();
  for (const [lon, name] of [[270, '동지'], [285, '소한'], [300, '대한'], [90, '하지'], [105, '소서'], [120, '대서']] as Array<[number, string]>) {
    for (const dayIdx of [0, 10, 20]) { // 甲子·甲戌·甲申일 → 상·중·하원
      for (let h = 0; h < 60; h++) {
        const r = buildQimen({ pillars: { year: '甲子', month: '丙子', day: ganzhi(dayIdx), hour: ganzhi(h) }, term: { longitude: lon, name, at: '' } });
        for (const f of r.formats) {
          if (f.gong === null) continue;
          const p = r.palaces[f.gong - 1];
          const hs = [p.heavenStem, p.heavenStemExtra].filter(Boolean) as string[];
          switch (f.name) {
            case '神遁': assert.ok(hs.includes('丙') && p.door === '生門' && p.deity === '九天'); break;
            case '鬼遁': assert.ok((hs.includes('丁') && p.door === '休門' || hs.includes('乙') && p.door === '開門') && p.deity === '九地'); break;
            case '風遁': assert.equal(p.gong, 4); assert.ok((hs.includes('乙') && GOOD3.includes(p.door)) || (hs.includes('丙') && p.door === '開門')); break;
            case '雲遁': assert.ok(hs.includes('乙') && ((p.earthStem === '辛' && GOOD3.includes(p.door)) || (p.door === '開門' && p.gong === 2))); break;
            case '龍遁': assert.ok(hs.includes('乙') && p.door === '休門' && (p.gong === 1 || p.earthStem === '癸')); break;
            case '虎遁': assert.ok((hs.includes('乙') && p.earthStem === '辛' && ['休門', '生門'].includes(p.door)) || (hs.includes('辛') && p.door === '生門' && p.gong === 8)); break;
            case '真詐': assert.ok(GOOD3.includes(p.door) && p.deity === '太陰' && hs.some((x) => '乙丙丁'.includes(x))); break;
            case '重詐': assert.ok(GOOD3.includes(p.door) && p.deity === '九地' && hs.some((x) => '乙丙丁'.includes(x))); break;
            case '休詐': assert.ok(GOOD3.includes(p.door) && p.deity === '六合' && hs.some((x) => '乙丙丁'.includes(x))); break;
            case '地假': assert.ok(p.door === '杜門' && p.deity === '九地' && hs.some((x) => '丁己癸'.includes(x))); break;
            case '天假': assert.ok(p.door === '景門' && p.deity === '九天' && hs.some((x) => '乙丙丁'.includes(x))); break;
            case '神假': assert.ok(p.door === '傷門' && p.deity === '九地' && hs.some((x) => '丁己癸'.includes(x))); break;
            case '鬼假': assert.ok(p.door === '死門' && p.deity === '九地' && hs.some((x) => '丁己癸'.includes(x))); break;
            case '天網四張': assert.ok(hs.includes('癸')); break;
            default: continue;
          }
          seen.add(f.name);
        }
      }
    }
  }
  for (const n of ['神遁', '鬼遁', '風遁', '雲遁', '龍遁', '虎遁', '真詐', '重詐', '休詐', '地假', '天假', '神假', '鬼假', '天網四張']) assert.ok(seen.has(n), `${n} 이 한 번도 안 나옴`);
});

test('天網四張: 천반 癸는 매 국에 꼭 한 궁 있어 늘 판정되고, 1~4궁은 낮음·6~9궁은 높음', () => {
  const r = buildQimen({ pillars: { year: '甲子', month: '丙子', day: '甲子', hour: '乙丑' }, term: { longitude: 270, name: '동지', at: '' } });
  const f = r.formats.filter((x) => x.name === '天網四張');
  assert.equal(f.length, 1);
  assert.equal(f[0].gong, 4); assert.match(f[0].note, /낮음/);
});

test('팔괘 물상: 한글·한자 낱말 → 괘 (八卦萬物屬類·驗色占)', () => {
  const t = (w: string) => objectTrigram(w)?.trigram;
  assert.equal(t('노인'), '乾'); assert.equal(t('老人'), '乾'); assert.equal(t('말'), '乾');
  assert.equal(t('어머니'), '坤'); assert.equal(t('소'), '坤'); assert.equal(t('노란색'), '坤');
  assert.equal(t('닭'), '巽'); assert.equal(t('雞'), '巽'); assert.equal(t('스님'), '巽');
  assert.equal(t('붉은 꽃'), '離'); assert.equal(t('빨강'), '離'); assert.equal(t('문서'), '離');
  assert.equal(t('개'), '艮'); assert.equal(t('소년'), '艮'); assert.equal(t('바위'), '艮');
  assert.equal(t('양'), '兌'); assert.equal(t('하얀 그릇'), '兌');
  assert.equal(t('돼지'), '坎'); assert.equal(t('검정'), '坎');
  assert.equal(t('용'), '震'); assert.equal(t('파란 것'), '震');
  assert.equal(objectTrigram('외계인'), null);
  assert.equal(directionTrigram('남동')?.trigram, '巽'); assert.equal(directionTrigram('북')?.trigram, '坎'); assert.equal(directionTrigram('서북쪽')?.trigram, '乾');
});

test('단법후천 기괘: 老人有憂色占 — 노인(乾1) + 동남(巽5) + 卯時4 → 10 → 天風姤 四爻 (castMeihua 로 재현)', () => {
  const n = numbersFromObject('노인', '동남', 4);
  assert.deepEqual([n.upper, n.lower, n.moving, n.total], [1, 5, 4, 10]);
  const r = castMeihua({ datetime: '2026-10-19T06:00:00+09:00', material: { object: '노인', direction: '동남' } }); // 卯時
  assert.equal(r.meta.method, 'object');
  assert.equal(r.benGua.hanja, '天風姤'); assert.equal(r.benGua.movingLine, 4);
  // 牛哀鳴占: 소(坤8) + 북(坎6) + 午時7 → 21 → 地水師 三爻
  const m = numbersFromObject('소', '북', 7);
  assert.deepEqual([m.upper, m.lower, m.moving], [8, 6, 3]);
  assert.throws(() => numbersFromObject('외계인', '북', 1), /물상 사전/);
});
