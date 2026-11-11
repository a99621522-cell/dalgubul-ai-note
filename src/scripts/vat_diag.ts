/** 지난 신고 진단 — 과세기간마다 '무엇이 잘못·누락됐나 → 어느 칸을 어떻게 고치나 → 고친 신고서 → 효과(돌려받는 돈)'(운영자 2026-11-05
 *  '부가가치세 신고할 때 무엇이 잘못되었거나 누락되어 어떻게 고치면 되고 고친 내용과 효과를 나타나게 해 … 이 앱은 돈을 돌려받는 게 목적').
 *  새 판정 규칙 없음 — vat_review.ts 의 건별 판정(judge)·신고서 값(vat_unlock filedSummary)을 과세기간마다 신고서 칸으로 대조만 한다.
 *  금액 나눔: 덜 공제받은 몫 G = 있어야 할 공제 세액 − 신고 (18). 그중 '신고서에 아예 없던 세금계산서' 몫 = 빠진 세액 × (공제 대상 비율), 나머지는 '불공제로 넣은 것'을
 *  과세 시설 전용·공통(안분) 공제 대상 세액 비율로 나눈다(건별로 무엇이 (17)에 들어갔는지는 신고서에 없으므로 나눔은 어림 — 화면에 적음). 판정은 참고이며 기관의 판단이 아니다. */
import { esc, fmt, lawLink, lawText, uniq, type Basis, type Data, type AuditCase } from './vat_rules';
import { p as hp, table as htable, type Block as HBlock } from './hwpx';

export type DiagIn = {
  k: string; name: string; filed: 'filed' | 'excluded' | 'none' | 'unknown'; due: string; claim: string; days: number; future: boolean;
  deduct: number | null; nondeduct: number | null; total16: number | null; er: number | null;
  doc: { hasNd: boolean; hasCommon: boolean; ndReasons: Record<number, number>; files: string[] } | null;
  recv: number; should: number;
  ok: { tax: number; claim: number; n: number; facs: { name: string; tax: number; n: number; type?: string }[] };
  split: { tax: number; claim: number; n: number };
  undecided: { tax: number; n: number };
  other: { tax: number; n: number; fixTax: number };
  gate?: { inv: number; card: number; c1012: number | null; c15: number | null; c16: number | null; c17: number | null; c18: number | null; ndSum: number | null };
};
export type Finding = { key: string; title: string; what: string; how: string; effect: number | null; effectNote: string; basis: Basis[] };
export type FixRow = { cell: string; label: string; before: number | null; after: number | null; src?: string };
export type GateRow = { name: string; list: number | null; filed: number | null; state: 'ok' | 'more' | 'less' | 'na'; note: string };
export type Diag = { corrected?: CorrDoc[]; gate?: GateRow[]; prov?: boolean; upto?: number; types: string[]; k: string; name: string; state: 'claim' | 'late' | 'unknown' | 'ok' | 'over' | 'expired'; gain: number; cond: number; findings: Finding[]; fixed: FixRow[]; claim: string; days: number; due: string };

const B = (law: string, art: string): Basis => ({ law, art });
const ND_NAME: Record<number, string> = { 1: '① 필요적 기재사항 누락 등', 2: '② 사업과 직접 관련 없는 지출', 3: '③ 비영업용 승용자동차 구입·유지·임차', 4: '④ 기업업무추진비 등', 5: '⑤ 면세사업등 관련', 6: '⑥ 토지의 자본적 지출 관련', 7: '⑦ 사업자등록 전 매입세액', 8: '⑧ 금·구리 스크랩 거래계좌 미사용' };
const TOL = 1000;   // 원 단위 끝수·카드 소액 차이는 '빠짐'으로 보지 않는다

/* 대조 관문 — 올린 목록과 신고서 칸이 맞는지(차이 1,000원 이하는 같음). 신고 쪽이 크면 목록이 덜 올라온 것이라 그 기간 금액은 잠정 */
export function gateRows(x: DiagIn): GateRow[] {
  const g = x.gate; if (!g) return [];
  const row = (name: string, list: number | null, filed: number | null, more: string, less: string): GateRow => { if (list === null || filed === null) return { name, list, filed, state: 'na', note: filed === null ? '신고서 칸을 못 읽음' : '목록 없음' }; const d = list - filed; return { name, list, filed, state: Math.abs(d) <= TOL ? 'ok' : d > 0 ? 'more' : 'less', note: Math.abs(d) <= TOL ? '같음' : d > 0 ? `${more} ${fmt(d)}원` : `${less} ${fmt(-d)}원` }; };
  const out = [row('세금계산서 — 매입 목록 ↔ 신고서 (10)+(12)', g.inv || null, g.c1012, '목록이 많음 — 신고에서 빠진 세금계산서 후보', '신고가 많음 — 목록이 덜 올라옴(다른 기간·종이 세금계산서)')];
  if (g.card || g.c15) out.push(row('사업용 카드 — 카드 목록 ↔ (15) 그 밖의 공제매입세액', g.card || null, g.c15, '목록이 많음 — 카드 공제 빠짐 후보', '신고가 많음 — 카드 목록이 덜 올라옴(현금영수증 등)'));
  if (g.c16 !== null && g.c17 !== null && g.c18 !== null) { const d = g.c16 - g.c17 - g.c18; out.push({ name: '칸 계산 — (16) − (17) = (18)', list: g.c16 - g.c17, filed: g.c18, state: Math.abs(d) <= 10 ? 'ok' : 'less', note: Math.abs(d) <= 10 ? '맞음' : '신고서 읽기 확인' }); }
  if (g.ndSum !== null && g.c17 !== null) { const d = g.ndSum - g.c17; out.push({ name: '불공제 명세 합 ↔ (17)', list: g.ndSum, filed: g.c17, state: Math.abs(d) <= TOL ? 'ok' : d > 0 ? 'more' : 'less', note: Math.abs(d) <= TOL ? '같음' : '명세서 확인(사유 칸 읽기·합계)' }); }
  return out;
}
export function diagnose(x: DiagIn): Diag {
  const gate = gateRows(x); const short = gate.some(g => g.state === 'less' && g.name.startsWith('세금계산서'));
  const F: Finding[] = short ? [{ key: 'list-short', title: '매입 목록이 신고보다 적음 — 금액은 잠정', what: `이 과세기간에 올린 매입 세금계산서 목록 세액이 신고서 (10)+(12)보다 적습니다. 목록이 덜 올라왔거나(다른 기간·일부 사업장), 종이 세금계산서·예정신고 누락분이 신고에 들어 있을 수 있습니다.`, how: '홈택스 「전자세금계산서 목록조회(매입)」에서 이 과세기간(1~6월 또는 7~12월) 전체를 다시 받아 놓으세요. 종이 세금계산서는 매입처별 세금계산서합계표(종이분)로 확인합니다.', effect: null, effectNote: '목록을 다 올리면 금액 확정', basis: [] }] : [];
  const base = { gate, prov: short, types: [...new Set(x.ok.facs.map(f => f.type).filter(Boolean))] as string[], k: x.k, name: x.name, claim: x.claim, days: x.days, due: x.due };
  const facTxt = x.ok.facs.slice(0, 4).map(f => `「${f.name}」 ${fmt(f.tax)}원(${f.n}건)`).join(', ') + (x.ok.facs.length > 4 ? ` 외 ${x.ok.facs.length - 4}곳` : '');
  const otherF = (): Finding | null => x.other.tax > 0 ? { key: 'other', title: '우리 명의가 아닌 세금계산서', what: `공급받는 자가 우리 등록번호가 아닌 세금계산서 ${x.other.n}건, 세액 ${fmt(x.other.tax)}원 — 이대로는 공제할 수 없습니다.`, how: x.other.fixTax > 0 ? `공급자에게 공급받는 자를 우리 등록번호로 고친 수정세금계산서를 받아(확정신고기한 다음 날부터 1년 안) 경정청구에 넣습니다. 기한 안 세액 ${fmt(x.other.fixTax)}원.` : '수정세금계산서 발급 기한(확정신고기한 다음 날부터 1년)이 지났습니다 — 착오 정정이 아니면 공제가 어렵습니다.', effect: x.other.fixTax || null, effectNote: x.other.fixTax ? '수정세금계산서를 받으면(조건부)' : '', basis: [B('act', '제39조'), B('decree', '제70조')] } : null;
  const undF = (): Finding | null => x.undecided.tax > 0 ? { key: 'undecided', title: '아직 판단하지 못한 세액', what: `시설·용도가 안 정해졌거나(시설 유형이 운영 방식에 달림 포함) 면세비율이 없어 세지 못한 세액 ${fmt(x.undecided.tax)}원(${x.undecided.n}건).`, how: '③에서 공급자의 시설·용도를 고르고, ②에 그 기간 면세비율(공제받지못할매입세액명세서)을 넣으면 효과가 계산됩니다.', effect: null, effectNote: '정하면 늘 수 있음', basis: [B('act', '제40조'), B('decree', '제81조')] } : null;
  const push = (f: Finding | null) => { if (f) F.push(f); };
  if (x.days < 0) { push(undF()); return { ...base, state: 'expired', gain: 0, cond: 0, findings: F, fixed: [] }; }
  if (x.filed === 'none' || x.filed === 'excluded') {
    const none = x.filed === 'none';
    F.push({ key: none ? 'nofile' : 'excluded', title: none ? '이 과세기간 신고가 없음' : '이 매입 목록이 신고에 들어가지 않음', what: none ? `이 과세기간의 부가가치세 신고가 없습니다. 매입 목록의 공제 대상 매입세액 ${fmt(x.should)}원을 한 번도 공제받지 않았습니다.` : `신고는 했지만 이 매입 목록(세액 ${fmt(x.recv)}원)은 넣지 않았다고 표시했습니다. 그중 공제 대상 ${fmt(x.should)}원을 공제받지 않았습니다.`,
      how: none ? '기한후신고서를 냅니다 — 매입세액 (10)·(11)에 목록을 넣고, 과세 시설 매출(사용료 등)이 있으면 매출세액 (1)과 무신고·납부지연 가산세도 함께 적습니다.' : '경정청구서 (10) 일반매입(고정자산이면 (11))에 목록의 공급가액·세액을 더하고, 매입처별 세금계산서합계표에 공급자를 추가합니다(묶음 03_공급자별_합계).',
      effect: x.should, effectNote: none ? '매출세액·가산세가 있으면 그만큼 줄어듦' : '', basis: none ? [B('basic', '제45조의3'), B('act', '제38조')] : [B('basic', '제45조의2'), B('act', '제38조'), B('act', '제54조')] });
    push(otherF()); push(undF());
    const fixed: FixRow[] = none ? [{ cell: '(10)~(16)', label: '매입세액 합계', before: 0, after: x.recv }, { cell: '(17)', label: '공제받지 못할 매입세액', before: 0, after: x.recv - x.should }, { cell: '(18)', label: '공제 매입세액', before: 0, after: x.should }]
      : [{ cell: '(16)', label: '매입세액 합계', before: x.total16, after: x.total16 === null ? null : x.total16 + x.recv }, { cell: '(17)', label: '공제받지 못할 매입세액', before: x.nondeduct, after: x.nondeduct === null ? null : x.nondeduct + x.recv - x.should }, { cell: '(18)', label: '공제 매입세액', before: x.deduct, after: x.deduct === null ? null : x.deduct + x.should }];
    return { ...base, state: none ? 'late' : 'claim', gain: x.should, cond: x.other.fixTax, findings: F, fixed };
  }
  if (x.filed === 'unknown' || x.deduct === null) {
    F.push({ key: 'nofiled', title: '신고 값이 없어 대조하지 못함', what: `이 과세기간 신고서의 공제 매입세액 (18)을 아직 모릅니다. 매입 목록으로 본 공제 대상은 ${fmt(x.should)}원입니다.`, how: '②에 그 기간 신고서(홈택스 「신고내역 조회」의 신고서 PDF)를 올리면 무엇이 빠졌는지·얼마인지가 나옵니다.', effect: null, effectNote: `상한 ${fmt(x.should)}원(목록이 신고에 하나도 안 들어갔다면)`, basis: [B('basic', '제45조의2')] });
    push(otherF()); push(undF());
    return { ...base, state: 'unknown', gain: 0, cond: x.other.fixTax, findings: F, fixed: [] };
  }
  const D = x.deduct, N = x.nondeduct; const R = x.total16 ?? (N !== null ? D + N : null);
  const G = x.should - D; const gain = Math.max(0, G);
  const miss = R !== null && x.recv - R > TOL ? x.recv - R : 0; const ratio = x.recv > 0 ? x.should / x.recv : 0;
  const g1 = miss ? Math.min(gain, Math.round(miss * ratio)) : 0; const g2 = gain - g1;
  if (miss) F.push({ key: 'missing', title: '세금계산서가 신고에서 빠짐', what: `홈택스 매입 목록의 세액 합은 ${fmt(x.recv)}원인데 신고서 매입세액 합계 (16)은 ${fmt(R!)}원입니다 — ${fmt(miss)}원어치 세금계산서가 신고(매입처별 세금계산서합계표)에 들어가지 않았습니다.`,
    how: '경정청구서 (10) 일반매입(시설 공사·장비면 (11) 고정자산)에 빠진 공급가액·세액을 더하고, 매입처별 세금계산서합계표에 빠진 공급자를 추가합니다(묶음 03_공급자별_합계). 빠진 것 중 과세 시설 몫은 (18) 공제로, 면세·행정 몫은 (17) 불공제로 나눕니다.',
    effect: g1 || null, effectNote: g1 ? '빠진 세액 가운데 공제 대상 몫(목록 전체의 공제 대상 비율로 어림)' : '빠진 것이 모두 불공제 대상이면 환급은 없고 합계표만 바로잡음', basis: [B('act', '제38조'), B('act', '제54조'), B('basic', '제45조의2')] });
  if (g2 > 0) {
    const okC = x.ok.claim, spC = x.split.claim; const den = okC + spC || 1; const gOk = Math.round(g2 * okC / den), gSp = g2 - gOk;
    const nd5 = x.doc?.ndReasons[5]; const ndList = x.doc ? Object.entries(x.doc.ndReasons).filter(([, v]) => v > 0).map(([n, v]) => `${ND_NAME[Number(n)] ?? n} ${fmt(v)}원`).join(', ') : '';
    if (gOk > 0) F.push({ key: 'taxable-as-exempt', title: '과세 시설 지출을 공제하지 않음', what: `과세 시설 지출 ${facTxt || `${fmt(x.ok.tax)}원`}의 매입세액은 전액 공제 대상인데, 신고 때 공제받은 매입세액 (18)은 ${fmt(D)}원뿐입니다. ${N !== null ? `공제받지 못할 매입세액 (17) ${fmt(N)}원${nd5 ? ` — 그중 '⑤ 면세사업등 관련' ${fmt(nd5)}원` : ''}에 들어간 것으로 보입니다.` : ''}${ndList && !nd5 ? ` (불공제 명세: ${ndList})` : ''}`,
      how: `경정청구서에서 이 시설 지출을 (17) 불공제에서 빼 (18) 공제로 옮깁니다 — 공제받지못할매입세액명세서의 '⑤ 면세사업등 관련' 금액을 그만큼 줄이고, 시설이 과세라는 근거(사용료 수입을 과세 매출로 신고한 사실·조례)와 지출이 그 시설 것이라는 증빙(계약서·검수조서·사업명)을 붙입니다.`,
      effect: gOk, effectNote: '덜 공제받은 몫을 과세 시설 전용·공통 공제 대상 비율로 나눈 어림', basis: [B('act', '제38조'), B('act', '제39조'), B('basic', '제45조의2')] });
    if (gSp > 0) F.push({ key: 'no-apportion', title: '같이 쓴 지출을 안분하지 않음', what: `여러 시설·행정이 같이 쓴 지출 ${fmt(x.split.tax)}원(${x.split.n}건) 가운데 과세 몫 ${fmt(x.split.claim)}원(면세비율 ${x.er ?? '?'}%)을 공제하지 않은 것으로 보입니다.${x.doc && !x.doc.hasCommon ? ' 신고서에 공통매입세액 안분 계산(공제받지못할매입세액명세서 3번)이 없어 전액 불공제로 처리된 것으로 보입니다.' : ''}`,
      how: '공제받지못할매입세액명세서에 공통매입세액 안분 계산(공통매입세액 × 면세공급가액 ÷ 총공급가액 = 불공제)을 넣고, 나머지(과세 몫)를 (18) 공제로 옮깁니다. 확정신고면 6개월 전체 비율로 정산합니다.',
      effect: gSp, effectNote: '덜 공제받은 몫을 과세 시설 전용·공통 공제 대상 비율로 나눈 어림', basis: [B('act', '제40조'), B('decree', '제81조'), B('decree', '제82조')] });
  }
  if (G < -TOL) F.push({ key: 'over', title: '목록보다 더 공제받음', what: `신고 때 공제받은 매입세액 (18) ${fmt(D)}원이 매입 목록·판정으로 본 공제 대상 ${fmt(x.should)}원보다 ${fmt(-G)}원 많습니다.`, how: '카드·종이 세금계산서·현금영수증 분이 신고에 들어 있으면 정상입니다(③에 그 목록도 올리면 맞춰집니다). 그것이 아니면 면세·행정 지출을 공제한 것일 수 있어 수정신고를 검토합니다(가산세 감면은 빨리 낼수록 큼).', effect: null, effectNote: '돌려받을 돈 없음', basis: [B('basic', '제45조'), B('basic', '제48조')] });
  push(otherF()); push(undF());
  const after16 = R !== null ? R + miss : null; const after18 = D + gain;
  const docTxt = x.doc?.files.length ? `신고서(${x.doc.files.join(', ')})` : '② 표에 적은 신고 값';
  const fixed: FixRow[] = [{ cell: '(16)', label: '매입세액 합계', before: R, after: after16, src: miss ? `${docTxt} + 신고에서 빠진 목록 세액 ${fmt(miss)}원(매입 목록 대조)` : docTxt }, { cell: '(17)', label: '공제받지 못할 매입세액', before: N, after: after16 !== null ? after16 - after18 : null, src: '고친 (16) − 고친 (18)' }, { cell: '(18)', label: '공제 매입세액', before: D, after: after18, src: `당초 + 돌려받을 세액 ${fmt(gain)}원 = 매입 목록 건별 판정(과세 시설 전용 전액·같이 쓴 지출은 면세비율만큼 뺀 몫, 법 제38조·제40조) − 신고 (18)` }];
  return { ...base, state: gain > 0 ? 'claim' : G < -TOL ? 'over' : 'ok', gain, cond: x.other.fixTax, findings: F, fixed };
}

