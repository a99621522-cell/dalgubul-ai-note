/** /vat/trend/ 납부액 추이·절감 현황표 — 절감 사유 보고용(운영자 지시 2026-10-27 '절감 사유에 맞게'). 저장된 신고 기록(filings)과 손으로 넣은 지난 기수 값을 모아
 *  기수별 매출세액(a)·매입세액(b)·납부액(a−b), 연도 합계, 전년 대비 차이를 표로. 절감 사유 메모는 localStorage(vat-trend-v1). 이 도구는 값을 옮길 뿐 평가하지 않는다. */
import { $, esc, num, fmt, loadData, getFilings, readJsonFile, periodInfo, downloadText, toCsv, ymd, type Data, type Filing, type PeriodKey } from './vat_rules';
type Row = { key: PeriodKey; out: number; inp: number; src: string };
const KEY = 'vat-trend-v1';
const D = loadData();
if (D) init(D);
function init(_D: Data) {
  let manual: Row[] = []; let memo = ''; try { const s = JSON.parse(localStorage.getItem(KEY) || '{}'); manual = s.manual ?? []; memo = s.memo ?? ''; } catch { /* */ }
  const files = new Map<PeriodKey, Filing>();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify({ manual, memo })); } catch { /* */ } };
  const fromFiling = (f: Filing): Row => { const c = (n: string) => f.cells[n]?.tax ?? 0; const out = c('1') + c('3') + c('4'); const c16 = c('10') + c('12') + c('13') + c('14') + c('44') + c('45') + c('48'); const c17 = c('53') + c('54'); return { key: f.period, out, inp: c16 - c17, src: '신고 기록' }; };
  const sel = $<HTMLSelectElement>('tr-period')!; const y = new Date().getFullYear(); sel.innerHTML = Array.from({ length: 6 }, (_, i) => y - 5 + i).flatMap(yy => ['1P', '1F', '2P', '2F'].map(k => `<option value="${yy}-${k}">${periodInfo(`${yy}-${k}`).name}</option>`)).join('');
  $<HTMLTextAreaElement>('tr-memo')!.value = memo; $('tr-memo')!.addEventListener('change', () => { memo = $<HTMLTextAreaElement>('tr-memo')!.value; save(); });
  $('tr-add')!.addEventListener('click', () => { const k = sel.value; manual = manual.filter(r => r.key !== k); manual.push({ key: k, out: num($<HTMLInputElement>('tr-out')!.value), inp: num($<HTMLInputElement>('tr-in')!.value), src: '직접 입력' }); save(); render(); });
  $<HTMLInputElement>('tr-open')?.addEventListener('change', async e => { for (const f of [...((e.target as HTMLInputElement).files ?? [])]) { try { const j = await readJsonFile(f) as Filing; if (j && j.v === 1 && j.period && j.cells) files.set(j.period, j); } catch { /* */ } } render(); });
  function render() {
    const all = new Map<PeriodKey, Row>(); for (const f of Object.values(getFilings())) all.set(f.period, fromFiling(f)); for (const f of files.values()) all.set(f.period, fromFiling(f)); for (const r of manual) all.set(r.key, r);
    const rows = [...all.values()].sort((a, b) => a.key.localeCompare(b.key)); if (!rows.length) { $('tr-table')!.innerHTML = '<p class="meta">신고 기록이 없습니다. 신고 준비에서 저장했거나 filing JSON 을 열거나, 지난 기수 값을 직접 넣으세요.</p>'; return; }
    const years = [...new Set(rows.map(r => r.key.slice(0, 4)))]; const yTot: Record<string, { out: number; inp: number; n: number }> = {};
    const body = years.map(yy => { const rs = rows.filter(r => r.key.startsWith(yy)); const t = { out: rs.reduce((s, r) => s + r.out, 0), inp: rs.reduce((s, r) => s + r.inp, 0), n: rs.length }; yTot[yy] = t; return rs.map((r, i) => `<tr>${i === 0 ? `<th scope="row" rowspan="${rs.length + 1}">${yy}</th>` : ''}<td>${esc(periodInfo(r.key).name.replace(/^\d{4}년 /, ''))}</td><td>${fmt(r.out)}</td><td>${fmt(r.inp)}</td><td>${fmt(r.out - r.inp)}</td><td class="note">${esc(r.src)}${r.src === '직접 입력' ? ` <button type="button" class="link-btn no-print" data-del="${r.key}">삭제</button>` : ''}</td></tr>`).join('') + `<tr class="total"><td>합계(${t.n}기수)</td><td>${fmt(t.out)}</td><td>${fmt(t.inp)}</td><td>${fmt(t.out - t.inp)}</td><td></td></tr>`; }).join('');
    const diffs = years.slice(1).map((yy, i) => { const a = yTot[years[i]], b = yTot[yy]; const pa = a.out - a.inp, pb = b.out - b.inp; return `<li>${yy}년과 ${years[i]}년 납부액 차이: ${fmt(pa)} − ${fmt(pb)} = <strong>${fmt(pa - pb)}</strong>${a.n !== b.n ? ` <span class="note">(기수 수가 다름 ${a.n}↔${b.n} — 같은 기수끼리 견줄 것)</span>` : ''}</li>`; }).join('');
    $('tr-table')!.innerHTML = `<div class="scroll-x"><table class="data-table vat-table form" data-stack="off"><caption>연도별 부가가치세 납부액 비교 — 매출세액(a) · 매입세액(b, 차감 매입세액) · 납부액(a−b)</caption><thead><tr><th scope="col">연도</th><th scope="col">구분</th><th scope="col">매출세액(a)</th><th scope="col">매입세액(b)</th><th scope="col">납부액(a−b)</th><th scope="col">출처</th></tr></thead><tbody>${body}</tbody></table></div>${diffs ? `<ul class="meta-list">${diffs}</ul>` : ''}<p class="meta">매입세액(b)은 신고서 (16) 매입세액 합계 − (17) 공제받지 못할 매입세액. 납부액에 경감·공제·가산세·예정고지는 넣지 않았습니다(신고서 (30)과 다를 수 있음). 값을 옮길 뿐 늘고 준 까닭은 아래 메모에 기관이 적습니다.</p>`;
    $('tr-table')!.querySelectorAll<HTMLButtonElement>('[data-del]').forEach(b => b.addEventListener('click', () => { manual = manual.filter(r => r.key !== b.dataset.del); save(); render(); }));
    $('tr-csv')!.onclick = () => downloadText(`부가세납부액추이-${ymd(new Date())}.csv`, toCsv([['연도', '구분', '매출세액', '매입세액', '납부액', '출처'], ...rows.map(r => [r.key.slice(0, 4), periodInfo(r.key).name, r.out, r.inp, r.out - r.inp, r.src]), ...years.map(yy => [yy, '합계', yTot[yy].out, yTot[yy].inp, yTot[yy].out - yTot[yy].inp, '']), ['', '절감 사유 메모', memo, '', '', '']]), 'text/csv;charset=utf-8');
  }
  $('tr-print')!.addEventListener('click', () => window.print());
  render();
}
