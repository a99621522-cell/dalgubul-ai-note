/** 기관 설정을 만드는 공용 조각(운영자 2026-10-28 '각 알고리즘별로 연결해야 돼 · 지금은 기관 선택에 아무것도 안 떠'):
 *  ① 예시(조례·의회 시설, data/vat/presets) → 시설 목록  ② 지자체 세입예산서(/vat-revenue.json) → 시설 후보(이미 있는 시설과 이름으로 합침)
 *  ③ 「기관 선택 → 바로 시작」 조각(quickStart): 기관 설정이 없는 화면(대시보드·지출 기록·신고 준비·과세사업 찾기)에서 기관을 고르면 그 자리에서 org 를 만들어 저장하고 화면을 잇는다.
 *  기관 설정 마법사(vat_setup.ts)도 같은 함수를 쓴다. 서버 없음, 개인정보 없음, 평가 없음. */
import { $, esc, uid, ymd, setOrg, toast, type Data, type Org, type OrgFacility, type Preset, type Run , findOrgNo, orgNoNote , type OrgNo } from './vat_rules';
import { applyAskDefaults } from './vat_ask';

export type RevRow = { mok_code: string; mok: string; dept: string; item: string; amount_k: number; vat_key: string; fac_key: string; grant: boolean };
export type ExpRow = { bureau: string; dept: string; detail: string; codes: string[]; facility: boolean; public_ops: boolean; grant: boolean; fac_key: string };
export type RevGov = { key: string; name: string; year: string; acct?: string; sum_k?: number; note?: string; rows: RevRow[]; expense: ExpRow[] };
/** 세입예산서 사업 가운데 '시설' 성격으로 보는 revenue_items 키 */
export const FAC_KEYS = new Set(['sports', 'golf', 'lodging', 'culture', 'venue', 'program', 'parking', 'water', 'funeral', 'transit', 'marina', 'lease_bldg', 'use_permit', 'food', 'vending', 'welfare', 'equip_rent', 'ad_space', 'waste_bag']);
export const facRows = (g: RevGov) => g.rows.filter(r => !r.grant && FAC_KEYS.has(r.vat_key));
let govsP: Promise<RevGov[]> | null = null;
/** /vat-revenue.json 을 한 번만 받는다(2MB). 실패하면 빈 목록 */
export const loadGovs = () => (govsP ??= fetch('/vat-revenue.json').then(r => r.json()).then((j: { govs: RevGov[] }) => j.govs ?? []).catch(() => [] as RevGov[]));
export const normN = (x: string) => x.replace(/\s|\(.*?\)|운영|관리|사업|비|지원|센터$/g, '').toLowerCase();
export const emptyOrg = (name = ''): Org => ({ v: 1, org: name, dept: '', unit: 'site', facilities: [], handover_day: 5, created: ymd(new Date()), kind: 'gov' });

/** 예시(조례·의회 의안·회의록으로 만든 시설 목록) → 시설. 운영 방식은 '확인 필요', 수탁기관은 이름만 */
export function presetFacilities(p: Preset): OrgFacility[] {
  const out = p.facilities.map(f => ({ id: uid(), type: f.type, name: f.name, ...(typeof f.share === 'number' ? { share: f.share } : {}), ...(f.alias?.length ? { alias: f.alias } : {}), run: (['direct', 'entrusted_org', 'entrusted_own'].includes(f.run ?? '') ? f.run : 'unknown') as Run, income: ['card'], deposit: false, contractor_dept: f.contractor ? `${f.contractor}(협약서 확인)` : f.op === '공단' ? `${p.org.replace(/^대구광역시\s*/, '')}시설관리공단(부서 확인)` : f.op === '재단' ? '재단(협약서 확인)' : '', note: (f.op ? `[${f.op}] ` : '') + (f.term ? `위탁 기간 ${f.term}(의회 동의안 제안설명 기준, 협약서로 확인). ` : '') + (f.note ?? ''), ...(f.alias?.length ? { alias: f.alias } : {}) }));
  out.forEach((f, i) => applyAskDefaults(f, p.facilities[i].ask));   // 확인 질문 기본값(vat_ask.ts)
  return out;
}

