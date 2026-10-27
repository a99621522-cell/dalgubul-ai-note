/** /vat/ 시작 화면 — 다음 신고 기한·인계 마감 D-day 와 이 브라우저의 설정 상태(서버 없음) */
import { $, getOrg, allLedgers, getFilings, nextFiling, handoverDue, ymd, esc, fmt, loadData } from './vat_rules';
const dd = $('dday');
if (dd) {
  const now = new Date(); const f = nextFiling(now); const org = getOrg();
  const parts = [`<span>다음 신고 <b>${esc(f.name)}</b> ${ymd(f.due)} · <b>D-${f.days}</b></span>`];
  const next11 = new Date(now.getFullYear(), now.getMonth() + 1, 11); parts.push(`<span>지난달 전자세금계산서 전송 기한 <b>${ymd(next11)}</b></span>`);
  if (org) { const h = handoverDue(org.handover_day || 5, now); parts.push(`<span>인계표 마감 <b>${ymd(h.due)}</b> · D-${h.days}</span>`); }
  dd.innerHTML = parts.join('');
  const a = $('role-a-state'), b = $('role-b-state');
  const n = Object.values(allLedgers()).reduce((s, r) => s + r.length, 0);
  if (a) a.textContent = org ? `이 브라우저 기록 ${n}건 · 시설 ${org.facilities.length}곳` : '③ 기관 설정을 먼저 하면 시설을 고를 수 있습니다';
  if (b) b.textContent = org ? `이 브라우저의 설정: ${org.org} · ${org.created} 저장 — 고치려면 누르고, 신고 때는 '신고 준비'로` : '아직 설정이 없습니다 — 5문항, 약 10분';
}

/* 절감 요약 — 이 브라우저 기록만으로(운영자 2026-10-27 '절감이 목적이야'): ① 발굴 후보 수(과세사업 찾기 답) ② 수정세금계산서를 받으면 살아나는 세액(다른 명의 빨강, 기한 안) ③ 확인하면 살아날 수 있는 세액(노랑) ④ 최근 신고 기록의 공통매입세액 면세분(전용 분리로 줄일 수 있는 상한). 평가 아님 */
const sv = $('sv-sum');
if (sv) {
  const D = loadData(); const today = ymd(new Date()); const rows = Object.values(allLedgers()).flat();
  let cand = 0; try { const a = JSON.parse(localStorage.getItem('vat-discover-v1') || '{}') as Record<string, string>; cand = (D?.revenue_items ?? []).filter(i => i.status === 'taxable' && a[i.key] === 'unfiled').length; } catch { /* */ }
  const fixable = rows.filter(r => r.v === 'no' && r.payee === 'contractor' && !r.done && (!r.fix_due || r.fix_due >= today)); const fixTax = fixable.reduce((s, r) => s + r.tax, 0);
  const expired = rows.filter(r => r.v === 'no' && r.payee === 'contractor' && !r.done && r.fix_due && r.fix_due < today).reduce((s, r) => s + r.tax, 0);
  const pend = rows.filter(r => r.v === 'check' && !r.done); const pendTax = pend.reduce((s, r) => s + r.tax, 0);
  const fl = Object.values(getFilings()).sort((a, b) => b.period.localeCompare(a.period))[0]; const nd = fl ? fl.groups.reduce((s, g) => s + Math.max(0, g.nondeduct), 0) : 0;
  const items = [
    `<li>길 1 — 과세사업 찾기에서 '과세인데 신고 안 함'으로 표시한 수입 <b>${cand}</b>개 ${cand ? '→ <a href="/vat/discover/">등록·신고 검토</a>' : '(<a href="/vat/discover/">점검표</a>를 아직 안 채웠거나 후보 없음)'}</li>`,
    `<li>길 2 — 다른 명의 세금계산서로 빠진 세액 <b>${fmt(fixTax)}</b>원(${fixable.length}건, 수정세금계산서 기한 안) → 공급자에게 수정 요청하면 살아납니다${expired ? ` · 기한 지남 ${fmt(expired)}원은 착오 정정이 아니면 불가` : ''}; 확인 필요(노랑) <b>${fmt(pendTax)}</b>원(${pend.length}건) → 귀속·공급자 확인</li>`,
    `<li>길 3 — ${fl ? `최근 신고 기록(${fl.period})의 공통매입세액 면세분 <b>${fmt(nd)}</b>원 → 전용 분리·비율 관리로 줄일 수 있는 상한(<a href="/vat/prepare/">절감 분석</a>)` : '신고 기록이 없어 공통매입세액 면세분을 아직 셀 수 없습니다(<a href="/vat/prepare/">신고 준비</a>에서 저장)'}</li>`,
    `<li>길 4 — 지난 5년 빠진 매입세액은 <a href="/vat/review/">지난 신고 점검</a>에 홈택스 매입 목록을 붙여넣어야 계산됩니다(저장하지 않음)</li>`];
  sv.innerHTML = `<ul class="meta-list">${items.join('')}</ul><p class="note">이 숫자는 이 브라우저에 있는 기록만으로 센 것이고, 공제 여부의 최종 판단은 신고인 몫입니다.</p>`;
}
