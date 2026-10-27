/** /vat/review/ 지난 신고 점검 — 경정청구 후보(신고 담당). 홈택스 매입 목록(전자세금계산서·사업용 카드, 건별)과 신고한 매입 내역(매입처별 세금계산서합계표·신용카드매출전표등 수령명세서 = 공급자별 합계)을 과세기간·공급자별로 합쳐 견주고, 빠진 매입세액 후보와 경정청구 기한(국세기본법 제45조의2, 법정신고기한 뒤 5년)·신고 자체가 없던 기간의 기한후신고(제45조의3)를 보인다.
 *  세무사 평가 반영(2026-10-27) 2차: 합계표는 공급자별 합계라 건별 맞추기가 아니라 집계 비교여야 한다. 차이는 후보일 뿐 — 불공제·면세 귀속 건은 빼야 하고 판단·청구는 신고인 몫. 서버 없음, 저장 없음. */
import { $, esc, num, fmt, loadData, getOrg, parseTable, guessColumns, COL_GUESS, claimPeriod, fixDue, downloadText, toCsv, lawLink, ymd, type Data } from './vat_rules';
type Row = { d: string; supplier: string; sreg: string; desc: string; amt: number; tax: number; preg: string; pkey: string };
type Agg = { key: string; sreg: string; name: string; n: number; amt: number; tax: number };
const D = loadData();
if (D) init(D);
function init(D: Data) {
  const org = getOrg(); const regIn = $<HTMLInputElement>('rv-reg')!; if (org && org.unit === 'entity' && org.reg_no) regIn.value = org.reg_no;
  const today = ymd(new Date());
  const A_KEYS = ['date', 'supplier', 'supplier_reg', 'desc', 'amt', 'tax', 'total', 'payee_reg'], B_KEYS = ['date', 'supplier', 'supplier_reg', 'amt', 'tax', 'total'];
  let gridA: string[][] = []; let periods: string[] = [];
  const colBox = (id: string, grid: string[][], map: Record<string, number>, keys: string[]) => { const names = grid[0] ?? []; return `<div class="vc-form" id="${id}"><p class="q-title full">열 맞추기 <span class="note">${grid.length - 1}행 — 머리글에서 짐작했습니다. 틀리면 고르세요.</span></p>${COL_GUESS.filter(g => keys.includes(g.key)).map(g => `<label>${g.name} <select data-col="${g.key}"><option value="">(없음)</option>${names.map((n, i) => `<option value="${i}" ${map[g.key] === i ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select></label>`).join('')}</div>`; };
  const readMap = (root: ParentNode) => { const m: Record<string, number> = {}; root.querySelectorAll<HTMLSelectElement>('select[data-col]').forEach(s => { if (s.value !== '') m[s.dataset.col!] = Number(s.value); }); return m; };
  const toRows = (grid: string[][], map: Record<string, number>, fixedPeriod?: string): Row[] => grid.slice(1).map(r => { const g = (k: string) => map[k] === undefined ? '' : (r[map[k]] ?? ''); let amt = num(g('amt')), tax = num(g('tax')); const total = num(g('total')); if (!amt && total) { amt = Math.round(total / 1.1); tax = total - amt; } if (amt && !tax && map.tax === undefined) tax = Math.floor(amt * 0.1);
    const dm = g('date').match(/(\d{4})[.\-/]?(\d{2})[.\-/]?(\d{2})/); const d = dm ? `${dm[1]}-${dm[2]}-${dm[3]}` : ''; const p = fixedPeriod && fixedPeriod !== 'date' ? fixedPeriod : (claimPeriod(d)?.key ?? '');
    return { d, supplier: g('supplier'), sreg: g('supplier_reg').replace(/\D/g, ''), desc: g('desc'), amt, tax, preg: g('payee_reg').replace(/\D/g, ''), pkey: p }; }).filter(r => r.pkey && (r.amt || r.tax || r.supplier));
  const supKey = (r: Row) => r.sreg || ('n:' + r.supplier.replace(/\s|\(주\)|주식회사|㈜/g, ''));
  const aggregate = (rows: Row[]) => { const m = new Map<string, Map<string, Agg>>(); for (const r of rows) { const pm = m.get(r.pkey) ?? new Map<string, Agg>(); m.set(r.pkey, pm); const k = supKey(r); const a = pm.get(k) ?? { key: k, sreg: r.sreg, name: r.supplier || r.desc, n: 0, amt: 0, tax: 0 }; a.n++; a.amt += r.amt; a.tax += r.tax; if (!a.name && r.supplier) a.name = r.supplier; pm.set(k, a); } return m; };
  const pName = (k: string) => { const [y, h] = k.split('-'); return `${y}년 제${h}기(${h === '1' ? '1~6' : '7~12'}월)`; };
  const pInfo = (k: string) => claimPeriod(`${k.split('-')[0]}-${k.split('-')[1] === '1' ? '03' : '09'}-01`)!;
  /* B 블록(신고 내역) 추가 */
  const bWrap = $('rv-bs')!; let nB = 0;
  const addB = () => { nB++; const el = document.createElement('div'); el.className = 'vc-form'; el.dataset.b = String(nB); el.innerHTML = `<p class="q-title full">신고 내역 ${nB} <button type="button" class="link-btn" data-del>빼기</button></p>
    <label>어느 신고의 내역인가요 <select data-bp><option value="date">날짜 열로 가름(건별 목록)</option>${periods.map(p => `<option value="${p}">${pName(p)} 신고분</option>`).join('')}</select><span class="note">홈택스 「신고내역 조회」 → 그 신고의 매입처별 세금계산서합계표(공급자별 합계: 등록번호·상호·매수·공급가액·세액) 또는 신용카드매출전표등 수령명세서를 머리글부터 붙여넣기. 합계표에는 날짜가 없으니 어느 신고분인지 고르세요.</span></label>
    <label class="full"><textarea data-bt rows="4" placeholder="사업자등록번호	상호	매수	공급가액	세액&#10;111-11-11111	가전력	2	3,000,000	300,000" style="min-height:6em;padding:8px;border:1px solid var(--line-strong);border-radius:var(--radius);background:var(--bg);color:var(--ink);font:inherit"></textarea></label><div data-bcols class="full"></div>`;
    el.querySelector('[data-del]')!.addEventListener('click', () => el.remove()); el.querySelector<HTMLTextAreaElement>('[data-bt]')!.addEventListener('change', () => { const g = parseTable(el.querySelector<HTMLTextAreaElement>('[data-bt]')!.value); el.querySelector('[data-bcols]')!.innerHTML = g.length > 1 ? colBox(`rv-bc${el.dataset.b}`, g, guessColumns(g[0]), B_KEYS) : ''; });
    bWrap.appendChild(el); };
  $('rv-addb')!.addEventListener('click', addB);
  const refreshBPeriods = () => bWrap.querySelectorAll<HTMLSelectElement>('[data-bp]').forEach(s => { const cur = s.value; s.innerHTML = `<option value="date">날짜 열로 가름(건별 목록)</option>` + periods.map(p => `<option value="${p}">${pName(p)} 신고분</option>`).join(''); if ([...s.options].some(o => o.value === cur)) s.value = cur; });
  $<HTMLFormElement>('rv-form')!.addEventListener('submit', e => {
    e.preventDefault(); gridA = parseTable($<HTMLTextAreaElement>('rv-a')!.value);
    if (gridA.length < 2) { $('rv-cols')!.innerHTML = '<p class="callout info">받은 매입 목록을 머리글 줄부터 붙여넣으세요.</p>'; return; }
    const mapA = guessColumns(gridA[0]); periods = [...new Set(toRows(gridA, mapA).map(r => r.pkey))].sort(); refreshBPeriods();
    $('rv-cols')!.innerHTML = colBox('rv-colA', gridA, mapA, A_KEYS) + '<div class="actions"><button type="button" class="btn" id="rv-build">과세기간별로 견주기</button></div>';
    $('rv-build')!.addEventListener('click', build); build();
  });
  let out: (string | number)[][] = []; const filedSel: Record<string, 'filed' | 'none'> = {}; const manualIn: Record<string, number> = {};
  function build() {
    const mapA = readMap($('rv-colA')!); const reg = regIn.value.replace(/\D/g, ''); const A = toRows(gridA, mapA); periods = [...new Set(A.map(r => r.pkey))].sort(); refreshBPeriods();
    const other = A.filter(r => reg && r.preg && r.preg !== reg); const mine = A.filter(r => !(reg && r.preg && r.preg !== reg));
    const B: Row[] = []; const bPeriods = new Set<string>();
    bWrap.querySelectorAll<HTMLElement>('[data-b]').forEach(el => { const g = parseTable(el.querySelector<HTMLTextAreaElement>('[data-bt]')!.value); if (g.length < 2) return; const box = el.querySelector('[data-bcols]')!; const map = box.querySelector('select') ? readMap(box) : guessColumns(g[0]); const fp = el.querySelector<HTMLSelectElement>('[data-bp]')!.value; const rows = toRows(g, map, fp); rows.forEach(r => bPeriods.add(r.pkey)); B.push(...rows); });
    const aAgg = aggregate(mine), bAgg = aggregate(B);
    out = [['과세기간', '신고', '수취 건수', '수취 매입세액', '신고 내역 매입세액', '빠진 후보 세액', '신고가 더 많은 세액', '법정신고기한', '경정청구 기한', '상태']];
    const detail: string[] = [];
    const rows = periods.map(k => { const P = pInfo(k); const pa = aAgg.get(k) ?? new Map<string, Agg>(); const pb = bAgg.get(k); const hasB = bPeriods.has(k); const filed = filedSel[k] ?? 'filed';
      const aTax = [...pa.values()].reduce((s, a) => s + a.tax, 0), aN = [...pa.values()].reduce((s, a) => s + a.n, 0);
      let bTax = 0, miss = 0, over = 0; const lines: string[] = [];
      if (filed === 'none') { miss = aTax; }
      else if (hasB) { const keys = new Set([...pa.keys(), ...(pb?.keys() ?? [])]); for (const sk of keys) { const a = pa.get(sk), b = pb?.get(sk); const at = a?.tax ?? 0, bt = b?.tax ?? 0; bTax += bt; const d = at - bt; if (d > 0) { miss += d; lines.push(`<li>${esc(a?.name || b?.name || sk)}${a?.sreg ? ` (${esc(a.sreg)})` : ''} — 받은 ${a?.n ?? 0}건 ${fmt(at)} · 신고 ${fmt(bt)} → <strong>빠진 후보 ${fmt(d)}</strong></li>`); } else if (d < 0) { over += -d; lines.push(`<li>${esc(b?.name || sk)} — 받은 ${fmt(at)} · 신고 ${fmt(bt)} → 신고가 ${fmt(-d)} 더 많음(과다 공제·다른 증빙인지 확인)</li>`); } } }
      else { bTax = manualIn[k] ?? 0; miss = Math.max(0, aTax - bTax); }
      const st = filed === 'none' ? (P.due > today ? '아직 신고 전 — 확정신고에 넣는다' : '신고 없음 — 기한후신고(국세기본법 제45조의3), 세무서 결정 통지 전까지') : P.days < 0 ? '경정청구 기한 지남' : P.due > today ? '아직 신고 전 — 확정신고에 넣는다' : `청구 가능 D-${P.days}`;
      out.push([pName(k), filed === 'none' ? '안 함' : '함', aN, aTax, filed === 'none' ? 0 : bTax, miss, over, P.due, filed === 'none' ? '(기한후신고)' : P.claim, st]);
      if (lines.length) detail.push(`<details class="vat-more"><summary>${esc(pName(k))} 공급자별 차이 ${lines.length}건</summary><ul class="meta-list">${lines.join('')}</ul></details>`);
      return `<tr class="${miss && filed !== 'none' && P.days >= 0 && P.due <= today ? 'v-check' : ''}"><th scope="row">${esc(pName(k))}</th><td><select data-filed="${k}"><option value="filed" ${filed === 'filed' ? 'selected' : ''}>함</option><option value="none" ${filed === 'none' ? 'selected' : ''}>안 함</option></select></td><td>${aN}</td><td>${fmt(aTax)}</td><td>${filed === 'none' ? '—' : hasB ? fmt(bTax) : `<input type="text" inputmode="numeric" data-man="${k}" value="${bTax ? fmt(bTax) : ''}" placeholder="신고서 (10)+(12)+(44)+(45) 세액" style="width:11em" />`}</td><td><strong>${fmt(miss)}</strong></td><td>${over ? fmt(over) : ''}</td><td>${P.due}</td><td>${filed === 'none' ? '—' : P.claim}</td><td class="keep">${esc(st)}</td></tr>`; }).join('');
    const otherList = other.map(r => { const fd = fixDue(r.d); return `<li>${r.d} ${esc(r.supplier || r.desc)} — 세액 ${fmt(r.tax)} · 공급받는 자 ${esc(r.preg)} — 우리 명의가 아니라 경정청구 대상이 아닙니다. 수정세금계산서 기한 ${fd?.due ?? '?'}${fd && fd.days < 0 ? '(지남 — 착오 정정이 아니면 불가)' : ''}</li>`; });
    $('rv-result')!.innerHTML = `<div class="section-head"><h2>과세기간별 비교 <span class="meta">${B.length ? `신고 내역 ${B.length}행을 공급자별로 합쳐 견줌` : '신고 내역이 없으면 과세기간마다 신고한 매입세액을 넣으세요'}</span></h2></div>
      <div class="scroll-x"><table class="data-table vat-table" data-stack="off"><caption>지난 신고 점검 — 받은 매입세액과 신고한 매입세액(참고용, ${today})</caption><thead><tr>${out[0].map(h => `<th scope="col">${esc(String(h))}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>
      <p class="meta">'신고' 칸을 '안 함'으로 바꾸면 그 과세기간은 경정청구가 아니라 <strong>기한후신고</strong>(국세기본법 제45조의3 — 법정신고기한까지 신고하지 않은 자는 세무서장이 결정·통지하기 전까지 기한후신고서를 낼 수 있음) 길로 표시됩니다. 신고 내역을 붙여넣은 기간은 공급자별 합계로 견주고, 아니면 신고서 세액을 직접 넣습니다.</p>
      ${detail.join('')}
      ${otherList.length ? `<h3>우리 명의가 아닌 세금계산서 ${other.length}건</h3><ul class="meta-list">${otherList.join('')}</ul>` : ''}
      <div class="callout warn"><strong>차이가 곧 환급액은 아닙니다.</strong> 빠진 후보 가운데 ① 면세·행정 일에만 쓴 것(불공제) ② 토지·승용차·접대비 ③ 과세·면세 공통 지출(안분해야 함) ④ 증빙 요건을 못 갖춘 것은 빼야 합니다. 건마다 <a href="/vat/tools/">지출 건 판정</a>으로 확인하고, 남는 것을 과세기간별로 경정청구합니다. '신고가 더 많음'은 과다 공제이거나 다른 증빙(종이 세금계산서 등)일 수 있으니 확인합니다. 매출을 빠뜨린 것이 있으면 수정신고 대상입니다.</div>
      <h3>경정청구·기한후신고 절차</h3><ul class="meta-list"><li>${esc(D.rules.filing.claim ?? '')}</li><li>홈택스 「경정청구」에서 과세기간을 고르고 매입세액을 고친 신고서와 매입처별 세금계산서합계표·신용카드매출전표등 수령명세서(추가분)를 냅니다. 세무서는 2개월 안에 결과를 통지합니다.</li><li>신고 자체가 없던 과세기간은 기한후신고서(과세표준·세액·가산세 포함)를 내고 낼 세액이 있으면 납부합니다(제45조의3 제1항·제2항). 세무서는 신고일부터 3개월 안에 결정·경정해 통지합니다(제3항).</li><li>근거: ${lawLink(D, { law: 'basic', art: '제45조의2' })} · ${lawLink(D, { law: 'basic', art: '제45조의3' })} · ${lawLink(D, { law: 'decree', art: '제74조' })} · ${lawLink(D, { law: 'act', art: '제54조' })}</li></ul>
      <div class="actions no-print"><button type="button" class="btn secondary" id="rv-csv">비교표 CSV 내려받기</button></div>`;
    $('rv-csv')?.addEventListener('click', () => downloadText(`지난신고점검-${today}.csv`, toCsv(out), 'text/csv;charset=utf-8'));
    $('rv-result')!.querySelectorAll<HTMLInputElement>('[data-man]').forEach(i => i.addEventListener('change', () => { manualIn[i.dataset.man!] = num(i.value); build(); }));
    $('rv-result')!.querySelectorAll<HTMLSelectElement>('[data-filed]').forEach(s => s.addEventListener('change', () => { filedSel[s.dataset.filed!] = s.value as 'filed' | 'none'; build(); }));
  }
}
