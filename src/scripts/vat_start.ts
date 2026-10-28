/** /vat/ 대시보드(공무원 UX 재설계 2026-10-28, docs/design/vat-ux-spec.md §2) — 상태 카드 4개 + 1차 행동 단추 하나 + '지금 살릴 수 있는 세액'(이전 그대로). 서버 없음, 이 브라우저 기록만 */
import { $, getOrg, allLedgers, getFilings, nextFiling, handoverDue, ymd, esc, fmt, loadData, openItems, periodInfo, periodKeyOf, monthStr, inFiling } from './vat_rules';
const D = loadData(); const now = new Date(); const f = nextFiling(now); const org = getOrg();
const ledgers = allLedgers(); const rows = Object.values(ledgers).flat(); const oi = openItems(rows);
/* 기록 없는 시설·달 — 다음 신고 기간의 달 가운데 지난 달까지 × 신고 대상 시설 */
const curKey = periodKeyOf(monthStr(new Date(now.getFullYear(), now.getMonth() - 1, 1))); const P = periodInfo(curKey);
const facs = org && D ? org.facilities.filter(x => inFiling(D, x)) : []; const lastMonth = monthStr(new Date(now.getFullYear(), now.getMonth() - 1, 1));
const months = P.own.filter(m => m <= lastMonth); const empty: string[] = []; for (const fc of facs) for (const m of months) if (!ledgers[`${fc.id}:${m}`]?.length) empty.push(`${fc.name} ${m}`);
const fl = Object.values(getFilings()).sort((a, b) => b.period.localeCompare(a.period))[0]; const nd = fl ? fl.groups.reduce((s, g) => s + Math.max(0, g.nondeduct) + Math.max(0, g.admin_nondeduct ?? 0), 0) : 0;

