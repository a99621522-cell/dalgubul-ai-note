/** /vat/ 시작 화면 — 다음 신고 기한·인계 마감 D-day 와 이 브라우저의 설정 상태(서버 없음) */
import { $, getOrg, allLedgers, nextFiling, handoverDue, ymd, esc } from './vat_rules';
const dd = $('dday');
if (dd) {
  const now = new Date(); const f = nextFiling(now); const org = getOrg();
  const parts = [`<span>다음 신고 <b>${esc(f.name)}</b> ${ymd(f.due)} · <b>D-${f.days}</b></span>`];
  const next11 = new Date(now.getFullYear(), now.getMonth() + 1, 11); parts.push(`<span>지난달 전자세금계산서 전송 기한 <b>${ymd(next11)}</b></span>`);
  if (org) { const h = handoverDue(org.handover_day || 5, now); parts.push(`<span>인계표 마감 <b>${ymd(h.due)}</b> · D-${h.days}</span>`); }
  dd.innerHTML = parts.join('');
  const a = $('role-a-state'), b = $('role-b-state');
  const n = Object.values(allLedgers()).reduce((s, r) => s + r.length, 0);
  if (a) a.textContent = org ? `설정 있음: ${org.org} 시설 ${org.facilities.length}곳 · 이 브라우저 기록 ${n}건` : '먼저 신고 담당에게 기관 설정 파일(org.json)을 받으세요';
  if (b) b.textContent = org ? `이 브라우저의 설정: ${org.org} · ${org.created} 저장 — 고치려면 누르고, 신고 때는 '신고 준비'로` : '아직 설정이 없습니다 — 5문항, 약 10분';
}
