/** 돌려받기 — '공개 지출 자료로 후보 찾기'(붙여넣기 없음, 운영자 2026-11-03 '홈택스 붙여넣는 것은 공무원이 안 할 것 같은데 방법을 찾아봐').
 *  대구 주민참여 재정 포털의 지출건별 공개 자료(data/vat/expense, 과세기간×부서×세부사업×통계목 집계 — 거래처·세액 없음)를 지자체만 고르면 받아
 *  세부사업마다 어느 시설 지출인지 정하고(매핑표·시설 이름 일치로 먼저 채움, 고른 것은 매핑표에 남아 뒤에 세금계산서 목록을 넣을 때 자동 귀속)
 *  통계목 성격(MOK_CLASS)으로 매입세액이 있을 법한 지출만 골라 과세기간×시설의 '세액 추정'(지출액 × 10/110)과 공제 대상 추정을 보인다.
 *  결과는 '어느 부서의 어느 사업 세금계산서만 받아오면 되나' 목록(CSV·요청 메모) — 실제 청구는 그 세금계산서로. 새 규칙 없음, 판정은 참고 */
import { $, esc, fmt, matchMap, matchFacilityName, facilityStatus, learnMap, setOrg, toCsv, downloadText, toast, claimPeriod, ymd, type Data, type Org, type OrgFacility } from './vat_rules';

type Agg = { p: string; acct: string; dept: string; biz: string; mok: string; n: number; amt: number; card: number; petty: number; max: number; memo: string[] };
type Gov = { key: string; name: string; fetched: string; periods: string[]; days: string[]; failed_days: string[]; note: string; source: string; rows: Agg[] };
type GovMeta = { key: string; name: string; fetched: string; periods: string[]; days: number; rows: number; note: string };
type Cls = 'vat' | 'check' | 'no' | 'none';
/** 통계목 → 매입세액 성격. vat: 재화·용역을 사서 세금계산서·카드 전표를 받는 지출 / check: 위탁·대행 — 수탁자가 과세사업자면 세금계산서(공단·공사 대행은 조특법 면제) / no: 불공제(업무추진비·여비) / none: 인건비·보상금·보조금·반환금 등 매입세액이 없는 지출 */
export const MOK_CLASS: { re: RegExp; cls: Cls }[] = [
  { re: /업무추진비|여비|특정업무경비|직급보조|정원가산/, cls: 'no' },
  { re: /위탁|대행|행사실비지원/, cls: 'check' },
  { re: /사무관리비|공공운영비|행사운영비|재료비|연구개발비|시설비|감리비|시설부대비|행사관련시설비|자산.*취득비|물품취득|차량선박비|임차료|시설장비유지비|복지제도시행경비|운영비$/, cls: 'vat' },
  { re: /./, cls: 'none' }];
export const mokClass = (mok: string): Cls => MOK_CLASS.find(m => m.re.test(mok))!.cls;
const CLS_NAME: Record<Cls, string> = { vat: '매입세액 있을 법함', check: '위탁·대행(확인)', no: '불공제 통계목', none: '매입세액 없음(인건비·보조금 등)' };
type Asg = { fid: string; use: 'this' | 'multi' | 'admin' };
type PubState = { v: 1; gov: string; asg: Record<string, Asg> };
const KEY = 'vat-pub-v1';

