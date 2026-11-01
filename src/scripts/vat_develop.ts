/** /vat/develop/ 공영개발·분양 사업(세무회계법인 2차 4번 — 지자체 부가세에서 가장 큰 금액: 산업단지·택지 조성, 공설시장·지식산업센터 분양).
 *  토지 분양 면세(법 제26조 제1항 제14호)·건물 분양 과세, 토지 관련 매입세액 불공제(법 제39조 제1항 제7호), 공통비는 예정공급가액 비율(영 제81조 제4항 제2호)→정산(제82조),
 *  중간지급조건부 공급시기(영 제28조 제3항 제3호·시행규칙 제18조), 조기환급(법 제59조 제2항·영 제107조). 과세기간별 매입·매출세액 흐름표와 점검표. 조문·산수만, 평가 없음. 주택(조특법 면세)은 다루지 않음 */
import { $, esc, num, fmt, pct, loadData, lawLink, earlyRefundSchedule, periodKeyOf, periodInfo, downloadText, toCsv, ymd, monthStr, type Data } from './vat_rules';
type Dev = { name: string; landSale: number; bldSale: number; landCost: number; bldCost: number; common: number; start: string; end: string; contractM: string; contractP: number; midN: number; midP: number; every: 1 | 2 | 0; checks: Record<string, boolean>; saved: string };
export const DEV_KEY = 'vat-develop-v1';
export const getDevs = (): Dev[] => { try { const v = JSON.parse(localStorage.getItem(DEV_KEY) || '[]'); return Array.isArray(v) ? v : []; } catch { return []; } };
const setDevs = (a: Dev[]) => { try { localStorage.setItem(DEV_KEY, JSON.stringify(a)); } catch { /* */ } };
const CHECKS: { stage: string; id: string; text: string; basis: { law: 'act' | 'decree' | 'rule'; art: string } }[] = [
  { stage: '계획', id: 'p1', text: '분양 계약서에 토지 가액과 건물 가액을 따로 적는다(다른 법령에 따른 구분이면 실지거래가액, 아니면 기준시가·감정가액 비례 안분과 30% 차이 검증)', basis: { law: 'act', art: '제29조' } },
  { stage: '계획', id: 'p2', text: '조성 공사 내역을 토지 관련(부지 조성·토목·형질변경·철거)과 건물·구축물로 나눠 발주·계약한다', basis: { law: 'act', art: '제39조' } },
  { stage: '계획', id: 'p3', text: '설계·감리·기반시설·판촉처럼 토지·건물에 함께 드는 공통비는 예정공급가액(토지 면세 / 건물 과세) 비율로 안분할 근거(분양 계획서)를 둔다', basis: { law: 'decree', art: '제81조' } },
  { stage: '계획', id: 'p4', text: '사업 특별회계(공영개발)의 사업자등록 또는 사업장 추가를 첫 세금계산서 전에 마친다', basis: { law: 'act', art: '제39조' } },
  { stage: '조성', id: 'c1', text: '조성·건축 중 매월 또는 매 2월 조기환급 신고(기간 끝 +25일)와 감가상각자산 취득명세서 첨부', basis: { law: 'decree', art: '제107조' } },
  { stage: '조성', id: 'c2', text: '토지 관련 세금계산서는 불공제로 적고(공제받지 못할 매입세액 명세서 ⑥), 건물분만 공제한다', basis: { law: 'act', art: '제39조' } },
  { stage: '분양', id: 's1', text: '계약금 뒤 인도까지 6개월 이상이고 중도금을 나눠 받으면 중간지급조건부 — 대가를 받기로 한 날마다 건물분 세금계산서를 발급하고 매출세액을 신고한다', basis: { law: 'rule', art: '제18조' } },
  { stage: '분양', id: 's2', text: '토지분은 면세 공급가액(계산서)으로 신고하고, 그 과세기간 면세비율이 커지므로 같은 단위의 공통매입세액 안분에 반영한다', basis: { law: 'act', art: '제26조' } },
  { stage: '정산', id: 'f1', text: '분양 공급가액이 확정되는 과세기간의 확정신고에서 예정공급가액 안분을 정산한다', basis: { law: 'decree', art: '제82조' } },
  { stage: '정산', id: 'f2', text: '미분양 토지·건물의 임대·사용허가로 바뀌면 과세·면세 구분과 재계산(감가상각자산)을 다시 본다', basis: { law: 'decree', art: '제83조' } }];
