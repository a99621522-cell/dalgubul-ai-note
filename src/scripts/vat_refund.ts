/** /vat/review/ 세 걸음 판(2026-11-05 docs/prompts/vat_refund_3steps.md · 설계 docs/design/vat-refund-3steps.md).
 *  ① 기관 고르기 ② 지난 신고서 올리기 ③ 홈택스 매입 목록 올리기 — 걸음마다 금액 띠(#rf-band) 하나가 갱신되고, 끝은 할 일 목록(#rf-todo).
 *  계산은 vat_review.ts 그대로(이 모듈은 'vat-rv-built' 이벤트를 듣고 그리기만). 나라장터 계약(vat_contracts.ts)으로 ① 요약과 ② 기간 비교를 만든다.
 *  추정(계약금액 × 10/110)은 회색 작은 글씨 — 돌려받을 금액이 아니다. 판정은 참고이며 기관의 판단이 아니다. */
import { $, esc, fmt, loadData, getOrg, claimPeriod, ymd, type Data } from './vat_rules';
import { contractsCtx, type CtrCtx } from './vat_contracts';
import type { UResult } from './vat_unlock';

type Per = { k: string; name: string; filed: string; deduct: number | null; open: boolean; days: number; claim: string; due: string; diff: number | null; should: number };
type Built = { rows: number; U?: UResult; total?: number; capTotal?: number; undAll?: number; needDed?: number; per?: Per[]; sup?: { n: number; assigned: number; ctr: number; taxAll: number; taxAssigned: number; todo: number }; filed: { k: string; deduct: number | null; er: number | null }[]; filedState: Record<string, { filed: string; deduct: number | null }>; ctx: { gov: string; name: string } | null };

const D = loadData();
if (D && $('rf-band')) init(D);

