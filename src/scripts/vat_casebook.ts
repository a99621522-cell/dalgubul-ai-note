/** 신고별 경정청구 작업서(엑셀) — 부가세 신고를 모르는 공무원이 그대로 따라 하게(운영자 2026-11-24 '공공세무 전문가·사이트 구축 전문가라면 … 신고한 사례별로 경정신고서 만들고 근거와 이유를 제시해줘, 엑셀파일이 좋을 것 같아').
 *  올린 신고서(예정·확정) 한 장마다 시트 한 장: 홈택스 경정청구 화면에 옮길 칸(당초 → 경정 후) · 불공제 명세서 고칠 값 · 쉬운 말 이유 · 근거 조문과 유권해석 · 시설별 내역 · 확인할 것 · 붙임 서류 · 검토란.
 *  숫자는 돌려받기 화면의 건별 판정(judge — 새 규칙 없음)을 그 신고서의 신고기간 달에 맞춰 나눈 것. 매입 목록이 없으면 나라장터 계약 어림(추정)을 그 과세기간 확정 신고서에 둔다.
 *  담당자 이름·전화는 넣지 않는다(검토란은 빈칸). 판정은 참고이며 기관의 판단이 아니다. */
import { fmt, LAW, lawUrl, type Data, type Basis } from './vat_rules';
import { latestDocs, type BaseRow, type FiledDoc } from './vat_unlock';
import { xlsxBlob, type Sheet } from './xlsx_write';
import { corrReason, type CorrDoc } from './vat_diag';

export type CbRow = { d: string; sup: string; sreg: string; desc: string; tax: number; amt: number; claim: number; fac: string; facType?: string; share?: number; label: string; basis: Basis[]; why: string[] };
export type CbCand = { k: string; amt: number; byFac: { fac: string; est: number; type?: string; share?: number }[]; sups: number };
type Cell = (string | number | null | undefined);

