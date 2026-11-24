/** 세무서 담당 조사관을 설득하는 경정청구 꾸러미(운영자 2026-11-24, docs/prompts/vat_persuade_taxoffice.md).
 *  '설득'은 조사관이 스스로 확인하려던 것을 먼저 꺼내 놓는 것 — 쟁점을 등급으로 나눠(vat_casebook caseIssues) 1·2등급만 이번에 청구하고,
 *  3등급(매출 신고가 전제)·4등급(해석 다툼)은 먼저 밝히고 처리 방법(수정신고 비교·사전답변 질의 초안)을 붙인다.
 *  새 판정 규칙 없음 — 숫자는 신고서별 작업서(caseCorrDocs·caseBook)와 같은 계산. 사람 이름·전화·계좌 없음(빈칸). 판정은 참고이며 기관의 판단이 아니다. */
import { fmt, penaltyCalc, inquiryText, lawText, type Data, type PersuadeQ } from './vat_rules';
import { caseIssues, caseCorrDocs, caseBook, type CbIn, type Issue, type Grade, type Conf } from './vat_casebook';
import { claimFormPdf, reasonDocPdf } from './vat_claimform';
import { xlsxBlob, type Sheet } from './xlsx_write';
import type { CorrDoc } from './vat_diag';

export type PFile = { name: string; data: string | Uint8Array };
type Cell = string | number | null | undefined;
const pName = (k: string) => { const [y, h] = k.split('-'); return `${y}년 제${h}기`; };
let FIRST = (g: Grade) => g <= 2;
/** 3등급을 '매출 수정신고와 같이 냄'으로 확인하면 이번 청구에 넣는다 */
const setFirst = (o: CbIn) => { FIRST = (g: Grade) => g <= 2 || (g === 3 && o.conf?.g3 === 'together'); };
export const CONF_KEY = 'vat-confirm-v1';
/** 제출 전 확인 질문(화면 버튼) — 지금 등급에서 청구에 영향이 있는 사실만. 누르면 등급·청구액·10 답·00 할 일이 바뀐다(2026-11-24 운영자 '공무원이 기재 할 일을 최대한 줄여') */
export type ConfItem = { id: string; q: string; opts: [string, string][]; v?: string };
export function confItems(D: Data, o: CbIn): ConfItem[] {
  const iss = caseIssues(D, o); const cf = o.conf ?? {}; const out: ConfItem[] = []; const seen = new Set<string>();
  const facs = [...new Set(iss.map(i => i.fac))].filter(f => !f.startsWith('('));
  for (const f of facs) { const xs = iss.filter(i => i.fac === f); const type = xs[0]?.type; const c = cf.fac?.[f] ?? {};
    const open = xs.some(i => i.grade === 2) || xs.some(i => /관람석|강습료|사용료를 과세 매출로|매출이 없음/.test(i.why));
    if (!open) continue;
    if (type === 'sports' && (xs.some(i => i.grade === 2) || xs.some(i => /관람석|강습료/.test(i.why)))) {
      out.push({ id: `seats|${f}`, q: `${f} — 관중이 경기를 보는 관람석이 있나요?`, opts: [['no', '없음'], ['yes', '있음']], v: c.seats });
      out.push({ id: `lessons|${f}`, q: `${f} — 구가 직접 여는 강좌의 수강료 수입이 있나요?`, opts: [['no', '없음'], ['yes', '있음']], v: c.lessons }); }
    if (!seen.has(f)) { seen.add(f); out.push({ id: `sales|${f}`, q: `${f} — 이 시설 사용료를 지난 부가세 신고 때 매출로 넣었나요?`, opts: [['yes', '넣었음'], ['no', '안 넣었음']], v: c.sales }); } }
  if (iss.some(i => i.fac === '(신고서 숫자로 다시 계산)')) out.push({ id: 'apport', q: '같이 쓴 지출의 부가세를 나눌 때 매출 금액 비율로 나눴나요?(지난 신고서 뒤쪽 명세서의 3번 표)', opts: [['supply', '매출 금액 비율'], ['other', '다른 기준']], v: cf.apport });
  if (iss.some(i => i.grade === 3)) out.push({ id: 'g3', q: '사용료를 매출로 넣지 않은 시설 — 빠진 매출을 이번에 같이 고쳐 낼까요?(같이 내면 그 시설 부가세도 이번에 돌려받고, 가산세 감면이 큼)', opts: [['together', '같이 냄'], ['later', '나중에']], v: cf.g3 });
  return out;
}
/** 확인 답을 Conf 에 넣기 */
export function confSet(c: Conf, id: string, v: string): Conf { const [k, f] = id.split('|'); const n: Conf = { ...c, fac: { ...(c.fac ?? {}) }, at: new Date().toISOString().slice(0, 10) };
  if (f) { const x = { ...(n.fac![f] ?? {}) } as Record<string, string>; x[k] = v; n.fac![f] = x; } else (n as Record<string, unknown>)[k] = v; return n; }
const GNAME: Record<Grade, string> = { 1: '계산 정정', 2: '증빙으로 끝남', 3: '매출과 함께', 4: '해석 다툼' };
/** 확정신고기한(가산세 어림의 법정신고기한) */
const finDue = (k: string) => { const [y, h] = k.split('-').map(Number); return h === 1 ? `${y}-07-25` : `${y + 1}-01-25`; };
const bin = async (b: Blob) => new Uint8Array(await b.arrayBuffer());
/** 은/는 — 마지막 글자 받침으로 */
const eun = (s: string) => { const c = s.trim().slice(-1).charCodeAt(0); return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? `${s}은` : `${s}는`; };
/** 사업자등록번호 3-2-5 */
const bizno = (s: string) => { const d = String(s ?? '').replace(/\D/g, ''); return d.length === 10 ? `${d.slice(0, 3)}-${d.slice(3, 5)}-${d.slice(5)}` : s; };

export type Plan = { issues: Issue[]; sum: Record<Grade, number>; first: number; later: number; urgent: Issue[]; M: Map<string, CorrDoc[]>; nDocs: number; span: string; g3: G3[]; reqs: string[]; qs: PersuadeQ[] };
type G3 = { k: string; fac: string; gap: string; amt: number; rev: number; sales: number; pen: number; net: number | null };

