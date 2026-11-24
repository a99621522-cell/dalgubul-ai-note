/** 신고별 경정청구 작업서(엑셀) — 부가세 신고를 모르는 공무원이 그대로 따라 하게(운영자 2026-11-24 '공공세무 전문가·사이트 구축 전문가라면 … 신고한 사례별로 경정신고서 만들고 근거와 이유를 제시해줘, 엑셀파일이 좋을 것 같아').
 *  올린 신고서(예정·확정) 한 장마다 시트 한 장: 홈택스 경정청구 화면에 옮길 칸(당초 → 경정 후) · 불공제 명세서 고칠 값 · 쉬운 말 이유 · 근거 조문과 유권해석 · 시설별 내역 · 확인할 것 · 붙임 서류 · 검토란.
 *  숫자는 돌려받기 화면의 건별 판정(judge — 새 규칙 없음)을 그 신고서의 신고기간 달에 맞춰 나눈 것. 매입 목록이 없으면 나라장터 계약 어림(추정)을 그 과세기간 확정 신고서에 둔다.
 *  담당자 이름·전화는 넣지 않는다(검토란은 빈칸). 판정은 참고이며 기관의 판단이 아니다. */
import { fmt, LAW, lawUrl, type Data, type Basis } from './vat_rules';
import { latestDocs, type FiledDoc } from './vat_unlock';
import { xlsxBlob, type Sheet } from './xlsx_write';
import { corrReason, type CorrDoc } from './vat_diag';

export type CbRow = { d: string; sup: string; sreg: string; desc: string; tax: number; amt: number; claim: number; fac: string; facType?: string; share?: number; label: string; basis: Basis[]; why: string[] };
export type CbCand = { k: string; amt: number; byFac: { fac: string; est: number; type?: string; share?: number }[]; sups: number };
type Cell = (string | number | null | undefined);

const LAWFULL: Record<string, string> = { act: '부가가치세법', decree: '부가가치세법 시행령', rule: '부가가치세법 시행규칙', basic: '국세기본법', special: '조세특례제한법', special_decree: '조세특례제한법 시행령' };
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
/** 경정청구 기한 — 법정신고기한 + 5년(국세기본법 제45조의2 제1항). 확정신고는 확정신고기한, 예정신고서는 예정신고기한으로 보수적으로 둔다(관할 세무서 확인) */
const claimDue = (y: number, h: number) => h === 1 ? `${y + 5}-07-25` : `${y + 6}-01-25`;
const days = (to: string, today: string) => Math.round((new Date(to).getTime() - new Date(today).getTime()) / 864e5);
const tax = (d: FiledDoc, n: number) => d.cells[n]?.tax ?? null;
const amt = (d: FiledDoc, n: number) => d.cells[n]?.amt ?? null;

