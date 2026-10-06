/**
 * 표 도구 — 사이트의 모든 통계표(table.data-table) 아래에 「한글 표 복사 ▾」「CSV」「PDF 내려받기」 단추를 붙인다.
 * 공무원 문서는 대부분 한글(HWP)이라 표를 바로 붙여넣게 한다(운영자 지시 2026-09-27). 복사는 클립보드에 HTML 표(한글·워드·엑셀에 표로 붙음)와
 * 탭 구분 글을 같이 넣는다. 파일은 pdf.ts 로 브라우저에서 만든 PDF(HWPX 내려받기는 한글에서 깨져 PDF 로 바꿈, 운영자 지시 2026-10-01).
 *
 * 데스크톱·한글 업무 흐름 개선(docs/prompts/site_desktop_hwp_ui.md 실행, 2026-10-06):
 *  - HTML 페이로드: rowspan·colspan 그대로, <colgroup> 열 폭(화면 폭 비율), 머리 음영, 숫자 오른쪽·tabular, 맑은 고딕 10pt, 테두리 0.5pt(한글 0.12mm 근사),
 *    표 제목·출처 줄을 선택해서 같이 넣음. 글(text/plain)은 병합 칸을 채운 격자 TSV(엑셀·메모).
 *  - 복사 묶음: 표만 / 제목·출처 줄 포함 / 머리 없이 / 선택 행만(grid.ts 의 행 체크) / 개조식 요약 문장(값을 그대로 옮긴 사실 문장, 평가 없음)
 *  - CSV(UTF-8 BOM, 엑셀·한글 '표 변환'용). 숨긴 열(열 선택기·반응형)은 복사·CSV·PDF 에서 뺀다.
 */
import { buildPdf, downloadPdf, p, table, safeName, today, type Block } from './pdf';

const clean = (s: string) => s.replace(/\s+/g, ' ').trim();
const visible = (c: Element) => getComputedStyle(c).display !== 'none' && !c.classList.contains('grid-sel');   // 그리드의 행 체크 열·숨긴 열(.col-off)은 뺀다
type Cell = { text: string; rs: number; cs: number; th: boolean; num: boolean };
type Grid = { head: Cell[][]; body: Cell[][]; headFlat: string[][]; bodyFlat: string[][]; widths: number[] };
const NUM = /^[\d,.%~\-–+−\s곳명건개년월억원만천]+$/;

/** 선택 행(grid.ts 가 tr[aria-selected="true"] 로 표시)이 있으면 그 행만 */
function bodyRows(tbl: HTMLTableElement, onlySelected: boolean): HTMLTableRowElement[] {
  const all = Array.from(tbl.tBodies).flatMap(b => Array.from(b.rows)).filter(r => visible(r) && !r.classList.contains('empty'));
  if (!onlySelected) return all;
  const sel = all.filter(r => r.getAttribute('aria-selected') === 'true');
  return sel.length ? sel : all;
}

/** 칸 단위(병합 보존)와 채운 격자(병합 칸을 같은 값으로 채움) 둘 다 */
function grid(tbl: HTMLTableElement, opt: { onlySelected?: boolean; noHead?: boolean } = {}): Grid {
  const cells = (tr: HTMLTableRowElement): Cell[] => Array.from(tr.cells).filter(visible).map(c => {
    const t = clean((c as HTMLElement).innerText);
    return { text: t, rs: c.rowSpan || 1, cs: c.colSpan || 1, th: c.tagName === 'TH', num: NUM.test(t || 'x') && /\d/.test(t) };
  });
  const headTr = opt.noHead || !tbl.tHead ? [] : Array.from(tbl.tHead.rows).filter(visible);
  const head = headTr.map(cells), body = bodyRows(tbl, !!opt.onlySelected).map(cells);
  const flat = (rows: Cell[][]): string[][] => {   // rowspan·colspan 을 펼친 격자
    const out: string[][] = []; const carry: Record<number, [number, string]> = {};
    for (const r of rows) {
      const row: string[] = []; let col = 0;
      const take = () => { while (carry[col] && carry[col][0] > 0) { row.push(carry[col][1]); carry[col][0]--; col++; } };
      for (const c of r) { take(); for (let i = 0; i < c.cs; i++) { row.push(c.text); if (c.rs > 1) carry[col] = [c.rs - 1, c.text]; col++; } }
      take(); out.push(row);
    }
    return out;
  };
  // 열 폭: 화면에서 보이는 칸 폭(첫 본문 행 기준) → 비율. 병합 없는 행이 없으면 균등
  const ref = (body.length ? bodyRows(tbl, false)[0] : headTr[0]);
  const ws = ref ? Array.from(ref.cells).filter(visible).map(c => (c as HTMLElement).getBoundingClientRect().width || 1) : [];
  const sum = ws.reduce((a, b) => a + b, 0) || 1;
  return { head, body, headFlat: flat(head), bodyFlat: flat(body), widths: ws.map(w => w / sum) };
}