/** 등급·금액·먼저 낼 묶음의 고친 신고서·매출과 함께 비교·필요한 증빙 요청 */
export function persuadePlan(D: Data, o: CbIn): Plan {
  setFirst(o);
  const issues = caseIssues(D, o); const sum = { 1: 0, 2: 0, 3: 0, 4: 0 } as Record<Grade, number>; for (const i of issues) sum[i.grade] += i.amt;
  const M = caseCorrDocs(D, o, FIRST); const docs = [...M.values()].flat(); const ks = [...new Set(issues.map(i => i.k))].sort();
  /* 3등급 — 과세기간 × 시설로 모아, 시설 수입(세입예산 연 수입 ÷ 2, 부가세 포함으로 보고 ÷ 11)의 매출세액과 과소신고·납부지연 가산세(오늘 수정신고·납부)를 뺀 순액 */
  const m3 = new Map<string, G3>(); for (const i of issues) if (i.grade === 3) { const key = `${i.k}|${i.fac}`; const x = m3.get(key) ?? { k: i.k, fac: i.fac, gap: i.gap ?? '', amt: 0, rev: 0, sales: 0, pen: 0, net: null }; x.amt += i.amt; m3.set(key, x); }
  for (const x of m3.values()) { const rev = Math.round((o.revByFac?.[x.fac] ?? 0) / 2); x.rev = rev; if (!rev) continue; x.sales = Math.round(rev / 11); const p = penaltyCalc(D, { tax: x.sales, due: finDue(x.k), payDate: o.today, kind: 'under' }); x.pen = p.total; x.net = x.amt - x.sales - x.pen; }
  const P = D.rules.persuade; const qIds = new Set<string>(['Q01', 'Q02', 'Q03', 'Q04', 'Q05', 'Q06', 'Q07', 'Q17', 'Q18', 'Q25', 'Q26', 'Q27', 'Q29', ...issues.flatMap(i => i.q)]);
  if (issues.some(i => i.est)) qIds.add('Q08'); if (issues.some(i => /수영|체육센터|국민체육|반다비/.test(i.fac))) qIds.add('Q14'); if (sum[3]) qIds.add('Q28'); if ((o.rows ?? []).some(r => r.claim && /건립|조성|증축|신축|리모델링|건설/.test(r.desc))) { qIds.add('Q15'); qIds.add('Q24'); }
  const qs = (P?.questions ?? []).filter(q => qIds.has(q.id));
  const reqs = [...new Set(qs.map(q => q.req).filter(Boolean))];
  return { issues, sum, first: pl1(sum, o), later: pl1later(sum, o), urgent: issues.filter(i => i.grade >= 3 && i.left <= 90), M, nDocs: docs.length, span: ks.length ? `${pName(ks[0])} ~ ${pName(ks[ks.length - 1])}` : '', g3: [...m3.values()], reqs, qs };
}

const pl1 = (s: Record<Grade, number>, o: CbIn) => s[1] + s[2] + (o.conf?.g3 === 'together' ? s[3] : 0);
const pl1later = (s: Record<Grade, number>, o: CbIn) => s[4] + (o.conf?.g3 === 'together' ? 0 : s[3]);
/** 쟁점을 '무엇 — 시설들' 묶음으로(요약서 3·4번) */
function groups(L: Issue[]) { const m = new Map<string, { why: string; grade: Grade; facs: Set<string>; amt: number; q: string[]; ks: Set<string> }>();
  for (const i of L) { const key = `${i.grade}|${i.why}`; const x = m.get(key) ?? { why: i.why, grade: i.grade, facs: new Set<string>(), amt: 0, q: i.q, ks: new Set<string>() }; x.facs.add(i.fac); x.amt += i.amt; x.ks.add(i.k); m.set(key, x); }
  return [...m.values()].sort((a, b) => b.amt - a.amt); }
const facList = (s: Set<string>, n = 4) => { const a = [...s]; return a.slice(0, n).join(', ') + (a.length > n ? ` 외 ${a.length - n}곳` : ''); };

