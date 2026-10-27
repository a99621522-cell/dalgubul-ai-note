/**
 * 지자체 부가가치세 매입세액 점검기 — /vat/ (운영자 지시 2026-10-27)
 * 페이지에 묻어 온 규칙 JSON(#vat-data ← data/vat/rules.yml)으로 ① 지출 건 판정(공제·안분·불공제·세액 없음·확인 필요) ② 공통매입세액 안분 ③ 감가상각자산 재계산 ④ 점검표(localStorage)를 브라우저 안에서만 한다.
 * 서버·AI 호출 없음. 판정은 선택지만으로 하는 참고용이며 조문 번호를 함께 보인다(평가·해석 아님).
 */
type Basis = { law: string; art: string };
type Opt = { key: string; name: string };
type Data = {
  law_url: string; laws: Record<string, string>;
  rules: { nondeductible: { key: string; no: string; name: string; fix: string; basis: Basis[] }[]; card: { summary: string; not_allowed: string; verify?: boolean }; late_invoice: { summary: string; verify?: boolean };
    common: { summary: string; formula: string; skip: { key: string; name: string; cond: string; ratio_lt?: number; amount_lt?: number }[]; no_supply: string; prelim: string };
    recalc: { rates: { building: number; other: number }; threshold_pp: number } };
  inputs: Record<'use' | 'kind' | 'proof' | 'supplier' | 'timing', Opt[]>;
};
type Verdict = 'ok' | 'split' | 'no' | 'none' | 'check';
const LABEL: Record<Verdict, string> = { ok: '공제', split: '안분 뒤 공제(공통)', no: '불공제', none: '매입세액 없음', check: '확인 필요' };
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T | null;
const num = (s: string | undefined | null) => { const v = Number(String(s ?? '').replace(/[^0-9.\-]/g, '')); return Number.isFinite(v) ? v : 0; };
const fmt = (n: number) => Math.round(n).toLocaleString('ko-KR');
const pct = (r: number) => (r * 100).toFixed(2).replace(/\.?0+$/, '') + '%';
const esc = (s: string) => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' } as Record<string, string>)[c]);

const dataEl = $('vat-data');
if (dataEl) init(JSON.parse(dataEl.textContent || '{}') as Data);

