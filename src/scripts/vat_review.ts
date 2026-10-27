/** /vat/review/ 지난 신고 점검 — 경정청구 후보(신고 담당). 홈택스 매입 목록(전자세금계산서·사업용 카드)과 신고한 매입 내역을 과세기간별로 견줘 빠진 매입세액과 경정청구 기한(국세기본법 제45조의2, 법정신고기한 뒤 5년)을 보인다.
 *  세무사 평가 반영(2026-10-27): 앞으로의 신고만 보던 도구에 '지난 5년 누락분 찾기'를 더함. 차이는 후보일 뿐 — 불공제·면세 귀속 건은 빼야 하고, 판단·청구는 신고인 몫. 서버 없음, 저장 없음(붙여넣은 글자는 이 화면에만). */
import { $, esc, num, fmt, loadData, getOrg, parseTable, guessColumns, COL_GUESS, claimPeriod, fixDue, downloadText, toCsv, lawLink, ymd, type Data } from './vat_rules';
type Row = { d: string; supplier: string; sreg: string; desc: string; amt: number; tax: number; preg: string; period: ReturnType<typeof claimPeriod> };
const D = loadData();
if (D) init(D);
function init(D: Data) {
  const org = getOrg(); const regIn = $<HTMLInputElement>('rv-reg')!; if (org && org.unit === 'entity' && org.reg_no) regIn.value = org.reg_no;
  const today = ymd(new Date());
  let gridA: string[][] = [], gridB: string[][] = [], mapA: Record<string, number> = {}, mapB: Record<string, number> = {};
  const colBox = (id: string, grid: string[][], map: Record<string, number>, keys: string[]) => { const names = grid[0] ?? []; return `<div class="vc-form" id="${id}"><p class="q-title full">열 맞추기 <span class="note">${grid.length - 1}행 — 머리글에서 짐작했습니다. 틀리면 고르세요.</span></p>${COL_GUESS.filter(g => keys.includes(g.key)).map(g => `<label>${g.name} <select data-col="${g.key}"><option value="">(없음)</option>${names.map((n, i) => `<option value="${i}" ${map[g.key] === i ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select></label>`).join('')}</div>`; };
  const readMap = (id: string) => { const m: Record<string, number> = {}; document.querySelectorAll<HTMLSelectElement>(`#${id} select[data-col]`).forEach(s => { if (s.value !== '') m[s.dataset.col!] = Number(s.value); }); return m; };
  const toRows = (grid: string[][], map: Record<string, number>): Row[] => grid.slice(1).map(r => { const g = (k: string) => map[k] === undefined ? '' : (r[map[k]] ?? ''); let amt = num(g('amt')), tax = num(g('tax')); const total = num(g('total')); if (!amt && total) { amt = Math.round(total / 1.1); tax = total - amt; } if (amt && !tax && map.tax === undefined) tax = Math.floor(amt * 0.1);
    const dm = g('date').match(/(\d{4})[.\-/]?(\d{2})[.\-/]?(\d{2})/); const d = dm ? `${dm[1]}-${dm[2]}-${dm[3]}` : ''; return { d, supplier: g('supplier'), sreg: g('supplier_reg').replace(/\D/g, ''), desc: g('desc'), amt, tax, preg: g('payee_reg').replace(/\D/g, ''), period: claimPeriod(d) }; }).filter(r => r.d && (r.amt || r.tax));
  $<HTMLFormElement>('rv-form')!.addEventListener('submit', e => {
    e.preventDefault(); gridA = parseTable($<HTMLTextAreaElement>('rv-a')!.value); gridB = parseTable($<HTMLTextAreaElement>('rv-b')!.value);
    if (gridA.length < 2) { $('rv-cols')!.innerHTML = '<p class="callout info">매입 목록을 머리글 줄부터 붙여넣으세요.</p>'; return; }
    mapA = guessColumns(gridA[0]); mapB = gridB.length > 1 ? guessColumns(gridB[0]) : {};
    $('rv-cols')!.innerHTML = colBox('rv-colA', gridA, mapA, ['date', 'supplier', 'supplier_reg', 'desc', 'amt', 'tax', 'total', 'payee_reg']) + (gridB.length > 1 ? colBox('rv-colB', gridB, mapB, ['date', 'supplier', 'supplier_reg', 'amt', 'tax', 'total']) : '') + '<div class="actions"><button type="button" class="btn" id="rv-build">과세기간별로 견주기</button></div>';
    $('rv-build')!.addEventListener('click', build); build();
  });
  let out: (string | number)[][] = [];
  function build() {
    mapA = readMap('rv-colA'); if (gridB.length > 1) mapB = readMap('rv-colB');
    const reg = regIn.value.replace(/\D/g, ''); const A = toRows(gridA, mapA); const B = gridB.length > 1 ? toRows(gridB, mapB) : [];
    const other = A.filter(r => reg && r.preg && r.preg !== reg); const mine = A.filter(r => !(reg && r.preg && r.preg !== reg));
    // B 와 맞추기: 같은 과세기간 + 공급자 등록번호(없으면 공급가액) + 세액이 같은 행을 하나씩 소비
    const pool = B.map(b => ({ ...b, used: false })); const unmatched: Row[] = []; let matched = 0;
    for (const a of mine) { const hit = pool.find(b => !b.used && b.period?.key === a.period?.key && b.tax === a.tax && (a.sreg && b.sreg ? a.sreg === b.sreg : b.amt === a.amt)); if (hit) { hit.used = true; matched++; } else unmatched.push(a); }
    const byP = new Map<string, { p: NonNullable<Row['period']>; n: number; tax: number; amt: number; miss: Row[] }>();
    for (const r of mine) { if (!r.period) continue; const g = byP.get(r.period.key) ?? { p: r.period, n: 0, tax: 0, amt: 0, miss: [] }; g.n++; g.tax += r.tax; g.amt += r.amt; byP.set(r.period.key, g); }
    for (const r of unmatched) if (r.period) byP.get(r.period.key)!.miss.push(r);
    const hasB = B.length > 0; const keys = [...byP.keys()].sort();
    const manual = (k: string) => num(document.querySelector<HTMLInputElement>(`[data-filed="${k}"]`)?.value);
    out = [['과세기간', '수취 건수', '수취 매입세액', hasB ? '신고와 맞은 건' : '신고한 매입세액(입력)', '빠진 후보 건', '빠진 후보 세액', '법정신고기한', '경정청구 기한', '상태']];
    const rows = keys.map(k => { const g = byP.get(k)!; const filedTax = hasB ? g.tax - g.miss.reduce((s, r) => s + r.tax, 0) : manual(k); const diff = hasB ? g.miss.reduce((s, r) => s + r.tax, 0) : Math.max(0, g.tax - filedTax); const st = g.p.days < 0 ? '경정청구 기한 지남' : g.p.due > today ? '아직 신고 전(확정신고에 넣는다)' : `청구 가능 D-${g.p.days}`;
      out.push([g.p.name, g.n, g.tax, hasB ? g.n - g.miss.length : filedTax, hasB ? g.miss.length : (diff ? '—' : 0), diff, g.p.due, g.p.claim, st]);
      return `<tr class="${diff && g.p.days >= 0 && g.p.due <= today ? 'v-check' : ''}"><th scope="row">${esc(g.p.name)}</th><td>${g.n}</td><td>${fmt(g.tax)}</td><td>${hasB ? `${g.n - g.miss.length}건` : `<input type="text" inputmode="numeric" data-filed="${k}" value="${filedTax ? fmt(filedTax) : ''}" placeholder="신고서 (10)+(12)+(44)+(45) 세액" style="width:11em" />`}</td><td>${hasB ? g.miss.length : (diff ? '—' : 0)}</td><td><strong>${fmt(diff)}</strong></td><td>${g.p.due}</td><td>${g.p.claim}</td><td class="keep">${esc(st)}</td></tr>`; }).join('');
    const missList = hasB ? keys.flatMap(k => byP.get(k)!.miss.map(r => `<li>${r.d} ${esc(r.supplier || r.desc)}${r.sreg ? ` (${esc(r.sreg)})` : ''} — 공급가액 ${fmt(r.amt)} · 세액 ${fmt(r.tax)}</li>`)) : [];
    const otherList = other.map(r => { const fd = fixDue(r.d); return `<li>${r.d} ${esc(r.supplier || r.desc)} — 세액 ${fmt(r.tax)} · 공급받는 자 ${esc(r.preg)} — 우리 명의가 아니라 경정청구 대상이 아닙니다. 수정세금계산서 기한 ${fd?.due ?? '?'}${fd && fd.days < 0 ? '(지남 — 착오 정정이 아니면 불가)' : ''}</li>`; });
    $('rv-result')!.innerHTML = `<div class="section-head"><h2>과세기간별 비교 <span class="meta">${hasB ? `신고 내역 ${B.length}건과 맞춤(맞은 건 ${matched})` : '신고한 매입세액을 과세기간마다 넣으면 차이가 계산됩니다'}</span></h2></div>
      <div class="scroll-x"><table class="data-table vat-table" data-stack="off"><caption>지난 신고 점검 — 수취 매입세액과 신고 매입세액(참고용, ${today})</caption><thead><tr>${out[0].map(h => `<th scope="col">${esc(String(h))}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>
      ${hasB ? '' : '<p class="meta">신고 세액을 넣은 뒤 다시 「과세기간별로 견주기」를 누르면 차이가 계산됩니다. 홈택스 「신고내역 조회」의 신고서에서 (10)(12)(44)(45) 세액을 더한 값입니다.</p>'}
      ${missList.length ? `<h3>신고 내역에 없는 수취 건 ${missList.length}건 — 경정청구 후보</h3><ul class="meta-list">${missList.join('')}</ul>` : ''}
      ${otherList.length ? `<h3>우리 명의가 아닌 세금계산서 ${other.length}건</h3><ul class="meta-list">${otherList.join('')}</ul>` : ''}
      <div class="callout warn"><strong>차이가 곧 환급액은 아닙니다.</strong> 빠진 후보 가운데 ① 면세·행정 일에만 쓴 것(불공제) ② 토지·승용차·접대비 ③ 과세·면세 공통 지출(안분해야 함) ④ 증빙 요건을 못 갖춘 것은 빼야 합니다. 건마다 <a href="/vat/tools/">지출 건 판정</a>으로 확인하고, 남는 것을 과세기간별로 경정청구합니다. 반대로 매출을 빠뜨린 것이 있으면 수정신고 대상입니다.</div>
      <h3>경정청구 절차</h3><ul class="meta-list"><li>${esc(D.rules.filing.claim ?? '')}</li><li>홈택스 「경정청구」 메뉴에서 과세기간을 고르고 매입세액을 고친 신고서와 매입처별 세금계산서합계표·신용카드매출전표등 수령명세서(추가분)를 냅니다. 세무서는 2개월 안에 결과를 통지합니다.</li><li>근거: ${lawLink(D, { law: 'basic', art: '제45조의2' })} · ${lawLink(D, { law: 'decree', art: '제74조' })} · ${lawLink(D, { law: 'act', art: '제54조' })}</li></ul>
      <div class="actions no-print"><button type="button" class="btn secondary" id="rv-csv">비교표 CSV 내려받기</button></div>`;
    $('rv-csv')?.addEventListener('click', () => downloadText(`지난신고점검-${today}.csv`, toCsv(out), 'text/csv;charset=utf-8'));
    $('rv-result')!.querySelectorAll<HTMLInputElement>('[data-filed]').forEach(i => i.addEventListener('change', () => { i.value = num(i.value) ? fmt(num(i.value)) : ''; }));
  }
}