/** 검토 요약서 — 조사관이 읽는 순서(세무서 용어). 엑셀 첫 시트와 PDF 가 같은 줄 */
export function summaryRows(D: Data, o: CbIn, pl: Plan): { head: string[]; parts: { h: string; lines?: string[]; table?: Cell[][] }[] } {
  const P = D.rules.persuade; const firstIss = pl.issues.filter(i => FIRST(i.grade)); const laterIss = pl.issues.filter(i => !FIRST(i.grade));
  const head = [`부가가치세 경정청구 검토 요약서 — ${o.org}${o.reg ? ` (${o.reg})` : ''}`, `${o.today} 작성 · 관할 세무서 제출·내부 결재 공용 · 숫자는 당초 신고서와 세금계산서로 다시 계산한 값`];
  const parts: { h: string; lines?: string[]; table?: Cell[][] }[] = [];
  parts.push({ h: '1. 청구 요지', lines: [`${eun(o.org)} ${pl.span} 부가가치세 신고서 ${pl.nDocs}장에 대하여 경정을 청구합니다. 청구 세액은 ${fmt(pl.first)}원입니다(계산 정정 ${fmt(pl.sum[1])}원, 증빙으로 확인되는 과세사업 매입세액 ${fmt(pl.sum[2])}원${o.conf?.g3 === 'together' && pl.sum[3] ? `, 같은 날 매출 수정신고를 함께 내는 시설의 매입세액 ${fmt(pl.sum[3])}원` : ''}).`,
    ...(pl.later ? [o.conf?.g3 === 'together' ? `해석이 필요한 몫 ${fmt(pl.sum[4])}원은 이번 청구에 넣지 않았으며, 그 처리는 4번에 먼저 밝힙니다.` : `매출 신고 확인이 전제인 몫 ${fmt(pl.sum[3])}원과 해석이 필요한 몫 ${fmt(pl.sum[4])}원은 이번 청구에 넣지 않았으며, 그 처리는 4번에 먼저 밝힙니다.`] : [])] });
  const T: Cell[][] = [['과세기간·구분', '당초 (16)', '당초 (17)', '당초 (18)', '경정 후 (17)', '경정 후 (18)', '청구 세액', '등급', '청구 기한', '붙임']];
  for (const k of [...pl.M.keys()].sort()) for (const c of pl.M.get(k)!) { const cell = (n: number) => c.cells.find(x => x.n === n); const gs = [...new Set(pl.issues.filter(i => i.key === k && FIRST(i.grade)).map(i => i.grade))].sort().join('·');
    const iss = pl.issues.find(i => i.key === k); T.push([`${pName(c.k)} ${c.kind}`, cell(16)?.before ?? null, cell(17)?.before ?? null, cell(18)?.before ?? null, cell(17)?.after ?? null, cell(18)?.after ?? null, c.delta, gs || '1', iss ? `${iss.cdue} (D-${iss.left})` : '', `02 ${c.page ?? ''}쪽·03·04`]); }
  T.push(['합계', null, null, null, null, null, [...pl.M.values()].flat().reduce((n, c) => n + c.delta, 0), '', '', '']);
  parts.push({ h: '2. 과세기간별 당초 → 경정 후', table: T, lines: ['등급: 1 = 당초 신고서 숫자만으로 다시 계산되는 몫, 2 = 과세 시설 지출을 세금계산서·계약서로 보이는 몫. (16) 받은 매입세액 합계, (17) 공제받지 못할 매입세액, (18) 공제받는 매입세액.'] });
  const lawOf = (g: { grade: Grade }) => g.grade === 1 ? '부가가치세법 제40조, 같은 법 시행령 제81조 제1항·제82조' : '부가가치세법 제26조 제1항 제19호·제38조, 같은 법 시행령 제46조 제3호, 재경부 부가가치세제과-186(2007. 3. 22.)';   /* 세무서 제출 문서에는 청구를 받치는 조문만(2017두55329 는 안분 기준 다툼 쪽 근거라 내부 자료에만 — 세무법인 역할 시험 2026-11-24) */
  const g12 = groups(firstIss).slice(0, 3);
  { const docs = o.docs ?? []; const ks = [...new Set(firstIss.filter(i => i.grade === 2).map(i => i.k))]; const nd2 = ks.some(k => docs.some(d => `${d.year}-${d.half}` === k && (d.nd?.reasons[2]?.tax ?? 0) > 0 && (d.nd?.reasons[2]?.tax ?? 0) >= (d.nd?.reasons[5]?.tax ?? 0)));
    const lines = g12.length ? g12.map((g, i) => `${i + 1}) ${g.grade === 1 ? '당초 명세서의 공통매입세액 안분·정산 계산' : `과세사업 시설(${facList(g.facs)})의 매입세액 불공제`} ${fmt(g.amt)}원 — ${g.grade === 1 ? '총공급가액을 신고서 과세표준((1)~(4))과 면세공급가액의 합으로 바로잡아 시행령 제81조 제1항 식을 다시 계산하면 불공제가 줄어듦(계산 줄은 붙임 03 2항·04 2항, 예정신고분이 있으면 제82조 정산 내역을 함께 붙임)' : `사용료를 과세 매출로 신고하는 시설의 공사·관리비 매입세액${nd2 ? ". 당초 신고 때 이 지출을 행정 지출과 구분하지 않고 '② 사업과 직접 관련 없는 지출'로 함께 불공제함" : ''}`}. 근거: ${lawOf(g)}. 붙임 ${g.grade === 1 ? '03·04' : '04·05·06·07'}`) : ['청구할 1·2등급 쟁점이 없습니다.'];
    parts.push({ h: '3. 쟁점(금액 큰 순)', lines }); }
  { const ks = [...new Set(firstIss.filter(i => i.grade === 2).map(i => i.k))].sort(); const docs = o.docs ?? [];
    const L = ks.map(k => { const cs = docs.filter(d => `${d.year}-${d.half}` === k).flatMap(d => (d.base?.length ? d.base.map(b => `${b.code} ${fmt(b.amt)}원`) : (d.codes ?? []).map(c => `${c.code}${c.zero ? ' 0원' : ''}`))); return cs.length ? `${pName(k)}: ${[...new Set(cs)].join(', ')}` : ''; }).filter(Boolean);
    if (L.length) parts.push({ h: '3-1. 당초 신고서 과세표준 명세(업종코드 · 금액)', lines: [...L, '청구한 시설의 사용료는 위 업종 코드의 과세 매출로 신고하였습니다(시설별 세입 실적과의 대사는 청구인 붙임).'] }); }
  const dis = groups(laterIss).map(g => g.grade === 3 ? `${facList(g.facs)}: 그 시설 사용료의 과세 매출 신고를 확인하고 있어 이번 청구에 넣지 않았습니다(${fmt(g.amt)}원, ${[...g.ks].sort().map(pName).join(', ')}).` : `${facList(g.facs)}: ${g.why} — 이번 청구에 넣지 않았고, 서면질의(또는 세법해석 사전답변)로 기준을 정한 뒤 따로 청구합니다(${fmt(g.amt)}원, ${[...g.ks].sort().map(pName).join(', ')}).`);
  if (pl.urgent.length) dis.push(`경정청구 기한이 90일 안에 끝나는 몫이 있습니다(${[...new Set(pl.urgent.map(i => `${pName(i.k)} ${i.cdue}`))].join(', ')}) — 기한을 지키려면 그 몫만 따로 청구하는 안을 관할 세무서와 상의합니다(국세기본법 제45조의2 제1항).`);
  if (o.conf?.g3 === 'together' && pl.sum[3]) { const f3 = [...new Set(pl.issues.filter(i => i.grade === 3).map(i => i.fac))]; dis.unshift(`${facList(new Set(f3))}: 그 기간 사용료를 매출로 신고하지 않은 것을 확인해, 같은 날 매출 수정신고(국세기본법 제45조)를 함께 내고 그 시설 매입세액 ${fmt(pl.sum[3])}원을 이번에 청구합니다.`); }
  if (dis.length) dis.push('이번 청구에서 뺀 세금계산서는 당초 신고대로 공제받지 못할 매입세액에 남아 있으며, 따로 청구할 때 같은 세금계산서를 이번 청구와 겹치지 않게 적습니다(붙임 04 2항·06).');
  parts.push({ h: '4. 청구인이 먼저 밝히는 것', lines: dis.length ? dis : [P?.disclose_none ?? ''] });
  parts.push({ h: '5. 붙임', lines: [...FILES.filter(f => SUBMIT.includes(f.n) && f.n !== '01').map(f => `붙임 ${f.n} ${f.t}`), '청구인이 더 붙이는 것: 당초 신고서·공제받지 못할 매입세액 명세서 사본(같은 과세기간 예정신고서 포함, 홈택스 신고내역 출력), 사업자등록증 사본, 시설별 사용료 조례 별표와 그 기간 사용료 세입 실적(과세표준 대사), 세액이 큰 계약의 계약서·준공검사조서'] });
  return { head, parts };
}

/** 세무서에 내는 파일(01 요약서 + 붙임 02~07). 00·08~12 는 기관 안에서만 쓴다 */
export const SUBMIT = ['01', '02', '03', '04', '05', '06', '07'];
/** 묶음 파일 이름(앞 번호 = 붙임 번호) */
export const FILES = [
  { n: '00', f: '00_이렇게_하세요(할일7).txt', t: '청구인 할 일' }, { n: '01', f: '01_검토요약서.pdf', t: '검토 요약서' },
  { n: '02', f: '02_경정청구서(별지16의2)_신고서별.pdf', t: '경정청구서(국세기본법 시행규칙 별지 제16호의2서식, 신고서별)' }, { n: '03', f: '03_경정청구_사유서.pdf', t: '경정청구 사유서(신고서별, 근거 법령)' },
  { n: '04', f: '04_재계산표_신고서별.xlsx', t: '재계산표(신고서별 당초 → 경정 후, 불공제 명세서 고칠 값)' }, { n: '05', f: '05_공제로_옮기는_세금계산서_공급자별.csv', t: '불공제에서 공제로 옮기는 세금계산서(공급자별, 당초 신고 포함 여부)' },
  { n: '06', f: '06_건별_귀속명세.xlsx', t: '세금계산서별 시설 귀속 명세' }, { n: '07', f: '07_근거_조문·유권해석_발췌.pdf', t: '근거 조문·유권해석 발췌' },
  { n: '08', f: '08_부서별_증빙요청_메모.txt', t: '부서별 증빙 요청 메모(청구인 내부용)' }, { n: '09', f: '09_세무서_사전상담_대본.txt', t: '사전 상담 대본(청구인 내부용)' },
  { n: '10', f: '10_보완요청_답변틀.txt', t: '자료 보완 요청 답변 틀(청구인 내부용)' }, { n: '11', f: '11_사전답변·질의서_초안(4등급).txt', t: '해석이 필요한 몫의 질의서 초안' },
  { n: '12', f: '12_수정신고_함께내기_비교.xlsx', t: '매출 신고 확인이 필요한 몫 — 수정신고와 함께 낼 때의 순액 비교' },
  { n: '13', f: '13_내부_작업서(확인할_것·쟁점_등급·전체_금액).xlsx', t: '기관 내부 작업서 — 모든 등급의 신고서별 계산, 확인할 것, 법령 검토, 세무서가 볼 것' },
];

