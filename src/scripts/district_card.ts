/**
 * 구·군 한 장 요약(Word·PDF) — /stats/districts/ (운영자 지시 2026-10-26 '1 2 3 다 해봐').
 * 페이지의 #gu-data JSON(화면과 같은 값)만 담는다. Word 는 한글에서 바로 열어 편집·HWP 저장이 된다(HWPX 는 시험 관문 뒤).
 * 공개 자료, 값 그대로, 평가·순위 없음.
 */
import { p, table, safeName, today, type Block } from './pdf';

type Gu = { name: string; rows: [string, string, string][]; tables: { title: string; head: string[]; rows: string[][]; note?: string }[] };
type Data = { url: string; built: string; sources: string; gu: Gu[] };

function blocks(d: Data, g: Gu): Block[] {
  const out: Block[] = [
    p('kicker', [`구·군 경제 현황  ·  대구광역시`, 'kicker']),
    p('title', [`${g.name} 경제 현황`, 'title']), p('rule', ['', 'caption']),
    p('h3', ['주요 숫자', 'h3']),
    table([['항목', '값', '기준·시점'], ...g.rows], { widths: [15000, 11000, 22188] }),
    p('spacer', ['', 'caption']),
  ];
  for (const t of g.tables) {
    if (!t.rows.length) continue;
    out.push(p('h3', [t.title, 'h3']));
    out.push(table([t.head, ...t.rows]));
    if (t.note) out.push(p('note', [t.note, 'note']));
    out.push(p('spacer', ['', 'caption']));
  }
  out.push(p('note', ['근거마다 세는 곳이 다릅니다 — 인구·취업자·통근은 사는 곳, 국민연금은 사업장 주소, 기업 수는 공장 등록, 전입·전출은 주민등록 신고 기준이라 서로 더하거나 나누지 않습니다.', 'note']));
  out.push(p('src', [`출처: ${d.sources}. ${d.url}, ${today()} 내려받음. 공개 자료를 그대로 옮긴 것으로 평가·순위가 아닙니다.`, 'src']));
  return out;
}

function init(): void {
  const el = document.getElementById('gu-data');
  const sel = document.getElementById('gu-sel') as HTMLSelectElement | null;
  if (!el || !sel) return;
  const d = JSON.parse(el.textContent || '{}') as Data;
  const cur = () => d.gu.find(x => x.name === sel.value) ?? d.gu[0];
  const status = document.getElementById('gu-status');
  const busy = async (btn: HTMLButtonElement, fn: () => Promise<void>) => {
    const t = btn.textContent; btn.disabled = true; btn.textContent = '만드는 중…';
    try { await fn(); if (status) status.textContent = ''; }
    catch (e) { console.error(e); if (status) status.textContent = '파일을 만들지 못했습니다. 새로고침 뒤 다시 눌러 주세요.'; }
    finally { btn.disabled = false; btn.textContent = t; }
  };
  document.getElementById('gu-docx')?.addEventListener('click', e => busy(e.currentTarget as HTMLButtonElement, async () => {
    const g = cur();
    const { buildDocx } = await import('./company_docx');
    const blob = await buildDocx(blocks(d, g), `${g.name} 경제 현황`);
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${safeName(g.name)} 경제 현황.docx`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }));
  document.getElementById('gu-pdf')?.addEventListener('click', e => busy(e.currentTarget as HTMLButtonElement, async () => {
    const g = cur();
    const { buildPdf, downloadPdf } = await import('./pdf');
    downloadPdf(`${safeName(g.name)} 경제 현황.pdf`, await buildPdf(blocks(d, g), `${g.name} 경제 현황`, { landscape: false }));
  }));
  // 카드의 '한 장 받기' 링크: 선택 상자를 그 구·군으로 바꾸고 위로
  document.querySelectorAll<HTMLAnchorElement>('a[data-gu]').forEach(a => a.addEventListener('click', ev => {
    ev.preventDefault(); sel.value = a.dataset.gu!; document.getElementById('gu-dl')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); sel.focus();
  }));
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