/* 실제 사례(data/vat/cases.yml mistakes) — 같은 잘못을 겪은 지자체의 경정청구·권익위·감사 지적. 이 기간 시설 유형과 겹치는 사례 먼저, 그다음 최근 순 */
const MKEY: Record<string, string> = { excluded: 'missing', nofile: 'nofile', missing: 'missing', 'taxable-as-exempt': 'taxable-as-exempt', 'no-apportion': 'no-apportion', cashout: 'cashout' };
export function casesFor(D: Data, key: string, types: string[] = [], n = 3): AuditCase[] {
  const mk = MKEY[key]; if (!mk) return [];
  return (D.cases ?? []).filter(c => c.mistakes?.includes(mk)).map(c => ({ c, o: c.keys.filter(k => types.includes(k)).length })).sort((a, b) => b.o - a.o || String(b.c.date).localeCompare(String(a.c.date))).slice(0, n).map(x => x.c);
}
export function casesHtml(L: AuditCase[], head = '실제 사례'): string {
  if (!L.length) return '';
  return `<div class="rf-cases"><p><span class="rf-k">${esc(head)}</span></p><ul>${L.map(c => `<li><details><summary><b>${esc(c.org)}</b> <span class="meta">${esc(String(c.date))} · ${esc(c.kind)}</span>${c.amount ? ` — ${esc(c.amount)}` : ''}${c.verify ? ' <span class="vbadge">원문 확인 필요</span>' : ''}<br><span class="note">${esc(c.title)}</span></summary><p class="note">${esc(c.facts)}</p><p class="note">출처: ${c.url ? `<a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.src)}</a>` : esc(c.src)}</p></details></li>`).join('')}</ul></div>`;
}
/* 자료를 올리기 전 — 다른 지자체가 실제로 틀린 것(사례에서 모음): 우리도 확인할 곳 */
export function commonMistakesHtml(D: Data): string {
  const G: { key: string; title: string; check: string }[] = [
    { key: 'taxable-as-exempt', title: '과세 시설 지출을 공제하지 않음', check: '체육센터·문화센터·임대 건물·휴양림·캠핑장처럼 사용료를 받는 시설의 신축·수선·운영 지출을 면세·행정으로 보고 불공제했는지' },
    { key: 'no-apportion', title: '같이 쓴 지출을 안분하지 않음', check: '임대·과세 공간과 행정 공간이 섞인 건물의 건축비·관리비를 임대(예정)면적 등으로 나누지 않고 전액 불공제했는지' },
    { key: 'missing', title: '세금계산서가 신고에서 빠짐', check: '신축 공사처럼 사업 부서가 받은 세금계산서가 회계 부서에 넘어가지 않아 매입처별 세금계산서합계표에서 빠졌는지' },
    { key: 'nofile', title: '과세 매출을 신고하지 않음', check: '공유재산 사용료·대부료에 받은 부가가치세를 예수금으로만 두고 신고하지 않았는지(가산세)' },
    { key: 'cashout', title: '돌려받은 돈·납부잔액을 세입 처리하지 않음', check: '매입세액 공제로 덜 낸 납부잔액·환급금을 세입세출외현금에 그대로 두었는지' }];
  return `<p class="rf-dg-sum">아직 대조할 자료가 없습니다. 먼저 <b>다른 지자체가 실제로 틀린 곳</b>을 보고, 우리 기관도 같은 곳을 확인하세요 — ②에 지난 신고서, ③에 매입 목록을 올리면 과세기간마다 무엇이 틀렸는지·얼마인지가 나옵니다.</p>
    ${G.map(g => { const L = casesFor(D, g.key, [], 6); return L.length ? `<details class="rf-dg"><summary><b>${esc(g.title)}</b> <span class="note">— 사례 ${L.length}건</span></summary><p><span class="rf-k">확인할 곳</span> ${esc(g.check)}</p>${casesHtml(L)}</details>` : ''; }).join('')}`;
}
/** 경정청구 사유 한 줄(항목 이름을 이어 붙임) */
export const reasonLine = (d: Diag) => { const t = d.findings.filter(f => f.effect && !['other'].includes(f.key)).map(f => f.title.replace(/^.*? — /, '')); return t.length ? `${t.join(', ')} — 과세사업 관련 매입세액 공제 누락(부가가치세법 제38조)` : '과세사업 관련 매입세액 공제 누락(부가가치세법 제38조)'; };
const STATE_TXT: Record<Diag['state'], string> = { claim: '경정청구로 돌려받을 돈 있음', late: '기한후신고로 돌려받을 돈 있음', unknown: '신고서를 올리면 진단', ok: '덜 공제받은 몫 없음', over: '목록보다 더 공제받음', expired: '경정청구 기한 지남' };
const law = (D: Data, bs: Basis[]) => uniq(bs).map(b => lawLink(D, b)).join(' · ');
export function diagHtml(D: Data, L: Diag[]): string {
  const onlyNo = (d: Diag) => !d.gain && d.findings.length > 0 && d.findings.every(f => f.key === 'nofile'); const miss = L.filter(onlyNo);
  const show = L.filter(d => (d.findings.length || d.gain) && !onlyNo(d));
  const missHtml = miss.length ? `<p class="note rf-miss"><b>신고서를 올리지 않은 과세기간 ${miss.length}개:</b> ${miss.sort((a, b) => a.k.localeCompare(b.k)).map(d => esc(d.name)).join(' · ')} — 홈택스 → 신고/납부 → 세금신고 → 신고내역 조회에서 이 기간 신고서·명세서를 PDF 로 저장해 같은 칸에 놓으면 함께 계산합니다(신고하지 않은 기간이면 기한후신고 대상).</p>` : '';
  if (!show.length) return missHtml;
  const gain = show.filter(d => d.state !== 'expired').reduce((s, d) => s + d.gain, 0), cond = show.filter(d => d.state !== 'expired').reduce((s, d) => s + d.cond, 0), upto = show.reduce((s, d) => s + (d.upto ?? 0), 0);
  const nF = show.reduce((s, d) => s + d.findings.filter(f => !['undecided', 'nofiled', 'arith', 'nd-missing'].includes(f.key)).length, 0);
  const card = (d: Diag, i: number) => `<details class="rf-dg" id="rf-dg-${d.k}" ${i === 0 && (d.gain > 0 || d.upto) ? 'open' : ''}><summary><b>${esc(d.name)}</b>${d.prov ? ' <span class="vbadge warn">잠정</span>' : ''} — ${esc(d.state === 'unknown' && d.upto ? '신고서로 찾은 확인할 금액' : STATE_TXT[d.state])}${d.gain > 0 ? ` <b class="rf-dg-amt">${fmt(d.gain)}원</b>` : ''}${d.upto ? ` <span class="note">(확인하면 최대 +${fmt(d.upto)}원)</span>` : ''}${d.cond ? ` <span class="note">(+조건부 ${fmt(d.cond)}원)</span>` : ''} <span class="meta">${d.days >= 0 ? `경정청구 기한 ${esc(d.claim)} · D-${d.days}` : '기한 지남'}</span></summary>
    ${d.gate?.length ? `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table rf-gate" data-stack="off"><caption>대조 — 올린 목록과 신고서 칸이 맞나</caption><thead><tr><th scope="col">대조</th><th scope="col">목록·계산</th><th scope="col">신고서</th><th scope="col">결과</th></tr></thead><tbody>${d.gate.map(g => `<tr class="g-${g.state}"><th scope="row">${esc(g.name)}</th><td>${g.list === null ? '—' : fmt(g.list)}</td><td>${g.filed === null ? '—' : fmt(g.filed)}</td><td>${g.state === 'ok' ? '✓ ' : g.state === 'na' ? '' : '△ '}${esc(g.note)}</td></tr>`).join('')}</tbody></table></div>` : ''}
    ${!d.corrected?.length && d.fixed.length && d.fixed.some(r => r.before !== r.after) ? `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table" data-stack="off"><caption>홈택스 경정청구 입력값 — 신고서 칸 순서(당초 → 경정 후)</caption><thead><tr><th scope="col">칸</th><th scope="col">항목</th><th scope="col">당초 신고</th><th scope="col">경정 후</th><th scope="col">차이</th><th scope="col">출처</th></tr></thead><tbody>${d.fixed.map(r => `<tr><th scope="row">${esc(r.cell)}</th><td>${esc(r.label)}</td><td>${r.before === null ? '<span class="note">—</span>' : fmt(r.before)}</td><td>${r.after === null ? '<span class="note">—</span>' : fmt(r.after)}</td><td>${r.before !== null && r.after !== null && r.after !== r.before ? `${r.after > r.before ? '+' : ''}${fmt(r.after - r.before)}` : ''}</td><td class="note">${esc(r.src ?? '')}</td></tr>`).join('')}<tr class="rf-dg-eff"><th scope="row">효과</th><td colspan="5">납부할 세액이 <b>${fmt(d.gain)}원</b> 줄어 그만큼 돌려받습니다(환급 때 국세환급가산금이 붙습니다 — 국세기본법 제52조)</td></tr></tbody></table></div><p class="note rf-dg-how"><b>홈택스에서:</b> 신고/납부 → 세금신고 → 부가가치세 → 경정청구 → ${esc(d.name)} 확정신고 불러오기 → 위 칸을 '경정 후' 값으로 고침 → 사유: '${esc(reasonLine(d))}' → 붙임: 매입처별 세금계산서합계표 추가분(공급자별)·공제받지못할매입세액명세서(고친 안분)·청구 사유서·근거 조문·진단표(묶음 zip 의 03·06·12 파일) → 환급받을 계좌. 세무서는 2개월 안에 결과를 알립니다(국세기본법 제45조의2 제3항).</p>` : ''}
    ${d.corrected?.length ? correctedHtml(d.corrected) : ''}
    <ol class="rf-dg-list">${d.findings.map(f => `<li><p class="rf-dg-t"><b>${esc(f.title)}</b>${f.effect ? ` → <b>${fmt(f.effect)}원</b>` : ''}${f.effectNote ? ` <span class="note">(${esc(f.effectNote)})</span>` : ''}</p><div class="rf-why"><p><span class="rf-k">무엇이</span> ${esc(f.what)}</p><p><span class="rf-k">고치기</span> ${esc(f.how)}</p>${f.basis.length ? `<p><span class="rf-k">근거</span> ${law(D, f.basis)}</p>` : ''}${casesHtml(casesFor(D, f.key, d.types), '같은 잘못의 실제 사례')}</div></li>`).join('')}</ol>${d.gain > 0 ? casesHtml(casesFor(D, 'cashout', [], 2), '돌려받은 뒤 — 환급금은 바로 세입 처리(감사 지적 사례)') : ''}</details>`;
  return `${missHtml}<p class="rf-dg-sum">지난 신고 ${show.length}개 과세기간을 대조했습니다 — 잘못·누락 <b>${nF}</b>건, 고치면 돌려받는 돈 <b>${fmt(gain)}원</b>${cond ? ` (+ 수정세금계산서를 받으면 ${fmt(cond)}원)` : ''}${upto ? ` · 확인하면 최대 <b>+${fmt(upto)}원</b>(신고서의 불공제 사유 가운데 공제될 수 있는 것)` : ''}.</p>
    ${show.sort((a, b) => b.gain - a.gain || (b.upto ?? 0) - (a.upto ?? 0) || a.k.localeCompare(b.k)).map((d, i) => card(d, i)).join('')}
    <p class="note">'무엇이'의 금액 나눔(빠진 세금계산서 / 불공제로 넣은 것 / 안분 안 함)은 어림입니다 — 신고서에는 건별로 무엇을 (17)에 넣었는지가 없어 매입 목록의 공제 대상 비율로 나눴습니다. 합계(덜 공제받은 몫 = 있어야 할 공제 세액 − 신고 (18))는 정확히 그 차이입니다. 판정은 참고이며 기관의 판단이 아닙니다.</p>`;
}
export function diagCsv(L: Diag[], D?: Data): string[][] {
  const rows: string[][] = [['과세기간', '상태', '돌려받을 돈', '조건부', '경정청구 기한', '항목', '무엇이 잘못·누락', '고치는 법', '효과(원)', '효과 설명', '근거', '같은 잘못의 실제 사례']];
  for (const d of L) for (const f of d.findings) rows.push([d.name, STATE_TXT[d.state], String(d.gain), String(d.cond), d.claim, f.title, f.what, f.how, f.effect == null ? '' : String(f.effect), f.effectNote, f.basis.map(lawText).join(' · '), D ? casesFor(D, f.key, d.types).map(c => `${c.org}(${c.date}, ${c.kind}${c.amount ? `, ${c.amount}` : ''}) ${c.title}`).join(' / ') : '']);
  rows.push([]); rows.push(['과세기간', '칸', '항목', '당초 신고', '경정 후', '차이', '출처', '경정청구 사유']);
  for (const d of L) for (const r of d.fixed) rows.push([d.name, r.cell, r.label, r.before == null ? '' : String(r.before), r.after == null ? '' : String(r.after), r.before != null && r.after != null ? String(r.after - r.before) : '', r.src ?? '', reasonLine(d)]);
  return rows;
}

/* ── 신고서만으로 진단(운영자 2026-11-05 '과거 국세청에 신고한 자료를 올리면 바로 계산되고 이유가 나와야') ──
 *  매입 목록 없이 신고서·공제받지못할매입세액명세서(제22호) 숫자만으로 다시 계산한다.
 *  확정 금액(sure): ① 안분 생략 기준(공통매입세액 5만 원 미만 / 면세비율 5% 미만이고 500만 원 미만 — 시행령 제81조 제2항)인데 안분해 불공제 ② 안분 식(공통매입세액 × 면세공급가액 ÷ 총공급가액)과 다른 불공제
 *  ③ 총공급가액이 신고서의 과세 공급가액((1)~(6))보다 작아 면세비율이 부풀려짐 — 셋을 함께 반영한 '바른 불공제'와의 차이만큼.
 *  확인할 금액(upto): ⑤ 면세사업등 관련(과세 시설 지출이 섞였는지) · ① 필요적 기재사항 누락 등 · ⑦ 사업자등록 전 — 최대 금액과 확인할 곳. */
type Cellx = { n?: number | null; amt: number | null; tax: number | null };
export type FiledDocLite = { year: number; half: 1 | 2; kind: string; file: string; reg?: string; cells: Record<number, Cellx>; pen?: number; due?: number; nd: { reasons: Record<number, Cellx>; common: { sup: number; tax: number; total: number; exempt: number; nd: number } | null; settle?: { tax: number; ratio: number; ndAll: number; prev: number; add: number } | null; recalc?: { tax: number; rate: number; delta: number; add: number } | null } | null; base?: { label: string; code: string; amt: number }[] };
export type FixPart = { doc: FiledDocLite; delta: number; sec: '안분' | '정산' | '정산(새로 넣음)'; rows: { label: string; before: number | null; after: number | null }[] };
export type FiledCheck = { k: string; findings: Finding[]; sure: number; upto: number; docs: string[]; n17: number | null; n18: number | null; n16: number | null; n1012: number | null; fixes?: FixPart[] };
export function filedChecks(D: Data, docs: FiledDocLite[], taxableFacs: string[]): Map<string, FiledCheck> {
  const out = new Map<string, FiledCheck>(); const skip = D.rules.common?.skip ?? [];
  const r5 = skip.find(s => s.key === 'ratio5') as { ratio_lt?: number; amount_lt?: number } | undefined, sm = skip.find(s => s.key === 'small') as { amount_lt?: number } | undefined;
  const RLT = r5?.ratio_lt ?? 0.05, RAMT = r5?.amount_lt ?? 5000000, SMALL = sm?.amount_lt ?? 50000;
  const perDoc = new Map<FiledDocLite, { right: number; diff: number }>();
  for (const d of docs) {
    const k = `${d.year}-${d.half}`; const o: FiledCheck = out.get(k) ?? { k, findings: [], sure: 0, upto: 0, docs: [], n17: null, n18: null, n16: null, n1012: null }; o.docs.push(`${d.kind} 신고서(${d.file})`); const tag = `${d.kind}신고`;
    const c16 = d.cells[16]?.tax ?? null, c17 = d.cells[17]?.tax ?? null, c18 = d.cells[18]?.tax ?? null; if (c17 !== null) o.n17 = (o.n17 ?? 0) + c17; if (c18 !== null) o.n18 = (o.n18 ?? 0) + c18; if (c16 !== null) o.n16 = (o.n16 ?? 0) + c16; if (d.cells[10]?.tax != null || d.cells[12]?.tax != null) o.n1012 = (o.n1012 ?? 0) + (d.cells[10]?.tax ?? 0) + (d.cells[12]?.tax ?? 0) + (d.cells[13]?.tax ?? 0);
    if (c16 !== null && c17 !== null && c18 !== null && Math.abs(c16 - c17 - c18) > 10) o.findings.push({ key: 'arith', title: `${tag} — 칸 계산이 맞지 않음`, what: `(16) ${fmt(c16)} − (17) ${fmt(c17)} = ${fmt(c16 - c17)} 인데 (18)은 ${fmt(c18)}원으로 읽혔습니다.`, how: '신고서 원본의 (16)(17)(18)을 확인하세요 — 읽기가 틀렸으면 ② 표에서 고쳐 넣습니다.', effect: null, effectNote: '확인', basis: [] });
    const cm = d.nd?.common; const salesT = [1, 2, 3, 4, 5, 6].reduce((s, n) => s + (d.cells[n]?.amt ?? 0), 0);
    if (cm && cm.tax > 0) {
      const er = cm.total > 0 ? cm.exempt / cm.total : 0; const why: string[] = []; let right: number; const totalOk = Math.max(cm.total, cm.exempt + salesT);
      if (cm.tax < SMALL) { right = 0; why.push(`공통매입세액이 ${fmt(cm.tax)}원으로 ${fmt(SMALL)}원 미만이면 안분하지 않고 전액 공제합니다(시행령 제81조 제2항 제2호)`); }
      else if (cm.exempt / totalOk < RLT && cm.tax < RAMT) { right = 0; why.push(`면세공급가액 비율이 ${(cm.exempt / totalOk * 100).toFixed(2)}%로 5% 미만이고 공통매입세액이 ${fmt(RAMT)}원 미만이면 안분하지 않고 전액 공제합니다(시행령 제81조 제2항 제1호)`); }
      else { right = Math.floor(cm.tax * cm.exempt / totalOk);
        if (totalOk > cm.total + 1000) why.push(`안분에 쓴 총공급가액 ${fmt(cm.total)}원이 신고서의 과세 공급가액 ${fmt(salesT)}원 + 면세공급가액 ${fmt(cm.exempt)}원 = ${fmt(cm.exempt + salesT)}원보다 작아 면세비율이 ${(er * 100).toFixed(2)}%로 부풀려졌습니다(바른 비율 ${(cm.exempt / totalOk * 100).toFixed(2)}%)`);
        if (cm.nd - Math.floor(cm.tax * er) > 1000) why.push(`명세서의 불공제 ${fmt(cm.nd)}원이 안분 식(${fmt(cm.tax)} × ${fmt(cm.exempt)} ÷ ${fmt(cm.total)} = ${fmt(Math.floor(cm.tax * er))}원)보다 큽니다`); }
      const diff = cm.nd - right; perDoc.set(d, { right, diff: diff > 1000 && why.length ? diff : 0 });
      if (diff > 1000 && why.length) { (o.fixes ??= []).push({ doc: d, delta: diff, sec: '안분', rows: [{ label: '⑫ 총공급가액 등', before: cm.total, after: totalOk }, { label: '⑬ 면세공급가액 등', before: cm.exempt, after: cm.exempt }, { label: '⑭ 불공제 매입세액', before: cm.nd, after: right }] }); o.sure += diff; o.findings.push({ key: 'apportion-calc', title: `${tag} — 공통매입세액을 더 불공제함`, what: `${why.join('. ')}. 바른 불공제는 ${fmt(right)}원인데 ${fmt(cm.nd)}원을 불공제했습니다.`, how: `경정청구서의 공제받지못할매입세액명세서 '공통매입세액 안분 계산'을 고쳐 불공제를 ${fmt(cm.nd)} → ${fmt(right)}원으로, 신고서 (17)을 ${fmt(diff)}원 줄이고 (18)을 그만큼 늘립니다.`, effect: diff, effectNote: '신고서 숫자로 다시 계산한 금액', basis: [B('act', '제40조'), B('decree', '제81조'), B('basic', '제45조의2')] }); }
    }
    const R = d.nd?.reasons ?? {}; const t = (n: number) => R[n]?.tax ?? 0;
    if (t(5) > 0) { o.upto += t(5); o.findings.push({ key: 'taxable-as-exempt', title: `${tag} — '⑤ 면세사업등 관련' 불공제 ${fmt(t(5))}원 확인`, what: `면세사업 관련으로 ${R[5]?.n ? `세금계산서 ${R[5].n}장, ` : ''}세액 ${fmt(t(5))}원을 불공제했습니다. 이 가운데 사용료를 받는 과세 시설(${taxableFacs.length ? taxableFacs.slice(0, 5).join('·') + (taxableFacs.length > 5 ? ' 등' : '') : '체육센터·임대 건물·휴양림 등'})의 신축·수선·운영 지출이 있으면 그만큼 공제 대상입니다 — 다른 지자체 환급의 대부분이 이 경우입니다.`, how: `홈택스에서 이 과세기간 매입 세금계산서 목록(엑셀)을 받아 ③에 올리면 어느 공급자·시설의 세액인지 가려 확정 금액이 나옵니다. 과세 시설 지출이면 (17)에서 (18)로 옮겨 경정청구합니다.`, effect: t(5), effectNote: '최대 — 과세 시설 지출만큼', basis: [B('act', '제38조'), B('act', '제39조'), B('basic', '제45조의2')] }); }
    if (t(1) > 0) { o.upto += t(1); o.findings.push({ key: 'missing', title: `${tag} — '① 필요적 기재사항 누락 등' 불공제 ${fmt(t(1))}원 확인`, what: `세금계산서를 늦게 받았거나 기재사항이 빠져 ${fmt(t(1))}원을 불공제했습니다. 확정신고기한 다음 날부터 1년 안에 받은 것(시행령 제75조 제7호)이나 수정세금계산서로 고친 것은 공제됩니다.`, how: '그 세금계산서의 작성일자·발급일자를 보고, 기한 안이거나 수정세금계산서를 받으면 경정청구에 넣습니다.', effect: t(1), effectNote: '최대 — 요건을 갖춘 것만', basis: [B('act', '제39조'), B('decree', '제75조'), B('decree', '제70조')] }); }
    if (t(7) > 0) { o.upto += t(7); o.findings.push({ key: 'prereg', title: `${tag} — '⑦ 사업자등록 전 매입세액' 불공제 ${fmt(t(7))}원 확인`, what: `사업자등록 전 매입세액 ${fmt(t(7))}원을 불공제했습니다. 공급시기가 속한 과세기간이 끝난 뒤 20일 안에 등록을 신청했으면 그 기간 매입세액은 공제됩니다.`, how: '시설(사업장)의 사업자등록 신청일과 세금계산서 작성일을 견줘, 요건 안이면 경정청구에 넣습니다.', effect: t(7), effectNote: '최대 — 등록 신청일 요건 안의 것만', basis: [B('act', '제39조')] }); }
    if ((d.cells[1]?.tax ?? 0) + (d.cells[3]?.tax ?? 0) + (d.cells[4]?.tax ?? 0) > 0 && (c18 ?? 0) === 0) o.findings.push({ key: 'taxable-as-exempt', title: `${tag} — 과세 매출은 있는데 공제받은 매입세액이 0`, what: `과세 매출세액을 신고했는데 공제받은 매입세액 (18)이 0원입니다. 과세 시설의 운영·수선 지출 세금계산서가 하나도 신고에 들어가지 않았을 수 있습니다.`, how: '그 과세 시설의 지출 세금계산서(홈택스 매입 목록)를 ③에 올리면 공제 대상이 계산됩니다.', effect: null, effectNote: '목록을 올리면 계산', basis: [B('act', '제38조')] });
    if ((c17 ?? 0) > 0 && !d.nd) o.findings.push({ key: 'nd-missing', title: `${tag} — 불공제 명세서가 없음`, what: `(17) 공제받지 못할 매입세액 ${fmt(c17!)}원의 사유(면세사업 관련·안분 등)가 보이지 않습니다.`, how: '신고서와 함께 낸 「공제받지못할매입세액명세서」 PDF 도 ②에 올리면 사유별로 다시 계산합니다.', effect: null, effectNote: '명세서를 올리면 계산', basis: [B('decree', '제81조')] });
    /* 매출 쪽 — 과세표준 명세에 면세 시설 수입으로 보이는 업종이 있으면(낸 매출세액 최대, 그 시설 매입세액 공제분은 빠짐 — 순효과) */
    for (const b of d.base ?? []) { const t = SALES_KW.find(x => x.re.test(b.label)); const fr = t && D.facilities.find(x => x.key === t.type); if (!t || fr?.status !== 'exempt') continue; const tax = Math.floor(b.amt / 10); o.upto += tax;
      o.findings.push({ key: 'sales-exempt', title: `${tag} — 면세 수입을 과세 매출로 신고했을 수 있음: ${b.label}`, what: `과세표준 명세에 '${b.label}' ${fmt(b.amt)}원이 과세 매출로 들어 있습니다. ${fr.name}은 지자체가 직접 운영하면 면세(부가가치세법 제26조 제1항 제19호)입니다. 그렇다면 낸 매출세액 ${fmt(tax)}원은 낼 필요가 없던 세금입니다.`, how: `그 수입이 직영 ${t.what} 수입인지 세입 결의로 확인 → 맞으면 경정청구서의 과세표준을 ${fmt(b.amt)}원 줄이고 면세 수입금액으로 옮깁니다. 다만 그 시설 지출 매입세액을 공제받아 왔다면 그만큼은 불공제로 바뀝니다(순효과로 봄).`, effect: tax, effectNote: '최대 — 직영 면세 시설 수입으로 확인되는 만큼(그 시설 매입세액 공제분은 빠짐)', basis: [{ law: 'act', art: '제26조' }, { law: 'basic', art: '제45조의2' }] }); }
    out.set(k, o);
  }
  /* 예정 → 확정 정산(시행령 제82조): 예정 때 안분한 공통매입세액을 확정 때 6개월 면세비율로 다시 셈 */
  const byK = new Map<string, FiledDocLite[]>(); for (const d of docs) { const k = `${d.year}-${d.half}`; (byK.get(k) ?? byK.set(k, []).get(k)!).push(d); }
  const ratioOf = new Map<string, number>();
  for (const [k, L] of byK) { const o = out.get(k)!; const R = [...L].reverse(); const f = R.find(d => d.kind === '확정' && (d.nd?.settle || d.nd?.common)) ?? R.find(d => d.kind === '확정'); const e = R.find(d => d.kind === '예정' && d.nd?.common && d.nd.common.tax > 0 && (!f?.reg || !d.reg || d.reg === f.reg));
    const st = f?.nd?.settle, ec = e?.nd?.common, fc = f?.nd?.common;
    if (st && st.tax > 0) { ratioOf.set(k, st.ratio);
      const right17 = Math.floor(st.tax * st.ratio); const prevRight = ec ? ec.nd - (perDoc.get(e!)?.diff ?? 0) : st.prev; const right19 = right17 - prevRight; const d19 = st.add - right19;
      if (d19 > 1000) { (o.fixes ??= []).push({ doc: f!, delta: d19, sec: '정산', rows: [{ label: '⑮ 총공통매입세액', before: st.tax, after: st.tax }, { label: '⑯ 면세사업등 확정비율(%)', before: Math.round(st.ratio * 10000) / 100, after: Math.round(st.ratio * 10000) / 100 }, { label: '⑰ 불공제 매입세액 총액', before: st.ndAll, after: right17 }, { label: '⑱ 기불공제 매입세액', before: st.prev, after: prevRight }, { label: '⑲ 가산 불공제 매입세액', before: st.add, after: right19 }] }); o.sure += d19; o.findings.push({ key: 'settle', title: '확정신고 — 공통매입세액 정산을 더 불공제함', what: `정산 내역: 총공통매입세액 ${fmt(st.tax)}원 × 확정 면세비율 ${(st.ratio * 100).toFixed(2)}% = ${fmt(right17)}원에서 예정 때 불공제한 ${fmt(prevRight)}원을 빼면 이번에 더할 불공제는 ${fmt(right19)}원인데 ${fmt(st.add)}원을 불공제했습니다${ec && Math.abs(st.prev - ec.nd) > 1000 ? ` (명세서의 기불공제 ${fmt(st.prev)}원이 예정 신고서의 불공제 ${fmt(ec.nd)}원과 다릅니다)` : ''}.`, how: `경정청구서의 공제받지못할매입세액명세서 '공통매입세액의 정산 내역'을 고쳐 ⑲를 ${fmt(st.add)} → ${fmt(right19)}원으로, 신고서 (17)을 ${fmt(d19)}원 줄입니다.`, effect: d19, effectNote: '신고서 숫자로 다시 계산한 금액', basis: [{ law: 'decree', art: '제82조' }, { law: 'basic', art: '제45조의2' }] }); } }
    else if (ec && f) {
      if (fc && fc.total + ec.total > 0) { const r6 = (ec.exempt + fc.exempt) / Math.max(ec.total + fc.total, 1); ratioOf.set(k, r6); const right = Math.floor((ec.tax + fc.tax) * r6); const filedNd = ec.nd + fc.nd - (perDoc.get(e!)?.diff ?? 0) - (perDoc.get(f)?.diff ?? 0); const dd = filedNd - right;
        if (dd > 1000) { (o.fixes ??= []).push({ doc: f, delta: dd, sec: '정산(새로 넣음)', rows: [{ label: '⑮ 총공통매입세액', before: null, after: ec.tax + fc.tax }, { label: '⑯ 면세사업등 확정비율(%)', before: null, after: Math.round(r6 * 10000) / 100 }, { label: '⑰ 불공제 매입세액 총액', before: null, after: right }, { label: '⑱ 기불공제 매입세액', before: null, after: ec.nd - (perDoc.get(e!)?.diff ?? 0) }, { label: '⑲ 가산 불공제 매입세액', before: fc.nd - (perDoc.get(f)?.diff ?? 0), after: right - (ec.nd - (perDoc.get(e!)?.diff ?? 0)) }] }); o.sure += dd; o.findings.push({ key: 'settle', title: '확정신고 — 예정분 공통매입세액을 6개월 비율로 정산하지 않음', what: `예정(${fmt(ec.tax)}원)·확정(${fmt(fc.tax)}원) 공통매입세액을 6개월 면세비율 ${(r6 * 100).toFixed(2)}%(면세 ${fmt(ec.exempt + fc.exempt)} ÷ 총 ${fmt(ec.total + fc.total)})로 다시 셈하면 불공제는 ${fmt(right)}원인데, 예정·확정 신고에서 ${fmt(filedNd)}원을 불공제했습니다.`, how: `경정청구서의 공제받지못할매입세액명세서에 '공통매입세액의 정산 내역'을 넣어 확정분 불공제를 ${fmt(dd)}원 줄이고 신고서 (17)도 같이 줄입니다.`, effect: dd, effectNote: '신고서 숫자로 다시 계산한 금액', basis: [{ law: 'decree', art: '제82조' }, { law: 'basic', art: '제45조의2' }] }); } }
      else o.findings.push({ key: 'settle-check', title: '확정신고 — 공통매입세액 정산 내역이 보이지 않음', what: `예정신고 때 공통매입세액 ${fmt(ec.tax)}원 가운데 ${fmt(ec.nd)}원을 불공제했는데, 확정신고 명세서에 정산 내역이 없습니다.`, how: '확정 신고서와 함께 낸 공제받지못할매입세액명세서 PDF 를 올리면 6개월 비율로 다시 계산합니다.', effect: null, effectNote: '명세서를 올리면 계산', basis: [{ law: 'decree', art: '제82조' }] }); }
    else if (fc && fc.total > 0) ratioOf.set(k, fc.exempt / fc.total);
  }
  /* 감가상각자산 재계산(시행령 제83조): 면세비율이 직전 과세기간보다 5%p 넘게 바뀌었는데 재계산 내역이 없으면 */
  const ks = [...ratioOf.keys()].sort();
  for (let i = 1; i < ks.length; i++) { const [k0, k1] = [ks[i - 1], ks[i]]; const [y0, h0] = k0.split('-').map(Number), [y1, h1] = k1.split('-').map(Number); if (y1 * 2 + h1 - (y0 * 2 + h0) !== 1) continue;
    const r0 = ratioOf.get(k0)!, r1 = ratioOf.get(k1)!; if (Math.abs(r1 - r0) < 0.05) continue; const f = [...(byK.get(k1) ?? [])].reverse().find(d => d.kind === '확정'); if (f?.nd?.recalc) continue;
    const down = r1 < r0; out.get(k1)!.findings.push({ key: 'recalc', title: `확정신고 — 면세비율이 ${(r0 * 100).toFixed(1)}% → ${(r1 * 100).toFixed(1)}%로 바뀌었는데 재계산 내역이 없음`, what: `과세·면세에 같이 쓰는 건물·설비(감가상각자산)를 산 뒤 면세비율이 5%p 넘게 바뀌면 남은 기간 몫을 다시 셉니다(시행령 제83조). 이번에는 면세비율이 ${down ? '줄어 공제가 늘어나는' : '늘어 공제가 줄어드는'} 쪽입니다.`, how: down ? '지난 과세기간에 산 공통 건물·설비(취득가·매입세액·취득 시기)를 자산대장에서 찾아 재계산 내역(⑳×㉑×㉒)을 넣어 경정청구합니다 — 건물 체감률 5%, 그 밖 25%.' : '공제가 줄어드는 쪽이라 돌려받을 돈은 아니지만, 다음 신고에서 빠뜨리면 가산세가 붙을 수 있어 자산대장을 확인합니다.', effect: null, effectNote: down ? '자산대장(취득가·시기)을 올리면 계산' : '확인(돌려받을 돈 아님)', basis: [{ law: 'decree', art: '제83조' }] }); }
  return out;
}
/** 과세표준 명세 업종 글자 → 면세 시설 유형(지자체 직영이면 면세인 것만) */
const SALES_KW: { re: RegExp; type: string; what: string }[] = [
  { re: /주차/, type: 'parking', what: '공영주차장' }, { re: /농기계|농업용\s*기계|농업기계/, type: 'equip_rent', what: '농기계 임대' },
  { re: /체육공원|공원\s*운영/, type: 'park_sports', what: '체육공원 운동시설' }, { re: /종량제|폐기물/, type: 'waste_bag', what: '종량제 봉투·폐기물 처리' }, { re: /상수도|하수도|수도/, type: 'water', what: '상·하수도' }];
/** 대상 기간 가운데 신고서가 없는 과세기간 — docs 가 하나라도 있을 때만 */
export function missingPeriods(docs: FiledDocLite[], win: string[]): Map<string, FiledCheck> {
  const out = new Map<string, FiledCheck>(); if (!docs.length) return out; const has = new Set(docs.map(d => `${d.year}-${d.half}`));
  for (const k of win) { if (has.has(k)) continue; const [y, h] = k.split('-');
    out.set(k, { k, findings: [{ key: 'nofile', title: '이 과세기간 신고서를 올리지 않음', what: `${y}년 제${h}기 신고서가 없습니다. 이 기간도 경정청구가 됩니다.`, how: `홈택스 → 신고/납부 → 세금신고 → 신고내역 조회 → ${y}년 제${h}기 부가가치세 신고서(예정·확정)와 공제받지못할매입세액명세서를 PDF 로 저장해 같은 칸에 놓으세요. 실제로 신고하지 않은 기간이면 기한후신고 대상입니다(국세기본법 제45조의3).`, effect: null, effectNote: '신고서를 올리면 계산', basis: [{ law: 'basic', art: '제45조의2' }, { law: 'basic', art: '제45조의3' }] }], sure: 0, upto: 0, docs: [], n17: null, n18: null, n16: null, n1012: null }); }
  return out;
}
/* 신고서 진단을 행 진단에 합친다 — 목록으로 진단한 기간은 신고서 확정 금액이 이미 그 차이 안에 들어 있어 더하지 않고 '목록 대조에 포함'으로 둔다 */
export function mergeFiled(rowDiags: Diag[], fc: Map<string, FiledCheck>, meta: (k: string) => { name: string; claim: string; days: number; due: string }): { diags: Diag[]; fsure: number } {
  const by = new Map(rowDiags.map(d => [d.k, d])); let fsure = 0;
  for (const [k, c] of fc) {
    const d = by.get(k);
    const corr = correctedFilings(new Map([[k, c]])).get(k);
    if (d) { if (corr) d.corrected = corr; for (const f of c.findings) d.findings.push(f.key === 'apportion-calc' || f.effectNote.startsWith('최대') ? { ...f, effectNote: `${f.effectNote} — 매입 목록 대조 금액에 이미 들어 있음` } : f); continue; }
    const m = meta(k); if (m.days < 0) continue; fsure += c.sure;
    const gate: GateRow[] = [{ name: '세금계산서 — 매입 목록 ↔ 신고서 (10)+(12)', list: null, filed: c.n1012, state: 'na', note: '이 기간 매입 목록이 없음 — 홈택스 매입 목록을 올리면 대조하고 빠진 것을 찾습니다' }];
    if (c.n16 !== null && c.n17 !== null && c.n18 !== null) { const dd = c.n16 - c.n17 - c.n18; gate.push({ name: '칸 계산 — (16) − (17) = (18)', list: c.n16 - c.n17, filed: c.n18, state: Math.abs(dd) <= 10 ? 'ok' : 'less', note: Math.abs(dd) <= 10 ? '맞음' : '신고서 읽기 확인' }); }
    by.set(k, { ...(corr ? { corrected: corr } : {}), gate, types: [], k, name: m.name, claim: m.claim, days: m.days, due: m.due, state: c.sure > 0 ? 'claim' : c.findings.length ? 'unknown' : 'ok', gain: c.sure, cond: 0, findings: c.findings, fixed: c.sure > 0 ? [{ cell: '(17)', label: '공제받지 못할 매입세액', before: c.n17, after: c.n17 === null ? null : c.n17 - c.sure, src: `${c.docs.join(', ')} — 공통매입세액 안분을 신고서 숫자로 다시 계산(시행령 제81조)` }, { cell: '(18)', label: '공제 매입세액', before: c.n18, after: c.n18 === null ? null : c.n18 + c.sure, src: '당초 + 줄어든 불공제' }] : [], upto: c.upto } as Diag);
  }
  return { diags: [...by.values()], fsure };
}

/* ── 환급 계산서(운영자 2026-11-05 '과거 부가가치 신고세액 자료만 올리면 무엇을 어떤 이유로 어떻게 하면 얼마나 환급받는지로') ──
 *  진단(diags)의 항목을 한 표로: 과세기간·기한 | 무엇이 잘못됐나 | 왜(이유·근거 조문) | 어떻게 하면(홈택스 경정청구 칸·붙임) | 돌려받을 돈.
 *  돌려받을 돈은 세 칸으로만 — 확정(신고서·목록 숫자로 다시 계산), 확인하면 최대(불공제 사유의 세액 — 과세 시설 지출만큼만 돌아옴), 계약 어림(그 기간 과세 시설 나라장터 계약 세액 어림과 견준 값, 회색 참고).
 *  합계: 매입 목록을 올린 기간은 그 기간 진단의 gain(항목별 나눔은 어림), 신고서만 있는 기간은 신고서로 다시 계산한 금액. 기한이 지난 기간은 뺌. 새 계산 규칙 없음. */
/* ── 쉬운 말(운영자 2026-11-05 '신고하는 공무원은 세무나 회계 전문가가 아니야') ──
 *  화면 첫 줄은 이 말로, 조문·서식 용어는 '검토자용 자세히'에 접는다. 뜻은 각 Finding 의 what/how 그대로 — 새 판정 없음. */
export const PLAIN: Record<string, { t: string; todo: string }> = {
  'apportion-calc': { t: '함께 쓴 물건·공사의 부가세를 나누는 계산을 틀려, 돌려받을 수 있는 부가세를 덜 받았어요', todo: '아래 「고친 신고서」 값을 홈택스 경정청구 화면에 그대로 옮겨 적으면 됩니다. 다른 자료는 필요 없어요.' },
  'settle': { t: '반년 끝(확정신고)에 다시 맞추는 계산을 틀려, 부가세를 덜 받았어요', todo: '「고친 신고서」 값을 홈택스 경정청구 화면에 옮겨 적으면 됩니다. 다른 자료는 필요 없어요.' },
  'settle-check': { t: '분기 신고 때 나눈 부가세를 반년 끝에 다시 맞췄는지 보이지 않아요', todo: '그 기간 확정신고 때 함께 낸 「공제받지 못할 매입세액 명세서」 PDF 를 홈택스에서 받아 같은 칸에 놓아 주세요.' },
  'taxable-as-exempt': { t: '돈을 받는 시설(체육관·주차장·임대 등)에 쓴 비용의 부가세를 돌려받지 않은 것으로 처리했을 수 있어요', todo: '그 기간 홈택스 매입 세금계산서 목록(엑셀)을 받아 놓으면 어느 것이 돌려받을 수 있는지 점검기가 골라 줍니다.' },
  'missing': { t: '늦게 받았거나 빈칸이 있던 세금계산서라서 부가세를 돌려받지 않았어요 — 기준 안이면 돌려받을 수 있어요', todo: '그 세금계산서를 받은 날짜를 확인해 주세요(공급한 때부터 1년 안이면 대부분 됩니다).' },
  'prereg': { t: '사업자등록 전에 쓴 비용이라 부가세를 돌려받지 않았어요 — 등록 신청 날짜에 따라 돌려받을 수 있어요', todo: '그 시설(사업장)의 사업자등록 신청일을 확인해 주세요.' },
  'sales-exempt': { t: '세금을 안 내도 되는 수입(우리 기관이 직접 운영하는 주차장 등)에 세금을 냈을 수 있어요', todo: '그 수입이 우리 기관이 직접 운영하는 시설 수입인지 세입 담당에게 확인해 주세요. 맞으면 낸 세금을 돌려받습니다.' },
  'recalc': { t: '함께 쓰는 건물·설비의 쓰임 비율이 크게 바뀌었는데 다시 계산하지 않았어요', todo: '그 건물·설비를 산 때와 값(자산대장)을 확인해 주세요. 비율이 줄었으면 돌려받을 돈이 생깁니다.' },
  'nofile': { t: '아직 올리지 않은 기간의 신고서가 있어요', todo: '홈택스에서 그 기간 신고서 PDF 를 받아 같은 칸에 놓아 주세요.' },
  'no-apportion': { t: '함께 쓴 비용의 부가세를 나누지 않고 모두 돌려받지 않은 것으로 처리했어요', todo: '「고친 신고서」 값을 홈택스 경정청구 화면에 옮겨 적으면 됩니다.' },
  'nofiled': { t: '이 기간은 신고를 하지 않은 것으로 보여요 — 늦게라도 신고하면 돌려받을 수 있어요', todo: '실제로 신고하지 않았는지 확인해 주세요. 맞으면 기한후신고를 합니다.' },
  'list-short': { t: '신고서에 넣은 세금계산서보다 올린 목록이 적어요 — 목록을 더 받아야 해요', todo: '그 기간 매입 세금계산서 목록을 다시 받아 놓아 주세요.' },
};
const plain = (f: Finding) => PLAIN[f.key] ?? { t: f.title, todo: f.how };
export type CalcRow = { k: string; name: string; claim: string; days: number; f: Finding; kind: 'sure' | 'upto' | 'inlist' | 'none'; est: number | null };
export function refundCalc(L: Diag[], estBy?: Map<string, number>) {
  const rows: CalcRow[] = []; let sure = 0, upto = 0, est = 0; const miss: string[] = [];
  for (const d of L) { if (d.state === 'expired' || d.days < 0) continue; const list = d.types.length > 0; sure += d.gain; let up5 = 0;
    for (const f of d.findings) { if (f.key === 'nofile') { miss.push(d.name); continue; } const inl = /이미 들어 있음/.test(f.effectNote); const kind: CalcRow['kind'] = inl ? 'inlist' : f.effect == null ? 'none' : f.effectNote.startsWith('최대') ? 'upto' : 'sure';
      let e: number | null = null; if (kind === 'upto') { upto += f.effect!; if (f.key === 'taxable-as-exempt' && estBy?.has(d.k)) { e = Math.min(f.effect!, Math.max(0, (estBy.get(d.k) ?? 0) - up5)); up5 += e; est += e; } }
      if (kind === 'sure' && list) { /* 목록 대조 기간의 항목별 금액은 어림 — 합계는 gain */ }
      rows.push({ k: d.k, name: d.name, claim: d.claim, days: d.days, f, kind, est: e }); } }
  const ord = { sure: 0, upto: 1, none: 2, inlist: 3 } as const;
  rows.sort((a, b) => ord[a.kind] - ord[b.kind] || (b.f.effect ?? 0) - (a.f.effect ?? 0) || a.days - b.days);
  if (miss.length) { const first = L.filter(d => miss.includes(d.name)).sort((a, b) => a.days - b.days)[0]; rows.push({ k: 'nofile', name: `${miss.length}개 과세기간`, claim: first?.claim ?? '', days: first?.days ?? 0, kind: 'none', est: null, f: { key: 'nofile', title: '신고서를 올리지 않은 과세기간', what: `${miss.sort().join(' · ')} — 이 기간들도 경정청구가 됩니다.`, how: '홈택스 → 신고/납부 → 세금신고 → 신고내역 조회에서 이 기간 신고서·공제받지못할매입세액명세서를 PDF 로 저장해 같은 칸에 놓으세요. 신고하지 않은 기간이면 기한후신고 대상입니다.', effect: null, effectNote: '신고서를 올리면 계산', basis: [{ law: 'basic', art: '제45조의2' }, { law: 'basic', art: '제45조의3' }] } }); }
  return { rows, sure, upto, est };
}
export function refundCalcHtml(D: Data, L: Diag[], estBy?: Map<string, number>, win?: string): string {
  const R = refundCalc(L, estBy); const ex = L.filter(d => d.state === 'expired' || d.days < 0); if (!R.rows.length && !ex.length) return '';
  const money = (r: CalcRow) => r.kind === 'sure' ? `<b>${fmt(r.f.effect!)}원</b><br><span class="meta">바로 돌려받을 돈</span>`
    : r.kind === 'upto' ? `최대 <b>${fmt(r.f.effect!)}원</b><br><span class="meta">확인하면 더 받을 수 있어요</span>${r.est != null ? `<br><span class="meta rf-est">계약으로 짐작하면 약 ${fmt(r.est)}원(참고)</span>` : ''}`
    : r.kind === 'inlist' ? `<span class="meta">${esc(r.f.effectNote)}</span>` : `<span class="meta">${esc(r.f.effectNote)}</span>`;
  const dd = (r: CalcRow) => `${esc(r.name)}<br><span class="meta">경정청구 ${esc(r.claim)}까지 ${r.days <= 90 ? '⚠ ' : ''}D-${r.days}</span>`;
  return `<section class="rf-calc" aria-labelledby="rf-calc-h"><div class="rf-h"><h2 id="rf-calc-h">돌려받을 돈 — 무엇이 문제이고, 무엇을 하면, 얼마를 받나</h2></div>
    <p class="note">판정은 참고이며 기관의 판단이 아닙니다. 올린 신고서(와 매입 목록)의 숫자로 다시 계산했습니다.</p>
    ${win ? `<p class="rf-win"><b>대상 기간: ${esc(win)}</b> <span class="meta">— 경정청구가 되는 과세기간(법정신고기한 + 5년, 국세기본법 제45조의2). 이 밖의 자료는 계산에서 뺍니다.</span></p>` : ''}
    ${ex.length ? `<p class="note">경정청구 기한이 지난 과세기간 ${ex.length}개(${ex.map(d => esc(d.name)).join(' · ')})는 돌려받을 수 없어 계산에서 뺐습니다.</p>` : ''}
    <div class="rf-calc-sum"><div><span class="meta">바로 돌려받을 돈</span><b id="rf-calc-sure">${fmt(R.sure)}원</b><span class="meta">신고서 숫자로 다시 계산한 금액 — 다른 자료 없이 경정청구할 수 있어요</span></div>
      <div><span class="meta">확인하면 더 받을 수 있는 돈(최대)</span><b id="rf-calc-upto">${fmt(R.upto)}원</b><span class="meta">담당 부서에 자료를 받아 확인되는 만큼만</span></div>
      ${R.est ? `<div class="rf-est"><span class="meta">참고 어림</span><b>${fmt(R.est)}원</b><span class="meta">계약 금액으로 짐작한 값 — 신청 금액이 아님</span></div>` : ''}</div>
    ${stepsHtml(R)}
    <div class="actions no-print"><button type="button" class="btn" id="rf-calc-zip">경정청구 자료 내려받기(고친 신고서·근거·결재용 보고 — zip)</button></div>
    ${nextDocsHtml(R.rows)}
    <div class="scroll-x" tabindex="0" role="region" aria-label="돌려받을 돈 표"><table class="data-table rf-calc-t" data-stack="off"><thead><tr><th>기간</th><th>무엇이 문제인가</th><th>할 일</th><th>자세한 이유(검토자용)</th><th>돌려받을 돈</th></tr></thead><tbody>
    ${R.rows.map(r => `<tr class="rf-calc-${r.kind}"><td data-label="기간">${dd(r)}</td><td data-label="무엇이 문제인가"><b>${esc(plain(r.f).t)}</b></td><td data-label="할 일">${esc(plain(r.f).todo)}${r.kind === 'sure' && L.find(d => d.k === r.k)?.corrected?.length ? ` <a href="#rf-dg-${esc(r.k)}" data-open-dg="${esc(r.k)}">고친 신고서 보기 ↓</a>` : ''}</td><td data-label="자세한 이유"><details class="rf-tech"><summary>${esc(r.f.title)}</summary><p>${esc(r.f.what)}</p><p>${esc(r.f.how)}</p>${r.f.basis.length ? `<p class="meta">근거: ${law(D, r.f.basis)}</p>` : ''}</details></td><td class="num" data-label="돌려받을 돈">${money(r)}</td></tr>`).join('')}
    </tbody></table></div>
    <p class="note">경정청구로 돌려받는 세금에는 국세환급가산금이 붙습니다(국세기본법 제52조). 돌려받은 돈은 바로 세입으로 처리합니다(2025년 대구광역시 정부합동감사 지적 사항).</p></section>`;
}
/** 이렇게 하세요 — 비전문가 담당자용 순서(쉬운 말). 홈택스 메뉴 이름은 화면에 따라 조금 다를 수 있음 */
function stepsHtml(R: ReturnType<typeof refundCalc>): string {
  const ks = [...new Set(R.rows.filter(r => r.kind === 'sure').map(r => r.name))]; const up = R.rows.filter(r => r.kind === 'upto').length;
  return `<div class="rf-steps-plain"><p><b>이렇게 하세요</b></p><ol>
    ${ks.length ? `<li><b>바로 돌려받을 돈(${ks.length}개 기간)</b> — 아래 단추로 자료를 내려받습니다. 홈택스에 기관 인증서로 들어가 <b>신고/납부 → 세금신고 → 부가가치세 → 경정청구</b>에서 기간을 고르고, 「고친 신고서」의 고친 값을 칸마다 옮겨 적은 뒤, 사유 문장을 붙여넣고 묶음의 파일을 붙여 제출합니다.</li>` : '<li>신고서 숫자만으로 바로 돌려받을 돈은 없었어요.</li>'}
    ${up ? `<li><b>더 받을 수 있는 돈(${up}건)</b> — 표의 '할 일'대로 담당 부서에 자료를 부탁하세요. 아래 「부탁 메모 복사」를 쓰면 됩니다. 받은 파일은 같은 칸에 놓으면 다시 계산합니다.</li>` : ''}
    <li>돌려받은 돈은 바로 세입으로 처리하세요(감사에서 지적되는 일이 많아요).</li></ol>
    <p class="note">모르는 말이 나오면 '자세한 이유(검토자용)'를 펼치거나, 묶음의 결재용 보고를 세무 담당·세무대리인에게 보여 주세요. 판정은 참고이며 기관의 판단이 아닙니다.</p></div>`;
}
/** 다음에 받으면 금액이 커지는 자료 — '확인하면 최대' 항목을 자료별로 묶어 금액 큰 순 3개(선택) */
const NEXT_DOC: Record<string, (name: string) => string> = {
  'taxable-as-exempt': n => `${n} 홈택스 매입 목록(조회/발급 → 전자세금계산서 → 목록조회 → 매입) 엑셀 — 면세사업 관련으로 불공제한 것 가운데 과세 시설 지출을 가려 확정 금액으로`,
  'missing': n => `${n} 늦게 받거나 기재사항이 빠진 세금계산서의 수취일·수정세금계산서 — 1년 요건 안의 것은 공제`,
  'prereg': n => `${n} 사업장 등록 신청일 — 과세기간 끝 20일 안이면 공제`,
  'sales-exempt': n => `${n} 그 수입의 세입 결의(e호조) — 직영 면세 시설 수입이면 낸 매출세액을 돌려받음`,
  'recalc': n => `${n} 공통 건물·설비 자산대장(취득가·매입세액·취득 시기) — 재계산으로 공제 늘어남`,
};
function nextDocsHtml(rows: CalcRow[]): string {
  const m = new Map<string, { txt: string; amt: number }>();
  for (const r of rows) { if (r.kind !== 'upto' && !(r.f.key === 'recalc' && /줄어/.test(r.f.what))) continue; const f = NEXT_DOC[r.f.key]; if (!f) continue; const key = `${r.k}|${r.f.key}`; const x = m.get(key) ?? { txt: f(r.name), amt: 0 }; x.amt += r.est ?? r.f.effect ?? 0; m.set(key, x); }
  const L = [...m.values()].sort((a, b) => b.amt - a.amt).slice(0, 3); if (!L.length) return '';
  const memo = `[부가세 경정청구 자료 부탁]\n지난 부가가치세 신고를 다시 계산하는 데 아래 자료가 필요합니다. 파일로 보내 주세요.\n${L.map((x, i) => `${i + 1}. ${x.txt}`).join('\n')}\n(지자체 부가세 절감 점검기로 계산 — 판정은 참고이며 기관의 판단이 아닙니다)`;
  return `<div class="rf-next"><p><b>더 받으려면 — 이 자료를 부탁하세요</b> <span class="meta">선택 — 여기서 끝내도 '바로 돌려받을 돈'은 경정청구할 수 있어요</span></p><ol>${L.map(x => `<li>${esc(x.txt)}${x.amt ? ` <span class="meta">— 최대 ${fmt(x.amt)}원</span>` : ''}</li>`).join('')}</ol><div class="actions no-print"><button type="button" class="btn secondary" data-copy-memo="${esc(memo)}">부탁 메모 복사</button></div></div>`;
}
export function refundCalcCsv(L: Diag[], estBy?: Map<string, number>): string[][] {
  const R = refundCalc(L, estBy); const K = { sure: '확정', upto: '확인하면 최대', inlist: '목록 대조에 포함', none: '자료 필요' };
  return [['과세기간', '경정청구 기한', '무엇이 잘못됐나', '왜(이유)', '근거', '어떻게 하면', '구분', '돌려받을 돈(원)', '계약 어림(참고)', '설명'], ...R.rows.map(r => [r.name, r.claim, r.f.title, r.f.what, uniq(r.f.basis).map(lawText).join(' · '), r.f.how, K[r.kind], r.f.effect == null ? '' : String(r.f.effect), r.est == null ? '' : String(r.est), r.f.effectNote]), [], ['합계', '', '', '', '', '', '확정', String(R.sure)], ['', '', '', '', '', '', '확인하면 최대', String(R.upto)], ['', '', '', '', '', '', '계약 어림(참고)', String(R.est)]];
}

/** 결재용 검토 보고(Word — 한글에서 바로 열림). 돌려받을 돈 표·고칠 칸·고치는 법·붙임. 숫자는 refundCalc 그대로 */
export function reportBlocks(L: Diag[], orgName: string, win: string): HBlock[] {
  const R = refundCalc(L); const K = { sure: '확정', upto: '확인하면 최대', inlist: '목록 대조에 포함', none: '자료 필요' } as const; const today = new Date().toISOString().slice(0, 10);
  const money = (r: CalcRow) => r.f.effect == null ? '—' : `${fmt(r.f.effect)}원`;
  const fx = L.filter(d => d.days >= 0).flatMap(d => d.fixed.filter(x => x.before !== x.after).map(x => [d.name, x.cell, x.label, x.before == null ? '' : fmt(x.before), x.after == null ? '' : fmt(x.after), x.before != null && x.after != null ? fmt(x.after - x.before) : '']));
  const act = R.rows.filter(r => r.kind === 'sure' || r.kind === 'upto');
  return [hp('title', [`부가가치세 경정청구 검토(${win})`, 'title']),
    hp('note', [`${orgName} · ${today} · 지자체 부가세 절감 점검기로 계산 · 판정은 참고이며 기관의 판단이 아닙니다`, 'note']),
    hp('h3', ['1. 개요', 'h3']),
    hp('body', [`대상 기간(경정청구가 되는 과세기간) ${win}의 신고서를 다시 계산했습니다.`, 'body']),
    hp('body', [`· 확정 ${fmt(R.sure)}원 — 신고서 숫자로 다시 계산한 금액(경정청구하면 돌려받는 돈)`, 'body']),
    hp('body', [`· 확인하면 최대 ${fmt(R.upto)}원 — 불공제 사유·과세표준 가운데 과세 시설 지출 또는 면세 수입으로 확인되는 만큼`, 'body']),
    hp('h3', ['2. 과세기간별 결과', 'h3']),
    htable([['과세기간', '무엇이 잘못됐나', '돌려받을 돈', '구분', '근거'], ...R.rows.map(r => [r.name, r.f.title, money(r), K[r.kind], uniq(r.f.basis).map(lawText).join(' · ')])], { head: true, widths: [14, 40, 14, 12, 20] }),
    ...(fx.length ? [hp('h3', ['3. 고칠 칸 — 홈택스 경정청구 입력값', 'h3']), htable([['과세기간', '칸', '항목', '당초', '경정 후', '차이'], ...fx], { head: true, widths: [16, 8, 28, 16, 16, 16] })] : []),
    hp('h3', [`${fx.length ? 4 : 3}. 어떻게 고치나`, 'h3']),
    ...act.flatMap(r => [hp('body', [`□ ${r.name} — ${r.f.title}`, 'body']), hp('body', [r.f.what, 'body']), hp('body', ['· ' + r.f.how, 'body'])]),
    hp('h3', [`${fx.length ? 5 : 4}. 붙임`, 'h3']),
    hp('body', ['· 경정청구서(홈택스 신고/납부 → 세금신고 → 부가가치세 → 경정청구) — 위 고칠 칸 값', 'body']),
    hp('body', ['· 공제받지못할매입세액명세서(고친 안분·정산), 매입처별 세금계산서합계표 추가분(매입 목록을 대조한 경우)', 'body']),
    hp('body', ['· 근거 조문·유권해석(묶음의 06 파일), 돌려받을 돈 표(13 파일)', 'body']),
    hp('note', ['경정청구로 돌려받는 세금에는 국세환급가산금이 붙습니다(국세기본법 제52조). 돌려받은 돈은 바로 세입으로 처리합니다(2025년 대구광역시 정부합동감사 지적 사항).', 'note'])];
}

/* ── 고친 신고서(운영자 2026-11-05 '과거 신고한 자료를 올리면 수정 자료로 다시 신고할 수 있게') ──
 *  올린 신고서의 칸을 그대로 두고 고칠 칸만 바꾼다: (17) − 줄어든 불공제, (18) + 같은 금액, 명세서의 안분·정산 칸은 다시 계산한 값.
 *  경정청구서 줄: 당초 납부(환급)세액 → 고친 값 → 돌려받을 세액. 납부세액은 매출세액 − (18) 로 어림(가산세·경감공제·예정고지 등은 원래 신고서 그대로). 새 계산 규칙 없음. */
const CELL_NAME: Record<number, string> = { 1: '과세 세금계산서 발급분', 2: '과세 매입자발행 세금계산서', 3: '과세 신용카드·현금영수증 발행분', 4: '과세 기타(정규영수증 외 매출분)', 5: '영세율 세금계산서 발급분', 6: '영세율 기타', 7: '예정신고 누락분(매출)', 8: '대손세액 가감', 9: '매출 합계', 10: '세금계산서 수취분 일반매입', 11: '수출기업 수입분 납부유예', 12: '세금계산서 수취분 고정자산 매입', 13: '예정신고 누락분(매입)', 14: '매입자발행 세금계산서', 15: '그 밖의 공제매입세액', 16: '매입 합계', 17: '공제받지 못할 매입세액', 18: '차감계(공제받는 매입세액)' };
export type CorrDoc = { k: string; kind: string; file: string; reg: string; delta: number; cells: { n: number; label: string; amt: number | null; before: number | null; after: number | null }[]; parts: { sec: string; rows: { label: string; before: number | null; after: number | null }[] }[]; payBefore: number | null; payAfter: number | null; tb?: number | null; pen?: number | null; due?: number | null };
export function correctedFilings(fc: Map<string, FiledCheck>): Map<string, CorrDoc[]> {
  const out = new Map<string, CorrDoc[]>();
  for (const [k, c] of fc) { if (!c.fixes?.length) continue; const by = new Map<FiledDocLite, FixPart[]>(); for (const x of c.fixes) (by.get(x.doc) ?? by.set(x.doc, []).get(x.doc)!).push(x);
    const L: CorrDoc[] = [];
    for (const [d, parts] of by) { const delta = parts.reduce((s, x) => s + x.delta, 0);
      const cells = Object.keys(d.cells).map(Number).filter(n => n >= 1 && n <= 18).sort((a, b) => a - b).map(n => { const t = d.cells[n]?.tax ?? null; const after = t == null ? null : n === 17 ? t - delta : n === 18 ? t + delta : t; return { n, label: CELL_NAME[n] ?? `(${n})`, amt: d.cells[n]?.amt ?? null, before: t, after }; });
      const sales = d.cells[9]?.tax ?? [1, 2, 3, 4, 5, 6, 7, 8].reduce((s, n) => s + (d.cells[n]?.tax ?? 0), 0); const c18 = d.cells[18]?.tax ?? null;
      const tb = d.cells[9]?.amt ?? ([1, 2, 3, 4, 5, 6, 7, 8].some(n => d.cells[n]?.amt != null) ? [1, 2, 3, 4, 5, 6, 7, 8].reduce((t, n) => t + (d.cells[n]?.amt ?? 0), 0) : null);
      L.push({ k, kind: d.kind, file: d.file, reg: d.reg ?? '', delta, cells, parts: parts.map(x => ({ sec: x.sec, rows: x.rows })), payBefore: c18 == null ? null : sales - c18, payAfter: c18 == null ? null : sales - c18 - delta, tb, pen: d.pen ?? null, due: d.due ?? null }); }
    out.set(k, L); }
  return out;
}
const n0 = (v: number | null) => v == null ? '' : fmt(v);
/** 경정청구 사유 문장(고친 신고서 한 장) — 화면·경정청구서 밑자료 공용 */
export function corrReason(c: CorrDoc): string { const why = c.parts.map(p => p.sec === '안분' ? '공통매입세액 안분 계산에서 총공급가액 등을 잘못 넣어' : p.sec === '정산' ? '공통매입세액 정산 계산을 잘못하여' : '예정신고분 공통매입세액을 확정신고 때 6개월 비율로 정산하지 않아').join(', '); const y = c.k.split('-'); return `${y[0]}년 제${y[1]}기 ${c.kind}신고 때 ${why} 매입세액 ${fmt(c.delta)}원을 덜 공제받았으므로 국세기본법 제45조의2에 따라 경정을 청구합니다(부가가치세법 시행령 제81조·제82조).`; }
/** 경정청구서 기재 밑자료(세무 검토 반영 2026-11-05) — 과세기간·신고서 한 장마다 한 줄: 세목·과세기간·신고 구분·사업자등록번호·법정신고기한·경정청구 기한·당초/경정 후 납부(환급)세액·돌려받을 세액·사유·붙임.
 *  서식 칸 번호는 쓰지 않는다(홈택스 경정청구 화면·국세기본법 시행규칙 서식 칸 이름으로 옮김). 법정신고기한은 공휴일이면 다음 날 */
export function claimRows(M: Map<string, CorrDoc[]>): string[][] {
  const rows: string[][] = [['세목', '과세기간', '신고 구분', '사업자등록번호', '법정신고기한', '경정청구 기한(법정신고기한 + 5년)', '당초 납부(환급)세액', '경정 후 납부(환급)세액', '돌려받을 세액', '경정청구 이유', '붙임', '확인할 것']];
  for (const [k, L] of [...M].sort()) for (const c of L) { const [y, h] = k.split('-').map(Number); const due = h === 1 ? `${y}-07-25` : `${y + 1}-01-25`; const claim = h === 1 ? `${y + 5}-07-25` : `${y + 6}-01-25`;
    rows.push(['부가가치세', `${y}년 제${h}기`, c.kind, c.reg, due, claim, c.payBefore != null ? String(c.payBefore) : '', c.payAfter != null ? String(c.payAfter) : '', String(c.delta), corrReason(c), '고친 신고서(이 자료의 \'고친 신고서\' 시트) · 공제받지 못할 매입세액 명세서 고친 값 · 당초 신고서 사본', c.parts.some(p => p.sec === '안분' || p.sec === '정산') ? '원래 신고가 공급가액 비율로 나눴을 때의 금액 — 매입가액·면적 기준이었다면 다시 셈(시행령 제81조 제4항)' : '']); }
  return rows;
}
export function correctedHtml(L: CorrDoc[]): string {
  return L.map(c => `<div class="rf-corr"><p><b>고친 ${esc(c.kind)} 신고서</b>${c.reg ? ` · ${esc(c.reg)}` : ''} <span class="meta">(${esc(c.file)}) — 경정청구 화면에 이 '고친 값'을 넣습니다</span></p>
    <div class="scroll-x" tabindex="0" role="region" aria-label="고친 신고서"><table class="data-table vat-table" data-stack="off"><thead><tr><th scope="col">칸</th><th scope="col">항목</th><th scope="col" class="num">당초 세액</th><th scope="col" class="num">고친 세액</th><th scope="col" class="num">차이</th></tr></thead><tbody>
    ${c.cells.map(x => `<tr${x.before !== x.after ? ' class="rf-chg"' : ''}><td>(${x.n})</td><td>${esc(x.label)}</td><td class="num">${n0(x.before)}</td><td class="num">${x.before !== x.after ? `<b>${n0(x.after)}</b>` : n0(x.after)}</td><td class="num">${x.before != null && x.after != null && x.before !== x.after ? fmt(x.after - x.before) : ''}</td></tr>`).join('')}
    ${c.payBefore != null ? `<tr class="rf-chg"><td></td><td>납부(환급)세액 — 매출세액 − (18) (가산세·경감공제·예정고지는 원래대로)</td><td class="num">${fmt(c.payBefore)}</td><td class="num"><b>${fmt(c.payAfter!)}</b></td><td class="num">${fmt(c.payAfter! - c.payBefore)}</td></tr>` : ''}</tbody></table></div>
    ${c.parts.map(p => `<p class="note"><b>공제받지못할매입세액명세서 — ${esc(p.sec === '안분' ? '공통매입세액 안분 계산' : '공통매입세액의 정산')}${p.sec === '정산(새로 넣음)' ? '(새로 넣는 칸)' : ''}</b></p><div class="scroll-x" tabindex="0" role="region" aria-label="고친 명세서"><table class="data-table vat-table" data-stack="off"><thead><tr><th scope="col">칸</th><th scope="col" class="num">당초</th><th scope="col" class="num">고친 값</th></tr></thead><tbody>${p.rows.map(r => `<tr${r.before !== r.after ? ' class="rf-chg"' : ''}><td>${esc(r.label)}</td><td class="num">${n0(r.before)}</td><td class="num">${r.before !== r.after ? `<b>${n0(r.after)}</b>` : n0(r.after)}</td></tr>`).join('')}</tbody></table></div>`).join('')}
    ${(() => { const reason = corrReason(c);
      return `<p class="rf-reason"><b>사유 문장</b> ${esc(reason)} <button type="button" class="link-btn no-print" data-copy-memo="${esc(reason)}">복사</button></p>`; })()}
    <p class="rf-claim">경정청구서: 당초 신고 ${c.payBefore != null ? `납부(환급)세액 ${fmt(c.payBefore)}원 → 고친 값 ${fmt(c.payAfter!)}원, ` : ''}<b>돌려받을 세액 ${fmt(c.delta)}원</b></p></div>`).join('');
}
export function correctedCsv(M: Map<string, CorrDoc[]>): string[][] {
  const rows: string[][] = [['과세기간', '구분', '사업자등록번호', '파일', '서식', '칸', '항목', '당초', '고친 값', '차이']];
  for (const [k, L] of [...M].sort()) for (const c of L) { const P = `${k.split('-')[0]}년 제${k.split('-')[1]}기`;
    for (const x of c.cells) rows.push([P, c.kind, c.reg, c.file, '신고서', `(${x.n})`, x.label, n0(x.before), n0(x.after), x.before != null && x.after != null ? String(x.after - x.before) : '']);
    if (c.payBefore != null) rows.push([P, c.kind, c.reg, c.file, '신고서', '', '납부(환급)세액(매출세액 − (18), 참고)', String(c.payBefore), String(c.payAfter), String(c.payAfter! - c.payBefore)]);
    for (const p of c.parts) for (const r of p.rows) rows.push([P, c.kind, c.reg, c.file, `명세서 ${p.sec}`, '', r.label, n0(r.before), n0(r.after), r.before != null && r.after != null ? String(r.after - r.before) : '']);
    rows.push([P, c.kind, c.reg, c.file, '경정청구서', '', '돌려받을 세액', '', String(c.delta), '']); }
  return rows;
}
