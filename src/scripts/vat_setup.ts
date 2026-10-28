/** /vat/setup/ 기관 설정 마법사(신고 담당). 5문항 → org.json + 시설 카드. localStorage 저장, 서버 없음, 개인정보 없음. */
import { loadGovs, addRevenueFacilities, presetFacilities, facRows, normN, type RevGov } from './vat_org';
import { FEE_NAME, type Fee, $, esc, loadData, getOrg, setOrg, downloadText, readJsonFile, facilityRule, facilityStatus, RUN_NAME, runName, STATUS_LABEL_SHORT, uid, ymd, reduceMotion, toast, vatConfirm, gridKeys, helpWire, type Data, type Org, type OrgFacility, type Run, type OrgKind } from './vat_rules';
const D = loadData();
if (D) init(D);
function init(D: Data) {
  let org: Org = getOrg() ?? { v: 1, org: '', dept: '', unit: 'site', facilities: [], handover_day: 5, created: ymd(new Date()) };
  let step = 1, maxStep = 1;
  const steps = [...document.querySelectorAll<HTMLElement>('.step')];
  const chips = [...document.querySelectorAll<HTMLButtonElement>('#st-steps button')];
  /* 단계 표시줄은 단추(공무원 UX 재설계 2026-10-28): 간 적 있는 단계는 눌러 되돌아가고, 아직 안 간 단계는 비활성. aria-live 로 단계 바뀜을 읽는다 */
  const show = (n: number) => { step = n; maxStep = Math.max(maxStep, n); steps.forEach(s => { s.hidden = Number(s.dataset.step) !== n; }); chips.forEach((c, i) => { if (i + 1 === n) c.setAttribute('aria-current', 'step'); else c.removeAttribute('aria-current'); c.disabled = i + 1 > maxStep; }); const live = $('st-step-live'); if (live) live.textContent = `${n}/5 단계 ${chips[n - 1]?.textContent ?? ''}`; if (n === 3) renderFac(); if (n === 5) renderResult(); window.scrollTo({ top: 0, behavior: reduceMotion() ? 'auto' : 'smooth' }); };
  document.addEventListener('keydown', e => { if (!e.altKey) return; const to = e.key === 'ArrowRight' ? step + 1 : e.key === 'ArrowLeft' ? step - 1 : 0; if (!to || to < 1 || to > 5) return; /* 앞으로는 「다음」과 같다(읽고 저장), 뒤로는 자유 */ e.preventDefault(); if (step === 1) read1(); if (step === 2) read2(); if (step === 3) read3(); if (step === 4) read4(); save(); show(to); });   // Alt+←/→ 단계 이동(입력 상자 안에서도)
  chips.forEach(c => c.addEventListener('click', () => { const n = Number(c.dataset.go); if (!n || n === step || c.disabled) return; if (step === 1) read1(); if (step === 2) read2(); if (step === 3) read3(); if (step === 4) read4(); save(); show(n); }));
  const save = () => { org.created = ymd(new Date()); org.facilities.forEach(f => { f.kind = org.kind ?? 'gov'; if (f.kind === 'contractor' && f.run === 'entrusted_own') f.run = 'unknown'; }); setOrg(org); };
  const kindRadios = [...document.querySelectorAll<HTMLInputElement>('input[name=st-kind]')]; const parentWrap = $('st-parent-wrap')!;
  const syncKind = () => { org.kind = (kindRadios.find(r => r.checked)?.value as OrgKind) ?? 'gov'; parentWrap.hidden = org.kind !== 'contractor'; };
  kindRadios.forEach(r => r.addEventListener('change', syncKind));

  /* 1단계 */
  const unitRadios = [...document.querySelectorAll<HTMLInputElement>('input[name=st-unit]')];
  const regWrap = $('st-regno-wrap')!;
  const syncUnit = () => { const u = (unitRadios.find(r => r.checked)?.value ?? 'site') as Org['unit']; org.unit = u; regWrap.hidden = u !== 'entity'; };
  unitRadios.forEach(r => r.addEventListener('change', syncUnit));
  const fill1 = () => { ($<HTMLInputElement>('st-org')!).value = org.org; ($<HTMLInputElement>('st-dept')!).value = org.dept; kindRadios.forEach(r => { r.checked = r.value === (org.kind ?? 'gov'); }); ($<HTMLInputElement>('st-parent')!).value = org.parent ?? ''; syncKind(); unitRadios.forEach(r => { r.checked = r.value === org.unit; }); ($<HTMLInputElement>('st-regno')!).value = org.reg_no ?? ''; syncUnit(); ($<HTMLInputElement>('st-day')!).value = String(org.handover_day || 5); document.querySelectorAll<HTMLInputElement>('input[name=st-type]').forEach(c => { c.checked = org.facilities.some(f => f.type === c.value); }); };
  const read1 = () => { org.org = ($<HTMLInputElement>('st-org')!).value.trim(); org.dept = ($<HTMLInputElement>('st-dept')!).value.trim(); syncKind(); org.parent = ($<HTMLInputElement>('st-parent')!).value.trim() || undefined; syncUnit(); org.reg_no = ($<HTMLInputElement>('st-regno')!).value.trim() || undefined; };
  /* 2단계 */
  /* smart default(공무원 UX 재설계 2026-10-28): 새로 고른 시설의 수입 종류 기본값을 유형으로 — 임대·사용허가는 세금계산서(+보증금), 그 밖은 카드. 불러온 시설은 그대로 */
  const DEF_INV = new Set(['lease', 'use_permit', 'lease_bldg', 'ad_space']);
  const defIncome = (t: string) => DEF_INV.has(t) ? ['invoice'] : ['card'];
  const read2 = () => {
    const types = [...document.querySelectorAll<HTMLInputElement>('input[name=st-type]:checked')].map(c => c.value);
    for (const t of types) if (!org.facilities.some(f => f.type === t)) org.facilities.push({ id: uid(), type: t, name: facilityRule(D, { type: t } as OrgFacility)?.name.split('(')[0].trim() ?? t, run: 'direct', income: defIncome(t), deposit: t === 'lease' });
    org.facilities = org.facilities.filter(f => f.type === 'other' || f.note || types.includes(f.type));
    const others = ($<HTMLInputElement>('st-other')!).value.split(',').map(s => s.trim()).filter(Boolean);
    for (const o of others) if (!org.facilities.some(f => f.type === 'other' && f.name === o)) org.facilities.push({ id: uid(), type: 'other', name: o, run: 'direct', income: ['card'], deposit: false });
  };
  /* 예시 불러오기(공개 조례로 만든 시설 목록, 운영 방식은 '확인 필요') */
  /* 되돌리기(공무원 UX 재설계): 덮어쓰기·지우기 전에 직전 설정을 vat-org-backup-v1 에 두고 토스트로 되돌린다 */
  const backup = () => { const snap = JSON.stringify(org); try { localStorage.setItem('vat-org-backup-v1', snap); } catch { /* */ } return () => { org = JSON.parse(snap) as Org; save(); fill1(); show(org.facilities.length ? 3 : 1); }; };
  document.querySelectorAll<HTMLButtonElement>('[data-preset]').forEach(b => b.addEventListener('click', async () => {
    const p = (D.presets ?? []).find(x => x.key === b.dataset.preset); if (!p) return;
    if (org.facilities.length && !(await vatConfirm(`지금 시설 ${org.facilities.length}곳을 지우고 ${p.org} 예시 ${p.facilities.length}곳으로 바꿉니다. 바꾼 뒤 10초 안에 되돌릴 수 있습니다.`, '바꾸기'))) return;
    const undo = backup(); toast(`${p.org} 예시 ${p.facilities.length}곳으로 바꿨습니다`, { fn: undo });
    read1(); if (!org.org) { org.org = p.org; ($<HTMLInputElement>('st-org')!).value = p.org; }
    org.facilities = presetFacilities(p);
    document.querySelectorAll<HTMLInputElement>('input[name=st-type]').forEach(c => { c.checked = org.facilities.some(f => f.type === c.value); });
    save();
    /* 같은 지자체의 세입예산서가 있으면 골라 두고(조례 시설 ↔ 세입 사업을 이름으로 합치는 순서: 예시 → 세입 후보), 없으면 3단계로 */
    if (govSel && govs.some(g => g.key === p.key)) { govSel.value = p.key; govSel.dispatchEvent(new Event('change')); $('st-rev-note')!.textContent += ' — 「시설 후보 불러오기」를 누르면 세입 사업을 이름이 같은 예시 시설에 붙이고, 없는 것만 새 시설로 넣습니다.'; }
    else show(3);
  }));
  /* 세입예산서에서 시설 후보(운영자 지시 2026-10-27 '세입 자료부터 받아서 해'): /vat-revenue.json 의 세외수입 사업 가운데 시설 성격(사용료·임대·입장료·숙박·주차 …) 행을 시설로 */
  const govSel = $<HTMLSelectElement>('st-gov'); let govs: RevGov[] = [];
  if (govSel) loadGovs().then(gs => { govs = gs; govSel.innerHTML = '<option value="">— 지자체 —</option>' + govs.map(g => `<option value="${g.key}">${esc(g.name)} ${g.year}</option>`).join(''); let saved = ''; try { saved = localStorage.getItem('vat-gov') || ''; } catch { /* */ } if (saved && govs.some(g => g.key === saved)) { govSel.value = saved; govSel.dispatchEvent(new Event('change')); } });   // 과세사업 찾기에서 고른 지자체(vat-gov)를 이어받음
  govSel?.addEventListener('change', () => { const g = govs.find(x => x.key === govSel.value); ($<HTMLButtonElement>('st-rev-add')!).disabled = !g; ($<HTMLButtonElement>('st-exp-map')!).disabled = !g || !g.expense?.length; $('st-rev-note')!.textContent = g ? `시설 성격 사업 ${facRows(g).length}개${g.expense?.length ? ` · 세출 세부사업 ${g.expense.length}개` : ''}${g.note ? ` — 자료 한계: ${g.note}` : ''}` : ''; });
  /* 세출 세부사업명 → 시설 매핑표 밑그림(운영자 '세출도 해봐'): 시설 이름 낱말이 든 세부사업을 그 시설로, 금액 없음. 붙여넣기 때 사업명 열이 이 글자면 자동 귀속 */
  $('st-exp-map')?.addEventListener('click', () => {
    const g = govs.find(x => x.key === govSel!.value); if (!g || !g.expense?.length) return; read1(); const rules = org.map ?? (org.map = []); let n = 0, ops = 0;
    for (const e of g.expense) { const d = e.detail; const hit = org.facilities.find(f => { const a = normN(f.name), b = normN(d); return a.length >= 3 && (b.includes(a) || (a.length >= 4 && a.includes(b) && b.length >= 4)); });
      if (hit) { if (!rules.some(r => r.pat === d)) { rules.push({ pat: d, fid: hit.id, use: 'this' }); n++; } }
      else if (e.public_ops) ops++; }
    save(); $('st-rev-note')!.textContent = `매핑표에 ${n}줄 추가(세출 세부사업 → 시설). 시설 이름과 맞지 않는 공공운영비 사업 ${ops}개는 붙여넣기 때 '행정과 함께'(본청 공통) 후보입니다.`;
  });
  $('st-rev-add')?.addEventListener('click', () => {
    const g = govs.find(x => x.key === govSel!.value); if (!g) return; read1(); const undoRev = backup(); if (!org.org) { org.org = g.name; ($<HTMLInputElement>('st-org')!).value = g.name; }
    const { n, merged, k } = addRevenueFacilities(D, org, g); try { localStorage.setItem('vat-gov', g.key); } catch { /* */ }
    document.querySelectorAll<HTMLInputElement>('input[name=st-type]').forEach(c => { c.checked = org.facilities.some(f => f.type === c.value); });
    save(); toast(`새 시설 후보 ${n}곳을 넣고, 이미 있는 시설 ${merged}곳에 세입 사업 ${k}건을 붙였습니다 — 3단계에서 운영 방식·등록번호를 채우세요`, { fn: undoRev }); show(3);
  });
  /* 3단계 — 시설 그리드(공무원 UX 재설계 2026-10-28, docs/design/vat-ux-spec.md §3.1): 시설마다 카드 한 장 대신 표 한 줄. 필터(전체·검토 대기·확인 필요·번호 없음)·행 선택·일괄 적용·펼침 행(받는 것·확인 근거·메모·복제·빼기). 저장 로직(read3)은 같은 [data-k]·[data-inc] 를 읽는다 */
  const facBox = $('st-fac')!;
  let facFilter: 'all' | 'pending' | 'check' | 'noreg' = 'all';
  const rowSt = (f: OrgFacility) => { const r = facilityRule(D, f); const C = org.kind === 'contractor'; return ((C ? (r?.contractor_status === 'none' ? 'exempt' : r?.contractor_status) : r?.status) ?? r?.status ?? 'check') as 'taxable' | 'exempt' | 'check'; };
  const matches = (f: OrgFacility) => facFilter === 'all' || (facFilter === 'pending' && f.run === 'unknown') || (facFilter === 'check' && rowSt(f) === 'check') || (facFilter === 'noreg' && org.unit === 'site' && !f.reg_no);
  function renderFac() {
    if (!org.facilities.length) { facBox.innerHTML = '<p class="empty">2단계에서 시설을 고르세요. <a class="btn secondary" href="#" data-go2>시설 고르기</a></p>'; facBox.querySelector('[data-go2]')?.addEventListener('click', e => { e.preventDefault(); show(2); }); return; }
    const C = org.kind === 'contractor'; const site = org.unit === 'site';
    const nPend = org.facilities.filter(f => f.run === 'unknown').length, nChk = org.facilities.filter(f => rowSt(f) === 'check').length, nNoReg = site ? org.facilities.filter(f => !f.reg_no).length : 0;
    if (!facBox.dataset.filterSet) { facBox.dataset.filterSet = '1'; facFilter = nPend ? 'pending' : 'all'; }
    if ((facFilter === 'pending' && !nPend) || (facFilter === 'check' && !nChk) || (facFilter === 'noreg' && !nNoReg)) facFilter = 'all';   // 거른 결과가 비면 전체로(일괄 적용 뒤 화면이 비지 않게)
    const chip = (k: typeof facFilter, name: string, n: number) => `<button type="button" class="chip" data-filter="${k}" aria-pressed="${facFilter === k}">${name} <b>${n}</b></button>`;
    const runOpts = (sel: Run) => (Object.keys(RUN_NAME) as Run[]).filter(k => !(C && k === 'entrusted_own')).map(k => `<option value="${k}" ${sel === k ? 'selected' : ''}>${runName(org.kind, k)}</option>`).join('');
    const row = (f: OrgFacility) => { f.kind = org.kind ?? 'gov'; const r = facilityRule(D, f); const st = rowSt(f); const pend = f.run === 'unknown'; const hid = matches(f) ? '' : 'hidden';
      return `<tr data-fid="${f.id}" ${pend ? 'data-pending' : ''} ${hid}>
        <td><input type="checkbox" data-sel aria-label="${esc(f.name)} 선택" /></td>
        <th scope="row"><input type="text" data-k="name" value="${esc(f.name)}" maxlength="40" aria-label="시설 이름" /></th>
        <td class="note"><span class="verdict ${st}">${st === 'taxable' ? '과세' : st === 'exempt' ? '면세' : '확인 필요'}</span> ${esc((r?.name ?? '직접 추가').split('(')[0])}${!C && r?.interp ? ' <span class="vbadge">유권해석</span>' : ''}</td>
        <td><select data-k="run" aria-label="운영 방식">${runOpts(f.run)}</select></td>
        <td><input type="text" data-k="contractor_dept" value="${esc(f.contractor_dept ?? '')}" placeholder="${C ? '체육사업팀 / 군 ○○과' : '공단 체육사업팀'}" aria-label="수탁기관·담당 부서" /></td>
        ${site ? `<td><input type="text" data-k="reg_no" value="${esc(f.reg_no ?? '')}" placeholder="000-00-00000" inputmode="numeric" aria-label="사업자등록번호" /></td>` : ''}
        <td class="inc"><label><input type="checkbox" data-inc="invoice" ${f.income.includes('invoice') ? 'checked' : ''}/> 계산서</label><label><input type="checkbox" data-inc="card" ${f.income.includes('card') ? 'checked' : ''}/> 카드</label><label><input type="checkbox" data-k="deposit" ${f.deposit ? 'checked' : ''}/> 보증금</label></td>
        <td class="st"><span class="verdict check" data-pend-badge ${pend ? '' : 'hidden'}>검토 대기</span></td>
        <td><button type="button" class="link-btn" data-more aria-expanded="false" aria-controls="sub-${f.id}">더보기</button></td></tr>
      <tr class="sub" id="sub-${f.id}" data-sub="${f.id}" hidden><td colspan="${site ? 9 : 8}"><div class="vc-form">
        <label class="full" data-fee-q ${f.run === 'entrusted_own' && !C ? '' : 'hidden'}>수탁기관 자기 사업일 때 — 우리 기관이 수탁기관에게 받는 것 <select data-k="fee">${(Object.keys(FEE_NAME) as Fee[]).map(k => `<option value="${k}" ${(f.fee ?? 'unknown') === k ? 'selected' : ''}>${FEE_NAME[k]}</option>`).join('')}</select><span class="note">사용료·임대료를 받아 과세로 신고하고 있을 때만 우리 기관이 이 시설에 직접 낸 돈(수선·장비)의 부가세를 공제할 수 있습니다. 받지만 과세 신고 여부를 모르면 노랑, 무상이면 불공제. 무상 → 유상(과세)으로 바꾸면 그 전에 산 건물·설비의 불공제 매입세액을 과세사업 전환 매입세액(시행령 제85조)으로 일부 되살릴 수 있습니다 — <a href="/vat/prepare/#p-convert">신고 준비의 전환 계산기</a>.</span></label>
        ${st === 'check' ? `<label class="full">확인 결과·근거(유권해석·질의회신 번호, 결정일 — 정해졌으면 2단계에서 시설 유형을 과세·면세 유형으로 바꾸고 여기 근거를 남깁니다) <input type="text" data-k="decision" value="${esc(f.decision ?? '')}" maxlength="120" placeholder="예: 2026-09-01 세무서 질의회신 ○○, 과세로 처리" /></label>` : ''}
        ${f.note ? `<p class="note full">출처 메모: ${esc(f.note)}</p>` : ''}${r?.note ? `<p class="note full">${esc(r.note)}</p>` : ''}${C && r?.contractor_note ? `<p class="note full">수탁기관 기준 — ${esc(r.contractor_note)}</p>` : ''}
        <div class="actions"><button type="button" class="link-btn" data-dup>같은 유형 하나 더</button><button type="button" class="link-btn" data-del>이 시설 빼기</button></div></div></td></tr>`; };
    facBox.innerHTML = `<div class="filters" role="group" aria-label="시설 거르기">${chip('all', '전체', org.facilities.length)}${chip('pending', '검토 대기', nPend)}${chip('check', '과세 여부 확인', nChk)}${site ? chip('noreg', '등록번호 없음', nNoReg) : ''}<span class="note" id="st-fac-live" aria-live="polite"></span></div>
      <div class="bulk vc-form"><span class="q-title full" style="font-size:var(--small)">선택한 행에 한꺼번에 — 비워 둔 칸은 바꾸지 않습니다</span>
        <label>운영 방식 <select data-bk="run"><option value="">— 바꾸지 않음 —</option>${runOpts('' as Run)}</select></label>
        <label>${C ? '담당 부서' : '수탁기관·담당 부서'} <input type="text" data-bk="contractor_dept" placeholder="비우면 그대로" /></label>
        ${site ? '<label>사업자등록번호 <input type="text" data-bk="reg_no" placeholder="비우면 그대로" inputmode="numeric" /></label>' : ''}
        <div class="actions"><button type="button" class="btn secondary" data-bulk="sel">선택 행에 적용</button><button type="button" class="btn secondary" data-bulk="vis">보이는 행 전체에 적용</button></div></div>
      <div class="scroll-x" tabindex="0" role="region" aria-label="시설 표"><table class="data-table vat-table vat-grid" id="st-grid" data-stack="off"><caption class="sr-only">시설마다 이름·운영 방식·등록번호·수입 종류</caption>
      <thead><tr><th scope="col"><input type="checkbox" data-sel-all aria-label="보이는 행 모두 선택" /></th><th scope="col">시설 이름</th><th scope="col">유형 · 부가세</th><th scope="col">운영 방식</th><th scope="col">${C ? '담당 부서' : '수탁기관·부서'}</th>${site ? '<th scope="col">등록번호</th>' : ''}<th scope="col">수입</th><th scope="col">상태</th><th scope="col"><span class="sr-only">더보기</span></th></tr></thead>
      <tbody>${org.facilities.map(row).join('')}</tbody></table></div>`;
    const tbl = facBox.querySelector<HTMLTableElement>('#st-grid')!; gridKeys(tbl); helpWire(facBox, D);
    const vis = () => [...tbl.querySelectorAll<HTMLTableRowElement>('tbody tr[data-fid]')].filter(tr => !tr.hidden);
    const live = (m: string) => { const l = $('st-fac-live'); if (l) l.textContent = m; };
    facBox.querySelectorAll<HTMLButtonElement>('[data-filter]').forEach(b => b.addEventListener('click', () => { facFilter = b.dataset.filter as typeof facFilter; facBox.querySelectorAll<HTMLButtonElement>('[data-filter]').forEach(x => x.setAttribute('aria-pressed', String(x === b))); read3(); tbl.querySelectorAll<HTMLTableRowElement>('tbody tr[data-fid]').forEach(tr => { const f = org.facilities.find(x => x.id === tr.dataset.fid)!; tr.hidden = !matches(f); if (tr.hidden) { const sub = tbl.querySelector<HTMLTableRowElement>(`tr[data-sub="${f.id}"]`); if (sub) { sub.hidden = true; tr.querySelector('[data-more]')?.setAttribute('aria-expanded', 'false'); } } }); live(`${vis().length}곳 보임`); }));
    tbl.querySelector<HTMLInputElement>('[data-sel-all]')?.addEventListener('change', e => { const on = (e.target as HTMLInputElement).checked; vis().forEach(tr => { tr.querySelector<HTMLInputElement>('[data-sel]')!.checked = on; }); });
    tbl.querySelectorAll<HTMLButtonElement>('[data-more]').forEach(b => b.addEventListener('click', () => { const tr = b.closest<HTMLTableRowElement>('tr')!; const sub = tbl.querySelector<HTMLTableRowElement>(`tr[data-sub="${tr.dataset.fid}"]`)!; const open = sub.hidden; sub.hidden = !open; b.setAttribute('aria-expanded', String(open)); b.textContent = open ? '접기' : '더보기'; }));
    tbl.querySelectorAll<HTMLSelectElement>('select[data-k=run]').forEach(sel => sel.addEventListener('change', () => { const tr = sel.closest<HTMLTableRowElement>('tr')!; const sub = tbl.querySelector<HTMLElement>(`tr[data-sub="${tr.dataset.fid}"]`)!; const q = sub.querySelector<HTMLElement>('[data-fee-q]'); if (q) q.hidden = sel.value !== 'entrusted_own'; const pend = sel.value === 'unknown'; tr.toggleAttribute('data-pending', pend); tr.querySelector<HTMLElement>('[data-pend-badge]')!.hidden = !pend; if (sel.value === 'entrusted_own' && sub.hidden) { sub.hidden = false; tr.querySelector('[data-more]')?.setAttribute('aria-expanded', 'true'); } }));
    tbl.querySelectorAll<HTMLButtonElement>('[data-dup]').forEach(b => b.addEventListener('click', () => { read3(); const fid = b.closest<HTMLElement>('[data-sub]')!.dataset.sub; const f = org.facilities.find(x => x.id === fid)!; org.facilities.splice(org.facilities.indexOf(f) + 1, 0, { ...f, id: uid(), name: f.name + ' 2', reg_no: '' }); renderFac(); }));
    tbl.querySelectorAll<HTMLButtonElement>('[data-del]').forEach(b => b.addEventListener('click', () => { read3(); const fid = b.closest<HTMLElement>('[data-sub]')!.dataset.sub; const f = org.facilities.find(x => x.id === fid); if (!f) return; const snap = JSON.stringify(org.facilities); org.facilities = org.facilities.filter(x => x.id !== fid); renderFac(); toast(`'${f.name}'을 뺐습니다`, { fn: () => { org.facilities = JSON.parse(snap); renderFac(); } }); }));
    /* 일괄 적용: 선택 행 또는 보이는 행 전체에 운영 방식·부서·등록번호 중 채운 것만 */
    facBox.querySelectorAll<HTMLButtonElement>('[data-bulk]').forEach(b => b.addEventListener('click', () => {
      read3(); const rows = b.dataset.bulk === 'sel' ? vis().filter(tr => tr.querySelector<HTMLInputElement>('[data-sel]')!.checked) : vis(); if (!rows.length) { live('선택한 행이 없습니다 — 왼쪽 체크 상자로 고르세요'); return; }
      const g = (k: string) => facBox.querySelector<HTMLInputElement | HTMLSelectElement>(`[data-bk=${k}]`)?.value.trim() ?? ''; const run = g('run') as Run | '', dept = g('contractor_dept'), reg = g('reg_no'); if (!run && !dept && !reg) { live('바꿀 값을 하나 이상 넣으세요'); return; }
      const snap = JSON.stringify(org.facilities); let n = 0; for (const tr of rows) { const f = org.facilities.find(x => x.id === tr.dataset.fid)!; if (run) f.run = run; if (dept) f.contractor_dept = dept; if (reg) f.reg_no = reg; n++; }
      renderFac(); live(`${n}행에 적용했습니다`); toast(`${n}행에 ${[run && `운영 방식 '${runName(org.kind, run).split('(')[0].trim()}'`, dept && '부서', reg && '등록번호'].filter(Boolean).join('·')} 적용`, { fn: () => { org.facilities = JSON.parse(snap); renderFac(); } }); }));
    live(`${vis().length}곳 보임${nPend ? ` · 검토 대기 ${nPend}` : ''}`);
  }
  const read3 = () => { facBox.querySelectorAll<HTMLElement>('tr[data-fid]').forEach(box => { const f = org.facilities.find(x => x.id === box.dataset.fid); if (!f) return; const sub = facBox.querySelector<HTMLElement>(`tr[data-sub="${f.id}"]`); const els = [...box.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-k]'), ...(sub ? sub.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-k]') : [])]; els.forEach(el => { const k = el.dataset.k!; if (k === 'deposit') f.deposit = (el as HTMLInputElement).checked; else (f as unknown as Record<string, unknown>)[k] = el.value.trim(); }); f.income = [...box.querySelectorAll<HTMLInputElement>('[data-inc]:checked')].map(c => c.dataset.inc!); }); };
  const read4 = () => { org.handover_day = Math.min(28, Math.max(1, Number(($<HTMLInputElement>('st-day')!).value) || 5)); };

  /* 5단계 */
  function renderResult() {
    const rows = org.facilities.map(f => { const st = facilityStatus(D, f); return `<tr><th scope="row">${esc(f.name)}</th><td><span class="verdict ${st === 'agency' ? 'none' : st}">${STATUS_LABEL_SHORT[st]}</span></td><td>${f.run === 'unknown' ? '<span class="verdict check">운영 방식 확인</span> ' : ''}${esc(runName(org.kind, f.run))}${f.contractor_dept ? ' · ' + esc(f.contractor_dept) : ''}${f.run === 'entrusted_own' ? ` · 받는 것: ${esc(FEE_NAME[f.fee ?? 'unknown'].split('(')[0])}` : ''}${f.decision ? ` · 근거: ${esc(f.decision)}` : ''}</td><td>${esc(org.unit === 'entity' ? (org.reg_no || '—') : (f.reg_no || '—'))}</td><td>${f.income.map(i => i === 'invoice' ? '세금계산서' : '카드·현금영수증').join('·')}${f.deposit ? ' · 보증금' : ''}</td></tr>`; }).join('');
    $('st-summary')!.innerHTML = `<p><strong>${esc(org.org || '(기관 이름 없음)')}</strong>${org.kind === 'contractor' ? ` <span class="verdict check">수탁기관${org.parent ? ' · 위탁기관 ' + esc(org.parent) : ''}</span>` : ''} · ${esc(org.dept || '부서 없음')} · ${org.unit === 'entity' ? '사업자 단위 과세' : '사업장별 등록'} · 인계표 매달 ${org.handover_day}일까지 · 저장 ${org.created}</p>
      <div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table" data-stack="off"><caption>${esc(org.org)} 과세사업 시설 설정</caption><thead><tr><th scope="col">시설</th><th scope="col">부가세</th><th scope="col">운영</th><th scope="col">세금계산서 받을 번호</th><th scope="col">수입 종류</th></tr></thead><tbody>${rows || '<tr><td colspan="5">시설 없음</td></tr>'}</tbody></table></div>`;
    $('cards')!.innerHTML = org.facilities.map(f => card(f)).join('');
    /* 대행 협약서 점검표(세무회계법인 2차 6번): 군 명의 사업의 지출 매입세액이 군·공단 사이에 떨어지지 않게 — 수탁기관이거나 위탁 시설이 있을 때, 체크는 이 브라우저(vat-contract-v1) */
    const AC = D.rules.agency_contract ?? []; const box = $('st-contract'); if (box) { const need = org.kind === 'contractor' || org.facilities.some(f => f.run === 'entrusted_org' || f.run === 'entrusted_own'); box.hidden = !need || !AC.length;
      if (need && AC.length) { let st: Record<string, boolean> = {}; try { st = JSON.parse(localStorage.getItem('vat-contract-v1') || '{}'); } catch { /* */ }
        box.innerHTML = `<details class="vat-more"><summary><strong>대행·위탁 협약서 점검표</strong> ${AC.length}개 — 군과 공단 사이에 떨어지는 매입세액 막기</summary><p class="meta">협약서(또는 운영 지침)에 이 항목이 있는지 봅니다. 조문이 아니라 절차 체크이며, 없으면 협약 갱신 때 넣을 자리입니다.</p><ul class="checks">${AC.map(c => `<li><label><input type="checkbox" data-ac="${c.key}" ${st[c.key] ? 'checked' : ''}/> <span>${esc(c.text)}</span></label></li>`).join('')}</ul></details>`;
        box.querySelectorAll<HTMLInputElement>('[data-ac]').forEach(c => c.addEventListener('change', () => { st[c.dataset.ac!] = c.checked; try { localStorage.setItem('vat-contract-v1', JSON.stringify(st)); } catch { /* */ } })); } }
  }
  function card(f: OrgFacility) {
    const st = facilityStatus(D, f); const r = facilityRule(D, f); const reg = org.unit === 'entity' ? org.reg_no : f.reg_no;
    const what = st === 'taxable' ? `이용료·임대료에 부가세 10%가 붙고 <strong>${esc(org.org)}</strong>에서 신고합니다. 이 시설에 쓴 돈의 영수증(세금계산서·카드 전표)은 <strong>${esc(org.org)} 등록번호 ${esc(reg || '(번호 확인)')}</strong>로 받습니다. 그래야 그 부가세를 돌려받습니다.`
      : st === 'exempt' ? `이 시설 수입에는 부가세가 붙지 않고, 이 시설에만 쓴 돈의 부가세도 돌려받지 못합니다. 다만 <strong>다른 과세 시설과 함께 쓴 지출</strong>(공동 전기·청소 등)은 '여러 시설이 같이'로 표시해 주세요 — 나눠서 공제합니다.`
      : st === 'agency' ? `<strong>${esc(org.parent || '군·시')}</strong>의 사업을 ${esc(org.org)}가 대행하는 시설입니다. 이용료는 군 수입(군이 신고)이고, 이 시설에 쓴 돈의 세금계산서는 <strong>군 등록번호</strong>로 받아 군이 공제합니다. ${esc(org.org)}의 수입은 대행수수료(과세 용역 — 군에 세금계산서 발급)뿐이며, 공단 명의로 받은 지출은 재청구 구조가 아니면 누구도 공제하지 못합니다.`
      : st === 'own' ? `수탁기관이 자기 이름으로 하는 사업입니다. 수탁기관이 쓰는 돈의 부가세 신고는 수탁기관이 하고, 영수증도 수탁기관 이름으로 받습니다. <strong>${esc(org.org)}가 이 시설에 직접 내는 돈(수선·장비·공사)</strong>은 따로입니다 — ${f.fee === 'taxable' ? `${esc(org.org)}가 수탁기관에게 사용료·임대료를 받아 과세로 신고하므로 그 돈의 영수증은 ${esc(org.org)} 등록번호 ${esc(reg || '(번호 확인)')}로 받고 기록합니다(공제 대상).` : f.fee === 'free' ? `${esc(org.org)}가 사용료를 받지 않는 무상 사용이라 그 돈의 부가세는 돌려받지 못합니다. 큰 수선·설비가 예정돼 있으면 유상 사용허가로 바꿀 수 있는지 재산 담당과 검토합니다.` : `${esc(org.org)}가 수탁기관에게 사용료를 받는지(위·수탁 계약·사용허가서) 확인해 기관 설정에서 고르세요. 받으면 공제 대상, 무상이면 공제 불가.`}`
      : `과세인지 면세인지 법령 글자로 정해지지 않아 <strong>${esc(org.dept || '신고 담당 부서')}</strong>가 유권해석으로 정합니다. 정해질 때까지 영수증은 ${esc(org.org)} 이름으로 받고 기록은 계속합니다.`;
    return `<article class="fcard"><h3>${esc(f.name)} <span class="verdict ${st === 'agency' ? 'none' : st}">${STATUS_LABEL_SHORT[st]}</span></h3>
      <dl class="kv"><dt>기관</dt><dd>${esc(org.org)} · ${esc(org.dept || '')}</dd><dt>운영</dt><dd>${esc(runName(org.kind, f.run))}${f.contractor_dept ? ' · ' + esc(f.contractor_dept) : ''}</dd><dt>시설 유형</dt><dd>${esc(r?.name ?? '직접 추가')} — ${esc(r?.group ?? '')}</dd><dt>등록번호</dt><dd>${esc(reg || '—')}</dd></dl>
      <p>${what}</p>${st === 'own' && (f.fee ?? 'unknown') === 'unknown' ? '<p class="callout warn">우리 기관이 수탁기관에게 사용료·임대료를 받는지 아직 정하지 않았습니다. 그때까지 우리 기관이 이 시설에 직접 낸 돈은 노랑(확인 필요)으로 기록됩니다.</p>' : ''}${f.run === 'unknown' ? '<p class="callout warn">운영 방식이 아직 정해지지 않았습니다. 위·수탁 계약서로 "우리 기관 명의 사업(대행)"인지 "수탁기관 자기 사업"인지 확인해 기관 설정에서 고르세요. 수탁기관 자기 사업이면 이 카드의 매입세액 안내는 적용되지 않습니다.</p>' : ''}
      ${(st !== 'own' && st !== 'agency') || f.fee === 'taxable' ? `<h4>매달 할 일</h4><ol>
        <li>영수증마다 <strong>어느 시설에 쓴 돈인지</strong> 적어 둡니다(이 시설만 / 여러 시설 / 사무실과 함께).</li>
        <li>세금계산서의 <strong>공급받는 자</strong>가 ${esc(org.org)} 등록번호인지 봅니다. 공단·개인 이름이면 그 자리에서 수정 요청.</li>
        <li>카드 전표는 <strong>부가세 금액이 따로 적힌 것</strong>을 받습니다(간이영수증은 안 됩니다). 기관 법인카드는 홈택스 「사업용 신용카드」에 등록해 두면 자동 집계됩니다(신고 담당이 한 번).</li>
        <li><strong>매달 ${org.handover_day}일까지</strong> <a href="/vat/monthly/">시설 지출 기록</a>에서 만든 매입 인계표를 ${esc(org.dept || '신고 담당 부서')}에 보냅니다.</li></ol>
      <h4>하면 안 되는 것</h4><ul><li>수탁기관·개인 이름으로 세금계산서 받기</li><li>간이영수증으로 끝내기</li><li>영수증 버리기 — 확정신고 뒤 5년 보관</li></ul>` : ''}
      <p class="note">근거: 부가가치세법 제26조 제1항 제19호·시행령 제46조(과세 범위), 제32조·제39조(세금계산서), 제40조·시행령 제81조(공통 지출). 참고용이며 신고 책임은 신고인에게 있습니다. 문의: ${esc(org.dept || '신고 담당 부서')}</p></article>`;
  }

  /* 단추 */
  document.querySelectorAll<HTMLButtonElement>('[data-next]').forEach(b => b.addEventListener('click', () => { if (step === 1) read1(); if (step === 2) read2(); if (step === 3) read3(); if (step === 4) read4(); save(); show(step + 1); }));
  document.querySelectorAll<HTMLButtonElement>('[data-prev]').forEach(b => b.addEventListener('click', () => { if (step === 3) read3(); save(); show(step - 1); }));
  $('st-download')?.addEventListener('click', () => { save(); downloadText(`org-${org.org || 'vat'}.json`, JSON.stringify(org, null, 2), 'application/json'); });
  $('st-print')?.addEventListener('click', () => { document.body.classList.add('print-cards'); window.print(); setTimeout(() => document.body.classList.remove('print-cards'), 500); });
  $('st-reset')?.addEventListener('click', async () => { if (!(await vatConfirm('이 브라우저의 기관 설정을 지우고 처음부터 합니다. 내려받은 파일은 남고, 10초 안에 되돌릴 수 있습니다.', '지우기'))) return; const undo = backup(); toast('기관 설정을 지웠습니다', { fn: undo }); setOrg(null); org = { v: 1, org: '', dept: '', unit: 'site', facilities: [], handover_day: 5, created: ymd(new Date()) }; fill1(); ($<HTMLInputElement>('st-other')!).value = ''; show(1); });
  $<HTMLInputElement>('st-open')?.addEventListener('change', async e => { const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return; try { const o = await readJsonFile(f) as Org; if (!o || o.v !== 1 || !Array.isArray(o.facilities)) throw new Error('형식'); org = o; save(); fill1(); $('st-loaded')!.textContent = `열었습니다: ${o.org} · 시설 ${o.facilities.length}곳`; show(5); } catch { $('st-loaded')!.textContent = '기관 설정 파일(org.json)이 아닙니다.'; } });
  fill1(); show(getOrg() ? 5 : 1);
}
