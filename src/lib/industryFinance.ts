import { readCsv } from './csv';
/** 산업별 자금 흐름(운영자 지시 2026-10-14 '산업 중심으로 — 그렇게 진행해'): 한국은행 대구 예금은행 산업별 대출금(data/bok/daegu_loans_industry.csv, 분기 말 잔액)을
 *  같은 산업의 부가가치(KOSIS 지역소득, grdp-sido-industry-all) · 종사자(전국사업체조사, biz-census-sido-industry-all) 비중과 나란히 놓는다.
 *  값은 원 통계 그대로, 비중·지수는 나눗셈만. 평가·순위 없음. 제조업은 대출 자료가 한 덩어리라 세부 업종으로 나누지 않는다. */

/** 대출 표의 업종 10개 ↔ 지역소득 경제활동 ↔ 사업체조사 대분류 */
export const SECTORS = [
  { key: '제조업', loan: '제조업', gva: '제조업', emp: '제조업(10~34)' },
  { key: '부동산업', loan: '부동산업', gva: '부동산업', emp: '부동산업(68)' },
  { key: '도매 및 소매업', loan: '도매 및 소매업', gva: '도매 및 소매업', emp: '도매 및 소매업(45~47)' },
  { key: '숙박 및 음식점업', loan: '숙박 및 음식점업', gva: '숙박 및 음식점업', emp: '숙박 및 음식점업(55~56)' },
  { key: '건설업', loan: '건설업', gva: '건설업', emp: '건설업(41~42)' },
  { key: '농림어업', loan: '농림어업', gva: '농업 임업 및 어업', emp: '농업 임업 및 어업(01~03)' },
  { key: '운수 및 창고업', loan: '운수 및 창고업', gva: '운수 및 창고업', emp: '운수 및 창고업(49~52)' },
  { key: '금융 및 보험업', loan: '금융 및 보험업', gva: '금융 및 보험업', emp: '금융 및 보험업(64~66)' },
  { key: '전기·가스·증기', loan: '전기·가스·증기·공기조절', gva: '전기 가스 증기 및 공기 조절 공급업', emp: '전기 가스 증기 및 공기조절 공급업(35)' },
  { key: '광업', loan: '광업', gva: '광업', emp: '광업(05~08)' },
] as const;
export const OTHER = '그 밖의 업종';

const num = (v: string | undefined) => { const n = Number(String(v ?? '').replace(/,/g, '')); return v != null && v !== '' && Number.isFinite(n) ? n : null; };

type LoanSeries = { periods: string[]; prelim: Set<string>; val: (col: string, p: string) => number | null };
let _loans: LoanSeries | null = null;
export function loanSeries(): LoanSeries {
  if (_loans) return _loans;
  const m = new Map<string, number>(); const ps = new Set<string>(); const prelim = new Set<string>();
  for (const r of readCsv('data/bok/daegu_loans_industry.csv')) {
    const v = num(r.value); if (v == null) continue;
    m.set(`${r.column}|${r.period}`, v); ps.add(r.period); if (r.prelim) prelim.add(r.period);
  }
  // 연말 비교 기준은 연간 행(YYYY = 그해 4분기 말)과 분기 행. 2020 은 분기 행이 없어 연간 행을 2020 말로 쓴다.
  const periods = [...ps].filter(p => /Q/.test(p) || p === '2020').sort((a, b) => (a === '2020' ? '2020-Q4' : a).localeCompare(b === '2020' ? '2020-Q4' : b));
  _loans = { periods, prelim, val: (c, p) => m.get(`${c}|${p}`) ?? null };
  return _loans;
}
export const qLabel = (p: string) => p === '2020' ? '2020년 말' : `${p.slice(0, 4)}년 ${p.slice(-1)}분기`;
export const qShort = (p: string) => p === '2020' ? '20말' : `${p.slice(2, 4)}.${p.slice(-1)}Q`;

