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
  const formats = detectFormats({ palaces, zhishiDoor, zhishiGong: land, shift, p0, pt, dayStemEff, hourStem, wubuyushi, yang, dun: ju.dun });
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
  if (name.length === 1 && STEMS.includes(name as never)) return heavenPalaceOf(name);
  const byDoor = palaces.find((p) => p.door === name); if (byDoor) return byDoor.gong;
  const byStar = palaces.find((p) => p.star === name && !p.isCenter); if (byStar) return byStar.gong;
  const byDeity = palaces.find((p) => p.deity === name); if (byDeity) return byDeity.gong;
  return null;
}

interface Ctx { palaces: Palace[]; zhishiDoor: string; zhishiGong: number; shift: number; p0: number; pt: number; dayStemEff: string; hourStem: string; wubuyushi: boolean; yang: boolean; dun: '陽' | '陰' }

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
      // 天遁 丙+生門+戊(지반), 地遁 乙+開門+己(지반), 人遁 丁+休門+太陰
      if (h === '丙' && p.door === '生門' && p.earthStem === '戊') push('天遁', '吉', p.gong, '丙+生門+戊');
      if (h === '乙' && p.door === '開門' && p.earthStem === '己') push('地遁', '吉', p.gong, '乙+開門+己');
      if (h === '丁' && p.door === '休門' && p.deity === '太陰') push('人遁', '吉', p.gong, '丁+休門+太陰');
      // 三奇入墓: 乙 in 坤2, 丙·丁 in 乾6 (※ 丁 입묘를 艮8 로 보는 유파 있음)
      if ((h === '乙' && p.gong === 2) || ((h === '丙' || h === '丁') && p.gong === 6)) push('三奇入墓', '凶', p.gong, `${h} 입묘`);
      // 六儀擊刑: 戊3 己2 庚8 辛9 壬4 癸4
      const jx: Record<string, number> = { 戊: 3, 己: 2, 庚: 8, 辛: 9, 壬: 4, 癸: 4 };
      if (jx[h] === p.gong) push('六儀擊刑', '凶', p.gong, `${h} 격형`);
    }
    // 門迫: 門克宮
    if (p.doorVsPalace === '迫') push('門迫', '凶', p.gong, `${p.door} 이 ${p.trigram}궁을 극함`);
  }
  return out;
}

export { STEM_ELEMENT, BRANCH_ELEMENT };