/** 청구인 할 일 7개 이하 — 순서: 증빙 받기 → 확인 관문 → 결재 → 사전 상담 → 서명·계좌 → 제출 → 그 뒤(신규 공무원·세무법인 역할 시험 2026-11-24) */
function todoText(D: Data, o: CbIn, pl: Plan): string {
  const L: string[] = []; const first = pl.issues.filter(i => FIRST(i.grade)); const minDue = first.length ? first.reduce((a, i) => i.cdue < a ? i.cdue : a, first[0].cdue) : '';
  const offices = (o.docs ?? []).map(d => d.office).filter(Boolean) as string[]; const office = offices.sort((a, b) => offices.filter(x => x === b).length - offices.filter(x => x === a).length)[0];
  const sales3 = pl.g3.reduce((n, x) => n + (x.rev ? x.sales + x.pen : 0), 0); const noRev3 = pl.g3.filter(x => !x.rev).map(x => x.fac);
  const sports = [...new Set(first.filter(i => i.type === 'sports').map(i => i.fac))]; const hasSport = sports.length > 0; const has1 = first.some(i => i.grade === 1); const fac2 = [...new Set(first.filter(i => i.grade === 2).map(i => i.fac))];
  const g3f = [...new Set(pl.g3.map(x => x.fac))]; const g3amt = pl.sum[3]; const site = typeof location !== 'undefined' ? `${location.origin}/vat/review/` : '돌려받기 화면';
  L.push(`${o.org} 부가가치세 경정청구 — 할 일 (${o.today} 작성)`, '', `이번에 청구할 세액 ${fmt(pl.first)}원 · 신고서 ${pl.nDocs}장${minDue ? ` · 가장 이른 청구 기한 ${minDue}` : ''}${office ? ` · 관할 ${office} 세무서` : ''}`,
    '경정청구는 지난 신고에서 더 낸 세금을 바로잡는 정상 절차입니다(국세기본법 제45조의2). 숫자와 근거는 01~07 에 다 있고, 확인이 끝나지 않은 몫은 이번 청구에서 뺐습니다. 이 자료의 판정은 참고 계산이며 기관의 판단이 아닙니다 — 아래 2번 확인을 마친 뒤 냅니다.', '');
  const T: [string, string, string, string][] = [];
  if (pl.reqs.length) T.push([`08 메모를 부서별로 보내 서류를 받습니다(${pl.reqs.length}가지 서류)`, '내부 메신저 또는 업무 연락에 메모를 그대로 붙여넣기(받는 부서 이름은 08 에서 고침)', '보내기 10분, 회신 1~2주', '08 의 ☐ 가 모두 ☑']);
  const ci = confItems(D, o); const left = ci.filter(x => !x.v);
  if (left.length) T.push([`제출 전 확인 ${left.length}가지가 남았습니다 — 돌려받기 화면 「세무서에 내기 전 확인」에서 08 로 받은 서류를 보고 버튼을 누른 뒤 이 묶음을 다시 받습니다(적을 것 없음, 누르면 청구액·답변이 저절로 바뀜). 화면: ${site}${left.map(x => `\n       ☐ ${x.q}`).join('')}`, '08 로 받은 서류와 당초 신고서(홈택스 신고내역 출력)', '15분', '화면의 확인이 모두 끝남']);
  T.push([`01${g3amt && o.conf?.g3 !== 'together' ? '·12' : ''} 를 붙여 결재를 받습니다 — 결재 문서 본문은 아래 「과장님께 드릴 3줄」을 그대로 붙여넣기. 결재선은 기관의 세무 신고 결재선과 같게`, '전자결재', '하루', '결재 완료']);
  T.push([`관할 세무서 부가가치세과에 사전 상담 전화를 합니다 — 09 대본을 읽고 답을 적습니다(제출 방식: 홈택스/서면)`, `${office ? `${office} 세무서` : '신고서에 적힌 관할 세무서'} 대표 전화 → 부가가치세과`, '5분', '09 의 빈칸을 채움']);
  T.push(['홈택스로 내면 02 에는 아무것도 적지 않습니다(02 는 증빙으로 올림). 서면으로 낼 때만 02 의 각 쪽에 기관장 성명·직인, 전화, 환급 계좌, 청구 날짜를 적습니다(이 앱은 사람 이름·전화·계좌를 넣지 않음)', '환급 계좌는 세입 담당 부서에 묻고, 직인은 직인 관리 부서(총무 담당)에서 받습니다', '서면만 10분', '서면이면 02 의 빈칸이 없음']);
  T.push(['경정청구를 냅니다 — 홈택스면 04 각 신고서 시트 「1. 홈택스 경정청구 화면에 넣을 값」을 칸 번호대로 옮기고 환급 계좌를 화면에서 한 번 넣은 뒤, 01~07 과 당초 신고서 사본을 증빙으로 올립니다. 서면이면 01~07 을 출력해 냅니다. 08~13 은 내지 않습니다', '홈택스(부가세 신고 때 쓰던 기관 사업자 인증서 — 없으면 지난 신고 담당자에게 물음) → 신고/납부 → 세금신고 → 부가가치세 → 경정청구. 서면이면 관할 세무서 민원봉사실', '신고서마다 15분', '접수증을 출력해 둠']);
  T.push(['그 뒤: 세무서가 자료 보완을 요청하면 10 에서 비슷한 질문 번호를 찾아 답을 고쳐 보냅니다. 환급 통지를 받으면 바로 세외수입으로 처리합니다(세입세출외현금에 두지 않음 — 정부합동감사 지적 사례)', '10 답변 틀 · 세입 담당 부서', '건마다 20분', '회신·세입 처리 완료']);
  T.forEach(([a, b, c, d], i) => L.push(`☐ ${i + 1}. ${a}`, `     어디서: ${b} · 걸리는 시간: ${c} · 끝났는지: ${d}`, ''));
  { const kn = [...new Set(pl.issues.map(i => i.k))].sort().map(pName).join(', ');
    L.push('과장님께 드릴 3줄', `- 지난 부가세 신고서 ${pl.nDocs}장(${kn})을 다시 계산해, ${fmt(pl.first)}원을 돌려받는 경정청구를 냅니다(과세 시설 지출 공제 ${fmt(pl.sum[2])}원${pl.sum[1] ? ` · 계산 정정 ${fmt(pl.sum[1])}원` : ''}${o.conf?.g3 === 'together' && pl.sum[3] ? ` · 매출을 함께 고치는 시설 ${fmt(pl.sum[3])}원` : ''}).`,
      `- 확인이 더 필요한 ${fmt(pl.later)}원은 이번에 넣지 않습니다${pl.sum[3] && o.conf?.g3 !== 'together' ? ` — 매출 신고 확인 ${fmt(pl.sum[3])}원(${g3f.slice(0, 3).join(', ')})` : ''}${pl.sum[4] ? `, 해석 필요 ${fmt(pl.sum[4])}원` : ''}.`,
      pl.sum[3] && o.conf?.g3 === 'together' ? `- ${g3f.slice(0, 3).join(', ')}의 빠진 사용료 매출은 같은 날 수정신고로 함께 고칩니다(매출세액·가산세 약 ${fmt(sales3)}원 — 12 비교표, 스스로 고치면 가산세 감면).` : pl.sum[3] ? `- ${g3f.slice(0, 3).join(', ')}의 사용료 매출 신고가 빠졌다면 매출세액·가산세 약 ${fmt(sales3)}원을 더 낼 수 있어(12 비교표), 수정신고를 같이 낼지 이번 결재에서 정해 주십시오.` : `- 가장 이른 청구 기한은 ${minDue}이고, 돌려받은 돈은 세외수입으로 처리합니다.`, '');
    void noRev3; }
  if (pl.later) L.push('나중 묶음(이번에 내지 않음)', ...(pl.sum[3] && o.conf?.g3 !== 'together' ? [`- 매출 신고 확인이 필요한 몫 ${fmt(pl.sum[3])}원 → 12 비교표. 화면에서 '같이 냄'을 누르면 이번 청구에 들어감(같은 날 내야 감면이 큼)`] : []), ...(pl.sum[4] ? [`- 해석이 필요한 몫 ${fmt(pl.sum[4])}원 → 11 질의서 초안을 고쳐 국세청 서면질의 또는 세법해석 사전답변으로`] : []), '');
  L.push('세무서에 내는 파일(01 요약서 + 붙임 02~07)', ...FILES.filter(f => SUBMIT.includes(f.n)).map(f => `- ${f.f} — ${f.t}`), '', '기관 안에서만 쓰는 파일(세무서에 내지 않음)', ...FILES.filter(f => !SUBMIT.includes(f.n)).map(f => `- ${f.f} — ${f.t}`), '',
    '낱말 풀이', '- 경정청구: 이미 낸 부가세 신고를 고쳐, 더 낸 세금을 돌려 달라고 세무서에 청구하는 것', '- 제1기·제2기, 예정·확정: 1~6월이 제1기, 7~12월이 제2기. 석 달마다 예정신고, 여섯 달마다 확정신고', '- 매입세액: 공사·물품 대금과 함께 낸 부가세. 과세 시설에 쓴 것은 돌려받을 수 있음', '- 불공제 / 공제받지 못할 매입세액: 돌려받지 않은 것으로 처리한 매입세액', '- (16)(17)(18): 신고서 칸 번호 — (16) 받은 매입세액 합계, (17) 그 가운데 공제받지 않은 것, (18) 공제받은 것',
    '- 과세사업·면세: 사용료에 부가세가 붙는 시설(체육시설·숙박·임대 등)이 과세사업. 지자체의 다른 일은 대부분 면세라 그 지출의 부가세는 돌려받지 못함', '- 공통매입세액 안분: 과세·면세에 같이 쓴 지출의 부가세를 비율로 나누는 것', '- 과세표준 명세·업종코드: 신고서의 업종별 매출 칸과 6자리 업종 번호(예: 9113·809 로 시작하면 스포츠시설 운영, 55 숙박, 70 부동산 임대) — 세무서는 공제받는 시설의 매출이 여기에 있는지 봄', '- 공급가액: 부가세를 뺀 거래 금액. 총공급가액 = 과세 매출 + 면세 수입, 면세공급가액 = 면세 수입', "- 시행령 제81조 제1항 식: 같이 쓴 지출의 부가세 × (면세공급가액 ÷ 총공급가액) = 돌려받지 못하는 몫", '- 자유 이용료·강습료: 시설을 그냥 쓰는 요금(과세)과 강좌 수강료(지자체 직영 강좌는 면세)', "- ② 사업과 직접 관련 없는 지출: 불공제 사유 칸 가운데 하나 — 과세 시설 지출을 여기에 넣으면 돌려받지 못함",
    '- 합계표: 매입처별 세금계산서합계표 — 신고 때 빠진 세금계산서가 있을 때만 경정청구와 함께 냄', '- 수정신고: 덜 낸 세금을 스스로 고쳐 내는 것(가산세 감면)', '- 세외수입 / 세입세출외현금: 돌려받은 돈은 세외수입으로 바로 넣음. 세입세출외현금(보관금)으로 두면 감사 지적', '- 서면질의·사전답변: 국세청에 법 해석을 미리 묻는 길',
    '- 등급: 1 계산 정정 · 2 증빙으로 끝남(이번 청구) · 3 매출 신고 확인 · 4 해석 필요(나중 묶음)', '- 유권해석·판례 번호(예: 부가가치세제과-186): 국세청·기재부 회신과 법원 판결의 번호 — 세무서도 같은 번호로 찾음', '- D-609: 청구 기한까지 남은 날');
  void D; return L.join('\n');
}

