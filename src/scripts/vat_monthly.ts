/** /vat/monthly/ 시설 지출 기록 → 매입 인계표(수탁기관·시설 부서). 판정은 vat_rules.judge(공용), 질문은 현장 말. localStorage 저장, 서버 없음. */
import { $, esc, num, fmt, loadData, judge, toInput, getOrg, setOrg, getLedger, setLedger, readJsonFile, downloadText, toCsv, facilityStatus, STATUS_WORD, RUN_NAME, PROOF_Q, PAYEE_Q, USE_Q, WHAT_Q, ASSET_WHAT, SIGNAL, LABEL, lawLink, lawText, uniq, uid, ymd, monthStr, periodOf, nextFiling, handoverDue, type Data, type Org, type OrgFacility, type LedgerRow, type ProofQ, type PayeeQ, type UseQ, type Out } from './vat_rules';
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
    form.hidden = s === 'own'; if (s === 'own') note.innerHTML += '<br>이 시설의 지출은 수탁기관 장부에 적습니다. 설정이 틀렸으면 신고 담당에게 알리세요.';
    renderList();
  }
  facSel.addEventListener('change', pick); monthIn.addEventListener('change', pick);
  $<HTMLInputElement>('m-open')?.addEventListener('change', async e => { const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return; try { const o = await readJsonFile(f) as Org; if (!o || o.v !== 1 || !Array.isArray(o.facilities)) throw new Error(); org = o; setOrg(o); renderOrg(); } catch { $('m-org-state')!.textContent = '기관 설정 파일(org.json)이 아닙니다.'; } });

  /* 판정·기록 */
  form.addEventListener('submit', e => {
    e.preventDefault(); if (!org || !fac) return;
    const q = { proof: val('m-proof') as ProofQ, payee: (($('m-payee-q') as HTMLElement).hidden ? 'org' : val('m-payee')) as PayeeQ, vat_sep: val('m-vatsep') === '1', use: val('m-use') as UseQ, what: val('m-what'), asset: ASSET_WHAT.has(val('m-what')) && ($<HTMLInputElement>('m-asset')!).checked, late: ($<HTMLInputElement>('m-late')!).checked };
    const m = toInput(D, org, fac, q); const o: Out = m.override ?? judge(D, m.input); if (m.note) o.why.push(m.note);
    const amt = num($<HTMLInputElement>('m-amt')!.value); let tax = num($<HTMLInputElement>('m-tax')!.value); if (!tax && amt && o.v !== 'none') tax = Math.floor(amt * 0.1);
    const row: LedgerRow = { id: uid(), d: $<HTMLInputElement>('m-d')!.value || ymd(new Date()), desc: $<HTMLInputElement>('m-desc')!.value.trim() || '(내용 없음)', amt, tax, proof: q.proof, payee: q.payee, vat_sep: q.vat_sep, use: q.use, what: q.what, asset: q.asset, late: q.late, v: o.v, title: o.title, todo: o.todo[0] || '', basis: uniq(o.basis).map(lawText).join(', '), done: false };
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
    tb.innerHTML = rows.map(r => `<tr class="v-${r.v}${r.done ? ' done' : ''}" data-id="${r.id}"><td>${r.d}</td><td>${esc(r.desc)}</td><td>${r.amt ? fmt(r.amt) : ''}</td><td>${r.tax ? fmt(r.tax) : ''}</td><td>${esc(name(PROOF_Q, r.proof))}</td><td>${esc(name(PAYEE_Q, r.payee))}</td><td>${esc(name(USE_Q, r.use))}</td><td>${esc(name(WHAT_Q, r.what))}${r.asset ? ' · 여러 해 씀' : ''}${r.late ? ' · 지연' : ''}</td><td class="keep"><span class="sig ${r.v}"></span>${LABEL[r.v]}</td><td class="note">${esc(r.todo)}</td><td class="note">${esc(r.basis)}</td><td class="no-print keep"><label><input type="checkbox" data-done ${r.done ? 'checked' : ''}/> 처리</label> <button type="button" class="link-btn" data-del>삭제</button></td></tr>`).join('');
    const n = (v: string) => rows.filter(r => r.v === v).length; const t = (v: string) => rows.filter(r => r.v === v).reduce((s, r) => s + r.tax, 0);
    $('m-sum')!.textContent = `${rows.length}건 · 초록 ${n('ok')}건 ${fmt(t('ok'))}원 · 파랑 ${n('split')}건 ${fmt(t('split'))}원 · 빨강 ${n('no')}건 · 노랑 ${n('check')}건 · 회색 ${n('none')}건 — 미처리 빨강·노랑 ${rows.filter(r => (r.v === 'no' || r.v === 'check') && !r.done).length}건`;
    tb.querySelectorAll<HTMLInputElement>('[data-done]').forEach(c => c.addEventListener('change', () => { const r = rows.find(x => x.id === c.closest('tr')!.getAttribute('data-id'))!; r.done = c.checked; setLedger(fac!.id, month, rows); renderList(); }));
    tb.querySelectorAll<HTMLButtonElement>('[data-del]').forEach(b => b.addEventListener('click', () => { const id = b.closest('tr')!.getAttribute('data-id'); setLedger(fac!.id, month, rows.filter(x => x.id !== id)); renderList(); }));
  }
  const header = ['기관', '시설', '달', '날짜', '내용', '공급가액', '부가세', '영수증', '받는 사람', '어디에 썼나', '무엇', '여러 해 씀', '지연 수취', '판정', '지금 할 일', '근거', '처리'];
  $('m-csv')?.addEventListener('click', () => { if (!fac || !org) return; const rows = getLedger(fac.id, month); downloadText(`매입인계표-${org.org}-${fac.name}-${month}.csv`, toCsv([header, ...rows.map(r => [org!.org, fac!.name, month, r.d, r.desc, r.amt, r.tax, name(PROOF_Q, r.proof), name(PAYEE_Q, r.payee), name(USE_Q, r.use), name(WHAT_Q, r.what), r.asset ? '예' : '', r.late ? '예' : '', LABEL[r.v], r.todo, r.basis, r.done ? '처리' : ''])]), 'text/csv;charset=utf-8'); });
  $('m-json')?.addEventListener('click', () => { if (!fac || !org) return; downloadText(`ledger-${org.org}-${fac.name}-${month}.json`, JSON.stringify({ v: 1, org: org.org, facility: fac.id, facility_name: fac.name, type: fac.type, month, period: periodOf(month), exported: ymd(new Date()), rows: getLedger(fac.id, month) }, null, 2), 'application/json'); });
  $('m-print')?.addEventListener('click', () => window.print());
  $('m-clear')?.addEventListener('click', () => { if (fac && confirm(`${fac.name} ${month} 기록 ${getLedger(fac.id, month).length}건을 지웁니다.`)) { setLedger(fac.id, month, []); renderList(); res.innerHTML = ''; } });
  renderOrg();
}