function init(D: Data) {
  const LAW: Record<string, string> = { act: '법', decree: '시행령', rule: '시행규칙', basic: '국세기본법' };
  const B = (law: string, art: string): Basis => ({ law, art });
  const link = (b: Basis) => `<a href="${D.law_url.replace('{law}', D.laws[b.law]).replace('{art}', b.art)}" target="_blank" rel="noopener">${LAW[b.law]} ${b.art}</a>`;
  const bText = (b: Basis) => `${LAW[b.law]} ${b.art}`;
  const nd = (k: string) => D.rules.nondeductible.find(n => n.key === k)!;
  const name = (g: keyof Data['inputs'], k: string) => D.inputs[g].find(o => o.key === k)?.name ?? k;

  /* ---------- ① 지출 건 판정 ---------- */
  type Input = { use: string; kind: string; proof: string; supplier: string; timing: string };
  type Out = { v: Verdict; title: string; why: string[]; todo: string[]; basis: Basis[]; verify?: boolean; recalc?: boolean; split?: boolean };
  function judge(i: Input): Out {
    const why: string[] = [], todo: string[] = [], basis: Basis[] = []; let verify = false;
    const done = (v: Verdict, title: string, extra: Partial<Out> = {}): Out => ({ v, title, why, todo, basis, verify, ...extra });
    // 1. 부가가치세 거래가 아니거나 면세 거래 — 공제할 세액 자체가 없다
    if (i.kind === 'payroll' || i.kind === 'tax') { why.push('급여·세금·공과금·과태료는 재화·용역의 공급이 아니어서 부가가치세가 붙지 않습니다.'); return done('none', '매입세액이 없는 지출'); }
    if (i.kind === 'insurance' || i.kind === 'exempt_goods') { why.push('보험·금융 용역, 수돗물·도서·교육·의료 같은 면세 재화·용역에는 매입세액이 없습니다.'); basis.push(B('act', '제26조')); return done('none', '면세 거래 — 매입세액 없음'); }
    if (i.proof === 'bill') { why.push('계산서는 면세 거래의 증빙이라 공제할 세액이 없습니다.'); todo.push('과세 거래인데 계산서를 받았다면 공급자에게 세금계산서로 다시 발급을 요청합니다.'); basis.push(B('act', '제26조'), B('act', '제38조')); return done('none', '계산서(면세 거래) — 매입세액 없음'); }
    // 2. 증빙 요건
    if (i.proof === 'receipt') { const n = nd('no_invoice'); why.push(`세금계산서(또는 요건을 갖춘 신용카드매출전표)를 받지 않은 매입세액은 공제하지 않습니다(${n.no}).`); todo.push('공급자가 일반과세자면 공급받는 자를 우리 기관 사업자등록번호로 한 세금계산서를, 카드 결제면 부가가치세액이 따로 적힌 전표를 받습니다.'); basis.push(...n.basis); return done('no', '증빙 없음 — 불공제'); }
    if (i.proof === 'tax_invoice_other') { const n = nd('no_invoice'); why.push(`공급받는 자가 우리 기관이 아닌 세금계산서는 '사실과 다른 세금계산서'로 공제하지 않습니다(${n.no}).`); todo.push('공급자에게 공급받는 자를 지자체(과세사업 등록번호)로 한 수정세금계산서를 요청합니다. 그 시설이 수탁기관 자기 사업이라면 그 기관의 매입세액이지 우리 것이 아닙니다 — 위·수탁 계약에서 사업자가 누구인지 확인합니다.'); basis.push(...n.basis, B('decree', '제75조')); return done('no', '다른 명의 세금계산서 — 불공제'); }
    if (i.proof === 'card_novat') { why.push('부가가치세액이 따로 적히지 않은 전표, 세금계산서를 발급할 수 없는 간이과세자·면세사업자의 전표는 공제 요건을 갖추지 못합니다.'); todo.push('공급자가 일반과세자면 부가가치세액이 구분된 전표 재발급 또는 세금계산서를 요청합니다. 간이(발급 불가)·면세 공급자면 공제할 수 없습니다.'); basis.push(B('act', '제46조')); verify = !!D.rules.card.verify; return done('no', '요건 못 갖춘 카드 전표 — 불공제'); }
    if (i.proof === 'card_vat') {
      if (i.supplier === 'simple_no') { why.push('세금계산서를 발급할 수 없는 간이과세자·면세사업자의 카드 전표는 공제하지 못합니다.'); basis.push(B('act', '제46조')); return done('no', '영수증 발급 기간 간이과세자·면세 공급자 카드 전표 — 불공제'); }
      if (i.supplier === 'unknown') { why.push('카드 전표로 공제하려면 공급자가 일반과세자(또는 세금계산서를 발급할 수 있는 간이과세자)여야 합니다.'); todo.push('홈택스 「사업자등록 상태 조회」로 공급자의 과세 유형을 확인한 뒤 다시 판정합니다.'); basis.push(B('act', '제46조')); return done('check', '공급자 과세 유형 확인 필요'); }
      todo.push('신고 때 「신용카드매출전표등 수령명세서」에 적고 전표를 5년 보관합니다. 목욕·이발·미용업, 여객운송업(전세버스 제외), 입장권 발행 사업, 비급여 미용 진료, 무도·자동차운전학원의 전표는 공제하지 못합니다(시행령 제88조 제5항).'); basis.push(B('decree', '제88조')); basis.push(B('act', '제46조'), B('act', '제71조')); verify = !!D.rules.card.verify;
    }
    // 3. 종류로 불공제
    if (i.kind === 'land') { const n = nd('land'); why.push(`토지 취득·조성·형질변경, 토지만 쓰려는 건물 철거비의 매입세액은 공제하지 않습니다(${n.no}, 시행령 제80조).`); todo.push('건물 신축·수선 몫이 섞여 있으면 계약·견적에서 토지 관련분과 나눠 적습니다 — 건물분은 공제 대상입니다.'); basis.push(...n.basis); return done('no', '토지 관련 매입세액 — 불공제'); }
    if (i.kind === 'car') { const n = nd('car'); why.push(`8인승 이하 비영업용 승용차의 구입·임차·유지(유류·수리) 매입세액은 공제하지 않습니다(${n.no}).`); todo.push('9인승 이상 승합차·화물차·경차·운수업 등 영업용이면 대상이 아니므로 차종을 확인합니다.'); basis.push(...n.basis); return done('no', '비영업용 승용차 — 불공제'); }
    if (i.kind === 'entertain') { const n = nd('entertain'); why.push(`기업업무추진비(접대비)와 이와 유사한 비용의 매입세액은 공제하지 않습니다(${n.no}).`); todo.push('직원 복리후생비·광고선전비는 여기 들지 않으므로 지출 성격을 서류에 적습니다.'); basis.push(...n.basis); return done('no', '접대·기념품 — 불공제'); }
    // 4. 시기
    if (i.timing === 'prereg') { const n = nd('pre_reg'); why.push(`사업자등록 신청 전의 매입세액은 공제하지 않습니다(${n.no}). 다만 공급시기가 속하는 과세기간이 끝난 뒤 20일 이내에 등록을 신청하면 그 과세기간 시작일까지의 매입세액은 공제됩니다.`); todo.push('등록 신청일과 공급시기가 속한 과세기간 종료일을 견주어 20일 이내인지 확인합니다. 새 과세사업은 시작 전에 등록(또는 업종 추가)합니다.'); basis.push(...n.basis); return done('check', '등록 전 매입세액 — 20일 요건 확인'); }
    if (i.timing === 'late') { why.push(D.rules.late_invoice.summary); todo.push('공급시기가 속한 과세기간의 확정신고기한까지 받았으면 그대로 공제(시행령 제75조 제3호). 그 뒤 1년 안에 받았으면 수정신고·경정청구서와 함께 내야 공제(제7호). 1년이 지났으면 공제할 수 없습니다.'); basis.push(B('decree', '제75조')); verify = verify || !!D.rules.late_invoice.verify; }
    // 5. 위탁수수료·복리후생 성격
    if (i.kind === 'outsource') { why.push('수탁기관(지방공단 등)은 지자체가 아니므로 그 기관이 지자체에 공급하는 용역은 과세이고 세금계산서를 받습니다. 다만 실비를 전달·정산하는 돈이면 용역 공급이 아니어서 세금계산서 대상이 아닙니다.'); todo.push('위·수탁 계약서에서 대행 수수료(용역)와 사업비 실비 정산을 나눠 보고, 용역분은 아래 귀속(과세·면세·공통)에 따라 공제·안분합니다.'); basis.push(B('act', '제26조'), B('act', '제38조'), B('decree', '제75조')); if (i.use === 'unknown') return done('check', '위탁수수료 — 용역인지 실비 정산인지 확인'); }
    if (i.kind === 'welfare') { why.push('직원 복리후생비는 접대비가 아니며 사업 관련 지출입니다. 그 직원이 어느 사업(과세·면세) 일을 하는지에 따라 귀속이 정해집니다.'); }
    // 6. 귀속
    const cap = i.kind === 'building' || i.kind === 'equip';
    if (i.use === 'exempt') { const n = nd('exempt_use'); why.push(`면세사업·고유 행정사무에 쓰인 매입세액은 공제하지 않습니다(${n.no}).`); todo.push('과세 시설과 함께 쓰인 지출이라면 "면세"가 아니라 "공통"으로 다시 판정합니다.'); basis.push(...n.basis); return done('no', '면세사업 관련 — 불공제'); }
    if (i.use === 'taxable') { why.push('과세사업에만 쓰인 지출의 매입세액은 전액 공제합니다. 실지귀속이 분명하므로 안분하지 않습니다.'); todo.push('지출 원장·계약서에 어느 과세 시설인지 적어 실지귀속 근거를 남깁니다.'); if (cap) todo.push('감가상각자산은 뒤에 면세사업에도 쓰이게 되면 재계산 대상이 되므로 취득 과세기간·매입세액을 자산 대장에 적어 둡니다.'); basis.push(B('act', '제38조'), B('act', '제40조'), B('decree', '제81조')); return done('ok', '과세사업 실지귀속 — 전액 공제', { recalc: cap }); }
    if (i.use === 'common') { why.push('과세·면세에 함께 쓰여 실지귀속을 가를 수 없는 공통매입세액은 총공급가액 중 면세공급가액 비율로 안분해 면세분을 뺍니다.'); todo.push('아래 「공통매입세액 안분 계산기」로 불공제분을 구합니다(면세비율 5% 미만·공통매입세액 500만 원 미만, 5만 원 미만이면 안분 생략). 예정신고 때 안분한 것은 확정신고 때 정산합니다.'); todo.push('계량기·계약을 시설별로 나눌 수 있으면 나눠 실지귀속으로 바꿉니다 — 과세 시설분은 전액 공제됩니다.'); if (cap) todo.push('감가상각자산은 뒤 과세기간 면세비율이 5%p 이상 바뀌면 납부세액을 재계산합니다(법 제41조, 시행령 제83조).'); basis.push(B('act', '제40조'), B('decree', '제81조'), B('decree', '제82조')); if (cap) basis.push(B('act', '제41조'), B('decree', '제83조')); return done('split', '공통매입세액 — 안분 뒤 공제', { recalc: cap, split: true }); }
    why.push('어느 사업에 쓰였는지 모르면 공제 여부를 정할 수 없습니다. 실지귀속을 먼저 가릅니다.'); todo.push('지출 결의서·계약서·검수 조서에서 어느 시설(과세 시설/행정청사/겸용)에 쓰였는지 확인합니다. 시설이 과세사업인지는 「3. 우리 시설은 과세사업인가」 표로 봅니다.'); basis.push(B('act', '제40조'), B('decree', '제81조'));
    return done('check', '귀속(과세·면세·공통) 확인 필요');
  }

  const form = $<HTMLFormElement>('vc-form'), res = $('vc-result'), addBtn = $<HTMLButtonElement>('vc-add'), tbl = $<HTMLTableElement>('vc-table'), wrap = $('vc-table-wrap'), sum = $('vc-sum'), clr = $('vc-clear');
  let last: { i: Input; o: Out; desc: string; amount: number; tax: number } | null = null;
  /* 표 도구 막대(table_tools 가 .scroll-x 다음에 붙임)는 표에 행이 있을 때만 보인다 */
  const showTable = (on: boolean) => { wrap!.hidden = !on; const bar = wrap?.nextElementSibling as HTMLElement | null; if (bar?.classList.contains('table-tools')) bar.hidden = !on; };
  showTable(false); document.addEventListener('DOMContentLoaded', () => showTable(false)); window.setTimeout(() => showTable(false), 0);   // table_tools 가 먼저·나중 어느 쪽에 붙어도 숨긴다
  const read = (): Input => ({ use: $<HTMLSelectElement>('vc-use')!.value, kind: $<HTMLSelectElement>('vc-kind')!.value, proof: $<HTMLSelectElement>('vc-proof')!.value, supplier: $<HTMLSelectElement>('vc-supplier')!.value, timing: $<HTMLSelectElement>('vc-timing')!.value });
  form?.addEventListener('submit', e => {
    e.preventDefault();
    const i = read(); const o = judge(i);
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
function uniq(b: Basis[]) { const seen = new Set<string>(); return b.filter(x => { const k = x.law + x.art; if (seen.has(k)) return false; seen.add(k); return true; }); }
