/** /vat/review/ 세 걸음 판(2026-11-05 docs/prompts/vat_refund_3steps.md · 설계 docs/design/vat-refund-3steps.md).
 *  ① 기관 고르기 ② 지난 신고서 올리기 ③ 홈택스 매입 목록 올리기 — 걸음마다 금액 띠(#rf-band) 하나가 갱신되고, 끝은 할 일 목록(#rf-todo).
 *  계산은 vat_review.ts 그대로(이 모듈은 'vat-rv-built' 이벤트를 듣고 그리기만). 나라장터 계약(vat_contracts.ts)으로 ① 요약과 ② 기간 비교를 만든다.
 *  추정(계약금액 × 10/110)은 회색 작은 글씨 — 돌려받을 금액이 아니다. 판정은 참고이며 기관의 판단이 아니다. */
import { $, esc, fmt, loadData, getOrg, claimPeriod, ymd, lawLink, uniq, facilityRule, facilityStatus, bizType, downloadText, toCsv, penaltyCalc, type Data, type Basis } from './vat_rules';
import { contractsCtx, type CtrCtx } from './vat_contracts';
import { commonMistakesHtml, refundCalcHtml, refundCalc, PLAIN, type Diag, type CalcRow } from './vat_diag';
import { buildQuestions, askHtml, answer, answerGroup, undo, revenueOf } from './vat_ask';
import { focusHtml, wireFocus } from './vat_focus';
import type { UResult } from './vat_unlock';

