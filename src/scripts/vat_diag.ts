/** 지난 신고 진단 — 과세기간마다 '무엇이 잘못·누락됐나 → 어느 칸을 어떻게 고치나 → 고친 신고서 → 효과(돌려받는 돈)'(운영자 2026-11-05
 *  '부가가치세 신고할 때 무엇이 잘못되었거나 누락되어 어떻게 고치면 되고 고친 내용과 효과를 나타나게 해 … 이 앱은 돈을 돌려받는 게 목적').
 *  새 판정 규칙 없음 — vat_review.ts 의 건별 판정(judge)·신고서 값(vat_unlock filedSummary)을 과세기간마다 신고서 칸으로 대조만 한다.
 *  금액 나눔: 덜 공제받은 몫 G = 있어야 할 공제 세액 − 신고 (18). 그중 '신고서에 아예 없던 세금계산서' 몫 = 빠진 세액 × (공제 대상 비율), 나머지는 '불공제로 넣은 것'을
 *  과세 시설 전용·공통(안분) 공제 대상 세액 비율로 나눈다(건별로 무엇이 (17)에 들어갔는지는 신고서에 없으므로 나눔은 어림 — 화면에 적음). 판정은 참고이며 기관의 판단이 아니다. */
import { esc, fmt, lawLink, lawText, uniq, type Basis, type Data } from './vat_rules';

export type DiagIn = {
  k: string; name: string; filed: 'filed' | 'excluded' | 'none' | 'unknown'; due: string; claim: string; days: number; future: boolean;
  deduct: number | null; nondeduct: number | null; total16: number | null; er: number | null;
  doc: { hasNd: boolean; hasCommon: boolean; ndReasons: Record<number, number>; files: string[] } | null;
  recv: number; should: number;
  ok: { tax: number; claim: number; n: number; facs: { name: string; tax: number; n: number }[] };
  split: { tax: number; claim: number; n: number };
  undecided: { tax: number; n: number };
  other: { tax: number; n: number; fixTax: number };
};
export type Finding = { key: string; title: string; what: string; how: string; effect: number | null; effectNote: string; basis: Basis[] };
export type FixRow = { cell: string; label: string; before: number | null; after: number | null };
export type Diag = { k: string; name: string; state: 'claim' | 'late' | 'unknown' | 'ok' | 'over' | 'expired'; gain: number; cond: number; findings: Finding[]; fixed: FixRow[]; claim: string; days: number; due: string };

const B = (law: string, art: string): Basis => ({ law, art });
const ND_NAME: Record<number, string> = { 1: '① 필요적 기재사항 누락 등', 2: '② 사업과 직접 관련 없는 지출', 3: '③ 비영업용 승용자동차 구입·유지·임차', 4: '④ 기업업무추진비 등', 5: '⑤ 면세사업등 관련', 6: '⑥ 토지의 자본적 지출 관련', 7: '⑦ 사업자등록 전 매입세액', 8: '⑧ 금·구리 스크랩 거래계좌 미사용' };
const TOL = 1000;   // 원 단위 끝수·카드 소액 차이는 '빠짐'으로 보지 않는다

export function diagnose(x: DiagIn): Diag {
  const F: Finding[] = []; const base = { k: x.k, name: x.name, claim: x.claim, days: x.days, due: x.due };
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
  const fixed: FixRow[] = [{ cell: '(16)', label: '매입세액 합계', before: R, after: after16 }, { cell: '(17)', label: '공제받지 못할 매입세액', before: N, after: after16 !== null ? after16 - after18 : null }, { cell: '(18)', label: '공제 매입세액', before: D, after: after18 }];
  return { ...base, state: gain > 0 ? 'claim' : G < -TOL ? 'over' : 'ok', gain, cond: x.other.fixTax, findings: F, fixed };
}