export async function mountPublic(root: HTMLElement, D: Data, org: Org | null, hooks: { er: (pkey: string) => number | null; onLearn?: () => void }) {
  const st: PubState = (() => { try { const j = JSON.parse(localStorage.getItem(KEY) || 'null'); return j && j.v === 1 ? j : { v: 1, gov: '', asg: {} }; } catch { return { v: 1, gov: '', asg: {} }; } })();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch { /* */ } };
  let metas: GovMeta[] = [];
  try { const r = await fetch('/vat-expense/index.json'); metas = ((await r.json()) as { govs: GovMeta[] }).govs ?? []; } catch { /* */ }
  const guess = () => { if (st.gov) return st.gov; let g = ''; try { g = localStorage.getItem('vat-gov') || ''; } catch { /* */ } if (g && metas.some(m => m.key === g)) return g; const nm = (org?.org ?? '').replace(/\s/g, ''); return metas.find(m => nm && (nm.includes(m.name) || m.name.includes(nm.replace(/대구광역시|청$/g, ''))))?.key ?? ''; };
  root.innerHTML = `<p class="callout info"><strong>붙여넣기 없이 가는 길.</strong> 대구광역시 주민참여 재정 포털이 공개한 <strong>지출건별 자료</strong>(부서·세부사업·통계목·지출액·지급일자)를 지자체만 고르면 이 화면이 받아, 어느 사업 지출이 과세 시설 지출인지 정하고 <strong>돌려받을 수 있는 세액의 상한을 추정</strong>합니다. 거래처·세액 칸이 없는 자료라 세액은 지출액 × 10/110 추정이고, 실제 청구는 그 사업의 세금계산서로 합니다(마지막에 '어느 부서의 어느 사업 세금계산서만 받아오면 되나' 목록이 나옵니다).</p>
    <div class="vc-form"><label>지자체 <select id="pub-gov"><option value="">— 고르기 —</option>${metas.map(m => `<option value="${esc(m.key)}" ${guess() === m.key ? 'selected' : ''}>${esc(m.name)} (${esc(m.periods[0] ?? '')}~${esc(m.periods[m.periods.length - 1] ?? '')}, ${m.rows.toLocaleString()}묶음)</option>`).join('')}</select></label><div class="actions"><button type="button" class="btn" id="pub-load">공개 지출 자료 불러오기</button><span class="note" id="pub-stat">${metas.length ? '' : '공개 지출 자료가 아직 없습니다(러너가 모으는 중)'}</span></div></div>
    <div id="pub-body"></div>`;
  const sel = $<HTMLSelectElement>('pub-gov')!; let gov: Gov | null = null;
  const load = async () => { const k = sel.value; if (!k) { toast('지자체를 고르세요'); return; } $('pub-stat')!.textContent = '받는 중…'; try { gov = (await (await fetch(`/vat-expense/${k}.json`)).json()) as Gov; st.gov = k; save(); $('pub-stat')!.textContent = `${gov.name} — ${gov.periods.join('·')} · 지급일 ${gov.days.length}일치 · 받은 날 ${gov.fetched}`; build(); } catch { $('pub-stat')!.textContent = '받지 못했습니다'; } };
  $('pub-load')!.addEventListener('click', load);
  if (sel.value && (st.gov === sel.value || !$('rv-result')?.textContent?.trim())) void load();

  type Biz = { key: string; dept: string; biz: string; periods: Set<string>; n: number; amt: Record<Cls, number>; moks: Map<string, number>; memos: string[]; card: number; rows: Agg[] };
  let filter: 'todo' | 'done' | 'all' = 'todo'; let q = '';
  const FIDS = () => [{ id: 'none', name: '— 모름' }, ...(org?.facilities.filter(f => f.track !== false).map(f => ({ id: f.id, name: `${f.name} [${({ taxable: '과세', exempt: '면세', check: '확인', own: '수탁', agency: '대행' } as Record<string, string>)[facilityStatus(D, f)]}]` })) ?? []), { id: 'admin', name: '본청·행정 공통(과세 시설과 함께)' }, { id: 'exempt', name: '면세·행정 전용(공제 없음)' }];
  const fidSel = (cur: string | undefined, attr: string) => `<select ${attr} aria-label="시설"><option value="">(지정 안 함)</option>${FIDS().map(o => `<option value="${o.id}" ${cur === o.id ? 'selected' : ''}>${esc(o.name)}</option>`).join('')}</select>`;
  const auto = (b: Biz): Asg | undefined => { if (!org) return undefined; const m = matchMap(org, b.biz, b.dept); if (m) return { fid: m.fid, use: m.use === 'multi' || m.use === 'admin' ? m.use : 'this' }; const f = matchFacilityName(org, b.biz, b.dept); return f ? { fid: f.id, use: 'this' } : undefined; };   // 적요는 보지 않는다 — '비슬산 …' 같은 지명이 여러 사업 적요에 나와 엉뚱한 시설에 붙는다
  const asgOf = (b: Biz): { a: Asg | undefined; how: '지정' | '자동' | '' } => st.asg[b.key] ? { a: st.asg[b.key], how: '지정' } : (() => { const a = auto(b); return { a, how: a ? '자동' : '' as const }; })();
  function build() {
    if (!gov) return; const body = $('pub-body')!;
    const bizs = new Map<string, Biz>();
    for (const r of gov.rows) { const k = `${r.dept}|${r.biz}`; const b = bizs.get(k) ?? { key: k, dept: r.dept, biz: r.biz, periods: new Set(), n: 0, amt: { vat: 0, check: 0, no: 0, none: 0 }, moks: new Map(), memos: [], card: 0, rows: [] }; const c = mokClass(r.mok); b.periods.add(r.p); b.n += r.n; b.amt[c] += r.amt; b.moks.set(r.mok, (b.moks.get(r.mok) ?? 0) + r.amt); b.card += r.card; for (const m of r.memo) if (b.memos.length < 3 && !b.memos.includes(m)) b.memos.push(m); b.rows.push(r); bizs.set(k, b); }
    const all = [...bizs.values()].filter(b => b.amt.vat + b.amt.check > 0).sort((x, y) => (y.amt.vat + y.amt.check) - (x.amt.vat + x.amt.check));
    const done = all.filter(b => asgOf(b).a); const sumV = (L: Biz[]) => L.reduce((s, b) => s + b.amt.vat + b.amt.check, 0);
    const vis = all.filter(b => (filter === 'all' || (filter === 'todo' ? !asgOf(b).a : !!asgOf(b).a)) && (!q || (b.biz + b.dept + b.memos.join(' ')).includes(q)));
    /* 결과: 과세기간 × 시설 */
    type Cell = { amt: number; est: number; claim: number | null; n: number };
    const per = new Map<string, Map<string, Cell>>(); const facName = (id: string) => id === 'admin' ? '본청·행정 공통' : id === 'exempt' ? '면세·행정 전용' : id === 'none' ? '모름' : (org?.facilities.find(f => f.id === id)?.name ?? id);
    const rateOf = (a: Asg, p: string, f?: OrgFacility): number | null => { if (a.fid === 'exempt') return 0; if (a.fid === 'none') return null; if (a.fid === 'admin' || a.use !== 'this') { const er = hooks.er(p); return er === null ? null : 1 - er / 100; } if (!f) return null; const s = facilityStatus(D, f); return s === 'taxable' ? 1 : s === 'exempt' || s === 'own' || s === 'agency' ? 0 : null; };
    const want: { dept: string; biz: string; p: string; n: number; amt: number; fac: string; note: string }[] = [];
    for (const b of done) { const a = asgOf(b).a!; const f = org?.facilities.find(x => x.id === a.fid); for (const r of b.rows) { const c = mokClass(r.mok); if (c !== 'vat' && c !== 'check') continue; const rate = rateOf(a, r.p, f); const est = Math.floor(r.amt * 10 / 110); const pm = per.get(r.p) ?? new Map<string, Cell>(); const cell = pm.get(a.fid) ?? { amt: 0, est: 0, claim: 0, n: 0 }; cell.amt += r.amt; cell.est += est; cell.n += r.n; cell.claim = rate === null || cell.claim === null ? (rate === null ? null : cell.claim) : cell.claim + Math.floor(est * rate); pm.set(a.fid, cell); per.set(r.p, pm); if (rate === null || rate > 0) want.push({ dept: r.dept, biz: r.biz, p: r.p, n: r.n, amt: r.amt, fac: facName(a.fid), note: c === 'check' ? `${r.mok} — 수탁자가 과세사업자면 세금계산서` : r.mok }); } }
    const periods = [...per.keys()].sort(); const today = ymd(new Date());
    const tot = (f: (c: Cell) => number | null) => periods.reduce((s, p) => s + [...per.get(p)!.values()].reduce((x, c) => x + (f(c) ?? 0), 0), 0);
    const claimTot = tot(c => c.claim), estTot = tot(c => c.est), unknownTot = tot(c => c.claim === null ? c.est : 0);
    const pInfo = (k: string) => claimPeriod(`${k.split('-')[0]}-${k.split('-')[1] === '1' ? '03' : '09'}-01`)!; const pName = (k: string) => `${k.split('-')[0]}년 제${k.split('-')[1]}기`;
    body.innerHTML = `<div class="section-head"><h3>세부사업마다 어느 시설 지출인지</h3><span class="meta">매입세액이 있을 법한 지출이 있는 세부사업 ${all.length}개 · 지정 ${done.length}개 · 금액 기준 ${sumV(all) ? Math.round(sumV(done) / sumV(all) * 100) : 0}%</span></div>
      <p class="note">지출액이 큰 사업부터 시설을 고르세요. 기관 설정의 시설 이름·매핑표와 맞는 사업은 이미 들어가 있고, 여기서 고른 것은 매핑표에 남아 나중에 세금계산서 목록을 넣을 때 자동으로 귀속됩니다. 통계목 가운데 ${esc(CLS_NAME.vat)}·${esc(CLS_NAME.check)}만 셉니다(인건비·보조금·보상금·업무추진비·여비는 제외).</p>
      <div class="filters" role="group" aria-label="거르기">${(['todo', 'done', 'all'] as const).map(f => `<button type="button" class="chip" data-pf="${f}" aria-pressed="${filter === f}">${f === 'todo' ? `미지정 ${all.length - done.length}` : f === 'done' ? `지정됨 ${done.length}` : `전체 ${all.length}`}</button>`).join('')} <input type="search" id="pub-q" placeholder="사업·부서·적요 찾기" value="${esc(q)}" style="max-width:16em" /></div>
      <div class="actions"><label><input type="checkbox" id="pub-sel-all" /> 보이는 사업 모두 선택</label> ${fidSel(undefined, 'id="pub-bk-fid"')} <select id="pub-bk-use" aria-label="용도"><option value="this">이 시설만</option><option value="multi">여러 시설이 같이</option><option value="admin">행정 일과 함께</option></select> <button type="button" class="btn secondary" id="pub-bk-apply">선택한 사업에 적용</button></div>
      <div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table" data-stack="off" id="pub-biz"><caption>세부사업별 — 공개 지출 자료(${esc(gov.name)}, ${esc(gov.periods[0])}~${esc(gov.periods[gov.periods.length - 1])}), 매입세액이 있을 법한 통계목 지출액 순</caption><thead><tr><th scope="col"><span class="sr-only">선택</span></th><th scope="col">부서</th><th scope="col">세부사업</th><th scope="col">통계목(지출액 큰 순)</th><th scope="col">지출액(매입세액 가능)</th><th scope="col">위탁·대행</th><th scope="col">건</th><th scope="col">시설</th><th scope="col">용도</th><th scope="col">적요 본보기</th></tr></thead><tbody>${vis.slice(0, 300).map(b => { const { a, how } = asgOf(b); return `<tr data-bk="${esc(b.key)}"><td><input type="checkbox" data-psel="${esc(b.key)}" /></td><td>${esc(b.dept)}</td><th scope="row">${esc(b.biz)}${how === '자동' ? '<br><span class="vbadge">이름 일치</span>' : ''}${b.card ? `<br><span class="note">카드결제 ${b.card}건</span>` : ''}</th><td class="note">${[...b.moks.entries()].sort((x, y) => y[1] - x[1]).slice(0, 3).map(([m, v]) => `${esc(m)} ${fmt(v)}`).join('<br>')}</td><td>${fmt(b.amt.vat)}</td><td>${b.amt.check ? fmt(b.amt.check) : '—'}</td><td>${b.n}</td><td>${fidSel(a?.fid, `data-pb-fid="${esc(b.key)}"`)}</td><td><select data-pb-use="${esc(b.key)}" aria-label="용도"><option value="this" ${!a || a.use === 'this' ? 'selected' : ''}>이 시설만</option><option value="multi" ${a?.use === 'multi' ? 'selected' : ''}>여러 시설이 같이</option><option value="admin" ${a?.use === 'admin' ? 'selected' : ''}>행정 일과 함께</option></select></td><td class="note">${b.memos.map(esc).join('<br>')}</td></tr>`; }).join('')}</tbody></table></div>${vis.length > 300 ? `<p class="note">${vis.length}개 가운데 지출액이 큰 300개만 보입니다. 찾기로 줄이세요.</p>` : ''}
      <div class="section-head"><h3>상한 추정 — 과세기간 × 시설</h3><span class="meta">판정은 참고이며 기관의 판단이 아닙니다 · 세액은 지출액 × 10/110 추정</span></div>
      <div class="vc-cards"><div class="vc-card"><h3>공제 대상 추정(상한)</h3><p class="big" id="pub-claim">${fmt(claimTot)}<span class="note">원</span></p><p class="note">과세 시설 전용은 전액, 공통은 (1 − 면세비율)만큼 — ②에 과세기간 면세비율을 넣으면 공통이 계산됩니다</p></div><div class="vc-card"><h3>시설 지출의 세액 추정</h3><p class="big">${fmt(estTot)}<span class="note">원</span></p><p class="note">지정한 시설 지출(매입세액 가능 통계목) 전체의 10/110</p></div><div class="vc-card"><h3>아직 못 센 세액</h3><p class="big">${fmt(unknownTot)}<span class="note">원</span></p><p class="note">기준이 '확인'인 시설·면세비율 없는 공통·'모름'</p></div></div>
      ${periods.length ? `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table" data-stack="off" id="pub-per"><caption>과세기간별 추정 — 지정한 시설 지출만</caption><thead><tr><th scope="col">과세기간</th><th scope="col">시설</th><th scope="col">건</th><th scope="col">지출액</th><th scope="col">세액 추정</th><th scope="col">공제 대상 추정</th><th scope="col">경정청구 기한</th></tr></thead><tbody>${periods.flatMap(p => [...per.get(p)!.entries()].sort((x, y) => y[1].est - x[1].est).map(([fid, c]) => `<tr><th scope="row">${esc(pName(p))}</th><td>${esc(facName(fid))}</td><td>${c.n}</td><td>${fmt(c.amt)}</td><td>${fmt(c.est)}</td><td>${c.claim === null ? '<span class="vbadge">확인·면세비율 필요</span>' : fmt(c.claim)}</td><td>${pInfo(p).days < 0 ? '지남' : `${pInfo(p).claim} (D-${pInfo(p).days})`}</td></tr>`)).join('')}</tbody></table></div>` : '<p class="note">아직 시설을 지정한 사업이 없습니다. 위 표에서 지출액이 큰 사업부터 시설을 고르세요.</p>'}
      ${want.length ? `<div class="section-head"><h3>세금계산서를 받아올 사업 목록</h3><span class="meta">${want.length}줄 — 이 사업들의 세금계산서(전자) 목록만 있으면 됩니다</span></div>
      <p class="note">부서(또는 세무대리인)에 이 목록을 주고 그 사업·기간의 매입 세금계산서 목록(홈택스 전자세금계산서 목록조회 또는 e호조 지출 증빙)을 받아, 위 「파일 놓기」로 넣으면 매핑표로 자동 귀속되어 과세기간별 청구 후보가 건별로 나옵니다.</p>
      <textarea id="pub-memo" rows="7" class="full" readonly style="width:100%;padding:8px;border:1px solid var(--line-strong);border-radius:var(--radius);background:var(--bg);color:var(--ink);font:inherit">${esc(memoText(want, gov.name, today))}</textarea>
      <div class="actions no-print"><button type="button" class="btn" id="pub-csv">받아올 사업 목록 CSV</button><button type="button" class="btn secondary" id="pub-print">인쇄</button><button type="button" class="btn secondary" id="pub-copy">요청 메모 복사</button></div>` : ''}
      <p class="note">${esc(gov.note)} · 출처: ${esc(gov.source)}${gov.failed_days.length ? ` · 받지 못한 날 ${gov.failed_days.length}일` : ''}</p>`;
    /* 이벤트 */
    body.querySelectorAll<HTMLButtonElement>('[data-pf]').forEach(b => b.addEventListener('click', () => { filter = b.dataset.pf as typeof filter; build(); }));
    $<HTMLInputElement>('pub-q')?.addEventListener('change', e => { q = (e.target as HTMLInputElement).value.trim(); build(); });
    const set = (k: string) => { const b = bizs.get(k)!; const fid = body.querySelector<HTMLSelectElement>(`[data-pb-fid="${CSS.escape(k)}"]`)!.value; const use = body.querySelector<HTMLSelectElement>(`[data-pb-use="${CSS.escape(k)}"]`)!.value as Asg['use']; if (!fid) delete st.asg[k]; else { st.asg[k] = { fid, use }; if (org && fid !== 'none') { learnMap(org, b.biz, fid, use); setOrg(org); hooks.onLearn?.(); } } save(); build(); };
    body.querySelectorAll<HTMLSelectElement>('[data-pb-fid],[data-pb-use]').forEach(s => s.addEventListener('change', () => set(s.dataset.pbFid ?? s.dataset.pbUse!)));
    $<HTMLInputElement>('pub-sel-all')?.addEventListener('change', e => body.querySelectorAll<HTMLInputElement>('[data-psel]').forEach(c => { c.checked = (e.target as HTMLInputElement).checked; }));
    $('pub-bk-apply')?.addEventListener('click', () => { const fid = $<HTMLSelectElement>('pub-bk-fid')!.value; const use = $<HTMLSelectElement>('pub-bk-use')!.value as Asg['use']; const keys = [...body.querySelectorAll<HTMLInputElement>('[data-psel]:checked')].map(c => c.dataset.psel!); if (!keys.length) { toast('사업을 먼저 선택하세요'); return; } if (!fid) { toast('적용할 시설을 고르세요'); return; } for (const k of keys) { st.asg[k] = { fid, use }; const b = bizs.get(k); if (org && b && fid !== 'none') learnMap(org, b.biz, fid, use); } if (org) { setOrg(org); hooks.onLearn?.(); } save(); build(); toast(`${keys.length}개 사업에 적용했습니다`); });
    $('pub-csv')?.addEventListener('click', () => downloadText(`세금계산서-받아올-사업-${gov!.name}-${today}.csv`, toCsv([['부서', '세부사업', '과세기간', '건수', '지출액', '시설', '통계목·비고'], ...want.sort((x, y) => x.dept.localeCompare(y.dept) || y.amt - x.amt).map(w => [w.dept, w.biz, pName(w.p), w.n, w.amt, w.fac, w.note])]), 'text/csv;charset=utf-8'));
    $('pub-print')?.addEventListener('click', () => window.print());
    $('pub-copy')?.addEventListener('click', async () => { try { await navigator.clipboard.writeText($<HTMLTextAreaElement>('pub-memo')!.value); toast('복사했습니다'); } catch { toast('복사하지 못했습니다 — 글상자를 직접 선택해 복사하세요'); } });
  }
  function memoText(want: { dept: string; biz: string; p: string; n: number; amt: number; fac: string }[], govName: string, today: string) {
    const by = new Map<string, typeof want>(); for (const w of want) { const L = by.get(w.dept) ?? []; L.push(w); by.set(w.dept, L); }
    const pName = (k: string) => `${k.split('-')[0]}년 제${k.split('-')[1]}기`;
    return `[매입 세금계산서 목록 요청 — ${govName} 부가가치세 경정청구 준비, ${today}]\n아래 세부사업의 지출 가운데 세금계산서(전자·종이)·사업용 카드로 결제한 건의 목록(작성일자·공급자·등록번호·품목·공급가액·세액)을 과세기간별로 보내 주세요. 홈택스 「전자세금계산서 목록조회(매입)」 엑셀 또는 e호조 지출 증빙 목록이면 됩니다.\n\n` +
      [...by.entries()].map(([d, L]) => { const g = new Map<string, { ps: Set<string>; amt: number; fac: string }>(); for (const w of L) { const x = g.get(w.biz) ?? { ps: new Set(), amt: 0, fac: w.fac }; x.ps.add(w.p); x.amt += w.amt; g.set(w.biz, x); } return `■ ${d}\n` + [...g.entries()].sort((a, b) => b[1].amt - a[1].amt).map(([b, x]) => `  - ${b} (${[...x.ps].sort().map(pName).join('·')}, 지출 ${fmt(x.amt)}원, 시설: ${x.fac})`).join('\n'); }).join('\n') +
      `\n\n※ 공개 지출 자료(대구 주민참여 재정 포털)로 고른 사업입니다. 세금계산서가 없는 지출(인건비·보조금 등)은 제외했습니다. 담당자 이름·연락처는 보낼 때 적습니다.`;
  }
}
