import fs from 'node:fs';
import { readCsv, companies, complexes } from './csv';
import { kosisTable } from './kosis';
import { industryGroups } from './industry';
/** /stats/districts/ — 구·군 경제 현황(운영자 지시 2026-10-26 '구·군 경제 현황 만들어봐').
 *  이미 받아 둔 공개 자료만 구·군으로 나눠 나란히 놓는다: 주민등록인구·지역별고용조사(KOSIS), 국민연금 가입 사업장 공개 파일, 기업 사전,
 *  인구총조사 통근·통학(2020), 한국관광 데이터랩. 근거마다 기준(거주지·사업장 소재지·공장 등록)이 달라 서로 더하거나 나누지 않는다.
 *  값은 원 자료 그대로, 묶음 합·비중 나눗셈만. 평가·순위 없음 — 행 순서는 행정 순서. */

export const GU = ['중구', '동구', '서구', '남구', '북구', '수성구', '달서구', '달성군', '군위군'] as const;
const NPS_CODE: Record<string, string> = { '110': '중구', '140': '동구', '170': '서구', '200': '남구', '230': '북구', '260': '수성구', '290': '달서구', '710': '달성군', '720': '군위군' };
const DL_CODE: Record<string, string> = { '27110': '중구', '27140': '동구', '27170': '서구', '27200': '남구', '27230': '북구', '27260': '수성구', '27290': '달서구', '27710': '달성군', '27720': '군위군' };
const num = (v: unknown): number | null => { const n = Number(String(v ?? '').replace(/,/g, '')); return v === '' || v == null || !Number.isFinite(n) ? null : n; };
const ymLabel = (ym: string) => `${ym.slice(0, 4)}년 ${Number(ym.slice(-2))}월`;

/** 주민등록인구(KOSIS gu_population 표). */
export function population() {
  const t = kosisTable('gu_population');
  if (!t) return null;
  const c = t.columns;
  const iNow = c.findIndex(x => /^\d{4}-\d{2}/.test(x)), i15 = c.findIndex(x => x.startsWith('2015')), iEnd = c.findIndex(x => x.includes('연말'));
  const by = new Map(t.rows.map(r => [String(r[0]), { now: num(r[iNow]), y2015: num(r[i15]), yEnd: num(r[iEnd]) }]));
  return { latest: t.latest, endLabel: c[iEnd]?.replace('(명)', '') ?? '', by, source: t.source };
}