/** 세입예산서의 시설 성격 사업을 시설 후보로. 이미 있는 시설(예시·직접 입력)과 이름이 서로 품거나 앞 6글자 이상 같으면 그 시설에 붙이고(rev·메모), 없는 것만 새로 넣는다(운영 방식 '확인 필요'). 반환: 새 시설 수·합친 시설 수·붙인 사업 수 */
export function addRevenueFacilities(D: Data, org: Org, g: RevGov) {
  const clean = (s: string) => s.replace(/\s*(수입|입장료|사용료|임대료|이용료|관람료|주차요금|주차료|대관료|수강료|회비|요금)\s*(수입)?$/g, '').replace(/\(.*?\)/g, '').trim() || s;
  const pref = (a: string, b: string) => { let n = 0; while (n < a.length && n < b.length && a[n] === b[n]) n++; return n; };
  const score = (fn: string, b: string) => { const a = normN(fn); if (a.length < 3 || b.length < 3) return 0; if (b.includes(a) || (a.length >= 4 && b.length >= 4 && a.includes(b))) return 100 + Math.min(a.length, b.length); const p = pref(a, b); return p >= 6 && a.length > p && b.includes(a.slice(p)) ? p + 20 : 0; };
  const pick = (item: string) => { const b = normN(clean(item)); let best: OrgFacility | undefined, bs = 0; for (const f of org.facilities) { const sc = Math.max(score(f.name, b), ...(f.alias ?? []).map(x => score(x, b))); if (sc > bs) { bs = sc; best = f; } } return best; };
  let n = 0, k = 0; const merged = new Set<string>(); const seen = new Set(org.facilities.map(f => f.name));
  for (const r of facRows(g).sort((a, b) => b.amount_k - a.amount_k)) {
    const line = `[세입예산서 ${g.year}] ${r.dept} · ${r.mok_code} ${r.mok} · ${r.item} ${r.amount_k.toLocaleString('ko-KR')}천원`;
    const hit = pick(r.item);
    if (hit) { hit.rev = hit.rev ?? []; if (hit.rev.includes(r.item)) continue; hit.rev.push(r.item); hit.note = (hit.note ? hit.note.replace(/\s*$/, ' ') : '') + line + '.'; merged.add(hit.id); k++; continue; }
    const it = (D.revenue_items ?? []).find(i => i.key === r.vat_key); const type = it?.type && D.facilities.some(f => f.key === it.type) ? it.type : (D.facilities.some(f => f.key === r.vat_key) ? r.vat_key : 'use_permit');
    const name = clean(r.item); if (seen.has(name)) continue; seen.add(name);
    org.facilities.push({ id: uid(), type, name: name.slice(0, 40), run: 'unknown' as Run, income: ['card'], deposit: false, contractor_dept: '', kind: org.kind ?? 'gov', rev: [r.item], note: `${line} — 운영 방식·등록번호 확인` }); n++;
  }
  return { n, merged: merged.size, k };
}