const st = $('vat-status');
if (st) {
  const card = (href: string, k: string, v: string, d: string, go: string, cls = '') => `<li class="${cls}"><a href="${href}"><span class="k">${k}</span><span class="v">${v}</span><span class="d">${d}</span><span class="go">${go} →</span></a></li>`;
  st.innerHTML = !org
    ? `<li><a href="/vat/setup/"><span class="k">시작</span><span class="v">설정 없음</span><span class="d">우리 기관과 돈을 받는 시설을 적으면 그때부터 기록·신고 준비가 됩니다(약 5~10분).</span><span class="go">기관 설정 →</span></a></li>`
    : card('/vat/prepare/', '다음 신고', `D-${f.days}`, `${esc(f.name)} · ${ymd(f.due)}`, '신고 준비', f.days <= 14 ? 'warn' : '')
      + card('/vat/monthly/', '기록 없는 시설·달', `${empty.length}<span class="d"> / ${facs.length * months.length}</span>`, empty.length ? esc(empty.slice(0, 3).join(', ')) + (empty.length > 3 ? ` 외 ${empty.length - 3}` : '') : `${esc(P.name)} 기간의 지난 달까지 모두 기록됨`, '지출 기록', empty.length ? 'warn' : '')
      + card('/vat/monthly/', '처리할 것', String(oi.total), oi.total ? `다른 명의 ${oi.red.length}건 ${fmt(oi.redTax)}원 · 확인 필요 ${oi.yellow.length}건 · 근거 없는 전용 ${oi.noEvid.length}건${oi.expired ? ` · 수정 기한 지남 ${oi.expired}` : ''}` : '빨강·노랑·근거 없음이 없습니다', '처리하기', oi.red.length ? 'alert' : oi.total ? 'warn' : '')
      + card('/vat/prepare/', '지난 기 공통 면세분', fl ? `${fmt(nd)}<span class="d">원</span>` : '—', fl ? `${fl.period} 신고 기록의 (54) — 전용 분리·비율 관리로 줄일 수 있는 상한` : '신고 기록을 저장하면 보입니다', '절감 분석');
  /* 1차 행동 단추 하나: 설정 없음 → 설정 / 처리할 것 → 처리 / 기한 30일 안 → 신고 준비 / 그 밖 → 이번 달 기록 */
  const cta = $<HTMLAnchorElement>('vat-cta')!, why = $('vat-cta-why')!;
  if (!org) { cta.href = '/vat/setup/'; cta.textContent = '기관 설정 시작'; why.textContent = '5문항 · 예시(달성군)와 세입예산서에서 시설을 불러올 수 있습니다.'; }
  else if (oi.red.length) { cta.href = '/vat/monthly/'; cta.textContent = `다른 명의 ${oi.red.length}건 처리하기`; why.textContent = '수정세금계산서 기한 안에 공급자에게 요청해야 그 세액이 살아납니다.'; }
  else if (f.days <= 30) { cta.href = '/vat/prepare/'; cta.textContent = `${f.name.replace(/\(.*\)/, '').trim()} 준비`; why.textContent = `${ymd(f.due)}까지 · 기록을 신고서 칸으로 옮깁니다.`; }
  else if (empty.length) { cta.href = '/vat/monthly/?open=1'; cta.textContent = '이번 달 지출 기록'; why.textContent = '홈택스 매입 목록을 붙여넣고 어느 시설 지출인지만 고릅니다.'; }
  else { cta.href = '/vat/monthly/'; cta.textContent = '지출 기록 보기'; why.textContent = oi.total ? '확인 필요·근거 없음을 정리하면 신고 준비가 짧아집니다.' : '이번 기간 기록이 다 있습니다.'; }
}
const dd = $('dday');
if (dd) {
  const parts = [`<span>다음 신고 <b>${esc(f.name)}</b> ${ymd(f.due)} · <b>D-${f.days}</b></span>`];
  const next11 = new Date(now.getFullYear(), now.getMonth() + 1, 11); parts.push(`<span>지난달 전자세금계산서 전송 기한 <b>${ymd(next11)}</b></span>`);
  if (org) { const h = handoverDue(org.handover_day || 5, now); parts.push(`<span>인계표 마감 <b>${ymd(h.due)}</b> · D-${h.days}</span>`); }
  dd.innerHTML = parts.join('');
  const a = $('role-a-state'), b = $('role-b-state');
  if (a) a.textContent = org ? `이 브라우저 기록 ${rows.length}건 · 시설 ${org.facilities.length}곳` : '③ 기관 설정을 먼저 하면 시설을 고를 수 있습니다';
  if (b) b.textContent = org ? `이 브라우저의 설정: ${org.org} · ${org.created} 저장` : '아직 설정이 없습니다 — 5문항, 약 10분';
}
/* 절감 요약(이전 그대로 — 운영자 2026-10-27 '절감이 목적이야'): ① 발굴 후보 ② 다른 명의 빨강 세액 ③ 노랑 세액 ④ 최근 신고 기록의 공통 면세분. 평가 아님 */
const sv = $('sv-sum');
if (sv) {
  const today = ymd(new Date());
  let cand = 0; try { const a = JSON.parse(localStorage.getItem('vat-discover-v1') || '{}') as Record<string, string>; cand = (D?.revenue_items ?? []).filter(i => i.status === 'taxable' && a[i.key] === 'unfiled').length; } catch { /* */ }
  const expired = rows.filter(r => r.v === 'no' && r.payee === 'contractor' && !r.done && r.fix_due && r.fix_due < today).reduce((s, r) => s + r.tax, 0);
  const fixable = oi.red.filter(r => !r.fix_due || r.fix_due >= today); const fixTax = fixable.reduce((s, r) => s + r.tax, 0);
  const items = [
    `<li>길 1 — 과세사업 찾기에서 '과세인데 신고 안 함'으로 표시한 수입 <b>${cand}</b>개 ${cand ? '→ <a href="/vat/discover/">등록·신고 검토</a>' : '(<a href="/vat/discover/">점검표</a>를 아직 안 채웠거나 후보 없음)'}</li>`,
    `<li>길 2 — 다른 명의 세금계산서로 빠진 세액 <b>${fmt(fixTax)}</b>원(${fixable.length}건, 수정세금계산서 기한 안) → 공급자에게 수정 요청하면 살아납니다${expired ? ` · 기한 지남 ${fmt(expired)}원은 착오 정정이 아니면 불가` : ''}; 확인 필요(노랑) <b>${fmt(oi.yellowTax)}</b>원(${oi.yellow.length}건) → 귀속·공급자 확인</li>`,
    `<li>길 3 — ${fl ? `최근 신고 기록(${fl.period})의 공통매입세액 면세분 <b>${fmt(nd)}</b>원 → 전용 분리·비율 관리로 줄일 수 있는 상한(<a href="/vat/prepare/">절감 분석</a>)` : '신고 기록이 없어 공통매입세액 면세분을 아직 셀 수 없습니다(<a href="/vat/prepare/">신고 준비</a>에서 저장)'}</li>`,
    `<li>길 4 — 지난 5년 빠진 매입세액은 <a href="/vat/review/">지난 신고 점검</a>에 홈택스 매입 목록을 붙여넣어야 계산됩니다(저장하지 않음)</li>`];
  sv.innerHTML = `<ul class="meta-list">${items.join('')}</ul><p class="note">이 숫자는 이 브라우저에 있는 기록만으로 센 것이고, 공제 여부의 최종 판단은 신고인 몫입니다.</p>`;
}