const D = loadData();
if (D && $('dv-form')) init(D);
function init(D: Data) {
  const DV = D.rules.develop; const g = (k: string) => $<HTMLInputElement | HTMLSelectElement>(k)!;
  if (!(g('dv-start') as HTMLInputElement).value) { g('dv-start').value = monthStr(); const e = new Date(); e.setMonth(e.getMonth() + 23); g('dv-end').value = monthStr(e); g('dv-cm').value = monthStr(new Date(new Date().setMonth(new Date().getMonth() + 6))); }
  const read = (): Dev => { const cur = getDevs().find(p => p.name === g('dv-name').value.trim()); return { name: g('dv-name').value.trim() || '(이름 없음)', landSale: num(g('dv-ls').value), bldSale: num(g('dv-bs').value), landCost: num(g('dv-lc').value), bldCost: num(g('dv-bc').value), common: num(g('dv-cc').value), start: g('dv-start').value, end: g('dv-end').value, contractM: g('dv-cm').value, contractP: num(g('dv-cp').value), midN: num(g('dv-mn').value), midP: num(g('dv-mp').value), every: Number(g('dv-every').value) as 0 | 1 | 2, checks: cur?.checks ?? {}, saved: ymd(new Date()) }; };
  const fill = (p: Dev) => { g('dv-name').value = p.name; g('dv-ls').value = p.landSale ? fmt(p.landSale) : ''; g('dv-bs').value = p.bldSale ? fmt(p.bldSale) : ''; g('dv-lc').value = p.landCost ? fmt(p.landCost) : ''; g('dv-bc').value = p.bldCost ? fmt(p.bldCost) : ''; g('dv-cc').value = p.common ? fmt(p.common) : ''; g('dv-start').value = p.start; g('dv-end').value = p.end; g('dv-cm').value = p.contractM; g('dv-cp').value = String(p.contractP); g('dv-mn').value = String(p.midN); g('dv-mp').value = String(p.midP); g('dv-every').value = String(p.every); };
  const renderSaved = () => { $<HTMLSelectElement>('dv-saved')!.innerHTML = '<option value="">— 저장된 사업 —</option>' + getDevs().map(p => `<option value="${esc(p.name)}">${esc(p.name)} (${p.saved})</option>`).join(''); };
  $<HTMLSelectElement>('dv-saved')?.addEventListener('change', e => { const p = getDevs().find(x => x.name === (e.target as HTMLSelectElement).value); if (p) { fill(p); run(); } });
  $('dv-run')?.addEventListener('click', run); $('dv-save')?.addEventListener('click', () => { const p = read(); setDevs([...getDevs().filter(x => x.name !== p.name), p]); renderSaved(); run(); $('dv-msg')!.textContent = `'${p.name}' 저장.`; });
  $('dv-del')?.addEventListener('click', () => { const n = g('dv-name').value.trim(); if (!n || !confirm(`'${n}' 저장을 지웁니다.`)) return; setDevs(getDevs().filter(x => x.name !== n)); renderSaved(); });
  $('dv-print')?.addEventListener('click', () => window.print());
  const toN = (m: string) => Number(m.slice(0, 4)) * 12 + Number(m.slice(5, 7)) - 1; const toM = (n: number) => `${Math.floor(n / 12)}-${String(n % 12 + 1).padStart(2, '0')}`;
  function run() {
    const p = read(); const out = $('dv-result')!; const sale = p.landSale + p.bldSale; const taxShare = sale ? p.bldSale / sale : 0;   // 예정공급가액 비율(과세 = 건물)
    const tLand = Math.floor(p.landCost * 0.1), tBld = Math.floor(p.bldCost * 0.1), tCom = Math.floor(p.common * 0.1);
    const comDed = Math.floor(tCom * taxShare), comNo = tCom - comDed; const ded = tBld + comDed, no = tLand + comNo; const outTax = Math.floor(p.bldSale * 0.1);
    /* 과세기간별 흐름: 매입은 공사 기간 균등, 매출은 계약금(계약 달)·중도금(계약 달과 준공 달 사이 균등)·잔금(준공 달) × 건물 분양가 × 10% */
    const a = toN(p.start), b = toN(p.end); const months = b >= a ? b - a + 1 : 0; const inPer = months ? ded / months : 0;
    const flow = new Map<string, { inTax: number; outTax: number }>(); const addF = (m: string, i: number, o: number) => { const k = periodKeyOf(m); const x = flow.get(k) ?? { inTax: 0, outTax: 0 }; x.inTax += i; x.outTax += o; flow.set(k, x); };
    for (let i = a; i <= b; i++) addF(toM(i), inPer, 0);
    const cm = p.contractM ? toN(p.contractM) : a; const restP = Math.max(0, 100 - p.contractP - p.midP); if (p.bldSale) { addF(toM(cm), 0, Math.floor(outTax * p.contractP / 100)); if (p.midN > 0 && p.midP > 0) { const span = Math.max(1, b - cm); for (let j = 1; j <= p.midN; j++) addF(toM(Math.min(b, cm + Math.round(span * j / (p.midN + 1)))), 0, Math.floor(outTax * p.midP / 100 / p.midN)); } addF(toM(b), 0, Math.floor(outTax * restP / 100)); }
    const keys = [...flow.keys()].sort(); let cum = 0;
    const sched = p.every ? earlyRefundSchedule(p.start, p.end, p.every, D) : [];
    out.innerHTML = `<div class="section-head"><h2>결과 — ${esc(p.name)}</h2><span class="meta">참고용 · 공사비 균등 집행 가정 · 주택 분양(조특법 면세)은 제외</span></div>
      <div class="vc-card"><h3>매입세액 갈래</h3>${tbl('공제·불공제 (예정공급가액 비율 = 건물 분양가 ÷ 전체 분양가 = ' + pct(taxShare) + ')', ['구분', '공급가액', '세액', '처리'], `
        <tr><th scope="row">토지 관련 공사(조성·토목·철거)</th><td>${fmt(p.landCost)}</td><td>${fmt(tLand)}</td><td class="note">불공제 — 법 제39조 제1항 제7호</td></tr>
        <tr><th scope="row">건물·구축물 건축</th><td>${fmt(p.bldCost)}</td><td>${fmt(tBld)}</td><td class="note">과세 분양분 공제(주택이면 조특법 확인)</td></tr>
        <tr><th scope="row">공통(설계·감리·기반시설·판촉)</th><td>${fmt(p.common)}</td><td>${fmt(tCom)}</td><td class="note">예정공급가액 비율 ${pct(taxShare)} 공제 ${fmt(comDed)} · 불공제 ${fmt(comNo)} → 분양 확정 과세기간에 정산(영 제82조)</td></tr>
        <tr class="total"><th scope="row">공제 예상</th><td></td><td>${fmt(ded)}</td><td class="note">조기환급 대상(매출세액과 상계 뒤)</td></tr>
        <tr class="total"><th scope="row">불공제 예상</th><td></td><td>${fmt(no)}</td><td class="note">사업비(원가)에 들어감</td></tr>
        <tr class="total"><th scope="row">건물 분양 매출세액</th><td>${fmt(p.bldSale)}</td><td>${fmt(outTax)}</td><td class="note">토지 분양 ${fmt(p.landSale)}은 면세(계산서)</td></tr>`)}
      <ul class="meta-list"><li>${esc(DV?.land_sale ?? '')}</li><li>${esc(DV?.land_cost ?? '')}</li></ul></div>
      <div class="vc-card"><h3>과세기간별 흐름 — 환급에서 납부로 바뀌는 때</h3>${tbl('매입세액(공제분)·매출세액·차액 (중간지급조건부: 계약금 ' + p.contractP + '% · 중도금 ' + p.midN + '회 ' + p.midP + '% · 잔금 ' + restP + '%)', ['과세기간', '매입세액(공제)', '매출세액(건물 분양)', '차액(− 환급 / + 납부)', '누적', '조기환급'], keys.map(k => { const x = flow.get(k)!; const d = x.outTax - x.inTax; cum += d; return `<tr><th scope="row">${periodInfo(k).name.replace('신고', '')}</th><td>${fmt(Math.floor(x.inTax))}</td><td>${fmt(x.outTax)}</td><td>${d < 0 ? `−${fmt(Math.floor(-d))}` : fmt(Math.floor(d))}</td><td>${cum < 0 ? `−${fmt(Math.floor(-cum))}` : fmt(Math.floor(cum))}</td><td class="note">${d < 0 && p.every && k <= periodKeyOf(p.end) ? '조기환급 신고 가능(설비)' : d < 0 ? '예정·확정 환급' : '납부'}</td></tr>`; }).join(''))}
      <ul class="meta-list"><li>${esc(DV?.timing ?? '')}</li><li>${esc(DV?.refund ?? '')}</li></ul>
      ${sched.length ? `<details class="vat-more"><summary>조기환급 신고 ${sched.length}회 일정(매 ${p.every}개월)</summary>${tbl('조기환급 — 기간 끝 +25일 신고, +15일 환급', ['기간', '신고기한', '환급 기한'], sched.map(r => `<tr><th scope="row">${r.from}${r.to !== r.from ? `~${r.to}` : ''}</th><td>${r.fileDue}</td><td>${r.refundBy}</td></tr>`).join(''))}</details>` : ''}</div>
      <div class="vc-card"><h3>계획 → 조성 → 분양 → 정산 점검표</h3>${['계획', '조성', '분양', '정산'].map(st => `<h4>${st}</h4><ul class="checks">${CHECKS.filter(c => c.stage === st).map(c => `<li><label><input type="checkbox" data-chk="${c.id}" ${p.checks[c.id] ? 'checked' : ''}/> <span>${esc(c.text)}</span> <span class="note">${lawLink(D, c.basis)}</span></label></li>`).join('')}</ul>`).join('')}
      <p class="meta">${esc(DV?.housing ?? '')} 근거: ${(DV?.basis ?? []).map(b => lawLink(D, b)).join(' · ')}</p></div>
      <div class="actions no-print"><button type="button" class="btn secondary" id="dv-csv">흐름표·점검표 CSV</button></div>`;
    out.querySelectorAll<HTMLInputElement>('[data-chk]').forEach(c => c.addEventListener('change', () => { const ps = getDevs(); const cur = ps.find(x => x.name === p.name); if (!cur) { $('dv-msg')!.textContent = '체크를 남기려면 먼저 「저장」을 누르세요.'; return; } cur.checks[c.dataset.chk!] = c.checked; setDevs(ps); }));
    $('dv-csv')?.addEventListener('click', () => { let c2 = 0; downloadText(`공영개발-${p.name}.csv`, toCsv([['사업', p.name], ['공제 예상', ded, '불공제 예상', no, '건물 분양 매출세액', outTax], [], ['과세기간', '매입세액(공제)', '매출세액', '차액', '누적'], ...keys.map(k => { const x = flow.get(k)!; const d = x.outTax - x.inTax; c2 += d; return [periodInfo(k).name, Math.floor(x.inTax), x.outTax, Math.floor(d), Math.floor(c2)]; }), [], ['단계', '점검 항목', '확인'], ...CHECKS.map(c => [c.stage, c.text, p.checks[c.id] ? '예' : ''])]), 'text/csv;charset=utf-8'); });
  }
  renderSaved();
}
const tbl = (cap: string, head: string[], body: string) => `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table form" data-stack="off"><caption>${cap}</caption><thead><tr>${head.map(h => `<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;