function requestText(D: Data, o: CbIn, pl: Plan): string {
  const R = D.rules.persuade?.requests ?? []; const facs = [...new Set(pl.issues.map(i => i.fac))].filter(f => !f.startsWith('(')); const ks = [...new Set(pl.issues.map(i => i.k))].sort().map(pName);
  const first = pl.issues.filter(i => FIRST(i.grade)); const minDue = first.length ? first.reduce((a, i) => i.cdue < a ? i.cdue : a, first[0].cdue) : '';
  const by = new Date(o.today); by.setDate(by.getDate() + 14); const back = `${by.getFullYear()}-${String(by.getMonth() + 1).padStart(2, '0')}-${String(by.getDate()).padStart(2, '0')}`;
  const L = [`부서별 증빙 요청 메모 (${o.today}) — 그대로 붙여넣어 보내세요. 받는 부서 이름은 기관에 맞게 고칩니다.`, ''];
  const Q = D.rules.persuade?.questions ?? []; const facOf = (key: string) => { const ids = new Set(Q.filter(q => q.req === key).map(q => q.id)); const fs = [...new Set(pl.issues.filter(i => i.q.some(x => ids.has(x))).map(i => i.fac))].filter(f => !f.startsWith('(')); return fs.length ? fs : facs; };
  /* 받는 부서 — 시설에 매인 서류는 기관 설정 메모의 세입예산서 부서(시설별)로 나눠 보내고, 없으면 rules.yml 의 짐작 이름(운영자 2026-11-24 '공무원이 기재 할 일을 최대한 줄여') */
  const byDept = new Map<string, { docs: string; why: string; facs: string[] }[]>(); const put = (dept: string, x: { docs: string; why: string; facs: string[] }) => { const a = byDept.get(dept) ?? []; a.push(x); byDept.set(dept, a); };
  for (const key of pl.reqs) { const r = R.find(x => x.key === key); if (!r) continue; const fs = facOf(key); const known = new Map<string, string[]>(); const rest: string[] = [];
    if (!['bizreg', 'hometax', 'subsidy'].includes(key)) for (const f of fs) { const d = o.deptByFac?.[f]; if (d) known.set(d, [...(known.get(d) ?? []), f]); else rest.push(f); } else rest.push(...fs);
    for (const [d, f2] of known) put(d, { docs: r.docs, why: r.why, facs: f2 }); if (rest.length || !known.size) put(r.dept, { docs: r.docs, why: r.why, facs: rest.length ? rest : fs }); }
  for (const [dept, xs] of byDept) {
    L.push('────────────────────', `받는 곳: ${dept}${R.some(r => r.dept === dept) && !dept.includes('본인') ? ' (부서 이름은 짐작 — 맞게 고쳐 보냄)' : ''}`, `제목: 부가가치세 경정청구 증빙 요청`, '', `부가가치세 경정청구(${ks.join(', ')})에 필요한 자료를 ${back}까지 보내 주십시오${minDue ? `(가장 이른 청구 기한 ${minDue})` : ''}.`, '');
    xs.forEach((x, i) => L.push(`${i + 1}. ${x.docs}`, `   해당 시설: ${x.facs.slice(0, 12).join(', ')}${x.facs.length > 12 ? ` 외 ${x.facs.length - 12}곳` : ''}`, `   쓰는 곳: ${x.why}`, `   ☐ 받음`));
    L.push(''); }
  if (!pl.reqs.length) L.push('요청할 증빙이 없습니다.'); return L.join('\n');
}