export type CbIn = { org: string; reg: string; today: string; docs: FiledDoc[]; rows: CbRow[]; cand?: CbCand[]; corr?: Map<string, CorrDoc[]> };   /* corr: 신고서 숫자만으로 고친 값(진단의 안분 재계산 등) */
const short = (n: string) => n.replace(/\(.*?\)/g, '').replace(/\s+/g, ' ').trim();
/** 신고서별 고친 신고서 → 국세청 경정청구서 서식(vat_claimform claimFormPdf)·사유서에 그대로 넣는 값. 열쇠 'YYYY-H|0(예정)·1(확정)' 순서가 PDF 쪽 순서 */
export type Case = { d: FiledDoc; k: string; pre: boolean; nextFin: boolean; name: string; rows: CbRow[]; listTax: number; should: number; gainAmt: number | null; gain: number; est?: CbCand; due: string; cdue: string; left: number; mode: 'list' | 'cand' | 'corr' | 'none'; sheet: string; corr?: CorrDoc };
type FacSum = { fac: string; type?: string; share?: number; n: number; tax: number; claim: number; label: string };
function buildCases(D: Data, o: CbIn): { cases: Case[]; docs: FiledDoc[]; facsOf: (c: Case) => FacSum[] } {
  void D; const docs = latestDocs(o.docs).sort((a, b) => a.year - b.year || a.half - b.half || a.from - b.from);
  const cand = new Map((o.cand ?? []).map(c => [c.k, c]));
  /* 신고서 → 그 신고기간 달의 매입 건 */
  const cases: Case[] = docs.map(d => {
    const k = `${d.year}-${d.half}`; const pre = d.kind === '예정'; const mon = (r: CbRow) => { const y = Number(r.d.slice(0, 4)), m = Number(r.d.slice(5, 7)); return y === d.year && m >= d.from && m <= d.to; };
    const rows = o.rows.filter(mon); const listTax = rows.reduce((n, r) => n + r.tax, 0); const should = rows.reduce((n, r) => n + r.claim, 0);
    const ded = tax(d, 18) ?? 0; const est = !o.rows.length && !pre ? cand.get(k) : undefined;
    const corr = o.corr?.get(k)?.find(x => x.kind === d.kind && x.delta > 0);
    const gain = rows.length ? Math.max(0, should - ded) : est ? est.amt : corr ? corr.delta : 0; const sAmt = rows.reduce((n, r) => n + (r.tax ? Math.round(r.amt * r.claim / r.tax) : 0), 0); const gainAmt = rows.length && should > 0 ? Math.round(sAmt * gain / should) : null;
    const cdue = pre ? `${d.year + 5}-${d.half === 1 ? '04' : '10'}-25` : claimDue(d.year, d.half);   /* 예정신고서 자체를 고치면 예정신고기한 + 5년으로 보수적으로(확정신고 경정청구에 합치면 확정 기준) */
    const nextFin = pre && !docs.some(x => x.year === d.year && x.half === d.half && x.kind !== '예정') && legalDue(d.year, d.half, false) >= o.today;   /* 확정신고가 아직 — 경정청구 대신 확정신고 (13) 예정신고 누락분으로 */
    return { d, k, pre, name: `${pName(k)} ${d.kind}`, rows, nextFin, listTax, should, gainAmt, gain, est, due: legalDue(d.year, d.half, pre), cdue, left: days(cdue, o.today), mode: rows.length ? 'list' : est ? 'cand' : corr ? 'corr' : 'none', corr: rows.length || est ? undefined : corr, sheet: `${String(d.year).slice(2)}-${d.half}기 ${d.kind}` };
  });
  function facsOf(c: Case): FacSum[] { const m = new Map<string, { fac: string; type?: string; share?: number; n: number; tax: number; claim: number; label: string }>();
    if (c.mode === 'list') for (const r of c.rows) { if (!r.claim) continue; const x = m.get(r.fac) ?? { fac: r.fac, type: r.facType, share: r.share, n: 0, tax: 0, claim: 0, label: r.label }; x.n++; x.tax += r.tax; x.claim += r.claim; m.set(r.fac, x); }
    else if (c.est) { const tot = c.est.byFac.reduce((n, x) => n + x.est, 0) || 1; for (const x of c.est.byFac) m.set(x.fac, { fac: x.fac, type: x.type, share: x.share, n: 0, tax: x.est, claim: Math.round(c.est.amt * x.est / tot), label: '나라장터 계약 어림' + (typeof x.share === 'number' && x.share < 1 ? `(과세 몫 ${Math.round(x.share * 100)}% 반영)` : '') }); }
    return [...m.values()].sort((a, b) => b.claim - a.claim); }
  return { cases, docs, facsOf };
}
export function caseCorrDocs(D: Data, o: CbIn): Map<string, CorrDoc[]> {
  const M = new Map<string, CorrDoc[]>(); const { cases, facsOf } = buildCases(D, o);
  const most = (xs: (string | undefined)[]) => { const c = new Map<string, number>(); for (const x of xs) if (x) c.set(x, (c.get(x) ?? 0) + 1); return [...c].sort((a, b) => b[1] - a[1])[0]?.[0] ?? ''; };
  const addr0 = most(cases.map(c => c.d.addr)), office0 = most(cases.map(c => c.d.office));
  for (const c of cases) { if (c.left < 0 || c.nextFin || c.gain <= 0) continue; const d = c.d; const t = (n: number) => d.cells[n]?.tax ?? null;
    const ded = t(18) ?? 0, c9 = t(9); const F = facsOf(c); const nd2 = d.nd?.reasons[2]?.tax ?? 0, nd5 = d.nd?.reasons[5]?.tax ?? 0; const why = nd2 >= nd5 && nd2 > 0 ? "'사업과 직접 관련 없는 지출'" : nd5 > 0 ? "'면세사업 관련'" : '불공제';
    if (c.mode === 'corr' && c.corr) { M.set(`${c.k}|${c.pre ? 0 : 1}`, [{ ...c.corr, reg: c.corr.reg || d.reg || o.reg, addr: d.addr || addr0 || undefined, filedOn: d.filedOn, office: d.office || office0 || undefined, pen: c.corr.pen ?? d.pen ?? null, due: c.corr.due ?? d.due ?? null, tb: c.corr.tb ?? d.cells[9]?.amt ?? null }]); continue; }
    const names = F.slice(0, 3).map(f => short(f.fac)).join('·') + (F.length > 3 ? ` 등 ${F.length}곳` : '');
    const reason = `사용료를 과세 매출로 신고하는 시설(${names})의 공사·관리·운영비 매입세액 ${fmt(c.gain)}원을 ${why}로 불공제함. 과세사업에 쓴 매입세액은 공제 대상(부가가치세법 제38조, 같은 법 시행령 제46조)이므로 공제받지 못할 매입세액을 ${fmt(c.gain)}원 줄여 경정을 청구함${F.some(f => typeof f.share === 'number' && f.share < 1) ? '(같이 쓰는 건물은 과세 면적 비율만, 같은 법 시행령 제81조)' : ''}${c.mode === 'cand' ? ' — 금액은 계약으로 짐작한 값, 세금계산서로 확인 뒤 확정' : ''}. 세부 근거는 붙임 엑셀·사유서.`;
    const doc: CorrDoc = { k: c.k, kind: d.kind, file: d.file, reg: d.reg || o.reg, delta: c.gain, reason, addr: d.addr || addr0 || undefined, filedOn: d.filedOn, office: d.office || office0 || undefined,
      cells: [{ n: 16, label: '매입세액 합계', amt: d.cells[16]?.amt ?? null, before: t(16), after: t(16) }, { n: 17, label: '공제받지 못할 매입세액', amt: d.cells[17]?.amt ?? null, before: t(17), after: t(17) != null ? t(17)! - c.gain : null }, { n: 18, label: '차감계(공제받는 매입세액)', amt: d.cells[18]?.amt ?? null, before: ded, after: ded + c.gain }],
      parts: d.nd ? [{ sec: '명세서', rows: [{ label: nd2 >= nd5 ? '② 사업과 직접 관련 없는 지출' : '⑤ 면세사업등 관련', before: nd2 >= nd5 ? nd2 : nd5, after: (nd2 >= nd5 ? nd2 : nd5) - c.gain }] }] : [],
      payBefore: c9 != null ? c9 - ded : null, payAfter: c9 != null ? c9 - ded - c.gain : null, tb: d.cells[9]?.amt ?? null, pen: d.pen ?? null, due: d.due ?? null };
    M.set(`${c.k}|${c.pre ? 0 : 1}`, [doc]); }
  let pg = 0; for (const k of [...M.keys()].sort()) for (const x of M.get(k)!) x.page = ++pg;
  return M;
}
export function caseBook(D: Data, o: CbIn): Blob | null {
  const { cases, docs, facsOf } = buildCases(D, o); if (!docs.length) return null; const facs = facsOf;
  const pages = new Map<string, number>(); for (const [k, v] of caseCorrDocs(D, o)) pages.set(k, v[0].page ?? 0);
  const pageOf = (c: Case) => pages.get(`${c.k}|${c.pre ? 0 : 1}`) ?? 0;
  const open = cases.filter(c => c.left >= 0 && !c.nextFin);
  const total = open.reduce((n, c) => n + c.gain, 0);
  const sheets: Sheet[] = [];

  /* 1. 먼저 읽기 */
  { const R: Cell[][] = []; const st: Record<number, number> = {}; const add = (r: Cell[], s = 0) => { if (s) st[R.length] = s; R.push(r); };
    add([`${o.org} 부가가치세 경정청구 작업서 — 신고서별`], 2); add([`${o.today} 작성 · 지자체 부가세 돌려받기(참고 계산 — 신고 책임은 신고인, 판정은 기관의 판단이 아닙니다)`]);
    add([`사업자등록번호 ${o.reg || '(확인)'} · 올린 신고서 ${docs.length}장 · 경정청구 기한 안 ${open.length}장 · 돌려받을 세액 합계(어림) ${fmt(total)}원${o.rows.length ? '' : ' — 매입 목록이 없어 조달청 나라장터 계약으로 짐작한 값'}`], 1); add([]);
    add(['이 파일로 하는 일 — 순서대로'], 3);
    [['1', '「신고별 요약」 시트에서 경정청구 기한이 가까운 신고서부터 봅니다(남은 날이 적은 순).'],
     ['2', '그 신고서 시트의 「확인할 것」을 하나씩 확인합니다 — 시설이 사용료를 과세로 신고해 온 곳인지, 같이 쓰는 건물의 면적, 세금계산서의 받는 쪽 사업자등록번호.'],
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
  { const head = ['순서', '신고서', '시트', '경정청구서 PDF 쪽', '신고기간', '법정신고기한', '경정청구 기한', '남은 날', '당초 공제받은 매입세액 (18)', '경정 후 (18)', '돌려받을 세액', '근거', '주된 이유', '확인할 것'];
    const L = [...cases].sort((a, b) => (a.left < 0 ? 1e9 : a.left) - (b.left < 0 ? 1e9 : b.left) || b.gain - a.gain);
    const rows: Cell[][] = [head, ...L.map((c, i) => { const ded = tax(c.d, 18) ?? 0; const why = topReason(c); return [i + 1, c.name, c.sheet, pageOf(c) || '—', `${c.d.year}-${String(c.d.from).padStart(2, '0')} ~ ${String(c.d.to).padStart(2, '0')}월`, c.due, c.cdue, c.left < 0 ? '기한 지남' : c.nextFin ? `확정신고(${legalDue(c.d.year, c.d.half, false)})에 넣기` : c.left, ded, c.gain ? ded + c.gain : ded, c.left < 0 || c.nextFin ? 0 : c.gain, c.mode === 'list' ? '매입 목록(세금계산서)' : c.mode === 'cand' ? '조달청 계약(추정)' : c.mode === 'corr' ? '신고서 숫자 재계산' : '—', why, checks(c).length]; }),
      [], ['', '합계(기한 안)', '', '', '', '', '', '', '', '', total]];
    sheets.push({ name: '신고별 요약', rows, widths: [6, 18, 14, 10, 16, 12, 12, 9, 16, 16, 16, 18, 70, 10] }); }

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
    if (c.pre) out.push('예정신고분 — 예정신고서를 따로 경정청구할지(기한을 예정신고기한 + 5년으로 보수적으로 적었습니다), 같은 과세기간 확정신고 경정청구에 합칠지 관할 세무서에 먼저 묻습니다');
    if (F.some(f => /공통|본청|행정/.test(f.fac + f.label))) out.push('본청·행정과 같이 쓴 지출은 공급가액이 없는 고유사무가 섞여 매입가액·면적 같은 다른 기준이 필요할 수 있습니다(대법원 2017두55329) — 기준을 정해 세무서 질의로 굳힙니다');
    out.push('수탁기관(재단·민간위탁)이 운영하는 시설 지출은 그 기관 몫이라 넣지 않았습니다 — 위·수탁 협약서의 사용료(무상·유상) 조항 확인');
    return out; }
  function reasonText(c: Case): string {
    if (c.mode === 'corr' && c.corr) return corrReason(c.corr) + ` 이에 따라 납부세액 ${fmt(c.gain)}원을 돌려주시기 바랍니다(국세기본법 제45조의2 제1항).`;
    const F = facs(c); const nd2 = c.d.nd?.reasons[2]?.tax ?? 0; const c16 = tax(c.d, 16) ?? 0; const ded = tax(c.d, 18) ?? 0;
    const a = `청구인 ${o.org}(${o.reg || '사업자등록번호'})은 ${pName(c.k)} ${c.d.kind}신고(신고기간 ${c.d.year}. ${c.d.from}. ~ ${c.d.to}.)에서 받은 세금계산서 매입세액 ${fmt(c16)}원 가운데 ${fmt(ded)}원만 공제받았습니다${nd2 > 0 ? `(${fmt(nd2)}원은 '사업과 직접 관련 없는 지출'로 불공제)` : ''}.`;
    const b = F.length ? ` 그러나 이 가운데 ${F.slice(0, 5).map(f => `${f.fac} ${fmt(f.claim)}원`).join(', ')}${F.length > 5 ? ` 외 ${F.length - 5}곳` : ''}은 청구인이 사용료를 받아 과세 매출로 신고하는 시설(지방자치단체가 공급하더라도 과세되는 사업, 부가가치세법 제26조 제1항 제19호·같은 법 시행령 제46조)의 공사·관리·운영에 쓴 것으로 공제 대상 매입세액(같은 법 제38조)입니다.` : '';
    const sh = F.filter(f => typeof f.share === 'number' && f.share < 1); const cc = sh.length ? ` 과세·면세 공간이 섞인 건물(${sh.map(f => f.fac).join(', ')})의 매입세액은 과세로 쓰는 면적 비율만큼만 넣었습니다(같은 법 제40조, 시행령 제81조 제4항).` : '';
    const d = ` 따라서 공제받지 못할 매입세액 (17)을 ${fmt(tax(c.d, 17) ?? 0)}원에서 ${fmt(Math.max(0, (tax(c.d, 17) ?? 0) - c.gain))}원으로, 공제받는 매입세액 (18)을 ${fmt(ded)}원에서 ${fmt(ded + c.gain)}원으로 고쳐 납부세액 ${fmt(c.gain)}원을 돌려주시기 바랍니다(국세기본법 제45조의2 제1항).`;
    return a + b + cc + d; }
  function plain(c: Case): string {
    if (c.mode === 'corr') return `신고서 숫자를 다시 계산해 보니 같이 쓴 비용의 부가세를 나누는 계산이 맞지 않아 ${fmt(c.gain)}원을 더 냈습니다. 그 몫을 돌려 달라고 신청하는 것입니다.`;
    const F = facs(c); if (!c.gain) return '이 신고서에서 고칠 것을 찾지 못했습니다.';
    return `돈을 받는 시설(${F.slice(0, 4).map(f => f.fac).join(', ')})에 쓴 공사·관리비의 부가세는 원래 돌려받을 수 있는 돈인데, 신고 때 '행정에 쓴 돈'과 같이 묶어 돌려받지 않은 것으로 처리했습니다. 그 몫 ${fmt(c.gain)}원을 돌려 달라고 신청하는 것입니다.${c.mode === 'cand' ? ' (계약 금액으로 짐작한 값 — 세금계산서로 확인 필요)' : ''}`; }

  for (const c of cases) {
    const d = c.d; const R: Cell[][] = []; const st: Record<number, number> = {}; const add = (r: Cell[], s = 0) => { if (s) st[R.length] = s; R.push(r); };
    const c16 = tax(d, 16), c17 = tax(d, 17), c18 = tax(d, 18), c9 = tax(d, 9); const ded = c18 ?? 0; const g = c.left < 0 ? 0 : c.gain;
    add([`${c.name} 경정청구 — ${o.org}`], 2);
    add(['신고기간', `${d.year}. ${d.from}. ~ ${d.to}. (${d.kind})`, '법정신고기한', c.due, '경정청구 기한', `${c.cdue}${c.left < 0 ? ' — 지남(청구 불가)' : ` (D-${c.left})`}`]);
    add(['사업자등록번호', d.reg || o.reg || '', '당초 신고 파일', d.file, '근거 자료', c.mode === 'list' ? `매입 목록 ${c.rows.length}건` : c.mode === 'cand' ? '조달청 나라장터 계약(추정)' : c.mode === 'corr' ? '신고서 숫자 재계산' : '없음']);
    add(['돌려받을 세액', g, '쉬운 말', plain(c)], 5);
    if (pageOf(c)) add(['경정청구서', `함께 받은 「경정청구서(국세청 서식)」 PDF ${pageOf(c)}쪽 — 숫자를 다 채워 두었습니다. 기관장 성명·서명, 전화, 환급 계좌, 날짜만 적으면 됩니다. 같은 쪽 번호의 「경정청구 사유서」 PDF 를 붙임으로 냅니다.`], 5);
    if (c.nextFin) add(['', `이 과세기간 확정신고(기한 ${legalDue(d.year, d.half, false)})가 아직이라 경정청구를 하지 않고, 확정신고서의 (13) 예정신고 누락분 칸(매입)에 이 ${fmt(g)}원을 넣어 공제받습니다. 아래 값은 그 계산 근거입니다(요약 합계에서는 뺐습니다).`], 5);
    add([]);
    add(['1. 홈택스 경정청구 화면에 넣을 값 (일반과세자 신고서 칸)'], 3); add(['칸', '이름', '당초 금액', '당초 세액', '경정 후 금액', '경정 후 세액', '바뀌는 세액', '설명'], 1);
    const sales: [number, string][] = [[1, '세금계산서 발급분(과세 매출)'], [3, '신용카드·현금영수증 발행분'], [4, '기타(정규영수증 외 매출분)'], [9, '과세표준 및 매출세액 합계']];
    for (const [n, nm] of sales) if (d.cells[n]) add([`(${n})`, nm, amt(d, n), tax(d, n), amt(d, n), tax(d, n), 0, '매출은 바꾸지 않음']);
    add(['(10)', '세금계산서 수취분 일반매입', amt(d, 10), tax(d, 10), amt(d, 10), tax(d, 10), 0, '이미 신고에 들어 있는 세금계산서 — 그대로']);
    add(['(16)', '매입세액 합계', amt(d, 16), c16, amt(d, 16), c16, 0, '그대로']);
    const ga = c.left < 0 ? 0 : c.gainAmt; const a17 = amt(d, 17) != null && ga != null ? Math.max(0, (amt(d, 17) ?? 0) - ga) : null;
    add(['(17)', '공제받지 못할 매입세액', amt(d, 17), c17, a17, c17 != null ? Math.max(0, c17 - g) : null, -g, ga != null ? '과세 시설 몫(공급가액·세액)을 빼서 줄임' : '과세 시설 몫을 빼서 줄임 — 금액 칸은 세금계산서 공급가액 합으로 맞추기'], 1);
    add(['(18)', '차감계(공제받는 매입세액)', amt(d, 18), c18, amt(d, 18) != null && ga != null ? (amt(d, 18) ?? 0) + ga : null, ded + g, g, '(16) − (17)'], 1);
    if (c9 != null) add(['', '납부(환급)세액 = 매출세액 − (18)', null, c9 - ded, null, c9 - ded - g, -g, '이만큼 덜 내야 했음 → 돌려받음']);
    if (d.due != null) add(['(30)', '차가감 납부할 세액(환급받을 세액)', null, d.due, null, d.due - g, -g, '경정 후 값이 음수(−)면 그만큼 돌려받는다는 뜻']);
    add([]); add(['2. 공제받지 못할 매입세액 명세서 — 고칠 값'], 3); add(['사유', '', '당초 매수', '당초 공급가액', '당초 세액', '경정 후 세액', '바뀌는 세액', '설명'], 1);
    const RN = ['① 필요적 기재사항 누락 등', '② 사업과 직접 관련 없는 지출', '③ 비영업용 소형승용차', '④ 기업업무추진비 등', '⑤ 면세사업등 관련', '⑥ 토지의 자본적 지출', '⑦ 사업자등록 전 매입세액', '⑧ 금·구리 스크랩'];
    const rs = d.nd?.reasons ?? {}; const target = (rs[2]?.tax ?? 0) >= (rs[5]?.tax ?? 0) ? 2 : 5; let left = g;
    RN.forEach((nm, i) => { const n = i + 1, x = rs[n]; if (!x?.tax && n !== target) return; const cut = n === target ? Math.min(left, x?.tax ?? 0) : 0; if (n === target) left -= cut; add([nm, '', x?.n ?? null, x?.amt ?? null, x?.tax ?? 0, (x?.tax ?? 0) - cut, -cut, n === target && cut ? '과세 시설 몫을 이 사유에서 뺌 — 그 세금계산서가 이 사유로 묶여 있던 것' : '']); });
    if (!d.nd) add(['(이 신고서에 명세서가 없음)', '', null, null, null, null, null, '당초 신고 때 낸 명세서를 홈택스 신고내역에서 확인']);
    add([]); add(['3. 이유'], 3);
    add(['청구 사유(그대로 붙여넣기)', reasonText(c)], 4);
    add(['쉬운 말', plain(c)], 4);
    add([]); add(['4. 근거 — 법령'], 3); add(['조문', '무엇을 정했나', '원문 링크'], 1);
    const bs: Basis[] = [{ law: 'basic', art: '제45조의2' }, { law: 'act', art: '제38조' }, { law: 'act', art: '제39조' }, { law: 'act', art: '제26조' }, { law: 'decree', art: '제46조' }];
    for (const r of c.rows) if (r.claim) for (const b of r.basis) if (!bs.some(x => x.law === b.law && x.art === b.art)) bs.push(b);
    if (facs(c).some(f => typeof f.share === 'number' && f.share < 1)) for (const b of [{ law: 'act', art: '제40조' }, { law: 'decree', art: '제81조' }]) if (!bs.some(x => x.law === b.law && x.art === b.art)) bs.push(b);
    for (const b of bs) add(lawLine(D, b), 4);
    const types = [...new Set(facs(c).map(f => f.type).filter(Boolean) as string[])]; const rids = [...new Set(types.flatMap(t => D.facilities.find(x => x.key === t)?.rulings ?? []))];
    const RL = (D.rulings ?? []).filter(x => rids.includes(x.id));
    if (RL.length) { add([]); add(['5. 근거 — 유권해석·판례(같은 종류 시설)'], 3); add(['번호', '제목·요지', '원문'], 1); for (const x of RL) add([x.no, `${x.title} — ${x.gist}${x.verify ? ' (원문 확인 필요)' : ''}`, x.url ?? ''], 4); }
    for (const t of types) { const fr = D.facilities.find(x => x.key === t); if (fr?.cond) { if (!RL.length) { add([]); add(['5. 근거 — 시설 종류 기준'], 3); } add([fr.name, fr.cond], 4); } }
    add([]); add(['시설별 내역'], 3); add(['시설', '판정', '건수', '이 기간 매입세액', '공제 대상 세액', '과세 몫'], 1);
    for (const f of facs(c)) add([f.fac, f.label, f.n || null, f.tax, f.claim, typeof f.share === 'number' && f.share < 1 ? `${Math.round(f.share * 100)}%(추정)` : '100%']);
    add([]); add(['확인할 것 — 확인하면 ☑'], 3); for (const x of checks(c)) add(['☐', x], 4);
    add([]); add(['6. 붙임 서류'], 3);
    ['당초 신고서 사본(홈택스 → 신고/납부 → 세금신고 → 신고내역 조회 출력)', '고친 공제받지 못할 매입세액 명세서(위 2.)', '시설이 과세 사업이라는 근거 — 사용료 조례 별표(부가가치세 포함 문구)·과세표준 명세의 업종', '그 시설에 쓴 지출이라는 근거 — 계약서·검수조서·세금계산서 목록(이 파일 「건별 근거」)', ...(facs(c).some(f => typeof f.share === 'number' && f.share < 1) ? ['면적 근거 — 건축물대장·사용허가서(과세로 쓰는 면적)'] : [])].forEach(x => add(['☐', x], 4));
    add([]); add(['7. 검토'], 3); add(['작성', '', '검토', '', '결재', '']); add(['작성일', '', '세무서 접수일', '', '결과 통지일', '']);
    sheets.push({ name: c.sheet, rows: R, style: st, freeze: false, widths: [22, 40, 16, 16, 16, 16, 14, 60] });
  }

  /* 4. 건별 근거 */
  if (o.rows.length) {
    const rows: Cell[][] = [['신고서(시트)', '날짜', '공급자', '공급자 등록번호', '품목·사업명', '공급가액', '세액', '시설', '판정', '공제 대상 세액', '근거 조문', '이유']];
    for (const c of cases) for (const r of c.rows) if (r.claim) rows.push([c.sheet, r.d, r.sup, r.sreg, r.desc, r.amt, r.tax, r.fac, r.label, r.claim, r.basis.map(b => `${LAW[b.law] ?? b.law} ${b.art}`).join(' · '), r.why.join(' ')]);
    sheets.push({ name: '건별 근거', rows, widths: [14, 11, 24, 14, 40, 14, 12, 28, 30, 14, 26, 60] });
  }
  return xlsxBlob(sheets);
}
