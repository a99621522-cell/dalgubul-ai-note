/**
 * 그래프 도구 — figure.chart(인라인 SVG) 아래에 「PNG 저장」「SVG 저장」「그래프 복사」「캡션 복사」 단추(docs/prompts/site_desktop_hwp_ui.md, 2026-10-06).
 * PNG 는 흰 바탕·2배 해상도(한글 본문 폭 150mm 에 300dpi 상당), 캡션은 '그림. 제목 — 자료: …' 문장. 서버 없음.
 */
const clean = (s: string) => s.replace(/\s+/g, ' ').trim();
const download = (name: string, blob: Blob) => { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); };
const safe = (s: string) => s.replace(/[\\/:*?"<>|\n]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80);
const today = () => new Date().toISOString().slice(0, 10);

function visibleSvg(fig: HTMLElement): SVGSVGElement | null {
  return Array.from(fig.querySelectorAll<SVGSVGElement>('svg')).find(s => s.getBoundingClientRect().width > 0) ?? fig.querySelector('svg');
}
function serialize(svg: SVGSVGElement): { xml: string; w: number; h: number } {
  const c = svg.cloneNode(true) as SVGSVGElement;
  const r = svg.getBoundingClientRect();
  const vb = svg.viewBox.baseVal; const w = vb?.width || r.width || 800, h = vb?.height || r.height || 400;
  c.setAttribute('xmlns', 'http://www.w3.org/2000/svg'); c.setAttribute('width', String(w)); c.setAttribute('height', String(h));
  // 페이지 CSS 변수를 쓰는 색은 그림 밖에서 사라지므로 계산된 색으로 박는다
  const src = svg.querySelectorAll<SVGElement>('*'), dst = c.querySelectorAll<SVGElement>('*');
  src.forEach((el, i) => { const cs = getComputedStyle(el); const d = dst[i]; if (!d) return;
    for (const k of ['fill', 'stroke', 'font-family', 'font-size', 'font-weight', 'opacity', 'stroke-width'] as const) { const v = cs.getPropertyValue(k); if (v && v !== 'none' || k === 'fill' || k === 'stroke') d.style.setProperty(k, v); } });
  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect'); bg.setAttribute('width', '100%'); bg.setAttribute('height', '100%'); bg.setAttribute('fill', '#ffffff'); c.insertBefore(bg, c.firstChild);
  return { xml: new XMLSerializer().serializeToString(c), w, h };
}
async function toPng(svg: SVGSVGElement, scale = 2): Promise<Blob> {
  const { xml, w, h } = serialize(svg);
  const url = URL.createObjectURL(new Blob([xml], { type: 'image/svg+xml;charset=utf-8' }));
  try {
    const img = new Image(); img.decoding = 'async';
    await new Promise<void>((ok, no) => { img.onload = () => ok(); img.onerror = () => no(new Error('svg')); img.src = url; });
    const cv = document.createElement('canvas'); cv.width = Math.round(w * scale); cv.height = Math.round(h * scale);
    const ctx = cv.getContext('2d')!; ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, cv.width, cv.height); ctx.drawImage(img, 0, 0, cv.width, cv.height);
    return await new Promise<Blob>((ok, no) => cv.toBlob(b => (b ? ok(b) : no(new Error('png'))), 'image/png'));
  } finally { URL.revokeObjectURL(url); }
}
function captionOf(fig: HTMLElement): string {
  const cap = fig.querySelector('figcaption'); const t = cap ? clean((cap as HTMLElement).innerText) : clean(document.title.replace(/\s*[|·-]\s*다잇다.*$/, ''));
  const src = /자료|출처/.test(t) ? '' : ' — 자료: daitda.co.kr' + location.pathname;
  return `그림. ${t}${src} (${today()} 받음)`;
}
function toast(msg: string): void {
  let t = document.getElementById('tt-toast');
  if (!t) { t = document.createElement('div'); t.id = 'tt-toast'; t.setAttribute('role', 'status'); t.setAttribute('aria-live', 'polite'); document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('on'); clearTimeout((t as any)._tm); (t as any)._tm = setTimeout(() => t!.classList.remove('on'), 2200);
}

export function attachChart(fig: HTMLElement): void {
  if (fig.dataset.ctools || !fig.querySelector('svg')) return; fig.dataset.ctools = '1';
  const bar = document.createElement('div'); bar.className = 'chart-tools';
  const mk = (label: string, title: string) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'btn secondary'; b.textContent = label; b.title = title; bar.appendChild(b); return b; };
  const name = () => safe(clean((fig.querySelector('figcaption') as HTMLElement | null)?.innerText || document.title));
  mk('PNG 저장', '흰 바탕 2배 해상도 — 한글 「그림 넣기」용').addEventListener('click', async () => { const s = visibleSvg(fig); if (!s) return; try { download(`${name()}.png`, await toPng(s, 2)); } catch { toast('PNG 를 만들지 못했습니다'); } });
  mk('SVG 저장', '벡터 원본').addEventListener('click', () => { const s = visibleSvg(fig); if (!s) return; download(`${name()}.svg`, new Blob([serialize(s).xml], { type: 'image/svg+xml' })); });
  mk('그래프 복사', '그림(PNG)으로 복사 — 한글·워드에 바로 붙여넣기').addEventListener('click', async () => { const s = visibleSvg(fig); if (!s) return;
    try { const png = await toPng(s, 2); await navigator.clipboard.write([new ClipboardItem({ 'image/png': png })]); toast('그래프를 그림으로 복사했습니다'); } catch { toast('이 브라우저는 그림 복사를 지원하지 않습니다 — PNG 저장을 쓰세요'); } });
  mk('캡션 복사', "'그림. 제목 — 자료' 문장").addEventListener('click', async () => { try { await navigator.clipboard.writeText(captionOf(fig)); toast('캡션 복사됨'); } catch { toast('복사 실패'); } });
  const after = fig.querySelector('figcaption') ?? fig.lastElementChild;
  (after ?? fig).insertAdjacentElement(after ? 'afterend' : 'beforeend', bar);
}
export function init(): void { document.querySelectorAll<HTMLElement>('figure.chart, figure.tcard').forEach(attachChart); }
if (typeof document !== 'undefined') { if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init(); }
