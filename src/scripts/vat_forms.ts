/** 신고 준비 결과를 국세청 서식 모양으로 — 운영자 지시 2026-10-27 '결과물이 국세청에 신고하는 시스템과 유사하게 → 순서대로 해'.
 *  홈택스 화면을 흉내 내지 않고(기관 로고·문구 없음) 부가가치세법 시행규칙 별지 서식의 칸 배치·번호만 따른다(시행규칙 2026-04-01 시행 판 본문의 서식, 별지 제21호 <개정 2026.3.20.>):
 *  ① 일반과세자 부가가치세 신고서(제21호) 1쪽 (1)~(30) + 4쪽 명세 (36)~(56)  ② 매입처별 세금계산서합계표(갑)(제39호(1))  ③ 신용카드매출전표등 수령명세서(갑)(제16호(1))
 *  ④ 공제받지 못할 매입세액 명세서(제22호: 사유별 ①~⑨ · 안분 ⑩~⑭ · 정산 ⑮~ · 재계산)  ⑤ 부동산임대공급가액명세서(제25호)  ⑥ 과세사업전환 감가상각자산 신고서(제17호)  ⑦ 홈택스 입력 순서표.
 *  이 도구가 채우지 못하는 칸(영세율·대손·경감공제·가산세·예정고지 등)은 비워 두고 '홈택스에서 직접'으로 표시한다. 참고용, 신고 책임은 신고인. */
