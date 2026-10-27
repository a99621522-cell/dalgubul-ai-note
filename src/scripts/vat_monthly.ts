/** /vat/monthly/ 시설 지출 기록 → 매입 인계표(수탁기관·시설 부서). 판정은 vat_rules.judge(공용), 질문은 현장 말. localStorage 저장, 서버 없음. */
import { $, esc, num, fmt, loadData, judge, toInput, fixDue, FEE_NAME, parseTable, guessColumns, COL_GUESS, guessWhat, getOrg, setOrg, getLedger, setLedger, readJsonFile, downloadText, toCsv, facilityStatus, STATUS_WORD, RUN_NAME, PROOF_Q, PAYEE_Q, USE_Q, WHAT_Q, ASSET_WHAT, SIGNAL, LABEL, lawLink, lawText, uniq, uid, ymd, monthStr, periodOf, nextFiling, handoverDue, type Data, type Org, type OrgFacility, type LedgerRow, type ProofQ, type PayeeQ, type UseQ, type Out } from './vat_rules';
const D = loadData();
if (D) init(D);
function init(D: Data) {
  let org: Org | null = getOrg(); let fac: OrgFacility | null = null; let month = monthStr();
  const facSel = $<HTMLSelectElement>('m-fac')!, monthIn = $<HTMLInputElement>('m-month')!, form = $<HTMLFormElement>('m-form')!, res = $('m-result')!;
  monthIn.value = month; ($<HTMLInputElement>('m-d')!).value = ymd(new Date());
  const f0 = nextFiling(); $('m-dday')!.textContent = `다음 신고 ${f0.name} D-${f0.days}` + (org ? ` · 인계표 마감 D-${handoverDue(org.handover_day || 5).days}` : '');
  const chips = (id: string, name: string, opts: { key: string; name: string }[], first = true) => { $(id)!.innerHTML = opts.map((o, i) => `<label><input type="radio" name="${name}" value="${o.key}" ${first && i === 0 ? 'checked' : ''}/> ${esc(o.name)}</label>`).join(''); };
  chips('m-proof', 'm-proof', PROOF_Q); chips('m-payee', 'm-payee', PAYEE_Q); chips('m-use', 'm-use', USE_Q); chips('m-what', 'm-what', WHAT_Q);
  const val = (name: string) => (document.querySelector<HTMLInputElement>(`input[name=${name}]:checked`)?.value ?? '');
  const syncQ = () => { const p = val('m-proof'); const card = p === 'card' || p === 'cash'; $('m-vat-q')!.hidden = !card; $('m-payee-q')!.hidden = p === 'bill' || p === 'none'; $('m-asset-q')!.hidden = !ASSET_WHAT.has(val('m-what')); };
  form.addEventListener('change', syncQ); syncQ();

  function renderOrg() {
    const st = $('m-org-state')!;
    if (!org) { st.innerHTML = '이 브라우저에 기관 설정이 없습니다. 아래에서 파일을 여세요.'; facSel.innerHTML = '<option value="">— 기관 설정을 먼저 여세요 —</option>'; form.hidden = true; return; }
    st.innerHTML = `<strong>${esc(org.org)}</strong> · ${esc(org.dept || '')} · 시설 ${org.facilities.length}곳 · 인계표 매달 ${org.handover_day}일까지 · 설정 ${org.created}`;
    facSel.innerHTML = '<option value="">— 시설을 고르세요 —</option>' + org.facilities.map(f => { const s = facilityStatus(D, f); return `<option value="${f.id}">${esc(f.name)} (${s === 'taxable' ? '과세' : s === 'exempt' ? '면세' : s === 'own' ? '수탁기관 신고' : '확인 필요'})</option>`; }).join('');
    const last = sessionStorage.getItem('vat-fac'); if (last && org.facilities.some(f => f.id === last)) { facSel.value = last; pick(); }
  }
  function pick() {
    fac = org?.facilities.find(f => f.id === facSel.value) ?? null; month = monthIn.value || monthStr();
    const note = $('m-facnote')!;
    if (!fac) { form.hidden = true; $('m-list')!.hidden = true; note.textContent = ''; return; }
    sessionStorage.setItem('vat-fac', fac.id);
    const s = facilityStatus(D, fac); const reg = org!.unit === 'entity' ? org!.reg_no : fac.reg_no;
    note.innerHTML = `<span class="verdict ${s}">${STATUS_WORD[s]}</span> · ${esc(RUN_NAME[fac.run])}${reg ? ` · 영수증 받을 번호 <strong>${esc(reg)}</strong>` : ''} · ${periodOf(month)}신고 대상 달`;
    form.hidden = false; if (s === 'own') note.innerHTML += `<br>수탁기관이 쓴 돈은 수탁기관 장부에 적습니다. <strong>${esc(org!.org)}가 이 시설에 직접 낸 돈(수선·장비·공사)</strong>만 여기에 넣으세요 — ${esc(org!.org)}가 수탁기관에게 받는 것: ${esc(FEE_NAME[fac.fee ?? 'unknown'])}.`;
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
    const row: LedgerRow = { id: uid(), d: $<HTMLInputElement>('m-d')!.value || ymd(new Date()), desc: $<HTMLInputElement>('m-desc')!.value.trim() || '(내용 없음)', amt, tax, proof: q.proof, payee: q.payee, vat_sep: q.vat_sep, use: q.use, what: q.what, asset: q.asset, late: q.late, subsidy: q.subsidy, fix_due: fd?.due, v: o.v, title: o.title, todo: o.todo[0] || '', basis: uniq(o.basis).map(lawText).join(', '), done: false };
    const rows = getLedger(fac.id, month); rows.push(row); setLedger(fac.id, month, rows);
    res.innerHTML = `<div class="vc-card"><h3><span class="sig ${o.v}"></span>${esc(SIGNAL[o.v])}<span class="verdict ${o.v}">${LABEL[o.v]}</span></h3><p><strong>${esc(o.title)}</strong> — ${esc(row.desc)}${tax ? ` · 부가세 ${fmt(tax)}원` : ''}</p>
      <p class="label">왜</p><ul>${o.why.map(w => `<li>${esc(w)}</li>`).join('')}</ul>${o.todo.length ? `<p class="label">지금 할 일</p><ul>${o.todo.map(w => `<li>${esc(w)}</li>`).join('')}</ul>` : ''}
      <p class="label">근거 조문</p><p class="meta">${uniq(o.basis).map(b => lawLink(D, b)).join(' · ')}</p><p class="meta">기록에 넣었습니다. 아래 표에서 확인하세요.</p></div>`;
    renderList(); ($<HTMLInputElement>('m-desc')!).value = ''; ($<HTMLInputElement>('m-amt')!).value = ''; ($<HTMLInputElement>('m-tax')!).value = ''; ($<HTMLInputElement>('m-desc')!).focus();
  });
  const name = (opts: { key: string; name: string }[], k: string) => opts.find(o => o.key === k)?.name.split('(')[0].trim() ?? k;
  function renderList() {
    if (!fac) return; const rows = getLedger(fac.id, month); const list = $('m-list')!; list.hidden = !rows.length; if (!rows.length) return;
    $('m-list-title')!.textContent = `${fac.name} · ${month.replace('-', '년 ')}월 기록`; $('m-caption')!.textContent = `매입 인계표 — ${org!.org} ${fac.name} ${month.replace('-', '년 ')}월 (${periodOf(month)}신고 대상, 참고용 판정)`;
    const tb = $<HTMLTableElement>('m-table')!.tBodies[0];
    tb.innerHTML = rows.map(r => `<tr class="v-${r.v}${r.done ? ' done' : ''}" data-id="${r.id}"><td>${r.d}</td><td>${esc(r.desc)}</td><td>${r.amt ? fmt(r.amt) : ''}</td><td>${r.tax ? fmt(r.tax) : ''}</td><td>${esc(name(PROOF_Q, r.proof))}</td><td>${esc(name(PAYEE_Q, r.payee))}</td><td>${esc(name(USE_Q, r.use))}</td><td>${esc(name(WHAT_Q, r.what))}${r.asset ? ' · 여러 해 씀' : ''}${r.late ? ' · 지연' : ''}${r.subsidy ? ' · 보조금' : ''}</td><td class="keep"><span class="sig ${r.v}"></span>${LABEL[r.v]}</td><td class="note">${esc(r.todo)}</td><td class="note">${esc(r.basis)}</td><td class="no-print keep"><label><input type="checkbox" data-done ${r.done ? 'checked' : ''}/> 처리</label> <button type="button" class="link-btn" data-del>삭제</button></td></tr>`).join('');
    const n = (v: string) => rows.filter(r => r.v === v).length; const t = (v: string) => rows.filter(r => r.v === v).reduce((s, r) => s + r.tax, 0);
    $('m-sum')!.textContent = `${rows.length}건 · 초록 ${n('ok')}건 ${fmt(t('ok'))}원 · 파랑 ${n('split')}건 ${fmt(t('split'))}원 · 빨강 ${n('no')}건 · 노랑 ${n('check')}건 · 회색 ${n('none')}건 — 미처리 빨강·노랑 ${rows.filter(r => (r.v === 'no' || r.v === 'check') && !r.done).length}건`;
    tb.querySelectorAll<HTMLInputElement>('[data-done]').forEach(c => c.addEventListener('change', () => { const r = rows.find(x => x.id === c.closest('tr')!.getAttribute('data-id'))!; r.done = c.checked; setLedger(fac!.id, month, rows); renderList(); }));
    tb.querySelectorAll<HTMLButtonElement>('[data-del]').forEach(b => b.addEventListener('click', () => { const id = b.closest('tr')!.getAttribute('data-id'); setLedger(fac!.id, month, rows.filter(x => x.id !== id)); renderList(); }));
  }
  const header = ['기관', '시설', '달', '날짜', '내용', '공급가액', '부가세', '영수증', '받는 사람', '어디에 썼나', '무엇', '여러 해 씀', '지연 수취', '보조금', '수정세금계산서 기한', '판정', '지금 할 일', '근거', '처리'];
  $('m-csv')?.addEventListener('click', () => { if (!fac || !org) return; const rows = getLedger(fac.id, month); downloadText(`매입인계표-${org.org}-${fac.name}-${month}.csv`, toCsv([header, ...rows.map(r => [org!.org, fac!.name, month, r.d, r.desc, r.amt, r.tax, name(PROOF_Q, r.proof), name(PAYEE_Q, r.payee), name(USE_Q, r.use), name(WHAT_Q, r.what), r.asset ? '예' : '', r.late ? '예' : '', r.subsidy ? '예' : '', r.fix_due ?? '', LABEL[r.v], r.todo, r.basis, r.done ? '처리' : ''])]), 'text/csv;charset=utf-8'); });
  $('m-json')?.addEventListener('click', () => { if (!fac || !org) return; downloadText(`ledger-${org.org}-${fac.name}-${month}.json`, JSON.stringify({ v: 1, org: org.org, facility: fac.id, facility_name: fac.name, type: fac.type, month, period: periodOf(month), exported: ymd(new Date()), rows: getLedger(fac.id, month) }, null, 2), 'application/json'); });
  $('m-print')?.addEventListener('click', () => window.print());
  $('m-clear')?.addEventListener('click', () => { if (fac && confirm(`${fac.name} ${month} 기록 ${getLedger(fac.id, month).length}건을 지웁니다.`)) { setLedger(fac.id, month, []); renderList(); res.innerHTML = ''; } });
  /* ---------- 여러 건 한꺼번에(붙여넣기) ---------- */
  const mbWrap = $<HTMLDetailsElement>('mb-wrap')!; const mbForm = $<HTMLFormElement>('mb-form')!;
  const mbVal = (n: string) => document.querySelector<HTMLInputElement>(`input[name=${n}]:checked`)?.value ?? '';
  mbForm.addEventListener('change', () => { const card = mbVal('mb-proof') !== 'e_invoice'; $('mb-vat-q')!.hidden = !card; $('mb-payee-q')!.hidden = card; });
  let grid: string[][] = [], hasHeader = false, map: Record<string, number> = {};
  mbForm.addEventListener('submit', e => {
    e.preventDefault(); grid = parseTable($<HTMLTextAreaElement>('mb-text')!.value); if (!grid.length) { $('mb-map')!.innerHTML = '<p class="callout info">붙여넣은 글자가 없습니다.</p>'; return; }
    map = guessColumns(grid[0]); hasHeader = Object.keys(map).length >= 2; if (!hasHeader) map = {};
    const ncol = Math.max(...grid.map(r => r.length)); const names = Array.from({ length: ncol }, (_, i) => hasHeader ? (grid[0][i] || `열 ${i + 1}`) : `열 ${i + 1}`);
    $('mb-map')!.innerHTML = `<div class="vc-form"><p class="q-title full">열 맞추기 <span class="note">${hasHeader ? '머리글에서 짐작했습니다' : '머리글을 찾지 못해 열 번호로 고르세요'} · ${grid.length - (hasHeader ? 1 : 0)}행</span></p>${COL_GUESS.map(g => `<label>${g.name} <select data-col="${g.key}"><option value="">(없음)</option>${names.map((n, i) => `<option value="${i}" ${map[g.key] === i ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select></label>`).join('')}<div class="actions"><button type="button" class="btn" id="mb-build">미리보기</button></div></div>`;
    $('mb-build')!.addEventListener('click', buildPreview);
    buildPreview();
  });
  function buildPreview() {
    if (!org || !fac) return; map = {}; $('mb-map')!.querySelectorAll<HTMLSelectElement>('select[data-col]').forEach(s => { if (s.value !== '') map[s.dataset.col!] = Number(s.value); });
    const rows = grid.slice(hasHeader ? 1 : 0); const reg = (org.unit === 'entity' ? org.reg_no : fac.reg_no)?.replace(/\D/g, '') ?? '';
    const proof = mbVal('mb-proof'); const batchPayee = mbVal('mb-payee');
    const items = rows.map(r => { const g = (k: string) => map[k] === undefined ? '' : (r[map[k]] ?? ''); let amt = num(g('amt')), tax = num(g('tax')); const total = num(g('total')); if (!amt && total) { amt = Math.round(total / 1.1); tax = total - amt; } if (amt && !tax && map.tax === undefined) tax = Math.floor(amt * 0.1);
      const desc = [g('supplier'), g('desc')].filter(Boolean).join(' · ') || '(내용 없음)'; const preg = g('payee_reg').replace(/\D/g, '');
      const payee = proof === 'e_invoice' ? (preg ? (reg && preg === reg ? 'org' : 'contractor') : batchPayee) : 'org';
      const d = (g('date').match(/(\d{4})[.\-/]?(\d{2})[.\-/]?(\d{2})/) ?? []); const date = d.length ? `${d[1]}-${d[2]}-${d[3]}` : `${month}-01`;
      return { date, desc, amt, tax, payee, what: guessWhat(desc), asset: false, use: 'this', on: amt > 0 || tax > 0 }; });
    $('mb-preview')!.innerHTML = `<div class="scroll-x"><table class="data-table vat-table" id="mb-table" data-stack="off"><caption>붙여넣은 ${items.length}건 — 행마다 '어디에'와 '무엇'을 고르고 넣기</caption><thead><tr><th scope="col">넣기</th><th scope="col">날짜</th><th scope="col">내용</th><th scope="col">공급가액</th><th scope="col">부가세</th><th scope="col">받는 사람</th><th scope="col">어디에 썼나</th><th scope="col">무엇</th><th scope="col">여러 해 씀</th></tr></thead><tbody>${items.map((it, i) => `<tr data-i="${i}"><td><input type="checkbox" data-on ${it.on ? 'checked' : ''}/></td><td>${it.date}</td><td>${esc(it.desc)}</td><td>${it.amt ? fmt(it.amt) : ''}</td><td>${it.tax ? fmt(it.tax) : ''}</td><td>${it.payee === 'org' ? '우리 기관' : it.payee === 'contractor' ? '<span class="verdict no">다른 명의</span>' : '<span class="verdict check">모름</span>'}</td><td><select data-use>${USE_Q.map(o => `<option value="${o.key}">${o.name}</option>`).join('')}</select></td><td><select data-what>${WHAT_Q.map(o => `<option value="${o.key}" ${o.key === it.what ? 'selected' : ''}>${o.name.split('(')[0]}</option>`).join('')}</select></td><td><input type="checkbox" data-asset /></td></tr>`).join('')}</tbody></table></div>
      <div class="actions"><button type="button" class="btn" id="mb-add">체크한 행을 기록에 넣기</button><span class="meta">넣은 뒤 아래 '이 달 기록' 표에서 신호등을 확인합니다. 같은 영수증을 두 번 넣지 않게 주의하세요.</span></div>`;
    $('mb-add')!.addEventListener('click', () => {
      if (!org || !fac) return; const led = getLedger(fac.id, month); let n = 0; const vatSep = mbVal('mb-vatsep') !== '0';
      document.querySelectorAll<HTMLTableRowElement>('#mb-table tbody tr').forEach(tr => { if (!tr.querySelector<HTMLInputElement>('[data-on]')!.checked) return; const it = items[Number(tr.dataset.i)]; const use = tr.querySelector<HTMLSelectElement>('[data-use]')!.value as UseQ; const what = tr.querySelector<HTMLSelectElement>('[data-what]')!.value; const asset = ASSET_WHAT.has(what) && tr.querySelector<HTMLInputElement>('[data-asset]')!.checked;
        const q = { proof: proof as ProofQ, payee: it.payee as PayeeQ, vat_sep: vatSep, use, what, asset, late: false }; const m = toInput(D, org!, fac!, q); const o: Out = m.override ?? judge(D, m.input); if (m.note) o.why.push(m.note);
        const fd = m.input.proof === 'tax_invoice_other' && o.v === 'no' ? fixDue(it.date) : null; if (fd) o.todo.unshift(`수정세금계산서 기한 ${fd.due}(${fd.days >= 0 ? `D-${fd.days}` : `${-fd.days}일 지남`}).`);
        led.push({ id: uid(), d: it.date, desc: it.desc, amt: it.amt, tax: o.v === 'none' ? 0 : it.tax, proof: q.proof, payee: q.payee, vat_sep: vatSep, use, what, asset, late: false, fix_due: fd?.due, v: o.v, title: o.title, todo: o.todo[0] || '', basis: uniq(o.basis).map(lawText).join(', '), done: false }); n++; });
      setLedger(fac.id, month, led); renderList(); $('mb-preview')!.innerHTML = `<p class="callout ok">${n}건을 ${fac.name} ${month} 기록에 넣었습니다.</p>`; $<HTMLTextAreaElement>('mb-text')!.value = ''; $('m-list')!.scrollIntoView({ behavior: 'smooth' });
    });
  }
  const origPick = pick; // 시설을 고르면 대량 입력도 열린다
  facSel.addEventListener('change', () => { mbWrap.hidden = !fac; }); monthIn.addEventListener('change', () => { mbWrap.hidden = !fac; });
  void origPick;
  renderOrg(); mbWrap.hidden = !fac;
}
