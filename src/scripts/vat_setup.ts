/** /vat/setup/ 기관 설정 마법사(신고 담당). 5문항 → org.json + 시설 카드. localStorage 저장, 서버 없음, 개인정보 없음. */
import { $, esc, loadData, getOrg, setOrg, downloadText, readJsonFile, facilityRule, facilityStatus, STATUS_WORD, RUN_NAME, uid, ymd, type Data, type Org, type OrgFacility, type Run } from './vat_rules';
const D = loadData();
if (D) init(D);
function init(D: Data) {
  let org: Org = getOrg() ?? { v: 1, org: '', dept: '', unit: 'site', facilities: [], handover_day: 5, created: ymd(new Date()) };
  let step = 1;
  const steps = [...document.querySelectorAll<HTMLElement>('.step')];
  const chips = [...document.querySelectorAll<HTMLElement>('#st-steps span')];
  const show = (n: number) => { step = n; steps.forEach(s => { s.hidden = Number(s.dataset.step) !== n; }); chips.forEach((c, i) => { if (i + 1 === n) c.setAttribute('aria-current', 'step'); else c.removeAttribute('aria-current'); }); if (n === 3) renderFac(); if (n === 5) renderResult(); window.scrollTo({ top: 0, behavior: 'smooth' }); };
  const save = () => { org.created = ymd(new Date()); setOrg(org); };

  /* 1단계 */
  const unitRadios = [...document.querySelectorAll<HTMLInputElement>('input[name=st-unit]')];
  const regWrap = $('st-regno-wrap')!;
  const syncUnit = () => { const u = (unitRadios.find(r => r.checked)?.value ?? 'site') as Org['unit']; org.unit = u; regWrap.hidden = u !== 'entity'; };
  unitRadios.forEach(r => r.addEventListener('change', syncUnit));
  const fill1 = () => { ($<HTMLInputElement>('st-org')!).value = org.org; ($<HTMLInputElement>('st-dept')!).value = org.dept; unitRadios.forEach(r => { r.checked = r.value === org.unit; }); ($<HTMLInputElement>('st-regno')!).value = org.reg_no ?? ''; syncUnit(); ($<HTMLInputElement>('st-day')!).value = String(org.handover_day || 5); document.querySelectorAll<HTMLInputElement>('input[name=st-type]').forEach(c => { c.checked = org.facilities.some(f => f.type === c.value); }); };
  const read1 = () => { org.org = ($<HTMLInputElement>('st-org')!).value.trim(); org.dept = ($<HTMLInputElement>('st-dept')!).value.trim(); syncUnit(); org.reg_no = ($<HTMLInputElement>('st-regno')!).value.trim() || undefined; };
  /* 2단계 */
  const read2 = () => {
    const types = [...document.querySelectorAll<HTMLInputElement>('input[name=st-type]:checked')].map(c => c.value);
    for (const t of types) if (!org.facilities.some(f => f.type === t)) org.facilities.push({ id: uid(), type: t, name: facilityRule(D, { type: t } as OrgFacility)?.name.split('(')[0].trim() ?? t, run: 'direct', income: ['card'], deposit: false });
    org.facilities = org.facilities.filter(f => f.type === 'other' || types.includes(f.type));
    const others = ($<HTMLInputElement>('st-other')!).value.split(',').map(s => s.trim()).filter(Boolean);
    for (const o of others) if (!org.facilities.some(f => f.type === 'other' && f.name === o)) org.facilities.push({ id: uid(), type: 'other', name: o, run: 'direct', income: ['card'], deposit: false });
  };
  /* 3단계 */
  const facBox = $('st-fac')!;
  function renderFac() {
    if (!org.facilities.length) { facBox.innerHTML = '<p class="empty">2단계에서 시설을 고르세요.</p>'; return; }
    facBox.innerHTML = org.facilities.map(f => { const r = facilityRule(D, f); const st = r?.status ?? 'check'; return `<div class="vc-form" data-fid="${f.id}">
      <p class="q-title full"><span class="verdict ${st}">${st === 'taxable' ? '과세' : st === 'exempt' ? '면세' : '확인 필요'}</span> ${esc(r?.name ?? '직접 추가')}${r?.interp ? '<span class="vbadge">유권해석·분류 확인</span>' : ''}</p>
      <label>시설 이름 <input type="text" data-k="name" value="${esc(f.name)}" maxlength="40" /></label>
      <label>운영 방식 <select data-k="run">${(Object.keys(RUN_NAME) as Run[]).map(k => `<option value="${k}" ${f.run === k ? 'selected' : ''}>${RUN_NAME[k]}</option>`).join('')}</select></label>
      <label>수탁기관·담당 부서(위탁일 때, 부서명만) <input type="text" data-k="contractor_dept" value="${esc(f.contractor_dept ?? '')}" placeholder="예: 시설관리공단 체육사업팀" /></label>
      ${org.unit === 'site' ? `<label>이 시설(사업장)의 사업자등록번호 <input type="text" data-k="reg_no" value="${esc(f.reg_no ?? '')}" placeholder="000-00-00000" inputmode="numeric" /></label>` : ''}
      <div class="q"><span class="q-title" style="font-size:var(--small)">수입은 어떻게 받나요(여럿)</span><div class="choices">
        <label><input type="checkbox" data-inc="invoice" ${f.income.includes('invoice') ? 'checked' : ''}/> 세금계산서 발급(기관·법인 손님)</label>
        <label><input type="checkbox" data-inc="card" ${f.income.includes('card') ? 'checked' : ''}/> 카드·현금영수증(개인 손님)</label>
        <label><input type="checkbox" data-k="deposit" ${f.deposit ? 'checked' : ''}/> 임대 보증금을 받는다</label></div></div>
      <div class="actions"><button type="button" class="link-btn" data-dup>같은 유형 하나 더</button><button type="button" class="link-btn" data-del>이 시설 빼기</button></div>
      ${r?.note ? `<p class="note full">${esc(r.note)}</p>` : ''}</div>`; }).join('');
    facBox.querySelectorAll<HTMLButtonElement>('[data-dup]').forEach(b => b.addEventListener('click', () => { read3(); const f = org.facilities.find(x => x.id === b.closest<HTMLElement>('[data-fid]')!.dataset.fid)!; org.facilities.splice(org.facilities.indexOf(f) + 1, 0, { ...f, id: uid(), name: f.name + ' 2', reg_no: '' }); renderFac(); }));
    facBox.querySelectorAll<HTMLButtonElement>('[data-del]').forEach(b => b.addEventListener('click', () => { read3(); org.facilities = org.facilities.filter(x => x.id !== b.closest<HTMLElement>('[data-fid]')!.dataset.fid); renderFac(); }));
  }
  const read3 = () => { facBox.querySelectorAll<HTMLElement>('[data-fid]').forEach(box => { const f = org.facilities.find(x => x.id === box.dataset.fid); if (!f) return; box.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-k]').forEach(el => { const k = el.dataset.k!; if (k === 'deposit') f.deposit = (el as HTMLInputElement).checked; else (f as unknown as Record<string, unknown>)[k] = el.value.trim(); }); f.income = [...box.querySelectorAll<HTMLInputElement>('[data-inc]:checked')].map(c => c.dataset.inc!); }); };
  const read4 = () => { org.handover_day = Math.min(28, Math.max(1, Number(($<HTMLInputElement>('st-day')!).value) || 5)); };

  /* 5단계 */
  function renderResult() {
    const rows = org.facilities.map(f => { const st = facilityStatus(D, f); return `<tr><th scope="row">${esc(f.name)}</th><td><span class="verdict ${st}">${st === 'taxable' ? '과세' : st === 'exempt' ? '면세' : st === 'own' ? '수탁기관 신고' : '확인 필요'}</span></td><td>${esc(RUN_NAME[f.run])}${f.contractor_dept ? ' · ' + esc(f.contractor_dept) : ''}</td><td>${esc(org.unit === 'entity' ? (org.reg_no || '—') : (f.reg_no || '—'))}</td><td>${f.income.map(i => i === 'invoice' ? '세금계산서' : '카드·현금영수증').join('·')}${f.deposit ? ' · 보증금' : ''}</td></tr>`; }).join('');
    $('st-summary')!.innerHTML = `<p><strong>${esc(org.org || '(기관 이름 없음)')}</strong> · ${esc(org.dept || '부서 없음')} · ${org.unit === 'entity' ? '사업자 단위 과세' : '사업장별 등록'} · 인계표 매달 ${org.handover_day}일까지 · 저장 ${org.created}</p>
      <div class="scroll-x"><table class="data-table vat-table" data-stack="off"><caption>${esc(org.org)} 과세사업 시설 설정</caption><thead><tr><th scope="col">시설</th><th scope="col">부가세</th><th scope="col">운영</th><th scope="col">세금계산서 받을 번호</th><th scope="col">수입 종류</th></tr></thead><tbody>${rows || '<tr><td colspan="5">시설 없음</td></tr>'}</tbody></table></div>`;
    $('cards')!.innerHTML = org.facilities.map(f => card(f)).join('');
  }
  function card(f: OrgFacility) {
    const st = facilityStatus(D, f); const r = facilityRule(D, f); const reg = org.unit === 'entity' ? org.reg_no : f.reg_no;
    const what = st === 'taxable' ? `이용료·임대료에 부가세 10%가 붙고 <strong>${esc(org.org)}</strong>에서 신고합니다. 이 시설에 쓴 돈의 영수증(세금계산서·카드 전표)은 <strong>${esc(org.org)} 등록번호 ${esc(reg || '(번호 확인)')}</strong>로 받습니다. 그래야 그 부가세를 돌려받습니다.`
      : st === 'exempt' ? `이 시설 수입에는 부가세가 붙지 않고, 이 시설에만 쓴 돈의 부가세도 돌려받지 못합니다. 다만 <strong>다른 과세 시설과 함께 쓴 지출</strong>(공동 전기·청소 등)은 '여러 시설이 같이'로 표시해 주세요 — 나눠서 공제합니다.`
      : st === 'own' ? `수탁기관이 자기 이름으로 하는 사업입니다. 부가세 신고도 수탁기관이 하고, 영수증도 수탁기관 이름으로 받습니다. 이 도구에 기록하지 않습니다.`
      : `과세인지 면세인지 법령 글자로 정해지지 않아 <strong>${esc(org.dept || '신고 담당 부서')}</strong>가 유권해석으로 정합니다. 정해질 때까지 영수증은 ${esc(org.org)} 이름으로 받고 기록은 계속합니다.`;
    return `<article class="fcard"><h3>${esc(f.name)} <span class="verdict ${st}">${st === 'taxable' ? '과세' : st === 'exempt' ? '면세' : st === 'own' ? '수탁기관 신고' : '확인 필요'}</span></h3>
      <dl class="kv"><dt>기관</dt><dd>${esc(org.org)} · ${esc(org.dept || '')}</dd><dt>운영</dt><dd>${esc(RUN_NAME[f.run])}${f.contractor_dept ? ' · ' + esc(f.contractor_dept) : ''}</dd><dt>시설 유형</dt><dd>${esc(r?.name ?? '직접 추가')} — ${esc(r?.group ?? '')}</dd><dt>등록번호</dt><dd>${esc(reg || '—')}</dd></dl>
      <p>${what}</p>
      ${st !== 'own' ? `<h4>매달 할 일</h4><ol>
        <li>영수증마다 <strong>어느 시설에 쓴 돈인지</strong> 적어 둡니다(이 시설만 / 여러 시설 / 사무실과 함께).</li>
        <li>세금계산서의 <strong>공급받는 자</strong>가 ${esc(org.org)} 등록번호인지 봅니다. 공단·개인 이름이면 그 자리에서 수정 요청.</li>
        <li>카드 전표는 <strong>부가세 금액이 따로 적힌 것</strong>을 받습니다(간이영수증은 안 됩니다).</li>
        <li><strong>매달 ${org.handover_day}일까지</strong> <a href="/vat/monthly/">시설 지출 기록</a>에서 만든 매입 인계표를 ${esc(org.dept || '신고 담당 부서')}에 보냅니다.</li></ol>
      <h4>하면 안 되는 것</h4><ul><li>수탁기관·개인 이름으로 세금계산서 받기</li><li>간이영수증으로 끝내기</li><li>영수증 버리기 — 확정신고 뒤 5년 보관</li></ul>` : ''}
      <p class="note">근거: 부가가치세법 제26조 제1항 제19호·시행령 제46조(과세 범위), 제32조·제39조(세금계산서), 제40조·시행령 제81조(공통 지출). 참고용이며 신고 책임은 신고인에게 있습니다. 문의: ${esc(org.dept || '신고 담당 부서')}</p></article>`;
  }

  /* 단추 */
  document.querySelectorAll<HTMLButtonElement>('[data-next]').forEach(b => b.addEventListener('click', () => { if (step === 1) read1(); if (step === 2) read2(); if (step === 3) read3(); if (step === 4) read4(); save(); show(step + 1); }));
  document.querySelectorAll<HTMLButtonElement>('[data-prev]').forEach(b => b.addEventListener('click', () => { if (step === 3) read3(); save(); show(step - 1); }));
  $('st-download')?.addEventListener('click', () => { save(); downloadText(`org-${org.org || 'vat'}.json`, JSON.stringify(org, null, 2), 'application/json'); });
  $('st-print')?.addEventListener('click', () => { document.body.classList.add('print-cards'); window.print(); setTimeout(() => document.body.classList.remove('print-cards'), 500); });
  $('st-reset')?.addEventListener('click', () => { if (!confirm('이 브라우저의 기관 설정을 지우고 처음부터 합니다. 내려받은 파일은 남습니다.')) return; setOrg(null); org = { v: 1, org: '', dept: '', unit: 'site', facilities: [], handover_day: 5, created: ymd(new Date()) }; fill1(); ($<HTMLInputElement>('st-other')!).value = ''; show(1); });
  $<HTMLInputElement>('st-open')?.addEventListener('change', async e => { const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return; try { const o = await readJsonFile(f) as Org; if (!o || o.v !== 1 || !Array.isArray(o.facilities)) throw new Error('형식'); org = o; save(); fill1(); $('st-loaded')!.textContent = `열었습니다: ${o.org} · 시설 ${o.facilities.length}곳`; show(5); } catch { $('st-loaded')!.textContent = '기관 설정 파일(org.json)이 아닙니다.'; } });
  fill1(); show(getOrg() ? 5 : 1);
}
