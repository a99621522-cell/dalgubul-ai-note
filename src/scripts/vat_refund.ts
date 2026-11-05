/** /vat/review/ 세 걸음 판(2026-11-05 docs/prompts/vat_refund_3steps.md · 설계 docs/design/vat-refund-3steps.md).
 *  ① 기관 고르기 ② 지난 신고서 올리기 ③ 홈택스 매입 목록 올리기 — 걸음마다 금액 띠(#rf-band) 하나가 갱신되고, 끝은 할 일 목록(#rf-todo).
 *  계산은 vat_review.ts 그대로(이 모듈은 'vat-rv-built' 이벤트를 듣고 그리기만). 나라장터 계약(vat_contracts.ts)으로 ① 요약과 ② 기간 비교를 만든다.
 *  추정(계약금액 × 10/110)은 회색 작은 글씨 — 돌려받을 금액이 아니다. 판정은 참고이며 기관의 판단이 아니다. */
import { $, esc, fmt, loadData, getOrg, claimPeriod, ymd, lawLink, uniq, facilityRule, facilityStatus, bizType, type Data, type Basis } from './vat_rules';
import { contractsCtx, type CtrCtx } from './vat_contracts';
import { commonMistakesHtml, refundCalcHtml, type Diag } from './vat_diag';
import { buildQuestions, askHtml, answer, answerGroup, undo } from './vat_ask';
import type { UResult } from './vat_unlock';

type Per = { k: string; name: string; filed: string; deduct: number | null; open: boolean; days: number; claim: string; due: string; diff: number | null; should: number };
type Built = { diags?: Diag[]; diag?: string; fsure?: number; facTax?: Record<string, number>; rows: number; U?: UResult; total?: number; capTotal?: number; undAll?: number; needDed?: number; per?: Per[]; sup?: { n: number; assigned: number; ctr: number; taxAll: number; taxAssigned: number; todo: number }; filed: { k: string; deduct: number | null; er: number | null; salesSup?: number | null }[]; filedState: Record<string, { filed: string; deduct: number | null }>; ctx: { gov: string; name: string } | null };

const D = loadData();
if (D && $('rf-band')) init(D);