/** 표 바로 위의 제목(h1~h3 또는 .section-head) — 없으면 data-title, 그다음 문서 제목 */
function titleOf(tbl: HTMLTableElement, anchor: Element): string {
  if (tbl.dataset.title) return clean(tbl.dataset.title);
  const cap = tbl.querySelector('caption'); if (cap) return clean((cap as HTMLElement).innerText);
  let el: Element | null = anchor;
  for (let i = 0; el && i < 40; i++) {
    let sib = el.previousElementSibling;
    while (sib) {
      if (/^H[1-3]$/.test(sib.tagName)) return clean((sib as HTMLElement).innerText);
      const h = sib.matches('.section-head, header') ? sib.querySelector('h1,h2,h3') : null;
      if (h) return clean((h as HTMLElement).innerText);
      sib = sib.previousElementSibling;
    }
    el = el.parentElement;
    if (!el || el.tagName === 'MAIN') break;
  }
  return document.title.replace(/\s*[|·-]\s*다잇다.*$/, '');
}

/** 표 바로 뒤의 '출처…·기준…' 문장 */
function sourceOf(anchor: Element): string {
  let n = anchor.nextElementSibling;
  if (n && n.classList.contains('table-tools')) n = n.nextElementSibling;
  if (n && n.matches('p.meta, .meta, .tiny') && /출처|기준|자료/.test((n as HTMLElement).innerText)) return clean((n as HTMLElement).innerText).slice(0, 300);
  return '';
}
const sourceLine = (src: string) => `자료: ${src || '다잇다(daitda.co.kr) — 공개 자료를 같은 형식으로 옮긴 것이며 평가·순위·추천이 아닙니다'} · daitda.co.kr${location.pathname} · ${today()} 받음`;

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
/** 한글·워드·엑셀이 읽는 HTML 표(인라인 스타일만). 테두리 0.5pt ≈ 한글 0.12mm, 머리 음영, 숫자 오른쪽 */
function html(g: Grid, opt: { title?: string; source?: string } = {}): string {
  const FONT = "font-family:'맑은 고딕','Malgun Gothic',sans-serif;font-size:10pt";
  const cell = (c: Cell, head: boolean) => `<${head || c.th ? 'th' : 'td'}${c.rs > 1 ? ` rowspan="${c.rs}"` : ''}${c.cs > 1 ? ` colspan="${c.cs}"` : ''} style="border:0.5pt solid #000;padding:3pt 5pt;${head ? 'background:#eef3fa;font-weight:bold;text-align:center;vertical-align:middle' : c.th ? 'font-weight:bold;text-align:left' : `text-align:${c.num ? 'right' : 'left'}`};${c.num ? 'white-space:nowrap;font-variant-numeric:tabular-nums;' : ''}${FONT}">${esc(c.text) || '&nbsp;'}</${head || c.th ? 'th' : 'td'}>`;
  const cols = g.widths.length ? `<colgroup>${g.widths.map(w => `<col style="width:${(w * 100).toFixed(1)}%">`).join('')}</colgroup>` : '';
  const cap = opt.title ? `<p style="${FONT};font-weight:bold;margin:0 0 3pt">${esc(opt.title)}</p>` : '';
  const src = opt.source ? `<p style="${FONT};font-size:9pt;color:#444;margin:3pt 0 0">${esc(opt.source)}</p>` : '';
  return `${cap}<table border="1" cellspacing="0" cellpadding="3" style="border-collapse:collapse;border:0.5pt solid #000;${FONT};width:100%">${cols}` +
    (g.head.length ? `<thead>${g.head.map(r => `<tr>${r.map(c => cell(c, true)).join('')}</tr>`).join('')}</thead>` : '') +
    `<tbody>${g.body.map(r => `<tr>${r.map(c => cell(c, false)).join('')}</tr>`).join('')}</tbody></table>${src}`;
}
const tsv = (g: Grid, opt: { title?: string; source?: string } = {}) => [opt.title ? [opt.title] : null, ...g.headFlat, ...g.bodyFlat, opt.source ? [opt.source] : null].filter((r): r is string[] => !!r).map(r => r.join('\t')).join('\n');
/** 두 줄 머리는 '묶음 머리 열 머리'(예: 매출액(억 원) 2023) 한 줄로 합친다 — CSV·개조식 문장용 */
function headLabels(g: Grid): string[] {
  const head = g.headFlat.length ? g.headFlat[g.headFlat.length - 1] : [];
  const top = g.headFlat.length > 1 ? g.headFlat[0] : [];
  return head.map((h, i) => clean([top[i] && top[i] !== h ? top[i] : '', h].filter(Boolean).join(' ')));
}
const csv = (g: Grid) => '﻿' + [g.headFlat.length ? headLabels(g) : null, ...g.bodyFlat].filter((r): r is string[] => !!r).map(r => r.map(v => /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v).join(',')).join('\r\n');