/** 「기관 선택 → 바로 시작」 조각. 선택지 = 예시(preset) + 세입예산서 지자체. 고르고 누르면 org 를 만들어 저장하고 onDone(org) */
/** 공개 자료의 기관 번호를 시설마다 채운다(운영자 지시 2026-11-03 '기관번호를 넣어 그것은 할 수 있잖아'): 비어 있는 시설 등록번호는 본청 번호로(사업장별로 따로 등록한 시설이면 담당자가 고친다 — 메모에 출처), 수탁기관 칸에 적힌 공단·재단 이름이 공개 자료에 있으면 그 번호를 덧붙인다 */
export function fillFacilityNos(D: Data, org: Org, on: OrgNo) {
  let n = 0, c = 0;
  for (const f of org.facilities) {
    if (!f.reg_no && f.run !== 'entrusted_own') { f.reg_no = on.bizno; f.note = (f.note ? f.note + ' ' : '') + `등록번호는 본청 번호(${on.verify ? '2차 자료' : '나라장터'}) — 이 시설이 사업장별로 따로 등록돼 있으면 그 번호로 고치기.`; n++; }
    if (f.contractor_dept) { const nm = f.contractor_dept.replace(/\(.*?\)/g, '').trim(); const co = nm ? findOrgNo(D, nm) : undefined; if (co && !f.contractor_dept.includes(co.bizno)) { f.contractor_dept = f.contractor_dept.replace(nm, `${nm} ${co.bizno}`); c++; } }
  }
  return { n, c };
}
export const quickStartHtml = (id: string, lead = '기관을 고르면 그 기관의 시설·공개 자료를 불러와 바로 이어집니다.') =>
  `<div class="vat-qs vc-form" id="${id}" data-qs><p class="q-title full">기관 선택 → 바로 시작</p><p class="note full">${esc(lead)}</p><label>기관 <select data-qs-sel aria-label="기관 선택"><option value="">불러오는 중…</option></select></label><div class="actions"><button type="button" class="btn" data-qs-go disabled>이 기관으로 시작</button></div><p class="note full" data-qs-msg role="status"></p></div>`;
