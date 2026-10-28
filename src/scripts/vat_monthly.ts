/** /vat/monthly/ 시설 지출 기록 → 매입 인계표(수탁기관·시설 부서). 판정은 vat_rules.judge(공용), 질문은 현장 말. localStorage 저장, 서버 없음. */
import { $, esc, num, fmt, loadData, judge, toInput, fixDue, FEE_NAME, payeeQ, runName, STATUS_LABEL_SHORT, parseTable, guessColumns, COL_GUESS, guessWhat, EVID_Q, matchMap, learnMap, type Evid, getOrg, setOrg, getLedger, setLedger, readJsonFile, downloadText, toCsv, facilityStatus, STATUS_WORD, RUN_NAME, PROOF_Q, PAYEE_Q, USE_Q, WHAT_Q, ASSET_WHAT, SIGNAL, LABEL, lawLink, lawText, uniq, uid, ymd, monthStr, periodOf, nextFiling, handoverDue, toast, vatConfirm, gridKeys, helpWire, scrollTo, type Data, type Org, type OrgFacility, type LedgerRow, type ProofQ, type PayeeQ, type UseQ, type Out, type Verdict } from './vat_rules';
const D = loadData();
if (D) init(D);
function init(D: Data) {
  const VSHAPE: Record<Verdict, string> = { ok: '●', split: '◆', no: '■', none: '○', check: '▲' };   // 색 + 모양 + 글자(1.4.1)
  let org: Org | null = getOrg(); let fac: OrgFacility | null = null; let month = monthStr();
  const facSel = $<HTMLSelectElement>('m-fac')!, monthIn = $<HTMLInputElement>('m-month')!, form = $<HTMLFormElement>('m-form')!, res = $('m-result')!;
  /* 깊은 링크(공무원 UX 재설계 2026-10-28): ?fac=<id>&month=YYYY-MM&open=1 — 대시보드·신고 준비 '지금 고치기'가 쓴다 */
  const qs = new URLSearchParams(location.search); if (/^\d{4}-\d{2}$/.test(qs.get('month') ?? '')) month = qs.get('month')!;
  monthIn.value = month; ($<HTMLInputElement>('m-d')!).value = ymd(new Date());
  const f0 = nextFiling(); $('m-dday')!.textContent = `다음 신고 ${f0.name} D-${f0.days}` + (org ? ` · 인계표 마감 D-${handoverDue(org.handover_day || 5).days}` : '');
  const chips = (id: string, name: string, opts: { key: string; name: string }[], first = true) => { $(id)!.innerHTML = opts.map((o, i) => `<label><input type="radio" name="${name}" value="${o.key}" ${first && i === 0 ? 'checked' : ''}/> ${esc(o.name)}</label>`).join(''); };
  chips('m-proof', 'm-proof', PROOF_Q); chips('m-payee', 'm-payee', payeeQ(org?.kind)); chips('m-use', 'm-use', USE_Q); chips('m-what', 'm-what', WHAT_Q); chips('m-evid', 'm-evid', EVID_Q);
  const val = (name: string) => (document.querySelector<HTMLInputElement>(`input[name=${name}]:checked`)?.value ?? '');
  const syncQ = () => { const p = val('m-proof'); const card = p === 'card' || p === 'cash'; $('m-vat-q')!.hidden = !card; $('m-payee-q')!.hidden = p === 'bill' || p === 'none'; $('m-asset-q')!.hidden = !ASSET_WHAT.has(val('m-what')); $('m-evid-q')!.hidden = val('m-use') !== 'this'; };
  form.addEventListener('change', syncQ); syncQ();

  function renderOrg() {
    const st = $('m-org-state')!;
    if (!org) { st.innerHTML = '이 브라우저에 기관 설정이 없습니다. 아래에서 파일을 여세요.'; facSel.innerHTML = '<option value="">— 기관 설정을 먼저 여세요 —</option>'; form.hidden = true; return; }
    st.innerHTML = `<strong>${esc(org.org)}</strong>${org.kind === 'contractor' ? ' <span class="verdict check">수탁기관</span>' : ''} · ${esc(org.dept || '')} · 시설 ${org.facilities.length}곳 · 인계표 매달 ${org.handover_day}일까지 · 설정 ${org.created}`; chips('m-payee', 'm-payee', payeeQ(org.kind));
    facSel.innerHTML = '<option value="">— 시설을 고르세요 —</option>' + org.facilities.map(f => { const s = facilityStatus(D, f); return `<option value="${f.id}">${esc(f.name)} (${STATUS_LABEL_SHORT[s]})</option>`; }).join('');
    const last = qs.get('fac') || sessionStorage.getItem('vat-fac'); if (last && org.facilities.some(f => f.id === last)) { facSel.value = last; pick(); if (qs.get('open') === '1') { const w = $<HTMLDetailsElement>('mb-wrap'); if (w) { w.open = true; } } if (qs.get('fac')) scrollTo(qs.get('open') === '1' ? $('mb-wrap') : $('m-list')); }
    renderRules();
  }
  function pick() {
    fac = org?.facilities.find(f => f.id === facSel.value) ?? null; month = monthIn.value || monthStr();
    const note = $('m-facnote')!;
    if (!fac) { form.hidden = true; $('m-list')!.hidden = true; note.textContent = ''; return; }
    sessionStorage.setItem('vat-fac', fac.id);
    const s = facilityStatus(D, fac); const reg = org!.unit === 'entity' ? org!.reg_no : fac.reg_no;
    note.innerHTML = `<span class="verdict ${s === 'agency' ? 'none' : s}">${STATUS_WORD[s]}</span> · ${esc(runName(org!.kind, fac.run))}${reg ? ` · 영수증 받을 번호 <strong>${esc(reg)}</strong>` : ''} · ${periodOf(month)}신고 대상 달`;
    form.hidden = false; if (s === 'agency') note.innerHTML += `<br>군 명의 사업이라 지출 영수증은 <strong>${esc(org!.parent || '군')} 등록번호</strong>로 받습니다. 여기 넣으면 공단 명의인지 군 명의인지 가려 줍니다(군 명의는 군 신고 담당에게 인계).`; if (s === 'own') note.innerHTML += `<br>수탁기관이 쓴 돈은 수탁기관 장부에 적습니다. <strong>${esc(org!.org)}가 이 시설에 직접 낸 돈(수선·장비·공사)</strong>만 여기에 넣으세요 — ${esc(org!.org)}가 수탁기관에게 받는 것: ${esc(FEE_NAME[fac.fee ?? 'unknown'])}.`;
    renderList();
  }
  facSel.addEventListener('change', pick); monthIn.addEventListener('change', pick);
  $<HTMLInputElement>('m-open')?.addEventListener('change', async e => { const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return; try { const o = await readJsonFile(f) as Org; if (!o || o.v !== 1 || !Array.isArray(o.facilities)) throw new Error(); org = o; setOrg(o); renderOrg(); } catch { $('m-org-state')!.textContent = '기관 설정 파일(org.json)이 아닙니다.'; } });

  /* 판정·기록 */
  form.addEventListener('submit', e => {
    e.preventDefault(); if (!org || !fac) return;
    const q = { proof: val('m-proof') as ProofQ, payee: (($('m-payee-q') as HTMLElement).hidden ? 'org' : val('m-payee')) as PayeeQ, vat_sep: val('m-vatsep') === '1', use: val('m-use') as UseQ, what: val('m-what'), asset: ASSET_WHAT.has(val('m-what')) && ($<HTMLInputElement>('m-asset')!).checked, late: ($<HTMLInputElement>('m-late')!).checked, subsidy: ($<HTMLInputElement>('m-subsidy')!).checked };
    const m = toInput(D, org, fac, q); const o: Out = m.override ?? judge(D, m.input); if (m.note) o.why.push(m.note);
    const d0 = $<HTMLInputElement>('m-d')!.value || ymd(new Date()); const fd = m.input.proof === 'tax_invoice_other' && o.v === 'no' ? fixDue(d0) : null; if (fd) o.todo.unshift(`수정세금계산서 발급 기한 ${fd.due}(${fd.days >= 0 ? `D-${fd.days}` : `${-fd.days}일 지남 — 착오 정정이 아니면 공제 불가`}) — 공급일 기준 과세기간 확정신고기한 다음 날부터 1년(시행령 제70조 제1항 제6호).`);
    const amt = num($<HTMLInputElement>('m-amt')!.value); let tax = num($<HTMLInputElement>('m-tax')!.value); if (!tax && amt && o.v !== 'none') tax = Math.floor(amt * 0.1);
    const row: LedgerRow = { id: uid(), d: $<HTMLInputElement>('m-d')!.value || ymd(new Date()), desc: $<HTMLInputElement>('m-desc')!.value.trim() || '(내용 없음)', amt, tax, proof: q.proof, payee: q.payee, vat_sep: q.vat_sep, use: q.use, what: q.what, asset: q.asset, late: q.late, subsidy: q.subsidy, fix_due: fd?.due, evid: q.use === 'this' ? (val('m-evid') as Evid) : undefined, v: o.v, title: o.title, todo: o.todo[0] || '', basis: uniq(o.basis).map(lawText).join(', '), done: false };
    const rows = getLedger(fac.id, month); rows.push(row); setLedger(fac.id, month, rows);
    res.innerHTML = `<div class="vc-card"><p class="note">판정은 참고이며 기관의 판단이 아닙니다.</p><h3><span class="sig ${o.v}" aria-hidden="true"></span>${esc(SIGNAL[o.v])}<span class="verdict ${o.v}">${LABEL[o.v]}</span></h3><p><strong>${esc(o.title)}</strong> — ${esc(row.desc)}${tax ? ` · 부가세 ${fmt(tax)}원` : ''}</p>
      <p class="label">왜</p><ul>${o.why.map(w => `<li>${esc(w)}</li>`).join('')}</ul>${o.todo.length ? `<p class="label">지금 할 일</p><ul>${o.todo.map(w => `<li>${esc(w)}</li>`).join('')}</ul>` : ''}
      <p class="label">근거 조문</p><p class="meta">${uniq(o.basis).map(b => lawLink(D, b)).join(' · ')}</p><p class="meta">기록에 넣었습니다. 아래 표에서 확인하세요.</p></div>`;
    renderList(); ($<HTMLInputElement>('m-desc')!).value = ''; ($<HTMLInputElement>('m-amt')!).value = ''; ($<HTMLInputElement>('m-tax')!).value = ''; ($<HTMLInputElement>('m-desc')!).focus();
  });
  const name = (opts: { key: string; name: string }[], k: string) => opts.find(o => o.key === k)?.name.split('(')[0].trim() ?? k;
  function renderList() {
    if (!fac) return; const rows = getLedger(fac.id, month); const list = $('m-list')!; list.hidden = !rows.length; if (!rows.length) return;
    $('m-list-title')!.textContent = `${fac.name} · ${month.replace('-', '년 ')}월 기록`; $('m-caption')!.textContent = `매입 인계표 — ${org!.org} ${fac.name} ${month.replace('-', '년 ')}월 (${periodOf(month)}신고 대상, 참고용 판정)`;
    const tb = $<HTMLTableElement>('m-table')!.tBodies[0];
    tb.innerHTML = rows.map(r => `<tr class="v-${r.v}${r.done ? ' done' : ''}" data-id="${r.id}"><td>${r.d}</td><td>${esc(r.desc)}</td><td>${r.amt ? fmt(r.amt) : ''}</td><td>${r.tax ? fmt(r.tax) : ''}</td><td>${esc(name(PROOF_Q, r.proof))}</td><td>${esc(name(PAYEE_Q, r.payee))}</td><td>${esc(name(USE_Q, r.use))}</td><td>${esc(name(WHAT_Q, r.what))}${r.asset ? ' · 여러 해 씀' : ''}${r.late ? ' · 지연' : ''}${r.subsidy ? ' · 보조금' : ''}</td><td class="note">${r.use === 'this' ? (!r.evid || r.evid === 'none' ? '<span class="verdict check">근거 없음</span>' : esc(name(EVID_Q, r.evid))) : ''}${r.biz ? `<br>${esc(r.biz)}` : ''}</td><td class="keep"><span class="sig ${r.v}" aria-hidden="true"></span><span class="sr-only">${VSHAPE[r.v]}</span>${LABEL[r.v]}</td><td class="note">${esc(r.todo)}</td><td class="note">${esc(r.basis)}</td><td class="no-print keep"><label><input type="checkbox" data-done ${r.done ? 'checked' : ''}/> 처리</label> <button type="button" class="link-btn" data-del>삭제</button></td></tr>`).join('');
    const n = (v: string) => rows.filter(r => r.v === v).length; const t = (v: string) => rows.filter(r => r.v === v).reduce((s, r) => s + r.tax, 0);
    $('m-sum')!.textContent = `${rows.length}건 · 초록 ${n('ok')}건 ${fmt(t('ok'))}원 · 파랑 ${n('split')}건 ${fmt(t('split'))}원 · 빨강 ${n('no')}건 · 노랑 ${n('check')}건 · 회색 ${n('none')}건 — 미처리 빨강·노랑 ${rows.filter(r => (r.v === 'no' || r.v === 'check') && !r.done).length}건`;
    tb.querySelectorAll<HTMLInputElement>('[data-done]').forEach(c => c.addEventListener('change', () => { const r = rows.find(x => x.id === c.closest('tr')!.getAttribute('data-id'))!; r.done = c.checked; setLedger(fac!.id, month, rows); renderList(); }));
    tb.querySelectorAll<HTMLButtonElement>('[data-del]').forEach(b => b.addEventListener('click', () => { const id = b.closest('tr')!.getAttribute('data-id'); const fid = fac!.id, m = month; const snap = rows.slice(); setLedger(fid, m, rows.filter(x => x.id !== id)); renderList(); toast('1건을 지웠습니다', { fn: () => { setLedger(fid, m, snap); renderList(); } }); }));
  }
  const header = ['기관', '시설', '달', '날짜', '내용', '공급가액', '부가세', '영수증', '받는 사람', '어디에 썼나', '무엇', '전용 근거', '사업·부서', '여러 해 씀', '지연 수취', '보조금', '수정세금계산서 기한', '판정', '지금 할 일', '근거', '처리'];
  $('m-csv')?.addEventListener('click', () => { if (!fac || !org) return; const rows = getLedger(fac.id, month); downloadText(`매입인계표-${org.org}-${fac.name}-${month}.csv`, toCsv([header, ...rows.map(r => [org!.org, fac!.name, month, r.d, r.desc, r.amt, r.tax, name(PROOF_Q, r.proof), name(PAYEE_Q, r.payee), name(USE_Q, r.use), name(WHAT_Q, r.what), r.use === 'this' ? name(EVID_Q, r.evid ?? 'none') : '', r.biz ?? '', r.asset ? '예' : '', r.late ? '예' : '', r.subsidy ? '예' : '', r.fix_due ?? '', LABEL[r.v], r.todo, r.basis, r.done ? '처리' : ''])]), 'text/csv;charset=utf-8'); });
  $('m-json')?.addEventListener('click', () => { if (!fac || !org) return; downloadText(`ledger-${org.org}-${fac.name}-${month}.json`, JSON.stringify({ v: 1, org: org.org, facility: fac.id, facility_name: fac.name, type: fac.type, month, period: periodOf(month), exported: ymd(new Date()), rows: getLedger(fac.id, month) }, null, 2), 'application/json'); });
  $('m-print')?.addEventListener('click', () => window.print());
  $('m-clear')?.addEventListener('click', async () => { if (!fac) return; const rows = getLedger(fac.id, month); if (!(await vatConfirm(`${fac.name} ${month} 기록 ${rows.length}건을 지웁니다. 10초 안에 되돌릴 수 있습니다.`, '지우기'))) return; const fid = fac.id, m = month; setLedger(fid, m, []); renderList(); res.innerHTML = ''; toast(`${rows.length}건을 지웠습니다`, { fn: () => { setLedger(fid, m, rows); renderList(); } }); });
  /* ---------- 여러 건 한꺼번에(붙여넣기) — 공무원 UX 재설계 2026-10-28(docs/design/vat-ux-spec.md §3.2): 열 머리 드롭다운으로 열 교정(즉시 다시 그림), 매핑표 자동 귀속 행은 접고 미확정만 보이기, 행 선택 → 일괄 지정, 행마다 즉시 신호등(넣을 때와 같은 toInput→judge), 인라인 검증(금액 없음·날짜 확인·중복 가능 → 체크 해제), 넣기 뒤 토스트 되돌리기. 판정 규칙은 그대로 ---------- */
  const mbWrap = $<HTMLDetailsElement>('mb-wrap')!; const mbForm = $<HTMLFormElement>('mb-form')!;
  const mbVal = (n: string) => document.querySelector<HTMLInputElement>(`input[name=${n}]:checked`)?.value ?? '';
  mbForm.addEventListener('change', () => { const card = mbVal('mb-proof') !== 'e_invoice'; $('mb-vat-q')!.hidden = !card; $('mb-payee-q')!.hidden = card; if (grid.length) buildPreview(); });
  let grid: string[][] = [], hasHeader = false, map: Record<string, number> = {}; let mbView: 'pending' | 'auto' | 'all' = 'pending';
  type Item = { date: string; rawDate: string; desc: string; amt: number; tax: number; payee: PayeeQ; sup: string; sreg: string; what: string; asset: boolean; use: UseQ; evid: Evid; fid: string; auto: boolean; biz: string; dept: string; on: boolean; flags: string[]; v: Verdict; title: string };
  let items: Item[] = [];
  mbForm.addEventListener('submit', e => {
    e.preventDefault(); grid = parseTable($<HTMLTextAreaElement>('mb-text')!.value); $('mb-map')!.innerHTML = ''; if (!grid.length) { $('mb-preview')!.innerHTML = '<p class="callout info" role="status">붙여넣은 글자가 없습니다 — 홈택스 목록을 머리글 줄부터 복사해 위 칸에 붙여넣으세요.</p>'; return; }
    map = guessColumns(grid[0]); hasHeader = Object.keys(map).length >= 2; if (!hasHeader) map = {}; mbView = 'pending';
    buildPreview();
  });
  /** 행 하나를 넣을 때와 똑같이 판정(미리보기용, 저장 안 함) */
  const judgeItem = (it: Item, proof: string, vatSep: boolean) => { const rf = org!.facilities.find(f => f.id === it.fid); if (!rf) return { v: 'check' as Verdict, title: '시설 없음' }; const q = { proof: proof as ProofQ, payee: it.payee, vat_sep: vatSep, use: it.use, what: it.what, asset: ASSET_WHAT.has(it.what) && it.asset, late: false }; const m = toInput(D, org!, rf, q); const o: Out = m.override ?? judge(D, m.input); return { v: o.v, title: o.title }; };
  const vcell = (it: Item) => `<span class="sig ${it.v}" aria-hidden="true"></span><span class="sr-only">${VSHAPE[it.v]}</span> ${LABEL[it.v]}${it.v === 'no' || it.v === 'check' ? `<br><span class="note">${esc(it.title)}</span>` : ''}`;
  function buildPreview() {
    if (!org || !fac) return; const rowsRaw = grid.slice(hasHeader ? 1 : 0); const reg = (org.unit === 'entity' ? org.reg_no : fac.reg_no)?.replace(/\D/g, '') ?? '';
    const proof = mbVal('mb-proof'); const batchPayee = mbVal('mb-payee'); const vatSep = mbVal('mb-vatsep') !== '0'; const evidDefault = (mbVal('mb-evid') || 'contract') as Evid;
    const existing = new Map<string, LedgerRow[]>(); const exist = (fid: string) => { let l = existing.get(fid); if (!l) { l = getLedger(fid, month); existing.set(fid, l); } return l; };
    const keep = new Map(items.map(it => [it.rawDate + '|' + it.desc + '|' + it.amt, it]));   // 열을 고쳐 다시 그려도 담당자가 고른 시설·어디에·무엇은 남긴다
    items = rowsRaw.map(r => { const g = (k: string) => map[k] === undefined ? '' : (r[map[k]] ?? ''); let amt = num(g('amt')), tax = num(g('tax')); const total = num(g('total')); if (!amt && total) { amt = Math.round(total / 1.1); tax = total - amt; } if (amt && !tax && map.tax === undefined) tax = Math.floor(amt * 0.1);
      const desc = [g('supplier'), g('desc')].filter(Boolean).join(' · ') || '(내용 없음)'; const preg = g('payee_reg').replace(/\D/g, ''); const sup = g('supplier'), sreg = g('supplier_reg').replace(/\D/g, '');
      const payee = (proof === 'e_invoice' ? (preg ? (reg && preg === reg ? 'org' : 'contractor') : batchPayee) : 'org') as PayeeQ;
      const rawDate = g('date'); const d = (rawDate.match(/(\d{4})[.\-/]?(\d{2})[.\-/]?(\d{2})/) ?? []); const date = d.length ? `${d[1]}-${d[2]}-${d[3]}` : `${month}-01`;
      const biz = g('biz').trim(), dept = g('dept').trim(); const mapped = matchMap(org!, biz, dept); const prev = keep.get(rawDate + '|' + desc + '|' + amt);
      const it: Item = { date, rawDate, desc, amt, tax, payee, sup, sreg, what: prev?.what ?? guessWhat(desc), asset: prev?.asset ?? false, use: prev?.use ?? mapped?.use ?? 'this', evid: prev?.evid ?? evidDefault, fid: prev?.fid ?? mapped?.fid ?? fac!.id, auto: !!mapped && !prev, biz, dept, on: true, flags: [], v: 'check', title: '' };
      if (!(amt > 0 || tax > 0)) { it.flags.push('금액 없음'); it.on = false; } if (!d.length) it.flags.push(`날짜 확인(${month}-01로 둠)`);
      if (exist(it.fid).some(x => x.d === date && x.amt === amt && x.tax === tax && (x.sup ? x.sup === sup : x.desc === desc))) { it.flags.push('중복 가능'); it.on = false; }
      Object.assign(it, judgeItem(it, proof, vatSep)); return it; });
    const nAuto = items.filter(it => it.auto).length, nPend = items.length - nAuto, nFlag = items.filter(it => it.flags.length).length; if (!nAuto && mbView === 'auto') mbView = 'all'; if (!nAuto) mbView = mbView === 'pending' ? 'all' : mbView;
    const ncol = Math.max(...grid.map(r => r.length)); const names = Array.from({ length: ncol }, (_, i) => hasHeader ? (grid[0][i] || `열 ${i + 1}`) : `열 ${i + 1}`);
    const colSel = (k: string, label: string) => `<select class="colsel" data-col="${k}" aria-label="원본 열: ${label}"><option value="">${esc(label)}: 없음</option>${names.map((n, i) => `<option value="${i}" ${map[k] === i ? 'selected' : ''}>${esc(label)} ← ${esc(n)}</option>`).join('')}</select>`;
    const facOpts = (sel: string) => org!.facilities.map(f => `<option value="${f.id}" ${f.id === sel ? 'selected' : ''}>${esc(f.name)}</option>`).join('');
    const opt = (o: { key: string; name: string }[], sel: string) => o.map(x => `<option value="${x.key}" ${x.key === sel ? 'selected' : ''}>${esc(x.name.split('(')[0])}</option>`).join('');
    const show = (it: Item) => mbView === 'all' || (mbView === 'pending' ? !it.auto : it.auto);
    $('mb-preview')!.innerHTML = `<p class="note">판정은 참고이며 기관의 판단이 아닙니다. 열 머리의 선택 상자로 원본 열을 바로잡으면 표가 다시 그려집니다(고른 시설·어디에·무엇은 남습니다).</p>
      <div class="filters" role="group" aria-label="보기"><button type="button" class="chip" data-view="pending" aria-pressed="${mbView === 'pending'}">미확정만 <b>${nPend}</b></button><button type="button" class="chip" data-view="auto" aria-pressed="${mbView === 'auto'}" ${nAuto ? '' : 'disabled'}>매핑표로 자동 귀속 <b>${nAuto}</b></button><button type="button" class="chip" data-view="all" aria-pressed="${mbView === 'all'}">전체 <b>${items.length}</b></button><span class="note" id="mb-status" role="status">${items.length}행 읽음${nAuto ? ` · 자동 ${nAuto}` : ''}${nFlag ? ` · 확인할 행 ${nFlag}(금액 없음·날짜·중복 가능은 체크를 풀어 두었습니다)` : ''}</span></div>
      <div class="bulk vc-form"><span class="q-title full" style="font-size:var(--small)">선택한 행에 한꺼번에 — 비워 둔 것은 바꾸지 않습니다</span>
        <label>시설 <select data-mbk="fid"><option value="">— 그대로 —</option>${facOpts('')}</select></label><label>어디에 썼나 <select data-mbk="use"><option value="">— 그대로 —</option>${opt(USE_Q, '')}</select></label><label>무엇 <select data-mbk="what"><option value="">— 그대로 —</option>${opt(WHAT_Q, '')}</select></label><label>근거 <select data-mbk="evid"><option value="">— 그대로 —</option>${opt(EVID_Q, '')}</select></label>
        <div class="actions"><button type="button" class="btn secondary" data-mbulk>선택 행에 적용</button></div></div>
      <div class="scroll-x" tabindex="0" role="region" aria-label="붙여넣은 지출 미리보기"><table class="data-table vat-table vat-grid" id="mb-table" data-stack="off"><caption>붙여넣은 ${items.length}건 — 행마다 시설·어디에·무엇을 확인하고 넣기 (Ctrl+Enter = 넣기)</caption>
      <thead><tr><th scope="col"><input type="checkbox" data-on-all aria-label="보이는 행 모두 선택" /></th><th scope="col">날짜</th><th scope="col">내용</th><th scope="col">사업·부서</th><th scope="col">시설</th><th scope="col">공급가액</th><th scope="col">부가세</th><th scope="col">받는 사람</th><th scope="col">어디에 썼나</th><th scope="col">무엇</th><th scope="col">근거</th><th scope="col">여러 해</th><th scope="col">판정(미리)</th></tr>
      <tr class="colmap"><th scope="row"><span class="sr-only">원본 열</span></th><td>${colSel('date', '날짜')}</td><td>${colSel('supplier', '공급자')}${colSel('desc', '품목·내용')}</td><td>${colSel('biz', '사업명')}${colSel('dept', '부서')}</td><td></td><td>${colSel('amt', '공급가액')}${colSel('total', '합계')}</td><td>${colSel('tax', '세액')}</td><td>${colSel('payee_reg', '공급받는자 등록번호')}${colSel('supplier_reg', '공급자 등록번호')}</td><td colspan="5" class="note">← 열이 틀리면 여기서 고릅니다</td></tr></thead>
      <tbody>${items.map((it, i) => `<tr data-i="${i}" class="v-${it.v}${it.auto ? ' auto' : ''}" ${show(it) ? '' : 'hidden'}><td><input type="checkbox" data-on ${it.on ? 'checked' : ''} aria-label="${i + 1}행 넣기" /></td><td>${it.date}</td><td>${esc(it.desc)}${it.flags.map(f => ` <span class="verdict check">${esc(f)}</span>`).join('')}</td><td class="note">${esc([it.biz, it.dept].filter(Boolean).join(' / '))}</td><td><select data-fac aria-label="시설">${facOpts(it.fid)}</select>${it.auto ? ' <span class="vbadge">자동</span>' : ''}</td><td>${it.amt ? fmt(it.amt) : ''}</td><td>${it.tax ? fmt(it.tax) : ''}</td><td>${it.payee === 'org' ? '우리 기관' : it.payee === 'contractor' ? '<span class="verdict no">다른 명의</span>' : '<span class="verdict check">모름</span>'}</td><td><select data-use aria-label="어디에 썼나">${opt(USE_Q, it.use)}</select></td><td><select data-what aria-label="무엇">${opt(WHAT_Q, it.what)}</select></td><td><select data-evid aria-label="전용 근거" ${it.use === 'this' ? '' : 'disabled'}>${opt(EVID_Q, it.evid)}</select></td><td><input type="checkbox" data-asset ${it.asset ? 'checked' : ''} aria-label="여러 해 쓰는 것" ${ASSET_WHAT.has(it.what) ? '' : 'disabled'} /></td><td class="keep" data-v>${vcell(it)}</td></tr>`).join('')}</tbody></table></div>
      <div class="actions"><button type="button" class="btn" id="mb-add">체크한 행을 기록에 넣기</button><span class="meta">넣은 뒤 10초 안에 되돌릴 수 있습니다. 같은 영수증을 두 번 넣지 않게 '중복 가능' 행을 확인하세요.</span></div>`;
    const tbl = $<HTMLTableElement>('mb-table')!; gridKeys(tbl);
    tbl.querySelectorAll<HTMLSelectElement>('select.colsel').forEach(sel => sel.addEventListener('change', () => { map = {}; tbl.querySelectorAll<HTMLSelectElement>('select.colsel').forEach(x => { if (x.value !== '') map[x.dataset.col!] = Number(x.value); }); buildPreview(); }));
    $('mb-preview')!.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(b => b.addEventListener('click', () => { mbView = b.dataset.view as typeof mbView; $('mb-preview')!.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(x => x.setAttribute('aria-pressed', String(x === b))); tbl.querySelectorAll<HTMLTableRowElement>('tbody tr').forEach(tr => { tr.hidden = !show(items[Number(tr.dataset.i)]); }); }));
    const visRows = () => [...tbl.querySelectorAll<HTMLTableRowElement>('tbody tr')].filter(tr => !tr.hidden);
    tbl.querySelector<HTMLInputElement>('[data-on-all]')?.addEventListener('change', e => { const on = (e.target as HTMLInputElement).checked; visRows().forEach(tr => { tr.querySelector<HTMLInputElement>('[data-on]')!.checked = on && !items[Number(tr.dataset.i)].flags.length; }); });   // 모두 선택은 확인할 행(금액 없음·날짜·중복 가능)을 건너뛴다 — 그 행은 직접 체크
    /* 행의 선택이 바뀌면 그 행만 다시 판정 */
    const readRow = (tr: HTMLTableRowElement) => { const it = items[Number(tr.dataset.i)]; it.fid = tr.querySelector<HTMLSelectElement>('[data-fac]')!.value; it.use = tr.querySelector<HTMLSelectElement>('[data-use]')!.value as UseQ; it.what = tr.querySelector<HTMLSelectElement>('[data-what]')!.value; it.evid = tr.querySelector<HTMLSelectElement>('[data-evid]')!.value as Evid; it.asset = tr.querySelector<HTMLInputElement>('[data-asset]')!.checked; tr.querySelector<HTMLSelectElement>('[data-evid]')!.disabled = it.use !== 'this'; tr.querySelector<HTMLInputElement>('[data-asset]')!.disabled = !ASSET_WHAT.has(it.what); Object.assign(it, judgeItem(it, proof, vatSep)); tr.className = `v-${it.v}${it.auto ? ' auto' : ''}`; tr.querySelector('[data-v]')!.innerHTML = vcell(it); return it; };
    tbl.querySelectorAll<HTMLTableRowElement>('tbody tr').forEach(tr => tr.addEventListener('change', e => { if ((e.target as HTMLElement).matches('[data-on]')) return; readRow(tr); }));
    $('mb-preview')!.querySelector<HTMLButtonElement>('[data-mbulk]')?.addEventListener('click', () => { const rows = visRows().filter(tr => tr.querySelector<HTMLInputElement>('[data-on]')!.checked); const st = $('mb-status')!; if (!rows.length) { st.textContent = '선택한 행이 없습니다 — 왼쪽 체크 상자로 고르세요'; return; } const g = (k: string) => $('mb-preview')!.querySelector<HTMLSelectElement>(`[data-mbk=${k}]`)!.value; const fid = g('fid'), use = g('use'), what = g('what'), evid = g('evid'); if (!fid && !use && !what && !evid) { st.textContent = '바꿀 값을 하나 이상 고르세요'; return; }
      for (const tr of rows) { if (fid) tr.querySelector<HTMLSelectElement>('[data-fac]')!.value = fid; if (use) tr.querySelector<HTMLSelectElement>('[data-use]')!.value = use; if (what) tr.querySelector<HTMLSelectElement>('[data-what]')!.value = what; if (evid) tr.querySelector<HTMLSelectElement>('[data-evid]')!.value = evid; readRow(tr); } st.textContent = `${rows.length}행에 적용했습니다`; });
    $('mb-preview')!.addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $('mb-add')?.click(); } });   // 미리보기 영역 어디서든 Ctrl+Enter = 넣기
    $('mb-add')!.addEventListener('click', () => {
      if (!org || !fac) return; const leds = new Map<string, LedgerRow[]>(); const ledOf = (fid: string) => { let l = leds.get(fid); if (!l) { l = getLedger(fid, month); leds.set(fid, l); } return l; }; let n = 0, learned = 0; const perFac = new Map<string, number>(); const added: { fid: string; ids: string[] }[] = []; const mapSnap = JSON.stringify(org.map ?? []);
      tbl.querySelectorAll<HTMLTableRowElement>('tbody tr').forEach(tr => { if (!tr.querySelector<HTMLInputElement>('[data-on]')!.checked) return; const it = readRow(tr); const use = it.use, what = it.what, asset = ASSET_WHAT.has(what) && it.asset;
        const fid = it.fid; const rf = org!.facilities.find(f => f.id === fid); if (!rf) return; const led = ledOf(fid); const evid = it.evid;
        if (it.biz || it.dept) { if (learnMap(org!, it.biz || it.dept, fid, use)) learned++; }
        const q = { proof: proof as ProofQ, payee: it.payee as PayeeQ, vat_sep: vatSep, use, what, asset, late: false }; const m = toInput(D, org!, rf, q); const o: Out = m.override ?? judge(D, m.input); if (m.note) o.why.push(m.note);
        const fd = m.input.proof === 'tax_invoice_other' && o.v === 'no' ? fixDue(it.date) : null; if (fd) o.todo.unshift(`수정세금계산서 기한 ${fd.due}(${fd.days >= 0 ? `D-${fd.days}` : `${-fd.days}일 지남`}).`);
        const id = uid(); led.push({ id, d: it.date, desc: it.desc, amt: it.amt, tax: o.v === 'none' ? 0 : it.tax, proof: q.proof, payee: q.payee, vat_sep: vatSep, use, what, asset, late: false, fix_due: fd?.due, sup: it.sup || undefined, sreg: it.sreg || undefined, evid: use === 'this' ? evid : undefined, biz: [it.biz, it.dept].filter(Boolean).join(' / ') || undefined, v: o.v, title: o.title, todo: o.todo[0] || '', basis: uniq(o.basis).map(lawText).join(', '), done: false }); n++; perFac.set(rf.name, (perFac.get(rf.name) ?? 0) + 1); let a = added.find(x => x.fid === fid); if (!a) { a = { fid, ids: [] }; added.push(a); } a.ids.push(id); });
      if (!n) { $('mb-status')!.textContent = '체크한 행이 없습니다'; return; }
      for (const [fid, led] of leds) setLedger(fid, month, led); if (learned) setOrg(org); renderRules(); renderList(); $('mb-preview')!.innerHTML = `<p class="callout ok" role="status">${n}건을 ${month} 기록에 넣었습니다 — ${[...perFac.entries()].map(([k, v]) => `${esc(k)} ${v}건`).join(', ')}${learned ? ` · 매핑표에 ${learned}줄 기억` : ''}. 아래 '이 달 기록' 표에서 신호등을 확인하세요.</p>`; $<HTMLTextAreaElement>('mb-text')!.value = ''; grid = []; items = []; scrollTo($('m-list'));
      const m0 = month; toast(`${n}건을 ${m0} 기록에 넣었습니다`, { fn: () => { for (const a of added) { const l = getLedger(a.fid, m0).filter(r => !a.ids.includes(r.id)); setLedger(a.fid, m0, l); } if (org) { org.map = JSON.parse(mapSnap); setOrg(org); renderRules(); } renderList(); } });
    });
  }
  /** 사업·부서 → 시설 매핑표(org.map): 붙여넣기 때 담당자가 고른 시설을 기억해 다음부터 자동 귀속 */
  function renderRules() {
    const box = $('mb-rules'); if (!box || !org) return; const rules = org.map ?? []; $('mb-rules-n')!.textContent = rules.length ? `${rules.length}줄` : '아직 없음';
    box.innerHTML = rules.length ? `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table compact" data-stack="off"><caption>사업·부서 글자 → 시설 (${rules.length}줄)</caption><thead><tr><th scope="col">사업명·부서 글자</th><th scope="col">시설</th><th scope="col">어디에</th><th scope="col" class="no-print">지우기</th></tr></thead><tbody>${rules.map((r, i) => `<tr><th scope="row">${esc(r.pat)}</th><td>${esc(org!.facilities.find(f => f.id === r.fid)?.name ?? '(없는 시설)')}</td><td>${esc(name(USE_Q, r.use ?? 'this'))}</td><td class="no-print"><button type="button" class="link-btn" data-rule-del="${i}">지우기</button></td></tr>`).join('')}</tbody></table></div>` : '<p class="meta">붙여넣은 표에 사업명·부서 열이 있고 행마다 시설을 골라 넣으면 여기 쌓입니다.</p>';
    box.querySelectorAll<HTMLButtonElement>('[data-rule-del]').forEach(b => b.addEventListener('click', () => { org!.map!.splice(Number(b.dataset.ruleDel), 1); setOrg(org); renderRules(); }));
  }
  renderRules();
  const origPick = pick; // 시설을 고르면 대량 입력도 열린다
  facSel.addEventListener('change', () => { mbWrap.hidden = !fac; }); monthIn.addEventListener('change', () => { mbWrap.hidden = !fac; });
  void origPick;
  renderOrg(); mbWrap.hidden = !fac;
}