/** 개조식 요약 문장: 행마다 '행 머리: 열1 값, 열2 값 …' — 표 값을 그대로 옮긴 사실 문장(평가·해석 없음). 처음 8행 */
function bullets(g: Grid, title: string, source: string): string {
  const labels = headLabels(g);
  const MAXC = 10;   // 열이 많은 표(상장기업 재무 26열)는 처음 10열까지만 — 문장이 너무 길어진다. 그리드 「열 선택」으로 숨기면 그 열은 빠진다
  const nCol = Math.max(...g.bodyFlat.map(r => r.length), 0);
  const lines = g.bodyFlat.slice(0, 8).map(r => {
    const name = r[0] || '';
    const parts = r.slice(1, MAXC).map((v, i) => (v && v !== '—' ? `${labels[i + 1] ?? ''} ${v}`.trim() : '')).filter(Boolean);
    return `○ ${name}${parts.length ? ': ' + parts.join(', ') : ''}`;
  });
  return [`□ ${title}`, ...lines, g.bodyFlat.length > 8 ? `  (이하 ${g.bodyFlat.length - 8}행 생략)` : '', nCol > MAXC ? `  (열 ${nCol}개 중 ${MAXC}개까지만 — 나머지는 표 복사로)` : '', `  ※ ${source}`].filter(Boolean).join('\n');
}

async function copyRich(h: string, plain: string): Promise<boolean> {
  try {
    if ('ClipboardItem' in window && navigator.clipboard?.write) {
      await navigator.clipboard.write([new ClipboardItem({ 'text/html': new Blob([h], { type: 'text/html' }), 'text/plain': new Blob([plain], { type: 'text/plain' }) })]);
      return true;
    }
  } catch { /* 아래 대체 방법 */ }
  const box = document.createElement('div');
  box.contentEditable = 'true'; box.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0'; box.innerHTML = h;
  document.body.appendChild(box);
  const range = document.createRange(); range.selectNodeContents(box);
  const sel = getSelection(); sel?.removeAllRanges(); sel?.addRange(range);
  let ok = false;
  try { ok = document.execCommand('copy'); } catch { ok = false; }
  sel?.removeAllRanges(); box.remove();
  if (!ok) { try { await navigator.clipboard.writeText(plain); ok = true; } catch { ok = false; } }
  return ok;
}
async function copyText(t: string): Promise<boolean> { try { await navigator.clipboard.writeText(t); return true; } catch { return false; } }

/** 짧은 알림(토스트) — 복사 결과·실패 원인 */
function toast(msg: string): void {
  let t = document.getElementById('tt-toast');
  if (!t) { t = document.createElement('div'); t.id = 'tt-toast'; t.setAttribute('role', 'status'); t.setAttribute('aria-live', 'polite'); document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('on');
  clearTimeout((t as any)._tm); (t as any)._tm = setTimeout(() => t!.classList.remove('on'), 2200);
}
function flash(btn: HTMLButtonElement, text: string) {
  const old = btn.textContent; btn.textContent = text; btn.disabled = true;
  setTimeout(() => { btn.textContent = old; btn.disabled = false; }, 1800);
}
const download = (name: string, blob: Blob) => { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); };