function init(D: Data) {
  const org = getOrg(); const today = ymd(new Date());
  let ctx: CtrCtx | null = null; let last: Built | null = null;
  const pName = (k: string) => { const [y, h] = k.split('-'); return `${y}년 제${h}기`; };
  const pInfo = (k: string) => claimPeriod(`${k.split('-')[0]}-${k.split('-')[1] === '1' ? '03' : '09'}-01`)!;
  /* 경정청구가 되는 과세기간(확정신고기한이 지났고 기한 + 5년 안) — 오늘 기준 */
  const openPeriods = () => { const L: string[] = []; const y0 = new Date().getFullYear() - 6; for (let y = y0; y <= new Date().getFullYear(); y++) for (const h of [1, 2]) { const k = `${y}-${h}`; const P = pInfo(k); if (P.due <= today && P.days >= 0) L.push(k); } return L; };
  const ctrByP = () => { const m = new Map<string, { tax: number; likely: number; nTax: number; nLikely: number; top: string[] }>(); for (const r of ctx?.rows ?? []) { if (!r.p) continue; const x = m.get(r.p) ?? { tax: 0, likely: 0, nTax: 0, nLikely: 0, top: [] }; if (r.taxable) { x.tax += r.est; x.nTax++; } else if (r.likely) { x.likely += r.est; x.nLikely++; } else continue; m.set(r.p, x); } for (const [k, x] of m) x.top = (ctx?.rows ?? []).filter(r => r.p === k && (r.taxable || r.likely)).sort((a, b) => b.est - a.est).slice(0, 2).map(r => r.c.nm); return m; };

  /* 걸음 상태 */
  const stepState = (b: Built | null) => { const s1 = !!org; const s2 = !!b && b.filed.length > 0; const s3 = !!b && b.rows > 0; return { s1, s2, s3 }; };
  const setStep = (id: string, done: boolean, cur: boolean, text: string) => { const li = $(id); if (!li) return; li.classList.toggle('done', done); li.classList.toggle('cur', cur); const st = $(`${id}-st`); if (st) st.innerHTML = text; };

  function band(b: Built | null) {
    const el = $('rf-band')!; const U = b?.U; const m = ctrByP(); let est = 0; for (const k of openPeriods()) { const x = m.get(k); if (x) est += x.tax + x.likely; }
    const sub = U ? `<span>확정(근거 갖춤) <b>${fmt(U.now)}</b>원</span><span>자료를 더 내면 <b>+${fmt(U.docs)}</b>원</span><span>판단 필요 <b>${fmt(U.judge)}</b>원</span>${U.assign ? `<span>시설 정하기 전 <b>${fmt(U.assign)}</b>원(세지 않음)</span>` : ''}` : '<span>③ 매입 목록을 올리면 금액이 나옵니다</span>';
    el.innerHTML = `<p class="rf-band-l">지금까지 찾은 돌려받을 수 있는 금액 <span class="meta">경정청구 · 참고 계산, 기관의 판단이 아닙니다</span></p>
      <p class="rf-band-n"><span id="rf-amt">${fmt(U ? U.now + U.docs : 0)}</span><small>원</small></p>
      <p class="rf-band-s">${sub}</p>
      ${est ? `<p class="rf-est note">참고: 경정청구가 되는 기간의 과세 시설일 법한 나라장터 계약 세액 추정 ${fmt(est)}원(계약금액 × 10/110 — 돌려받을 금액이 아닙니다)</p>` : ''}`;
  }

  function step1() {
    const body = $('rf-s1-body'); if (!body) return;
    if (!org) { setStep('rf-s1', false, true, '기관을 고르세요'); return; }
    const L = openPeriods(); const m = ctrByP(); const nTax = (ctx?.rows ?? []).filter(r => r.taxable && L.includes(r.p)).length, nLik = (ctx?.rows ?? []).filter(r => r.likely && L.includes(r.p)).length;
    const bar = L.map(k => { const P = pInfo(k); const x = m.get(k); return `<li class="${P.days < 120 ? 'soon' : ''}"><b>${esc(pName(k))}</b> <span class="meta">${P.days < 120 ? '⚠ ' : ''}D-${P.days} · ${esc(P.claim)}까지</span>${x ? ` <span class="note">계약 ${x.nTax + x.nLikely}건</span>` : ''}</li>`; }).join('');
    body.innerHTML = `<p><strong>${esc(org.org)}</strong> — 시설 ${org.facilities.length}곳 <a href="/vat/setup/" class="note">시설 고치기</a></p>
      ${ctx ? `<p class="note">이미 받아 둔 공개 자료를 붙였습니다 — 나라장터 계약 ${fmt(ctx.cg.rows.length)}건(${esc(ctx.gov.name)}, ${esc(ctx.cg.from)}~): 과세 시설에 붙은 계약 <b>${nTax}</b>건, 시설은 못 붙었지만 공제 가능성 있는 사업 유형 <b>${nLik}</b>건. 업체 사업자등록번호는 ③에서 매입 목록과 저절로 맞춥니다.</p>` : '<p class="note">이 기관의 나라장터 계약 자료는 아직 없습니다 — ②·③만으로도 됩니다.</p>'}
      <details class="vat-more"><summary>경정청구 기한 — 지금 되는 과세기간 ${L.length}개</summary><ul class="rf-dl">${bar}</ul><p class="note">법정신고기한(1~6월 → 7월 25일, 7~12월 → 다음 해 1월 25일) + 5년(국세기본법 제45조의2). ⚠ 는 120일 안.</p></details>`;
    setStep('rf-s1', true, false, '완료');
  }

  function step2(b: Built | null) {
    const box = $('rf-s2-cmp'); if (!box) return;
    const filed = new Map((b?.filed ?? []).map(f => [f.k, f])); const state = b?.filedState ?? {}; const m = ctrByP(); const L = openPeriods();
    const rows = L.map(k => { const f = filed.get(k); const s = state[k]; const ded = f?.deduct ?? s?.deduct ?? null; const x = m.get(k); const est = x ? x.tax + x.likely : 0; const none = s?.filed === 'none';
      const flag = none ? (est ? '기한후신고 후보' : '') : ded === null ? (est ? '신고서 필요' : '') : est > ded ? '먼저 볼 기간' : est > 0 && est > ded * 0.3 ? '살펴볼 기간' : '';
      return { k, ded, est, x, flag, none, P: pInfo(k) }; });
    const first = rows.filter(r => r.flag === '먼저 볼 기간' || r.flag === '기한후신고 후보').sort((a, c) => c.est - a.est);
    const look = rows.filter(r => r.flag === '살펴볼 기간').sort((a, c) => c.est - a.est);
    const pick = [...first, ...look]; const pickTxt = pick.length ? pick.map(r => pName(r.k)).join(', ') : '';
    if (!filed.size && !ctx) { box.innerHTML = ''; } else box.innerHTML = `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table" data-stack="off" id="rf-cmp"><caption>과세기간별 — 신고한 매입세액과 과세 시설일 법한 계약(참고)</caption><thead><tr><th scope="col">과세기간</th><th scope="col">신고한 매입세액 (18)</th><th scope="col">계약 세액 추정(참고)</th><th scope="col">큰 계약</th><th scope="col">경정청구 기한</th><th scope="col">표시</th></tr></thead><tbody>${rows.map(r => `<tr data-pk="${r.k}" class="${r.flag === '먼저 볼 기간' || r.flag === '기한후신고 후보' ? 'rf-hot' : ''}"><th scope="row">${esc(pName(r.k))}</th><td>${r.none ? '신고 안 함' : r.ded === null ? '<span class="note">—</span>' : fmt(r.ded)}</td><td class="note">${r.est ? fmt(r.est) : '—'}</td><td class="note">${r.x?.top.map(esc).join('<br>') ?? ''}</td><td>${esc(r.P.claim)} <span class="meta">D-${r.P.days}</span></td><td>${r.flag ? `<span class="vbadge">${esc(r.flag)}</span>` : ''}</td></tr>`).join('')}</tbody></table></div>
      <p class="note">계약 세액 추정은 과세 시설(또는 공통)에 붙은 계약과 공제 가능성 있는 사업 유형 계약의 계약금액 × 10/110 입니다. 신고 매입세액은 모든 지출의 합계라 견줌은 '먼저 볼 순서'일 뿐 증거가 아닙니다. 공사 기성·준공 세금계산서는 계약 다음 기에 나올 수 있습니다.</p>
      <p class="rf-pick" id="rf-pick">${pickTxt ? `<strong>홈택스에서 받을 기간:</strong> ${esc(pickTxt)} <span class="note">— ③에서 이 기간의 매입 목록부터 올리세요(나머지 기간은 그다음).</span>` : filed.size ? '<strong>홈택스에서 받을 기간:</strong> 계약으로는 눈에 띄는 기간이 없습니다 — ③에 경정청구가 되는 기간 전부를 올리세요.' : '<span class="note">지난 신고서를 올리면 기간마다 신고한 매입세액이 채워지고, 먼저 볼 기간이 표시됩니다.</span>'}</p>`;
    const done = !!b && b.filed.length > 0; setStep('rf-s2', done, !!org && !done, done ? `신고서 ${b!.filed.length}개 과세기간` : '신고서 PDF 를 놓으세요');
  }

  function step3(b: Built | null) {
    const done = !!b && b.rows > 0; const s = b?.sup;
    setStep('rf-s3', done && !!s && s.todo === 0, !!org && !done || (!!s && s.todo > 0), done && s ? `${fmt(b!.rows)}건 · 공급자 ${s.n}곳 중 저절로·직접 붙음 ${s.assigned}곳${s.ctr ? `(계약 업체 번호 일치 ${s.ctr}곳)` : ''}${s.todo ? ` · <b>남은 ${s.todo}곳</b>` : ''}` : '매입 목록 엑셀을 놓으세요');
  }

  function todo(b: Built | null) {
    const el = $('rf-todo'); if (!el) return; const U = b?.U;
    if (!U) { el.innerHTML = `<p class="note">${!org ? '① 기관을 고르면 시작합니다.' : '③에 매입 목록을 올리면 할 일 목록이 나옵니다.'}</p>`; return; }
    const perOf = (k: string) => U.per.find(p => p.k === k); const dOf = (ks: string[]) => ks.map(k => perOf(k)).filter(p => p && !p.expired && !p.future).sort((a, c) => a!.days - c!.days)[0];
    type T = { amt: number; days: number; html: string };
    const L: T[] = [];
    const nowPer = U.per.filter(p => p.now > 0 && !p.expired && !p.future); if (U.now > 0) { const d = nowPer.sort((a, c) => a.days - c.days)[0]; L.push({ amt: U.now, days: d?.days ?? 9999, html: `<b>지금 자료로 청구할 수 있는 금액 ${fmt(U.now)}원</b> — ${nowPer.map(p => esc(pName(p.k))).join(', ')} · 아래 「경정청구 묶음 내려받기」로 붙임 자료를 받아 홈택스 경정청구에 넣습니다` }); }
    for (const n of U.needs) { const d = dOf([...n.byK.keys()]); L.push({ amt: n.amount, days: d?.days ?? 9999, html: `<b>${esc(n.labels.join(' · '))}</b> — ${esc(n.whats[0] ?? '')} → 약 <b>${fmt(n.amount)}원</b> <span class="note">(${n.n}건)</span>` }); }
    for (const j of U.judgeList) L.push({ amt: j.amount, days: 9999, html: `<b>판단 필요: ${esc(j.label)}</b> — 약 ${fmt(j.amount)}원 <span class="note">(${j.n}건) · 기준·유권해석·질의서 초안은 '자세히 보기'의 근거 절</span>` });
    if (b?.sup?.todo) L.push({ amt: U.assign, days: 9999, html: `<b>시설을 못 정한 공급자 ${b.sup.todo}곳</b> — ③ 표에서 세액 큰 곳부터(약 ${fmt(U.assign)}원이 아직 셈에 안 들어감)` });
    if (b?.needDed) L.push({ amt: 0, days: 9999, html: `<b>신고 값이 없는 과세기간 ${b.needDed}개</b> — ②에 그 기간 신고서를 올리면 상한이 아니라 실제 차이가 나옵니다` });
    L.sort((a, c) => c.amt - a.amt || a.days - c.days);
    const dd = (d: number) => d < 9999 ? `<span class="vbadge${d < 120 ? ' warn' : ''}">D-${d}</span> ` : '';
    el.innerHTML = L.length ? `<ol class="rf-todo">${L.map(t => `<li>${dd(t.days)}${t.html}</li>`).join('')}</ol>` : '<p class="note">지금 자료로는 돌려받을 금액이 보이지 않습니다. 시설의 과세·면세 표시와 ③ 귀속을 다시 확인하세요.</p>';
    el.insertAdjacentHTML('beforeend', `<div class="actions"><button type="button" class="btn" id="rf-zip">경정청구 묶음 내려받기(zip)</button> <button type="button" class="btn secondary" id="rf-print">할 일 인쇄</button> <span class="note">묶음: 과세기간별 결과·건별 명세·공급자별 합계(합계표 추가분)·근거 조문·사유 초안·질의서 초안</span></div>`);
    $('rf-zip')?.addEventListener('click', () => { const z = $('rv-zip'); if (z) z.click(); });
    $('rf-print')?.addEventListener('click', () => { document.body.dataset.printHead = `지난 돈 돌려받기 — 할 일 · ${org?.org ?? ''} · ${today}`; document.body.classList.add('print-todo'); window.print(); setTimeout(() => document.body.classList.remove('print-todo'), 500); });
  }

  function draw() { const b = last; band(b); step1(); step2(b); step3(b); todo(b); }
  document.addEventListener('vat-rv-built', e => { last = (e as CustomEvent<Built>).detail; draw(); });
  void contractsCtx(D, org).then(c => { ctx = c; draw(); });
  draw();
  /* '다른 방법' 펼침 안 탭 / 자세히 보기로 가는 링크 */
  document.querySelectorAll<HTMLAnchorElement>('a[href="#rf-more"]').forEach(a => a.addEventListener('click', () => { const d = $('rf-more') as HTMLDetailsElement | null; if (d) d.open = true; }));
}