type Per = { k: string; name: string; filed: string; deduct: number | null; open: boolean; days: number; claim: string; due: string; diff: number | null; should: number };
type Built = { diags?: Diag[]; diag?: string; fsure?: number; facTax?: Record<string, number>; rows: number; U?: UResult; total?: number; capTotal?: number; undAll?: number; needDed?: number; per?: Per[]; sup?: { n: number; assigned: number; ctr: number; taxAll: number; taxAssigned: number; todo: number }; filed: { k: string; deduct: number | null; er: number | null; salesSup?: number | null; total?: number | null; ex5?: number | null }[]; filedState: Record<string, { filed: string; deduct: number | null }>; ctx: { gov: string; name: string } | null };

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
      else if (st === 'check') { why = `${fn}(${via})는 「${esc(rule?.name ?? '')}」 유형 — 운영 방식에 따라 과세·면세가 갈립니다: ${esc(rule?.cond || rule?.note || '')}`; bs = rule?.basis ?? []; extra = ' · 먼저 이 시설의 운영 방식(사용료를 받는지, 계속·반복 대관인지)을 확인하세요'; }
      else { why = `${fn}(${via})는 「${esc(rule?.name ?? '과세 시설')}」 유형으로 두어 과세 시설로 봅니다 — ${esc(rule?.cond || rule?.note || '')} 과세사업에 쓴 지출의 매입세액은 공제 대상입니다(유형이 다르면 확인 질문에서 고치면 다시 셉니다)`; bs = [B('act', '제38조'), ...(rule?.basis ?? [])]; }
    } else { const t = bizType(D, c.nm); why = `시설은 못 붙었지만 계약명이 「${esc(t?.name ?? '')}」 유형입니다 — ${esc(t?.hint ?? '')}`; bs = [B('act', '제38조'), B('act', '제39조')]; extra = ' · 먼저 이 시설이 사용료를 받는(과세) 시설인지 확인하세요 — ③ 매입 목록에서 공급자를 시설에 붙이면 다음부터 저절로 붙습니다'; }
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
      ${est && !(b?.filed?.length) ? `<p class="rf-est note">참고: 경정청구가 되는 기간에 과세 시설과 관련된 나라장터 계약의 부가세는 약 ${(est / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}억 원입니다. 이 가운데 공제받지 않은 몫이 있는지 지난 신고서로 확인합니다(돌려받을 금액이 아님).</p>` : ''}`;
  }

  function step1() {
    const body = $('rf-s1-body'); if (!body) return;
    if (!org) { setStep('rf-s1', false, true, '먼저 기관을 고르세요'); return; }
    const L = openPeriods(); const m = ctrByP(); const uq = (f: (r: CtrCtx['rows'][number]) => boolean) => new Set((ctx?.rows ?? []).filter(r => f(r) && L.includes(r.p)).map(r => r.ck)).size; const nTax = uq(r => r.taxable), nLik = uq(r => r.likely);
    const bar = L.map(k => { const P = pInfo(k); const x = m.get(k); return `<li class="${P.days < 120 ? 'soon' : ''}"><b>${esc(pName(k))}</b> <span class="meta">${P.days < 120 ? '⚠ ' : ''}D-${P.days} · ${esc(P.claim)}까지</span>${x ? ` <span class="note">계약 ${x.nTax + x.nLikely}건</span>` : ''}</li>`; }).join('');
    const gp = (D.govs ?? []).find(g => org.org === g.name || org.org.endsWith(g.name.replace(/^대구광역시\s*/, '')) && g.level === '기초' || (g.level === '광역' && org.org === '대구광역시'));
    const prof = gp ? `<details class="vat-more rf-gov"><summary>${esc(gp.name)}의 특성 — ${esc(gp.status)}${gp.corp.length ? ` · ${esc(gp.corp.map(c => c.name.replace(/\(.*$/, '')).join('·'))}` : ''}</summary>${gp.traits.length ? `<ul class="meta-list">${gp.traits.map(t => `<li>${esc(t)}</li>`).join('')}</ul>` : ''}${gp.corp.length ? `<ul class="meta-list">${gp.corp.map(c => `<li>${esc(c.name)}${c.bizno ? ` ${esc(c.bizno)}` : ''}${c.src ? ` <span class="meta">(${esc(c.src)})</span>` : ''}${c.note ? ` — ${esc(c.note)}` : ''}</li>`).join('')}</ul>` : ''}<p class="note">자료: ${[gp.preset ? `예시 설정 시설 ${gp.preset}곳` : '예시 설정 없음(세입예산서 시설 후보만)', gp.revenue ? `2026 세입예산서 ${gp.revenue}줄` : '', gp.contracts?.n ? `나라장터 계약 ${fmt(gp.contracts.n)}건(${esc(gp.contracts.from)}~${esc(gp.contracts.to)})` : '나라장터 계약 아직 없음'].filter(Boolean).join(' · ')}. 다른 지자체로 바꾸려면 위 「기관 바꾸기」.</p></details>` : '';
    body.innerHTML = `<p><strong>${esc(org.org)}</strong> — 시설 ${org.facilities.length}곳</p>${prof}${focusHtml(D, getOrg(), stakeOf(last), (last?.rows ?? 0) > 0)}
      <details class="vat-more rf-s1-more"><summary>이 기관의 공개 자료 · 경정청구 기한</summary>${ctx ? `<p class="note">이미 받아 둔 공개 자료를 붙였습니다 — 나라장터 계약 ${fmt(ctx.cg.rows.length)}건(${esc(ctx.gov.name)}, ${esc(ctx.cg.from)}~): 과세 시설에 붙은 계약 <b>${nTax}</b>건, 시설은 못 붙었지만 공제 가능성 있는 사업 유형 <b>${nLik}</b>건. 업체 사업자등록번호는 ③에서 매입 목록과 저절로 맞춥니다.</p>` : '<p class="note">이 기관의 나라장터 계약 자료는 아직 없습니다 — ②·③만으로도 됩니다.</p>'}
      <details class="vat-more"><summary>경정청구 기한 — 지금 되는 과세기간 ${L.length}개</summary><ul class="rf-dl">${bar}</ul><p class="note">법정신고기한(1~6월 → 7월 25일, 7~12월 → 다음 해 1월 25일) + 5년(국세기본법 제45조의2). ⚠ 는 120일 안.</p></details></details>`;
    wireFocus(body, getOrg(), () => { location.hash = 'rf-focus'; location.reload(); });
    setStep('rf-s1', true, false, '완료');
  }

  function whyList(first: string[]) {
    const L = openPeriods(); const fs = new Set(first);
    /* 공사 기간으로 나눈 조각을 계약 하나로 다시 모은다 — 경정청구가 되는 기간 몫만 더하고, 먼저 볼 기간에 걸친 계약을 앞으로 */
    const by = new Map<string, CR & { hot: boolean; inWin: string[] }>(); for (const r of (ctx?.rows ?? [])) { if (!(r.taxable || r.likely) || !L.includes(r.p)) continue; const x = by.get(r.ck); if (x) { x.est += r.est; x.inWin.push(r.p); x.hot ||= fs.has(r.p); } else by.set(r.ck, { ...r, hot: fs.has(r.p), inWin: [r.p] }); }
    const all = [...by.values()]; if (!all.length) return '';
    const sorted = all.sort((a, c) => (c.hot ? 1 : 0) - (a.hot ? 1 : 0) || (c.taxable ? 1 : 0) - (a.taxable ? 1 : 0) || c.est - a.est);
    return `<details class="vat-more rf-whys" id="rf-why"><summary>계약별로 — 무엇을 · 왜 · 어떻게 (${fmt(all.length)}건 가운데 ${Math.min(whyN, all.length)}건, 먼저 볼 기간·과세 시설·세액 큰 순)</summary>
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
    if (!filed.size && !ctx) { box.innerHTML = ''; } else box.innerHTML = `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table" data-stack="off" id="rf-cmp"><caption>과세기간별 — 신고한 매입세액과 과세 시설일 법한 계약(참고)</caption><thead><tr><th scope="col">과세기간</th><th scope="col">신고한 매입세액 (18)</th><th scope="col">계약 세액 추정(참고)</th><th scope="col">큰 계약</th><th scope="col">경정청구 기한</th><th scope="col">표시</th></tr></thead><tbody>${rows.map(r => `<tr data-pk="${r.k}" class="${r.flag === '먼저 볼 기간' || r.flag === '기한후신고 후보' ? 'rf-hot' : ''}"><th scope="row">${esc(pName(r.k))}</th><td data-label="신고한 매입세액 (18)">${r.none ? '신고 안 함' : r.ded === null ? '<span class="note">—</span>' : fmt(r.ded)}</td><td class="note" data-label="계약 세액 추정(참고)">${r.est ? fmt(r.est) : '—'}</td><td class="note rf-cmp-top" data-label="큰 계약">${r.x?.top.map(esc).join('<br>') ?? ''}</td><td data-label="경정청구 기한">${esc(r.P.claim)} <span class="meta">D-${r.P.days}</span></td><td data-label="표시">${r.flag ? `<span class="vbadge">${esc(r.flag)}</span>` : ''}</td></tr>`).join('')}</tbody></table></div>
      <p class="note">계약 세액 추정은 과세 시설(또는 공통)에 붙은 계약과 공제 가능성 있는 사업 유형 계약의 계약금액 × 10/110 입니다. 신고 매입세액은 모든 지출의 합계라 견줌은 '먼저 볼 순서'일 뿐 증거가 아닙니다. 공사 기성·준공 세금계산서는 계약 다음 기에 나올 수 있습니다.</p>
      <p class="rf-pick" id="rf-pick">${pickTxt ? `<strong>홈택스에서 받을 기간:</strong> ${esc(pickTxt)} <span class="note">— ③에서 이 기간의 매입 목록부터 올리세요(나머지 기간은 그다음).</span>` : filed.size ? '<strong>홈택스에서 받을 기간:</strong> 계약으로는 눈에 띄는 기간이 없습니다 — ③에 경정청구가 되는 기간 전부를 올리세요.' : '<span class="note">지난 신고서를 올리면 기간마다 신고한 매입세액이 채워지고, 먼저 볼 기간이 표시됩니다.</span>'}</p>${whyList(pick.map(r => r.k))}`;
    $('rf-why-more')?.addEventListener('click', () => { whyN += 20; step2(last); const d = $('rf-why') as HTMLDetailsElement | null; if (d) d.open = true; });
    const done = !!b && b.filed.length > 0; setStep('rf-s2', done, !!org && !done, done ? `신고서 ${b!.filed.length}개 과세기간` : '신고서 PDF 를 놓으세요');
    { const det = $('rf-s2-more') as HTMLDetailsElement | null; const sum = $('rf-s2-more-sum'); if (det && det.dataset.done !== String(done)) { det.dataset.done = String(done); det.open = !done; }   /* 신고서를 올렸으면 목록·표는 접고 결과를 먼저 */
      if (sum) sum.textContent = done ? `올린 신고서 ${b!.filed.length}개 과세기간 — 목록·과세기간별 신고 값 펼치기` : '올린 신고서 목록 · 과세기간별 신고 값'; }
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
    document.querySelectorAll<HTMLButtonElement>('[data-copy-memo]:not([data-wired])').forEach(b => { b.dataset.wired = '1'; b.addEventListener('click', async () => { try { await navigator.clipboard.writeText(b.dataset.copyMemo ?? ''); b.textContent = '복사했어요'; } catch { window.prompt('아래 글을 복사하세요', b.dataset.copyMemo ?? ''); } }); });
    $('rf-calc-zip')?.addEventListener('click', () => { const z = $('rv-zip'); if (z) z.click(); else document.dispatchEvent(new CustomEvent('vat-filed-bundle')); });
    el.querySelectorAll<HTMLAnchorElement>('[data-open-dg]').forEach(a => a.addEventListener('click', () => { const d = document.getElementById(`rf-dg-${a.dataset.openDg}`) as HTMLDetailsElement | null; if (d) d.open = true; })); }
  function diag(b: Built | null) { const el = $('rf-diag'); if (!el) return; el.innerHTML = b?.diag ? b.diag : commonMistakesHtml(D); el.querySelectorAll<HTMLButtonElement>('[data-copy-memo]:not([data-wired])').forEach(x => { x.dataset.wired = '1'; x.addEventListener('click', async () => { try { await navigator.clipboard.writeText(x.dataset.copyMemo ?? ''); x.textContent = '복사했어요'; } catch { window.prompt('아래 글을 복사하세요', x.dataset.copyMemo ?? ''); } }); }); }
  const forced = new Set<string>();
  /* 시설별로 걸린 돈 — 매입 목록 세액(tax)과 경정청구가 되는 과세기간의 계약 세액 어림(est). 질문 엔진·'먼저 볼 곳'이 같이 쓴다 */
  function stakeOf(b: Built | null) { const L = openPeriods();
    const stake = new Map<string, { tax: number; est: number }>(); for (const [k, v] of Object.entries(b?.facTax ?? {})) stake.set(k, { tax: v, est: 0 });
    for (const r of ctx?.rows ?? []) { if (!r.a || !L.includes(r.p)) continue; const x = stake.get(r.a.fid) ?? { tax: 0, est: 0 }; x.est += r.est; stake.set(r.a.fid, x); }
    return stake; }
  function ask(b: Built | null) { const el = $('rf-ask'); if (!el) return; const o = getOrg();
    const stake = stakeOf(b);
    const hasList = (b?.rows ?? 0) > 0; const fl = b?.filed ?? []; const salesFiled = fl.length ? fl.reduce((s, f) => s + (f.salesSup ?? 0), 0) : null;
    const all = buildQuestions(D, o, stake, { hasList, salesFiled, forced }); const qs = hasList ? all : all.filter(q => forced.has(q.key) || q.members.some(m => forced.has(`${m.fid}|${m.def.id}`)));   /* 매입 목록을 올리기 전에는 묻지 않는다(계약 어림만으로는 금액이 갈리지 않음) — 「바꾸기」로 연 것만 */
    el.innerHTML = askHtml(D, o, qs, hasList);
    const done = () => { location.hash = 'rf-ask'; location.reload(); };
    el.querySelectorAll<HTMLButtonElement>('.rf-q [data-ans]').forEach(btn => btn.addEventListener('click', () => { const box = btn.closest<HTMLElement>('.rf-q')!; const q = qs.find(x => x.key === box.dataset.qkey); const oo = getOrg(); if (!q || !oo) return; answer(oo, q.members[0].fid, q.members[0].def, btn.dataset.ans === 'x' ? null : Number(btn.dataset.ans)); done(); }));
    el.querySelectorAll<HTMLButtonElement>('[data-gsub],[data-gsub-x]').forEach(btn => btn.addEventListener('click', () => { const key = btn.dataset.gsub ?? btn.dataset.gsubX!; const q = qs.find(x => x.key === key); const oo = getOrg(); if (!q || !oo) return;
      const on = new Set([...el.querySelectorAll<HTMLInputElement>('input[data-gm]')].filter(i => i.dataset.gm === key && i.checked).map(i => i.dataset.fid!)); answerGroup(oo, q, on, btn.dataset.gsubX !== undefined); done(); }));
    el.querySelectorAll<HTMLButtonElement>('[data-reask]').forEach(btn => btn.addEventListener('click', () => { forced.add(btn.dataset.reask!); ask(last); $('rf-ask')?.scrollIntoView({ block: 'start' }); }));
    el.querySelectorAll<HTMLButtonElement>('[data-undo]').forEach(btn => btn.addEventListener('click', () => { const [fid, id] = btn.dataset.undo!.split('|'); const oo = getOrg(); if (!oo) return; undo(oo, fid, id); done(); }));
  }
  /* ③ 결과 요약 — 쉬운 화면(2026-11-05 docs/prompts/vat_review_ux_easiest.md): 한 문장 → 금액 두 칸(확정 / 확인하면 늘어날 수 있는 몫, 참고 어림은 접힘)
     → 출처 사슬 → 과세기간별 한 줄(무엇이 · 얼마 · 기한, 펼치면 왜·할 일·근거) → 빠진 기간 · 0원 → 내려받기 둘. 숫자는 refundCalc(돌려받을 돈 표)와 같다 — 새 계산 없음 */
  const josa = (w: string) => { const c = w.charCodeAt(w.length - 1); return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? '은' : '는'; };
  function summary(b: Built | null) {
    const el = $('rf-sum'); if (!el) return;
    const nF = b?.filed.length ?? 0, nR = b?.rows ?? 0;
    setStep('rf-go2', nF + nR > 0, !!org && nF + nR === 0, nF + nR ? `신고서 ${nF}개 과세기간${nR ? ` · 매입 ${fmt(nR)}건` : ''}` : org ? '파일을 놓으세요' : '기관을 고르면 열립니다');
    const done3 = (t: string) => setStep('rf-go3', !!t, false, t);
    if (!org) { el.innerHTML = '<p class="rf-empty">기관을 고르고 파일을 올리면 여기에 돌려받을 금액이 나옵니다.</p>'; done3(''); return; }
    if (!b || !(nF + nR)) { el.innerHTML = '<p class="rf-empty">2에 홈택스에서 받은 지난 신고서 PDF 를 놓으면 여기에 돌려받을 금액이 나옵니다.</p>'; done3(''); return; }
    const L = openPeriods(); const estBy = new Map<string, number>(); for (const r of ctx?.rows ?? []) if (r.taxable && L.includes(r.p)) estBy.set(r.p, (estBy.get(r.p) ?? 0) + r.est);
    const diags = b.diags ?? []; const R = refundCalc(diags, estBy); const U = b.U; const listOnly = !diags.length && !!U;
    const sure = listOnly ? U!.now : R.sure; const upto = listOnly ? U!.docs + U!.judge : R.upto; const est = listOnly ? 0 : R.est;
    const ex = diags.filter(d => d.state === 'expired' || d.days < 0);
    /* 매입 목록 없이 더 찾기(운영자 2026-11-05 '매입 목록 없이도 더 찾을 수 있게 해'): 신고서를 올린 과세기간마다
       '그 기간 신고서의 받은 부가세 합계 (16)' < '과세 시설 전용으로 붙은 나라장터 계약의 부가세 어림(계약금액 × 10/110, 공사 기간에 나눔, 과세 몫 share)' 이면
       차이만큼은 세금계산서가 신고에 아예 들어가지 않았을 수 있다(하한 — (16)에는 다른 지출도 들어 있으므로). 여기에 신고서가 '면세사업 관련'으로
       공제하지 않은 세액(⑤) 가운데 계약 어림까지를 더한 값(계약 어림을 넘지 않게)을 '후보(추정)'로 — 확정·최대와 섞지 않고, 확인할 업체 목록을 준다. 새 판정 규칙 없음 */
    type CC = { k: string; name: string; recv: number; ex5: number; est: number; miss: number; part5: number; cand: number; reg: number; fids: string[]; sups: { no: string; nm: string; est: number; ctrs: { nm: string; date: string; k: string; fac: string; est: number }[] }[] };
    const cands: CC[] = [];
    if (!nR && ctx) { const fk = new Map(b.filed.map(f => [f.k, f]));
      for (const k of L) { const f = fk.get(k); if (!f || f.total == null) continue;
        const rs = (ctx.rows ?? []).filter(r => r.p === k && r.taxable && r.a && r.a.fid !== 'admin' && r.a.fid !== 'exempt' && r.a.use !== 'admin' && r.a.use !== 'multi');
        const est = rs.reduce((n, r) => n + r.est, 0); if (!est) continue;
        const miss = Math.max(0, est - f.total); const part5 = Math.min(f.ex5 ?? 0, est); const cand = Math.min(est, miss + part5); if (cand <= 0) continue;
        const bySup = new Map<string, CC['sups'][number]>(); for (const r of rs) { const cs = r.c.corps.filter(p => /^\d{10}$/.test(p.no)); const key = cs[0]?.no ?? `?${r.c.nm}`; const x = bySup.get(key) ?? { no: cs[0]?.no ?? '', nm: cs.map(p => p.nm).join('·') || '(상호 확인)', est: 0, ctrs: [] }; x.est += r.est; const fac = org.facilities.find(q => q.id === r.a!.fid)?.name ?? ''; x.ctrs.push({ nm: r.c.nm, date: r.c.date, k: r.c.k, fac, est: r.est }); bySup.set(key, x); }
        cands.push({ k, name: pName(k), recv: f.total, ex5: f.ex5 ?? 0, est, miss, part5, cand, reg: cand - part5, fids: [...new Set(rs.map(r => r.a!.fid))], sups: [...bySup.values()].sort((a, c) => c.est - a.est) }); } }
    const candSum = cands.reduce((n, c) => n + c.cand, 0); const candIn = cands.reduce((n, c) => n + c.part5, 0); const candReg = candSum - candIn;
    /* 세무 검토 반영(2026-11-05 운영자 '순서대로 수정해' — 세무법인 관점 평가 1~4):
       ① 신고서에 없던 몫(candReg)은 그 시설이 사업자등록돼 있었고 세금계산서가 그 번호로 발급됐을 때만 — 등록 전 매입세액 불공제(법 제39조 제1항 제8호), 고유번호 기재분은 공급받는자가 달라 수정세금계산서(시행령 제70조) 기한 안에만
       ② 확정 가운데 안분·정산을 다시 한 몫은 원신고가 공급가액 비율로 나눴을 때만 맞음(시행령 제81조 제4항, 대법원 2017두55329)
       ③ 순액 — 과세 시설 몫은 그 시설 사용료를 과세 매출로 신고해 왔을 때만 그대로; 아니면 매출세액·과소신고·납부지연 가산세(세입예산서 연 수입 기준 어림)를 뺀다 */
    const APP = new Set(['apportion-calc', 'settle', 'no-apportion']); const sureApp = listOnly ? 0 : R.rows.filter(r => r.kind === 'sure' && APP.has(r.f.key)).reduce((n, r) => n + (r.f.effect ?? 0), 0);
    let salesTax = 0, salesPen = 0; const noRev = new Set<string>(); const revF = new Set<string>();
    /* 그 기간 신고서의 과세 매출((1)~(4) 공급가액)에 이미 들어 있을 만큼은 빼고, 시설 수입(세입예산 연 수입 ÷ 2, 부가세 포함 금액으로 보고 ÷ 11)이 신고 매출을 넘는 몫만 위험으로 센다 */
    for (const c of cands) { const P = pInfo(c.k); let gross = 0; for (const fid of c.fids) { const f = org.facilities.find(q => q.id === fid); if (!f) continue; const rv = revenueOf(f); if (!rv) { noRev.add(f.name); continue; } revF.add(f.name); gross += rv / 2; }
      const filedSales = (b.filed.find(f => f.k === c.k)?.salesSup ?? 0) * 1.1; const tax = Math.round(Math.max(0, gross - filedSales) / 11); if (!tax) continue; salesTax += tax; salesPen += penaltyCalc(D, { tax, due: P.due, payDate: today, kind: 'under' }).total; } const supN = new Set(cands.flatMap(c => c.sups.map(x => x.no || x.nm))).size;
    const nm = org.org; const amt = `<b id="rf-sum-amt" class="rf-sum-n">${fmt(sure)}원</b>`;
    const head = sure > 0 ? `<p class="rf-sum-l"><strong>${esc(nm)}</strong>${josa(nm)} 지난 신고를 고쳐 신청하면(경정청구) ${amt}을 돌려받을 수 있습니다.${upto > 0 ? ` 자료를 더 확인하면 <b>최대 ${fmt(upto)}원</b>까지 늘어날 수 있습니다.` : ''}</p>`
      : upto > 0 ? `<p class="rf-sum-l">지금 올린 숫자만으로 바로 돌려받을 돈은 ${amt}이지만, 자료를 더 확인하면 <b>최대 ${fmt(upto)}원</b>을 돌려받을 수 있습니다.</p>`
      : `<p class="rf-sum-l">찾은 돌려받을 돈: ${amt}</p>`;
    const headCand = candSum > 0 ? `<p class="rf-sum-l2">매입 목록 없이 나라장터 계약으로 보면${candIn ? ` 신고서에 들어 있던 세금계산서 가운데 <b>약 ${fmt(candIn)}원</b>을` : ''}${candIn && candReg ? ',' : ''}${candReg ? ` 그 시설이 사업자등록돼 있었고 세금계산서가 그 번호로 발급됐다면 <b>약 ${fmt(candReg)}원</b>을` : ''} 더 돌려받을 수 있을지 모릅니다 — 업체 ${supN}곳의 세금계산서만 확인하면 됩니다(추정, 아래 「매입 목록 없이 더 찾은 것」).</p>` : '';
    const netHtml = sure > 0 || candSum > 0 ? `<p class="rf-net" id="rf-net"><span class="rf-k">순으로 보면</span> ${sure > 0 ? `확정 ${fmt(sure)}원은 계산을 바로잡는 것이라 매출 쪽 영향 없이 그대로 돌려받습니다.` : ''}${candSum > 0 ? ` 계약으로 찾은 후보 ${fmt(candSum)}원은 그 시설 사용료를 과세 매출로 신고해 왔을 때만 그대로입니다.${salesTax ? ` 그 시설들 수입이 신고서의 과세 매출보다 많은 기간에는 신고하지 않은 사용료가 있을 수 있어, 그 부가세 약 <b>${fmt(salesTax)}원</b>과 가산세 약 <b>${fmt(salesPen)}원</b>을 빼면 순으로 약 <b id="rf-net-amt">${fmt(candSum - salesTax - salesPen)}원</b>입니다(2026년 세입예산 수입 ÷ 2 − 그 기간 신고 과세 매출, 어림 — ${esc([...revF].slice(0, 3).join('·'))}${revF.size > 3 ? ` 외 ${revF.size - 3}곳` : ''}).` : ''}${noRev.size ? ` ${esc([...noRev].slice(0, 3).join('·'))}${noRev.size > 3 ? ` 외 ${noRev.size - 3}곳` : ''}은 수입 자료가 없어 매출 쪽을 세지 못했습니다.` : ''}` : ''}</p>` : '';
    const cells = `<div class="rf-sum-cells"><div><span class="meta">확정 — 신고서 숫자로 다시 계산</span><b>${fmt(sure)}원</b></div><div><span class="meta">확인하면 늘어날 수 있는 몫(최대)</span><b>+${fmt(upto)}원</b></div>${candSum > 0 ? `<div class="rf-cand-cell"><span class="meta">계약으로 찾은 후보(추정)</span><b id="rf-cand-amt">+${fmt(candIn)}원</b>${candReg ? `<span class="meta" id="rf-cand-reg">사업자등록·번호가 맞으면 +${fmt(candReg)}원 더</span>` : ''}</div>` : ''}</div>${sureApp > 0 ? `<p class="note rf-sure-cond" id="rf-sure-cond">확정 가운데 ${fmt(sureApp)}원은 함께 쓴 비용의 부가세를 나누는 계산을 다시 한 몫입니다 — 원래 신고가 공급가액 비율로 나눴을 때만 맞습니다. 본청·행정과 함께 쓴 비용처럼 공급가액이 없는 쪽이 섞이면 매입가액·면적 같은 다른 기준을 써야 할 수 있으니(시행령 제81조 제4항, 대법원 2017두55329), 원래 신고서의 「공제받지 못할 매입세액 명세서」가 어떤 기준으로 나눴는지 먼저 확인하세요.</p>` : ''}${est ? `<details class="vat-more rf-est-more"><summary>참고 어림 보기</summary><p class="note">나라장터 계약 금액으로 짐작한 값 약 ${fmt(est)}원 — 신청할 금액이 아닙니다. 매입 목록을 올리면 실제 세금계산서로 셉니다.</p></details>` : ''}`;
    const src = `<p class="rf-src note">과세기간 ${nF}개의 신고서${nR ? `와 매입 ${fmt(nR)}건` : '로'}${nR ? '으로' : ''} 다시 계산했습니다 · 참고 계산이며 기관의 판단이 아닙니다.</p>`;
    /* 과세기간별 한 줄 */
    const byK = new Map<string, CalcRow[]>(); const other: CalcRow[] = []; let miss: CalcRow | null = null;
    for (const r of R.rows) { if (r.k === 'nofile') { miss = r; continue; } if (r.kind === 'sure' || r.kind === 'upto') { const a = byK.get(r.k) ?? []; a.push(r); byK.set(r.k, a); } else other.push(r); }
    const plainT = (r: CalcRow) => PLAIN[r.f.key]?.t ?? r.f.title; const plainTodo = (r: CalcRow) => PLAIN[r.f.key]?.todo ?? r.f.how;
    const money = (r: CalcRow) => r.kind === 'sure' ? `<b class="num">${fmt(r.f.effect ?? 0)}원</b>` : `<span class="num">최대 ${fmt(r.f.effect ?? 0)}원</span>`;
    const why = (r: CalcRow) => `<details class="rf-row-why"><summary>왜 · 어떻게</summary><p><span class="rf-k">할 일</span> ${esc(plainTodo(r))}</p><p class="note"><span class="rf-k">이유</span> ${esc(r.f.what)}</p>${APP.has(r.f.key) ? `<p class="note"><span class="rf-k">확인</span> 원래 신고가 공급가액 비율로 나눴을 때의 금액입니다. 매입가액·면적 기준으로 나눴다면 이 금액은 맞지 않습니다(시행령 제81조 제4항).</p>` : ''}${r.f.basis.length ? `<p class="note"><span class="rf-k">근거</span> ${law(r.f.basis)}</p>` : ''}${r.kind === 'sure' && diags.find(d => d.k === r.k)?.corrected?.length ? `<p><a href="#rf-dg-${esc(r.k)}" data-open-dg="${esc(r.k)}">고친 신고서 보기 ↓</a></p>` : ''}</details>`;
    const ks = [...byK.keys()].sort((a, c) => { const s = (k: string) => byK.get(k)!.reduce((n, r) => n + (r.kind === 'sure' ? (r.f.effect ?? 0) * 1e3 : (r.f.effect ?? 0)), 0); return s(c) - s(a); });
    const rows = ks.map(k => { const rs = byK.get(k)!; const r0 = rs[0]; return `<li class="rf-row"><div class="rf-row-h"><b>${esc(r0.name)}</b> <span class="meta">신청 기한 ${esc(r0.claim)}${r0.days <= 120 ? ' ⚠' : ''} · D-${r0.days}</span></div><ul>${rs.map(r => `<li><span class="rf-row-t">${esc(plainT(r))}</span> ${money(r)}${why(r)}</li>`).join('')}</ul></li>`; }).join('');
    const listUl = rows ? `<h3 class="rf-sum-h">과세기간별</h3><ol class="rf-rows">${rows}</ol>` : '';
    const otherHtml = other.length ? `<details class="vat-more"><summary>그 밖에 확인할 것 ${other.length}건(금액 없음)</summary><ul class="meta-list">${other.map(r => `<li><b>${esc(r.name)}</b> — ${esc(plainT(r))}<br><span class="note">${esc(plainTodo(r))}</span></li>`).join('')}</ul></details>` : '';
    const missHtml = miss ? `<p class="callout warn rf-miss-l">⚠ 신고서를 올리지 않은 과세기간이 있습니다 — ${esc(miss.f.what.replace(/ — 이 기간들도.*$/, ''))}. 올리면 더 찾을 수 있습니다.</p>` : '';
    const exHtml = ex.length ? `<p class="note">경정청구 기한(5년)이 지난 ${ex.length}개 과세기간(${ex.map(d => esc(d.name)).join(' · ')})은 돌려받을 수 없어 뺐습니다.</p>` : '';
    const zero = sure === 0 && upto === 0 && candSum === 0 ? `<div class="rf-zero"><p><b>찾은 것이 없습니다.</b> 이런 경우일 수 있습니다:</p><ol><li>지난 신고가 맞게 되어 있습니다.</li><li>신고서 숫자만으로는 보이지 않는 것 — 돈을 받는 시설(체육관·주차장·임대 등)에 쓴 비용을 공제하지 않은 경우는 <b>매입 목록 엑셀</b>을 올려야 찾습니다.</li><li>${ex.length && !rows ? '올린 신고서가 모두 경정청구 기한(5년)이 지났습니다.' : '올린 신고서가 일부 기간뿐입니다 — 5년치를 모두 올려 보세요.'}</li></ol></div>` : '';
    const sup = b.sup?.todo ? `<p class="note">매입 목록의 공급자 ${b.sup.todo}곳은 어느 시설 것인지 정하지 못해 아직 셈에 없습니다 — <a href="#rf-files" data-open-sec="rf-files">파일별로 보기·고치기</a>에서 정하세요.</p>` : '';
    const dl = sure > 0 || upto > 0 || candSum > 0 ? `<div class="rf-dl actions no-print"><button type="button" class="btn" id="rf-dl-submit">세무서·홈택스에 낼 자료 받기 <small>(엑셀+PDF)</small></button></div>
      <p class="note">돌려받는 신청은 홈택스 → 신고/납부 → 세금신고 → 부가가치세 → 경정청구 메뉴에서, 자료 안의 「고친 신고서」 값을 칸마다 옮겨 적으면 됩니다.${sure > 0 ? ` 결재·서면 제출용 <button type="button" class="link-btn no-print" id="rf-dl-form-pdf">경정청구서(국세청 서식) PDF 받기</button> · <button type="button" class="link-btn no-print" id="rf-dl-form">보기·인쇄</button> — 국세기본법 시행규칙 별지 제16호의2서식에 숫자를 채운 것입니다.` : ''}</p>
      <details class="vat-more rf-dl-more no-print"><summary>다른 형식 — 엑셀만 · PDF 만</summary><div class="actions"><button type="button" class="btn secondary" id="rf-dl-xlsx">엑셀만</button><button type="button" class="btn secondary" id="rf-dl-pdf">PDF 만</button></div></details>` : '';
    function candRows(): (string | number)[][] { return [['과세기간', '업체(상호)', '사업자등록번호', '계약명', '종류', '계약일', '시설', '부가세 어림(이 기간 몫)', '이 기간 신고서 받은 부가세 합계(16)', '이 기간 신고서에 들어 있던 몫(면세사업 관련 불공제 중)', '이 기간 신고서에 없던 몫(사업자등록·번호 확인 뒤)', '확인할 것'], ...cands.flatMap(c => c.sups.flatMap(x => x.ctrs.map(t => [c.name, x.nm, x.no, t.nm, t.k, t.date, t.fac, t.est, c.recv, c.part5, c.reg, '① 사업자등록(등록 전 매입 불공제, 법 제39조 제1항 제8호) ② 세금계산서 받는 쪽 번호(고유번호면 수정세금계산서 기한) ③ 사용료 과세 매출 신고'])))]; }
    const candHtml = cands.length ? `<section class="rf-cand" id="rf-cand" aria-labelledby="rf-cand-h"><h3 id="rf-cand-h">매입 목록 없이 더 찾은 것 — 나라장터 계약으로(추정)</h3>
      <p class="note">돈을 받는 시설(체육관·주차장·임대 등)에 쓴 공사·용역·물품 계약의 부가세는 돌려받을 수 있는 돈입니다. 그런데 그 기간 신고서에서 <b>받은 부가세 합계</b>가 이 계약들의 부가세보다 적으면, 세금계산서 일부가 신고에서 빠졌을 수 있습니다. 매입 목록을 통째로 받을 필요 없이 <b>아래 업체만</b> 확인하면 됩니다. 계약 금액으로 짐작한 값이라 신청 금액이 아닙니다.</p>
      <div class="callout warn rf-cand-cond" id="rf-cand-cond"><p><b>돌려받으려면 세 가지가 맞아야 합니다</b></p><ol>
        <li><b>그 시설(사업장)이 그 기간에 사업자등록이 되어 있었나</b> — 등록 신청 전에 산 것의 부가세는 공제하지 않습니다(과세기간이 끝난 뒤 20일 안에 등록을 신청했으면 예외).${org.unit === 'entity' ? ' 사업자 단위 과세라면 그 시설이 종된 사업장으로 신고돼 있으면 됩니다.' : ''}</li>
        <li><b>세금계산서의 받는 쪽 번호가 그 사업자등록번호인가</b> — 고유번호로 받은 세금계산서는 받는 쪽이 달라 공제되지 않을 수 있고, 공급자가 번호를 고쳐 다시 발급(수정세금계산서)할 수 있는 것은 확정신고기한 다음 날부터 1년 안뿐이라 대부분 지났습니다.</li>
        <li><b>그 시설 사용료를 과세 매출로 신고해 왔나</b> — 아니면 사용료의 부가세와 가산세를 먼저 셉니다(위 '순으로 보면').</li></ol>
        <p class="note">그래서 「신고서에 들어 있던 몫」(번호가 맞게 받아 신고했지만 '면세사업 관련'으로 공제하지 않은 것)이 먼저이고, 「신고서에 없던 몫」은 위 두 가지가 확인된 뒤에만 셉니다. <span class="rf-k">근거</span> ${law([B('act', '제39조'), B('decree', '제70조'), B('decree', '제75조')])}</p></div>
      <ol class="rf-rows">${cands.map(c => `<li class="rf-row rf-cand-row" data-k="${esc(c.k)}"><div class="rf-row-h"><b>${esc(c.name)}</b> <span class="num">약 ${fmt(c.cand)}원</span></div>
        <p class="note">신고서의 받은 부가세 합계 ${fmt(c.recv)}원 · 과세 시설 계약의 부가세 약 ${fmt(c.est)}원</p>
        <ul class="rf-cand-tiers">${c.part5 ? `<li><span class="vbadge">신고서에 들어 있던 몫</span> 약 <b>${fmt(c.part5)}원</b> — 신고서가 '면세사업 관련'으로 돌려받지 않은 ${fmt(c.ex5)}원 가운데 이 계약 몫일 수 있어요. 시설이 과세로 확인되면 돌려받습니다.</li>` : ''}${c.reg ? `<li><span class="vbadge warn">신고서에 없던 몫</span> 약 <b>${fmt(c.reg)}원</b> — 신고에 들어가지 않았을 수 있어요. 사업자등록 여부와 세금계산서의 받는 쪽 번호를 확인한 뒤에만 돌려받을 수 있습니다.</li>` : ''}</ul>
        ${c.sups.length > 3 ? `<p class="note">큰 업체 3곳만 확인해도 약 ${fmt(c.sups.slice(0, 3).reduce((n, x) => n + x.est, 0))}원(계약 몫의 ${Math.round(c.sups.slice(0, 3).reduce((n, x) => n + x.est, 0) / c.est * 100)}%)을 볼 수 있어요.</p>` : ''}<details class="rf-row-why"><summary>확인할 업체 ${c.sups.length}곳 · 왜 · 어떻게</summary><ul class="meta-list">${c.sups.slice(0, 12).map(x => `<li><b>${esc(x.nm)}</b>${x.no ? ` ${esc(x.no.replace(/^(\d{3})(\d{2})(\d{5})$/, '$1-$2-$3'))}` : ''} — 약 ${fmt(x.est)}원<br><span class="note">${x.ctrs.slice(0, 3).map(t => `${esc(t.nm)}(${esc(t.k)} · ${esc(t.date)}${t.fac ? ` · ${esc(t.fac)}` : ''})`).join(' / ')}${x.ctrs.length > 3 ? ` 외 ${x.ctrs.length - 3}건` : ''}</span></li>`).join('')}</ul>${c.sups.length > 12 ? `<p class="note">나머지 ${c.sups.length - 12}곳은 업체 목록 파일에 있습니다.</p>` : ''}
          <p><span class="rf-k">할 일</span> 홈택스 → 조회/발급 → 전자세금계산서 → 목록조회 → 매입에서 기간을 ${esc(c.name)}로 두고 '거래처 사업자등록번호'에 위 번호를 넣어 조회합니다. 나온 세금계산서 엑셀을 2에 놓으면 확정 금액으로 바뀝니다.</p>
          <p class="note"><span class="rf-k">이유</span> 돈을 받는 시설(과세사업)에 쓴 비용의 부가세는 돌려받습니다(공제). 세금계산서가 신고에 빠졌거나 '면세사업 관련'으로 처리됐다면 고쳐 신청할 수 있습니다.</p>
          <p class="note"><span class="rf-k">근거</span> ${law([B('act', '제38조'), B('act', '제39조'), B('basic', '제45조의2')])}</p></details></li>`).join('')}</ol>
      <div class="actions no-print"><button type="button" class="btn secondary" id="rf-cand-csv">확인할 업체 목록 받기(CSV)</button></div></section>` : '';
    el.innerHTML = head + netHtml + headCand + cells + src + dl + missHtml + zero + sup + listUl + candHtml + otherHtml + exHtml;
    document.dispatchEvent(new CustomEvent('vat-cand', { detail: cands.length ? candRows() : [] }));   /* 신고서만 올린 묶음(vat_review)에 '추가분 합계표 밑자료'로 */
    $('rf-cand-csv')?.addEventListener('click', () => downloadText(`확인할_업체_목록_${org.org}_${today}.csv`.replace(/\s+/g, '_'), toCsv(candRows()), 'text/csv;charset=utf-8'));
    done3(sure > 0 ? `${fmt(sure)}원` : upto > 0 ? `최대 ${fmt(upto)}원` : candSum > 0 ? `후보 약 ${fmt(candSum)}원` : '찾은 것 없음');
    const fire = (want: 'zip' | 'xlsx' | 'pdf') => { const id = { zip: 'rv-zip', xlsx: 'rv-xlsx', pdf: 'rv-pdf' }[want]; const z = $(id); if (z) z.click(); else document.dispatchEvent(new CustomEvent('vat-filed-bundle', { detail: { want } })); };
    $('rf-dl-submit')?.addEventListener('click', () => fire('zip')); $('rf-dl-xlsx')?.addEventListener('click', () => fire('xlsx')); $('rf-dl-pdf')?.addEventListener('click', () => fire('pdf'));
    el.querySelectorAll<HTMLAnchorElement>('[data-open-dg]').forEach(a => a.addEventListener('click', () => { const dd = $('rf-detail') as HTMLDetailsElement | null; if (dd) dd.open = true; const d = document.getElementById(`rf-dg-${a.dataset.openDg}`) as HTMLDetailsElement | null; if (d) d.open = true; }));
    el.querySelectorAll<HTMLAnchorElement>('[data-open-sec]').forEach(a => a.addEventListener('click', () => { const d = $(a.dataset.openSec!) as HTMLDetailsElement | null; if (d) d.open = true; }));
  }
  function draw() { const b = last; summary(b); band(b); calc(b); step1(); ask(b); step2(b); step3(b); diag(b); todo(b); }
  document.addEventListener('vat-rv-built', e => { last = (e as CustomEvent<Built>).detail; draw(); });
  void contractsCtx(D, org).then(c => { ctx = c; draw(); });
  draw();
  /* '다른 방법' 펼침 안 탭 / 자세히 보기로 가는 링크 */
  document.querySelectorAll<HTMLAnchorElement>('a[href="#rf-more"]').forEach(a => a.addEventListener('click', () => { const d = $('rf-more') as HTMLDetailsElement | null; if (d) d.open = true; }));
}
