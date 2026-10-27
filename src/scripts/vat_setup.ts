/** /vat/setup/ 기관 설정 마법사(신고 담당). 5문항 → org.json + 시설 카드. localStorage 저장, 서버 없음, 개인정보 없음. */
import { FEE_NAME, type Fee, $, esc, loadData, getOrg, setOrg, downloadText, readJsonFile, facilityRule, facilityStatus, RUN_NAME, runName, STATUS_LABEL_SHORT, uid, ymd, type Data, type Org, type OrgFacility, type Run, type OrgKind } from './vat_rules';
const D = loadData();
if (D) init(D);
function init(D: Data) {
  let org: Org = getOrg() ?? { v: 1, org: '', dept: '', unit: 'site', facilities: [], handover_day: 5, created: ymd(new Date()) };
  let step = 1;
  const steps = [...document.querySelectorAll<HTMLElement>('.step')];
  const chips = [...document.querySelectorAll<HTMLElement>('#st-steps span')];
  const show = (n: number) => { step = n; steps.forEach(s => { s.hidden = Number(s.dataset.step) !== n; }); chips.forEach((c, i) => { if (i + 1 === n) c.setAttribute('aria-current', 'step'); else c.removeAttribute('aria-current'); }); if (n === 3) renderFac(); if (n === 5) renderResult(); window.scrollTo({ top: 0, behavior: 'smooth' }); };
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
  const read2 = () => {
    const types = [...document.querySelectorAll<HTMLInputElement>('input[name=st-type]:checked')].map(c => c.value);
    for (const t of types) if (!org.facilities.some(f => f.type === t)) org.facilities.push({ id: uid(), type: t, name: facilityRule(D, { type: t } as OrgFacility)?.name.split('(')[0].trim() ?? t, run: 'direct', income: ['card'], deposit: false });
    org.facilities = org.facilities.filter(f => f.type === 'other' || f.note || types.includes(f.type));
    const others = ($<HTMLInputElement>('st-other')!).value.split(',').map(s => s.trim()).filter(Boolean);
    for (const o of others) if (!org.facilities.some(f => f.type === 'other' && f.name === o)) org.facilities.push({ id: uid(), type: 'other', name: o, run: 'direct', income: ['card'], deposit: false });
  };
  /* 예시 불러오기(공개 조례로 만든 시설 목록, 운영 방식은 '확인 필요') */
  document.querySelectorAll<HTMLButtonElement>('[data-preset]').forEach(b => b.addEventListener('click', () => {
    const p = (D.presets ?? []).find(x => x.key === b.dataset.preset); if (!p) return;
    if (org.facilities.length && !confirm(`지금 시설 ${org.facilities.length}곳을 지우고 ${p.org} 예시 ${p.facilities.length}곳으로 바꿉니다.`)) return;
    read1(); if (!org.org) { org.org = p.org; ($<HTMLInputElement>('st-org')!).value = p.org; }
    org.facilities = p.facilities.map(f => ({ id: uid(), type: f.type, name: f.name, run: 'unknown' as Run, income: ['card'], deposit: false, contractor_dept: f.contractor ? `${f.contractor}(협약서 확인)` : f.op === '공단' ? '달성군시설관리공단(부서 확인)' : '', note: (f.op ? `[${f.op}] ` : '') + (f.term ? `위탁 기간 ${f.term}(의회 동의안 제안설명 기준, 협약서로 확인). ` : '') + (f.note ?? '') }));
    document.querySelectorAll<HTMLInputElement>('input[name=st-type]').forEach(c => { c.checked = org.facilities.some(f => f.type === c.value); });
    save(); show(3);
  }));
  /* 세입예산서에서 시설 후보(운영자 지시 2026-10-27 '세입 자료부터 받아서 해'): /vat-revenue.json 의 세외수입 사업 가운데 시설 성격(사용료·임대·입장료·숙박·주차 …) 행을 시설로 */
  const FAC_KEYS = new Set(['sports', 'golf', 'lodging', 'culture', 'venue', 'program', 'parking', 'water', 'funeral', 'transit', 'marina', 'lease_bldg', 'use_permit', 'food', 'vending', 'welfare', 'equip_rent', 'ad_space', 'waste_bag']);
  type RevRow = { mok_code: string; mok: string; dept: string; item: string; amount_k: number; vat_key: string; fac_key: string; grant: boolean };
  type ExpRow = { bureau: string; dept: string; detail: string; codes: string[]; facility: boolean; public_ops: boolean; grant: boolean; fac_key: string };
  type RevGov = { key: string; name: string; year: string; rows: RevRow[]; expense: ExpRow[] };
  const govSel = $<HTMLSelectElement>('st-gov'); let govs: RevGov[] = [];
  if (govSel) fetch('/vat-revenue.json').then(r => r.json()).then((j: { govs: RevGov[] }) => { govs = j.govs; govSel.innerHTML = '<option value="">— 지자체 —</option>' + govs.map(g => `<option value="${g.key}">${esc(g.name)} ${g.year}</option>`).join(''); }).catch(() => { /* */ });
  govSel?.addEventListener('change', () => { const g = govs.find(x => x.key === govSel.value); ($<HTMLButtonElement>('st-rev-add')!).disabled = !g; ($<HTMLButtonElement>('st-exp-map')!).disabled = !g || !g.expense?.length; $('st-rev-note')!.textContent = g ? `시설 성격 사업 ${g.rows.filter(r => !r.grant && FAC_KEYS.has(r.vat_key)).length}개${g.expense?.length ? ` · 세출 세부사업 ${g.expense.length}개` : ''}` : ''; });
  /* 세출 세부사업명 → 시설 매핑표 밑그림(운영자 '세출도 해봐'): 시설 이름 낱말이 든 세부사업을 그 시설로, 금액 없음. 붙여넣기 때 사업명 열이 이 글자면 자동 귀속 */
  const normN = (x: string) => x.replace(/\s|\(.*?\)|운영|관리|사업|비|지원|센터$/g, '').toLowerCase();
  $('st-exp-map')?.addEventListener('click', () => {
    const g = govs.find(x => x.key === govSel!.value); if (!g || !g.expense?.length) return; read1(); const rules = org.map ?? (org.map = []); let n = 0, ops = 0;
    for (const e of g.expense) { const d = e.detail; const hit = org.facilities.find(f => { const a = normN(f.name), b = normN(d); return a.length >= 3 && (b.includes(a) || (a.length >= 4 && a.includes(b) && b.length >= 4)); });
      if (hit) { if (!rules.some(r => r.pat === d)) { rules.push({ pat: d, fid: hit.id, use: 'this' }); n++; } }
      else if (e.public_ops) ops++; }
    save(); $('st-rev-note')!.textContent = `매핑표에 ${n}줄 추가(세출 세부사업 → 시설). 시설 이름과 맞지 않는 공공운영비 사업 ${ops}개는 붙여넣기 때 '행정과 함께'(본청 공통) 후보입니다.`;
  });
  $('st-rev-add')?.addEventListener('click', () => {
    const g = govs.find(x => x.key === govSel!.value); if (!g) return; read1(); if (!org.org) { org.org = g.name; ($<HTMLInputElement>('st-org')!).value = g.name; }
    const clean = (s: string) => s.replace(/\s*(수입|입장료|사용료|임대료|이용료|관람료|주차요금|주차료|대관료|수강료|회비|요금)\s*(수입)?$/g, '').replace(/\(.*?\)/g, '').trim() || s;
    let n = 0; const seen = new Set(org.facilities.map(f => f.name));
    for (const r of g.rows.filter(x => !x.grant && FAC_KEYS.has(x.vat_key)).sort((a, b) => b.amount_k - a.amount_k)) {
      const it = (D.revenue_items ?? []).find(i => i.key === r.vat_key); const type = it?.type && D.facilities.some(f => f.key === it.type) ? it.type : (D.facilities.some(f => f.key === r.vat_key) ? r.vat_key : 'use_permit');
      const name = clean(r.item); if (seen.has(name)) continue; seen.add(name);
      org.facilities.push({ id: uid(), type, name: name.slice(0, 40), run: 'unknown' as Run, income: ['card'], deposit: false, contractor_dept: '', kind: org.kind ?? 'gov', note: `[세입예산서 ${g.year}] ${r.dept} · ${r.mok_code} ${r.mok} · ${r.item} ${r.amount_k.toLocaleString('ko-KR')}천원 — 운영 방식·등록번호 확인` }); n++;
    }
    document.querySelectorAll<HTMLInputElement>('input[name=st-type]').forEach(c => { c.checked = org.facilities.some(f => f.type === c.value); });
    save(); alert(`${n}곳을 시설 후보로 넣었습니다. 3단계에서 운영 방식·등록번호를 채우고 필요 없는 것은 지우세요.`); show(3);
  });
  /* 3단계 */
  const facBox = $('st-fac')!;
  function renderFac() {
    if (!org.facilities.length) { facBox.innerHTML = '<p class="empty">2단계에서 시설을 고르세요.</p>'; return; }
    facBox.innerHTML = org.facilities.map(f => { f.kind = org.kind ?? 'gov'; const r = facilityRule(D, f); const C = org.kind === 'contractor'; const st0 = (C ? (r?.contractor_status === 'none' ? 'exempt' : r?.contractor_status) : r?.status) ?? r?.status ?? 'check'; const st = st0; return `<div class="vc-form" data-fid="${f.id}">
      <p class="q-title full"><span class="verdict ${st}">${st === 'taxable' ? '과세' : st === 'exempt' ? '면세' : '확인 필요'}</span> ${esc(r?.name ?? '직접 추가')}${C ? ' <span class="note">수탁기관 기준' + (r?.contractor_note ? ' — ' + esc(r.contractor_note) : '') + '</span>' : r?.interp ? '<span class="vbadge">유권해석·분류 확인</span>' : ''}</p>
      <label>시설 이름 <input type="text" data-k="name" value="${esc(f.name)}" maxlength="40" /></label>
      <label>운영 방식 <select data-k="run">${(Object.keys(RUN_NAME) as Run[]).filter(k => !(C && k === 'entrusted_own')).map(k => `<option value="${k}" ${f.run === k ? 'selected' : ''}>${runName(org.kind, k)}</option>`).join('')}</select></label>
      <label>${C ? '담당 부서·위탁 부서(부서명만)' : '수탁기관·담당 부서(위탁일 때, 부서명만)'} <input type="text" data-k="contractor_dept" value="${esc(f.contractor_dept ?? '')}" placeholder="${C ? '예: 체육사업팀 / 군 ○○과' : '예: 시설관리공단 체육사업팀'}" /></label>
      <label class="full" data-fee-q ${f.run === 'entrusted_own' && !C ? '' : 'hidden'}>수탁기관 자기 사업일 때 — 우리 기관이 수탁기관에게 받는 것 <select data-k="fee">${(Object.keys(FEE_NAME) as Fee[]).map(k => `<option value="${k}" ${(f.fee ?? 'unknown') === k ? 'selected' : ''}>${FEE_NAME[k]}</option>`).join('')}</select><span class="note">사용료·임대료를 받아 과세로 신고하고 있을 때만 우리 기관이 이 시설에 직접 낸 돈(수선·장비)의 부가세를 공제할 수 있습니다. 받지만 과세 신고 여부를 모르면 노랑, 무상이면 불공제. <strong>무상 → 유상(과세)으로 바꾸면</strong> 그 전에 산 건물·설비의 불공제 매입세액을 과세사업 전환 매입세액(시행령 제85조)으로 일부 되살릴 수 있습니다 — <a href="/vat/prepare/#p-convert">신고 준비의 전환 계산기</a>.</span></label>
      ${st === 'check' ? `<label class="full">확인 결과·근거(유권해석·질의회신 번호, 결정일 — 정해졌으면 위 시설 유형을 과세·면세 유형으로 바꾸고 여기 근거를 남깁니다) <input type="text" data-k="decision" value="${esc(f.decision ?? '')}" maxlength="120" placeholder="예: 2026-09-01 세무서 질의회신 ○○, 과세로 처리" /></label>` : ''}
      ${org.unit === 'site' ? `<label>이 시설(사업장)의 사업자등록번호 <input type="text" data-k="reg_no" value="${esc(f.reg_no ?? '')}" placeholder="000-00-00000" inputmode="numeric" /></label>` : ''}
      <div class="q"><span class="q-title" style="font-size:var(--small)">수입은 어떻게 받나요(여럿)</span><div class="choices">
        <label><input type="checkbox" data-inc="invoice" ${f.income.includes('invoice') ? 'checked' : ''}/> 세금계산서 발급(기관·법인 손님)</label>
        <label><input type="checkbox" data-inc="card" ${f.income.includes('card') ? 'checked' : ''}/> 카드·현금영수증(개인 손님)</label>
        <label><input type="checkbox" data-k="deposit" ${f.deposit ? 'checked' : ''}/> 임대 보증금을 받는다</label></div></div>
      <div class="actions"><button type="button" class="link-btn" data-dup>같은 유형 하나 더</button><button type="button" class="link-btn" data-del>이 시설 빼기</button></div>
      ${f.note ? `<p class="note full">예시 출처 메모: ${esc(f.note)}</p>` : ''}${r?.note ? `<p class="note full">${esc(r.note)}</p>` : ''}</div>`; }).join('');
    facBox.querySelectorAll<HTMLSelectElement>('select[data-k=run]').forEach(sel => sel.addEventListener('change', () => { const q = sel.closest<HTMLElement>('[data-fid]')!.querySelector<HTMLElement>('[data-fee-q]'); if (q) q.hidden = sel.value !== 'entrusted_own'; }));
    facBox.querySelectorAll<HTMLButtonElement>('[data-dup]').forEach(b => b.addEventListener('click', () => { read3(); const f = org.facilities.find(x => x.id === b.closest<HTMLElement>('[data-fid]')!.dataset.fid)!; org.facilities.splice(org.facilities.indexOf(f) + 1, 0, { ...f, id: uid(), name: f.name + ' 2', reg_no: '' }); renderFac(); }));
    facBox.querySelectorAll<HTMLButtonElement>('[data-del]').forEach(b => b.addEventListener('click', () => { read3(); org.facilities = org.facilities.filter(x => x.id !== b.closest<HTMLElement>('[data-fid]')!.dataset.fid); renderFac(); }));
  }
  const read3 = () => { facBox.querySelectorAll<HTMLElement>('[data-fid]').forEach(box => { const f = org.facilities.find(x => x.id === box.dataset.fid); if (!f) return; box.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-k]').forEach(el => { const k = el.dataset.k!; if (k === 'deposit') f.deposit = (el as HTMLInputElement).checked; else (f as unknown as Record<string, unknown>)[k] = el.value.trim(); }); f.income = [...box.querySelectorAll<HTMLInputElement>('[data-inc]:checked')].map(c => c.dataset.inc!); }); };
  const read4 = () => { org.handover_day = Math.min(28, Math.max(1, Number(($<HTMLInputElement>('st-day')!).value) || 5)); };

  /* 5단계 */
  function renderResult() {
    const rows = org.facilities.map(f => { const st = facilityStatus(D, f); return `<tr><th scope="row">${esc(f.name)}</th><td><span class="verdict ${st === 'agency' ? 'none' : st}">${STATUS_LABEL_SHORT[st]}</span></td><td>${f.run === 'unknown' ? '<span class="verdict check">운영 방식 확인</span> ' : ''}${esc(runName(org.kind, f.run))}${f.contractor_dept ? ' · ' + esc(f.contractor_dept) : ''}${f.run === 'entrusted_own' ? ` · 받는 것: ${esc(FEE_NAME[f.fee ?? 'unknown'].split('(')[0])}` : ''}${f.decision ? ` · 근거: ${esc(f.decision)}` : ''}</td><td>${esc(org.unit === 'entity' ? (org.reg_no || '—') : (f.reg_no || '—'))}</td><td>${f.income.map(i => i === 'invoice' ? '세금계산서' : '카드·현금영수증').join('·')}${f.deposit ? ' · 보증금' : ''}</td></tr>`; }).join('');
    $('st-summary')!.innerHTML = `<p><strong>${esc(org.org || '(기관 이름 없음)')}</strong>${org.kind === 'contractor' ? ` <span class="verdict check">수탁기관${org.parent ? ' · 위탁기관 ' + esc(org.parent) : ''}</span>` : ''} · ${esc(org.dept || '부서 없음')} · ${org.unit === 'entity' ? '사업자 단위 과세' : '사업장별 등록'} · 인계표 매달 ${org.handover_day}일까지 · 저장 ${org.created}</p>
      <div class="scroll-x"><table class="data-table vat-table" data-stack="off"><caption>${esc(org.org)} 과세사업 시설 설정</caption><thead><tr><th scope="col">시설</th><th scope="col">부가세</th><th scope="col">운영</th><th scope="col">세금계산서 받을 번호</th><th scope="col">수입 종류</th></tr></thead><tbody>${rows || '<tr><td colspan="5">시설 없음</td></tr>'}</tbody></table></div>`;
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
  $('st-reset')?.addEventListener('click', () => { if (!confirm('이 브라우저의 기관 설정을 지우고 처음부터 합니다. 내려받은 파일은 남습니다.')) return; setOrg(null); org = { v: 1, org: '', dept: '', unit: 'site', facilities: [], handover_day: 5, created: ymd(new Date()) }; fill1(); ($<HTMLInputElement>('st-other')!).value = ''; show(1); });
  $<HTMLInputElement>('st-open')?.addEventListener('change', async e => { const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return; try { const o = await readJsonFile(f) as Org; if (!o || o.v !== 1 || !Array.isArray(o.facilities)) throw new Error('형식'); org = o; save(); fill1(); $('st-loaded')!.textContent = `열었습니다: ${o.org} · 시설 ${o.facilities.length}곳`; show(5); } catch { $('st-loaded')!.textContent = '기관 설정 파일(org.json)이 아닙니다.'; } });
  fill1(); show(getOrg() ? 5 : 1);
}
