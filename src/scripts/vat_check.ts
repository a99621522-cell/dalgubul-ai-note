/**
 * 지자체 부가가치세 매입세액 점검기 — /vat/ (운영자 지시 2026-10-27)
 * 페이지에 묻어 온 규칙 JSON(#vat-data ← data/vat/rules.yml)으로 ① 지출 건 판정(공제·안분·불공제·세액 없음·확인 필요) ② 공통매입세액 안분 ③ 감가상각자산 재계산 ④ 점검표(localStorage)를 브라우저 안에서만 한다.
 * 서버·AI 호출 없음. 판정은 선택지만으로 하는 참고용이며 조문 번호를 함께 보인다(평가·해석 아님).
 */
import { loadData, judge, LABEL, lawLink, lawText, uniq, optName, num, fmt, pct, esc, $, inquiryHtml, wireInquiry, type Data, type Input, type Out, type Basis } from './vat_rules';

const D0 = loadData();
if (D0) init(D0);

function init(D: Data) {
  const inq = $('inq-list'); if (inq) { inq.innerHTML = (D.inquiries ?? []).map(q => inquiryHtml(D, q)).join(''); wireInquiry(inq); }
  const B = (law: string, art: string): Basis => ({ law, art });
  const link = (b: Basis) => lawLink(D, b);
  const bText = lawText;
  const name = (g: keyof Data['inputs'], k: string) => optName(D, g, k);
  const judge1 = (i: Input): Out => judge(D, i);

  const form = $<HTMLFormElement>('vc-form'), res = $('vc-result'), addBtn = $<HTMLButtonElement>('vc-add'), tbl = $<HTMLTableElement>('vc-table'), wrap = $('vc-table-wrap'), sum = $('vc-sum'), clr = $('vc-clear');
  let last: { i: Input; o: Out; desc: string; amount: number; tax: number } | null = null;
  /* 표 도구 막대(table_tools 가 .scroll-x 다음에 붙임)는 표에 행이 있을 때만 보인다 */
  const showTable = (on: boolean) => { wrap!.hidden = !on; const bar = wrap?.nextElementSibling as HTMLElement | null; if (bar?.classList.contains('table-tools')) bar.hidden = !on; };
  showTable(false); document.addEventListener('DOMContentLoaded', () => showTable(false)); window.setTimeout(() => showTable(false), 0);   // table_tools 가 먼저·나중 어느 쪽에 붙어도 숨긴다
  const read = (): Input => ({ use: $<HTMLSelectElement>('vc-use')!.value, kind: $<HTMLSelectElement>('vc-kind')!.value, proof: $<HTMLSelectElement>('vc-proof')!.value, supplier: $<HTMLSelectElement>('vc-supplier')!.value, timing: $<HTMLSelectElement>('vc-timing')!.value });
  form?.addEventListener('submit', e => {
    e.preventDefault();
    const i = read(); const o = judge1(i);
    const amount = num($<HTMLInputElement>('vc-amount')?.value); let tax = num($<HTMLInputElement>('vc-tax')?.value); if (!tax && amount) tax = Math.floor(amount * 0.1);
    const desc = ($<HTMLInputElement>('vc-desc')?.value || '').trim() || '(내용 없음)';
    last = { i, o, desc, amount, tax };
    const taxLine = tax ? `<p class="label">세액</p><p class="big">${fmt(tax)}원 ${o.v === 'ok' ? '→ 공제' : o.v === 'no' || o.v === 'none' ? '→ 공제 0원' : o.v === 'split' ? '→ 면세비율만큼 빼고 공제' : ''}</p>` : '';
    res!.innerHTML = `<div class="vc-card"><h3><span class="verdict ${o.v}">${LABEL[o.v]}</span> ${esc(o.title)}${o.verify ? '<span class="vbadge">원문 확인 필요</span>' : ''}</h3>
      <p class="meta">${esc(desc)} · ${esc(name('use', i.use))} · ${esc(name('kind', i.kind))} · ${esc(name('proof', i.proof))}</p>${taxLine}
      <p class="label">왜</p><ul>${o.why.map(w => `<li>${esc(w)}</li>`).join('')}</ul>
      ${o.todo.length ? `<p class="label">해야 할 일</p><ul>${o.todo.map(w => `<li>${esc(w)}</li>`).join('')}</ul>` : ''}
      <p class="label">근거</p><p class="meta">${uniq(o.basis).map(link).join(' · ')}</p></div>`;
    addBtn!.disabled = false;
    res!.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
  addBtn?.addEventListener('click', () => {
    if (!last || !tbl) return;
    const { i, o, desc, amount, tax } = last;
    const ded = o.v === 'ok' ? tax : o.v === 'split' ? NaN : 0;
    const tr = document.createElement('tr'); tr.className = `v-${o.v}`;
    tr.innerHTML = [esc(desc), esc(name('use', i.use)), esc(name('kind', i.kind)), esc(name('proof', i.proof)), amount ? fmt(amount) : '', tax ? fmt(tax) : '', `<span class="verdict ${o.v}">${LABEL[o.v]}</span>${o.verify ? ' (원문 확인)' : ''}`, Number.isNaN(ded) ? '안분 계산' : tax ? fmt(ded) : '', esc(uniq(o.basis).map(bText).join(', ')), esc(o.todo[0] || '')].map((c, k) => `<td${k === 0 ? ' class="desc"' : ''}>${c}</td>`).join('');
    tbl.tBodies[0].appendChild(tr);
    showTable(true); clr!.hidden = false; addBtn.disabled = true; last = null; form?.reset();
    const rows = [...tbl.tBodies[0].rows]; let t = 0, d = 0, s = 0;
    rows.forEach(r => { const tx = num(r.cells[5].textContent); t += tx; if (r.classList.contains('v-ok')) d += tx; if (r.classList.contains('v-split')) s += tx; });
    sum!.hidden = false; sum!.textContent = `${rows.length}건 · 세액 합계 ${fmt(t)}원 · 전액 공제 ${fmt(d)}원 · 안분 대상(공통) ${fmt(s)}원 · 불공제·세액 없음·확인 ${fmt(t - d - s)}원 — 참고용, 신고서 값은 담당자가 확정`;
  });
  clr?.addEventListener('click', () => { if (!tbl) return; tbl.tBodies[0].innerHTML = ''; showTable(false); sum!.hidden = true; clr.hidden = true; });

  /* ---------- ② 공통매입세액 안분 ---------- */
  $<HTMLFormElement>('ap-form')?.addEventListener('submit', e => {
    e.preventDefault();
    const t = num($<HTMLInputElement>('ap-t')?.value), ex = num($<HTMLInputElement>('ap-e')?.value), c = num($<HTMLInputElement>('ap-c')?.value), type = $<HTMLSelectElement>('ap-type')!.value;
    const out = $('ap-result')!; const total = t + ex;
    if (!c) { out.innerHTML = `<p class="callout info">공통매입세액을 넣으세요.</p>`; return; }
    if (total <= 0) { out.innerHTML = `<div class="vc-card"><h3><span class="verdict check">확인 필요</span> 공급가액이 없음</h3><p>${esc(D.rules.common.no_supply)}</p><p class="meta">근거: ${link(B('decree', '제81조'))} · ${link(B('decree', '제82조'))}</p></div>`; return; }
    const ratio = ex / total;
    const sk = D.rules.common.skip; const small = sk.find(s => s.key === 'small')!, r5 = sk.find(s => s.key === 'ratio5')!;
    let skip: string | null = null;
    if (c < (small.amount_lt ?? 50000)) skip = small.name; else if (ratio < (r5.ratio_lt ?? 0.05) && c < (r5.amount_lt ?? 5000000)) skip = r5.name;
    const non = skip ? 0 : Math.floor(c * ratio); const ded = c - non;
    out.innerHTML = `<div class="vc-card"><h3><span class="verdict ${skip ? 'ok' : 'split'}">${skip ? '안분 생략 — 전액 공제' : '안분'}</span> 면세비율 ${pct(ratio)}</h3>
      <p class="meta">총공급가액 ${fmt(total)}원 = 과세 ${fmt(t)} + 면세 ${fmt(ex)} · 공통매입세액 ${fmt(c)}원 · ${type === 'prelim' ? '예정신고' : '확정신고'}</p>
      ${skip ? `<p>${esc(skip)}에 해당해 안분하지 않습니다.</p>` : `<p class="label">불공제(면세분)</p><p class="big">${fmt(non)}원</p><p class="meta">= ${fmt(c)} × ${fmt(ex)} ÷ ${fmt(total)} (원 미만 버림 — 신고서 작성 기준에 따릅니다)</p>`}
      <p class="label">공제</p><p class="big">${fmt(ded)}원</p>
      ${type === 'prelim' ? `<p class="meta">${esc(D.rules.common.prelim)}</p>` : `<p class="meta">예정신고 때 안분한 금액이 있으면 이 과세기간 전체 값으로 다시 구한 불공제분에서 예정신고 불공제분을 빼 정산합니다.</p>`}
      ${ratio < (r5.ratio_lt ?? 0.05) && !skip ? `<p class="meta">면세비율은 5% 미만이지만 공통매입세액이 ${fmt(r5.amount_lt ?? 5000000)}원 이상이라 안분합니다.</p>` : ''}
      <p class="label">근거</p><p class="meta">${link(B('act', '제40조'))} · ${link(B('decree', '제81조'))}</p></div>`;
  });

  /* ---------- ③ 재계산 ---------- */
  $<HTMLFormElement>('rc-form')?.addEventListener('submit', e => {
    e.preventDefault();
    const asset = $<HTMLSelectElement>('rc-asset')!.value as 'building' | 'other'; const c0 = num($<HTMLInputElement>('rc-c0')?.value); const r0 = num($<HTMLInputElement>('rc-r0')?.value) / 100, r1 = num($<HTMLInputElement>('rc-r1')?.value) / 100; const n = Math.max(0, Math.floor(num($<HTMLInputElement>('rc-n')?.value)));
    const out = $('rc-result')!; if (!c0) { out.innerHTML = `<p class="callout info">취득 때 공통매입세액을 넣으세요.</p>`; return; }
    const diff = r1 - r0; const th = D.rules.recalc.threshold_pp;
    if (Math.abs(diff) < th - 1e-9) { out.innerHTML = `<div class="vc-card"><h3><span class="verdict none">재계산 없음</span> 면세비율 변동 ${(diff * 100).toFixed(2)}%p</h3><p>취득(직전 재계산) 때와 견주어 5%p 이상 늘거나 줄지 않아 재계산하지 않습니다.</p><p class="meta">근거: ${link(B('act', '제41조'))} · ${link(B('decree', '제83조'))}</p></div>`; return; }
    const rate = D.rules.recalc.rates[asset]; const remain = Math.max(0, 1 - rate * n);
    if (remain <= 0) { out.innerHTML = `<div class="vc-card"><h3><span class="verdict none">재계산 없음</span> 체감 기간 지남</h3><p>경과 과세기간 ${n}회 × 체감률 ${rate * 100}% ≥ 100% 라 재계산할 잔액이 없습니다.</p></div>`; return; }
    const amt = c0 * remain * diff; const add = amt > 0;
    out.innerHTML = `<div class="vc-card"><h3><span class="verdict ${add ? 'no' : 'ok'}">${add ? '납부세액에 가산' : '납부세액에서 공제'}</span> ${fmt(Math.abs(amt))}원</h3>
      <p class="meta">= ${fmt(c0)} × (1 − ${rate * 100}% × ${n}) × ${add ? '+' : '−'}${(Math.abs(diff) * 100).toFixed(2)}%p · 남은 비율 ${pct(remain)}</p>
      <p>면세비율이 ${add ? '늘어' : '줄어'} 취득 때 ${add ? '공제했던' : '불공제했던'} 매입세액 일부를 ${add ? '가산' : '공제'}합니다. 이번 과세기간 확정신고서에 반영하고 다음 재계산의 기준 비율은 이번 비율(${pct(r1)})입니다.</p>
      <p class="label">근거</p><p class="meta">${link(B('act', '제41조'))} · ${link(B('decree', '제83조'))} · ${link(B('rule', '제55조'))}</p></div>`;
  });

  /* ---------- ④ 점검표 ---------- */
  const KEY = 'vat-check-v1'; const boxes = [...document.querySelectorAll<HTMLInputElement>('input[data-ck]')]; const cnt = $('ck-count');
  const load = (): Record<string, boolean> => { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { return {}; } };
  const refresh = () => { if (cnt) cnt.textContent = `${boxes.filter(b => b.checked).length} / ${boxes.length} 확인`; };
  const st = load(); boxes.forEach(b => { b.checked = !!st[b.dataset.ck!]; b.addEventListener('change', () => { const s = load(); s[b.dataset.ck!] = b.checked; try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* 저장 못 해도 계속 */ } refresh(); }); }); refresh();
  $('ck-reset')?.addEventListener('click', () => { boxes.forEach(b => { b.checked = false; }); try { localStorage.removeItem(KEY); } catch { /* */ } refresh(); });
  $('ck-print')?.addEventListener('click', () => window.print());
}