import { esc, fmt, pct, type Data, type Org, type OrgFacility, type LedgerRow, type Filing, type PeriodKey } from './vat_rules';
export type UsedRow = { f: OrgFacility; r: LedgerRow; isPre: boolean; inv: boolean; card: boolean };
export type ConvRow = { desc: string; tax: number; kind: 'building' | 'other'; acq: PeriodKey; common: boolean; credit: number; n: number; remain: number };
export type RecalcRow = { a: Filing['assets'][number]; from: PeriodKey; ratio: number; n: number; amt: number };
export type FormCtx = { D: Data; org: Org; P: { y: number; half: number; kind: 'P' | 'F'; name: string; own: string[]; prelim: string[]; full: string[]; due: string }; cells: Record<string, { amt: number; tax: number }>; used: UsedRow[]; groups: Filing['groups']; prelimIn: Record<string, { taxable: number; exempt: number; common: number; nondeduct: number }>; recalc: RecalcRow[]; conv: ConvRow[]; convRatio: number; sales: Record<string, { c1: number; c3: number; c4: number; dep?: number; days?: number; rate?: number; deem?: number }>; facs: OrgFacility[]; unresolved: string[]; excluded: string[]; missing: string[] };
const W = (n?: number) => n ? fmt(n) : '';
const cell = (c: Record<string, { amt: number; tax: number }>, no: string) => c[no] ?? { amt: 0, tax: 0 };
const supKey = (r: LedgerRow) => r.sreg || ('n:' + (r.sup || r.desc).replace(/\s|\(주\)|주식회사|㈜/g, ''));
const supName = (r: LedgerRow) => r.sup || r.desc.split(' · ')[0];
type Agg = { sreg: string; name: string; n: number; amt: number; tax: number };
function aggregate(rows: LedgerRow[]) { const m = new Map<string, Agg>(); for (const r of rows) { const k = supKey(r); const a = m.get(k) ?? { sreg: r.sreg || '', name: supName(r), n: 0, amt: 0, tax: 0 }; a.n++; a.amt += r.amt; a.tax += r.tax; m.set(k, a); } return [...m.values()].sort((a, b) => b.tax - a.tax); }
const tbl = (cap: string, head: string[], body: string, foot = '') => `<div class="scroll-x"><table class="data-table vat-table form" data-stack="off"><caption>${cap}</caption><thead><tr>${head.map(h => `<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${body}${foot}</tbody></table></div>`;
const DIRECT = '<td class="note" colspan="2">홈택스에서 직접</td>';
const NA = '<td class="note" colspan="2">해당 없음이면 비움</td>';

export function renderForms(x: FormCtx): string {
  const { D, org, P, cells, used, groups, recalc, conv, convRatio, sales, facs } = x; const c = (no: string) => cell(cells, no);
  const sum = (nos: string[], k: 'amt' | 'tax' = 'tax') => nos.reduce((s, n) => s + c(n)[k], 0);
  const c9t = sum(['1', '3', '4']), c9a = sum(['1', '3', '4'], 'amt'); const c15 = sum(['44', '45', '48']); const c16 = sum(['10', '12', '13', '14']) + c15; const c17 = sum(['53', '54']); const c18 = c16 - c17; const pay = c9t - c18;
  const row = (no: string, name: string, v?: { amt: number; tax: number } | null, rate = '', cls = '') => `<tr class="${cls}"><td>(${no})</td><th scope="row">${name}</th>${v === undefined ? DIRECT : v === null ? NA : `<td>${W(v.amt)}</td><td>${rate ? `<span class="note">${rate}</span> ` : ''}${fmt(v.tax)}</td>`}</tr>`;
  const sec = (t: string) => `<tr class="sec"><th colspan="4">${t}</th></tr>`;
  /* ── ① 신고서 1쪽 ── */
  const p1 = tbl(`일반과세자 부가가치세 ${P.kind === 'P' ? '예정' : '확정'}신고서 — ① 신고내용 (별지 제21호서식 제1쪽 배치) · ${esc(org.org)} · ${esc(P.name)}`, ['칸', '구분', '금액', '세액'],
    sec('과세표준 및 매출세액') + row('1', '과세 — 세금계산서 발급분', c('1'), '10/100') + row('2', '과세 — 매입자발행 세금계산서', null) + row('3', '과세 — 신용카드·현금영수증 발행분', c('3'), '10/100') + row('4', '과세 — 기타(정규영수증 외 매출분)', c('4'), '10/100') + row('5', '영세율 — 세금계산서 발급분', null) + row('6', '영세율 — 기타', null) + row('7', '예정신고 누락분(매출) — 4쪽 (40)', P.kind === 'F' ? undefined : null) + row('8', '대손세액 가감', null) + row('9', '합계 ㉮', { amt: c9a, tax: c9t }, '', 'total')
    + sec('매입세액') + row('10', '세금계산서 수취분 — 일반매입', c('10')) + row('11', '세금계산서 수취분 — 수출기업 수입분 납부유예', null) + row('12', '세금계산서 수취분 — 고정자산매입', c('12')) + row('13', '예정신고 누락분 — 4쪽 (43)', c('13')) + row('14', '매입자발행 세금계산서', c('14')) + row('15', '그 밖의 공제매입세액 — 4쪽 (52)', { amt: sum(['44', '45', '48'], 'amt'), tax: c15 }) + row('16', '합계 (10)−(11)+(12)+(13)+(14)+(15)', { amt: sum(['10', '12', '13', '14', '44', '45', '48'], 'amt'), tax: c16 }, '', 'total') + row('17', '공제받지 못할 매입세액 — 4쪽 (56)', { amt: sum(['53', '54'], 'amt'), tax: c17 }) + row('18', '차감계 (16)−(17) ㉯', { amt: 0, tax: c18 }, '', 'total')
    + `<tr class="total"><td></td><th scope="row">납부(환급)세액 ㉰ = 매출세액 ㉮ − 매입세액 ㉯</th><td></td><td><strong>${fmt(pay)}</strong>${pay < 0 ? ' <span class="note">(환급)</span>' : ''}</td></tr>`
    + sec('경감·공제세액 등 — 이 도구 범위 밖, 홈택스에서 직접') + row('19', '그 밖의 경감·공제세액 — 4쪽 (63)') + row('20', '신용카드매출전표등 발행공제 등(개인사업자) ', null) + row('21', '합계 ㉱') + row('22', '소규모 개인사업자 감면세액 ㉲', null) + row('23', '예정신고 미환급세액 ㉳', P.kind === 'F' ? undefined : null) + row('24', '예정고지세액 ㉴') + row('25', '수시부과세액 ㉵', null) + row('26', '사업양수자가 대리납부한 세액 ㉶', null) + row('27', '매입자 납부특례에 따라 납부한 세액 ㉷', null) + row('28', '신용카드업자가 대리납부한 세액 ㉸', null) + row('29', '가산세액 계 ㉹ — 4쪽 (84)')
    + `<tr class="total"><td>(30)</td><th scope="row">차감·가감하여 납부할 세액(환급받을 세액) = ㉰−㉱−㉲−㉳−㉴−㉵−㉶−㉷−㉸+㉹</th><td></td><td class="note">㉰ ${fmt(pay)} 에서 (19)~(29)를 홈택스에서 반영</td></tr>`);
  /* ── ① 신고서 4쪽 명세 ── */
  const preInv = used.filter(u => u.isPre && u.inv), preCard = used.filter(u => u.isPre && u.card);
  const sumRows = (rs: UsedRow[]) => ({ amt: rs.reduce((s, u) => s + u.r.amt, 0), tax: rs.reduce((s, u) => s + u.r.tax, 0) });
  const p4 = tbl('신고서 제4쪽 — 예정신고 누락분 · (15) 그 밖의 공제매입세액 · (17) 공제받지 못할 매입세액 명세', ['칸', '구분', '금액', '세액'],
    (P.kind === 'F' ? sec('예정신고 누락분 명세') + row('36', '(7) 매출 — 과세 세금계산서') + row('37', '(7) 매출 — 과세 기타') + row('38', '(7) 매출 — 영세율 세금계산서', null) + row('39', '(7) 매출 — 영세율 기타', null) + row('40', '(7) 합계') + row('41', '(13) 매입 — 세금계산서', sumRows(preInv)) + row('42', '(13) 매입 — 그 밖의 공제매입세액', sumRows(preCard)) + row('43', '(13) 합계', sumRows([...preInv, ...preCard]), '', 'total') : '')
    + sec('(15) 그 밖의 공제매입세액 명세') + row('44', '신용카드매출전표등 수령명세서 제출분 — 일반매입', c('44')) + row('45', '신용카드매출전표등 수령명세서 제출분 — 고정자산매입', c('45')) + row('46', '의제매입세액', null) + row('47', '재활용폐자원등 매입세액', null) + row('48', '과세사업전환 매입세액(제17호서식)', c('48')) + row('49', '재고매입세액', null) + row('50', '변제대손세액', null) + row('51', '외국인 관광객에 대한 환급세액', null) + row('52', '합계 → (15)', { amt: sum(['44', '45', '48'], 'amt'), tax: c15 }, '', 'total')
    + sec('(17) 공제받지 못할 매입세액 명세') + row('53', '공제받지 못할 매입세액(제22호서식 2.)', c('53')) + row('54', '공통매입세액 중 면세사업등 해당 세액(제22호서식 3.~5.)', c('54')) + row('55', '대손처분받은 세액', null) + row('56', '합계 → (17)', { amt: sum(['53', '54'], 'amt'), tax: c17 }, '', 'total'));
  /* ── ② 매입처별 세금계산서합계표(갑) ── */
  const eRows = used.filter(u => u.inv && !u.isPre && u.r.proof === 'e_invoice').map(u => u.r), pRows = used.filter(u => u.inv && !u.isPre && u.r.proof === 'p_invoice').map(u => u.r);
  const eAgg = aggregate(eRows), pAgg = aggregate(pRows);
  const tot = (a: Agg[]) => ({ n: a.length, cnt: a.reduce((s, r) => s + r.n, 0), amt: a.reduce((s, r) => s + r.amt, 0), tax: a.reduce((s, r) => s + r.tax, 0) });
  const te = tot(eAgg), tp = tot(pAgg);
  const f39 = tbl('매입처별 세금계산서합계표(갑) — 2. 매입세금계산서 총합계 (별지 제39호서식(1))', ['구분', '⑦ 매입처수', '⑧ 매수', '⑨ 공급가액', '⑩ 세액'],
    `<tr class="total"><th scope="row">합계</th><td>${te.n + tp.n}</td><td>${te.cnt + tp.cnt}</td><td>${fmt(te.amt + tp.amt)}</td><td>${fmt(te.tax + tp.tax)}</td></tr>
     <tr><th scope="row">과세기간 종료일 다음 달 11일까지 전송된 전자세금계산서 발급받은 분 — 사업자등록번호 발급받은 분 <span class="note">홈택스 자동 조회와 맞춰 봄</span></th><td>${te.n}</td><td>${te.cnt}</td><td>${fmt(te.amt)}</td><td>${fmt(te.tax)}</td></tr>
     <tr><th scope="row">위 전자세금계산서 외의 발급받은 분(종이·늦게 전송) — 사업자등록번호 발급받은 분 <span class="note">아래 3. 명세를 직접 입력</span></th><td>${tp.n}</td><td>${tp.cnt}</td><td>${fmt(tp.amt)}</td><td>${fmt(tp.tax)}</td></tr>`)
    + (pAgg.length ? tbl('3. 전자세금계산서 외 발급받은 매입처별 명세(합계금액으로)', ['⑪ 번호', '⑫ 사업자등록번호', '⑬ 상호(법인명)', '⑭ 매수', '⑮ 공급가액', '⑯ 세액'], pAgg.map((a, i) => `<tr><td>${i + 1}</td><td>${a.sreg ? esc(a.sreg) : '<span class="verdict check">등록번호 확인</span>'}</td><th scope="row">${esc(a.name)}</th><td>${a.n}</td><td>${fmt(a.amt)}</td><td>${fmt(a.tax)}</td></tr>`).join('')) : '<p class="meta">종이 세금계산서 수취분이 없습니다 — 전자분은 홈택스가 자동으로 불러옵니다.</p>')
    + (eAgg.length ? `<details class="vat-more"><summary>전자세금계산서 발급받은 분 공급자별 ${eAgg.length}곳(홈택스 자동 조회분과 대조용)</summary>${tbl('전자세금계산서 매입 — 공급자별', ['사업자등록번호', '상호', '매수', '공급가액', '세액'], eAgg.map(a => `<tr><td>${esc(a.sreg || '—')}</td><th scope="row">${esc(a.name)}</th><td>${a.n}</td><td>${fmt(a.amt)}</td><td>${fmt(a.tax)}</td></tr>`).join(''))}</details>` : '');
  /* ── ③ 신용카드매출전표등 수령명세서(갑) ── */
  const cardRows = used.filter(u => u.card && !u.isPre).map(u => u.r); const cashR = cardRows.filter(r => r.proof === 'cash'), crdR = cardRows.filter(r => r.proof === 'card');
  const S = (rs: LedgerRow[]) => ({ n: rs.length, amt: rs.reduce((s, r) => s + r.amt, 0), tax: rs.reduce((s, r) => s + r.tax, 0) }); const sc = S(cashR), sk = S(crdR), sa = S(cardRows);
  const f16 = tbl('신용카드매출전표등 수령명세서(갑) — 2. 신용카드 등 매입명세 합계 (별지 제16호서식(1))', ['구분', '거래건수', '공급가액', '세액'],
    `<tr class="total"><th scope="row">④ 합계</th><td>${sa.n}</td><td>${fmt(sa.amt)}</td><td>${fmt(sa.tax)}</td></tr><tr><th scope="row">⑤ 현금영수증</th><td>${sc.n}</td><td>${fmt(sc.amt)}</td><td>${fmt(sc.tax)}</td></tr><tr><th scope="row">⑥ 화물운전자복지카드</th><td colspan="3" class="note">해당 없음</td></tr><tr><th scope="row">⑦ 사업용 신용카드 <span class="note">홈택스에 등록한 카드면 자동 집계 — 등록하지 않은 카드는 ⑧에 가맹점별로</span></th><td>${sk.n}</td><td>${fmt(sk.amt)}</td><td>${fmt(sk.tax)}</td></tr><tr><th scope="row">⑧ 그 밖의 신용카드 등 — 3. 가맹점별 명세</th><td colspan="3" class="note">등록 안 한 카드 지출은 아래 공급자별 합계를 옮김</td></tr>`)
    + (crdR.length ? `<details class="vat-more"><summary>카드 지출 공급자(가맹점)별 ${aggregate(crdR).length}곳 — ⑧ 명세에 쓸 때</summary>${tbl('3. 그 밖의 신용카드 등 거래명세 합계(가맹점별)', ['⑩ 공급자(가맹점) 사업자등록번호', '가맹점', '거래건수', '공급가액', '세액'], aggregate(crdR).map(a => `<tr><td>${esc(a.sreg || '—')}</td><th scope="row">${esc(a.name)}</th><td>${a.n}</td><td>${fmt(a.amt)}</td><td>${fmt(a.tax)}</td></tr>`).join(''))}</details>` : '');
  /* ── ④ 공제받지 못할 매입세액 명세서 ── */
  const noRows = used.filter(u => u.inv && u.r.v === 'no').map(u => u.r); const reason = (r: LedgerRow) => r.what === 'car_pass' ? '③' : r.what === 'guest' ? '④' : r.what === 'land' ? '⑥' : '⑤';
  const RS: [string, string][] = [['①', '필요적 기재사항 누락 등'], ['②', '사업과 직접 관련 없는 지출'], ['③', '개별소비세법 제1조 제2항 제3호 자동차 구입·유지·임차'], ['④', '기업업무추진비 및 이와 유사한 비용 관련'], ['⑤', '면세사업등 관련'], ['⑥', '토지의 자본적 지출 관련'], ['⑦', '사업자등록 전 매입세액'], ['⑧', '금·구리 스크랩 거래계좌 미사용 관련']];
  const byR = (k: string) => S(noRows.filter(r => reason(r) === k));
  const f22a = tbl('공제받지 못할 매입세액 명세서 — 2. 공제받지 못할 매입세액 명세 (별지 제22호서식)', ['불공제 사유', '매수', '공급가액', '매입세액'], RS.map(([k, n]) => { const s = byR(k); return `<tr><th scope="row">${k} ${n}</th><td>${s.n || ''}</td><td>${W(s.amt)}</td><td>${W(s.tax)}</td></tr>`; }).join('') + `<tr class="total"><th scope="row">⑨ 합계 → (53)</th><td>${noRows.length}</td><td>${fmt(S(noRows).amt)}</td><td>${fmt(S(noRows).tax)}</td></tr>`);
  const gUse = groups.filter(g => g.common_tax || g.nondeduct);
  const f22b = gUse.length ? tbl('3. 공통매입세액 안분 계산 명세', ['번호', '등록 단위', '⑩ 공통매입 공급가액', '⑪ 세액', '⑫ 총공급가액 등', '⑬ 면세공급가액 등', '⑭ 불공제 매입세액 ⑪×(⑬÷⑫)'], gUse.map((g, i) => { const pi = x.prelimIn[g.key]; const fullT = g.taxable + (P.kind === 'F' ? pi?.taxable ?? 0 : 0), fullE = g.exempt + (P.kind === 'F' ? pi?.exempt ?? 0 : 0), fullC = g.common_tax + (P.kind === 'F' ? pi?.common ?? 0 : 0); const nd = g.skipped && !g.skipped.includes('안분(') ? 0 : Math.floor(fullC * g.ratio); return `<tr><td>${i + 1}</td><th scope="row">${esc(g.name)}${g.basis && g.basis !== 'supply' ? ` <span class="note">(${esc(g.skipped ?? '')})</span>` : ''}</th><td>${fmt(fullC * 10)}</td><td>${fmt(fullC)}</td><td>${fmt(fullT + fullE)}</td><td>${fmt(fullE)}</td><td>${fmt(nd)}</td></tr>`; }).join('')) + `<p class="meta">⑩ 공급가액은 세액 × 10으로 어림(공통 지출의 공급가액 합계로 바꿔 적어도 됨). 안분 생략 기준(5%·500만 원·5만 원)에 든 단위는 ⑭ 0.${P.kind === 'F' ? ' 확정신고는 6개월 전체 값.' : ''}</p>` : '<p class="meta">공통매입세액이 없어 3.~4. 명세는 비웁니다.</p>';
  const f22c = P.kind === 'F' && gUse.length ? tbl('4. 공통매입세액의 정산 명세(확정신고)', ['번호', '등록 단위', '⑮ 총공통매입세액', '⑯ 면세사업등 확정비율', '⑰ 불공제 매입세액 총액 ⑮×⑯', '⑱ 기 불공제 매입세액(예정)', '⑲ 가산 또는 공제되는 매입세액 ⑰−⑱'], gUse.map((g, i) => { const pi = x.prelimIn[g.key]; const fullC = g.common_tax + (pi?.common ?? 0); const total = Math.floor(fullC * g.ratio); return `<tr><td>${i + 1}</td><th scope="row">${esc(g.name)}</th><td>${fmt(fullC)}</td><td>${pct(g.ratio)}</td><td>${fmt(total)}</td><td>${fmt(pi?.nondeduct ?? 0)}</td><td>${fmt(total - (pi?.nondeduct ?? 0))}</td></tr>`; }).join('')) : '';
  const f22d = recalc.length ? tbl('5. 납부세액 또는 환급세액 재계산 명세', ['번호', '자산', '해당 재화의 매입세액', '경감률 1−(5/100 또는 25/100 × 경과 과세기간 수)', '증가 또는 감소된 면세 비율', '가산(+) 또는 공제(−)되는 매입세액'], recalc.map((r, i) => `<tr><td>${i + 1}</td><th scope="row">${esc(r.a.facility)} ${esc(r.a.desc)} (${r.from} 취득)</th><td>${fmt(r.a.tax)}</td><td>${pct(Math.max(0, 1 - (r.a.kind === 'building' ? 0.05 : 0.25) * r.n))}</td><td>${(r.ratio - r.a.ratio0) >= 0 ? '+' : ''}${pct(r.ratio - r.a.ratio0)}</td><td>${r.amt >= 0 ? '+' : ''}${fmt(r.amt)}</td></tr>`).join('') + `<tr class="total"><td></td><th scope="row">합계 → (54)에 합산</th><td colspan="3"></td><td>${fmt(recalc.reduce((s, r) => s + r.amt, 0))}</td></tr>`) : '';
  /* ── ⑤ 부동산임대공급가액명세서 ── */
  const depF = facs.filter(f => f.deposit);
  const f25 = depF.length ? tbl('부동산임대공급가액명세서 — 임대수입금액(과세표준) (별지 제25호서식)', ['① 부동산(시설)', '⑭ 보증금', '⑮ 월 임대료(기간 합)', '보증금 이자(간주임대료, 시행령 제65조)', '⑱ 합계 → (4)에 포함'], depF.map(f => { const s = sales[f.id]; return `<tr><th scope="row">${esc(f.name)}</th><td>${s?.dep ? fmt(s.dep) : '<span class="note">2절 간주임대료 계산기에 넣은 값</span>'}</td><td class="note">임대료 수입은 (1)(3)(4)에 넣은 값에서 임대 몫만 — 홈택스에서 임차인별로</td><td>${s?.deem ? fmt(s.deem) : ''}</td><td>${s?.deem ? fmt(s.deem) : ''}</td></tr>`; }).join('')) + '<p class="meta">임차인 상호·등록번호·입주일·면적은 임대차 계약서에서 홈택스에 직접 적습니다(개인 임차인의 주민등록번호는 이 도구에 넣지 않습니다).</p>' : '';
  /* ── ⑥ 과세사업전환 감가상각자산 신고서 ── */
  const f17 = conv.length ? tbl('과세사업전환 감가상각자산 신고서 — 3. 감가상각자산명세서 (별지 제17호서식) → 신고서 (48)', ['구분(건물·구축물·기타)', '수량', '취득 과세기간', '면세사업등 관련 불공제세액', '경과 과세기간', '과세사업 전환 공제매입세액'], conv.map(cv => `<tr><th scope="row">${cv.kind === 'building' ? '건물·구축물' : '기타'} — ${esc(cv.desc)}</th><td>1</td><td>${cv.acq}</td><td>${fmt(cv.tax)}</td><td>${cv.n}</td><td>${fmt(cv.credit)}${cv.common ? ` <span class="note">(과세 비율 ${pct(convRatio)})</span>` : ''}</td></tr>`).join('') + `<tr class="total"><th scope="row">합계 → (48)</th><td colspan="4"></td><td>${fmt(conv.reduce((s, v) => s + v.credit, 0))}</td></tr>`) + '<p class="meta">과세사업 사용·소비 시기(전환일)와 전환 전 면세사업자 인적사항은 홈택스 서식에 직접 적습니다. 확정신고와 함께 냅니다(시행령 제85조 제5항).</p>' : '';
  /* ── ⑦ 홈택스 입력 순서 ── */
  const steps = [
    ['기본정보', '홈택스 → 신고/납부 → 부가가치세 → 일반과세자 → ' + (P.kind === 'P' ? '예정신고' : '확정신고') + ' → 사업자등록번호·신고기간 확인', `등록번호 ${org.unit === 'entity' ? esc(org.reg_no || '—') : '시설(사업장)별'} · ${esc(P.name)}`],
    ['매출', '과세표준 및 매출세액: (1) 세금계산서 발급분은 「전자세금계산서 불러오기」로 자동, (3)(4)는 직접 입력, 보증금 시설은 부동산임대공급가액명세서 작성', `(1) ${fmt(c('1').amt)} · (3) ${fmt(c('3').amt)} · (4) ${fmt(c('4').amt)}`],
    ['매입 ①', '매입처별 세금계산서합계표 「작성하기」: 전자분은 불러오기 → 위 ② 총합계와 맞춰 봄, 종이분은 3. 명세를 공급자별로 입력 → (10)(12)에 반영', `전자 ${te.cnt}매 ${fmt(te.tax)} · 종이 ${tp.cnt}매 ${fmt(tp.tax)}`],
    ['매입 ②', '그 밖의 공제매입세액 (15) 「작성하기」: 신용카드매출전표등 수령명세서(사업용 카드 불러오기, 그 밖 카드는 가맹점별) → (44)(45)' + (conv.length ? '; 과세사업전환 매입세액 → (48)(별도 신고서 첨부)' : ''), `(44) ${fmt(c('44').tax)} · (45) ${fmt(c('45').tax)}` + (conv.length ? ` · (48) ${fmt(c('48').tax)}` : '')],
    ['매입 ③', '공제받지 못할 매입세액 (17) 「작성하기」: 사유별 명세 → (53), 공통매입세액 안분' + (P.kind === 'F' ? '·정산' : '') + (recalc.length ? '·재계산' : '') + ' → (54)', `(53) ${fmt(c('53').tax)} · (54) ${fmt(c('54').tax)}`],
    ...(P.kind === 'F' ? [['누락분', '예정신고 누락분 (7)(13): 4쪽 명세 (36)~(43)에 예정 때 빠진 것을 적음', `(13) ${fmt(c('13').tax)}`]] : []),
    ['경감·공제·가산세', '(19)~(29): 전자신고 세액공제(57) 등 경감·공제, 예정고지세액(24), 가산세(64)~(84)는 이 도구 범위 밖 — 홈택스 안내대로', '—'],
    ['제출', '신고서 미리보기에서 위 표와 칸마다 맞춰 본 뒤 제출 → 접수증 저장 → 납부서(또는 환급 계좌) 확인 → 신고 기록 저장(이 화면 아래 단추)', `㉰ ${fmt(pay)}`]];
  const order = tbl('홈택스 입력 순서 — 어느 서류를 먼저 쓰면 어느 칸이 채워지나', ['순서', '홈택스에서 할 일', '이 표의 값'], steps.map((s, i) => `<tr><td>${i + 1}. ${esc(s[0])}</td><td>${s[1]}</td><td>${s[2]}</td></tr>`).join(''));
  return `<div class="section-head"><h2>4. ${esc(P.name)} — 신고서 모양 결과</h2><span class="meta">참고용 · 부가가치세법 시행규칙 별지 서식의 칸 배치·번호(${esc(D.form_version ?? '2026-04-01')} 시행 판, 제21호서식 2026-03-20 개정)를 따름 · 홈택스 화면이 아님</span></div>
    <p class="meta">이 도구가 채우는 칸은 값이 있고, 못 채우는 칸은 '홈택스에서 직접' 또는 '해당 없음이면 비움'입니다. 원 미만 버림. 표 아래 「한글 표 복사」로 결재 문서에 붙일 수 있습니다.</p>
    ${p1}${p4}
    <h3>부속서류 — 홈택스 '작성하기' 순서대로</h3>
    <h4>② 매입처별 세금계산서합계표</h4>${f39}
    <h4>③ 신용카드매출전표등 수령명세서</h4>${f16}
    <h4>④ 공제받지 못할 매입세액 명세서</h4>${f22a}${f22b}${f22c}${f22d}
    ${depF.length ? `<h4>⑤ 부동산임대공급가액명세서</h4>${f25}` : ''}${conv.length ? `<h4>⑥ 과세사업전환 감가상각자산 신고서</h4>${f17}` : ''}
    <h3>⑦ 홈택스 입력 순서</h3>${order}`;
}
