/** 가산세 어림 계산기(세무회계법인 관점 검토 2026-10-27, 4번 — 줄인 만큼 지키기): 과소신고·무신고 세액과 법정신고기한·낼 날 → 과소신고(10%)·무신고(20%) 가산세, 수정신고·기한후신고 감면(국세기본법 제48조 제2항), 납부지연(1일 22/100,000). 경정청구(돌려받는 쪽)에는 가산세가 없다. 조문 값만, 평가 없음 */
import { $, esc, num, fmt, pct, loadData, lawLink, penaltyCalc, periodInfo, ymd } from './vat_rules';
const D = loadData(); const box = $('pn-box');
if (D && box) {
  const R = D.rules.penalty; const now = new Date(); const keys: string[] = []; for (let y = now.getFullYear() - 5; y <= now.getFullYear(); y++) for (const k of ['1P', '1F', '2P', '2F']) keys.push(`${y}-${k}`);
  box.innerHTML = `<form class="vc-form no-print" id="pn-form" autocomplete="off" onsubmit="return false"><p class="q-title full">가산세 어림 — 덜 낸 세액이 있을 때(경정청구에는 없음)</p>
    <label>신고 종류 <select id="pn-kind"><option value="under">신고는 했지만 덜 냄(과소신고 → 수정신고)</option><option value="none">신고 안 함(무신고 → 기한후신고)</option></select></label>
    <label>과세기간(법정신고기한) <select id="pn-period">${keys.filter(k => periodInfo(k).due <= ymd(now)).reverse().map(k => `<option value="${k}">${periodInfo(k).name} (기한 ${periodInfo(k).due})</option>`).join('')}</select></label>
    <label>덜 낸 세액(원) <input type="text" id="pn-tax" inputmode="numeric" placeholder="예: 3,000,000" /></label>
    <label>수정신고·납부할 날 <input type="date" id="pn-date" value="${ymd(now)}" /></label>
    <div class="actions"><button type="button" class="btn secondary" id="pn-run">계산</button></div></form><div id="pn-out"></div>`;
  $('pn-run')!.addEventListener('click', () => {
    const kind = ($<HTMLSelectElement>('pn-kind')!).value as 'under' | 'none'; const key = ($<HTMLSelectElement>('pn-period')!).value; const tax = num(($<HTMLInputElement>('pn-tax')!).value); const pay = ($<HTMLInputElement>('pn-date')!).value || ymd(now);
    if (!tax) { $('pn-out')!.innerHTML = '<p class="callout info">덜 낸 세액을 넣으세요.</p>'; return; }
    const P = periodInfo(key); const r = penaltyCalc(D, { tax, due: P.due, payDate: pay, kind });
    $('pn-out')!.innerHTML = `<div class="scroll-x"><table class="data-table vat-table form" data-stack="off"><caption>가산세 어림 — ${esc(P.name)} 덜 낸 세액 ${fmt(tax)}원을 ${pay}에 ${kind === 'none' ? '기한후신고' : '수정신고'}·납부할 때</caption><thead><tr><th scope="col">항목</th><th scope="col">계산</th><th scope="col">금액</th></tr></thead><tbody>
      <tr><th scope="row">${kind === 'none' ? '무신고 가산세(제47조의2)' : '과소신고 가산세(제47조의3)'}</th><td>${fmt(tax)} × ${pct(r.rateFile)}</td><td>${fmt(r.file)}</td></tr>
      <tr><th scope="row">${kind === 'none' ? '기한후신고 감면(제48조 제2항 제2호)' : '수정신고 감면(제48조 제2항 제1호)'}</th><td>법정신고기한 뒤 ${r.months}개월째 → ${r.relief ? `${pct(r.relief)} 감면` : '감면 없음(기한 경과)'}</td><td>−${fmt(r.file - r.fileAfter)}</td></tr>
      <tr><th scope="row">납부지연 가산세(제47조의4)</th><td>${fmt(tax)} × ${r.days}일 × 22/100,000</td><td>${fmt(r.late)}</td></tr>
      <tr class="total"><th scope="row">가산세 합계(어림)</th><td>본세 ${fmt(tax)} 별도</td><td>${fmt(r.total)}</td></tr></tbody></table></div>
      <ul class="meta-list"><li>${esc(R?.note ?? '')}</li><li>부정행위(40%)·영세율 과세표준 가산·지정납부기한 뒤 3% 가산(제47조의4 제1항 제3호)은 넣지 않았습니다. 예정신고 때 과소신고분을 확정신고기한까지 수정신고하면 감면이 다릅니다(제48조 제2항 제3호 다목).</li><li>근거: ${(R?.basis ?? []).map(b => lawLink(D, b)).join(' · ')}</li></ul>`;
  });
}
