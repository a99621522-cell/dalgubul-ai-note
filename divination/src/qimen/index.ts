// 기문둔갑 포국(시가·전반·차보법). 입력은 사주·절기·월지 같은 계산 값이고, 시각 변환은 cast 가 한다.
import { STEMS, BRANCHES, stemOf, branchOf, stemIndex, ganzhiIndex, relation, seasonElement, strength, BRANCH_ELEMENT, STEM_ELEMENT, type Element, type Rel, type Strength, type Branch } from '../common/ganzhi.ts';
import { PALACES, CW, OPPOSITE, CENTER_LODGE, STAR_HOME, STAR_ELEMENT, DOOR_HOME, DOOR_ELEMENT, DEITIES, EARTH_ORDER, XUN_YI, XUN_KONG, BRANCH_PALACE, HORSE_BRANCH, JU_TABLE, isYangDun, ALIASES } from './tables.ts';

export interface Palace {
  gong: number; trigram: string; direction: string; element: Element;
  earthStem: string; heavenStem: string; heavenStemExtra: string | null;
  door: string; star: string; deity: string;
  state: Strength;
  /** 門生宮=生, 宮生門=被生, 門克宮=迫, 宮克門=制 */
  doorVsPalace: '生' | '被生' | '迫' | '制' | '比和' | '';
  starVsPalace: Rel | '';
  isEmpty: boolean; isHorse: boolean; isCenter: boolean;
}
export interface Format { name: string; kind: '吉' | '凶'; gong: number | null; note: string }

export interface QimenChart {
  meta: {
    castAt: string; tz: string; localSolar: string; ziHour: string; correctionMin: number; effectiveLocal: string;
    school: { family: '時家'; plate: '轉盤'; method: '拆補'; centerLodge: 2 };
  };
  ju: { dun: '陽' | '陰'; number: number; jieqi: string; jieqiAt: string; yuan: '上' | '中' | '下'; futou: string };
  pillars: { year: string; month: string; day: string; hour: string };
  xunshou: string; zhifu: { star: string; gong: number }; zhishi: { door: string; gong: number };
  kongwang: [string, string]; yima: string; wubuyushi: boolean;
  palaces: Palace[];
  yongshinPalaces: { dayStem: number; hourStem: number; yearMing: number | null; matter: { name: string; gong: number | null }[] };
  formats: Format[];
  relations: { dayVsHour: Rel; dayVsMatter: { name: string; rel: Rel | null }[] };
}

export interface QimenInput {
  pillars: { year: string; month: string; day: string; hour: string };
  /** 현재 절기(황경)와 그 시각 문자열 */
  term: { longitude: number; name: string; at: string };
  /** 년명(질문자 생년 간지), 없으면 null */
  yearMing?: string | null;
  /** 사안 용신 이름 목록(한글·한자) */
  matter?: string[];
}

function cwIdx(p: number): number { return CW.indexOf(p); }
function lodge(p: number): number { return p === 5 ? CENTER_LODGE : p; }
function nextPalace(p: number, forward: boolean): number { return forward ? (p % 9) + 1 : ((p + 7) % 9) + 1; }

/** 일주 → 부두(甲·己일)와 원 */
export function yuanOf(dayGz: string): { futou: string; yuan: '上' | '中' | '下' } {
  const i = ganzhiIndex(dayGz);
  const f = i - (i % 5);
  const futou = STEMS[f % 10] + BRANCHES[f % 12];
  const b = BRANCHES[f % 12];
  const yuan = '子午卯酉'.includes(b) ? '上' : '寅申巳亥'.includes(b) ? '下' : '中';
  return { futou, yuan };
}