function scriptText(D: Data, o: CbIn, pl: Plan): string {
  const P = D.rules.persuade; const later = groups(pl.issues.filter(i => !FIRST(i.grade)));
  const summary = `${pl.span} 신고서 ${pl.nDocs}장에서 과세사업에 쓴 매입세액을 불공제했거나 공통매입세액 계산이 맞지 않아, ${fmt(pl.first)}원의 경정청구를 준비했습니다.`;
  const disclose = later.length ? later.slice(0, 3).map(g => `${facList(g.facs, 3)}은 ${g.why}이라 이번 청구에서 뺐습니다`).join('. ') + '.' : (P?.disclose_none ?? '');
  const L = [`관할 세무서 부가가치세과 사전 상담 대본 (3분) — ${o.org}`, ''];
  for (const s of P?.script ?? []) L.push('- ' + s.replace('{summary}', summary).replace('{disclose}', disclose));
  L.push('', '세무서가 물을 법한 것과 답(금액 큰 쟁점 순)', '');
  const top = pl.qs.filter(q => pl.issues.some(i => i.q.includes(q.id))).slice(0, 5); for (const q of (top.length ? top : pl.qs.slice(0, 5))) L.push(`문: ${q.q}`, `답: ${q.answer}`, '');
  L.push('받은 답 — 따로 적을 것은 세무서가 더 붙이라고 한 서류뿐입니다(있으면 08 처럼 해당 부서에 요청). 제출 방식은 정해 준 대로(말이 없으면 홈택스).');
  return L.join('\n');
}

/** 화면 확인으로 정해진 답(확인 전에는 rules.yml 의 '[확인 후 기재]' 답) */
function confAnswer(o: CbIn, pl: Plan, id: string): string | null { const cf = o.conf ?? {}; const fs = [...new Set(pl.issues.filter(i => FIRST(i.grade) && i.type === 'sports').map(i => i.fac))]; const all = (k: 'seats' | 'lessons' | 'sales', v: string, list: string[]) => list.length > 0 && list.every(f => cf.fac?.[f]?.[k] === v);
  const f2 = [...new Set(pl.issues.filter(i => FIRST(i.grade) && i.grade === 2).map(i => i.fac))];
  if (id === 'Q12' && all('seats', 'no', fs)) return `청구한 체육시설(${fs.join(', ')})에는 관중용 관람석이 없습니다(시설 현황표 붙임).`;
  if (id === 'Q14' && all('lessons', 'no', fs)) return `청구한 체육시설(${fs.join(', ')})에는 구가 직영하는 강좌 수강료 수입이 없고, 사용료는 시설 이용료입니다(수입 구분표 붙임).`;
  if (id === 'Q10' && all('sales', 'yes', f2)) return `청구한 시설(${f2.join(', ')})의 사용료는 그 기간 과세 매출로 신고하였습니다(붙임 01 3-1 업종코드, 세입 실적 대사 붙임).`;
  if (id === 'Q20' && cf.apport === 'supply') return '당초 명세서는 공급가액 비율로 나누었고, 총공급가액을 과세표준과 면세공급가액의 합으로 바로잡아 같은 식으로 다시 계산했습니다(붙임 03 2항·04 2항).';
  return null; }
function answerText(D: Data, pl: Plan, o: CbIn): string {
  const P = D.rules.persuade; const L = [`자료 보완 요청 답변 틀 — 세무서 질문과 가장 가까운 번호를 찾아 답과 붙임을 보냅니다. ${P?.law_note ?? ''}`, ''];
  (P?.steps ?? []).forEach((s, i) => { const qs = (P?.questions ?? []).filter(q => q.step === i + 1); if (!qs.length) return; L.push(`■ ${s}`);
    for (const q of qs) L.push(`${q.id}${pl.qs.includes(q) ? ' ★이번 청구에 해당' : ''} — ${q.q}`, `  답: ${confAnswer(o, pl, q.id) ?? q.answer}`, `  근거: ${q.basis}`, `  붙임: ${q.files || '없음'}${q.need ? ` · 준비할 것: ${q.need}` : ''}${q.fallback ? `\n  못 갖추면: ${q.fallback}` : ''}`, ''); });
  return L.join('\n');
}

function inquiryFile(D: Data, o: CbIn, pl: Plan): string {
  const g4 = groups(pl.issues.filter(i => i.grade === 4)); if (!g4.length) return '';
  const L = [`해석이 필요한 몫 — 질의서 초안 (${o.today}). 갑설·을설은 쟁점을 보이는 두 읽기이며 기관의 입장이 아닙니다. 보내는 길(국세청 서면질의 / 세법해석 사전답변)은 기관이 고릅니다.`, ''];
  for (const g of g4) { const facs = facList(g.facs, 8); let q = /본청·행정/.test(g.why) ? (D.inquiries ?? []).find(x => x.key === 'admin_common') : undefined;
    if (!q) { const t = pl.issues.find(i => g.facs.has(i.fac) && i.type)?.type; q = (D.inquiries ?? []).find(x => x.fac === t); }
    L.push('════════════════════', `쟁점: ${g.why} — ${facs} (${fmt(g.amt)}원)`, '');
    if (q) L.push(inquiryText(D, q, { org: o.org, facilities: facs }));
    else { const qq = (D.rules.persuade?.questions ?? []).filter(x => g.q.includes(x.id));
      L.push('부가가치세 법령해석 질의서 (초안)', '', `질의 기관: ${o.org} (사업자등록번호: ${o.reg || '[          ]'})`, '', '1. 사실관계', `  1) 질의 기관은 ${facs}을(를) 직접 운영하며 사용료를 받는다.`, '  2) [시설 현황 — 관람석 유무·좌석 수, 용도별 면적, 강습 운영 방식 등을 적는다]', '', '2. 질의 내용', ...qq.map((x, i) => `  ${i + 1}) ${x.q}`), '', `3. 관련 법령: ${qq.map(x => x.basis).join(' / ')}`, ''); }
    L.push(''); }
  return L.join('\n');
}