const STATE_TXT: Record<Diag['state'], string> = { claim: '경정청구로 돌려받을 돈 있음', late: '기한후신고로 돌려받을 돈 있음', unknown: '신고서를 올리면 진단', ok: '덜 공제받은 몫 없음', over: '목록보다 더 공제받음', expired: '경정청구 기한 지남' };
const law = (D: Data, bs: Basis[]) => uniq(bs).map(b => lawLink(D, b)).join(' · ');
export function diagHtml(D: Data, L: Diag[]): string {
  const show = L.filter(d => d.findings.length || d.gain);
  if (!show.length) return '';
  const gain = show.filter(d => d.state !== 'expired').reduce((s, d) => s + d.gain, 0), cond = show.filter(d => d.state !== 'expired').reduce((s, d) => s + d.cond, 0);
  const nF = show.reduce((s, d) => s + d.findings.filter(f => !['undecided', 'nofiled'].includes(f.key)).length, 0);
  const card = (d: Diag) => `<details class="rf-dg" id="rf-dg-${d.k}" ${d.gain > 0 ? 'open' : ''}><summary><b>${esc(d.name)}</b> — ${esc(STATE_TXT[d.state])}${d.gain > 0 ? ` <b class="rf-dg-amt">${fmt(d.gain)}원</b>` : ''}${d.cond ? ` <span class="note">(+조건부 ${fmt(d.cond)}원)</span>` : ''} <span class="meta">${d.days >= 0 ? `경정청구 기한 ${esc(d.claim)} · D-${d.days}` : '기한 지남'}</span></summary>
    ${d.fixed.length && d.fixed.some(r => r.before !== r.after) ? `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table" data-stack="off"><caption>고친 신고서 — 칸별로 처음 신고한 값과 바르게 고친 값</caption><thead><tr><th scope="col">칸</th><th scope="col">항목</th><th scope="col">처음 신고</th><th scope="col">고친 값</th><th scope="col">차이</th></tr></thead><tbody>${d.fixed.map(r => `<tr><th scope="row">${esc(r.cell)}</th><td>${esc(r.label)}</td><td>${r.before === null ? '<span class="note">—</span>' : fmt(r.before)}</td><td>${r.after === null ? '<span class="note">—</span>' : fmt(r.after)}</td><td>${r.before !== null && r.after !== null && r.after !== r.before ? `${r.after > r.before ? '+' : ''}${fmt(r.after - r.before)}` : ''}</td></tr>`).join('')}<tr class="rf-dg-eff"><th scope="row">효과</th><td colspan="4">납부할 세액이 <b>${fmt(d.gain)}원</b> 줄어 그만큼 돌려받습니다(환급 때 국세환급가산금이 붙습니다 — 국세기본법 제52조)</td></tr></tbody></table></div>` : ''}
    <ol class="rf-dg-list">${d.findings.map(f => `<li><p class="rf-dg-t"><b>${esc(f.title)}</b>${f.effect ? ` → <b>${fmt(f.effect)}원</b>` : ''}${f.effectNote ? ` <span class="note">(${esc(f.effectNote)})</span>` : ''}</p><div class="rf-why"><p><span class="rf-k">무엇이</span> ${esc(f.what)}</p><p><span class="rf-k">고치기</span> ${esc(f.how)}</p>${f.basis.length ? `<p><span class="rf-k">근거</span> ${law(D, f.basis)}</p>` : ''}</div></li>`).join('')}</ol></details>`;
  return `<p class="rf-dg-sum">지난 신고 ${show.length}개 과세기간을 매입 목록과 대조했습니다 — 잘못·누락 <b>${nF}</b>건, 고치면 돌려받는 돈 <b>${fmt(gain)}원</b>${cond ? ` (+ 수정세금계산서를 받으면 ${fmt(cond)}원)` : ''}.</p>
    ${show.sort((a, b) => b.gain - a.gain || a.k.localeCompare(b.k)).map(card).join('')}
    <p class="note">'무엇이'의 금액 나눔(빠진 세금계산서 / 불공제로 넣은 것 / 안분 안 함)은 어림입니다 — 신고서에는 건별로 무엇을 (17)에 넣었는지가 없어 매입 목록의 공제 대상 비율로 나눴습니다. 합계(덜 공제받은 몫 = 있어야 할 공제 세액 − 신고 (18))는 정확히 그 차이입니다. 판정은 참고이며 기관의 판단이 아닙니다.</p>`;
}
export function diagCsv(L: Diag[]): string[][] {
  const rows: string[][] = [['과세기간', '상태', '돌려받을 돈', '조건부', '경정청구 기한', '항목', '무엇이 잘못·누락', '고치는 법', '효과(원)', '효과 설명', '근거']];
  for (const d of L) for (const f of d.findings) rows.push([d.name, STATE_TXT[d.state], String(d.gain), String(d.cond), d.claim, f.title, f.what, f.how, f.effect == null ? '' : String(f.effect), f.effectNote, f.basis.map(lawText).join(' · ')]);
  rows.push([]); rows.push(['과세기간', '칸', '항목', '처음 신고', '고친 값', '차이']);
  for (const d of L) for (const r of d.fixed) rows.push([d.name, r.cell, r.label, r.before == null ? '' : String(r.before), r.after == null ? '' : String(r.after), r.before != null && r.after != null ? String(r.after - r.before) : '']);
  return rows;
}