export function juOf(termLongitude: number, dayGz: string): { dun: '陽' | '陰'; number: number; yuan: '上' | '中' | '下'; futou: string } {
  const { futou, yuan } = yuanOf(dayGz);
  const row = JU_TABLE[termLongitude];
  if (!row) throw new Error(`국수 표에 없는 절기: ${termLongitude}`);
  const number = row[yuan === '上' ? 0 : yuan === '中' ? 1 : 2];
  return { dun: isYangDun(termLongitude) ? '陽' : '陰', number, yuan, futou };
}

function xunOf(gz: string): number { return Math.floor(ganzhiIndex(gz) / 10); }

/** 甲 이면 그 순의 육의로 바꾼다 */
function effectiveStem(gz: string): string {
  const s = stemOf(gz);
  return s === '甲' ? XUN_YI[xunOf(gz)] : s;
}

export function buildQimen(input: QimenInput): Omit<QimenChart, 'meta'> {
  const { pillars } = input;
  const ju = juOf(input.term.longitude, pillars.day);
  const yang = ju.dun === '陽';
  // 지반
  const earth: Record<number, string> = {};
  let p = ju.number;
  for (const s of EARTH_ORDER) { earth[p] = s; p = nextPalace(p, yang); }
  const earthPalaceOf = (stem: string): number => Number(Object.keys(earth).find((k) => earth[Number(k)] === stem));
  // 순수·치부·치사
  const hourIdx = ganzhiIndex(pillars.hour);
  const xun = Math.floor(hourIdx / 10);
  const xunshou = STEMS[0] + BRANCHES[(xun * 10) % 12];
  const yi = XUN_YI[xun];
  const p0raw = earthPalaceOf(yi);
  const p0 = lodge(p0raw);
  const zhifuStar = p0raw === 5 ? '天禽' : STAR_HOME[p0raw];
  const zhishiDoor = DOOR_HOME[p0];
  const hourStem = effectiveStem(pillars.hour);
  const ptRaw = earthPalaceOf(hourStem);
  const pt = lodge(ptRaw);
  // 천반 구성·천반 간
  const shift = (cwIdx(pt) - cwIdx(p0) + 8) % 8;
  const star: Record<number, string> = {}; const heaven: Record<number, string> = {}; const extra: Record<number, string | null> = {};
  for (let i = 0; i < 8; i++) {
    const home = CW[i], land = CW[(i + shift) % 8];
    star[land] = STAR_HOME[home]; heaven[land] = earth[home]; extra[land] = home === CENTER_LODGE ? earth[5] : null;
  }
  star[5] = '天禽'; heaven[5] = earth[5]; extra[5] = null;
  // 팔문: 치사문이 순수 궁에서 시지까지 센 만큼 이동(중궁 포함 숫자 걸음)
  const steps = hourIdx - xun * 10;
  let land = p0;
  for (let i = 0; i < steps; i++) land = nextPalace(land, yang);
  land = lodge(land);
  const dshift = (cwIdx(land) - cwIdx(p0) + 8) % 8;
  const door: Record<number, string> = {};
  for (let i = 0; i < 8; i++) door[CW[(i + dshift) % 8]] = DOOR_HOME[CW[i]];
  door[5] = '';
  // 팔신: 천반 치부 위치(pt)에서 양둔 순행·음둔 역행
  const deity: Record<number, string> = {};
  for (let i = 0; i < 8; i++) {
    const pos = yang ? CW[(cwIdx(pt) + i) % 8] : CW[(cwIdx(pt) - i + 8) % 8];
    deity[pos] = DEITIES[i];
  }
  deity[5] = '';
  // 공망·역마·오불우시
  const kong = XUN_KONG[xun];
  const yima = HORSE_BRANCH[branchOf(pillars.hour)];
  const dayStemIdx = stemIndex(stemOf(pillars.day));
  const wubuyushi = stemIndex(stemOf(pillars.hour)) === (dayStemIdx + 6) % 10;
  const season = seasonElement(branchOf(pillars.month) as Branch);
  // 궁 목록
  const palaces: Palace[] = [];
  for (let g = 1; g <= 9; g++) {
    const info = PALACES[g];
    const d = door[g], s = star[g];
    let dvp: Palace['doorVsPalace'] = '';
    if (d) {
      const r = relation(DOOR_ELEMENT[d], info.element);
      dvp = r === '生' ? '生' : r === '克' ? '迫' : r === '被生' ? '被生' : r === '被克' ? '制' : '比和';
    }
    palaces.push({
      gong: g, trigram: info.trigram, direction: info.direction, element: info.element,
      earthStem: earth[g], heavenStem: heaven[g], heavenStemExtra: extra[g],
      door: d, star: s, deity: deity[g],
      state: strength(info.element, season),
      doorVsPalace: dvp,
      starVsPalace: g === 5 ? '' : relation(STAR_ELEMENT[s], info.element),
      isEmpty: kong.some((b) => BRANCH_PALACE[b] === g),
      isHorse: BRANCH_PALACE[yima] === g,
      isCenter: g === 5,
    });
  }
  const heavenPalaceOf = (stem: string): number => {
    const found = palaces.find((pp) => !pp.isCenter && (pp.heavenStem === stem || pp.heavenStemExtra === stem));
    return found ? found.gong : lodge(earthPalaceOf(stem));
  };
  const dayStemEff = effectiveStem(pillars.day);
  const dayP = heavenPalaceOf(dayStemEff);
  const hourP = heavenPalaceOf(hourStem);
  const yearMingP = input.yearMing ? heavenPalaceOf(effectiveStem(input.yearMing)) : null;
  const matterNames = input.matter ?? [];
  const matter = matterNames.map((name) => ({ name, gong: resolveName(name, palaces, heavenPalaceOf) }));
  const elem = (g: number): Element => PALACES[g].element;
  const relations = {
    dayVsHour: relation(elem(dayP), elem(hourP)),
    dayVsMatter: matter.map((m) => ({ name: m.name, rel: m.gong === null ? null : relation(elem(dayP), elem(m.gong)) })),
  };
  const formats = detectFormats({ palaces, zhishiDoor, zhishiGong: land, shift, p0, pt, dayStemEff, hourStem, xunYi: yi, wubuyushi, yang, dun: ju.dun });
  return {
    ju: { dun: ju.dun, number: ju.number, jieqi: input.term.name, jieqiAt: input.term.at, yuan: ju.yuan, futou: ju.futou },
    pillars,
    xunshou, zhifu: { star: zhifuStar, gong: pt }, zhishi: { door: zhishiDoor, gong: land },
    kongwang: [kong[0], kong[1]], yima, wubuyushi,
    palaces,
    yongshinPalaces: { dayStem: dayP, hourStem: hourP, yearMing: yearMingP, matter },
    formats,
    relations,
  };
}