function compareSheet(pl: Plan): Sheet[] {
  if (!pl.g3.length) return [];
  const R: Cell[][] = [['과세기간', '시설', '신고서에 없는 업종', '돌려받을 매입세액(A)', '그 기간 시설 수입 어림(세입예산 ÷ 2)', '매출세액 어림(B = 수입 ÷ 11)', '과소신고·납부지연 가산세 어림(C, 오늘 수정신고·납부)', '함께 낼 때 순액(A − B − C)', '떼어 둘 때']];
  for (const x of pl.g3.sort((a, b) => a.k.localeCompare(b.k))) R.push([pName(x.k), x.fac, x.gap, x.amt, x.rev || null, x.rev ? x.sales : null, x.rev ? x.pen : null, x.net, '이번 청구에서 뺌 — 매출 신고 여부는 그대로 남음']);
  R.push([], ['감면과 예외'], ['- 수정신고 감면율(과소신고 가산세): 법정신고기한 뒤 1개월 안 90% … 1년 6개월~2년 10%(국세기본법 제48조 제2항 제1호). 날이 갈수록 줄어듭니다.'], ['- 세무서가 경정할 것을 미리 알고 낸 수정신고는 감면에서 빠질 수 있습니다(같은 호 단서 — 원문 확인 필요). 경정청구로 세무서가 매출을 보기 전에, 같은 날 또는 먼저 냅니다.'], ['- 수입 어림은 과세기간(6개월) 기준 — 세입예산 연 수입 ÷ 2.'], [], ['읽는 법'], ['- 공제받으려는 시설의 사용료를 과세 매출로 신고하지 않았다면, 세무서는 매입세액 공제만 인정하지 않고 매출 누락도 함께 볼 수 있습니다(부가가치세법 제38조, 국세기본법 제45조의2).'], ['- 함께 내는 안: 매출 수정신고(국세기본법 제45조, 과소신고 가산세 감면 같은 법 제48조 제2항)와 경정청구를 같은 날 냅니다. 사업자에게 빌려주고 세금계산서를 발급하지 않았다면 공급가액의 2% 가산세가 더해집니다(부가가치세법 제60조 제2항 제2호 — 이 표에 넣지 않음).'], ['- 수입 어림은 기관 설정의 세입예산서 연 수입(부가세 포함으로 봄)의 절반입니다. 세입 결산 실적으로 바꾸면 정확해집니다. 수입 자료가 없는 시설은 비어 있습니다.'], ['- 순액이 음수여도 매출 신고 의무는 그대로입니다. 이 표는 어느 쪽이 유리한지를 정하지 않습니다 — 판정은 참고이며 기관의 판단이 아닙니다.']);
  return [{ name: '수정신고 함께내기 비교', rows: R, widths: [14, 30, 18, 16, 18, 16, 22, 18, 40] }];
}

async function legalPdf(D: Data, o: CbIn, pl: Plan): Promise<Blob | null> {
  /* 세무서에 내는 발췌 — 이번에 청구한 쟁점을 받치는 조문·유권해석만(모든 쟁점 표·부인 사례는 내부 13 으로 — 세무법인 역할 시험 2026-11-24) */
  try { const { buildPdf, p } = await import('./pdf');
    const first = pl.issues.filter(i => FIRST(i.grade)); const types = [...new Set(first.map(i => i.type).filter(Boolean) as string[])]; const g1 = first.some(i => i.grade === 1);
    const B = [p('kicker', [`붙임 07 · ${o.org}`, 'kicker']), p('title', ['근거 조문·유권해석 발췌', 'title']), p('note', ['조문은 국가법령정보센터 현행 원문, 유권해석은 번호와 요지(원문은 국세법령정보시스템에서 번호로 찾음).', 'note']),
      p('h3', ['1. 경정청구', 'h3']), p('body', ['국세기본법 제45조의2 제1항 — 과세표준신고서를 법정신고기한까지 제출한 자는 신고한 세액이 세법에 따라 신고하여야 할 세액을 초과하거나 환급세액이 미치지 못할 때 법정신고기한이 지난 후 5년 이내에 경정을 청구할 수 있다.', 'body']),
      p('h3', ['2. 공제하는 매입세액', 'h3']), p('body', ['부가가치세법 제38조 제1항 — 사업자가 자기의 사업을 위하여 사용하였거나 사용할 목적으로 공급받은 재화·용역의 부가가치세액은 매출세액에서 공제한다.', 'body'])];
    if (types.length) { B.push(p('h3', ['3. 지방자치단체가 공급해도 과세되는 사업', 'h3']), p('body', ['부가가치세법 제26조 제1항 제19호 — 국가·지방자치단체가 공급하는 재화·용역은 면세하되, 대통령령으로 정하는 것은 제외한다. 같은 법 시행령 제46조 제3호 — 부동산임대업, 도매 및 소매업, 음식점업·숙박업, 골프장 및 스키장 운영업, 기타 스포츠시설 운영업은 과세한다(제3호 내용은 2021년 이후 판에서 같음).', 'body']));
      for (const tp of types) { const fr = D.facilities.find(x => x.key === tp); if (!fr) continue; B.push(p('body', [`${fr.name} — ${fr.cond ?? fr.note}`, 'body']));
        for (const id of fr.rulings ?? []) { const r = (D.rulings ?? []).find(x => x.id === id); if (!r || r.verify) continue; if (/1330|209|306/.test(r.no)) continue;   /* 면세 쪽 예외(관람석 경기장·체육공원)는 제출 발췌에서 뺌 — 청구 시설이 해당하지 않음을 청구인이 확인(내부 08·13) */
          B.push(p('note', [`${r.kind} ${r.no} ${r.title}: ${r.gist}`, 'note'])); } } }
    if (g1) B.push(p('h3', [`${types.length ? 4 : 3}. 공통매입세액 안분`, 'h3']), p('body', ['부가가치세법 제40조 — 과세사업과 면세사업등에 공통으로 사용된 매입세액은 실지귀속에 따라 계산하되, 실지귀속을 구분할 수 없으면 총공급가액에 대한 면세공급가액의 비율 등으로 안분한다. 같은 법 시행령 제81조 제1항 — 공통매입세액 × (면세공급가액 ÷ 총공급가액). 제82조 — 예정신고 때 안분한 것은 확정신고 때 과세기간 전체로 정산한다.', 'body']));
    return await buildPdf(B, `근거 발췌 · ${o.org}`, { foot: '' }); } catch { return null; }
}

async function summaryPdf(D: Data, o: CbIn, pl: Plan): Promise<Blob | null> {
  try { const { buildPdf, p, table } = await import('./pdf'); const S = summaryRows(D, o, pl);
    const B = [p('title', [S.head[0], 'title']), p('note', [S.head[1], 'note'])];
    for (const x of S.parts) { B.push(p('h3', [x.h, 'h3'])); for (const l of x.lines ?? []) B.push(p('body', [l, 'body'])); if (x.table) B.push(table(x.table.map(r => r.map(v => typeof v === 'number' ? fmt(v) : String(v ?? ''))), { head: true })); }
    return await buildPdf(B, `검토 요약서 · ${o.org}`, { landscape: true, foot: '' }); } catch { return null; }
}

