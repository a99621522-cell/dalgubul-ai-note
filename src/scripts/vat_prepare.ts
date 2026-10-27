/** /vat/prepare/ 신고 준비(신고 담당). 인계표 → 신고서 칸별 숫자표 + 안분·정산·재계산 + 신고 기록. 참고용 계산, 서버 없음. */
import { $, esc, num, fmt, pct, loadData, getOrg, setOrg, allLedgers, readJsonFile, downloadText, toCsv, facilityStatus, facilityRule, inFiling, salesFacility, periodInfo, periodKeyOf, CELLS, getFilings, saveFiling, deemedRent, nextFiling, ymd, lawLink, type Data, type Org, type OrgFacility, type LedgerRow, type Filing, type PeriodKey } from './vat_rules';
type Ledger = { fid: string; name: string; type: string; month: string; rows: LedgerRow[]; src: string };
const D = loadData();
if (D) init(D);
function init(D: Data) {
  let org: Org | null = getOrg();
  const ledgers = new Map<string, Ledger>();
  const sales: Record<string, { c1: number; c3: number; c4: number }> = {};
  const exemptIn: Record<string, number> = {}; const basisIn: Record<string, { basis: string; ex: number; tot: number }> = {}; const prelimIn: Record<string, { taxable: number; exempt: number; common: number; nondeduct: number }> = {};
  let includePrelimRows = false;
  const f0 = nextFiling(); $('p-due')!.textContent = `다음 신고 ${f0.name} D-${f0.days}`;

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
      lastPeriod = sel.value; for (const k of Object.keys(sales)) delete sales[k]; for (const k of Object.keys(exemptIn)) delete exemptIn[k]; for (const k of Object.keys(prelimIn)) delete prelimIn[k];
      if (saved) { Object.assign(sales, saved.sales ?? {}); for (const g of saved.groups ?? []) exemptIn[g.key] = g.exempt; }
    } const prelimSaved = P.prelimKey ? getFilings()[P.prelimKey] : undefined;
    $('p-period-note')!.innerHTML = `${P.name}: 매입은 ${P.own[0]}~${P.own[P.own.length - 1]} 인계표${P.kind === 'F' ? `, 안분은 ${P.full[0]}~${P.full[5]} 전체 공급가액으로 정산(예정신고 ${prelimSaved ? `기록 ${prelimSaved.saved} 저장분을 씀` : '기록이 이 브라우저에 없음 — 아래에서 예정 때 값을 넣으세요'})` : ''}. 신고·납부 ${P.due}.${saved ? ` <strong>이 기간 신고 기록이 ${saved.saved}에 저장돼 있습니다</strong>(다시 만들면 덮어씀).` : ''}`;
    if (!org) { $('p-coverage')!.innerHTML = '<p class="empty">기관 설정을 먼저 여세요.</p>'; return; }
    const facs = org.facilities.filter(f => inFiling(D, f));
    const months = P.kind === 'F' ? [...P.prelim, ...P.own] : P.own;
    const cell = (f: OrgFacility, m: string) => { const l = ledgers.get(`${f.id}:${m}`); if (!l) return '<td class="note">없음</td>'; const open = l.rows.filter(r => (r.v === 'no' || r.v === 'check') && !r.done).length; return `<td>${l.rows.length}건${open ? ` <span class="verdict check">미처리 ${open}</span>` : ''}</td>`; };
    $('p-coverage')!.innerHTML = `<div class="scroll-x"><table class="data-table compact" data-stack="off"><caption>인계표 도착 현황 — ${esc(P.name)}</caption><thead><tr><th scope="col">시설</th>${months.map(m => `<th scope="col">${m}${P.prelim.includes(m) ? '<br><span class="note">예정분</span>' : ''}</th>`).join('')}</tr></thead><tbody>${facs.map(f => `<tr><th scope="row">${esc(f.name)}</th>${months.map(m => cell(f, m)).join('')}</tr>`).join('')}</tbody></table></div>
      ${P.kind === 'F' ? `<label class="choices" style="margin-top:8px"><span><input type="checkbox" id="p-inc-prelim" ${prelimSaved ? 'checked disabled' : ''}/> 예정 달(${P.prelim[0]}~${P.prelim[2]}) 기록 중 예정신고에 넣지 않은 것을 <strong>(13) 예정신고 누락분</strong>으로 넣기 ${prelimSaved ? '— 저장된 예정신고 기록과 견줘 빠진 행만 자동으로 넣습니다' : '— 예정신고 때 이미 넣은 행이 섞이면 이중 공제가 되니, 확실할 때만 켜세요'}</span></label>` : ''}`;
    includePrelimRows = !!prelimSaved; $<HTMLInputElement>('p-inc-prelim')?.addEventListener('change', e => { includePrelimRows = (e.target as HTMLInputElement).checked; });
    renderSales(P, facs); renderGroups(P, facs, prelimSaved); $('p-run-wrap')!.hidden = false; $('p-result')!.innerHTML = '';
  }
  function renderSales(P: ReturnType<typeof periodInfo>, facs: OrgFacility[]) {
    const wrap = $('p-sales-wrap')!; const tax = facs.filter(f => salesFacility(D, f)); wrap.hidden = !tax.length;
    const days = (() => { const a = new Date(Number(P.own[0].slice(0, 4)), Number(P.own[0].slice(5, 7)) - 1, 1); const last = P.own[P.own.length - 1]; const b = new Date(Number(last.slice(0, 4)), Number(last.slice(5, 7)), 0); return Math.round((b.getTime() - a.getTime()) / 86400000) + 1; })();
    $('p-sales')!.innerHTML = tax.map(f => { const s = sales[f.id] ?? (sales[f.id] = { c1: 0, c3: 0, c4: 0 }); return `<div class="vc-form" data-fid="${f.id}"><p class="q-title full">${esc(f.name)} <span class="note">${facilityRule(D, f)?.name ?? ''}${facilityStatus(D, f) === 'check' ? ' · 과세 여부 확인 필요' : ''}${facilityStatus(D, f) === 'own' ? ' · 수탁기관 자기 사업 — 우리 기관이 받는 사용료·임대료만' : ''}</span></p>
      <label>(1) 세금계산서 발급분 공급가액 <input type="text" inputmode="numeric" data-c="c1" value="${s.c1 ? fmt(s.c1) : ''}" /></label>
      <label>(3) 카드·현금영수증 발행분 공급가액 <input type="text" inputmode="numeric" data-c="c3" value="${s.c3 ? fmt(s.c3) : ''}" /></label>
      <label>(4) 기타(간주임대료 포함) 공급가액 <input type="text" inputmode="numeric" data-c="c4" value="${s.c4 ? fmt(s.c4) : ''}" /></label>
      ${f.deposit ? `<div class="q full"><span class="q-title" style="font-size:var(--small)">간주임대료 계산 — 보증금 × 일수 × 이자율 ÷ 365(시행령 제65조)</span><div class="deem"><label>보증금(원) <input type="text" inputmode="numeric" data-d="dep" /></label><label>일수 <input type="text" inputmode="numeric" data-d="days" value="${days}" /></label><label>이자율(%) <input type="text" inputmode="decimal" data-d="rate" placeholder="정기예금 이자율" /></label><button type="button" class="btn secondary" data-deem>(4)에 더하기</button></div><span class="note">이자율은 국세청 고시 '정기예금 이자율'을 확인해 넣습니다(해마다 바뀜). 계산한 금액은 (4)칸에 더해집니다.</span></div>` : ''}</div>`; }).join('');
    $('p-sales')!.querySelectorAll<HTMLInputElement>('input[data-c]').forEach(i => i.addEventListener('change', () => { const fid = i.closest<HTMLElement>('[data-fid]')!.dataset.fid!; sales[fid][i.dataset.c as 'c1' | 'c3' | 'c4'] = num(i.value); i.value = num(i.value) ? fmt(num(i.value)) : ''; refreshGroupTaxable(); }));
    $('p-sales')!.querySelectorAll<HTMLButtonElement>('[data-deem]').forEach(b => b.addEventListener('click', () => { const box = b.closest<HTMLElement>('[data-fid]')!; const fid = box.dataset.fid!; const g = (k: string) => num(box.querySelector<HTMLInputElement>(`[data-d=${k}]`)!.value); const r = deemedRent(g('dep'), g('days'), g('rate') / 100, P.y); sales[fid].c4 += r; const c4 = box.querySelector<HTMLInputElement>('[data-c=c4]')!; c4.value = fmt(sales[fid].c4); refreshGroupTaxable(); alert(`간주임대료 ${fmt(r)}원을 (4)에 더했습니다.`); }));
  }
  const groupsOf = (facs: OrgFacility[]) => { const m = new Map<string, OrgFacility[]>(); facs.forEach(f => { const k = groupKey(f); m.set(k, [...(m.get(k) ?? []), f]); }); return m; };
  const taxableOf = (fs: OrgFacility[]) => fs.reduce((s, f) => { const x = sales[f.id]; return s + (x ? x.c1 + x.c3 + x.c4 : 0); }, 0);
  function renderGroups(P: ReturnType<typeof periodInfo>, facs: OrgFacility[], prelimSaved?: Filing) {
    const gs = groupsOf(facs); $('p-groups-wrap')!.hidden = false;
    $('p-groups')!.innerHTML = [...gs.entries()].map(([k, fs]) => { const pre = prelimSaved?.groups.find(g => g.key === k); const pi = pre ? (prelimIn[k] = { taxable: pre.taxable, exempt: pre.exempt, common: pre.common_tax, nondeduct: pre.nondeduct }) : (prelimIn[k] ?? (prelimIn[k] = { taxable: 0, exempt: 0, common: 0, nondeduct: 0 }));
      return `<div class="vc-form" data-g="${esc(k)}"><p class="q-title full">${esc(groupName(k))}</p>
      <label>과세 공급가액(이 기간, 2절 합계) <input type="text" data-tax readonly value="${fmt(taxableOf(fs))}" /></label>
      <label>면세 공급가액(이 기간 — 면세 수입 + 면세사업 보조금) <input type="text" inputmode="numeric" data-ex value="${exemptIn[k] ? fmt(exemptIn[k]) : ''}" placeholder="없으면 0" /></label>
      <label>안분 기준 <select data-basis>${[['supply', '공급가액 비율(기본, 시행령 제81조 제1항)'], ['purchase', '매입가액 비율 — 공급가액이 없을 때 1순위(제4항 제1호)'], ['planned', '예정공급가액 비율 — 2순위(제4항 제2호)'], ['area', '예정사용면적 비율 — 3순위, 건물 신축·취득은 1순위(제4항 제3호·단서)']].map(([v, n]) => `<option value="${v}" ${(basisIn[k]?.basis ?? 'supply') === v ? 'selected' : ''}>${n}</option>`).join('')}</select></label>
      <div class="full" data-basis-in ${(basisIn[k]?.basis ?? 'supply') === 'supply' ? 'hidden' : ''}><label>면세 몫(매입가액·예정공급가액·면적) <input type="text" inputmode="decimal" data-bex value="${basisIn[k]?.ex ? fmt(basisIn[k].ex) : ''}" /></label> <label>전체(같은 단위) <input type="text" inputmode="decimal" data-btot value="${basisIn[k]?.tot ? fmt(basisIn[k].tot) : ''}" /></label><span class="note">공급가액 비율을 쓸 수 없는 기간(과세·면세 어느 한쪽 공급가액이 없음)에만. 건물·구축물을 예정사용면적으로 안분했으면 면적이 확정될 때까지 같은 기준(제5항).</span></div>
      ${P.kind === 'F' ? `<p class="note full">예정신고(${P.prelim[0]}~${P.prelim[2]}) 때 값 ${pre ? '— 저장된 기록에서 가져옴' : '— 예정신고서를 보고 넣으세요'}</p>
      <label>예정 과세 공급가액 <input type="text" inputmode="numeric" data-p="taxable" value="${pi.taxable ? fmt(pi.taxable) : ''}" /></label><label>예정 면세 공급가액 <input type="text" inputmode="numeric" data-p="exempt" value="${pi.exempt ? fmt(pi.exempt) : ''}" /></label>
      <label>예정 공통매입세액 <input type="text" inputmode="numeric" data-p="common" value="${pi.common ? fmt(pi.common) : ''}" /></label><label>예정 때 불공제한 면세분(54) <input type="text" inputmode="numeric" data-p="nondeduct" value="${pi.nondeduct ? fmt(pi.nondeduct) : ''}" /></label>` : ''}</div>`; }).join('');
    $('p-groups')!.querySelectorAll<HTMLInputElement>('input[data-ex]').forEach(i => i.addEventListener('change', () => { exemptIn[i.closest<HTMLElement>('[data-g]')!.dataset.g!] = num(i.value); i.value = fmt(num(i.value)); }));
    const readBasis = (box: HTMLElement) => { const k = box.dataset.g!; const b = basisIn[k] ?? (basisIn[k] = { basis: 'supply', ex: 0, tot: 0 }); b.basis = box.querySelector<HTMLSelectElement>('[data-basis]')!.value; b.ex = num(box.querySelector<HTMLInputElement>('[data-bex]')!.value); b.tot = num(box.querySelector<HTMLInputElement>('[data-btot]')!.value); box.querySelector<HTMLElement>('[data-basis-in]')!.hidden = b.basis === 'supply'; };
    $('p-groups')!.querySelectorAll<HTMLElement>('[data-g]').forEach(box => { box.querySelectorAll<HTMLElement>('[data-basis],[data-bex],[data-btot]').forEach(el => el.addEventListener('change', () => readBasis(box))); });
    $('p-groups')!.querySelectorAll<HTMLInputElement>('input[data-p]').forEach(i => i.addEventListener('change', () => { const k = i.closest<HTMLElement>('[data-g]')!.dataset.g!; (prelimIn[k] as unknown as Record<string, number>)[i.dataset.p!] = num(i.value); i.value = num(i.value) ? fmt(num(i.value)) : ''; }));
  }
  const refreshGroupTaxable = () => { if (!org) return; const gs = groupsOf(org.facilities.filter(f => inFiling(D, f))); $('p-groups')!.querySelectorAll<HTMLElement>('[data-g]').forEach(box => { const fs = gs.get(box.dataset.g!) ?? []; box.querySelector<HTMLInputElement>('[data-tax]')!.value = fmt(taxableOf(fs)); }); };

  /* ---------- 숫자표 ---------- */
  $('p-run')?.addEventListener('click', () => {
    if (!org) return; const P = periodInfo(sel.value); const prelimSaved = P.prelimKey ? getFilings()[P.prelimKey] : undefined; const prevIds = new Set(prelimSaved?.row_ids ?? []);
    const facs = org.facilities.filter(f => inFiling(D, f)); const gs = groupsOf(facs);
    const cells: Record<string, { amt: number; tax: number }> = {}; const add = (no: string, amt: number, tax: number) => { const c = cells[no] ?? (cells[no] = { amt: 0, tax: 0 }); c.amt += amt; c.tax += tax; };
    const common: Record<string, number> = {}; const rowIds: string[] = []; const unresolved: string[] = [], excluded: string[] = [], lateNote: string[] = [], missing: string[] = [];
    const assets: Filing['assets'] = []; let nInv = 0, nCard = 0, nNo = 0;
    for (const f of facs) {
      const months = includePrelimRows ? [...P.prelim, ...P.own] : P.own;
      for (const m of P.own) if (!ledgers.has(`${f.id}:${m}`)) missing.push(`${f.name} ${m}`);
      for (const m of months) {
        const l = ledgers.get(`${f.id}:${m}`); if (!l) continue; const isPre = P.prelim.includes(m);
        for (const r of l.rows) {
          if (isPre && prevIds.has(r.id)) continue;
          const tag = `${f.name} · ${r.d} ${r.desc} (${fmt(r.tax)}원)`;
          if (r.v === 'check') { unresolved.push(tag + ' — ' + r.todo); continue; }
          if (r.v === 'none') continue;
          const inv = (r.proof === 'e_invoice' || r.proof === 'p_invoice') && r.payee === 'org'; const card = (r.proof === 'card' || r.proof === 'cash') && r.vat_sep;
          if (r.v === 'no' && !inv) { excluded.push(tag + ' — ' + r.title + (r.fix_due ? ` · 수정세금계산서 기한 ${r.fix_due}${r.fix_due < ymd(new Date()) ? '(지남)' : ''}` : '')); continue; }
          if (!inv && !card) { excluded.push(tag + ' — 증빙 요건 미달'); continue; }
          rowIds.push(r.id); if (r.late) lateNote.push(tag);
          const main = isPre ? '13' : inv ? (r.asset ? '12' : '10') : (r.asset ? '45' : '44');
          add(main, r.amt, r.tax); if (inv) nInv++; else nCard++;
          const gk = groupKey(f);
          if (r.v === 'no') { add('53', r.amt, r.tax); nNo++; }
          if (r.v === 'split') common[gk] = (common[gk] ?? 0) + r.tax;
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
      if (!fullC) { if (ct || ex) groups.push({ key: k, name: groupName(k), taxable: tx, exempt: ex, ratio: fullT + fullE ? fullE / (fullT + fullE) : 0, common_tax: 0, nondeduct: 0 }); continue; }
      const b = basisIn[k]; const alt = b && b.basis !== 'supply' && b.tot > 0; const tot = fullT + fullE; const ratio = alt ? b.ex / b.tot : tot ? fullE / tot : 0; let skipped: string | undefined;
      const BASIS_NAME: Record<string, string> = { purchase: '매입가액 비율', planned: '예정공급가액 비율', area: '예정사용면적 비율' };
      if (!alt && !tot) skipped = '공급가액 없음 — 3절에서 안분 기준을 매입가액·예정공급가액·예정사용면적 비율로 고르면 계산합니다(시행령 제81조 제4항)';
      else if (fullC < (small.amount_lt ?? 50000)) skipped = small.name; else if (ratio < (r5.ratio_lt ?? 0.05) && fullC < (r5.amount_lt ?? 5000000)) skipped = r5.name;
      const fullNd = skipped ? 0 : Math.floor(fullC * ratio); const nd = P.kind === 'F' ? fullNd - (pi?.nondeduct ?? 0) : fullNd;
      if (!skipped || P.kind === 'F') add('54', 0, nd);
      groups.push({ key: k, name: groupName(k), taxable: tx, exempt: ex, ratio, common_tax: ct, nondeduct: nd, skipped: skipped ?? (alt ? `${BASIS_NAME[b.basis]}로 안분(${fmt(b.ex)} ÷ ${fmt(b.tot)})` : undefined), basis: alt ? b.basis : 'supply' });
      assets.filter(a => a.group === k && a.common).forEach(a => { a.ratio0 = ratio; });
    }
    /* 재계산(지난 신고 기록의 공통 자산) */
    const hi = (k: PeriodKey) => { const p = periodInfo(k); return p.y * 2 + p.half - 1; }; const curH = hi(sel.value);
    const recalc: { a: Filing['assets'][number]; from: PeriodKey; ratio: number; n: number; amt: number }[] = [];
    for (const [k, fl] of Object.entries(getFilings())) { if (k === sel.value || hi(k) >= curH) continue; for (const a of fl.assets ?? []) { if (!a.common) continue; const g = groups.find(x => x.key === a.group); if (!g) continue; const diff = g.ratio - a.ratio0; if (Math.abs(diff) < D.rules.recalc.threshold_pp) continue; const n = curH - hi(a.period); const remain = Math.max(0, 1 - D.rules.recalc.rates[a.kind] * n); if (remain <= 0) continue; recalc.push({ a, from: k, ratio: g.ratio, n, amt: Math.floor(a.tax * remain * diff) }); } }
    /* 결과 */
    const sum = (nos: string[]) => nos.reduce((s, n) => s + (cells[n]?.tax ?? 0), 0);
    const c15 = sum(['44', '45']), c16 = sum(['10', '12', '13']) + c15, c17 = sum(['53', '54']);
    const rowsHtml = CELLS.map(c => { const v = cells[c.no]; return `<tr><td>(${c.no})</td><th scope="row">${c.name}</th><td>${v && v.amt ? fmt(v.amt) : ''}</td><td>${v ? fmt(v.tax) : '0'}</td></tr>`; }).join('');
    const out = $('p-result')!;
    out.innerHTML = `<div class="section-head"><h2>4. ${esc(P.name)} — 신고서 칸별 숫자표</h2><span class="meta">참고용 · 시행규칙 별지 제21호서식(${esc(D.form_version ?? '2026-04-01')} 판에서 확인한 칸 번호 — 서식이 바뀌면 칸 번호를 다시 확인)</span></div>
      <div class="scroll-x"><table class="data-table vat-table" id="p-cells" data-stack="off"><caption>${esc(org.org)} ${esc(P.name)} 신고서 칸별 숫자표(인계표 ${ledgers.size}개 · 매입 ${rowIds.length}건 · 참고용)</caption><thead><tr><th scope="col">칸</th><th scope="col">이름</th><th scope="col">공급가액(금액)</th><th scope="col">세액</th></tr></thead><tbody>${rowsHtml}
        <tr class="total"><td></td><th scope="row">(15) 그 밖의 공제매입세액 합계 = (44)+(45)</th><td></td><td>${fmt(c15)}</td></tr><tr class="total"><td></td><th scope="row">(16) 매입세액 합계 = (10)+(12)+(13)+(15)</th><td></td><td>${fmt(c16)}</td></tr><tr class="total"><td></td><th scope="row">(17) 공제받지 못할 매입세액 = (53)+(54)</th><td></td><td>${fmt(c17)}</td></tr><tr class="total"><td></td><th scope="row">차감 매입세액 (16) − (17)</th><td></td><td>${fmt(c16 - c17)}</td></tr></tbody></table></div>
      <p class="meta">세금계산서 수취분 ${nInv}건(합계표), 카드·현금영수증 ${nCard}건(수령명세서), 그중 불공제 명세 ${nNo}건. 매출 (1)(3)(4)는 2절 입력값, 세액은 10%. (12)(45) 고정자산은 '여러 해 쓰는 것' 표시한 행. 원 미만 버림.</p>
      <h3>공통매입세액 안분</h3>${groups.length ? `<div class="scroll-x"><table class="data-table vat-table" data-stack="off"><caption>공통매입세액 안분 내역 — ${esc(P.name)}</caption><thead><tr><th scope="col">등록 단위</th><th scope="col">과세 공급가액</th><th scope="col">면세 공급가액</th><th scope="col">면세비율${P.kind === 'F' ? '(6개월)' : ''}</th><th scope="col">공통매입세액(이 기간)</th><th scope="col">(54) 면세분${P.kind === 'F' ? ' — 예정분 정산 뒤' : ''}</th><th scope="col">비고</th></tr></thead><tbody>${groups.map(g => `<tr><th scope="row">${esc(g.name)}</th><td>${fmt(g.taxable)}</td><td>${fmt(g.exempt)}</td><td>${pct(g.ratio)}</td><td>${fmt(g.common_tax)}</td><td>${fmt(g.nondeduct)}</td><td class="note">${esc(g.skipped ?? (P.kind === 'F' ? '과세기간 전체 공급가액으로 다시 계산해 예정신고 불공제분을 뺀 값(음수면 공제가 늘어남 — 공통매입세액 정산 명세서)' : '예정신고기간 공급가액으로 안분, 확정 때 정산'))}</td></tr>`).join('')}</tbody></table></div>` : '<p class="meta">공통(파랑) 지출이 없어 안분할 것이 없습니다.</p>'}
      <p class="meta">근거: ${lawLink(D, { law: 'act', art: '제40조' })} · ${lawLink(D, { law: 'decree', art: '제81조' })} · ${lawLink(D, { law: 'decree', art: '제82조' })} · 면세공급가액에는 면세사업 관련 국고·공공보조금을 넣습니다(제81조 제1항 단서).</p>
      <h3>감가상각자산 — 이번 기간 취득 ${assets.length}건 · 재계산 대상 ${recalc.length}건</h3>
      ${assets.length ? `<div class="scroll-x"><table class="data-table vat-table" data-stack="off"><caption>자산대장에 올릴 것(재계산 추적용)</caption><thead><tr><th scope="col">시설</th><th scope="col">내용</th><th scope="col">세액</th><th scope="col">종류</th><th scope="col">공통 여부</th><th scope="col">취득 때 면세비율</th></tr></thead><tbody>${assets.map(a => `<tr><th scope="row">${esc(a.facility)}</th><td>${esc(a.desc)}</td><td>${fmt(a.tax)}</td><td>${a.kind === 'building' ? '건물·구축물(5%)' : '그 밖(25%)'}</td><td>${a.common ? '공통(안분)' : '과세 전용'}</td><td>${a.common ? pct(a.ratio0) : '—'}</td></tr>`).join('')}</tbody></table></div>` : ''}
      ${recalc.length ? `<div class="scroll-x"><table class="data-table vat-table" data-stack="off"><caption>납부세액 재계산(법 제41조·시행령 제83조) — 면세비율이 5%p 이상 바뀐 공통 자산</caption><thead><tr><th scope="col">자산</th><th scope="col">취득 기간</th><th scope="col">취득 때 비율</th><th scope="col">이번 비율</th><th scope="col">경과 과세기간</th><th scope="col">가산(+)·공제(−) 세액</th></tr></thead><tbody>${recalc.map(r => `<tr><th scope="row">${esc(r.a.facility)} ${esc(r.a.desc)} (${fmt(r.a.tax)}원)</th><td>${r.from}</td><td>${pct(r.a.ratio0)}</td><td>${pct(r.ratio)}</td><td>${r.n}</td><td>${r.amt >= 0 ? '+' : ''}${fmt(r.amt)}</td></tr>`).join('')}</tbody></table></div><p class="meta">재계산액은 확정신고서에 따로 반영합니다(신고서 작성 요령의 재계산 칸). 저장하면 다음 재계산의 기준 비율이 이번 비율로 바뀝니다.</p>` : '<p class="meta">지난 신고 기록의 공통 자산 중 면세비율이 5%p 이상 바뀐 것은 없습니다(기록이 없으면 비교하지 못합니다).</p>'}
      <h3>처리할 것</h3>
      <ul class="meta-list">${missing.length ? `<li><strong>인계표가 아직 없는 시설·달 ${missing.length}</strong>: ${esc(missing.join(', '))} — 시설 담당에게 요청</li>` : '<li>이 기간 모든 시설·달의 인계표가 있습니다.</li>'}
        ${unresolved.length ? `<li><strong>노랑(확인 필요) ${unresolved.length}건 — 숫자표에서 뺐습니다</strong>:<br>${unresolved.map(esc).join('<br>')}</li>` : ''}
        ${excluded.length ? `<li><strong>신고서 밖 ${excluded.length}건(증빙 요건 미달·다른 명의 등)</strong> — 수정세금계산서를 받으면 다음 신고(또는 경정청구)에 넣습니다:<br>${excluded.map(esc).join('<br>')}</li>` : ''}
        ${lateNote.length ? `<li><strong>지연 수취 ${lateNote.length}건</strong>: 확정신고기한 뒤 1년 안이면 수정신고·경정청구서와 함께(시행령 제75조 제7호)<br>${lateNote.map(esc).join('<br>')}</li>` : ''}</ul>
      <h3>홈택스에 함께 낼 것</h3>
      <ul class="meta-list"><li>매입처별 세금계산서합계표(전자세금계산서는 자동 조회분 확인) — ${nInv}건</li><li>신용카드매출전표등 수령명세서 — ${nCard}건${D.rules.card.practice ? ' (기관 법인카드를 홈택스 사업용 신용카드로 등록해 두면 자동 집계)' : ''}</li>${nNo ? `<li>공제받지 못할 매입세액 명세서 — ${nNo}건(53)</li>` : ''}${groups.some(g => g.common_tax) ? '<li>공통매입세액 안분계산 내역(54)' + (P.kind === 'F' ? ' · 공통매입세액 정산 명세' : '') + '</li>' : ''}${facs.some(f => f.deposit) ? '<li>부동산임대공급가액명세서(보증금·간주임대료)</li>' : ''}${recalc.length ? '<li>납부세액 재계산 내역</li>' : ''}</ul>
      <div class="actions no-print"><button type="button" class="btn" id="p-save">신고 기록 저장(filing JSON 내려받기)</button><button type="button" class="btn secondary" id="p-csv">숫자표 CSV</button><button type="button" class="btn secondary" id="p-print">인쇄</button></div>
      <p class="meta">저장하면 이 브라우저에도 남아 확정신고 정산·다음 기간 재계산·인수인계에 쓰입니다. 표 아래 「한글 표 복사」로 공문에 붙일 수 있습니다. 참고용 계산이며 신고서의 최종 숫자와 책임은 신고인에게 있습니다.</p>`;
    const filing: Filing = { v: 1, org: org.org, period: sel.value, saved: ymd(new Date()), cells, row_ids: rowIds, groups, assets, sales: { ...sales } };
    $('p-save')?.addEventListener('click', () => { saveFiling(filing); recalc.forEach(r => { const fl = getFilings()[r.from]; const a = fl?.assets.find(x => x.id === r.a.id); if (a) { a.ratio0 = r.ratio; saveFiling(fl); } }); downloadText(`filing-${org!.org}-${sel.value}.json`, JSON.stringify(filing, null, 2), 'application/json'); alert('저장했습니다. 이 브라우저와 내려받은 파일에 남습니다.'); });
    $('p-csv')?.addEventListener('click', () => downloadText(`신고서숫자표-${org!.org}-${sel.value}.csv`, toCsv([['칸', '이름', '공급가액', '세액'], ...CELLS.map(c => [`(${c.no})`, c.name, cells[c.no]?.amt ?? 0, cells[c.no]?.tax ?? 0]), ['', '(16) 매입세액 합계', '', c16], ['', '(17) 공제받지 못할 매입세액', '', c17]]), 'text/csv;charset=utf-8'));
    $('p-print')?.addEventListener('click', () => window.print());
    out.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  loadLocal(); renderOrg(); renderPeriods();
}