function resolveName(raw: string, palaces: Palace[], heavenPalaceOf: (s: string) => number): number | null {
  let name = raw.trim();
  if (name === '경문') name = '景門'; // 한글 '경문' 은 景門으로 본다(驚門은 '놀랄 경문'·驚門 으로)
  if (name === '놀랄 경문') name = '驚門';
  name = ALIASES[name] ?? name;
  if (name === '역마' || name === '驛馬') return palaces.find((p) => p.isHorse)?.gong ?? null;
  if (name.length === 1 && STEMS.includes(name as never)) return heavenPalaceOf(name);
  const byDoor = palaces.find((p) => p.door === name); if (byDoor) return byDoor.gong;
  const byStar = palaces.find((p) => p.star === name && !p.isCenter); if (byStar) return byStar.gong;
  const byDeity = palaces.find((p) => p.deity === name); if (byDeity) return byDeity.gong;
  return null;
}

interface Ctx { palaces: Palace[]; zhishiDoor: string; zhishiGong: number; shift: number; p0: number; pt: number; dayStemEff: string; hourStem: string; /** 순수 육의(値符 儀) */ xunYi: string; wubuyushi: boolean; yang: boolean; dun: '陽' | '陰' }

/** 격국 판정. 조건은 각 줄 주석. 같은 궁의 길·흉을 모두 넣는다 */
export function detectFormats(c: Ctx): Format[] {
  const out: Format[] = [];
  const outer = c.palaces.filter((p) => !p.isCenter);
  const pairs = (p: Palace): Array<[string, string]> => {
    const r: Array<[string, string]> = [[p.heavenStem, p.earthStem]];
    if (p.heavenStemExtra) r.push([p.heavenStemExtra, p.earthStem]);
    return r;
  };
  const push = (name: string, kind: '吉' | '凶', gong: number | null, note: string) => out.push({ name, kind, gong, note });
  // 伏吟: 시간이 순수 육의와 같아 천반이 지반 위에 그대로 → 모든 궁 천지반 동일
  if (c.shift === 0) push('伏吟', '凶', null, '시간이 순수 육의 궁에 있어 천반·지반이 같음(정지·지연)');
  // 反吟: 치부성이 본궁의 대궁으로 감
  if (OPPOSITE[c.p0] === c.pt) push('反吟', '凶', c.pt, '치부성이 본궁의 맞은편 궁에 있음(뒤집힘·반복)');
  if (c.wubuyushi) push('五不遇時', '凶', null, '시간이 일간을 극함(甲日庚時 …)');
  for (const p of outer) {
    for (const [h, e] of pairs(p)) {
      // 三奇得使: 乙+戊/辛, 丙+己/庚, 丁+壬/癸
      if ((h === '乙' && (e === '戊' || e === '辛')) || (h === '丙' && (e === '己' || e === '庚')) || (h === '丁' && (e === '壬' || e === '癸'))) push('三奇得使', '吉', p.gong, `${h}+${e}`);
      if (h === '戊' && e === '丙') push('靑龍返首', '吉', p.gong, '戊+丙');
      if (h === '丙' && e === '戊') push('飛鳥跌穴', '吉', p.gong, '丙+戊');
      if (h === '庚' && e === '己') push('刑格', '凶', p.gong, '庚+己');
      if (h === '辛' && e === '乙') push('白虎猖狂', '凶', p.gong, '辛+乙');
      if (h === '癸' && e === '丁') push('螣蛇夭矯', '凶', p.gong, '癸+丁');
      if (h === '庚' && e === '丙') push('太白入熒', '凶', p.gong, '庚+丙');
      if (h === '丙' && e === '庚') push('熒入太白', '凶', p.gong, '丙+庚');
      if (h === '乙' && e === '辛') push('靑龍逃走', '凶', p.gong, '乙+辛');
      if (h === '丁' && e === '癸') push('朱雀投江', '凶', p.gong, '丁+癸');
      if (h === '庚' && e === '癸') push('大格', '凶', p.gong, '庚+癸');
      if (h === '庚' && e === '壬') push('小格', '凶', p.gong, '庚+壬');
      if (h === '庚' && e === '庚') push('戰格', '凶', p.gong, '庚+庚(伏吟格)');
      // 奇格: 六庚謹勿加三奇 (煙波釣叟歌)
      if (h === '庚' && '乙丙丁'.includes(e)) push('奇格', '凶', p.gong, `庚+${e}`);
      // 天乙伏宮格·天乙飛宮格: 庚加値符(순수 육의) / 値符加庚 (煙波釣叟歌 '庚加值符天乙伏，值符加庚天乙飛')
      if (h === '庚' && e === c.xunYi && c.xunYi !== '庚') push('天乙伏宮格', '凶', p.gong, `庚+値符儀(${e})`);
      if (h === c.xunYi && e === '庚' && c.xunYi !== '庚') push('天乙飛宮格', '凶', p.gong, `値符儀(${h})+庚`);
      // 伏勃·飛勃: 丙加天乙(値符儀) / 天乙加丙 (煙波釣叟歌 '丙加天乙為伏逆，天乙加丙為飛勃')
      if (h === '丙' && e === c.xunYi) push('伏勃', '凶', p.gong, `丙+値符儀(${e})`);
      if (h === c.xunYi && e === '丙') push('飛勃', '凶', p.gong, `値符儀(${h})+丙`);
      // 勃格: 丙奇臨時干 (『奇門遁甲統宗』 總賦 '丙奇臨時干名勃格而禍起')
      if (h === '丙' && e === c.hourStem && c.hourStem !== '丙') push('勃格', '凶', p.gong, `丙+시간(${e})`);
      // 伏干格·飛干格·時格 (일간·시간이 甲이면 육의로 대체)
      if (h === '庚' && e === c.dayStemEff && c.dayStemEff !== '庚') push('伏干格', '凶', p.gong, `庚+일간(${e})`);
      if (h === c.dayStemEff && e === '庚' && c.dayStemEff !== '庚') push('飛干格', '凶', p.gong, `일간(${h})+庚`);
      if (h === '庚' && e === c.hourStem && c.hourStem !== '庚') push('時格', '凶', p.gong, `庚+시간(${e})`);
    }
    const hs = [p.heavenStem, p.heavenStemExtra].filter(Boolean) as string[];
    for (const h of hs) {
      // 三奇得門: 乙丙丁 + 開休生門
      if ('乙丙丁'.includes(h) && ['開門', '休門', '生門'].includes(p.door)) push('三奇得門', '吉', p.gong, `${h}+${p.door}`);
      // 玉女守門: 丁 이 치사문 궁에
      if (h === '丁' && p.door === c.zhishiDoor) push('玉女守門', '吉', p.gong, '丁+치사문');
      // 天遁 丙+生門+丁(지반) — 煙波釣叟歌 '生門六丙合六丁', 遁甲演義 양둔4국 乙酉시·음둔6국 庚申시 예시.
      // 『奇門遁甲統宗』 奇門秘訣總賦는 '生丙臨戊天遁' 이라 丙+生門+戊 도 天遁으로 적고 note 에 출처를 남긴다
      if (h === '丙' && p.door === '生門' && p.earthStem === '丁') push('天遁', '吉', p.gong, '丙+生門+丁(煙波釣叟歌·遁甲演義)');
      if (h === '丙' && p.door === '生門' && p.earthStem === '戊') push('天遁', '吉', p.gong, '丙+生門+戊(奇門遁甲統宗)');
      if (h === '乙' && p.door === '開門' && p.earthStem === '己') push('地遁', '吉', p.gong, '乙+開門+己');
      if (h === '丁' && p.door === '休門' && p.deity === '太陰') push('人遁', '吉', p.gong, '丁+休門+太陰');
      // 三奇入墓: 乙 坤2(未), 丙 乾6(戌), 丁 艮8(丑) — 遁甲演義 王璋 주 '六乙下臨二宮 六丙到六宮 六丁下臨八宮'
      if ((h === '乙' && p.gong === 2) || (h === '丙' && p.gong === 6) || (h === '丁' && p.gong === 8)) push('三奇入墓', '凶', p.gong, `${h} 입묘`);
      // 六儀擊刑: 戊3 己2 庚8 辛9 壬4 癸4
      const jx: Record<string, number> = { 戊: 3, 己: 2, 庚: 8, 辛: 9, 壬: 4, 癸: 4 };
      if (jx[h] === p.gong) push('六儀擊刑', '凶', p.gong, `${h} 격형`);
    }
    // --- 『遁甲演義』 卷2 의 여섯 遁·三詐·五假·天網四張 ---
    const good3 = ['開門', '休門', '生門'].includes(p.door);
    for (const h of hs) {
      const qi = '乙丙丁'.includes(h);
      // 神遁 丙+生門+九天 / 鬼遁 丁+休門+九地, 乙+開門+九地
      if (h === '丙' && p.door === '生門' && p.deity === '九天') push('神遁', '吉', p.gong, '丙+生門+九天');
      if ((h === '丁' && p.door === '休門' && p.deity === '九地') || (h === '乙' && p.door === '開門' && p.deity === '九地')) push('鬼遁', '吉', p.gong, `${h}+${p.door}+九地`);
      // 風遁 乙+三吉門+巽4 / 丙+開門+巽4
      if (p.gong === 4 && ((h === '乙' && good3) || (h === '丙' && p.door === '開門'))) push('風遁', '吉', p.gong, `${h}+${p.door}+巽궁`);
      // 雲遁 乙+지반辛+三吉門 / 乙+開門+坤2
      if (h === '乙' && ((p.earthStem === '辛' && good3) || (p.door === '開門' && p.gong === 2))) push('雲遁', '吉', p.gong, p.earthStem === '辛' ? `乙+${p.door}+辛` : '乙+開門+坤궁');
      // 龍遁 乙+休門+坎1 / 乙+休門+지반癸
      if (h === '乙' && p.door === '休門' && (p.gong === 1 || p.earthStem === '癸')) push('龍遁', '吉', p.gong, p.gong === 1 ? '乙+休門+坎궁' : '乙+休門+癸');
      // 虎遁 乙+休門+지반辛(艮) / 乙+生門+辛 / 辛+生門+艮8
      if ((h === '乙' && p.earthStem === '辛' && (p.door === '休門' || p.door === '生門')) || (h === '辛' && p.door === '生門' && p.gong === 8)) push('虎遁', '吉', p.gong, `${h}+${p.door}+${h === '辛' ? '艮궁' : '辛'}`);
      // 三詐: 三吉門+三奇 아래 太陰=真詐·九地=重詐·六合=休詐
      if (qi && good3) {
        if (p.deity === '太陰') push('真詐', '吉', p.gong, `${h}+${p.door}+太陰 (施恩·隱遁)`);
        if (p.deity === '九地') push('重詐', '吉', p.gong, `${h}+${p.door}+九地 (取財·拜官)`);
        if (p.deity === '六合') push('休詐', '吉', p.gong, `${h}+${p.door}+六合 (合藥·祈禳)`);
      }
      // 五假(人假 제외): 地假 杜門+丁己癸+九地, 天假 景門+乙丙丁+九天, 神假 傷門+丁己癸+九地, 鬼假 死門+丁己癸+九地
      const djg = '丁己癸'.includes(h);
      if (p.door === '杜門' && djg && p.deity === '九地') push('地假', '吉', p.gong, `杜門+${h}+九地 (潛伏·藏形)`);
      if (p.door === '景門' && qi && p.deity === '九天') push('天假', '吉', p.gong, `景門+${h}+九天 (進謁·干求)`);
      if (p.door === '傷門' && djg && p.deity === '九地') push('神假', '吉', p.gong, `傷門+${h}+九地 (埋葬)`);
      if (p.door === '死門' && djg && p.deity === '九地') push('鬼假', '吉', p.gong, `死門+${h}+九地 (超亡·薦度)`);
      // 天網四張: 천반 癸 가 든 궁. 1~4궁 낮음(길 있음), 6~9궁 높음(길 없음)
      if (h === '癸') push('天網四張', '凶', p.gong, p.gong <= 4 ? `癸 ${p.gong}궁 — 그물 낮음(一二網低有路踪)` : `癸 ${p.gong}궁 — 그물 높음(八九高強)`);
    }
    // 門迫: 門克宮
    if (p.doorVsPalace === '迫') push('門迫', '凶', p.gong, `${p.door} 이 ${p.trigram}궁을 극함`);
  }
  return out;
}

export { STEM_ELEMENT, BRANCH_ELEMENT };
