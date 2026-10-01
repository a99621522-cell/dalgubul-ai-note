/**
 * 표 도구 — 사이트의 모든 통계표(table.data-table) 아래에 「한글 표 복사」「PDF 내려받기」 단추를 붙인다.
 * 공무원 문서는 대부분 한글(HWP)이라 표를 바로 붙여넣게 한다(운영자 지시 2026-09-27).
 * 복사는 클립보드에 HTML 표(한글·워드·엑셀에 표로 붙음)와 탭 구분 글을 같이 넣는다. 파일은 pdf.ts 로 브라우저에서 만든 PDF
 * (HWPX 내려받기는 한글에서 깨져 PDF 로 바꿈, 운영자 지시 2026-10-01).
 */
import { buildPdf, downloadPdf, p, table, safeName, today, type Block } from './pdf';

const clean = (s: string) => s.replace(/\s+/g, ' ').trim();

function grid(tbl: HTMLTableElement): { head: string[][]; body: string[][] } {
  const rows = (trs: HTMLTableRowElement[]) => trs.map(tr => Array.from(tr.cells).filter(c => getComputedStyle(c).display !== 'none').map(c => clean((c as HTMLElement).innerText)));
  const head = tbl.tHead ? rows(Array.from(tbl.tHead.rows)) : [];
  const body = rows(Array.from(tbl.tBodies).flatMap(b => Array.from(b.rows)));
  return { head, body };
}

/** 표 바로 위의 제목(h1~h3 또는 .section-head) — 없으면 문서 제목 */
function titleOf(anchor: Element): string {
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

/** 표 바로 뒤의 '출처…' 문장 */
function sourceOf(anchor: Element): string {
  const n = anchor.nextElementSibling;
  if (n && n.matches('p.meta, .meta') && /출처|기준/.test((n as HTMLElement).innerText)) return clean((n as HTMLElement).innerText);
  return '';
}

const NUM = /^[\d,.%~\-–+\s곳명건개년월억원만천]+$/;
function html(g: { head: string[][]; body: string[][] }): string {
  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const th = (s: string) => `<th style="border:1px solid #9db0cc;background:#eef3fa;padding:4px 8px;font-weight:bold;text-align:center">${esc(s)}</th>`;
  const td = (s: string) => `<td style="border:1px solid #d9dee7;padding:4px 8px;text-align:${NUM.test(s || 'x') ? 'right' : 'left'}">${esc(s)}</td>`;
  return `<table border="1" style="border-collapse:collapse;font-family:'맑은 고딕',sans-serif;font-size:10pt">` +
    (g.head.length ? `<thead>${g.head.map(r => `<tr>${r.map(th).join('')}</tr>`).join('')}</thead>` : '') +
    `<tbody>${g.body.map(r => `<tr>${r.map(td).join('')}</tr>`).join('')}</tbody></table>`;
}
const tsv = (g: { head: string[][]; body: string[][] }) => [...g.head, ...g.body].map(r => r.join('\t')).join('\n');

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

function flash(btn: HTMLButtonElement, text: string) {
  const old = btn.textContent; btn.textContent = text; btn.disabled = true;
  setTimeout(() => { btn.textContent = old; btn.disabled = false; }, 1800);
}

export function attach(tbl: HTMLTableElement): void {
  if (tbl.dataset.tools || tbl.closest('.no-tools')) return;
  tbl.dataset.tools = '1';
  const anchor = tbl.parentElement?.classList.contains('scroll-x') ? tbl.parentElement : tbl;
  const bar = document.createElement('div'); bar.className = 'table-tools';
  const mk = (label: string, title: string) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'btn secondary'; b.textContent = label; b.title = title; bar.appendChild(b); return b; };
  const copy = mk('한글 표 복사', '한글(HWP)·워드·엑셀에 붙여넣으면 표로 들어갑니다');
  const hwp = mk('PDF 내려받기', '이 표를 PDF 파일로 받습니다');
  copy.addEventListener('click', async () => {
    const g = grid(tbl);
    if (!g.body.length) return flash(copy, '표가 비어 있음');
    flash(copy, (await copyRich(html(g), tsv(g))) ? '복사됨 — 한글에 붙여넣기' : '복사 실패');
  });
  hwp.addEventListener('click', async () => {
    const g = grid(tbl);
    if (!g.body.length) return flash(hwp, '표가 비어 있음');
    const title = titleOf(anchor), src = sourceOf(anchor);
    const blocks: Block[] = [
      p('kicker', [document.title.replace(/\s*[|·-]\s*다잇다.*$/, ''), 'kicker']),
      p('title', [title, 'title']), p('rule', ['', 'caption']),
      table([...g.head.slice(0, 1), ...g.body], { head: g.head.length > 0 }),
      p('spacer', ['', 'caption']),
      p('src', [`출처: daitda.co.kr${location.pathname}, ${today()} 내려받음. ${src || '공개 자료를 같은 형식으로 집계한 것이며 평가·순위·추천이 아닙니다.'}`, 'src']),
    ];
    try {
      hwp.disabled = true; hwp.textContent = '만드는 중…';
      downloadPdf(`${safeName(title)}.pdf`, await buildPdf(blocks, title));
      hwp.textContent = 'PDF 내려받기'; hwp.disabled = false;
    } catch { hwp.disabled = false; flash(hwp, '만들기 실패'); }
  });
  anchor.insertAdjacentElement('afterend', bar);
}

export function init(): void {
  document.querySelectorAll<HTMLTableElement>('table.data-table').forEach(attach);
}
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
}