const csv = (R: Cell[][]) => '﻿' + R.map(r => r.map(v => { const s = String(v ?? ''); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; }).join(',')).join('\r\n');

/** 세무서 제출 묶음 — 00 ~ 12(앞 번호 = 붙임 번호). candRows: 매입 목록이 없을 때 계약 업체 목록(추가분 합계표 밑자료 대신) */
export async function persuadeFiles(D: Data, o: CbIn, candRows: (string | number)[][] = []): Promise<PFile[]> {
  const pl = persuadePlan(D, o); const out: PFile[] = []; const inner: PFile[] = []; const F = (n: string) => FILES.find(f => f.n === n)!.f;
  out.push({ name: F('00'), data: todoText(D, o, pl) });
  { const b = await summaryPdf(D, o, pl); if (b) out.push({ name: F('01'), data: await bin(b) }); }
  try { const b = pl.M.size ? await claimFormPdf(pl.M, o.org, o.reg, true) : null; if (b) out.push({ name: F('02'), data: await bin(b) }); } catch { /* 서식 PDF 를 못 만들어도 나머지 */ }
  try { const b = pl.M.size ? await reasonDocPdf(pl.M, o.org, o.reg, true) : null; if (b) out.push({ name: F('03'), data: await bin(b) }); } catch { /* */ }
  { const S = summaryRows(D, o, pl); const rows: Cell[][] = [[S.head[0]], [S.head[1]]]; const st: Record<number, number> = { 0: 2 }; for (const x of S.parts) { st[rows.length] = 3; rows.push([x.h]); for (const l of x.lines ?? []) { st[rows.length] = 4; rows.push([l]); } for (const r of x.table ?? []) rows.push(r); }
    const iss: Cell[][] = [['과세기간·구분', '시설', '등급', '등급 이름', '금액', '이번 청구', '이유', '추정 여부', '조사관 질문 번호', '청구 기한']]; for (const i of pl.issues) iss.push([i.name, i.fac, i.grade, GNAME[i.grade], i.amt, FIRST(i.grade) ? '넣음' : '뺌(나중 묶음)', i.why, i.est ? '계약금액 추정 — 세금계산서 확인 뒤' : '', i.q.join(' '), `${i.cdue} (D-${i.left})`]);
    const x = caseBook(D, o, FIRST, [{ name: '검토 요약', rows, style: st, freeze: false, widths: [120] }], true); if (x) out.push({ name: F('04'), data: await bin(x) });
    const w = caseBook(D, o, undefined, [{ name: '쟁점 등급', rows: iss, widths: [18, 30, 6, 12, 14, 14, 60, 22, 16, 18] }]); if (w) inner.push({ name: F('13'), data: await bin(w) }); }
  { const keep = new Set(pl.issues.filter(i => FIRST(i.grade)).map(i => `${i.k}|${i.fac}`)); const half = (d: string) => `${Number(d.slice(0, 4))}-${Number(d.slice(5, 7)) <= 6 ? 1 : 2}`;
    /* 과세기간마다 매입 목록 세액 합 ↔ 당초 신고서 (16) — 같으면 '이미 신고에 들어 있음'(합계표 추가 제출 대상 아님 — 세무법인·조사관 역할 시험 2026-11-24: 추가분이라 하면 이중 공제로 읽힘) */
    const listBy = new Map<string, number>(); for (const r of o.rows) listBy.set(half(r.d), (listBy.get(half(r.d)) ?? 0) + r.tax);
    const f16 = (k: string) => (o.docs ?? []).filter(d => `${d.year}-${d.half}` === k).reduce((n, d) => n + (d.cells[16]?.tax ?? 0), 0);
    const inFiled = (k: string) => (listBy.get(k) ?? 0) <= f16(k) + 1000 ? '들어 있음 — 합계표 추가 제출 대상 아님' : '신고에 없던 세금계산서가 섞여 있음 — 그 건만 매입처별 세금계산서합계표 추가분으로(시행령 제74조 제2호)';
    const m = new Map<string, { sup: string; sreg: string; n: number; amt: number; tax: number; claim: number }>();
    for (const r of o.rows) { if (!r.claim) continue; const k = half(r.d); if (!keep.has(`${k}|${r.fac}`)) continue; const key = `${k}|${r.sreg}`; const x = m.get(key) ?? { sup: r.sup, sreg: r.sreg, n: 0, amt: 0, tax: 0, claim: 0 }; x.n++; x.amt += r.amt; x.tax += r.tax; x.claim += r.claim; m.set(key, x); }
    if (m.size) out.push({ name: F('05'), data: csv([['과세기간', '공급자 상호', '공급자 사업자등록번호', '매수', '공급가액', '세액', '공제로 옮기는 세액', '당초 신고(16)에', '공급받는자 등록번호'], ...[...m.entries()].sort().map(([k, x]) => [pName(k.split('|')[0]), x.sup, bizno(x.sreg), x.n, x.amt, x.tax, x.claim, inFiled(k.split('|')[0]), o.reg])]) });
    else if (candRows.length > 1) out.push({ name: F('05').replace('.csv', '(계약_업체_추정).csv'), data: csv(candRows) });
    if (m.size) { const R: Cell[][] = [['과세기간', '날짜', '공급자', '공급자 등록번호', '공급받는자 등록번호', '품목·사업명', '공급가액', '세액', '시설', '그 시설로 본 이유', '공제로 옮기는 세액', '근거 조문']];
      for (const r of o.rows) { if (!r.claim) continue; const k = half(r.d); if (!keep.has(`${k}|${r.fac}`)) continue; R.push([pName(k), r.d, r.sup, bizno(r.sreg), o.reg, r.desc, r.amt, r.tax, r.fac, `${r.fac} 이름이 품목·계약명에 있음 — 사용료를 과세 매출로 신고하는 시설`, r.claim, r.basis.filter(b => !(b.law === 'rule' && b.art === '제35조') && (typeof r.share === 'number' && r.share < 1 || !((b.law === 'act' && b.art === '제40조') || (b.law === 'decree' && b.art === '제81조')))).map(lawText).join(' · ')]);   /* 전액 실지귀속 행에 안분 조문을 달지 않음(조사관 역할 시험 3회차) */ }
      out.push({ name: F('06'), data: await bin(xlsxBlob([{ name: '세금계산서별 시설 귀속', rows: R, widths: [12, 11, 24, 14, 14, 40, 14, 12, 26, 44, 14, 30] }])) }); } }
  { const b = await legalPdf(D, o, pl); if (b) out.push({ name: F('07'), data: await bin(b) }); }
  out.push({ name: F('08'), data: requestText(D, o, pl) }, { name: F('09'), data: scriptText(D, o, pl) }, { name: F('10'), data: answerText(D, pl, o) });
  { const t = inquiryFile(D, o, pl); if (t) out.push({ name: F('11'), data: t }); }
  { const s = compareSheet(pl); if (s.length) out.push({ name: F('12'), data: await bin(xlsxBlob(s)) }); }
  return [...out, ...inner];
}
