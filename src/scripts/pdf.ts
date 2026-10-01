/**
 * 브라우저에서 PDF 만들기 — 표 도구(table_tools)·기업 카드(company_card)·지침 검토 의견서(budget_check)가 쓴다.
 * 한글(HWPX) 파일이 한글 프로그램에서 깨져(운영자 확인 2026-10-01) PDF 로 바꿨다. 서버 호출 없음.
 * 글꼴은 Pretendard TTF(public/fonts/pdf, SIL OFL)를 누를 때만 받아 통째로 넣는다(PDF 약 1.2MB). pdf-lib 의 subset 은
 * 한글 글자를 빠뜨려(2026-10-01 확인: '대구' 등이 빈칸) 쓰지 않는다. 굵은 글씨는 같은 글꼴을 조금 비켜 두 번 그려 낸다.
 * 입력은 hwpx.ts 와 같은 Block(p·table)이라 호출하는 쪽은 buildHwpx 대신 buildPdf 만 부르면 된다.
 */
import { PDFDocument, rgb, type PDFFont, type PDFPage } from 'pdf-lib';
import fontkit from '@pdf-lib/fontkit';
import type { Block, Cell } from './hwpx';

export { p, table, safeName, today, type Block } from './hwpx';

let font: Promise<ArrayBuffer> | null = null;
const loadFont = () => (font ??= fetch('/fonts/pdf/Pretendard-Regular.ttf').then(r => { if (!r.ok) throw new Error('font'); return r.arrayBuffer(); }));

const MM = 72 / 25.4;
const INK = rgb(0.1, 0.1, 0.1), MUTED = rgb(0.42, 0.42, 0.42), PRIMARY = rgb(0.106, 0.31, 0.608);
const LINE = rgb(0.85, 0.87, 0.9), HEAD_BG = rgb(0.933, 0.953, 0.98), HEAD_LINE = rgb(0.616, 0.69, 0.8);
const NUMERIC = /^[\d,.%~\-–—\s곳명건개년월억원만천+]+$/;
type Style = { size: number; bold?: boolean; color?: ReturnType<typeof rgb>; before: number; after: number };
const STYLES: Record<string, Style> = {
  kicker: { size: 9, color: PRIMARY, before: 0, after: 2 },
  title: { size: 16, bold: true, before: 2, after: 4 },
  h2: { size: 13, bold: true, before: 10, after: 4 },
  h3: { size: 11.5, bold: true, before: 8, after: 3 },
  body: { size: 10, before: 2, after: 3 },
  note: { size: 8.5, color: MUTED, before: 1, after: 3 },
  caption: { size: 8.5, color: MUTED, before: 1, after: 2 },
  src: { size: 8, color: MUTED, before: 4, after: 2 },
};

/** 그리기·너비 단위 — 한글·띄어쓰기 묶음은 통째로, 그 밖(숫자·영문·기호)은 한 글자씩.
 *  Pretendard 는 숫자 사이 '-'·'~'·':' 같은 글자를 다른 모양으로 바꾸는데(calt), pdf-lib 가 바꾼 글자의 폭을 PDF 에 잘못 적어
 *  '2026- 10' 처럼 틈이 생기거나 뒤 글자와 겹친다(2026-10-01 확인). 한 글자씩 그리면 바뀌지 않는다. */
const tokens = (t: string): string[] => t.match(/[가-힣ㄱ-ㅎㅏ-ㅣ ]+|[\s\S]/gu) ?? [];
const wcache = new WeakMap<PDFFont, Map<string, number>>();
function measure(font: PDFFont, t: string, size: number): number {
  let m = wcache.get(font); if (!m) wcache.set(font, (m = new Map()));
  let w = 0;
  for (const k of tokens(t)) { let v = m.get(k); if (v === undefined) { v = font.widthOfTextAtSize(k, 1000) / 1000; m.set(k, v); } w += v; }
  return w * size;
}

const cellText = (c: Cell): string => (typeof c === 'string' ? c : c.map(b => ('segs' in b ? b.segs.map(s => s[0]).join('') : '')).join(' '));

/** 폭에 맞춰 줄 나누기 — 띄어쓰기에서 먼저 끊고, 한 낱말이 폭보다 길면 글자 단위로 */
function wrap(text: string, font: PDFFont, size: number, width: number): string[] {
  const out: string[] = [];
  for (const para of String(text ?? '').split('\n')) {
    let line = '';
    for (const word of para.split(/(\s+)/)) {
      if (!word) continue;
      const cand = line + word;
      if (measure(font, cand, size) <= width) { line = cand; continue; }
      if (line.trim()) { out.push(line.trimEnd()); line = ''; }
      let w = word.replace(/^\s+/, '');
      while (w && measure(font, w, size) > width) {
        let k = w.length;
        while (k > 1 && measure(font, w.slice(0, k), size) > width) k--;
        out.push(w.slice(0, k)); w = w.slice(k);
      }
      line = w;
    }
    out.push(line.trimEnd());
  }
  return out.length ? out : [''];
}