/** 좁은 화면 대응(디자인·UI 개선 2차 2026-10-06): ① 머리 칸 data-pri="2"(768px 아래 숨김)·"3"(1024px 아래 숨김) 열 우선순위
 *  ② 머리가 한 줄이고 병합이 없으며 열이 5개 이상인 표는 600px 아래에서 행마다 카드(td::before 에 머리 글자)로 — DOM 은 그대로라 복사·PDF 는 표 형태.
 *  data-stack="off" 로 끌 수 있고, 카드일 때 「표로 보기」 단추로 되돌린다. */
function responsive(tbl: HTMLTableElement, bar: HTMLElement): void {
  const head = tbl.tHead;
  if (!head || head.rows.length !== 1) return;
  const ths = Array.from(head.rows[0].cells);
  if (ths.some(c => c.colSpan > 1 || c.rowSpan > 1) || tbl.querySelector('tbody [rowspan], tbody [colspan]')) return;
  const rows = Array.from(tbl.tBodies).flatMap(b => Array.from(b.rows));
  ths.forEach((th, i) => {
    const cls = th.dataset.pri === '3' ? 'col-lg' : th.dataset.pri === '2' ? 'col-md' : '';
    if (cls) { th.classList.add(cls); rows.forEach(tr => tr.cells[i]?.classList.add(cls)); }
  });
  if (tbl.dataset.stack === 'off' || (ths.length < 5 && tbl.dataset.stack !== 'on')) return;
  const labels = ths.map(c => clean((c as HTMLElement).innerText));
  rows.forEach(tr => Array.from(tr.cells).forEach((c, i) => { if (c.tagName === 'TD' && !c.dataset.label) c.dataset.label = labels[i] ?? ''; }));
  tbl.classList.add('stackable');
  const b = document.createElement('button'); b.type = 'button'; b.className = 'btn secondary stack-toggle'; b.textContent = '표로 보기'; b.setAttribute('aria-pressed', 'false');
  b.addEventListener('click', () => { const on = tbl.classList.toggle('as-table'); b.textContent = on ? '카드로 보기' : '표로 보기'; b.setAttribute('aria-pressed', String(on)); });
  bar.prepend(b);
}