const LAWFULL: Record<string, string> = { act: '부가가치세법', decree: '부가가치세법 시행령', rule: '부가가치세법 시행규칙', basic: '국세기본법', special: '조세특례제한법', special_decree: '조세특례제한법 시행령', waste: '폐기물관리법' };
/** 자주 나오는 조문 — 무엇을 정한 조문인지 한 줄(조문 제목) */
const ART: Record<string, string> = {
  'act 제38조': '공제하는 매입세액 — 사업에 쓰려고 산 재화·용역의 부가세는 매출세액에서 뺀다', 'act 제39조': '공제하지 아니하는 매입세액 — 사업과 관련 없는 지출(제1항 제4호)·면세사업 관련(제1항 제7호) 등',
  'act 제40조': '공통매입세액의 안분 — 과세·면세에 같이 쓴 매입세액은 나눠서 공제', 'act 제26조': '면세 — 국가·지자체가 공급하는 재화·용역은 면세(제1항 제19호), 다만 시행령 제46조에 적힌 사업은 과세',
  'decree 제46조': '국가·지자체가 공급해도 과세되는 사업 — 스포츠시설 운영업·부동산 임대업·숙박업 등', 'decree 제81조': '공통매입세액의 안분 계산 — 공급가액 비율, 그게 없으면 매입가액·예정공급가액·예정사용면적 비율(제4항)',
  'decree 제82조': '공통매입세액의 정산', 'decree 제83조': '납부세액·환급세액의 재계산', 'decree 제70조': '수정세금계산서 발급 사유와 기한',
  'basic 제45조의2': '경정 등의 청구 — 법정신고기한이 지난 뒤 5년 안에 과다 신고한 세액을 고쳐 달라고 청구', 'basic 제52조': '국세환급가산금 — 돌려받을 때 이자 상당액을 더함',
};
const lawLine = (D: Data, b: Basis) => [`${LAWFULL[b.law] ?? LAW[b.law] ?? b.law} ${b.art}`, ART[`${b.law} ${b.art}`] ?? '(시설 종류 판정에 쓴 조문 — 원문 링크에서 확인)', (() => { try { return lawUrl(D, b); } catch { return ''; } })()];
const pName = (k: string) => { const [y, h] = k.split('-'); return `${y}년 제${h}기`; };
/** 법정신고기한(예정 4·10월 25일, 확정 7월·다음 해 1월 25일 — 토·일이면 다음 월요일, 공휴일은 반영하지 않음) */
function legalDue(y: number, h: number, pre: boolean): string { const [yy, mm] = h === 1 ? (pre ? [y, 4] : [y, 7]) : (pre ? [y, 10] : [y + 1, 1]); const d = new Date(yy, mm - 1, 25); while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() + 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
/** 경정청구 기한 — 그 과세기간 확정신고기한 + 5년(국세기본법 제45조의2 제1항). 예정신고분도 확정신고기한부터 센다(서면법규과-385) */
const claimDue = (y: number, h: number) => h === 1 ? `${y + 5}-07-25` : `${y + 6}-01-25`;
const days = (to: string, today: string) => Math.round((new Date(to).getTime() - new Date(today).getTime()) / 864e5);
const tax = (d: FiledDoc, n: number) => d.cells[n]?.tax ?? null;
const amt = (d: FiledDoc, n: number) => d.cells[n]?.amt ?? null;

export type CbIn = { org: string; reg: string; today: string; docs: FiledDoc[]; rows: CbRow[]; revText?: Record<string, string>; cand?: CbCand[]; corr?: Map<string, CorrDoc[]>; revByFac?: Record<string, number>; areaFac?: string[]; conf?: Conf; deptByFac?: Record<string, string> };
/** 제출 전 확인(화면에서 누름, 2026-11-24 운영자 '공무원이 기재 할 일을 최대한 줄여') — 시설별 관람석·강습료·과세 매출 신고, 당초 안분 기준, 3등급 수정신고를 같이 낼지. 'yes'·'no' 만, 비면 모름 */
export type Conf = { fac?: Record<string, { seats?: 'yes' | 'no'; lessons?: 'yes' | 'no'; sales?: 'yes' | 'no' }>; apport?: 'supply' | 'other'; g3?: 'together' | 'later'; at?: string };   /* revByFac: 시설 이름 → 세입예산 연 수입(원, 기관 설정 메모의 세입예산서 줄) */   /* corr: 신고서 숫자만으로 고친 값(진단의 안분 재계산 등) */
const short = (n: string) => n.replace(/\(.*?\)/g, '').replace(/\s+/g, ' ').trim();
/** 신고서별 고친 신고서 → 국세청 경정청구서 서식(vat_claimform claimFormPdf)·사유서에 그대로 넣는 값. 열쇠 'YYYY-H|0(예정)·1(확정)' 순서가 PDF 쪽 순서 */
export type Case = { d: FiledDoc; k: string; pre: boolean; nextFin: boolean; name: string; rows: CbRow[]; listTax: number; should: number; gainAmt: number | null; gain: number; est?: CbCand; due: string; cdue: string; left: number; mode: 'list' | 'cand' | 'corr' | 'none'; sheet: string; corr?: CorrDoc };
type FacSum = { fac: string; type?: string; share?: number; n: number; tax: number; claim: number; label: string };
function buildCases(D: Data, o: CbIn, pick?: (g: Grade) => boolean): { cases: Case[]; docs: FiledDoc[]; facsOf: (c: Case) => FacSum[] } {
  void D; const docs = latestDocs(o.docs).sort((a, b) => a.year - b.year || a.half - b.half || a.from - b.from);
  const cand = new Map((o.cand ?? []).map(c => [c.k, c]));
  /* 신고서 → 그 신고기간 달의 매입 건 */
  const cases: Case[] = docs.map(d => {
    const k = `${d.year}-${d.half}`; const pre = d.kind === '예정'; const mon = (r: CbRow) => { const y = Number(r.d.slice(0, 4)), m = Number(r.d.slice(5, 7)); return y === d.year && m >= d.from && m <= d.to; };
    const rows = o.rows.filter(mon); const listTax = rows.reduce((n, r) => n + r.tax, 0); const should = rows.reduce((n, r) => n + r.claim, 0);
    const ded = tax(d, 18) ?? 0; const est = !o.rows.length && !pre ? cand.get(k) : undefined;
    const corr = o.corr?.get(k)?.find(x => x.kind === d.kind && x.delta > 0);
    const gain = rows.length ? Math.max(0, should - ded) : est ? est.amt : corr ? corr.delta : 0; const sAmt = rows.reduce((n, r) => n + (r.tax ? Math.round(r.amt * r.claim / r.tax) : 0), 0); const gainAmt = rows.length && should > 0 ? Math.round(sAmt * gain / should) : null;
    const cdue = claimDue(d.year, d.half);   /* 예정신고분도 확정신고기한부터 5년(국세청 서면법규과-385, 서울고법 2008누9142) */
    const nextFin = pre && !docs.some(x => x.year === d.year && x.half === d.half && x.kind !== '예정') && legalDue(d.year, d.half, false) >= o.today;   /* 확정신고가 아직 — 경정청구 대신 확정신고 (13) 예정신고 누락분으로 */
    return { d, k, pre, name: `${pName(k)} ${d.kind}`, rows, nextFin, listTax, should, gainAmt, gain, est, due: legalDue(d.year, d.half, pre), cdue, left: days(cdue, o.today), mode: rows.length ? 'list' : est ? 'cand' : corr ? 'corr' : 'none', corr: rows.length || est ? undefined : corr, sheet: `${String(d.year).slice(2)}-${d.half}기 ${d.kind}` };
  });
  function facsOf(c: Case): FacSum[] { const m = new Map<string, { fac: string; type?: string; share?: number; n: number; tax: number; claim: number; label: string }>();
    if (c.mode === 'list') for (const r of c.rows) { if (!r.claim) continue; const x = m.get(r.fac) ?? { fac: r.fac, type: r.facType, share: r.share, n: 0, tax: 0, claim: 0, label: r.label }; x.n++; x.tax += r.tax; x.claim += r.claim; m.set(r.fac, x); }
    else if (c.est) { const tot = c.est.byFac.reduce((n, x) => n + x.est, 0) || 1; for (const x of c.est.byFac) m.set(x.fac, { fac: x.fac, type: x.type, share: x.share, n: 0, tax: x.est, claim: Math.round(c.est.amt * x.est / tot), label: '나라장터 계약 어림' + (typeof x.share === 'number' && x.share < 1 ? `(과세 몫 ${Math.round(x.share * 100)}% 반영)` : '') }); }
    return [...m.values()].sort((a, b) => b.claim - a.claim); }
  /* 등급 고르기(세무서 설득 꾸러미 '먼저 낼 묶음' = 1·2등급) — 고른 쟁점의 시설만 남기고 돌려받을 몫을 그 합으로 */
  if (pick) for (const c of cases) { if (c.left < 0 || c.nextFin || c.gain <= 0) continue; const sel = issuesOf(D, o, c, facsOf, docs).filter(i => pick(i.grade)); const g = sel.reduce((n, i) => n + i.amt, 0);
    if (c.mode === 'corr') { if (!g) { c.gain = 0; c.corr = undefined; c.mode = 'none'; } continue; }
    const keep = new Set(sel.map(i => i.fac)); c.gainAmt = c.gainAmt != null && c.gain ? Math.round(c.gainAmt * g / c.gain) : c.gainAmt; c.gain = g;
    c.rows = c.rows.filter(r => !r.claim || keep.has(r.fac)); if (c.est) c.est = { ...c.est, amt: g, byFac: c.est.byFac.filter(x => keep.has(x.fac)) }; }
  return { cases, docs, facsOf };
}
/** 쟁점 등급(세무서 설득 꾸러미, 2026-11-24 docs/prompts/vat_persuade_taxoffice.md) — 판정이 아니라 제출 방법을 정하는 꼬리표.
 *  1 계산 정정(신고서 숫자만) · 2 증빙으로 끝남(과세 시설 지출) · 3 매출과 함께(신고서 과세표준 명세에 그 업종 매출이 없는 시설) · 4 해석 다툼(기준 '확인' 시설·관람석 가능 경기장·추정 과세 몫·본청 공통) */
export type Grade = 1 | 2 | 3 | 4;
export type Issue = { key: string; k: string; name: string; pre: boolean; grade: Grade; fac: string; type?: string; amt: number; why: string; est: boolean; q: string[]; left: number; cdue: string; due: string; gap?: string };
export const GAP: Record<string, [RegExp, string]> = { lodging: [/^55/, '숙박업'], lease: [/^70/, '부동산임대업'], sports: [/^(809|9113)/, '스포츠시설 운영업'] };
/** 그 과세기간 신고서(예정·확정)의 과세표준 명세에 매출이 없는 업종(시설 유형 열쇠). 그 기간 명세를 못 읽었으면 전체 신고서로, 아무 명세도 없으면 빈 집합(모름 — 3등급으로 보내지 않음) */
export function gapTypes(docs: FiledDoc[], k?: string): Set<string> {
  const pd = k ? docs.filter(d => `${d.year}-${d.half}` === k) : []; const s = new Set<string>();
  const has = (ds: FiledDoc[], re: RegExp) => ds.some(d => (d.codes ?? []).some(x => re.test(x.code) && !x.zero));
  if (!pd.length || !pd.some(d => d.codes?.length)) { const all = docs.flatMap(d => d.codes ?? []); if (!all.length) return s; for (const [t, [re]] of Object.entries(GAP)) if (!all.some(x => re.test(x.code) && !x.zero)) s.add(t); return s; }
  /* 그 기간 명세에 업종코드가 없는 과세 매출이 있으면(코드 있는 줄 합 < 과세표준 (9) — (34) 수입금액 제외 줄은 서식상 코드를 적지 않음) 그 줄이 무슨 업종인지 모른다 — 다른 과세기간 절반 이상에 나오는 업종만 그 줄로 본다(환급만: 넓게 보면 매출 없는 시설을 청구해 더 낼 수 있음). */
  const unread = pd.some(d => { const tb = d.cells[9]?.amt; const sum = (d.base ?? []).reduce((n, b) => n + (b.code ? b.amt : 0), 0); return tb != null && tb > 0 && sum < tb - 1000; });
  const others = [...new Set(docs.map(d => `${d.year}-${d.half}`))].filter(x => x !== k);
  for (const [t, [re]] of Object.entries(GAP)) { if (has(pd, re) || (t === 'lease' && leaseAlt(pd))) continue;
    const n = others.filter(x => has(docs.filter(d => `${d.year}-${d.half}` === x), re)).length;
    if (unread && others.length && n * 2 >= others.length) continue; s.add(t); }
  return s; }
/** 부동산임대업(70…) 줄이 없거나 0원이어도, 그 기간 명세에 '임대'가 든 다른 업종 줄(예: 무형재산권 임대업)에 매출이 있으면 임대·대부료를 그 줄로 신고했다고 본다 —
 *  공유재산 대부는 세금계산서를 발급하므로 (1) 세금계산서 발급분과 함께 그 줄에 들어가 매출세액은 낸 것(업종코드만 다름). */
export function leaseAlt(ds: FiledDoc[]): BaseRow | null {
  for (const d of ds) for (const b of d.base ?? []) if (b.code && !/^70/.test(b.code) && b.amt > 0 && /임\s*대/.test(b.label)) return b;
  return null; }
const STADIUM = /운동장|경기장|야구장|축구장|구장/;
function gradeFac(D: Data, o: CbIn, f: { fac: string; type?: string; share?: number }, gap: Set<string>): { grade: Grade; why: string; q: string[]; gap?: string } {
  const fr = f.type ? D.facilities.find(x => x.key === f.type) : undefined;
  if (f.fac === '본청·행정 공통') return { grade: 4, why: '본청·행정과 같이 쓴 지출 — 나누는 기준(매입가액·예정사용면적)을 먼저 정함', q: ['Q22'] };
  if (fr?.status === 'check') return { grade: 4, why: `시설 유형 '${fr.name}'의 과세 여부가 운영 방식(사실)에 달림`, q: ['Q09'] };
  const cf = o.conf?.fac?.[f.fac];
  if (f.type === 'sports' && cf?.seats === 'yes') return { grade: 4, why: '관중용 관람석이 있음(청구인 확인) — 경기장 운영업 면세 여부를 질의로 정한 뒤 청구', q: ['Q12'] };
  if (f.type === 'sports' && cf?.lessons === 'yes') return { grade: 4, why: '직영 강습료 수입이 있음(청구인 확인) — 강습 몫(면세)을 빼는 비율을 정한 뒤 청구', q: ['Q14'] };
  /* 관람석 의심은 이름만으로 하지 않는다(2026-11-24 운영자 '관람객이 없을꺼야, 세입 보면 알 수 있잖아') — 시설 메모(세입예산서 줄)를 알면 입장료·관람료 수입이 있을 때만.
     환급만 원칙에서도 안전: 과세로 청구했는데 세무서가 경기장(면세)으로 보면 매입세액 대신 그동안 과세로 낸 사용료 매출세액을 돌려받는 쪽이라 더 낼 일이 없다 */
  const known = o.revText && f.fac in o.revText; const spect = /입장료|관람료|관람석|관중/.test(o.revText?.[f.fac] ?? '');
  if (f.type === 'sports' && STADIUM.test(f.fac) && cf?.seats !== 'no' && (!known || spect)) return { grade: 4, why: '관람석을 갖춘 경기장인지 확인 필요 — 관람석이 있으면 경기장 운영업으로 면세', q: ['Q12'] };
  if (typeof f.share === 'number' && f.share < 1 && !(o.areaFac ?? []).includes(f.fac)) return { grade: 4, why: `같이 쓰는 건물 — 과세 몫 ${Math.round(f.share * 100)}%는 추정, 용도별 면적표로 정해야 함`, q: ['Q19'] };
  if (cf?.sales === 'no') return { grade: 3, why: '그 기간 사용료를 과세 매출로 신고하지 않음(청구인 확인) — 이번 청구에서 뺌(청구하면 세무서가 매출세액·가산세를 함께 경정해 더 낼 수 있음)', q: ['Q10', 'Q28'], gap: '사용료' };
  if (f.type && gap.has(f.type) && cf?.sales !== 'yes') return { grade: 3, why: `신고서 과세표준 명세에 ${GAP[f.type][1]} 매출이 없음 — 사용료를 과세 매출로 신고했는지 먼저 확인`, q: ['Q10', 'Q28'], gap: GAP[f.type][1] };
  return { grade: 2, why: '과세 매출을 신고하는 시설의 지출 — 세금계산서·계약서로 그 시설 것임을 보임', q: ['Q09', 'Q16'] };
}
function issuesOf(D: Data, o: CbIn, c: Case, facsOf: (c: Case) => FacSum[], docs: FiledDoc[]): Issue[] {
  const base = { key: `${c.k}|${c.pre ? 0 : 1}`, k: c.k, name: c.name, pre: c.pre, left: c.left, cdue: c.cdue, due: c.due };
  if (c.mode === 'corr' && c.corr) return [{ ...base, grade: o.conf?.apport === 'other' ? 4 : 1, fac: '(신고서 숫자로 다시 계산)', amt: c.corr.delta, why: o.conf?.apport === 'other' ? '당초 명세서가 공급가액 비율이 아닌 기준으로 나눔(청구인 확인) — 나눌 기준을 질의로 정한 뒤 청구' : `당초 명세서의 공통매입세액 ${[...new Set(c.corr.parts.map(x => x.sec.replace(/\(.*\)/, '')))].join('·') || '안분'} 계산을 신고서 숫자로 다시 하면 불공제가 줄어듦`, est: false, q: ['Q20', 'Q21'] }];
  const F = facsOf(c).filter(f => f.claim > 0); const tot = F.reduce((n, f) => n + f.claim, 0); if (!tot || c.gain <= 0) return [];
  const gap = gapTypes(docs, c.k); const out = F.map(f => ({ ...base, ...gradeFac(D, o, f, gap), fac: f.fac, type: f.type, amt: Math.floor(c.gain * f.claim / tot), est: c.mode === 'cand' }));
  const rest = c.gain - out.reduce((n, x) => n + x.amt, 0); if (out.length) out[0].amt += rest; return out;
}
/** 경정청구할 신고서(기한 안·확정신고 전 예정 제외·돌려받을 몫 > 0)의 쟁점 목록 — 금액 큰 순이 아니라 신고서 순 */
export function caseIssues(D: Data, o: CbIn): Issue[] { const { cases, docs, facsOf } = buildCases(D, o); return cases.filter(c => c.left >= 0 && !c.nextFin && c.gain > 0).flatMap(c => issuesOf(D, o, c, facsOf, docs)); }
/** 돌려받을 몫 나누기(2026-11-24 수성구 2021년 제2기 — (18)이 (16)보다 커지던 것): 당초 (17)에서 뺄 수 있는 몫 cut(당초 (17)을 넘지 않음)과
 *  당초 신고에 아예 없던 세금계산서라 (10)·(16)에 더할 몫 add(매입처별 세금계산서합계표를 경정청구서와 함께 냄 — 부가가치세법 시행령 제74조 제2호, 가산세 없음 제108조 제6항) */
export function splitGain(d: FiledDoc, g: number, ga: number | null | undefined): { cut: number; add: number; addAmt: number | null; cutAmt: number | null } {
  const c17 = Math.max(0, d.cells[17]?.tax ?? 0), a17 = d.cells[17]?.amt ?? null; const cut = Math.min(g, c17); const add = g - cut;
  if (add > 0 && ga != null && a17 != null) return { cut, add, addAmt: Math.max(0, ga - a17), cutAmt: Math.min(ga, a17) };   /* (17)을 다 빼면 뺀 공급가액 = 당초 (17) 금액 */
  const addAmt = ga != null && g ? Math.round(ga * add / g) : null;
  return { cut, add, addAmt, cutAmt: ga != null ? ga - (addAmt ?? 0) : null }; }
export function caseCorrDocs(D: Data, o: CbIn, pick?: (g: Grade) => boolean): Map<string, CorrDoc[]> {
  const M = new Map<string, CorrDoc[]>(); const { cases, facsOf } = buildCases(D, o, pick);
  const most = (xs: (string | undefined)[]) => { const c = new Map<string, number>(); for (const x of xs) if (x) c.set(x, (c.get(x) ?? 0) + 1); return [...c].sort((a, b) => b[1] - a[1])[0]?.[0] ?? ''; };
  const addr0 = most(cases.map(c => c.d.addr)), office0 = most(cases.map(c => c.d.office)), rep0 = most(cases.map(c => c.d.rep)), tel0 = most(cases.map(c => c.d.tel));
  for (const c of cases) { if (c.left < 0 || c.nextFin || c.gain <= 0) continue; const d = c.d; const t = (n: number) => d.cells[n]?.tax ?? null;
    const ded = t(18) ?? 0, c9 = t(9); const F = facsOf(c); const nd2 = d.nd?.reasons[2]?.tax ?? 0, nd5 = d.nd?.reasons[5]?.tax ?? 0; const why = nd2 >= nd5 && nd2 > 0 ? "'사업과 직접 관련 없는 지출'" : nd5 > 0 ? "'면세사업 관련'" : '불공제';
    if (c.mode === 'corr' && c.corr) { M.set(`${c.k}|${c.pre ? 0 : 1}`, [{ ...c.corr, reg: c.corr.reg || d.reg || o.reg, addr: d.addr || addr0 || undefined, rep: rep0 || d.rep || undefined, tel: tel0 || d.tel || undefined, filedOn: d.filedOn, office: d.office || office0 || undefined, pen: c.corr.pen ?? d.pen ?? null, due: c.corr.due ?? d.due ?? null, tb: c.corr.tb ?? d.cells[9]?.amt ?? null }]); continue; }
    const names = F.slice(0, 3).map(f => short(f.fac)).join('·') + (F.length > 3 ? ` 등 ${F.length}곳` : '');
    const sp = splitGain(d, c.gain, c.gainAmt);
    const reason = sp.add > 0 ? `사용료를 과세 매출로 신고하는 시설(${names})의 공사·관리·운영비 매입세액 ${fmt(c.gain)}원 가운데 ${sp.cut ? `${fmt(sp.cut)}원은 ${why}로 불공제하고 ` : ''}${fmt(sp.add)}원은 받은 세금계산서를 신고에 넣지 않았음. 과세사업에 쓴 매입세액은 공제 대상(부가가치세법 제38조, 같은 법 시행령 제46조)이므로 빠진 세금계산서를 매입처별 세금계산서합계표로 함께 제출하고(같은 법 시행령 제74조 제2호) 공제받는 매입세액을 ${fmt(c.gain)}원 늘려 경정을 청구함. 세부 근거는 붙임 엑셀·사유서.` : `사용료를 과세 매출로 신고하는 시설(${names})의 공사·관리·운영비 매입세액 ${fmt(c.gain)}원을 ${why}로 불공제함. 과세사업에 쓴 매입세액은 공제 대상(부가가치세법 제38조, 같은 법 시행령 제46조)이므로 공제받지 못할 매입세액을 ${fmt(c.gain)}원 줄여 경정을 청구함${F.some(f => typeof f.share === 'number' && f.share < 1) ? '(같이 쓰는 건물은 과세 면적 비율만, 같은 법 시행령 제81조)' : ''}${c.mode === 'cand' ? ' — 금액은 계약으로 짐작한 값, 세금계산서로 확인 뒤 확정' : ''}. 세부 근거는 붙임 엑셀·사유서.`;
    const doc: CorrDoc = { k: c.k, kind: d.kind, file: d.file, reg: d.reg || o.reg, delta: c.gain, reason, addr: d.addr || addr0 || undefined, rep: rep0 || d.rep || undefined, tel: tel0 || d.tel || undefined, filedOn: d.filedOn, office: d.office || office0 || undefined,
      cells: [...(sp.add > 0 ? [{ n: 10, label: '세금계산서 수취분 일반매입', amt: d.cells[10]?.amt ?? null, before: t(10), after: (t(10) ?? 0) + sp.add }] : []), { n: 16, label: '매입세액 합계', amt: d.cells[16]?.amt ?? null, before: t(16), after: (t(16) ?? 0) + sp.add }, { n: 17, label: '공제받지 못할 매입세액', amt: d.cells[17]?.amt ?? null, before: t(17), after: t(17) != null ? t(17)! - sp.cut : null }, { n: 18, label: '차감계(공제받는 매입세액)', amt: d.cells[18]?.amt ?? null, before: ded, after: ded + c.gain }],
      parts: d.nd ? [{ sec: '명세서', rows: [{ label: nd2 >= nd5 ? '② 사업과 직접 관련 없는 지출' : '⑤ 면세사업등 관련', before: nd2 >= nd5 ? nd2 : nd5, after: (nd2 >= nd5 ? nd2 : nd5) - Math.min(sp.cut, nd2 >= nd5 ? nd2 : nd5) }] }] : [],
      payBefore: c9 != null ? c9 - ded : null, payAfter: c9 != null ? c9 - ded - c.gain : null, tb: d.cells[9]?.amt ?? null, pen: d.pen ?? null, due: d.due ?? null };
    M.set(`${c.k}|${c.pre ? 0 : 1}`, [doc]); }
  let pg = 0; for (const k of [...M.keys()].sort()) for (const x of M.get(k)!) x.page = ++pg;
  return M;
}

/** 법령 검토 표 — 원문을 대조한 결론만(평가·절세 문구 없음). 판정은 참고이며 기관의 판단이 아니다 */
export const LEGAL: string[][] = [
  ['지자체 체육시설 사용료의 과세 여부', '지자체가 공급하는 재화·용역은 면세가 원칙이지만, 시행령 제46조 제3호에 적힌 사업(부동산임대업·도매 및 소매업·음식점업·숙박업·골프장 및 스키장 운영업·기타 스포츠시설 운영업)은 과세. 관람석이 없는 수영장·헬스장·테니스장·풋살장·구장 이용료는 기타 스포츠시설 운영업으로 과세이고, 그 시설 매입세액은 공제 대상.', '부가가치세법 제26조 제1항 제19호, 같은 법 시행령 제46조 제3호(2025. 12. 30. 개정 현행 원문 대조), 재경부 부가가치세제과-186(2007. 3. 22.) 질의 8·31, 서면3팀-1502', '사용료에 부가세를 포함해 과세 신고해 온 직영 체육시설의 공사·관리비 매입세액은 공제 대상 — 이번 경정청구의 중심', '시설마다 조례 사용료 표(부가가치세 포함 문구)와 과세표준 명세 업종(809…)을 확인'],
  ['관람석을 갖춘 경기장', '일반 관중이 경기를 관람할 수 있는 시설(다중의 관중을 위한 관람석)을 갖춘 운동장·야구장·축구장·공인 수영장·체육관은 경기장 운영업이라 면세. 경기 없는 시간에 운동 공간으로 빌려주고 받는 사용료도 면세. 이용자 대기·후보선수용 좌석은 관람석이 아님.', '서면인터넷방문상담3팀-1330(2007. 5. 3., 구청 구민운동장 관람석 400석), 법규과-209(2013. 2. 26., 관람석 688석 공인 실내수영장 — 건설 매입세액 불공제), 재경부 부가가치세제과-306(2007. 4. 25.), 통계청 회신(2012. 4. 9.)', '관람석이 있는 운동장으로 판정되면 그 시설 몫은 공제되지 않고(감액), 그동안 과세로 낸 사용료 매출세액을 돌려받는 경정청구로 바뀜', '구민운동장·체육관·수영장의 관람석 유무·규모를 건축물대장·시설 현황으로 확인'],
  ['체육공원 안 운동시설', '지자체가 설치·운영하는 체육공원(시민공원) 안 운동시설 이용료는 체육공원 및 유사공원 운영업으로 면세. 사업자가 빌려 자기 계산으로 운영하면 과세.', '재경부 부가가치세제과-306(2007. 4. 25.)', '도시계획시설 공원 안 시설이면 그 시설 매입세액은 공제 대상이 아님', '도시관리계획 결정(공원) 여부 확인'],
  ['체육시설 안 강습·교육 강좌', '지자체가 직영하는 문화센터 교육 강좌, 별도 운동시설이 필요 없는 요가·댄스 강습은 면세. 체육시설 사용료는 과세. 수영 강습처럼 운동시설 안 강습은 교육이 주인지 시설 이용이 주인지 사실판단(심판례가 갈림).', '재경부 부가가치세제과-186 질의 7·8·14, 서면-2020-부가-6079, 조심2021서1060, 조심2022구6472', '강습료를 면세로 보면 그 체육센터는 과세·면세 공통 — 공급가액 비율로 안분(시행령 제81조)', '강습료·자유 이용료 수입을 나눠 보고 관할 세무서에 강습료 과세 여부 확인'],
  ['야영장·휴양림 숙박', '지자체가 직접 운영하는 오토캠핑장·야영장은 기타 관광 숙박시설 운영업으로 과세(관련 매입세액 공제). 자연휴양림 숲속의 집은 2007년 회신이 자연공원 운영업으로 과세하지 않는다고 했으나 그 뒤 회신은 확인 못함.', '국세청 기준-2016-법령해석부가-0149(2016. 8. 11.), 법규부가2012-402, 재경부 부가가치세제과-186 질의 18', '야영장 사용료를 숙박업 과세 매출로 신고하지 않았다면 매입세액만 공제받을 수 없음', '과세표준 명세에 숙박업(55…) 매출이 있는지 확인'],
  ['사용허가·점용료·임대', '행정재산 사용허가 사용료, 도로·하천·공원 점용료, 건물 일부 임대(카페·은행·자판기 자리)는 부동산임대업으로 과세.', '법제처 15-0228(2015. 7. 22.), 재경부 부가가치세제과-186 질의 3·9·22·24, 서면3팀-927', '임대 공간이 있는 건물의 공통 매입세액은 임대 면적 비율만큼 공제 대상', '임대 면적·사용허가 면적 확인, 부동산임대업(70…) 매출 신고 여부 대조'],
  ['공영주차장', '지자체 직영 주차장은 시행령 제46조 열거 업종이 아니라 면세 — 매입세액 불공제. 주차장 운영 위탁 대가도 면세.', '부가가치세법 시행령 제46조 제3호, 재경부 부가가치세제과-186 질의 6', '공영주차장 공사비 부가세는 돌려받을 수 없음(이 계산에서 0)', '없음'],
  ['개관 전 공사비 매입세액', '과세사업에 쓸 시설을 짓는 동안의 매입세액도 사업자등록 뒤 공급분이면 공제 대상(공급시기가 속한 과세기간). 과세·면세가 섞인 건물은 예정사용면적 비율로 나누고 완공 뒤 실제 면적으로 정산.', '부가가치세법 제38조, 같은 법 시행령 제81조 제4항 단서·제82조, 부산 남구 국민체육센터(2관) 건립비 부가세 15.49억 원 경정청구 환급(2024. 12.)', '건립 중이던 체육시설·복합시설 공사비가 이번 금액의 큰 몫', '설계도면의 용도별 면적으로 과세 몫 확인(시설 설정의 추정값을 실제 면적으로)'],
  ['본청·행정과 같이 쓴 지출', '고유사무(공급가액 없음)가 섞인 공통매입세액은 공급가액 비율을 그대로 쓸 수 없고 매입가액·예정공급가액·예정사용면적 등 다른 합리적 기준으로 나눔.', '대법원 2017두55329, 부가가치세법 시행령 제81조 제4항, 조심2014서3012', '이 계산은 본청 공통 지출을 공제에 넣지 않음(보수적)', '기준을 정하면 세무서 질의로 굳힌 뒤 추가 청구'],
  ['불공제 사유 칸', '고유사무(비과세) 지출은 면세사업등 관련(제7호)이고, 과세 시설 지출은 공제 대상 — ② 사업과 직접 관련 없는 지출(제4호) 하나로 묶을 수 없음.', '부가가치세법 제39조 제1항 제4호·제7호, 같은 법 제10조 제1항(면세사업등 = 면세사업 + 부가가치세가 과세되지 아니하는 사업)', '경정청구서·명세서에서 과세 시설 몫을 ②(또는 ⑤)에서 빼 공제받는 매입세액 (18)로 옮김', '없음'],
  ['경정청구 기한', '법정신고기한이 지난 뒤 5년 안. 예정신고분도 확정신고기한부터 셈. 세무서는 청구일부터 2개월 안에 결과 통지.', '국세기본법 제45조의2 제1항·제3항, 국세청 서면법규과-385(2013. 4. 3.), 서울고법 2008누9142', '2021년 제2기는 2027-01-25가 기한(가장 급함)', '기한이 가까운 신고서부터 접수'],
  ['사업자등록 전·다른 번호로 받은 세금계산서', '사업자등록 신청 전 매입세액은 불공제(과세기간 끝난 뒤 20일 안 신청분은 예외). 고유번호 등 다른 번호로 받은 세금계산서는 받는 쪽이 달라 공제 어려움 — 수정세금계산서는 기한 안에만.', '부가가치세법 제39조 제1항 제2호·제8호, 같은 법 시행령 제70조 제1항', '사업자등록 무렵 과세기간(신고서 (16)이 매입 목록보다 크게 작은 기간)은 금액이 조건부', '홈택스 매입 목록에서 그 세금계산서의 받는 쪽 번호 확인'],
  ['사업장 단위', '시청 산하기관(사업소·시설)도 사업장이 될 수 있고, 사업장별 신고가 원칙. 본청 번호 하나로 모든 시설을 신고해 왔다면 사업자단위과세 등록인지 확인.', '부가가치세법 제6조·제8조, 재경부 부가가치세제과-186 질의 1', '사업장별 등록 대상인데 본청 번호로 받은 세금계산서라면 다른 사업장 명의 문제가 생길 수 있음', '사업자등록증의 사업자단위과세 여부 확인'],
  ['국비·기금 재원', '보조금을 재원으로 산 것이어도 세금계산서를 받은 과세사업 매입세액은 공제 대상. 돌려받은 부가세는 세외수입으로 계상하는 것이 원칙(같은 사업 재투자 가능).', '국세청 부가가치세과-116(2013), 국고보조금 통합관리지침 제26조 제2항, 지방보조금 관리기준 제19조 제2항', '환급금을 국가에 반납할 의무는 원칙상 없음 — 기금 보조는 기금 정산 지침 확인', '보조사업 교부조건·기금 정산 지침에 부가세 환급금 조항이 있는지 확인'],
  ['매출 쪽 대조', '경정청구를 검토하는 세무서가 과세 시설의 매출 신고도 함께 볼 수 있음 — 공제받는 시설의 사용료가 과세 매출로 빠짐없이 신고됐는지가 전제.', '부가가치세법 제38조(과세사업 관련 매입세액), 국세기본법 제45조의2', '사용료 신고가 빠진 시설이 있으면 그 매출세액·가산세가 함께 생김', '과세표준 명세 업종과 세입 결산의 사용료 수입을 기간별로 대조'],
  ['환급가산금·세입 처리', '경정청구로 돌려받는 세액에는 국세환급가산금이 붙음(기산일은 국세기본법 시행령 제43조의3 — 이 검토에서 현행 원문을 열지 못함). 돌려받은 돈은 세입세출외현금에 두지 말고 바로 세입 처리.', '국세기본법 제52조, 같은 법 시행령 제43조의3, 2025년 대구광역시 정부합동감사 지적(부가세 납부잔액 보관)', '환급액이 이 계산보다 가산금만큼 많을 수 있음', '환급 통지 뒤 세입 처리 부서와 맞춤'],
];

/** 세무서 검토 — 경정청구를 받은 세무서가 확인하는 순서(실무 관점, 평가 아님) */
const TAXOFFICE: string[][] = [
  ['청구서 형식과 사유 증명 서류', '경정청구서에는 청구인의 성명·주소, 경정 전과 후의 과세표준·세액, 청구 이유를 적고(시행령 제25조의3 제1항), 서식의 첨부서류 칸대로 사유 증명자료를 붙인다. 세무서는 청구일부터 2개월 안에 결과를 알린다.', '경정청구서(이 묶음 1번), 사유서(3번), 당초 신고서 사본, 고친 공제받지 못할 매입세액 명세서', '국세기본법 제45조의2 제1항·제3항, 같은 법 시행령 제25조의3 제1항, 같은 법 시행규칙 별지 제16호의2서식'],
  ['공제 시설이 실제로 과세 매출을 신고해 왔는지', '매입세액은 과세사업에 쓴 것만 공제된다. 세무서는 과세표준 명세 업종과 그 시설 사용료 수입을 맞춰 보고, 매출이 빠졌으면 공제만 인정하지 않고 매출 누락을 함께 경정할 수 있다.', '시설별 사용료 수입(세입 결산)과 과세표준 명세 업종별 금액 대조표 — 빠진 시설은 청구에서 빼거나 매출 수정신고를 함께', '부가가치세법 제38조·제48조·제49조, 국세기본법 제45조의2'],
  ['세금계산서 하나하나의 실지귀속', '어느 시설 공사·관리에 쓴 것인지가 공제 여부를 가른다. 큰 공사부터 표본으로 본다.', '이 파일 「건별 근거」 + 큰 계약의 계약서·준공검사조서·설계 내역(시설명이 드러나는 것)', '부가가치세법 제38조·제40조'],
  ['같이 쓰는 건물의 과세 몫', '추정 비율은 인정되지 않는다. 신축 건물은 예정사용면적으로 나누고, 면적이 확정되는 과세기간 확정신고 때 정산해야 한다.', '설계도면·건축물대장의 용도별 면적표(수영장·헬스장·도서관·가족센터·주차장 등), 완공 뒤 정산 계산', '부가가치세법 시행령 제81조 제4항 단서·제82조 제2호·제83조'],
  ['관람석이 있는 경기장인지', '관람석을 갖춘 운동장·수영장은 경기장 운영업으로 면세라 그 매입세액은 공제되지 않는다. 운동장은 현장 확인이 나올 수 있다.', '관람석 유무·좌석 수(건축물대장·시설 현황), 사용료 조례 별표', '서면인터넷방문상담3팀-1330, 법규과-209, 부가가치세법 시행령 제46조 제3호'],
  ['강습료의 성격', '체육센터 수입의 대부분이 강습이면 교육 용역(면세) 여부를 묻고, 면세면 공통매입세액 안분을 요구할 수 있다.', '체육센터별 강습료·자유 이용료 수입 구분, 강습 운영 방식', '재경부 부가가치세제과-186 질의 7·8·14, 조심2021서1060·조심2022구6472'],
  ['개관 전 공사비', '과세사업에 쓸 시설인지(사용료 조례·운영 계획)와 사업자등록 뒤 공급분인지를 본다.', '사용료 조례(부가가치세 포함 문구)·개관 일정·운영 계획, 사업자등록증(개업일)', '부가가치세법 제38조·제39조 제1항 제8호'],
  ['받는 쪽 번호와 합계표', '세금계산서의 공급받는자가 구의 사업자등록번호여야 한다. 신고 때 매입처별 세금계산서합계표에 빠진 세금계산서는 경정청구서와 함께 합계표를 내면 공제된다.', '홈택스 매입 목록(공급받는자 번호 확인), 빠진 세금계산서의 매입처별 세금계산서합계표', '부가가치세법 제39조 제1항 제1호·제2호, 같은 법 시행령 제74조 제2호·제75조'],
  ['사업장 단위', '시설이 별도 사업장인데 본청 번호로 신고했다면 사업장 문제를 본다.', '사업자등록증(사업자단위과세 여부), 시설별 사업장 등록 현황', '부가가치세법 제6조·제8조, 재경부 부가가치세제과-186 질의 1'],
  ['환급 규모에 따른 검증', '환급액이 크면 서면 검토에 그치지 않고 현장 확인·환급 검증이 나올 수 있다. 결과에 동의하지 않으면 통지일(통지가 없으면 2개월이 지난 날)부터 90일 안에 이의신청·심사청구·심판청구.', '담당 부서 연락 창구 하나로 정하고, 위 서류를 시설별 묶음으로', '국세기본법 제45조의2 제3항, 제61조·제66조·제68조'],
  ['매출 누락이 드러났을 때의 가산세', '과소신고 가산세 10%, 납부지연 가산세(하루 10만분의 22), 사업자에게 빌려주고 세금계산서를 발급하지 않았으면 공급가액의 2%. 법정신고기한 뒤 2년 안에 스스로 수정신고하면 과소신고 가산세가 감면된다(1개월 90% ~ 2년 10%).', '빠진 매출이 있으면 경정청구와 같은 때에 수정신고(감면 기간 안의 과세기간부터)', '국세기본법 제47조의3·제47조의4·제48조 제2항, 부가가치세법 제60조 제2항'],
];
/** office: 세무서에 내는 판 — 공무원용 안내(먼저 읽기·신고별 요약·세무서가 볼 것·법령 검토·쉬운 말·확인할 것·붙임 체크·검토란)를 빼고, 청구하는 신고서 시트와 건별 근거만 */
export function caseBook(D: Data, o: CbIn, pick?: (g: Grade) => boolean, lead: Sheet[] = [], office = false, note = ''): Blob | null {
  const { cases, docs, facsOf } = buildCases(D, o, pick); if (!docs.length) return null; const facs = facsOf;
  const pages = new Map<string, number>(); for (const [k, v] of caseCorrDocs(D, o, pick)) pages.set(k, v[0].page ?? 0);
  const pageOf = (c: Case) => pages.get(`${c.k}|${c.pre ? 0 : 1}`) ?? 0;
  const open = cases.filter(c => c.left >= 0 && !c.nextFin);
  const total = open.reduce((n, c) => n + c.gain, 0);
  const sheets: Sheet[] = [];

  /* 1. 먼저 읽기 */
  if (!office) { const R: Cell[][] = []; const st: Record<number, number> = {}; const add = (r: Cell[], s = 0) => { if (s) st[R.length] = s; R.push(r); };
    add([`${o.org} 부가가치세 경정청구 작업서 — 신고서별`], 2); add([`${o.today} 작성 · 지자체 부가세 돌려받기(참고 계산 — 신고 책임은 신고인, 판정은 기관의 판단이 아닙니다)`]);
    add([`사업자등록번호 ${o.reg || '(확인)'} · 올린 신고서 ${docs.length}장 · 경정청구 기한 안 ${open.length}장 · 돌려받을 세액 합계(어림) ${fmt(total)}원${o.rows.length ? '' : ' — 매입 목록이 없어 조달청 나라장터 계약으로 짐작한 값'}`], 1); add([]);
    add(['이 파일로 하는 일 — 순서대로'], 3);
    [['1', '「신고별 요약」 시트에서 경정청구 기한이 가까운 신고서부터 봅니다(남은 날이 적은 순).'],
     ['2', '그 신고서 시트의 「확인할 것」을 하나씩 확인합니다 — 시설이 사용료를 과세로 신고해 온 곳인지, 같이 쓰는 건물의 면적, 세금계산서의 받는 쪽 사업자등록번호.'],
     ['2-1', '「법령 검토」 시트에 쟁점마다 결론·근거(법령·국세청 회신·판례·지침)·이 청구에 미치는 영향·할 일을 정리했습니다. 「확인할 것」이 왜 필요한지 여기서 봅니다.'],
     ['3', '함께 받은 「경정청구서(국세청 서식)」 PDF 의 그 쪽(요약의 「경정청구서 PDF 쪽」)을 엽니다. 숫자·이유·주소·최초신고일·세무서는 다 채워 두었습니다 — 기관장 성명·서명, 담당 전화, 환급 받을 세입 계좌, 청구 날짜만 적습니다.'],
     ['4', '내는 길은 둘 중 하나: ① 서면 — 그 쪽 경정청구서 + 같은 쪽 번호의 「경정청구 사유서」 + 붙임 서류를 관할 세무서에 냅니다. ② 홈택스 — 신고/납부 → 세금신고 → 부가가치세 → 경정청구에서 과세기간·예정/확정을 고르고, 시트 「1.」의 경정 후 값을 옮긴 뒤 경정청구서·사유서 PDF 를 첨부합니다.'],
     ['5', '세무서는 청구를 받은 날부터 2개월 안에 결과를 알려 줍니다(국세기본법 제45조의2 제3항). 돌려받은 돈은 세입으로 처리합니다 — 보관하다 감사에서 지적받은 사례가 있습니다.'],
     ['6', '과세인지 면세인지 판단이 어려운 시설은 시트의 「확인할 것」대로 관할 세무서에 묻거나 홈택스 서면질의로 먼저 확인합니다.']].forEach(r => add(r, 4));
    add([]); add(['처음 보는 말'], 3);
    [['매입세액', '우리 기관이 물건·공사·용역을 사면서 업체에 낸 부가세(세금계산서의 세액)'], ['공제', '낸 매입세액을 우리가 받은 부가세(매출세액)에서 빼 주는 것 — 빼면 그만큼 덜 내거나 돌려받습니다'],
     ['불공제', '매입세액을 빼 주지 않는 것 — 행정(고유사무)·면세 시설에 쓴 돈은 불공제입니다'], ['과세 시설', '사용료를 받아 부가세를 내는 시설(예: 사용료에 부가세를 포함하는 체육시설, 빌려준 공간) — 이 시설에 쓴 돈의 부가세는 공제됩니다'],
     ['안분', '과세 시설과 행정이 같이 쓴 지출의 부가세를 비율(면적·공급가액)로 나눠 과세 몫만 공제하는 것'], ['경정청구', '이미 낸 신고가 세금을 많이 내도록 잘못됐을 때 5년 안에 고쳐 달라고 하는 신청'],
     ['예정·확정', '부가세는 6개월(과세기간)마다 확정신고, 그 가운데 앞 3개월은 예정신고를 합니다'], ['(16)(17)(18)', '신고서 칸 번호 — (16) 받은 매입세액 합계, (17) 그 가운데 공제받지 못할 것, (18) 공제받은 것(= (16) − (17))']].forEach(r => add(r, 4));
    add([]); add(['계산 방식'], 3);
    add([`매입 건마다 어느 시설 것인지·과세인지를 정해(돌려받기 화면의 판정, 시설 설정의 과세 몫) 공제 대상 세액을 세고, 신고서의 신고기간 달로 나눠 그 신고서가 공제받은 (18)과 견줬습니다. 차이가 돌려받을 세액입니다.${o.rows.length ? '' : ' 매입 목록이 없을 때는 과세 시설에 붙은 나라장터 계약 금액의 부가세(10/110)를 그 과세기간 확정 신고서에 두었습니다 — 짐작한 값이라 세금계산서로 확인해야 확정됩니다.'}`], 4);
    sheets.push({ name: '먼저 읽기', rows: R, style: st, freeze: false, widths: [16, 110] }); }

  /* 2. 신고별 요약 — 기한 가까운 순 */
  if (!office) { const head = ['순서', '신고서', '시트', '경정청구서 PDF 쪽', '신고기간', '법정신고기한', '경정청구 기한', '남은 날', '당초 공제받은 매입세액 (18)', '경정 후 (18)', '돌려받을 세액', '근거', '주된 이유', '확인할 것'];
    const L = [...cases].sort((a, b) => (a.left < 0 ? 1e9 : a.left) - (b.left < 0 ? 1e9 : b.left) || b.gain - a.gain);
    const rows: Cell[][] = [head, ...L.map((c, i) => { const ded = tax(c.d, 18) ?? 0; const why = topReason(c); return [i + 1, c.name, c.sheet, pageOf(c) || '—', `${c.d.year}-${String(c.d.from).padStart(2, '0')} ~ ${String(c.d.to).padStart(2, '0')}월`, c.due, c.cdue, c.left < 0 ? '기한 지남' : c.nextFin ? `확정신고(${legalDue(c.d.year, c.d.half, false)})에 넣기` : c.left, ded, c.gain ? ded + c.gain : ded, c.left < 0 || c.nextFin ? 0 : c.gain, c.mode === 'list' ? '매입 목록(세금계산서)' : c.mode === 'cand' ? '조달청 계약(추정)' : c.mode === 'corr' ? '신고서 숫자 재계산' : '—', why, checks(c).length]; }),
      [], ['', '합계(기한 안)', '', '', '', '', '', '', '', '', total]];
    sheets.push({ name: '신고별 요약', rows, widths: [6, 18, 14, 10, 16, 12, 12, 9, 16, 16, 16, 18, 70, 10] }); }
  /* 2-1. 법령 검토 — 쟁점별 결론·근거·이 기관에 미치는 영향·할 일(2026-11-24 운영자 '부가가치세 전문가 입장에서 관련 법령·지침·국세청 질의 답변 등 가능한 모든 수단으로 검토') */
  /* 2-2. 세무서 검토 — 이 경정청구를 받은 관할 세무서 담당자가 확인할 것과 준비할 것(2026-11-24 운영자 '수성구 부가세 담당 세무서 공무원 입장에서도 검토') */
  if (!office) sheets.push({ name: '세무서가 볼 것', rows: [['순서', '세무서가 확인하는 것', '왜', '미리 준비할 것', '근거'], ...TAXOFFICE.map((r, i) => [i + 1, ...r])], widths: [6, 44, 52, 52, 40], style: Object.fromEntries(TAXOFFICE.map((_, i) => [i + 1, 4])) });
  if (!office) sheets.push({ name: '법령 검토', rows: [['쟁점', '결론', '근거(법령·유권해석·판례·지침)', '이 경정청구에 미치는 영향', '할 일'], ...LEGAL], widths: [26, 60, 50, 50, 46], style: Object.fromEntries(LEGAL.map((_, i) => [i + 1, 4])) });

  /* 3. 신고서마다 한 장 */
  function topReason(c: Case): string {
    if (!c.gain) return c.mode === 'none' ? (!o.rows.length && c.pre ? '계약 어림은 같은 과세기간 확정 신고서 시트에 합쳐 둠(예정분 포함)' : '이 신고기간 매입 자료가 없어 계산하지 않음') : '고칠 것을 찾지 못함';
    if (c.mode === 'corr') return '신고서 숫자로 다시 계산 — 공통매입세액 안분·정산 계산이 맞지 않음';
    const byF = facs(c).slice(0, 3).map(f => f.fac).join('·');
    const nd2 = c.d.nd?.reasons[2]?.tax ?? 0; const c16 = tax(c.d, 16) ?? 0;
    return `${nd2 > 0 && nd2 >= c16 * 0.9 ? "매입세액 전부를 '② 사업과 직접 관련 없는 지출'로 불공제 — " : ''}과세 시설(${byF || '시설 확인'}) 매입세액을 공제하지 않음`;
  }

  function checks(c: Case): string[] {
    const out: string[] = []; if (!c.gain) return out; const F = facs(c);
    if (c.mode === 'corr') return ['원래 신고서의 「공제받지 못할 매입세액 명세서」가 공급가액 비율로 나눴는지 확인 — 매입가액·면적 기준이면 이 금액은 맞지 않습니다(시행령 제81조 제4항, 대법원 2017두55329)', '안분에 쓴 총공급가액·면세공급가액을 그 기간 장부와 대조'];
    out.push(`이 시설들이 그 기간에 사용료를 과세 매출로 신고해 왔는지 — 신고서 과세표준 명세(업종)와 조례 사용료 표('부가가치세 포함' 문구)로 확인: ${F.slice(0, 6).map(f => f.fac).join(', ')}`);
    for (const f of F) if (typeof f.share === 'number' && f.share < 1) out.push(`「${f.fac}」은 과세 몫 ${Math.round(f.share * 100)}%로 계산했습니다(추정 기본값) — 건축물대장·사용허가서의 면적으로 과세로 쓰는 비율을 확인(시행령 제81조 제4항)`);
    if (c.mode === 'list' && c.listTax > (tax(c.d, 16) ?? 0) + 1000) out.push(`매입 목록 세액 ${fmt(c.listTax)}원이 신고서 받은 매입세액 (16) ${fmt(tax(c.d, 16) ?? 0)}원보다 ${fmt(c.listTax - (tax(c.d, 16) ?? 0))}원 많습니다 — 신고에 아예 안 들어간 세금계산서가 있다는 뜻입니다. 그 세금계산서의 받는 쪽 번호가 우리 사업자등록번호인지 홈택스 매입 목록으로 확인하고, 맞으면 (10)(16)도 늘립니다(고유번호로 받았으면 공제 어려움, 수정세금계산서 기한 시행령 제70조)`);
    if (c.mode === 'cand') out.push('매입 목록 대신 나라장터 계약 금액으로 짐작한 값입니다 — 홈택스 → 조회/발급 → 전자세금계산서 → 목록조회(매입)에서 이 기간 세금계산서를 받아 돌려받기 화면에 올리면 확정 금액으로 바뀝니다');
    if (c.pre) out.push('예정신고분 — 경정청구 기한은 확정신고기한부터 5년입니다(국세청 서면법규과-385). 예정신고서를 따로 고칠지, 같은 과세기간 확정신고 경정청구에 합칠지는 관할 세무서와 맞춥니다');
    /* 법령 검토(2026-11-24) — 시설 종류별로 판정이 갈리는 사실 */
    const SPORT = F.filter(f => f.type === 'sports' || f.type === 'golf');
    if (SPORT.length) out.push(`관람석 확인 — ${SPORT.slice(0, 6).map(f => short(f.fac)).join(', ')}: 일반 관중이 경기를 볼 수 있는 관람석을 갖춘 경기장(운동장·공인 수영장·체육관)이면 경기장 운영업이라 면세입니다(서면3팀-1330 구청 구민운동장 관람석 400석, 법규과-209 관람석 688석 공인 수영장). 그러면 그 시설 몫은 공제되지 않고(시설별 내역 금액만큼 줄어듦), 대신 그동안 과세로 낸 사용료의 매출세액을 돌려받는 경정청구가 됩니다. 이용자 대기·후보선수용 좌석만 있으면 관람석이 아닙니다(통계청 회신). 세입에 입장료·관람료가 없고 사용료에 부가세를 붙여 과세로 신고해 온 운동장은 운동시설 대여로 보아 이번 청구에 넣었습니다 — 세무서가 경기장(면세)으로 보더라도 매출세액을 돌려받는 쪽이라 더 낼 일은 없습니다.`);
    if (F.some(f => /수영|체육센터|국민체육|반다비/.test(f.fac))) out.push('강습료 비중 확인 — 지자체가 직영하는 교육·문화 강좌는 면세 여지가 있습니다(재경부 부가가치세제과-186 질의 7·8·14). 수영 등 강습료를 면세로 보면 그 체육센터는 과세(자유 이용)·면세(강습) 공통이라 공급가액 비율로 나눠야 합니다(시행령 제81조) — 관할 세무서에 강습료 과세 여부를 먼저 확인');
    { const codes = c.d.codes ?? []; if (codes.length) { const has = (re: RegExp) => codes.some(x => re.test(x.code) && !x.zero); const need: [string, RegExp, string][] = [['lodging', /^55/, '숙박업(55…)'], ['lease', /^70/, '부동산임대업(70…)'], ['sports', /^(809|9113)/, '스포츠시설 운영업(809…)']];
      /* (34) 수입금액 제외 줄은 서식상 업종코드를 적지 않는다 — 과세표준 (9)에는 들어가 매출세액은 낸 몫 */
      const tb = c.d.cells[9]?.amt ?? 0; const un = tb - (c.d.base ?? []).reduce((n, b) => n + (b.code ? b.amt : 0), 0);
      if (un > 1000) out.push(`업종코드 없는 과세 매출 ${fmt(un)}원 — 과세표준 명세의 (34) 수입금액 제외 줄처럼 업종코드를 적지 않는 줄에 들어간 매출입니다(서식상 이 줄에는 코드가 없음). 과세표준에는 들어가 매출세액은 낸 것이니, 아래 시설 사용료가 여기에 들어 있는지 그 기간 세입 실적으로 맞춰 봅니다.`);
      for (const [t, re, nm] of need) { const fs = F.filter(f => f.type === t); if (!fs.length || has(re)) continue;
        const alt = t === 'lease' ? leaseAlt([c.d]) : null;
        if (alt) { const rev = fs.reduce((n, f) => n + (o.revByFac?.[f.fac] ?? 0), 0); const mo = Math.max(1, (c.d.to ?? 12) - (c.d.from ?? 1) + 1); const per = Math.round(rev * mo / 12 / 1.1);
          out.push(`임대 매출 확인 — 이 신고서의 부동산임대업(70…) 줄은 ${codes.some(x => /^70/.test(x.code)) ? '0원이지만' : '없지만'} 업태·종목에 '임대'가 든 다른 업종 줄(업종코드 ${alt.code})에 ${fmt(alt.amt)}원이 있습니다. 공유재산 대부료는 세금계산서를 발급하는 매출이라 (1) 세금계산서 발급분과 함께 그 줄로 신고한 것으로 보아 ${fs.map(f => short(f.fac)).join(', ')} 몫을 청구에 넣었습니다(과세표준·매출세액은 이미 들어 있고 업종코드만 다름)${rev ? ` — 세입예산의 사용료·대부료 연 ${fmt(rev)}원이면 이 신고 기간(${mo}개월) 공급가액은 약 ${fmt(per)}원으로 그 줄 금액 안에 들어갑니다` : ''}. 홈택스 매출 전자세금계산서 목록에서 대부 받은 업체(은행·카페 등) 앞으로 발급한 세금계산서가 있는지 한 번 확인합니다.`); continue; }
        if (un > 1000) { out.push(`매출 대조 — 이 신고서 명세에 ${nm} 줄은 없고 업종코드 없는 과세 매출 ${fmt(un)}원이 있습니다. ${fs.map(f => short(f.fac)).join(', ')}의 사용료가 그 줄에 들어 있으면 과세 매출로 신고한 것이라 이 시설 매입세액 청구로 더 낼 일은 없습니다 — 세입 실적과 금액을 맞춰 확인.`); continue; }
        const rev = fs.reduce((n, f) => n + (o.revByFac?.[f.fac] ?? 0), 0); const vat = Math.round(rev / 11); const claim = fs.reduce((n, f) => n + f.claim, 0);
        out.push(`매출 대조(세무서가 먼저 볼 것) — 이 신고서 과세표준 명세에 ${nm} 매출이 없습니다(읽은 업종코드: ${codes.map(x => x.code + (x.zero ? '(0원)' : '')).join(', ')}). ${fs.map(f => short(f.fac)).join(', ')}의 사용료·임대료를 과세 매출로 신고하지 않았다면 매입세액(이 신고서 ${fmt(claim)}원)만 공제받을 수 없고, 세무서가 경정청구를 검토하며 매출 누락을 함께 경정할 수 있습니다${rev ? ` — 세입예산 연 ${fmt(rev)}원이면 부가세 연 약 ${fmt(vat)}원(부가세 포함 금액 ÷ 11), 5년이면 약 ${fmt(vat * 5)}원과 과소신고·납부지연 가산세${t === 'lease' ? '·세금계산서 미발급 가산세(사업자에게 빌려준 경우 공급가액의 2%)' : ''}로 이 시설 공제보다 클 수 있습니다` : ''}. 먼저 다른 업종에 묶어 신고했는지 확인하고, 빠졌으면 이 시설 몫은 청구하지 않습니다(이 앱은 돌려받는 청구만 만듭니다)`); } } }
    if (c.mode === 'list' && c.rows.some(r => r.claim && /건립|조성|증축|신축|리모델링|건설/.test(r.desc))) out.push('재원 확인 — 국비·기금으로 지은 시설이어도 매입세액은 공제됩니다. 돌려받은 부가세는 국고보조금 통합관리지침 제26조 제2항(지방보조금은 지방보조금 관리기준 제19조 제2항)에 따라 세외수입으로 계상하는 것이 원칙(같은 사업 재투자 가능) — 국민체육진흥기금 보조면 기금 사용·정산 지침도 확인');
    if (F.some(f => /공통|본청|행정/.test(f.fac + f.label))) out.push('본청·행정과 같이 쓴 지출은 공급가액이 없는 고유사무가 섞여 매입가액·면적 같은 다른 기준이 필요할 수 있습니다(대법원 2017두55329) — 기준을 정해 세무서 질의로 굳힙니다');
    out.push('수탁기관(재단·민간위탁)이 운영하는 시설 지출은 그 기관 몫이라 넣지 않았습니다 — 위·수탁 협약서의 사용료(무상·유상) 조항 확인');
    return out; }
  function reasonText(c: Case): string {
    if (c.mode === 'corr' && c.corr) return corrReason(c.corr) + ` 이에 따라 납부세액 ${fmt(c.gain)}원을 돌려주시기 바랍니다(국세기본법 제45조의2 제1항).`;
    const F = facs(c); const nd2 = c.d.nd?.reasons[2]?.tax ?? 0; const c16 = tax(c.d, 16) ?? 0; const ded = tax(c.d, 18) ?? 0;
    const a = `청구인 ${o.org}(${o.reg || '사업자등록번호'})은 ${pName(c.k)} ${c.d.kind}신고(신고기간 ${c.d.year}. ${c.d.from}. ~ ${c.d.to}.)에서 받은 세금계산서 매입세액 ${fmt(c16)}원 가운데 ${fmt(ded)}원만 공제받았습니다${nd2 > 0 ? `(${fmt(nd2)}원은 '사업과 직접 관련 없는 지출'로 불공제)` : ''}.`;
    const b = F.length ? ` 그러나 이 가운데 ${F.slice(0, 5).map(f => `${f.fac} ${fmt(f.claim)}원`).join(', ')}${F.length > 5 ? ` 외 ${F.length - 5}곳` : ''}은 청구인이 사용료를 받아 과세 매출로 신고하는 시설(지방자치단체가 공급하더라도 과세되는 사업, 부가가치세법 제26조 제1항 제19호·같은 법 시행령 제46조)의 공사·관리·운영에 쓴 것으로 공제 대상 매입세액(같은 법 제38조)입니다.` : '';
    const sh = F.filter(f => typeof f.share === 'number' && f.share < 1); const cc = sh.length ? ` 과세·면세 공간이 섞인 건물(${sh.map(f => f.fac).join(', ')})의 매입세액은 과세로 쓰는 면적 비율만큼만 넣었습니다(같은 법 제40조, 시행령 제81조 제4항).` : '';
    const sp = splitGain(c.d, c.gain, c.gainAmt);
    const d = sp.add > 0
      ? ` 이 가운데 ${fmt(sp.add)}원은 받은 세금계산서를 당초 신고에 넣지 않은 것이라 매입처별 세금계산서합계표를 이 청구서와 함께 제출합니다(같은 법 시행령 제74조 제2호). 따라서 매입세액 (16)을 ${fmt(c16)}원에서 ${fmt(c16 + sp.add)}원으로${sp.cut ? `, 공제받지 못할 매입세액 (17)을 ${fmt(tax(c.d, 17) ?? 0)}원에서 ${fmt(Math.max(0, (tax(c.d, 17) ?? 0) - sp.cut))}원으로` : ''}, 공제받는 매입세액 (18)을 ${fmt(ded)}원에서 ${fmt(ded + c.gain)}원으로 고쳐 납부세액 ${fmt(c.gain)}원을 돌려주시기 바랍니다(국세기본법 제45조의2 제1항).`
      : ` 따라서 공제받지 못할 매입세액 (17)을 ${fmt(tax(c.d, 17) ?? 0)}원에서 ${fmt(Math.max(0, (tax(c.d, 17) ?? 0) - c.gain))}원으로, 공제받는 매입세액 (18)을 ${fmt(ded)}원에서 ${fmt(ded + c.gain)}원으로 고쳐 납부세액 ${fmt(c.gain)}원을 돌려주시기 바랍니다(국세기본법 제45조의2 제1항).`;
    return a + b + cc + d; }
  function plain(c: Case): string {
    if (c.mode === 'corr') return `신고서 숫자를 다시 계산해 보니 같이 쓴 비용의 부가세를 나누는 계산이 맞지 않아 ${fmt(c.gain)}원을 더 냈습니다. 그 몫을 돌려 달라고 신청하는 것입니다.`;
    const F = facs(c); if (!c.gain) return '이 신고서에서 고칠 것을 찾지 못했습니다.';
    return `돈을 받는 시설(${F.slice(0, 4).map(f => f.fac).join(', ')})에 쓴 공사·관리비의 부가세는 원래 돌려받을 수 있는 돈인데, 신고 때 '행정에 쓴 돈'과 같이 묶어 돌려받지 않은 것으로 처리했습니다. 그 몫 ${fmt(c.gain)}원을 돌려 달라고 신청하는 것입니다.${c.mode === 'cand' ? ' (계약 금액으로 짐작한 값 — 세금계산서로 확인 필요)' : ''}`; }

  for (const c of cases) { if (office && (c.left < 0 || c.nextFin || c.gain <= 0)) continue;
    const d = c.d; const R: Cell[][] = []; const st: Record<number, number> = {}; const add = (r: Cell[], s = 0) => { if (s) st[R.length] = s; R.push(r); };
    const c16 = tax(d, 16), c17 = tax(d, 17), c18 = tax(d, 18), c9 = tax(d, 9); const ded = c18 ?? 0; const g = c.left < 0 ? 0 : c.gain;
    add([`${c.name} 경정청구 — ${o.org}${note}`], 2);
    add(['신고기간', `${d.year}. ${d.from}. ~ ${d.to}. (${d.kind})`, '법정신고기한', c.due, '경정청구 기한', `${c.cdue}${c.left < 0 ? ' — 지남(청구 불가)' : ` (D-${c.left})`}`]);
    add(['사업자등록번호', d.reg || o.reg || '', office ? '' : '당초 신고 파일', office ? '' : d.file, '근거 자료', c.mode === 'list' ? `매입 목록 ${c.rows.length}건` : c.mode === 'cand' ? '조달청 나라장터 계약(추정)' : c.mode === 'corr' ? '신고서 숫자 재계산' : '없음']);
    add(office ? ['돌려받을 세액', g] : ['돌려받을 세액', g, '쉬운 말', plain(c)], 5);
    if (pageOf(c) && !office) add(['경정청구서', `함께 받은 「경정청구서(국세청 서식)」 PDF ${pageOf(c)}쪽 — 숫자를 다 채워 두었습니다. 기관장 성명·서명, 전화, 환급 계좌, 날짜만 적으면 됩니다. 같은 쪽 번호의 「경정청구 사유서」 PDF 를 붙임으로 냅니다.`], 5);
    if (c.nextFin) add(['', `이 과세기간 확정신고(기한 ${legalDue(d.year, d.half, false)})가 아직이라 경정청구를 하지 않고, 확정신고서의 (13) 예정신고 누락분 칸(매입)에 이 ${fmt(g)}원을 넣어 공제받습니다. 아래 값은 그 계산 근거입니다(요약 합계에서는 뺐습니다).`], 5);
    add([]);
    add(['1. 홈택스 경정청구 화면에 넣을 값 (일반과세자 신고서 칸)'], 3); add(['칸', '이름', '당초 금액', '당초 세액', '경정 후 금액', '경정 후 세액', '바뀌는 세액', '설명'], 1);
    const sales: [number, string][] = [[1, '세금계산서 발급분(과세 매출)'], [3, '신용카드·현금영수증 발행분'], [4, '기타(정규영수증 외 매출분)'], [9, '과세표준 및 매출세액 합계']];
    for (const [n, nm] of sales) if (d.cells[n]) add([`(${n})`, nm, amt(d, n), tax(d, n), amt(d, n), tax(d, n), 0, '매출은 바꾸지 않음']);
    const ga = c.left < 0 ? 0 : c.gainAmt; const sp = c.mode === 'corr' ? { cut: g, add: 0, addAmt: 0, cutAmt: ga } : splitGain(d, g, ga);
    const plus = (a: number | null, b: number | null) => a != null && b != null ? a + b : null;
    add(['(10)', '세금계산서 수취분 일반매입', amt(d, 10), tax(d, 10), sp.add ? plus(amt(d, 10), sp.addAmt) : amt(d, 10), sp.add ? (tax(d, 10) ?? 0) + sp.add : tax(d, 10), sp.add, sp.add ? `당초 신고에 넣지 않은 세금계산서 ${fmt(sp.add)}원을 더함 — 매입처별 세금계산서합계표를 경정청구서와 함께 냄(시행령 제74조 제2호, 가산세 없음 — 제108조 제6항). 건별은 붙임 「건별 근거」` : '이미 신고에 들어 있는 세금계산서 — 그대로'], sp.add ? 1 : 0);
    add(['(16)', '매입세액 합계', amt(d, 16), c16, sp.add ? plus(amt(d, 16), sp.addAmt) : amt(d, 16), sp.add ? (c16 ?? 0) + sp.add : c16, sp.add, sp.add ? '(10)이 늘어난 만큼' : '그대로']);
    const a17 = c17 != null && c17 - sp.cut <= 0 ? 0 : amt(d, 17) != null && sp.cutAmt != null ? Math.max(0, (amt(d, 17) ?? 0) - sp.cutAmt) : null;
    add(['(17)', '공제받지 못할 매입세액', amt(d, 17), c17, a17, c17 != null ? Math.max(0, c17 - sp.cut) : null, -sp.cut, c.mode === 'corr' ? '공통매입세액 면세분을 다시 계산해 줄임(아래 2.)' : ga != null ? '과세 시설 몫(공급가액·세액)을 빼서 줄임' : '과세 시설 몫을 빼서 줄임 — 금액 칸은 세금계산서 공급가액 합으로 맞추기'], 1);
    add(['(18)', '차감계(공제받는 매입세액)', amt(d, 18), c18, amt(d, 18) != null && ga != null ? (amt(d, 18) ?? 0) + ga : null, ded + g, g, sp.add ? `(16) − (17) — 당초 (17)에서 뺀 ${fmt(sp.cut)}원 + 신고에 없던 세금계산서 ${fmt(sp.add)}원` : '(16) − (17)'], 1);
    if (c9 != null) add(['', '납부(환급)세액 = 매출세액 − (18)', null, c9 - ded, null, c9 - ded - g, -g, '이만큼 덜 내야 했음 → 돌려받음']);
    if (d.due != null) add(['(30)', '차가감 납부할 세액(환급받을 세액)', null, d.due, null, d.due - g, -g, '경정 후 값이 음수(−)면 그만큼 돌려받는다는 뜻']);
    if (c.mode === 'corr' && c.corr?.parts.length) { add([]); add(['2. 공제받지 못할 매입세액 명세서 — 공통매입세액 안분·정산 계산(당초 → 경정 후)'], 3); add(['항목', '', '', '', '당초', '경정 후', '차이', '설명'], 1);
      for (const p of c.corr.parts) for (const r of p.rows) add([`${p.sec}: ${r.label}`, '', null, null, r.before, r.after, r.before != null && r.after != null ? r.after - r.before : null, '부가가치세법 시행령 제81조 제1항 식(공통매입세액 × 면세공급가액 ÷ 총공급가액)으로 다시 계산']);
      add(['※ 당초 명세서가 공급가액 비율로 나눈 경우의 재계산입니다. 총공급가액에는 과세 공급가액((1)~(4))과 면세 공급가액을 모두 넣습니다.'], 4); }
    else { add([]); add(['2. 공제받지 못할 매입세액 명세서 — 고칠 값'], 3); add(['사유', '', '당초 매수', '당초 공급가액', '당초 세액', '경정 후 세액', '바뀌는 세액', '설명'], 1);
    const RN = ['① 필요적 기재사항 누락 등', '② 사업과 직접 관련 없는 지출', '③ 비영업용 소형승용차', '④ 기업업무추진비 등', '⑤ 면세사업등 관련', '⑥ 토지의 자본적 지출', '⑦ 사업자등록 전 매입세액', '⑧ 금·구리 스크랩'];
    const rs = d.nd?.reasons ?? {}; const target = (rs[2]?.tax ?? 0) >= (rs[5]?.tax ?? 0) ? 2 : 5; let left = g;
    const cutN = c.rows.filter(r => r.claim).length; RN.forEach((nm, i) => { const n = i + 1, x = rs[n]; if (!x?.tax && n !== target) return; const cut = n === target ? Math.min(left, x?.tax ?? 0) : 0; if (n === target) left -= cut; add([nm, '', x?.n ?? null, x?.amt ?? null, x?.tax ?? 0, (x?.tax ?? 0) - cut, -cut, n === target && cut ? `과세 시설 몫을 이 사유에서 뺌 — 경정 후 ${x?.n != null && cutN && !sp.add ? `${x.n - cutN}매 · ` : ''}${x?.amt != null && sp.cutAmt != null ? `공급가액 ${fmt((x?.tax ?? 0) - cut <= 0 ? 0 : Math.max(0, x.amt - sp.cutAmt))}원` : '공급가액은 세금계산서 합으로'}${sp.add ? ` · 나머지 ${fmt(sp.add)}원은 당초 신고에 없던 세금계산서라 이 명세서가 아니라 (10)에 더함` : ''}(뺀 세금계산서는 붙임 「건별 근거」)` : '']); });
    if (!d.nd) add(['(이 신고서에 명세서가 없음)', '', null, null, null, null, null, '당초 신고 때 낸 명세서를 홈택스 신고내역에서 확인']); }
    add([]); add(['3. 이유'], 3);
    add(['청구 사유(그대로 붙여넣기)', reasonText(c)], 4);
    if (!office) add(['쉬운 말', plain(c)], 4);
    add([]); add(['4. 근거 — 법령'], 3); add(['조문', '무엇을 정했나', '원문 링크'], 1);
    const bs: Basis[] = c.mode === 'corr' ? [{ law: 'basic', art: '제45조의2' }, { law: 'act', art: '제40조' }, { law: 'decree', art: '제81조' }, { law: 'decree', art: '제82조' }] : [{ law: 'basic', art: '제45조의2' }, { law: 'act', art: '제38조' }, { law: 'act', art: '제39조' }, { law: 'act', art: '제26조' }, { law: 'decree', art: '제46조' }];
    for (const r of c.rows) if (r.claim) for (const b of r.basis) if (!(b.law === 'rule' && b.art === '제35조') && !bs.some(x => x.law === b.law && x.art === b.art)) bs.push(b);   /* 시행규칙 제35조(과세 공급 범위 세부 — 국군 관계자 등)는 이 청구와 무관해 싣지 않음(세무법인 역할 시험 2026-11-24) */
    if (facs(c).some(f => typeof f.share === 'number' && f.share < 1)) for (const b of [{ law: 'act', art: '제40조' }, { law: 'decree', art: '제81조' }]) if (!bs.some(x => x.law === b.law && x.art === b.art)) bs.push(b);
    for (const b of bs) add(lawLine(D, b), 4);
    const types = [...new Set(facs(c).map(f => f.type).filter(Boolean) as string[])]; const rids = [...new Set(types.flatMap(t => D.facilities.find(x => x.key === t)?.rulings ?? []))];
    const RL = (D.rulings ?? []).filter(x => rids.includes(x.id));
    if (RL.length) { add([]); add(['5. 근거 — 유권해석·판례(같은 종류 시설)'], 3); add(['번호', '제목·요지', '원문'], 1); for (const x of RL) add([x.no, `${x.title} — ${x.gist}${x.verify ? ' (원문 확인 필요)' : ''}`, x.url ?? ''], 4); }
    for (const t of types) { const fr = D.facilities.find(x => x.key === t); if (fr?.cond) { if (!RL.length) { add([]); add(['5. 근거 — 시설 종류 기준'], 3); } add([fr.name, fr.cond], 4); } }
    add([]); add(['시설별 내역'], 3); add(['시설', '판정', '건수', '이 기간 매입세액', '공제 대상 세액', '과세 몫'], 1);
    for (const f of facs(c)) add([f.fac, f.label, f.n || null, f.tax, f.claim, typeof f.share === 'number' && f.share < 1 ? `${Math.round(f.share * 100)}%(추정)` : '100%']);
    if (!office) { add([]); add(['확인할 것 — 확인하면 ☑'], 3); for (const x of checks(c)) add(['☐', x], 4); }
    if (!office) { add([]); add(['6. 붙임 서류'], 3);
    ['당초 신고서 사본(홈택스 → 신고/납부 → 세금신고 → 신고내역 조회 출력)', '고친 공제받지 못할 매입세액 명세서(위 2.)', '시설이 과세 사업이라는 근거 — 사용료 조례 별표(부가가치세 포함 문구)·과세표준 명세의 업종', '그 시설에 쓴 지출이라는 근거 — 계약서·검수조서·세금계산서 목록(이 파일 「건별 근거」)', ...(facs(c).some(f => typeof f.share === 'number' && f.share < 1) ? ['면적 근거 — 건축물대장·사용허가서(과세로 쓰는 면적)'] : [])].forEach(x => add(['☐', x], 4)); }
    if (!office) { add([]); add(['7. 검토'], 3); add(['작성', '', '검토', '', '결재', '']); add(['작성일', '', '세무서 접수일', '', '결과 통지일', '']); }
    sheets.push({ name: c.sheet, rows: R, style: st, freeze: false, widths: [22, 40, 16, 16, 16, 16, 14, 60] });
  }

  /* 4. 건별 근거 */
  if (o.rows.length) {
    const rows: Cell[][] = [['신고서(시트)', '날짜', '공급자', '공급자 등록번호', '품목·사업명', '공급가액', '세액', '시설', '판정', '공제 대상 세액', '근거 조문', '이유']];
    for (const c of cases) for (const r of c.rows) if (r.claim) rows.push([c.sheet, r.d, r.sup, r.sreg, r.desc, r.amt, r.tax, r.fac, r.label, r.claim, r.basis.filter(b => !(b.law === 'rule' && b.art === '제35조')).map(b => `${LAW[b.law] ?? b.law} ${b.art}`).join(' · '), r.why.join(' ')]);
    sheets.push({ name: '건별 근거', rows, widths: [14, 11, 24, 14, 40, 14, 12, 28, 30, 14, 26, 60] });
  }
  return xlsxBlob([...lead, ...sheets]);
}