export async function buildPdf(blocks: Block[], title = '', opt: { landscape?: boolean } = {}): Promise<Blob> {
  const reg = await loadFont();
  const doc = await PDFDocument.create();
  doc.registerFontkit(fontkit);
  const F = await doc.embedFont(reg, { subset: false }), B = F;
  // 굵게: 같은 글꼴을 0.35pt 비켜 한 번 더 그린다
  // tokens() 단위로 나눠 그린다(위 measure 와 같은 단위라 너비 계산과 그림이 맞는다)
  const text = (pg: PDFPage, t: string, o: { x: number; y: number; size: number; color?: ReturnType<typeof rgb> }, bold = false) => {
    let x = o.x;
    for (const piece of tokens(t)) {
      if (piece.trim()) {
        pg.drawText(piece, { ...o, x, font: F, color: o.color ?? INK });
        if (bold) pg.drawText(piece, { ...o, x: x + Math.max(0.25, o.size * 0.03), font: F, color: o.color ?? INK });
      }
      x += measure(F, piece, o.size);
    }
  };
  doc.setTitle(title); doc.setCreator('다잇다 daitda.co.kr'); doc.setProducer('daitda.co.kr'); doc.setLanguage('ko-KR');
  const wide = opt.landscape ?? blocks.some(b => 'table' in b && Math.max(...b.table.map(r => r.length)) >= 7);
  const [PW, PH] = wide ? [297 * MM, 210 * MM] : [210 * MM, 297 * MM];
  const M = 15 * MM, W = PW - 2 * M, BOTTOM = M + 8;
  let page: PDFPage = doc.addPage([PW, PH]);
  let y = PH - M;
  const newPage = () => { page = doc.addPage([PW, PH]); y = PH - M; };
  const ensure = (h: number) => { if (y - h < BOTTOM) newPage(); };

  for (const b of blocks) {
    if ('segs' in b) {
      const st = STYLES[b.p];
      if (b.p === 'spacer') { y -= 6; continue; }
      if (b.p === 'rule') { ensure(6); page.drawLine({ start: { x: M, y: y - 2 }, end: { x: M + W, y: y - 2 }, thickness: 1.2, color: INK }); y -= 8; continue; }
      const s = st ?? STYLES.body, font = s.bold ? B : F, lh = s.size * 1.45;
      const body = b.segs.map(x => x[0]).join('');
      if (!body.trim()) { y -= s.before + s.after; continue; }
      y -= s.before;
      for (const ln of wrap(body, font, s.size, W)) {
        ensure(lh);
        text(page, ln, { x: M, y: y - s.size, size: s.size, color: s.color ?? INK }, !!s.bold);
        y -= lh;
      }
      y -= s.after;
      continue;
    }
    // 표
    const rows = b.table.map(r => r.map(cellText));
    const nCol = Math.max(...rows.map(r => r.length));
    rows.forEach(r => { while (r.length < nCol) r.push(''); });
    const size = nCol >= 8 ? 7.5 : nCol >= 6 ? 8 : 9, pad = 3, lh = size * 1.35;
    let widths: number[];
    if (b.widths && b.widths.length === nCol) {
      const sum = b.widths.reduce((a, c) => a + c, 0); widths = b.widths.map(w => (w / sum) * W);
    } else {   // 내용 길이로 나누되 한 열이 너무 좁거나 넓지 않게
      const want = Array.from({ length: nCol }, (_, j) => Math.min(Math.max(...rows.map(r => measure(F, r[j] || '', size))) + 2 * pad, W * 0.45));
      const min = Math.min(W / nCol, 18 * MM);
      const base = want.map(w => Math.max(w, min)); const sum = base.reduce((a, c) => a + c, 0);
      widths = base.map(w => (w / sum) * W);
    }
    const head = b.head !== false ? 1 : 0;
    const drawRow = (r: string[], isHead: boolean) => {
      const font = isHead ? B : F;
      const lines = r.map((c, j) => wrap(c, font, size, widths[j] - 2 * pad));
      const h = Math.max(...lines.map(l => l.length)) * lh + 2 * pad;
      if (y - h < BOTTOM) { newPage(); if (!isHead && head) drawRow(rows[0], true); }
      let x = M;
      r.forEach((c, j) => {
        const w = widths[j];
        page.drawRectangle({ x, y: y - h, width: w, height: h, color: isHead ? HEAD_BG : undefined, borderColor: isHead ? HEAD_LINE : LINE, borderWidth: 0.6 });
        const right = !isHead && NUMERIC.test(c || 'x');
        lines[j].forEach((ln, k) => {
          const tw = measure(font, ln, size);
          const tx = isHead ? x + (w - tw) / 2 : right ? x + w - pad - tw : x + pad;
          text(page, ln, { x: tx, y: y - pad - size - k * lh + 1.5, size }, isHead);
        });
        x += w;
      });
      y -= h;
    };
    y -= 2;
    rows.forEach((r, i) => drawRow(r, i < head));
    y -= 4;
  }
  // 쪽 번호
  const pages = doc.getPages();
  pages.forEach((pg, i) => {
    const t = `daitda.co.kr  ·  ${i + 1} / ${pages.length}`;
    text(pg, t, { x: PW - M - measure(F, t, 7.5), y: M / 2, size: 7.5, color: MUTED });
  });
  const bytes = await doc.save();
  return new Blob([bytes as BlobPart], { type: 'application/pdf' });
}

export function downloadPdf(name: string, blob: Blob): void {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name.endsWith('.pdf') ? name : `${name}.pdf`;
  document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 4000);   // 바로 지우면 파일 이름(download 속성)이 무시되는 브라우저가 있다
}