function init(D: Data) {
  const org = getOrg(); const today = ymd(new Date());
  let ctx: CtrCtx | null = null; let last: Built | null = null;
  const pName = (k: string) => { const [y, h] = k.split('-'); return `${y}년 제${h}기`; };
  const pInfo = (k: string) => claimPeriod(`${k.split('-')[0]}-${k.split('-')[1] === '1' ? '03' : '09'}-01`)!;
  /* 왜·근거 — 공무원이 납득하도록 항목마다 이유 한 줄과 조문(운영자 2026-11-05 '어떤 항목을 어떻게 해야 되는지 이유는 나와야') */
  const law = (bs?: Basis[]) => { const L = uniq(bs ?? []); return L.length ? L.map(b => lawLink(D, b)).join(' · ') : ''; };
  const B = (law: Basis['law'], art: string): Basis => ({ law, art } as Basis);
  const whyBox = (why: string, how: string, bs?: Basis[]) => `<div class="rf-why"><p><span class="rf-k">왜</span> ${why}</p>${how ? `<p><span class="rf-k">할 일</span> ${how}</p>` : ''}${law(bs) ? `<p><span class="rf-k">근거</span> ${law(bs)}</p>` : ''}</div>`;
  const noFmt = (n: string) => n.replace(/^(\d{3})(\d{2})(\d{5})$/, '$1-$2-$3');
  const g2b = (u: string) => /^https?:/.test(u) ? u : `https://www.g2b.go.kr/link/FIUA027_01/single/?${u}&srchName=ctrtCrst&openUrl=Y`;
  type CR = CtrCtx['rows'][number];
  function ctrWhy(r: CR) {
    const c = r.c; const f = r.a && org ? org.facilities.find(x => x.id === r.a!.fid) : undefined; const rule = f ? facilityRule(D, f) : undefined; const st = f ? facilityStatus(D, f) : undefined;
    const via = r.via === '지정' ? '직접 지정한 시설' : r.via === '매핑표' ? '전에 고른 사업명(매핑표)' : '계약명에 시설 이름이 들어 있음';
    const corps = c.corps.filter(p => /^\d{10}$/.test(p.no)); const corpTxt = corps.length ? corps.map(p => `${esc(p.nm || '(상호 확인)')} <b>${noFmt(p.no)}</b>`).join(', ') : '<span class="note">업체 번호 없음 — 계약명으로 찾기</span>';
    const pn = pName(r.p); let why = '', bs: Basis[] = [], extra = '';
    const win = (r as CR & { inWin?: string[] }).inWin; const pBadge = r.span ? `${pName(r.span.split('~')[0])}~${pName(r.span.split('~')[1])}` : pn;
    if (r.taxable && r.a) {
      const fn = r.a.fid === 'admin' ? '본청·행정 공통' : `「${esc(f?.name ?? '')}」`;
      if (r.a.fid === 'admin' || r.a.use === 'admin') { why = `${fn}에 붙은 지출(${via}) — 행정과 함께 쓰는 지출은 그 기간 면세비율만큼 빼고 공제합니다(안분). ${esc(D.rules.admin_common?.summary ?? '')}`; bs = [B('act', '제40조'), B('decree', '제81조'), ...(D.rules.admin_common?.basis ?? [])]; extra = ' · 그 기간 면세비율(② 신고서의 공제받지 못할 매입세액 명세서)이 있어야 금액이 정해집니다'; }
      else if (r.a.use === 'multi') { why = `${fn}과 다른 시설이 같이 쓰는 지출(${via}) — 과세 시설 몫은 면세비율만큼 빼고 공제합니다(안분)`; bs = [B('act', '제40조'), B('decree', '제81조')]; extra = ' · 그 기간 면세비율이 있어야 금액이 정해집니다'; }
      else if (st === 'check') { why = `${fn}(${via})는 기관 설정에서 「${esc(rule?.name ?? '')}」 유형 — 운영 방식에 따라 과세·면세가 갈립니다: ${esc(rule?.cond || rule?.note || '')}`; bs = rule?.basis ?? []; extra = ' · 먼저 이 시설의 운영 방식(사용료를 받는지, 계속·반복 대관인지)을 기관 설정에서 확인하세요'; }
      else { why = `${fn}(${via})는 기관 설정에서 「${esc(rule?.name ?? '과세 시설')}」 유형으로 두어 과세 시설로 봅니다 — ${esc(rule?.cond || rule?.note || '')} 과세사업에 쓴 지출의 매입세액은 공제 대상입니다(유형이 다르면 <a href="/vat/setup/?step=3">기관 설정</a>에서 고치면 다시 셉니다)`; bs = [B('act', '제38조'), ...(rule?.basis ?? [])]; }
    } else { const t = bizType(D, c.nm); why = `시설은 못 붙었지만 계약명이 「${esc(t?.name ?? '')}」 유형입니다 — ${esc(t?.hint ?? '')}`; bs = [B('act', '제38조'), B('act', '제39조')]; extra = ' · 먼저 이 시설이 사용료를 받는(과세) 시설인지 확인해 기관 설정에 시설로 넣으세요 — 넣으면 다음부터 저절로 붙습니다'; }
    const wk = c.k === '공사' ? D.rules.works?.options.find(o => o.key === r.cw) : undefined;
    if (c.k === '공사') extra += wk ? ` · 공사 갈래 짐작: ${esc(wk.short)} — ${esc(wk.why)}` : ' · 공사라면 과세 부분 전용인지·같이 쓰는 시설인지·부지 토목인지에 따라 공제가 갈립니다(③ 표 「공사라면」)';
    const how = `① 홈택스 「전자세금계산서 목록조회(매입)」에서 공급자 ${corpTxt} 의 ${esc(c.date)} 이후 세금계산서(선금·기성·준공)를 찾습니다 ② 그 세액이 ${esc(win && win.length > 1 ? `${pName(win[0])}~${pName(win[win.length - 1])}` : pn)} 신고서의 매입세액 (10)~(18)에 들어갔는지 봅니다 — 면세·행정으로 보고 (17) 불공제에 넣었거나 빠졌으면 ③에 그 목록을 올려 경정청구 후보로${extra}`;

    return `<li><p class="rf-ctr"><span class="vbadge">${esc(pBadge)}</span> ${c.url ? `<a href="${esc(g2b(c.url))}" target="_blank" rel="noopener">${esc(c.nm)}</a>` : esc(c.nm)} <span class="note">${esc(c.k)} · 계약 ${esc(c.date)} · 이번 차수 ${fmt(c.amt || c.tot)}원 → 세액 추정 ${fmt(r.est)}원(× 10/110, 참고)${r.span ? ` — 공사 기간(${esc(c.date)}~${esc(c.fin ?? '')})에 날수대로 나눠 경정청구가 되는 ${win?.length ?? 0}개 과세기간 몫만` : ''}</span></p>${whyBox(why, how, bs)}</li>`;
  }
  let whyN = 8;
  /* 경정청구가 되는 과세기간(확정신고기한이 지났고 기한 + 5년 안) — 오늘 기준 */
  const openPeriods = () => { const L: string[] = []; const y0 = new Date().getFullYear() - 6; for (let y = y0; y <= new Date().getFullYear(); y++) for (const h of [1, 2]) { const k = `${y}-${h}`; const P = pInfo(k); if (P.due <= today && P.days >= 0) L.push(k); } return L; };
  const ctrByP = () => { const m = new Map<string, { tax: number; likely: number; nTax: number; nLikely: number; top: string[] }>(); for (const r of ctx?.rows ?? []) { if (!r.p) continue; const x = m.get(r.p) ?? { tax: 0, likely: 0, nTax: 0, nLikely: 0, top: [] }; if (r.taxable) { x.tax += r.est; x.nTax++; } else if (r.likely) { x.likely += r.est; x.nLikely++; } else continue; m.set(r.p, x); } for (const [k, x] of m) x.top = [...new Set((ctx?.rows ?? []).filter(r => r.p === k && (r.taxable || r.likely)).sort((a, b) => b.est - a.est).map(r => r.c.nm))].slice(0, 2); return m; };

  /* 걸음 상태 */
  const stepState = (b: Built | null) => { const s1 = !!org; const s2 = !!b && b.filed.length > 0; const s3 = !!b && b.rows > 0; return { s1, s2, s3 }; };
  const setStep = (id: string, done: boolean, cur: boolean, text: string) => { const li = $(id); if (!li) return; li.classList.toggle('done', done); li.classList.toggle('cur', cur); const st = $(`${id}-st`); if (st) st.innerHTML = text; };

  function band(b: Built | null) {
    const el = $('rf-band')!; const U = b?.U; const m = ctrByP(); let est = 0; for (const k of openPeriods()) { const x = m.get(k); if (x) est += x.tax + x.likely; }
    const fs = b?.fsure ?? 0;
    const sub = (U ? `<span>확정(근거 갖춤) <b>${fmt(U.now)}</b>원</span><span>자료를 더 내면 <b>+${fmt(U.docs)}</b>원</span><span>판단 필요 <b>${fmt(U.judge)}</b>원</span>${U.assign ? `<span>시설 정하기 전 <b>${fmt(U.assign)}</b>원(세지 않음)</span>` : ''}` : '') + (fs ? `<span>신고서만으로 다시 계산 <b>+${fmt(fs)}</b>원</span>` : '') + (!U ? `<span>${fs ? '' : '② 지난 신고서를 올리면 바로 계산하고, '}③ 매입 목록을 올리면 더 찾습니다</span>` : '');
    el.innerHTML = `<p class="rf-band-l">지금까지 찾은 돌려받을 수 있는 금액 <span class="meta">경정청구 · 참고 계산, 기관의 판단이 아닙니다</span></p>
      <p class="rf-band-n"><span id="rf-amt">${fmt((U ? U.now + U.docs : 0) + fs)}</span><small>원</small></p>
      <p class="rf-band-s">${sub}</p>
      ${est ? `<p class="rf-est note">참고: 경정청구가 되는 기간의 과세 시설일 법한 나라장터 계약 세액 추정 ${fmt(est)}원(계약금액 × 10/110 — 돌려받을 금액이 아닙니다)</p>` : ''}`;
  }

  function step1() {
    const body = $('rf-s1-body'); if (!body) return;
    if (!org) { setStep('rf-s1', false, true, '기관을 고르세요'); return; }
    const L = openPeriods(); const m = ctrByP(); const uq = (f: (r: CtrCtx['rows'][number]) => boolean) => new Set((ctx?.rows ?? []).filter(r => f(r) && L.includes(r.p)).map(r => r.ck)).size; const nTax = uq(r => r.taxable), nLik = uq(r => r.likely);
    const bar = L.map(k => { const P = pInfo(k); const x = m.get(k); return `<li class="${P.days < 120 ? 'soon' : ''}"><b>${esc(pName(k))}</b> <span class="meta">${P.days < 120 ? '⚠ ' : ''}D-${P.days} · ${esc(P.claim)}까지</span>${x ? ` <span class="note">계약 ${x.nTax + x.nLikely}건</span>` : ''}</li>`; }).join('');
    const gp = (D.govs ?? []).find(g => org.org === g.name || org.org.endsWith(g.name.replace(/^대구광역시\s*/, '')) && g.level === '기초' || (g.level === '광역' && org.org === '대구광역시'));
    const prof = gp ? `<details class="vat-more rf-gov"><summary>${esc(gp.name)}의 특성 — ${esc(gp.status)}${gp.corp.length ? ` · ${esc(gp.corp.map(c => c.name.replace(/\(.*$/, '')).join('·'))}` : ''}</summary>${gp.traits.length ? `<ul class="meta-list">${gp.traits.map(t => `<li>${esc(t)}</li>`).join('')}</ul>` : ''}${gp.corp.length ? `<ul class="meta-list">${gp.corp.map(c => `<li>${esc(c.name)}${c.bizno ? ` ${esc(c.bizno)}` : ''}${c.src ? ` <span class="meta">(${esc(c.src)})</span>` : ''}${c.note ? ` — ${esc(c.note)}` : ''}</li>`).join('')}</ul>` : ''}<p class="note">자료: ${[gp.preset ? `예시 설정 시설 ${gp.preset}곳` : '예시 설정 없음(세입예산서 시설 후보만)', gp.revenue ? `2026 세입예산서 ${gp.revenue}줄` : '', gp.contracts?.n ? `나라장터 계약 ${fmt(gp.contracts.n)}건(${esc(gp.contracts.from)}~${esc(gp.contracts.to)})` : '나라장터 계약 아직 없음'].filter(Boolean).join(' · ')}. 다른 지자체로 바꾸려면 위 「기관 바꾸기」.</p></details>` : '';
    body.innerHTML = `<p><strong>${esc(org.org)}</strong> — 시설 ${org.facilities.length}곳 <a href="/vat/setup/" class="note">시설 고치기</a></p>${prof}
      ${ctx ? `<p class="note">이미 받아 둔 공개 자료를 붙였습니다 — 나라장터 계약 ${fmt(ctx.cg.rows.length)}건(${esc(ctx.gov.name)}, ${esc(ctx.cg.from)}~): 과세 시설에 붙은 계약 <b>${nTax}</b>건, 시설은 못 붙었지만 공제 가능성 있는 사업 유형 <b>${nLik}</b>건. 업체 사업자등록번호는 ③에서 매입 목록과 저절로 맞춥니다.</p>` : '<p class="note">이 기관의 나라장터 계약 자료는 아직 없습니다 — ②·③만으로도 됩니다.</p>'}
      <details class="vat-more"><summary>경정청구 기한 — 지금 되는 과세기간 ${L.length}개</summary><ul class="rf-dl">${bar}</ul><p class="note">법정신고기한(1~6월 → 7월 25일, 7~12월 → 다음 해 1월 25일) + 5년(국세기본법 제45조의2). ⚠ 는 120일 안.</p></details>`;
    setStep('rf-s1', true, false, '완료');
  }

  function whyList(first: string[]) {
    const L = openPeriods(); const fs = new Set(first);
    /* 공사 기간으로 나눈 조각을 계약 하나로 다시 모은다 — 경정청구가 되는 기간 몫만 더하고, 먼저 볼 기간에 걸친 계약을 앞으로 */
    const by = new Map<string, CR & { hot: boolean; inWin: string[] }>(); for (const r of (ctx?.rows ?? [])) { if (!(r.taxable || r.likely) || !L.includes(r.p)) continue; const x = by.get(r.ck); if (x) { x.est += r.est; x.inWin.push(r.p); x.hot ||= fs.has(r.p); } else by.set(r.ck, { ...r, hot: fs.has(r.p), inWin: [r.p] }); }
    const all = [...by.values()]; if (!all.length) return '';
    const sorted = all.sort((a, c) => (c.hot ? 1 : 0) - (a.hot ? 1 : 0) || (c.taxable ? 1 : 0) - (a.taxable ? 1 : 0) || c.est - a.est);
    return `<details class="vat-more rf-whys" id="rf-why" open><summary>계약별로 — 무엇을 · 왜 · 어떻게 (${fmt(all.length)}건 가운데 ${Math.min(whyN, all.length)}건, 먼저 볼 기간·과세 시설·세액 큰 순)</summary>
      <ol class="rf-why-list">${sorted.slice(0, whyN).map(ctrWhy).join('')}</ol>
      ${all.length > whyN ? `<button type="button" class="btn secondary" id="rf-why-more">${Math.min(20, all.length - whyN)}건 더 보기</button>` : ''}
      <p class="note">계약은 '어느 세금계산서를 찾을지' 알려 줄 뿐입니다. 돌려받을 금액은 ③에 올린 세금계산서로만 셉니다. 판정은 참고이며 기관의 판단이 아닙니다.</p></details>`;
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
      <p class="rf-pick" id="rf-pick">${pickTxt ? `<strong>홈택스에서 받을 기간:</strong> ${esc(pickTxt)} <span class="note">— ③에서 이 기간의 매입 목록부터 올리세요(나머지 기간은 그다음).</span>` : filed.size ? '<strong>홈택스에서 받을 기간:</strong> 계약으로는 눈에 띄는 기간이 없습니다 — ③에 경정청구가 되는 기간 전부를 올리세요.' : '<span class="note">지난 신고서를 올리면 기간마다 신고한 매입세액이 채워지고, 먼저 볼 기간이 표시됩니다.</span>'}</p>${whyList(pick.map(r => r.k))}`;
    $('rf-why-more')?.addEventListener('click', () => { whyN += 20; step2(last); const d = $('rf-why') as HTMLDetailsElement | null; if (d) d.open = true; });
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
    const needWhy = (key: string, whats: string[]) => { const ks = key.split('+'); const ws: string[] = [], bs: Basis[] = [];
      for (const k of ks) { if (k.startsWith('fac:')) { ws.push('세무서가 공제를 인정하려면 ① 그 지출이 이 시설 것이고 ② 이 시설이 과세사업(사용료를 받아 부가세를 신고)이라는 것을 보여야 합니다 — 면세사업에 쓴 매입세액은 공제하지 않습니다'); bs.push(B('act', '제38조'), B('act', '제39조')); }
        else if (k.startsWith('ratio:')) { ws.push('여러 시설·행정이 같이 쓴 지출은 그 과세기간 면세비율만큼 빼고 공제합니다(안분) — 비율이 있어야 금액이 정해집니다'); bs.push(B('act', '제40조'), B('decree', '제81조')); }
        else if (k.startsWith('fix:')) { ws.push('공급받는 자가 우리 등록번호가 아닌 세금계산서는 공제하지 않습니다 — 공급자가 공급받는 자를 고친 수정세금계산서를 발급하면 공제할 수 있습니다(확정신고기한 다음 날부터 1년 안)'); bs.push(B('act', '제39조'), B('decree', '제70조')); } }
      return whyBox(ws.join(' / '), whats.map(esc).join(' / ') + ' — 자료가 있으면 \'자세히 보기\'의 자료별 표에서 「있음」에 표시하세요', bs); };
    const judgeWhy = (key: string) => { if (key === 'admin') { const a = D.rules.admin_common; return whyBox(esc(a?.summary ?? '본청·행정 공통 지출은 고유사무에 공급가액이 없어 공급가액 비율로 나눌 수 없습니다'), `안분 기준(매입가액·예정공급가액·예정사용면적 중 하나)을 정하고, 기준이 굳지 않으면 국세청 질의서 초안(\'자세히 보기\'의 근거 절)으로 세무서에 묻습니다${a?.caution ? ` — ${esc(a.caution)}` : ''}`, [B('decree', '제81조'), ...(a?.basis ?? [])]); }
      const t = key.startsWith('type:') ? D.facilities.find(x => x.key === key.slice(5)) : undefined; return whyBox(`${esc(t?.name ?? '이 시설 유형')}은 운영 방식에 따라 과세·면세가 갈립니다${t?.cond ? `: ${esc(t.cond)}` : ''}`, '시설의 실제 운영 방식(사용료를 받는지, 계속·반복인지)을 확인해 기관 설정 시설 카드에 적고, 기준이 애매하면 질의서 초안으로 세무서에 묻습니다', t?.basis); };
    type T = { amt: number; days: number; html: string };
    const L: T[] = [];
    const nowPer = U.per.filter(p => p.now > 0 && !p.expired && !p.future); if (U.now > 0) { const d = nowPer.sort((a, c) => a.days - c.days)[0]; L.push({ amt: U.now, days: d?.days ?? 9999, html: `<b>지금 자료로 청구할 수 있는 금액 ${fmt(U.now)}원</b> — ${nowPer.map(p => esc(pName(p.k))).join(', ')}` + whyBox('과세 시설에 쓴 지출(공통 지출은 면세비율만큼 뺀 몫)의 매입세액이 그 기간 신고한 매입세액 (18)보다 많습니다. 모자란 몫은 법정신고기한 뒤 5년 안에 경정청구로 돌려받습니다', '아래 「경정청구 묶음 내려받기」로 붙임 자료(과세기간별 결과·건별 명세·공급자별 합계·사유 초안·근거 조문)를 받아 홈택스 「신고서 수정(경정청구)」에 넣습니다', [B('act', '제38조'), B('basic', '제45조의2')]) }); }
    for (const n of U.needs) { const d = dOf([...n.byK.keys()]); L.push({ amt: n.amount, days: d?.days ?? 9999, html: `<b>${esc(n.labels.join(' · '))}</b> → 약 <b>${fmt(n.amount)}원</b> <span class="note">(${n.n}건)</span>` + needWhy(n.key, n.whats) }); }
    for (const j of U.judgeList) L.push({ amt: j.amount, days: 9999, html: `<b>판단 필요: ${esc(j.label)}</b> — 약 ${fmt(j.amount)}원 <span class="note">(${j.n}건)</span>` + judgeWhy(j.key) });
    if (b?.sup?.todo) L.push({ amt: U.assign, days: 9999, html: `<b>시설을 못 정한 공급자 ${b.sup.todo}곳</b> — 약 ${fmt(U.assign)}원이 아직 셈에 안 들어감` + whyBox('시설이 정해져야 그 지출이 과세 시설 것(공제)인지 면세·행정 것(불공제)인지가 정해집니다', '③ 표에서 세액 큰 공급자부터 시설과 용도(이 시설만 / 여러 시설 / 행정과 함께)를 고릅니다 — 고른 것은 매핑표에 남아 다음 목록에 저절로 붙습니다', [B('act', '제38조'), B('act', '제39조'), B('act', '제40조')]) });
    if (b?.needDed) L.push({ amt: 0, days: 9999, html: `<b>신고 값이 없는 과세기간 ${b.needDed}개</b>` + whyBox('경정청구 금액은 \'공제받았어야 할 매입세액 − 신고 때 공제받은 매입세액 (18)\' 입니다. 신고 값이 없으면 목록 전부가 빠졌다고 보는 상한만 셀 수 있습니다', '②에 그 기간 신고서(홈택스 「신고서 조회」 PDF)를 올리면 실제 차이가 나옵니다', [B('basic', '제45조의2')]) });
    L.sort((a, c) => c.amt - a.amt || a.days - c.days);
    const dd = (d: number) => d < 9999 ? `<span class="vbadge${d < 120 ? ' warn' : ''}">D-${d}</span> ` : '';
    el.innerHTML = L.length ? `<ol class="rf-todo">${L.map(t => `<li>${dd(t.days)}${t.html}</li>`).join('')}</ol>` : '<p class="note">지금 자료로는 돌려받을 금액이 보이지 않습니다. 시설의 과세·면세 표시와 ③ 귀속을 다시 확인하세요.</p>';
    el.insertAdjacentHTML('beforeend', `<div class="actions"><button type="button" class="btn" id="rf-zip">경정청구 묶음 내려받기(zip)</button> <button type="button" class="btn secondary" id="rf-print">할 일 인쇄</button> <span class="note">묶음: 과세기간별 결과·건별 명세·공급자별 합계(합계표 추가분)·근거 조문·사유 초안·질의서 초안</span></div>`);
    $('rf-zip')?.addEventListener('click', () => { const z = $('rv-zip'); if (z) z.click(); });
    $('rf-print')?.addEventListener('click', () => { document.body.dataset.printHead = `지난 돈 돌려받기 — 할 일 · ${org?.org ?? ''} · ${today}`; document.body.classList.add('print-todo'); window.print(); setTimeout(() => document.body.classList.remove('print-todo'), 500); });
  }

  function calc(b: Built | null) { const el = $('rf-calc'); if (!el) return; const L = openPeriods(); const estBy = new Map<string, number>();
    for (const r of ctx?.rows ?? []) if (r.taxable && L.includes(r.p)) estBy.set(r.p, (estBy.get(r.p) ?? 0) + r.est);
    const nm = (k: string) => { const [y, h] = k.split('-'); return `${y}년 제${h}기`; }; const win = L.length ? `${nm(L[0])} ~ ${nm(L[L.length - 1])} (${L.length}개 과세기간)` : '';
    el.innerHTML = b?.diags?.length ? refundCalcHtml(D, b.diags, estBy, win) : '';
    el.querySelectorAll<HTMLAnchorElement>('[data-open-dg]').forEach(a => a.addEventListener('click', () => { const d = document.getElementById(`rf-dg-${a.dataset.openDg}`) as HTMLDetailsElement | null; if (d) d.open = true; })); }
  function diag(b: Built | null) { const el = $('rf-diag'); if (!el) return; el.innerHTML = b?.diag ? b.diag : commonMistakesHtml(D); }
  const forced = new Set<string>();
  function ask(b: Built | null) { const el = $('rf-ask'); if (!el) return; const o = getOrg(); const L = openPeriods();
    const stake = new Map<string, { tax: number; est: number }>(); for (const [k, v] of Object.entries(b?.facTax ?? {})) stake.set(k, { tax: v, est: 0 });
    for (const r of ctx?.rows ?? []) { if (!r.a || !L.includes(r.p)) continue; const x = stake.get(r.a.fid) ?? { tax: 0, est: 0 }; x.est += r.est; stake.set(r.a.fid, x); }
    const hasList = (b?.rows ?? 0) > 0; const fl = b?.filed ?? []; const salesFiled = fl.length ? fl.reduce((s, f) => s + (f.salesSup ?? 0), 0) : null;
    const qs = buildQuestions(D, o, stake, { hasList, salesFiled, forced }); el.innerHTML = askHtml(D, o, qs, hasList);
    const done = () => { location.hash = 'rf-ask'; location.reload(); };
    el.querySelectorAll<HTMLButtonElement>('.rf-q [data-ans]').forEach(btn => btn.addEventListener('click', () => { const box = btn.closest<HTMLElement>('.rf-q')!; const q = qs.find(x => x.key === box.dataset.qkey); const oo = getOrg(); if (!q || !oo) return; answer(oo, q.members[0].fid, q.members[0].def, btn.dataset.ans === 'x' ? null : Number(btn.dataset.ans)); done(); }));
    el.querySelectorAll<HTMLButtonElement>('[data-gsub],[data-gsub-x]').forEach(btn => btn.addEventListener('click', () => { const key = btn.dataset.gsub ?? btn.dataset.gsubX!; const q = qs.find(x => x.key === key); const oo = getOrg(); if (!q || !oo) return;
      const on = new Set([...el.querySelectorAll<HTMLInputElement>('input[data-gm]')].filter(i => i.dataset.gm === key && i.checked).map(i => i.dataset.fid!)); answerGroup(oo, q, on, btn.dataset.gsubX !== undefined); done(); }));
    el.querySelectorAll<HTMLButtonElement>('[data-reask]').forEach(btn => btn.addEventListener('click', () => { forced.add(btn.dataset.reask!); ask(last); $('rf-ask')?.scrollIntoView({ block: 'start' }); }));
    el.querySelectorAll<HTMLButtonElement>('[data-undo]').forEach(btn => btn.addEventListener('click', () => { const [fid, id] = btn.dataset.undo!.split('|'); const oo = getOrg(); if (!oo) return; undo(oo, fid, id); done(); }));
  }
  function draw() { const b = last; band(b); calc(b); step1(); ask(b); step2(b); step3(b); diag(b); todo(b); }
  document.addEventListener('vat-rv-built', e => { last = (e as CustomEvent<Built>).detail; draw(); });
  void contractsCtx(D, org).then(c => { ctx = c; draw(); });
  draw();
  /* '다른 방법' 펼침 안 탭 / 자세히 보기로 가는 링크 */
  document.querySelectorAll<HTMLAnchorElement>('a[href="#rf-more"]').forEach(a => a.addEventListener('click', () => { const d = $('rf-more') as HTMLDetailsElement | null; if (d) d.open = true; }));
}