/** 지역소득: 대구 명목 총부가가치(기초가격) 대비 업종 비중, 최근 연도 */
function gvaShares() {
  const rows = readCsv('data/kosis/grdp-sido-industry-all.csv').filter(r => r.C1_NM === '대구광역시' && r.ITM_NM === '명목');
  const year = rows.reduce((y, r) => (r.PRD_DE > y ? r.PRD_DE : y), '');
  const at = (name: string) => num(rows.find(r => r.PRD_DE === year && r.C2_NM.trim() === name)?.DT);
  return { year, total: at('총부가가치(기초가격)'), at };
}
/** 전국사업체조사: 대구 종사자 수, 최근 연도 */
function empShares() {
  const rows = readCsv('data/kosis/biz-census-sido-industry-all.csv').filter(r => r.C1_NM === '대구' && r.ITM_NM === '종사자수' && r.C3_NM === '계');
  const year = rows.reduce((y, r) => (r.PRD_DE > y ? r.PRD_DE : y), '');
  const at = (name: string) => num(rows.find(r => r.PRD_DE === year && r.C2_NM.trim() === name)?.DT);
  return { year, total: at('전체 산업'), at };
}

export type ShareRow = { key: string; loanLatest: number | null; loanBase: number | null; shLoanLatest: number | null; shLoanBase: number | null; gva: number | null; shGva: number | null; emp: number | null; shEmp: number | null };
export type Shares = { rows: ShareRow[]; latest: string; base: string; gvaYear: string; empYear: string; prelimLatest: boolean; totals: { loanLatest: number | null; loanBase: number | null; gva: number | null; emp: number | null } };

/** 업종별 비중 — 대출은 '산업별 소계'(기업 대출, 가계 제외) 대비, 부가가치는 총부가가치 대비, 종사자는 전체 산업 대비. '그 밖의 업종' = 합계 − 10개 */
export function industryShares(): Shares | null {
  const L = loanSeries(); if (!L.periods.length) return null;
  const g = gvaShares(), e = empShares();
  const latest = L.periods[L.periods.length - 1];
  const base = L.periods.includes(`${g.year}-Q4`) ? `${g.year}-Q4` : latest;   // 부가가치와 같은 해 말
  const tot = (p: string) => L.val('산업별 소계', p);
  const pct = (a: number | null, b: number | null) => (a != null && b ? (a / b) * 100 : null);
  const rows: ShareRow[] = SECTORS.map(s => {
    const lL = L.val(s.loan, latest), lB = L.val(s.loan, base), gv = g.at(s.gva), em = e.at(s.emp);
    return { key: s.key, loanLatest: lL, loanBase: lB, shLoanLatest: pct(lL, tot(latest)), shLoanBase: pct(lB, tot(base)), gva: gv, shGva: pct(gv, g.total), emp: em, shEmp: pct(em, e.total) };
  });
  const rest = (f: (r: ShareRow) => number | null, total: number | null) => total == null ? null : total - rows.reduce((a, r) => a + (f(r) ?? 0), 0);
  const o = { lL: rest(r => r.loanLatest, tot(latest)), lB: rest(r => r.loanBase, tot(base)), gv: rest(r => r.gva, g.total), em: rest(r => r.emp, e.total) };
  rows.push({ key: OTHER, loanLatest: o.lL, loanBase: o.lB, shLoanLatest: pct(o.lL, tot(latest)), shLoanBase: pct(o.lB, tot(base)), gva: o.gv, shGva: pct(o.gv, g.total), emp: o.em, shEmp: pct(o.em, e.total) });
  return { rows, latest, base, gvaYear: g.year, empYear: e.year, prelimLatest: L.prelim.has(latest), totals: { loanLatest: tot(latest), loanBase: tot(base), gva: g.total, emp: e.total } };
}

/** 업종별 대출 잔액 지수(2020년 말 = 100) — 작은 그래프용. 광업(수백억 원)·전기·가스(3천억 원대, 2021년 4분기에 한 분기만 5배로 튐)는 잔액이 작아 표에만 둔다 */
export const TABLE_ONLY = ['전기·가스·증기', '광업'];
export type IndexSeries = { key: string; points: { p: string; v: number; idx: number }[] };
export function loanIndex(): { series: IndexSeries[]; periods: string[]; base: string } {
  const L = loanSeries(); const base = '2020';
  const cols = [{ key: '산업별 소계', loan: '산업별 소계' }, ...SECTORS.filter(s => !TABLE_ONLY.includes(s.key))];
  const series = cols.map(c => {
    const b = L.val(c.loan, base);
    const points = L.periods.map(p => { const v = L.val(c.loan, p); return v != null && b ? { p, v, idx: (v / b) * 100 } : null; }).filter(Boolean) as IndexSeries['points'];
    return { key: c.key, points };
  });
  return { series, periods: L.periods, base };
}