/** 기관 설정 만들기 — v: 'preset:<key>' | 'gov:<key>' | '<key>'(예시가 있으면 예시, 없으면 세입예산서). 예시 시설·세입예산서 시설 후보·기관 번호·확인 질문 기본값을 넣는다(저장은 부르는 쪽) */
export async function makeOrg(D: Data, v: string): Promise<Org> {
  const presets = D.presets ?? []; const govs = await loadGovs(); const org = emptyOrg();
  const [kind, key] = v.includes(':') ? v.split(':') : [presets.some(p => p.key === v) ? 'preset' : 'gov', v];
  const p = presets.find(x => x.key === key); const g = govs.find(x => x.key === key);
  if (kind === 'preset' && p) { org.org = p.org; org.facilities = presetFacilities(p); }
  if (g) { if (!org.org) org.org = g.name; addRevenueFacilities(D, org, g); try { localStorage.setItem('vat-gov', g.key); } catch { /* */ } }
  if (!org.org) { const gp = D.govs?.find(x => x.key === key); if (gp) { org.org = gp.name; try { localStorage.setItem('vat-gov', key); } catch { /* */ } } }
  org.facilities.forEach(f => { f.kind = 'gov'; }); const on = findOrgNo(D, org.org); if (on) { org.reg_no = on.bizno; org.reg_src = orgNoNote(on); fillFacilityNos(D, org, on); }
  return org;
}
/** 링크 한 번으로 시작(?gov=dalseong) — 이 브라우저에 기관 설정이 없을 때만 만든다. 만들었으면 true */
export async function startFromLink(D: Data): Promise<boolean> {
  let key = ''; try { key = new URLSearchParams(location.search).get('gov') ?? ''; } catch { /* */ }
  if (!/^[a-z]+$/.test(key)) return false; let has = false; try { has = !!localStorage.getItem('vat-org-v1'); } catch { /* */ }
  if (has) return false; const known = (D.presets ?? []).some(p => p.key === key) || (D.govs ?? []).some(g => g.key === key) || (await loadGovs()).some(g => g.key === key); if (!known) return false;
  setOrg(await makeOrg(D, key)); try { localStorage.setItem('vat-gov', key); } catch { /* */ } return true;
}
export function wireQuickStart(root: ParentNode, D: Data, onDone: (o: Org) => void, preferGov?: string | null) {
  root.querySelectorAll<HTMLElement>('[data-qs]:not([data-wired])').forEach(box => { box.dataset.wired = '1';
    const sel = box.querySelector<HTMLSelectElement>('[data-qs-sel]')!, go = box.querySelector<HTMLButtonElement>('[data-qs-go]')!, msg = box.querySelector<HTMLElement>('[data-qs-msg]')!;
    const presets = D.presets ?? [];
    const draw = (govs: RevGov[]) => {
      const opts: string[] = ['<option value="">— 고르세요 —</option>'];
      if (D.govs?.length) { for (const g of D.govs) { const v = presets.some(p => p.key === g.key) ? `preset:${g.key}` : `gov:${g.key}`; const bits = [g.status, g.preset ? `예시 시설 ${g.preset}곳` : '', g.revenue ? `세입예산서 ${g.revenue}줄` : '', g.contracts?.n ? `나라장터 계약 ${g.contracts.n.toLocaleString('ko-KR')}건` : ''].filter(Boolean);
          opts.push(`<option value="${esc(v)}">${esc(g.name)} — ${esc(bits.join(' · '))}</option>`); }
        opts.push('<option value="blank">그 밖의 기관 — 이름만 적고 시설은 직접</option>'); sel.innerHTML = opts.join(''); go.disabled = false;
        let saved = ''; try { saved = localStorage.getItem('vat-gov') || ''; } catch { /* */ } const want = preferGov || saved; if (want) { const o = [...sel.options].find(x => x.value.endsWith(`:${want}`)); if (o) sel.value = o.value; }
        if (!sel.value) sel.value = presets.length ? `preset:${presets[0].key}` : ''; return; }
      for (const p of presets) opts.push(`<option value="preset:${esc(p.key)}">${esc(p.org)} — 예시(조례·의회 시설 ${p.facilities.length}곳${govs.some(g => g.key === p.key) ? ' + 세입예산서 후보' : ''})</option>`);
      for (const g of govs) { if (presets.some(p => p.key === g.key)) continue; opts.push(`<option value="gov:${esc(g.key)}">${esc(g.name)} — ${g.year}년 세입예산서 시설 후보 ${facRows(g).length}곳${g.note ? ' (자료 한계)' : ''}</option>`); }
      opts.push('<option value="blank">그 밖의 기관 — 이름만 적고 시설은 직접</option>');
      sel.innerHTML = opts.join(''); go.disabled = false;
      let saved = ''; try { saved = localStorage.getItem('vat-gov') || ''; } catch { /* */ }
      const want = preferGov || saved; if (want) { const v = presets.some(p => p.key === want) ? `preset:${want}` : govs.some(g => g.key === want) ? `gov:${want}` : ''; if (v) sel.value = v; }
      if (!sel.value && presets.length) sel.value = `preset:${presets[0].key}`;
    };
    loadGovs().then(draw);
    go.addEventListener('click', async () => {
      const v = sel.value; if (!v) { msg.textContent = '기관을 고르세요.'; sel.focus(); return; }
      let org: Org;
      if (v === 'blank') { const name = window.prompt('기관 이름(예: ○○군)'); if (!name) return; org = emptyOrg(name.trim()); org.facilities.forEach(f => { f.kind = 'gov'; }); }
      else org = await makeOrg(D, v);
      const on = findOrgNo(D, org.org); setOrg(org);
      toast(`${org.org} 기관 설정을 만들었습니다 — 시설 ${org.facilities.length}곳${on ? ` · 기관 번호 ${on.bizno}(${on.verify ? '2차 자료, 확인 필요' : '나라장터'})를 시설마다 넣었습니다` : ''}(운영 방식은 기관 설정에서, 사업장별로 따로 등록한 시설은 번호를 고치세요)`); msg.textContent = `${org.org} · 시설 ${org.facilities.length}곳으로 시작합니다.`; onDone(org);
    });
  });
}
/** 편의: 특정 요소 안에 조각을 그리고 바로 연결 */
export function mountQuickStart(el: HTMLElement | null, D: Data, onDone: (o: Org) => void, id = 'vat-qs', preferGov?: string | null) { if (!el) return; el.innerHTML = quickStartHtml(id); wireQuickStart(el, D, onDone, preferGov); void $; }
