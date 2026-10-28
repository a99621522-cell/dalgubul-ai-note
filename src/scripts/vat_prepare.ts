/** /vat/prepare/ 신고 준비(신고 담당). 인계표 → 신고서 칸별 숫자표 + 안분·정산·재계산 + 신고 기록. 참고용 계산, 서버 없음. */
import { renderForms, renderUnitSummary, renderSavings, type UsedRow, type ConvRow } from './vat_forms';
import { $, esc, num, fmt, pct, loadData, getOrg, setOrg, allLedgers, readJsonFile, downloadText, toCsv, facilityStatus, facilityRule, inFiling, salesFacility, convertCredit, periodInfo, periodKeyOf, prevPeriodKey, PRELIM_NOTICE_LIMIT, getFilings, saveFiling, penaltyCalc, lawLink, deemedRent, nextFiling, ymd, toast, helpWire, scrollTo, type Data, type Org, type OrgFacility, type LedgerRow, type Filing, type PeriodKey , rulingsHtml , inquiryHtml, wireInquiry } from './vat_rules';
type Ledger = { fid: string; name: string; type: string; month: string; rows: LedgerRow[]; src: string };
const D = loadData();
if (D) init(D);
function init(D: Data) {
  let org: Org | null = getOrg();
  const ledgers = new Map<string, Ledger>();
  const sales: Record<string, { c1: number; c3: number; c4: number; dep?: number; days?: number; rate?: number; deem?: number }> = {};
  const exemptIn: Record<string, number> = {}; const oneoffIn: Record<string, number> = {}; const adminIn: Record<string, { basis: string; ex: number; tot: number }> = {}; const basisIn: Record<string, { basis: string; ex: number; tot: number; building?: boolean }> = {}; const prelimIn: Record<string, { taxable: number; exempt: number; common: number; nondeduct: number }> = {};
  let includePrelimRows = false;
  const f0 = nextFiling(); $('p-due')!.textContent = `다음 신고 ${f0.name} D-${f0.days}`;
  /* 4단계 위저드 + 고정 요약(공무원 UX 재설계 2026-10-28, docs/design/vat-ux-spec.md §4) — 단계는 보이기만 바꾸고 계산은 그대로 */
  let pstep = 1, pmax = 1; const psteps = [...document.querySelectorAll<HTMLElement>('.pstep')]; const pchips = [...document.querySelectorAll<HTMLButtonElement>('#p-steps button')];
  const pshow = (n: number) => { pstep = n; pmax = Math.max(pmax, n); psteps.forEach(x => { x.hidden = Number(x.dataset.pstep) !== n; }); pchips.forEach((c, i) => { if (i + 1 === n) c.setAttribute('aria-current', 'step'); else c.removeAttribute('aria-current'); c.disabled = i + 1 > pmax; }); const live = $('p-step-live'); if (live) live.textContent = `${n}/4 단계 ${pchips[n - 1]?.textContent ?? ''}`; if (n !== 4) scrollTo($('p-steps')); renderSum(); };
  pchips.forEach(c => c.addEventListener('click', () => { const n = Number(c.dataset.pgo); if (n && n !== pstep && !c.disabled) pshow(n); }));
  document.querySelectorAll<HTMLButtonElement>('[data-pnext]').forEach(b => b.addEventListener('click', () => pshow(Math.min(4, pstep + 1))));
  document.querySelectorAll<HTMLButtonElement>('[data-pprev]').forEach(b => b.addEventListener('click', () => pshow(Math.max(1, pstep - 1))));
  document.addEventListener('keydown', e => { if (!e.altKey) return; if (e.key === 'ArrowRight' && pstep < 4 && (pstep < 3 || pmax >= 4)) { e.preventDefault(); pshow(pstep + 1); } if (e.key === 'ArrowLeft' && pstep > 1) { e.preventDefault(); pshow(pstep - 1); } });
  let lastRun: { nd: number; todo: number; pay: number; period: string } | null = null;
  function renderSum() {
    const box = $('p-sum'); if (!box) return; if (!org) { box.innerHTML = '<p class="empty">기관 설정이 없습니다 — <a href="/vat/setup/">기관 설정</a></p>'; return; }
    if (box.querySelector('p.empty')) box.innerHTML = '';
    const P = periodInfo(sel.value || periodKeyOf(ymd(new Date()).slice(0, 7))); const facs = org.facilities.filter(f => inFiling(D, f)); const months = P.kind === 'F' ? [...P.prelim, ...P.own] : P.own;
    let nRows = 0, nOpen = 0, nMissing = 0; for (const f of facs) for (const m of P.own) { const l = ledgers.get(`${f.id}:${m}`); if (!l) { nMissing++; continue; } nRows += l.rows.length; nOpen += l.rows.filter(r => (r.v === 'no' || r.v === 'check') && !r.done).length; }
    const salesSum = facs.reduce((s, f) => { const x = sales[f.id]; return s + (x ? x.c1 + x.c3 + x.c4 : 0); }, 0); const exSum = Object.values(exemptIn).reduce((s, v) => s + v, 0);
    const due = new Date(P.due); const today = new Date(); const dd = Math.round((new Date(due.getFullYear(), due.getMonth(), due.getDate()).getTime() - new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()) / 86400000);
    const it = (k: string, v: string, cls = '') => `<div class="ps-row ${cls}"><span class="k">${k}</span><span class="v">${v}</span></div>`;
    /* 단추는 한 번만 만들고 숫자 줄만 다시 그린다 — 입력 상자의 blur→change 가 renderSum 을 부를 때 누르던 단추가 사라지지 않게 */
    if (!box.querySelector('#ps-rows')) { box.innerHTML = `<div id="ps-rows"></div><div class="actions"><button type="button" class="btn secondary" data-psum-next>다음 단계</button><button type="button" class="btn" data-psum-run>숫자표 만들기</button><button type="button" class="btn secondary" data-psum-save hidden>신고 기록 저장</button></div><p class="note" id="ps-note"></p>`;
      box.querySelector('[data-psum-next]')!.addEventListener('click', () => pshow(Math.min(4, pstep + 1))); box.querySelector('[data-psum-run]')!.addEventListener('click', () => $('p-run')?.click()); box.querySelector('[data-psum-save]')!.addEventListener('click', () => $('p-save')?.click()); }
    $('ps-rows')!.innerHTML = `<p class="ps-title">${esc(P.name)}<br><span class="note">마감 ${P.due} · ${dd >= 0 ? `D-${dd}` : `${-dd}일 지남`}</span></p>
      ${it('신고 대상 시설', `${facs.length}곳`)}${it('기록(이 기간 달)', `${nRows}건${nOpen ? ` · <b>미처리 ${nOpen}</b>` : ''}`, nOpen ? 'warn' : '')}${it('기록 없는 시설·달', `${nMissing} / ${facs.length * P.own.length}`, nMissing ? 'warn' : '')}
      ${pmax >= 2 ? it('매출 합계(공급가액)', fmt(salesSum)) : ''}${pmax >= 3 ? it('면세 공급가액', fmt(exSum)) + it('면세비율(참고)', salesSum + exSum ? pct(exSum / (salesSum + exSum)) : '—') : ''}
      ${lastRun && lastRun.period === sel.value ? it('(54) 공통 면세분', fmt(lastRun.nd)) + it('납부(환급) 참고', fmt(lastRun.pay)) + it('처리할 것', `${lastRun.todo}건`, lastRun.todo ? 'warn' : '') : ''}`;
    (box.querySelector('[data-psum-next]') as HTMLElement).hidden = pstep >= 3; (box.querySelector('[data-psum-save]') as HTMLElement).hidden = !(lastRun && lastRun.period === sel.value);
    $('ps-note')!.textContent = `${months.length}개월 기록 기준 · 판정은 참고이며 기관의 판단이 아닙니다.`;
  }

  /* ---------- 자료 ---------- */
  const loadLocal = () => { for (const [k, rows] of Object.entries(allLedgers())) { const [fid, month] = k.split(':'); const f = org?.facilities.find(x => x.id === fid); if (!ledgers.has(k) || ledgers.get(k)!.src === 'local') ledgers.set(k, { fid, name: f?.name ?? fid, type: f?.type ?? 'other', month, rows, src: 'local' }); } };
  const renderOrg = () => { $('p-org-state')!.innerHTML = org ? `<strong>${esc(org.org)}</strong> · ${esc(org.dept || '')} · 시설 ${org.facilities.length}곳 · ${org.unit === 'entity' ? '사업자 단위 과세' : '사업장별 등록'}` : '기관 설정이 없습니다 — 파일을 열거나 <a href="/vat/setup/">기관 설정</a>에서 만드세요.'; };
  $<HTMLInputElement>('p-open-org')?.addEventListener('change', async e => { const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return; try { const o = await readJsonFile(f) as Org; if (!o || o.v !== 1) throw new Error(); org = o; setOrg(o); loadLocal(); renderOrg(); renderPeriods(); } catch { $('p-org-state')!.textContent = '기관 설정 파일(org.json)이 아닙니다.'; } });
  $<HTMLInputElement>('p-open-ledgers')?.addEventListener('change', async e => { const files = [...((e.target as HTMLInputElement).files ?? [])]; let n = 0; for (const f of files) { try { const j = await readJsonFile(f) as { v: number; facility: string; facility_name: string; type: string; month: string; rows: LedgerRow[] }; if (!j || j.v !== 1 || !j.month || !Array.isArray(j.rows)) throw new Error(); ledgers.set(`${j.facility}:${j.month}`, { fid: j.facility, name: j.facility_name, type: j.type, month: j.month, rows: j.rows, src: f.name }); n++; } catch { /* 건너뜀 */ } } $('p-ledger-state')!.textContent = `파일 ${n}개 읽음 · 인계표 ${ledgers.size}개(시설·달)`; renderPeriods(); });

  /* ---------- 기간 ---------- */
  const sel = $<HTMLSelectElement>('p-period')!;
  function renderPeriods() {
    const months = [...ledgers.values()].map(l => l.month).sort(); const now = new Date(); const y = now.getFullYear();
    const keys = new Set<string>(); for (const yy of [y - 1, y, y + 1]) for (const k of ['1P', '1F', '2P', '2F']) keys.add(`${yy}-${k}`); months.forEach(m => keys.add(periodKeyOf(m)));
    const cur = sel.value; sel.innerHTML = [...keys].sort().map(k => `<option value="${k}">${periodInfo(k).name} (마감 ${periodInfo(k).due})</option>`).join('');
    sel.value = cur && keys.has(cur) ? cur : (months.length ? periodKeyOf(months[months.length - 1]) : periodKeyOf(ymd(new Date(y, now.getMonth() - 1, 1)).slice(0, 7)));
    renderPeriod();
  }
  sel.addEventListener('change', renderPeriod);
  const facOf = (fid: string): OrgFacility | undefined => org?.facilities.find(f => f.id === fid);
  const groupKey = (f: OrgFacility | undefined) => !org ? 'x' : org.unit === 'entity' ? 'entity' : (f?.reg_no || 'noreg');
  const groupName = (k: string) => !org ? '' : k === 'entity' ? `${org.org} (사업자 단위)` : k === 'noreg' ? '등록번호 미입력 시설' : `등록번호 ${k} — ${org.facilities.filter(f => f.reg_no === k).map(f => f.name).join('·')}`;
  let lastPeriod = '';
  function renderPeriod() {
    const P = periodInfo(sel.value); const saved = getFilings()[sel.value];
    if (lastPeriod !== sel.value) {   // 기간이 바뀌면 매출·면세 입력은 그 기간 것으로(저장된 신고 기록이 있으면 되살림)
      lastPeriod = sel.value; for (const k of Object.keys(sales)) delete sales[k]; for (const k of Object.keys(exemptIn)) delete exemptIn[k]; for (const k of Object.keys(oneoffIn)) delete oneoffIn[k]; for (const k of Object.keys(prelimIn)) delete prelimIn[k];
      if (saved) { Object.assign(sales, saved.sales ?? {}); for (const g of saved.groups ?? []) { exemptIn[g.key] = g.exempt; if (g.oneoff) oneoffIn[g.key] = g.oneoff; } }
    } const prelimSaved = P.prelimKey ? getFilings()[P.prelimKey] : undefined;
    $('p-period-note')!.innerHTML = `${P.name}: 매입은 ${P.own[0]}~${P.own[P.own.length - 1]} 인계표${P.kind === 'F' ? `, 안분은 ${P.full[0]}~${P.full[5]} 전체 공급가액으로 정산(예정신고 ${prelimSaved ? `기록 ${prelimSaved.saved} 저장분을 씀` : '기록이 이 브라우저에 없음 — 아래에서 예정 때 값을 넣으세요'})` : ''}. 신고·납부 ${P.due}.${saved ? ` <strong>이 기간 신고 기록이 ${saved.saved}에 저장돼 있습니다</strong>(다시 만들면 덮어씀).` : ''}`;
    if (!org) { $('p-coverage')!.innerHTML = '<p class="empty">기관 설정을 먼저 여세요.</p>'; return; }
    const facs = org.facilities.filter(f => inFiling(D, f));
    const months = P.kind === 'F' ? [...P.prelim, ...P.own] : P.own;
    const cell = (f: OrgFacility, m: string) => { const l = ledgers.get(`${f.id}:${m}`); if (!l) return '<td class="note">없음</td>'; const open = l.rows.filter(r => (r.v === 'no' || r.v === 'check') && !r.done).length; return `<td>${l.rows.length}건${open ? ` <span class="verdict check">미처리 ${open}</span>` : ''}</td>`; };
    $('p-coverage')!.innerHTML = `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table compact" data-stack="off"><caption>인계표 도착 현황 — ${esc(P.name)}</caption><thead><tr><th scope="col">시설</th>${months.map(m => `<th scope="col">${m}${P.prelim.includes(m) ? '<br><span class="note">예정분</span>' : ''}</th>`).join('')}</tr></thead><tbody>${facs.map(f => `<tr><th scope="row">${esc(f.name)}</th>${months.map(m => cell(f, m)).join('')}</tr>`).join('')}</tbody></table></div>
      ${P.kind === 'F' ? `<label class="choices" style="margin-top:8px"><span><input type="checkbox" id="p-inc-prelim" ${prelimSaved ? 'checked disabled' : ''}/> 예정 달(${P.prelim[0]}~${P.prelim[2]}) 기록 중 예정신고에 넣지 않은 것을 <strong>(13) 예정신고 누락분</strong>으로 넣기 ${prelimSaved ? '— 저장된 예정신고 기록과 견줘 빠진 행만 자동으로 넣습니다' : '— 예정신고 때 이미 넣은 행이 섞이면 이중 공제가 되니, 확실할 때만 켜세요'}</span></label>` : ''}`;
    includePrelimRows = !!prelimSaved; $<HTMLInputElement>('p-inc-prelim')?.addEventListener('change', e => { includePrelimRows = (e.target as HTMLInputElement).checked; });
    renderSales(P, facs); renderGroups(P, facs, prelimSaved); renderConvert(P); $('p-run-wrap')!.hidden = false; $('p-result')!.innerHTML = ''; const rn = $('p-result-none'); if (rn) rn.hidden = false; lastRun = null; renderSum();
  }
  function renderSales(P: ReturnType<typeof periodInfo>, facs: OrgFacility[]) {
    const wrap = $('p-sales-wrap')!; const tax = facs.filter(f => salesFacility(D, f)); wrap.hidden = !tax.length; const none = $('p-sales-none'); if (none) none.hidden = !!tax.length;
    const days = (() => { const a = new Date(Number(P.own[0].slice(0, 4)), Number(P.own[0].slice(5, 7)) - 1, 1); const last = P.own[P.own.length - 1]; const b = new Date(Number(last.slice(0, 4)), Number(last.slice(5, 7)), 0); return Math.round((b.getTime() - a.getTime()) / 86400000) + 1; })();
    $('p-sales')!.innerHTML = tax.map(f => { const s = sales[f.id] ?? (sales[f.id] = { c1: 0, c3: 0, c4: 0 }); return `<div class="vc-form" data-fid="${f.id}"><p class="q-title full">${esc(f.name)} <span class="note">${facilityRule(D, f)?.name ?? ''}${facilityStatus(D, f) === 'check' ? ' · 과세 여부 확인 필요' : ''}${facilityStatus(D, f) === 'own' ? ' · 수탁기관 자기 사업 — 우리 기관이 받는 사용료·임대료만' : ''}</span></p>
      <label>(1) 세금계산서 발급분 공급가액 <input type="text" inputmode="numeric" data-c="c1" value="${s.c1 ? fmt(s.c1) : ''}" /></label>
      <label>(3) 카드·현금영수증 발행분 공급가액 <input type="text" inputmode="numeric" data-c="c3" value="${s.c3 ? fmt(s.c3) : ''}" /></label>
      <label>(4) 기타(간주임대료 포함) 공급가액 <input type="text" inputmode="numeric" data-c="c4" value="${s.c4 ? fmt(s.c4) : ''}" /></label>
      ${f.deposit ? `<div class="q full"><span class="q-title" style="font-size:var(--small)">간주임대료 계산 — 보증금 × 일수 × 이자율 ÷ 365(시행령 제65조)</span><div class="deem"><label>보증금(원) <input type="text" inputmode="numeric" data-d="dep" /></label><label>일수 <input type="text" inputmode="numeric" data-d="days" value="${days}" /></label><label>이자율(%) <input type="text" inputmode="decimal" data-d="rate" placeholder="정기예금 이자율" /></label><button type="button" class="btn secondary" data-deem>(4)에 더하기</button></div><span class="note">이자율은 국세청 고시 '정기예금 이자율'을 확인해 넣습니다(해마다 바뀜). 계산한 금액은 (4)칸에 더해집니다.</span></div>` : ''}</div>`; }).join('');
    $('p-sales')!.querySelectorAll<HTMLInputElement>('input[data-c]').forEach(i => i.addEventListener('change', () => { const fid = i.closest<HTMLElement>('[data-fid]')!.dataset.fid!; sales[fid][i.dataset.c as 'c1' | 'c3' | 'c4'] = num(i.value); i.value = num(i.value) ? fmt(num(i.value)) : ''; refreshGroupTaxable(); renderSum(); }));
    $('p-sales')!.querySelectorAll<HTMLButtonElement>('[data-deem]').forEach(b => b.addEventListener('click', () => { const box = b.closest<HTMLElement>('[data-fid]')!; const fid = box.dataset.fid!; const g = (k: string) => num(box.querySelector<HTMLInputElement>(`[data-d=${k}]`)!.value); const r = deemedRent(g('dep'), g('days'), g('rate') / 100, P.y); sales[fid].c4 += r; Object.assign(sales[fid], { dep: g('dep'), days: g('days'), rate: g('rate'), deem: (sales[fid].deem ?? 0) + r }); const c4 = box.querySelector<HTMLInputElement>('[data-c=c4]')!; c4.value = fmt(sales[fid].c4); refreshGroupTaxable(); renderSum(); toast(`간주임대료 ${fmt(r)}원을 (4)에 더했습니다`); }));
  }
  /** 과세사업 전환 매입세액(시행령 제85조) — 무상(면세)이던 시설을 유상(과세)으로 바꾼 과세기간의 확정신고에 */
  const convRows: { desc: string; tax: number; kind: 'building' | 'other'; acq: PeriodKey; common: boolean; gkey: string }[] = [];
  const convTaxRatio = () => { const tx = (org?.facilities.filter(f => inFiling(D, f)) ?? []).reduce((s, f) => s + (sales[f.id] ? sales[f.id].c1 + sales[f.id].c3 + sales[f.id].c4 : 0), 0); const ex = Object.values(exemptIn).reduce((s, v) => s + v, 0); return tx + ex ? tx / (tx + ex) : 1; };
  function renderConvert(P: ReturnType<typeof periodInfo>) {
    const wrap = $('p-convert')!; if (!wrap) return; wrap.hidden = false;
    const y = P.y; const acqOpts: PeriodKey[] = []; for (let yy = y - 10; yy <= y; yy++) acqOpts.push(`${yy}-1F`, `${yy}-2F`);
    const ratioEl = convTaxRatio;
    const draw = () => { const r = ratioEl(); $('p-conv-list')!.innerHTML = convRows.length ? `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table" data-stack="off"><caption>과세사업 전환 매입세액 — ${esc(P.name)} 확정신고에 공제(참고용)</caption><thead><tr><th scope="col">자산</th><th scope="col">불공제됐던 매입세액</th><th scope="col">종류</th><th scope="col">취득 과세기간</th><th scope="col">경과 과세기간</th><th scope="col">남은 비율</th><th scope="col">공통 사용</th><th scope="col">공제 세액</th><th scope="col" class="no-print"></th></tr></thead><tbody>${convRows.map((c, i) => { const cc = convertCredit(c.tax, c.kind, c.acq, sel.value, c.common ? r : 1); return `<tr><th scope="row">${esc(c.desc)}</th><td>${fmt(c.tax)}</td><td>${c.kind === 'building' ? '건물·구축물(5%)' : '그 밖(25%)'}</td><td>${c.acq}</td><td>${cc.n}</td><td>${pct(cc.remain)}</td><td>${c.common ? `과세 비율 ${pct(r)}${r < 0.05 ? ' — 5% 미만, 공제 없음' : ''}` : '과세 전용'}</td><td><strong>${fmt(cc.credit)}</strong></td><td class="no-print"><button type="button" class="link-btn" data-cdel="${i}">삭제</button></td></tr>`; }).join('')}<tr class="total"><th scope="row">합계</th><td colspan="6"></td><td>${fmt(convRows.reduce((s, c) => s + convertCredit(c.tax, c.kind, c.acq, sel.value, c.common ? r : 1).credit, 0))}</td><td></td></tr></tbody></table></div><p class="meta">확정신고 때 「과세사업전환 감가상각자산 신고서」를 함께 냅니다(제85조 제5항). 뒤에 면세비율이 5%p 이상 바뀌면 재계산(제7항 → 제83조). 취득이 과세기간 개시일 뒤면 개시일에 취득한 것으로 봅니다(제6항).</p>` : '<p class="meta">전환할 자산을 넣으면 공제 세액을 계산합니다.</p>'; $('p-conv-list')!.querySelectorAll<HTMLButtonElement>('[data-cdel]').forEach(b => b.addEventListener('click', () => { convRows.splice(Number(b.dataset.cdel), 1); draw(); })); };
    wrap.querySelector<HTMLSelectElement>('[data-cacq]')!.innerHTML = acqOpts.filter(k => k <= sel.value).map(k => `<option value="${k}">${periodInfo(k).name.replace(' 확정신고', '')}</option>`).join('');
    const uw = wrap.querySelector<HTMLElement>('[data-cunit-wrap]')!; const us = wrap.querySelector<HTMLSelectElement>('[data-cunit]')!; const ug = [...groupsOf(org?.facilities.filter(f => inFiling(D, f)) ?? []).keys()]; uw.hidden = !(org && org.unit === 'site' && ug.length > 1); us.innerHTML = ug.map(k => `<option value="${esc(k)}">${esc(groupName(k))}</option>`).join('');
    const addBtn = wrap.querySelector<HTMLButtonElement>('[data-cadd]')!; const fresh = addBtn.cloneNode(true) as HTMLButtonElement; addBtn.replaceWith(fresh);
    fresh.addEventListener('click', () => { const g = (k: string) => wrap.querySelector<HTMLInputElement | HTMLSelectElement>(`[data-${k}]`)!; const tax = num(g('ctax').value); if (!tax) { toast('불공제됐던 매입세액을 넣으세요'); (g('ctax') as HTMLInputElement).focus(); return; } convRows.push({ desc: g('cdesc').value.trim() || '(자산)', tax, kind: (g('ckind').value as 'building' | 'other'), acq: g('cacq').value, common: (g('ccommon') as HTMLInputElement).checked, gkey: org && org.unit === 'site' ? (g('cunit').value || 'noreg') : 'entity' }); (g('cdesc') as HTMLInputElement).value = ''; (g('ctax') as HTMLInputElement).value = ''; draw(); });
    draw();
  }
  const groupsOf = (facs: OrgFacility[]) => { const m = new Map<string, OrgFacility[]>(); facs.forEach(f => { const k = groupKey(f); m.set(k, [...(m.get(k) ?? []), f]); }); return m; };
  const taxableOf = (fs: OrgFacility[]) => fs.reduce((s, f) => { const x = sales[f.id]; return s + (x ? x.c1 + x.c3 + x.c4 : 0); }, 0);
  function renderGroups(P: ReturnType<typeof periodInfo>, facs: OrgFacility[], prelimSaved?: Filing) {
    const gs = groupsOf(facs); $('p-groups-wrap')!.hidden = false;
    $('p-groups')!.innerHTML = [...gs.entries()].map(([k, fs]) => { const pre = prelimSaved?.groups.find(g => g.key === k); const pi = pre ? (prelimIn[k] = { taxable: pre.taxable, exempt: pre.exempt, common: pre.common_tax, nondeduct: pre.nondeduct }) : (prelimIn[k] ?? (prelimIn[k] = { taxable: 0, exempt: 0, common: 0, nondeduct: 0 }));
      return `<div class="vc-form" data-g="${esc(k)}"><p class="q-title full">${esc(groupName(k))}</p>
      <label>과세 공급가액(이 기간, 2절 합계) <input type="text" data-tax readonly value="${fmt(taxableOf(fs))}" /></label>
      <label>면세 공급가액(이 기간 — 면세 수입 + 면세사업 보조금) <input type="text" inputmode="numeric" data-ex value="${exemptIn[k] ? fmt(exemptIn[k]) : ''}" placeholder="없으면 0" /></label>
      <label>그중 일회성 면세 공급(토지 매각 등, 참고용 — 면세비율 관리) <input type="text" inputmode="numeric" data-one value="${oneoffIn[k] ? fmt(oneoffIn[k]) : ''}" placeholder="없으면 비움" /></label>
      <label>안분 기준 <select data-basis>${[['supply', '공급가액 비율(기본, 시행령 제81조 제1항)'], ['purchase', '매입가액 비율 — 공급가액이 없을 때 1순위(제4항 제1호)'], ['planned', '예정공급가액 비율 — 2순위(제4항 제2호)'], ['area', '예정사용면적 비율 — 3순위, 건물 신축·취득은 1순위(제4항 제3호·단서)']].map(([v, n]) => `<option value="${v}" ${(basisIn[k]?.basis ?? 'supply') === v ? 'selected' : ''}>${n}</option>`).join('')}</select><span class="note" data-basis-note></span></label>
      <label class="choices"><span><input type="checkbox" data-bld ${basisIn[k]?.building ? 'checked' : ''}/> 이 공통매입세액은 <strong>건물·구축물 신축·취득분</strong>이고 과세·면세 예정사용면적을 나눌 수 있다(제4항 단서 — 공급가액이 있어도 면적 비율 우선)</span></label>
      <div class="full" data-basis-in ${(basisIn[k]?.basis ?? 'supply') === 'supply' ? 'hidden' : ''}><label>면세 몫(매입가액·예정공급가액·면적) <input type="text" inputmode="decimal" data-bex value="${basisIn[k]?.ex ? fmt(basisIn[k].ex) : ''}" /></label> <label>전체(같은 단위) <input type="text" inputmode="decimal" data-btot value="${basisIn[k]?.tot ? fmt(basisIn[k].tot) : ''}" /></label><span class="note">공급가액 비율을 쓸 수 없는 기간(과세·면세 어느 한쪽 공급가액이 없음)에만. 건물·구축물을 예정사용면적으로 안분했으면 면적이 확정될 때까지 같은 기준(제5항).</span></div>
      <details class="vat-more full" data-admin-wrap><summary><strong>본청·행정 공통</strong>('사무실·행정 일과 함께'로 적은 지출) — 공급가액 비율을 못 쓰므로 기준을 따로 넣습니다 <span class="note">유권해석 확인</span></summary>
      <p class="note">${esc(D.rules.admin_common?.summary ?? '')}</p>
      <div class="vc-form"><label>안분 기준(시행령 제81조 제4항 순서) <select data-abasis>${[['', '— 아직 안 정함(본청 공통은 (54)에 넣지 않고 처리할 것에 표시) —'], ['purchase', '1순위 매입가액 비율 — 면세등 관련 매입가액 ÷ 총매입가액(공통 제외)'], ['planned', '2순위 예정공급가액 비율'], ['area', '3순위 예정사용면적 비율']].map(([v, n]) => `<option value="${v}" ${(adminIn[k]?.basis ?? '') === v ? 'selected' : ''}>${n}</option>`).join('')}</select></label>
      <label>면세·행정(면세사업등) 몫 <input type="text" inputmode="decimal" data-aex value="${adminIn[k]?.ex ? fmt(adminIn[k].ex) : ''}" /></label><label>전체(같은 단위) <input type="text" inputmode="decimal" data-atot value="${adminIn[k]?.tot ? fmt(adminIn[k].tot) : ''}" /></label></div>
      <p class="note">${esc(D.rules.admin_common?.caution ?? '')}</p>${rulingsHtml(D, D.rules.admin_common?.rulings)}${(() => { const q = (D.inquiries ?? []).find(x => x.key === 'admin_common'); if (!q) return ''; const BL: Record<string, string> = { purchase: '시행령 제81조 제4항 제1호 매입가액 비율', planned: '제4항 제2호 예정공급가액 비율', area: '제4항 제3호 예정사용면적 비율' }; return inquiryHtml(D, q, { org: org.org || '', facilities: fs.filter(f => salesFacility(D, f)).map(f => `${f.name}(${facilityRule(D, f)?.name.split('(')[0] ?? f.type})`).join(', '), basis: BL[adminIn[k]?.basis ?? ''] || '' }); })()}</details>
      ${P.kind === 'F' ? `<p class="note full">예정신고(${P.prelim[0]}~${P.prelim[2]}) 때 값 ${pre ? '— 저장된 기록에서 가져옴' : '— 예정신고서를 보고 넣으세요'}</p>
      <label>예정 과세 공급가액 <input type="text" inputmode="numeric" data-p="taxable" value="${pi.taxable ? fmt(pi.taxable) : ''}" /></label><label>예정 면세 공급가액 <input type="text" inputmode="numeric" data-p="exempt" value="${pi.exempt ? fmt(pi.exempt) : ''}" /></label>
      <label>예정 공통매입세액 <input type="text" inputmode="numeric" data-p="common" value="${pi.common ? fmt(pi.common) : ''}" /></label><label>예정 때 불공제한 면세분(54) <input type="text" inputmode="numeric" data-p="nondeduct" value="${pi.nondeduct ? fmt(pi.nondeduct) : ''}" /></label>` : ''}</div>`; }).join('');
    wireInquiry($('p-groups')!);
    $('p-groups')!.querySelectorAll<HTMLInputElement>('input[data-ex]').forEach(i => i.addEventListener('change', () => { exemptIn[i.closest<HTMLElement>('[data-g]')!.dataset.g!] = num(i.value); i.value = fmt(num(i.value)); readBasis(i.closest<HTMLElement>('[data-g]')!); renderSum(); }));
    $('p-groups')!.querySelectorAll<HTMLElement>('[data-admin-wrap]').forEach(w => w.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-abasis],[data-aex],[data-atot]').forEach(el => el.addEventListener('change', () => { const k = w.closest<HTMLElement>('[data-g]')!.dataset.g!; adminIn[k] = { basis: w.querySelector<HTMLSelectElement>('[data-abasis]')!.value, ex: num(w.querySelector<HTMLInputElement>('[data-aex]')!.value), tot: num(w.querySelector<HTMLInputElement>('[data-atot]')!.value) }; })));
    $('p-groups')!.querySelectorAll<HTMLInputElement>('input[data-one]').forEach(i => i.addEventListener('change', () => { oneoffIn[i.closest<HTMLElement>('[data-g]')!.dataset.g!] = num(i.value); i.value = num(i.value) ? fmt(num(i.value)) : ''; }));
    const readBasis = (box: HTMLElement) => { const k = box.dataset.g!; const b = basisIn[k] ?? (basisIn[k] = { basis: 'supply', ex: 0, tot: 0 }); b.building = box.querySelector<HTMLInputElement>('[data-bld]')!.checked; lockBasis(box, b); b.basis = box.querySelector<HTMLSelectElement>('[data-basis]')!.value; b.ex = num(box.querySelector<HTMLInputElement>('[data-bex]')!.value); b.tot = num(box.querySelector<HTMLInputElement>('[data-btot]')!.value); box.querySelector<HTMLElement>('[data-basis-in]')!.hidden = b.basis === 'supply'; };
    $('p-groups')!.querySelectorAll<HTMLElement>('[data-g]').forEach(box => { box.querySelectorAll<HTMLElement>('[data-basis],[data-bex],[data-btot],[data-bld]').forEach(el => el.addEventListener('change', () => readBasis(box))); readBasis(box); });
    $('p-groups')!.querySelectorAll<HTMLInputElement>('input[data-p]').forEach(i => i.addEventListener('change', () => { const k = i.closest<HTMLElement>('[data-g]')!.dataset.g!; (prelimIn[k] as unknown as Record<string, number>)[i.dataset.p!] = num(i.value); i.value = num(i.value) ? fmt(num(i.value)) : ''; }));
  }
  /** 안분 기준 잠금(세무사 평가 2차): 과세·면세 공급가액이 둘 다 있으면 공급가액 비율만(시행령 제81조 제1항). 어느 한쪽이 없을 때만 매입가액 → 예정공급가액 → 예정사용면적 순서(제4항), 건물·구축물 신축·취득은 면적을 먼저(단서) */
  function lockBasis(box: HTMLElement, b: { basis: string; building?: boolean }) {
    const tx = num(box.querySelector<HTMLInputElement>('[data-tax]')!.value), ex = num(box.querySelector<HTMLInputElement>('[data-ex]')!.value); const sel = box.querySelector<HTMLSelectElement>('[data-basis]')!; const note = box.querySelector<HTMLElement>('[data-basis-note]')!;
    const both = tx > 0 && ex > 0; const allow = (v: string) => v === 'supply' || (b.building && v === 'area') || (!both && v !== 'supply');
    [...sel.options].forEach(o => { o.disabled = !allow(o.value); }); if (!allow(sel.value)) sel.value = b.building ? 'area' : 'supply';
    note.textContent = both ? (b.building ? '건물·구축물 신축·취득분 — 공급가액이 있어도 예정사용면적 비율을 먼저 씁니다(제4항 단서).' : '과세·면세 공급가액이 둘 다 있어 공급가액 비율만 쓸 수 있습니다(제1항). 다른 기준은 어느 한쪽 공급가액이 없을 때만 엽니다.') : '어느 한쪽 공급가액이 없어 제4항의 순서(매입가액 → 예정공급가액 → 예정사용면적)로 고릅니다.';
  }
  const refreshGroupTaxable = () => { if (!org) return; const gs = groupsOf(org.facilities.filter(f => inFiling(D, f))); $('p-groups')!.querySelectorAll<HTMLElement>('[data-g]').forEach(box => { const fs = gs.get(box.dataset.g!) ?? []; box.querySelector<HTMLInputElement>('[data-tax]')!.value = fmt(taxableOf(fs)); const b = basisIn[box.dataset.g!] ?? (basisIn[box.dataset.g!] = { basis: 'supply', ex: 0, tot: 0 }); lockBasis(box, b); b.basis = box.querySelector<HTMLSelectElement>('[data-basis]')!.value; box.querySelector<HTMLElement>('[data-basis-in]')!.hidden = b.basis === 'supply'; }); };

  /* ---------- 숫자표 ---------- */
  $('p-run')?.addEventListener('click', () => {
    if (!org) return; const P = periodInfo(sel.value); const prelimSaved = P.prelimKey ? getFilings()[P.prelimKey] : undefined; const prevIds = new Set(prelimSaved?.row_ids ?? []);
    const facs = org.facilities.filter(f => inFiling(D, f)); const gs = groupsOf(facs);
    const cells: Record<string, { amt: number; tax: number }> = {}; const add = (no: string, amt: number, tax: number) => { const c = cells[no] ?? (cells[no] = { amt: 0, tax: 0 }); c.amt += amt; c.tax += tax; };
    const common: Record<string, number> = {}; const commonAmt: Record<string, number> = {}; const adminC: Record<string, number> = {}; const adminNote: string[] = []; const subsidyRows: { f: OrgFacility; r: LedgerRow; ded: number }[] = []; const rowIds: string[] = []; const unresolved: string[] = [], excluded: string[] = [], lateNote: string[] = [], missing: string[] = []; const fix: Record<string, { f: OrgFacility; m: string; r: LedgerRow }[]> = { unresolved: [], excluded: [] }; const missingAt: { f: OrgFacility; m: string }[] = [];
    const assets: Filing['assets'] = []; let nInv = 0, nCard = 0, nNo = 0; const used: UsedRow[] = [];
    for (const f of facs) {
      const months = includePrelimRows ? [...P.prelim, ...P.own] : P.own;
      for (const m of P.own) if (!ledgers.has(`${f.id}:${m}`)) { missing.push(`${f.name} ${m}`); missingAt.push({ f, m }); }
      for (const m of months) {
        const l = ledgers.get(`${f.id}:${m}`); if (!l) continue; const isPre = P.prelim.includes(m);
        for (const r of l.rows) {
          if (isPre && prevIds.has(r.id)) continue;
          const tag = `${f.name} · ${r.d} ${r.desc} (${fmt(r.tax)}원)`;
          if (r.v === 'check') { unresolved.push(tag + ' — ' + r.todo); fix.unresolved.push({ f, m, r }); continue; }
          if (r.v === 'none') continue;
          const inv = (r.proof === 'e_invoice' || r.proof === 'p_invoice') && r.payee === 'org'; const card = (r.proof === 'card' || r.proof === 'cash') && r.vat_sep;
          if (r.v === 'no' && !inv) { excluded.push(tag + ' — ' + r.title + (r.fix_due ? ` · 수정세금계산서 기한 ${r.fix_due}${r.fix_due < ymd(new Date()) ? '(지남)' : ''}` : '')); fix.excluded.push({ f, m, r }); continue; }
          if (!inv && !card) { excluded.push(tag + ' — 증빙 요건 미달'); fix.excluded.push({ f, m, r }); continue; }
          rowIds.push(r.id); if (r.late) lateNote.push(tag); used.push({ f, r, isPre, inv, card });
          const main = isPre ? '13' : inv ? (r.asset ? '12' : '10') : (r.asset ? '45' : '44');
          add(main, r.amt, r.tax); if (inv) nInv++; else nCard++;
          const gk = groupKey(f);
          if (r.v === 'no') { add('53', r.amt, r.tax); nNo++; }
          if (r.v === 'split' && r.use === 'admin') { adminC[gk] = (adminC[gk] ?? 0) + r.tax; }
          else if (r.v === 'split') { common[gk] = (common[gk] ?? 0) + r.tax; commonAmt[gk] = (commonAmt[gk] ?? 0) + r.amt; }
          if (r.asset) assets.push({ id: r.id, facility: f.name, desc: r.desc, period: sel.value, tax: r.tax, kind: r.what === 'repair' ? 'building' : 'other', common: r.v === 'split', ratio0: 0, group: gk });
        }
      }
    }
    for (const f of facs) { const s = sales[f.id]; if (!s) continue; if (s.c1) add('1', s.c1, Math.floor(s.c1 * 0.1)); if (s.c3) add('3', s.c3, Math.floor(s.c3 * 0.1)); if (s.c4) add('4', s.c4, Math.floor(s.c4 * 0.1)); }
    /* 안분 */
    const groups: Filing['groups'] = []; const sk = D.rules.common.skip; const r5 = sk.find(s => s.key === 'ratio5')!, small = sk.find(s => s.key === 'small')!;
    for (const [k, fs] of gs) {
      const ct = common[k] ?? 0; const tx = taxableOf(fs), ex = exemptIn[k] ?? 0; const pi = prelimIn[k];
      const fullT = tx + (P.kind === 'F' ? pi?.taxable ?? 0 : 0), fullE = ex + (P.kind === 'F' ? pi?.exempt ?? 0 : 0), fullC = ct + (P.kind === 'F' ? pi?.common ?? 0 : 0);
      if (!fullC) { if (ct || ex) groups.push({ key: k, name: groupName(k), taxable: tx, exempt: ex, ratio: fullT + fullE ? fullE / (fullT + fullE) : 0, common_tax: 0, nondeduct: 0, oneoff: oneoffIn[k] || undefined }); continue; }
      const b = basisIn[k]; const alt = b && b.basis !== 'supply' && b.tot > 0; const tot = fullT + fullE; const ratio = alt ? b.ex / b.tot : tot ? fullE / tot : 0; let skipped: string | undefined;
      const BASIS_NAME: Record<string, string> = { purchase: '매입가액 비율', planned: '예정공급가액 비율', area: '예정사용면적 비율' };
      if (!alt && !tot) skipped = '공급가액 없음 — 3절에서 안분 기준을 매입가액·예정공급가액·예정사용면적 비율로 고르면 계산합니다(시행령 제81조 제4항)';
      else if (fullC < (small.amount_lt ?? 50000)) skipped = small.name; else if (ratio < (r5.ratio_lt ?? 0.05) && fullC < (r5.amount_lt ?? 5000000)) skipped = r5.name;
      const fullNd = skipped ? 0 : Math.floor(fullC * ratio); const nd = P.kind === 'F' ? fullNd - (pi?.nondeduct ?? 0) : fullNd;
      if (!skipped || P.kind === 'F') add('54', 0, nd);
      groups.push({ key: k, name: groupName(k), taxable: tx, exempt: ex, ratio, common_tax: ct, nondeduct: nd, skipped: skipped ?? (alt ? `${BASIS_NAME[b.basis]}로 안분(${fmt(b.ex)} ÷ ${fmt(b.tot)})` : undefined), basis: alt ? b.basis : 'supply', oneoff: oneoffIn[k] || undefined });
      assets.filter(a => a.group === k && a.common).forEach(a => { a.ratio0 = ratio; });
    }
    /* 본청·행정 공통(세무회계법인 2차 1번): 공급가액 비율 대신 입력한 기준으로, 기준이 없으면 (54)에 넣지 않고 처리할 것에 */
    for (const [k] of gs) { const at = adminC[k] ?? 0; if (!at) continue; const a = adminIn[k]; const g = groups.find(x => x.key === k) ?? (() => { const ng = { key: k, name: groupName(k), taxable: taxableOf(gs.get(k)!), exempt: exemptIn[k] ?? 0, ratio: 0, common_tax: 0, nondeduct: 0 }; groups.push(ng); return ng; })();
      g.admin_tax = at; if (a && a.basis && a.tot > 0) { g.admin_basis = a.basis; g.admin_ex = a.ex; g.admin_tot = a.tot; g.admin_ratio = Math.min(1, a.ex / a.tot); g.admin_nondeduct = Math.floor(at * g.admin_ratio); add('54', 0, g.admin_nondeduct); }
      else adminNote.push(`${groupName(k)}: 본청·행정 공통 ${fmt(at)}원 — 3절에서 안분 기준(매입가액·예정공급가액·예정사용면적)을 넣기 전에는 (54)에 넣지 않았습니다(전액 공제로 보이지만 그대로 신고하면 과대공제). 기준은 유권해석으로 확인`); }
    /* 보조사업 지출(세무회계법인 2차 3번): 공제받은 부가세는 보조금 정산과 연결 */
    for (const u of used) if (u.r.subsidy && (u.r.v === 'ok' || u.r.v === 'split')) { const g = groups.find(x => x.key === groupKey(u.f)); const ded = u.r.v === 'ok' ? u.r.tax : Math.floor(u.r.tax * (1 - (u.r.use === 'admin' ? (g?.admin_ratio ?? 0) : (g?.ratio ?? 0)))); subsidyRows.push({ f: u.f, r: u.r, ded }); }
    /* 재계산(지난 신고 기록의 공통 자산) */
    const hi = (k: PeriodKey) => { const p = periodInfo(k); return p.y * 2 + p.half - 1; }; const curH = hi(sel.value);
    const recalc: { a: Filing['assets'][number]; from: PeriodKey; ratio: number; n: number; amt: number }[] = [];
    for (const [k, fl] of Object.entries(getFilings())) { if (k === sel.value || hi(k) >= curH) continue; for (const a of fl.assets ?? []) { if (!a.common) continue; const g = groups.find(x => x.key === a.group); if (!g) continue; const diff = g.ratio - a.ratio0; if (Math.abs(diff) < D.rules.recalc.threshold_pp) continue; const n = curH - hi(a.period); const remain = Math.max(0, 1 - D.rules.recalc.rates[a.kind] * n); if (remain <= 0) continue; recalc.push({ a, from: k, ratio: g.ratio, n, amt: Math.floor(a.tax * remain * diff) }); } }
    /* 등록 단위(사업장)마다 신고서 한 장 — 사업자 단위 과세면 한 장 + 사업장별 명세(첨부 15) */
    const cr = convTaxRatio(); const convAll: ConvRow[] = convRows.map(cv => { const cc = convertCredit(cv.tax, cv.kind, cv.acq, sel.value, cv.common ? cr : 1); return { ...cv, credit: cc.credit, n: cc.n, remain: cc.remain }; });
    const units = org.unit === 'entity' ? [{ key: 'entity', fs: facs }] : [...gs.entries()].map(([key, fs]) => ({ key, fs }));
    const prevFiling = getFilings()[prevPeriodKey(sel.value)];
    const unitCells = (fs: OrgFacility[], us: UsedRow[], gk: string) => {
      const c: Record<string, { amt: number; tax: number }> = {}; const ad = (no: string, amt: number, tax: number) => { const x = c[no] ?? (c[no] = { amt: 0, tax: 0 }); x.amt += amt; x.tax += tax; };
      for (const u of us) { const main = u.isPre ? '13' : u.inv ? (u.r.asset ? '12' : '10') : (u.r.asset ? '45' : '44'); ad(main, u.r.amt, u.r.tax); if (u.r.v === 'no') ad('53', u.r.amt, u.r.tax); if (u.r.late && u.inv) ad('66', u.r.amt, Math.floor(u.r.amt * 5 / 1000)); }
      for (const f of fs) { const sl = sales[f.id]; if (!sl) continue; if (sl.c1) ad('1', sl.c1, Math.floor(sl.c1 * 0.1)); if (sl.c3) ad('3', sl.c3, Math.floor(sl.c3 * 0.1)); if (sl.c4) ad('4', sl.c4, Math.floor(sl.c4 * 0.1)); }
      for (const g of groups.filter(g => org!.unit === 'entity' || g.key === gk)) { if (g.nondeduct) ad('54', 0, g.nondeduct); if (g.admin_nondeduct) ad('54', 0, g.admin_nondeduct); }
      const rc = recalc.filter(r => org!.unit === 'entity' || r.a.group === gk).reduce((s, r) => s + r.amt, 0); if (rc) ad('54', 0, rc);
      const cv = convAll.filter(v => org!.unit === 'entity' || v.gkey === gk).reduce((s, v) => s + v.credit, 0); if (cv) ad('48', 0, cv);
      return c; };
    const unitHtml: string[] = []; const unitRecs: NonNullable<Filing['units']> = [];
    for (const un of units) {
      const fids = new Set(un.fs.map(f => f.id)); const us = used.filter(u => fids.has(u.f.id)); const ucells = unitCells(un.fs, us, un.key);
      const supply = ['1', '3', '4'].reduce((t, n) => t + (ucells[n]?.amt ?? 0), 0); const mt = ['1', '3', '4'].reduce((t, n) => t + (ucells[n]?.tax ?? 0), 0);
      const c15 = ['44', '45', '48'].reduce((t, n) => t + (ucells[n]?.tax ?? 0), 0), c16 = ['10', '12', '13', '14'].reduce((t, n) => t + (ucells[n]?.tax ?? 0), 0) + c15, c17 = ['53', '54'].reduce((t, n) => t + (ucells[n]?.tax ?? 0), 0); const pay = mt - (c16 - c17);
      /* 예정고지 판단: 직전 과세기간(확정) 신고 기록의 이 단위 공급가액 */
      const pu = prevFiling ? (prevFiling.units?.find(x => x.key === un.key) ?? (prevFiling.units ? undefined : { supply: ['1', '3', '4'].reduce((t, n) => t + (prevFiling.cells[n]?.amt ?? 0), 0), pay: 0 })) : undefined;
      const notice = pu ? (pu.supply < PRELIM_NOTICE_LIMIT ? 'notice' : 'file') : 'unknown';
      const name = org.unit === 'entity' ? `${org.org} (사업자 단위 과세${org.reg_no ? ' · ' + org.reg_no : ''})` : groupName(un.key);
      unitRecs.push({ key: un.key, name, cells: ucells, supply, pay });
      unitHtml.push(renderForms({ D, org, P, cells: ucells, used: us, groups: groups.filter(g => org!.unit === 'entity' || g.key === un.key), commonAmt, prelimIn, recalc: recalc.filter(r => org!.unit === 'entity' || r.a.group === un.key), conv: convAll.filter(v => org!.unit === 'entity' || v.gkey === un.key), convRatio: cr, sales, facs: un.fs, unitName: name, unitIndex: units.length > 1 ? `${unitHtml.length + 1}/${units.length}` : '', notice: { state: notice, prevSupply: pu?.supply ?? 0, prevPay: pu?.pay ?? 0, prevKey: prevPeriodKey(sel.value) }, unresolved, excluded, missing }));
    }
    const conv = convAll; void conv;
    /* 결과 */
    const out = $('p-result')!; const rn = $('p-result-none'); if (rn) rn.hidden = true;
    /* 예외 우선(공무원 UX 재설계): 처리할 것을 결과 맨 위에 종류별 배지 + '지금 고치기' 깊은 링크로. 목록 본문은 아래 펼침 */
    const risky0 = used.filter(u => u.r.v === 'ok' && u.r.use === 'this' && (!u.r.evid || u.r.evid === 'none') && u.r.tax > 0).map(u => ({ u, ratio: groups.find(x => x.key === groupKey(u.f))?.ratio ?? 0 })).filter(x => x.ratio > 0);
    const redRows = fix.excluded.filter(x => x.r.v === 'no' && x.r.payee === 'contractor'); const otherEx = fix.excluded.length - redRows.length;
    const link = (x: { f: OrgFacility; m: string }) => `/vat/monthly/?fac=${encodeURIComponent(x.f.id)}&month=${x.m}`;
    const firstLink = (xs: { f: OrgFacility; m: string }[]) => xs.length ? `<a class="btn secondary" href="${link(xs[0])}">지금 고치기</a>` : '';
    const todoItems: string[] = [];
    if (redRows.length) todoItems.push(`<li class="t-red"><span class="sig no" aria-hidden="true"></span><b>다른 명의 세금계산서 ${redRows.length}건</b> · ${fmt(redRows.reduce((s, x) => s + x.r.tax, 0))}원 — 공급자에게 수정세금계산서 요청(기한 안) ${firstLink(redRows)}</li>`);
    if (otherEx) todoItems.push(`<li class="t-red"><span class="sig no" aria-hidden="true"></span><b>증빙 미달·불공제 ${otherEx}건</b> — 신고서 밖 ${firstLink(fix.excluded.filter(x => !redRows.includes(x)))}</li>`);
    if (fix.unresolved.length) todoItems.push(`<li class="t-yellow"><span class="sig check" aria-hidden="true"></span><b>확인 필요(노랑) ${fix.unresolved.length}건</b> · ${fmt(fix.unresolved.reduce((s, x) => s + x.r.tax, 0))}원 — 신고서에서 뺐습니다 ${firstLink(fix.unresolved)}</li>`);
    if (risky0.length) todoItems.push(`<li class="t-yellow"><span class="sig ok" aria-hidden="true"></span><b>근거 없는 전용 지출 ${risky0.length}건</b> — 계약·계량·검수 기록을 채우거나 공통으로 ${firstLink(risky0.map(x => ({ f: x.u.f, m: x.u.r.d.slice(0, 7) })))}</li>`);
    if (missingAt.length) todoItems.push(`<li class="t-gray"><span class="sig none" aria-hidden="true"></span><b>기록 없는 시설·달 ${missingAt.length}</b> — ${esc(missing.slice(0, 3).join(', '))}${missing.length > 3 ? ` 외 ${missing.length - 3}` : ''} ${firstLink(missingAt)}</li>`);
    if (adminNote.length) todoItems.push(`<li class="t-yellow"><span class="sig split" aria-hidden="true"></span><b>본청·행정 공통 안분 기준 없음 ${adminNote.length}</b> — (54)에 미반영 <button type="button" class="btn secondary" data-goto-step="3">3단계에서 넣기</button></li>`);
    if (recalc.length) todoItems.push(`<li class="t-blue"><span class="sig split" aria-hidden="true"></span><b>지난 기 공통 자산 재계산 ${recalc.length}건</b> · ${recalc.reduce((s, r) => s + r.amt, 0) >= 0 ? '+' : ''}${fmt(recalc.reduce((s, r) => s + r.amt, 0))}원 — (54)에 합산, 서식 22호 5. 확인</li>`);
    if (subsidyRows.length) todoItems.push(`<li class="t-gray"><span class="sig ok" aria-hidden="true"></span><b>보조사업 지출 ${subsidyRows.length}건</b> — 공제받는 부가세 ${fmt(subsidyRows.reduce((s, x) => s + x.ded, 0))}원은 보조금 정산 지침 확인</li>`);
    if (lateNote.length) todoItems.push(`<li class="t-yellow"><span class="sig check" aria-hidden="true"></span><b>지연 수취 ${lateNote.length}건</b> — (66) 가산세 5/1,000</li>`);
    const todoCount = redRows.length + otherEx + fix.unresolved.length + risky0.length + missingAt.length + adminNote.length;
    /* 절감 한 줄: 면세분 합계 + 원인 3개 + 행동 링크. 자세한 표는 펼침 */
    const ndAll = groups.reduce((s, g) => s + Math.max(0, g.nondeduct) + Math.max(0, g.admin_nondeduct ?? 0), 0); const topC = used.filter(u => u.r.v === 'split').sort((a, b) => b.r.tax - a.r.tax)[0]; const gTop = topC ? groups.find(x => x.key === groupKey(topC.f)) : undefined; const sk0 = D.rules.common.skip.find(x => x.key === 'ratio5'); const cAll = groups.reduce((s, g) => s + g.common_tax, 0);
    const sav1 = cAll ? `<div class="vc-card" id="p-sav1"><h3>절감 — 이번 기 공통매입세액 면세분 <b>${fmt(ndAll)}</b>원</h3><ol class="meta-list">${topC ? `<li>가장 큰 공통 지출: ${esc(topC.f.name)} · ${esc(topC.r.desc)} 세액 ${fmt(topC.r.tax)}원 — 전용(계약·계량기 분리)이면 <b>${fmt(Math.floor(topC.r.tax * (gTop?.ratio ?? 0)))}</b>원이 돌아옵니다 → <a href="${link({ f: topC.f, m: topC.r.d.slice(0, 7) })}">지출 기록에서 근거 채우기</a></li>` : ''}<li>면세비율 ${groups.filter(g => g.common_tax).map(g => `${esc(g.name.split(' — ')[0])} ${pct(g.ratio)}`).join(' · ')} — 1%p 낮추면 약 ${fmt(Math.floor(cAll * 0.01))}원 — 면세 공급가액에 보조금·토지 매각·등록 단위 밖 수입이 섞였는지 3단계에서 확인</li><li>안분 생략 기준(${fmt(sk0?.amount_lt ?? 5000000)}원 미만 + 면세비율 ${pct(sk0?.ratio_lt ?? 0.05)} 미만)까지: 공통매입세액 ${fmt(cAll)}원${cAll < (sk0?.amount_lt ?? 5000000) ? ' — 금액 기준은 충족' : ` — ${fmt(cAll - (sk0?.amount_lt ?? 5000000))}원 초과`}</li></ol></div>` : '';
    out.innerHTML = `<div class="section-head"><h2>4. ${esc(P.name)} — 신고서 모양 결과${units.length > 1 ? ` · 등록 단위 ${units.length}개(신고서 ${units.length}장)` : ''}</h2><span class="meta">참고용 · 부가가치세법 시행규칙 별지 서식의 칸 배치·번호(${esc(D.form_version ?? '2026-04-01')} 시행 판) · 홈택스 화면이 아님</span></div>
      <p class="note">판정은 참고이며 기관의 판단이 아닙니다.</p>
      <section class="vc-card p-todo" id="p-todo" aria-live="polite"><h3>처리할 것 <b>${todoCount}</b>${todoCount ? '' : ' — 없음'}</h3>${todoItems.length ? `<ul class="todo">${todoItems.join('')}</ul>` : '<p class="meta">이 기간 모든 시설·달의 기록이 있고 빨강·노랑·근거 없음이 없습니다.</p>'}</section>
      ${sav1}
      ${org.unit === 'site' && units.length > 1 ? `<div class="callout info"><strong>사업장별 등록</strong> — 등록번호마다 신고서와 부속서류를 따로 냅니다(아래 ${units.length}묶음). 안분·예정고지도 등록 단위마다 따로 봅니다.</div>` : ''}
      ${org.unit === 'entity' ? renderUnitSummary(org, P, facs, used, sales, groups) : ''}
      ${unitHtml.join('<hr class="unit-sep" />')}
      <details class="vat-more" id="p-sav-wrap"><summary><strong>절감 분석 자세히</strong> — 공통 지출별 전용 전환 효과·면세비율 관리·등록 단위</summary>${renderSavings(D, org, P, groups, prelimIn, used, groupName)}</details>
      <h3>자산대장 — 이번 기간 취득 ${assets.length}건</h3>
      ${assets.length ? `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table" data-stack="off"><caption>자산대장에 올릴 것(재계산·전환 추적용)</caption><thead><tr><th scope="col">시설</th><th scope="col">내용</th><th scope="col">세액</th><th scope="col">종류</th><th scope="col">공통 여부</th><th scope="col">취득 때 면세비율</th></tr></thead><tbody>${assets.map(a => `<tr><th scope="row">${esc(a.facility)}</th><td>${esc(a.desc)}</td><td>${fmt(a.tax)}</td><td>${a.kind === 'building' ? '건물·구축물(5%)' : '그 밖(25%)'}</td><td>${a.common ? '공통(안분)' : '과세 전용'}</td><td>${a.common ? pct(a.ratio0) : '—'}</td></tr>`).join('')}</tbody></table></div>` : '<p class="meta">이번 기간에 \'여러 해 쓰는 것\'으로 표시한 지출이 없습니다.</p>'}
      <p class="meta">근거: ${lawLink(D, { law: 'act', art: '제40조' })} · ${lawLink(D, { law: 'decree', art: '제81조' })} · ${lawLink(D, { law: 'decree', art: '제82조' })} · ${lawLink(D, { law: 'decree', art: '제83조' })} · ${lawLink(D, { law: 'decree', art: '제85조' })} · ${lawLink(D, { law: 'act', art: '제48조' })} · ${lawLink(D, { law: 'act', art: '제60조' })} — 면세공급가액에는 면세사업 관련 국고·공공보조금을 넣습니다(제81조 제1항 단서). 세금계산서 ${nInv}건 · 카드·현금영수증 ${nCard}건 · 불공제 명세 ${nNo}건.</p>
      <details class="vat-more"><summary><strong>처리할 것 — 건별 목록</strong></summary>
      <ul class="meta-list">${missing.length ? `<li><strong>인계표가 아직 없는 시설·달 ${missing.length}</strong>: ${esc(missing.join(', '))} — 시설 담당에게 요청</li>` : '<li>이 기간 모든 시설·달의 기록이 있습니다.</li>'}
        ${adminNote.length ? `<li><strong>본청·행정 공통 안분 기준 없음 ${adminNote.length}</strong>:<br>${adminNote.map(esc).join('<br>')}</li>` : ''}
        ${subsidyRows.length ? `<li><strong>보조사업 지출 ${subsidyRows.length}건 — 공제받는 부가세 ${fmt(subsidyRows.reduce((s, x) => s + x.ded, 0))}원</strong>: ${esc(D.rules.subsidy_settle?.summary ?? '')} ${esc(D.rules.subsidy_settle?.todo ?? '')}<br>${subsidyRows.slice(0, 10).map(x => esc(`${x.f.name} · ${x.r.d} ${x.r.desc} (공제 ${fmt(x.ded)}원)`)).join('<br>')}${subsidyRows.length > 10 ? `<br>… 외 ${subsidyRows.length - 10}건` : ''}</li>` : ''}
        ${unresolved.length ? `<li><strong>노랑(확인 필요) ${unresolved.length}건 — 신고서에서 뺐습니다</strong>:<br>${unresolved.map(esc).join('<br>')}</li>` : ''}
        ${excluded.length ? `<li><strong>신고서 밖 ${excluded.length}건(증빙 요건 미달·다른 명의 등)</strong> — 수정세금계산서를 받으면 다음 신고(또는 경정청구)에 넣습니다:<br>${excluded.map(esc).join('<br>')}</li>` : ''}
        ${((): string => { /* 세무회계법인 관점 4번 — 전용(초록)인데 실지귀속 근거가 없는 지출: 조사 때 공통으로 뒤집히면 면세비율만큼 추징 + 가산세 */
          const risky = used.filter(u => u.r.v === 'ok' && u.r.use === 'this' && (!u.r.evid || u.r.evid === 'none') && u.r.tax > 0).map(u => { const g = groups.find(x => x.key === groupKey(u.f)); return { u, ratio: g?.ratio ?? 0 }; }).filter(x => x.ratio > 0);
          if (!risky.length) return ''; const exp = risky.reduce((s, x) => s + Math.floor(x.u.r.tax * x.ratio), 0); const today = ymd(new Date()); const pen = today > P.due ? penaltyCalc(D, { tax: exp, due: P.due, payDate: today, kind: 'under' }) : null;
          return `<li><strong>실지귀속 근거 없는 전용 지출 ${risky.length}건</strong>(세액 ${fmt(risky.reduce((s, x) => s + x.u.r.tax, 0))}원) — 계약·계량·검수 기록이 없으면 조사 때 공통으로 보아 면세비율만큼 <b>${fmt(exp)}</b>원이 추징될 수 있고${pen ? `, 지금 수정신고하면 과소신고 가산세 ${fmt(pen.fileAfter)}원(10% × 감면 뒤) + 납부지연 ${fmt(pen.late)}원(${pen.days}일 × 22/100,000) 어림` : ' 신고 뒤에는 과소신고(10%)·납부지연(1일 22/100,000) 가산세가 붙습니다'}. 지출 기록에서 '이 시설만 썼다는 근거'를 채우거나 공통으로 바꾸세요(국세기본법 제47조의3·제47조의4).<br>${risky.slice(0, 12).map(x => esc(`${x.u.f.name} · ${x.u.r.d} ${x.u.r.desc} (${fmt(x.u.r.tax)}원)`)).join('<br>')}${risky.length > 12 ? `<br>… 외 ${risky.length - 12}건` : ''}</li>`; })()}
        ${lateNote.length ? `<li><strong>지연 수취 ${lateNote.length}건</strong>: 확정신고기한 안에 받았으면 공제하되 (66) 지연수취 가산세 5/1,000, 그 뒤 1년 안이면 수정신고·경정청구서와 함께(시행령 제75조 제7호)<br>${lateNote.map(esc).join('<br>')}</li>` : ''}</ul></details>
      <div class="actions no-print"><button type="button" class="btn" id="p-save">신고 기록 저장(filing JSON 내려받기)</button><button type="button" class="btn secondary" id="p-csv">서식 표 CSV</button><button type="button" class="btn secondary" id="p-print">인쇄</button></div>
      <p class="meta">저장하면 이 브라우저에도 남아 확정신고 정산·다음 기간 재계산·예정고지 판단·인수인계에 쓰입니다. 표 아래 「한글 표 복사」로 공문에 붙일 수 있습니다. 참고용 계산이며 신고서의 최종 숫자와 책임은 신고인에게 있습니다.</p>`;
    /* 서식 탭: 등록 단위마다 section.ftab 를 tablist 로, 기본 '신고서'만. 인쇄 때는 CSS 가 전부 펼친다 */
    out.querySelectorAll<HTMLElement>('.unit').forEach((un, ui) => { const tabs = [...un.querySelectorAll<HTMLElement>('section.ftab')]; if (!tabs.length) return; const tl = document.createElement('div'); tl.className = 'tabs no-print'; tl.setAttribute('role', 'tablist'); tl.setAttribute('aria-label', '서식');
      tabs.forEach((t, i) => { const id = `ptab-${ui}-${t.dataset.tab}`; t.id = id + '-panel'; t.setAttribute('role', 'tabpanel'); t.setAttribute('aria-labelledby', id); t.hidden = i !== 0; const bt = document.createElement('button'); bt.type = 'button'; bt.id = id; bt.setAttribute('role', 'tab'); bt.setAttribute('aria-selected', String(i === 0)); bt.setAttribute('aria-controls', t.id); bt.tabIndex = i === 0 ? 0 : -1; bt.textContent = t.dataset.name ?? t.dataset.tab ?? ''; tl.appendChild(bt); });
      const sel2 = (i: number) => { const bs = [...tl.querySelectorAll<HTMLButtonElement>('[role=tab]')]; bs.forEach((x, j) => { x.setAttribute('aria-selected', String(i === j)); x.tabIndex = i === j ? 0 : -1; tabs[j].hidden = i !== j; }); bs[i].focus(); };
      tl.addEventListener('click', e => { const bt = (e.target as HTMLElement).closest<HTMLButtonElement>('[role=tab]'); if (bt) sel2([...tl.children].indexOf(bt)); });
      tl.addEventListener('keydown', e => { const bs = [...tl.children]; const i = bs.indexOf(document.activeElement as HTMLElement); if (i < 0) return; if (e.key === 'ArrowRight') { e.preventDefault(); sel2((i + 1) % bs.length); } if (e.key === 'ArrowLeft') { e.preventDefault(); sel2((i - 1 + bs.length) % bs.length); } if (e.key === 'Home') { e.preventDefault(); sel2(0); } if (e.key === 'End') { e.preventDefault(); sel2(bs.length - 1); } });
      tabs[0].before(tl); });
    helpWire(out, D); out.querySelector<HTMLButtonElement>('[data-goto-step]')?.addEventListener('click', () => pshow(3));
    for (const u of unitRecs) for (const [no, v] of Object.entries(u.cells)) if (no === '48' || no === '66' || (no === '54' && !cells['54'])) add(no, v.amt, v.tax);
    const payAll = unitRecs.reduce((s, u) => s + u.pay, 0); lastRun = { nd: cells['54']?.tax ?? 0, todo: todoCount, pay: payAll, period: sel.value }; pshow(4); scrollTo(out);
    const filing: Filing = { v: 1, org: org.org, period: sel.value, saved: ymd(new Date()), cells, row_ids: rowIds, groups, assets, sales: { ...sales }, units: unitRecs };
    $('p-save')?.addEventListener('click', () => { saveFiling(filing); recalc.forEach(r => { const fl = getFilings()[r.from]; const a = fl?.assets.find(x => x.id === r.a.id); if (a) { a.ratio0 = r.ratio; saveFiling(fl); } }); downloadText(`filing-${org!.org}-${sel.value}.json`, JSON.stringify(filing, null, 2), 'application/json'); toast('신고 기록을 저장했습니다 — 이 브라우저와 내려받은 파일에 남습니다'); renderSum(); });
    $('p-csv')?.addEventListener('click', () => { const rows: (string | number)[][] = [['표', '칸', '구분', '금액', '세액']]; out.querySelectorAll<HTMLTableElement>('table.form').forEach(t => { const cap = t.caption?.textContent ?? ''; t.querySelectorAll('tbody tr').forEach(tr => { const cs = [...tr.children].map(c => c.textContent?.trim() ?? ''); rows.push([cap, ...cs]); }); }); downloadText(`신고서-${org!.org}-${sel.value}.csv`, toCsv(rows), 'text/csv;charset=utf-8'); });
    $('p-print')?.addEventListener('click', () => window.print());
  });
  loadLocal(); renderOrg(); renderPeriods(); renderSum();
}