export function attach(tbl: HTMLTableElement): void {
  if (tbl.dataset.tools || tbl.closest('.no-tools')) return;
  tbl.dataset.tools = '1';
  const anchor = tbl.parentElement?.classList.contains('scroll-x') ? tbl.parentElement : tbl;
  const bar = document.createElement('div'); bar.className = 'table-tools';
  const mk = (label: string, title: string, parent: HTMLElement = bar) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'btn secondary'; b.textContent = label; b.title = title; parent.appendChild(b); return b; };
  // 복사 묶음: <details> 메뉴(키보드로 열고 닫힘)
  const menu = document.createElement('details'); menu.className = 'tt-menu';
  const sum = document.createElement('summary'); sum.className = 'btn secondary'; sum.textContent = '한글 표 복사 ▾'; sum.title = '한글(HWP)·워드·엑셀에 붙여넣으면 표로 들어갑니다';
  const list = document.createElement('div'); list.className = 'tt-list'; list.setAttribute('role', 'menu');
  menu.append(sum, list); bar.appendChild(menu);
  const item = (label: string, title: string, fn: () => Promise<boolean | string>) => {
    const b = mk(label, title, list); b.className = 'tt-item'; b.setAttribute('role', 'menuitem');
    b.addEventListener('click', async () => { menu.open = false; const r = await fn(); toast(typeof r === 'string' ? r : r ? `복사됨 — 한글에 붙여넣기 (${label})` : '복사 실패 — 브라우저가 막았거나 표가 비어 있음'); });
  };
  const info = () => ({ title: titleOf(tbl, anchor), source: sourceLine(sourceOf(anchor)) });
  item('표만 복사', '머리 포함, 제목·출처 없이', async () => { const g = grid(tbl); return g.body.length ? copyRich(html(g), tsv(g)) : '표가 비어 있음'; });
  item('제목·출처 줄 포함', '표 위에 제목, 아래에 자료 출처·받은 날짜 문단을 같이 넣습니다', async () => { const g = grid(tbl), o = info(); return g.body.length ? copyRich(html(g, o), tsv(g, o)) : '표가 비어 있음'; });
  item('머리 없이(값만)', '열 머리 없이 본문 행만', async () => { const g = grid(tbl, { noHead: true }); return g.body.length ? copyRich(html(g), tsv(g)) : '표가 비어 있음'; });
  item('선택 행만', '행 앞 체크(그리드 표)로 고른 행만 — 고른 행이 없으면 전체', async () => { const g = grid(tbl, { onlySelected: true }); return g.body.length ? copyRich(html(g), tsv(g)) : '표가 비어 있음'; });
  item('개조식 요약 문장', '표 값을 그대로 옮긴 사실 문장(처음 8행) — 평가·해석 없음', async () => { const g = grid(tbl), o = info(); if (!g.body.length) return '표가 비어 있음'; return (await copyText(bullets(g, o.title, o.source))) ? '개조식 문장 복사됨 — 한글에 붙여넣기' : '복사 실패'; });
  const help = document.createElement('p'); help.className = 'tt-help tiny muted';
  help.textContent = '한글에 붙인 뒤: ① 표 속성 → 글자처럼 취급 ② 셀 테두리 0.12mm ③ 표가 안 서면 워드에 먼저 붙이고 한글로 (또는 CSV → 표 만들기)';
  list.appendChild(help);
  const csvBtn = mk('CSV', '엑셀·한글 표 변환용 CSV(UTF-8)');
  csvBtn.addEventListener('click', () => { const g = grid(tbl); if (!g.body.length) return flash(csvBtn, '표가 비어 있음'); download(`${safeName(titleOf(tbl, anchor))}.csv`, new Blob([csv(g)], { type: 'text/csv;charset=utf-8' })); });
  const hwp = mk('PDF 내려받기', '이 표를 PDF 파일로 받습니다');
  hwp.addEventListener('click', async () => {
    const g = grid(tbl);
    if (!g.body.length) return flash(hwp, '표가 비어 있음');
    const title = titleOf(tbl, anchor), src = sourceOf(anchor);
    const blocks: Block[] = [
      p('kicker', [document.title.replace(/\s*[|·-]\s*다잇다.*$/, ''), 'kicker']),
      p('title', [title, 'title']), p('rule', ['', 'caption']),
      table([...g.headFlat.slice(-1), ...g.bodyFlat], { head: g.headFlat.length > 0 }),
      p('spacer', ['', 'caption']),
      p('src', [`출처: daitda.co.kr${location.pathname}, ${today()} 내려받음. ${src || '공개 자료를 같은 형식으로 집계한 것이며 평가·순위·추천이 아닙니다.'}`, 'src']),
    ];
    try {
      hwp.disabled = true; hwp.textContent = '만드는 중…';
      downloadPdf(`${safeName(title)}.pdf`, await buildPdf(blocks, title, { landscape: g.headFlat.at(-1)!.length > 7 }));
      hwp.textContent = 'PDF 내려받기'; hwp.disabled = false;
    } catch { hwp.disabled = false; flash(hwp, '만들기 실패'); }
  });
  document.addEventListener('click', e => { if (!menu.contains(e.target as Node)) menu.open = false; });
  menu.addEventListener('keydown', e => { if (e.key === 'Escape') { menu.open = false; sum.focus(); } });
  anchor.insertAdjacentElement('afterend', bar);
  responsive(tbl, bar);
}

/** 가로로 넘치는 .scroll-x 는 키보드로도 밀 수 있어야 한다(axe scrollable-region-focusable): 넘칠 때만 tabindex=0·role=region */
function focusableScroll(): void {
  document.querySelectorAll<HTMLElement>('.scroll-x').forEach(el => {
    const over = el.scrollWidth > el.clientWidth + 1;
    if (over) { el.tabIndex = 0; el.setAttribute('role', 'region'); if (!el.getAttribute('aria-label')) el.setAttribute('aria-label', (el.querySelector('table')?.getAttribute('data-title') || '표') + ' — 가로로 밀어 보기'); }
    else { el.removeAttribute('tabindex'); el.removeAttribute('role'); }
  });
}
let rt = 0;
export function init(): void {
  document.querySelectorAll<HTMLTableElement>('table.data-table').forEach(attach);
  focusableScroll();
  window.addEventListener('resize', () => { clearTimeout(rt); rt = window.setTimeout(focusableScroll, 150); });
}
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
}