/** 지역별고용조사 시군구·산업별 취업자(거주지 기준, 천 명, KOSIS employment_gu 표). */
export function employed() {
  const t = kosisTable('employment_gu');
  if (!t) return null;
  const groups = t.columns.slice(2).map(s => s.replace(/\s*\([A-Z~]+\)\s*$/, '').trim());
  const by = new Map(t.rows.map(r => [String(r[0]), { total: num(r[1]), g: r.slice(2).map(num) }]));
  const period = t.title.match(/\((\d{4}년 [상하]반기)/)?.[1] ?? t.latest;
  return { period, groups, by, source: t.source };
}

/** 국민연금 업종 코드(6자리, 옛 한국표준산업분류 바탕) 앞 두 자리 → 지역별고용조사와 같은 산업 묶음. 00 해당없음·99 사업자번호 없음은 미분류. */
export const NPS_GROUPS = ['농림어업', '광·제조업', '건설업', '도소매·숙박음식', '전기·운수·통신·금융', '사업·개인·공공서비스 등', '미분류'];
const npsGroup = (code: string): number => {
  const p = Number(code.slice(0, 2));
  if (!code || p === 0 || p === 99 || !Number.isFinite(p)) return 6;
  if (p <= 5) return 0;                       // 01~05 농업·임업·어업
  if (p <= 38) return 1;                      // 10~14 광업, 15~38 제조업(재생·소사장 포함)
  if (p === 40 || p === 41) return 4;         // 전기·가스·수도
  if (p === 45 || p === 46) return 2;         // 건설
  if (p >= 50 && p <= 55) return 3;           // 도소매·숙박음식
  if ((p >= 60 && p <= 67) || p === 72) return 4;   // 운수·통신·금융보험, 72 정보처리·소프트웨어
  return 5;                                   // 부동산·사업서비스·교육·보건·오락·개인서비스 등
};
export type Nps = { ym: string; sites: number; members: number; gain: number; loss: number; g: number[] };
const npsCache = new Map<string, Map<string, Nps> | null>();
function npsMonth(ym: string): Map<string, Nps> | null {
  if (npsCache.has(ym)) return npsCache.get(ym)!;
  const rows = readCsv(`data/nps/${ym}.csv`);
  if (!rows.length) { npsCache.set(ym, null); return null; }
  const by = new Map<string, Nps>(GU.map(g => [g, { ym, sites: 0, members: 0, gain: 0, loss: 0, g: NPS_GROUPS.map(() => 0) }]));
  for (const r of rows) {
    const gu = NPS_CODE[r['법정동주소광역시시군구코드']]; const o = gu ? by.get(gu) : null;
    if (!o) continue;
    o.gain += num(r['신규취득자수']) ?? 0; o.loss += num(r['상실가입자수']) ?? 0;
    if (r['사업장가입상태코드'] !== '1') continue;    // 2 = 탈퇴 사업장
    const m = num(r['가입자수']) ?? 0;
    o.sites++; o.members += m; o.g[npsGroup(r['사업장업종코드'] ?? '')] += m;
  }
  npsCache.set(ym, by); return by;
}
/** 최근 달과 비교 달. 2025-06 판부터 파일 추출 범위가 달라져(data/nps/README) 비교 달은 2025-06 이후 가장 이른 달. */
export function nps() {
  const months = fs.existsSync('data/nps') ? fs.readdirSync('data/nps').map(f => f.match(/^(\d{6})\.csv$/)?.[1]).filter((x): x is string => !!x).sort() : [];
  const latest = months.at(-1);
  if (!latest) return null;
  const sameYear = months.find(m => m === `${Number(latest.slice(0, 4)) - 1}${latest.slice(4)}` && m >= '202506');
  const base = sameYear ?? months.find(m => m >= '202506' && m < latest) ?? null;
  return { latest, latestLabel: ymLabel(latest), base, baseLabel: base ? ymLabel(base) : '', now: npsMonth(latest)!, prev: base ? npsMonth(base) : null };
}

/** 기업 사전(팩토리온 공장등록 + 산단 외 기업) 구·군 × 산업 그룹 기업 수. */
export function firms() {
  const groups = industryGroups().map(g => g.name);
  const by = new Map(GU.map(g => [g, { total: 0, fo: 0, foWorkers: 0, g: new Map<string, number>() }]));
  for (const c of companies()) {
    const o = by.get(c.district as typeof GU[number]); if (!o) continue;
    o.total++; o.g.set(c.sector_group, (o.g.get(c.sector_group) ?? 0) + 1);
    if (c.id.startsWith('c')) { o.fo++; o.foWorkers += Number(c.workers) || 0; }
  }
  const asOf = companies().find(c => c.id.startsWith('c'))?.as_of ?? '';
  return { groups: groups.filter(n => [...by.values()].some(o => o.g.get(n))), by, asOf };
}

/** 산업단지(팩토리온 단지 목록의 위치 칸)에 구·군 이름이 들어간 곳. 두 구·군에 걸친 단지는 양쪽에 적는다. */
export function complexesByGu() {
  const by = new Map<string, { name: string; firms: number; workers: number; shared: boolean }[]>(GU.map(g => [g, []]));
  for (const c of complexes()) {
    const hit = GU.filter(g => (c.location ?? '').split(/[·,\s]+/).some(t => t === g));
    for (const g of hit) by.get(g)!.push({ name: c.name, firms: num(c.firms) ?? 0, workers: num(c.workers) ?? 0, shared: hit.length > 1 });
  }
  return { by, asOf: complexes()[0]?.as_of ?? '' };
}

/** 인구총조사 현 거주지 × 통근·통학지(12세 이상, KOSIS DT_1PA2007, 대구·경북 표). 같은 이름(남구·북구)이 포항시 아래에도 있어 행 순서로 대구·경북을 가른다.
 *  2020년 군위군은 경북 소속이라 경북 쪽 군위군 행을 쓴다. 통근·통학을 합친 인원이며, 대구·경북 밖에 사는 사람의 유입은 이 표에 없다. */
export function commute() {
  const rows = readCsv('data/kosis/commute-od-dg.csv').filter(r => r.ITM_NM.startsWith('통근통학인구'));
  if (!rows.length) return null;
  const year = rows.map(r => r.PRD_DE).sort().at(-1)!;
  const cell = new Map<string, number>();
  let c1Scope = '', c1Prev = '', c1Key = '', c2Scope = '';
  for (const r of rows.filter(r => r.PRD_DE === year)) {
    if (r.C1_NM !== c1Prev) {   // 새 거주지 묶음
      c1Prev = r.C1_NM;
      if (r.C1_NM === '대구광역시') c1Scope = '대구'; else if (r.C1_NM === '경상북도') c1Scope = '경북'; else if (r.C1_NM === '계') c1Scope = '';
      c1Key = ['계', '대구광역시', '경상북도'].includes(r.C1_NM) ? r.C1_NM : `${c1Scope}:${r.C1_NM}`;
      c2Scope = '';
    }
    if (r.C2_NM === '대구광역시') c2Scope = '대구'; else if (r.C2_NM === '경상북도') c2Scope = '경북'; else if (r.C2_NM === '계') c2Scope = '';
    const c2Key = ['계', '대구광역시', '경상북도', '기타'].includes(r.C2_NM) ? r.C2_NM : `${c2Scope}:${r.C2_NM}`;
    cell.set(`${c1Key}|${c2Key}`, num(r.DT) ?? 0);
  }
  const key = (g: string) => (g === '군위군' ? '경북:군위군' : `대구:${g}`);
  const units = GU.map(key);
  const get = (a: string, b: string) => cell.get(`${a}|${b}`) ?? 0;
  const gbOther = (a: string) => get(a, '경상북도') - (units.includes('경북:군위군') && a !== '경북:군위군' ? get(a, '경북:군위군') : 0);
  const by = new Map(GU.map(g => {
    const k = key(g);
    const total = get(k, '계'), same = get(k, k);
    const toGu = units.filter(u => u !== k).reduce((s, u) => s + get(k, u), 0);       // 다른 대구 구·군(군위 포함)
    const toGb = k === '경북:군위군' ? get(k, '경상북도') - same : gbOther(k);          // 경북(군위 제외)
    const toEtc = Math.max(0, total - same - toGu - toGb);
    const inGu = units.filter(u => u !== k).reduce((s, u) => s + get(u, k), 0);
    const inGb = get('경상북도', k) - (k === '경북:군위군' ? get(k, k) : get('경북:군위군', k));
    return [g, { total, same, toGu, toGb, toEtc, inGu, inGb, net: inGu + inGb - toGu - toGb }];
  }));
  const matrix = GU.map(a => ({ from: a, cells: GU.map(b => get(key(a), key(b))), gb: key(a) === '경북:군위군' ? get(key(a), '경상북도') - get(key(a), key(a)) : gbOther(key(a)) }));
  const gbRow = GU.map(b => get('경상북도', key(b)) - (b === '군위군' ? get(key(b), key(b)) : get('경북:군위군', key(b))));
  return { year, by, matrix, gbRow, url: 'https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1PA2007' };
}

/** 한국관광 데이터랩: 외지인 방문자(연인원)·관광소비(내국인 전체, 신용카드) 최근 12개월 합과 그 앞 12개월 합. */
export function tourism() {
  const V = readCsv('data/tourism/datalab_visitors.csv'), S = readCsv('data/tourism/datalab_spend.csv').filter(r => r.group === '내국인' && r.industry === '전체');
  const months = [...new Set(V.filter(r => DL_CODE[r.code]).map(r => r.ym))].sort();
  if (months.length < 12) return null;
  const last12 = months.slice(-12), prev12 = months.length >= 24 ? months.slice(-24, -12) : [];
  const sum = (rows: Record<string, string>[], code: string, ms: string[], f: string) => {
    const hit = rows.filter(r => r.code === code && ms.includes(r.ym));
    return hit.length === ms.length && ms.length ? hit.reduce((s, r) => s + (num(r[f]) ?? 0), 0) : null;
  };
  const by = new Map(Object.entries(DL_CODE).map(([code, g]) => [g, {
    vis: sum(V, code, last12, 'visitors'), vis0: sum(V, code, prev12, 'visitors'),
    sp: sum(S, code, last12, 'amount_thousand_won'), sp0: sum(S, code, prev12, 'amount_thousand_won'),
  }]));
  return { from: ymLabel(last12[0]), to: ymLabel(last12.at(-1)!), by };
}

/** 국내인구이동통계 시군구별 이동자수(KOSIS DT_1B26001_A01, 저장 키 migration-sido — 시도·시군구 행이 함께 온다).
 *  '대구광역시' 행 바로 뒤의 구·군 행만 대구로 본다(중구·남구 등 같은 이름이 다른 시도에도 있다). 이름 속 띄어쓰기('중  구')는 붙인다.
 *  군위군은 2023년 7월부터 대구 아래에 온다 — 열두 달이 다 있지 않은 기간은 합을 내지 않는다. */
export const MIG_ITEMS = ['총전입', '총전출', '순이동', '시도내이동-시군구간 전입', '시도내이동-시군구간 전출', '시도간전입', '시도간전출'] as const;
export function migration() {
  const rows = readCsv('data/kosis/migration-sido.csv');
  if (!rows.length) return null;
  const v = new Map<string, number>();   // `${item}|${gu}|${YYYYMM}`
  // 행은 지역 묶음(그 안에 항목·달)으로 온다 — 지역 이름이 바뀌는 곳을 묶음 경계로 보고, '대구광역시' 묶음 뒤 구·군 묶음만 대구로 본다.
  let inDaegu = false, block = '';
  for (const r of rows) {
    const nm = r.C1_NM.replace(/\s+/g, '');
    if (r.C1_NM !== block) {
      block = r.C1_NM;
      if (nm === '대구광역시') inDaegu = true;
      else if (!(GU as readonly string[]).includes(nm)) inDaegu = false;
    }
    if (!inDaegu || nm === '대구광역시') continue;
    const n = num(r.DT); if (n != null) v.set(`${r.ITM_NM}|${nm}|${r.PRD_DE}`, n);
  }
  const months = [...new Set(rows.map(r => r.PRD_DE))].sort();
  const latest = months.at(-1)!;
  const last12 = months.slice(-12), prev12 = months.length >= 24 ? months.slice(-24, -12) : [];
  const sum = (item: string, g: string, ms: string[]) => { if (!ms.length) return null; let s = 0; for (const m of ms) { const x = v.get(`${item}|${g}|${m}`); if (x == null) return null; s += x; } return s; };
  const years = [...new Set(months.map(m => m.slice(0, 4)))].filter(y => months.filter(m => m.startsWith(y)).length === 12);
  const by = new Map(GU.map(g => {
    const s = (it: string, ms = last12) => sum(it, g, ms);
    const inner = s('시도내이동-시군구간 전입'), innerOut = s('시도내이동-시군구간 전출'), sidoIn = s('시도간전입'), sidoOut = s('시도간전출');
    return [g, {
      inflow: s('총전입'), outflow: s('총전출'), net: s('순이동'), netPrev: s('순이동', prev12),
      innerNet: inner != null && innerOut != null ? inner - innerOut : null, sidoNet: sidoIn != null && sidoOut != null ? sidoIn - sidoOut : null,
      latestNet: v.get(`순이동|${g}|${latest}`) ?? null,
      yearNet: years.map(y => sum('순이동', g, months.filter(m => m.startsWith(y)))),
    }];
  }));
  return { latest: ymLabel(latest), from: ymLabel(last12[0]), years, by, url: 'https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1B26001_A01' };
}

/** 소상공인시장진흥공단 상가(상권)정보 대구 집계(scripts/fetch_sbiz_stores.py → data/stores/). 상가업소 명단의 점포 수이지 사업체 조사 값이 아니다. */
export function stores() {
  let idx: { quarters: Record<string, { stores: number; file: string }>; source?: string; url?: string };
  try { idx = JSON.parse(fs.readFileSync('data/stores/index.json', 'utf-8')); } catch { return null; }
  const qs = Object.keys(idx.quarters).filter(q => fs.existsSync(`data/stores/gu_${q}.csv`)).sort();
  const q = qs.at(-1); if (!q) return null;
  const qLabel = (x: string) => `${x.slice(0, 4)}년 ${x.slice(-1)}분기`;
  const load = (x: string) => readCsv(`data/stores/gu_${x}.csv`);
  const cur = load(q);
  const yearAgo = `${Number(q.slice(0, 4)) - 1}${q.slice(4)}`;
  const prev = qs.includes(yearAgo) ? load(yearAgo) : null;
  const large = [...new Set(cur.map(r => r.large))].sort((a, b) => cur.filter(r => r.large === b).reduce((s, r) => s + Number(r.stores), 0) - cur.filter(r => r.large === a).reduce((s, r) => s + Number(r.stores), 0));
  const total = (rows: Record<string, string>[], g: string, l?: string) => rows.filter(r => r.sigungu === g && (!l || r.large === l)).reduce((s, r) => s + Number(r.stores), 0);
  const flow = readCsv('data/stores/flow.csv').filter(r => r.to === q);
  const from = flow[0]?.from ?? '';
  const by = new Map(GU.map(g => {
    const fl = flow.filter(r => r.sigungu === g);
    return [g, { total: total(cur, g), yearAgo: prev ? total(prev, g) : null, l: large.map(l => total(cur, g, l)),
      fresh: fl.length ? fl.reduce((s, r) => s + Number(r.new), 0) : null, gone: fl.length ? fl.reduce((s, r) => s + Number(r.gone), 0) : null,
      lNew: large.map(l => fl.filter(r => r.large === l).reduce((s, r) => s + Number(r.new), 0)), lGone: large.map(l => fl.filter(r => r.large === l).reduce((s, r) => s + Number(r.gone), 0)) }];
  }));
  const dong = readCsv(`data/stores/dong_${q}.csv`);
  const dongs = GU.flatMap(g => [...new Set(dong.filter(r => r.sigungu === g).map(r => r.dong))].sort((a, b) => a.localeCompare(b, 'ko')).map(d => ({ g, d, total: dong.filter(r => r.sigungu === g && r.dong === d).reduce((s, r) => s + Number(r.stores), 0), l: large.map(l => Number(dong.find(r => r.sigungu === g && r.dong === d && r.large === l)?.stores ?? 0)) })));
  return { q: qLabel(q), yearAgo: prev ? qLabel(yearAgo) : '', from: from ? qLabel(from) : '', large, by, dongs, quarters: qs.map(qLabel), source: idx.source ?? '', url: idx.url ?? '' };
}
