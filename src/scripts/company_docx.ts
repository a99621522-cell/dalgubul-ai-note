/**
 * 기업 카드 Word(.docx) — 브라우저에서 docx 패키지(동적 import, 누를 때만 받음)로 만든다(docs/prompts/site_desktop_hwp_ui.md '붙임 꾸러미', 2026-10-06).
 * 한글(HWP)은 .docx 를 바로 열어 편집·HWP 저장이 되므로 HWPX 대신 Word 파일을 준다(HWPX 는 한글에서 깨져 내림, 2026-10-01). 내용은 pdf 판(company_card.ts)과 같은 Block 자료.
 * 글꼴은 맑은 고딕(한글·워드 모두 있음), 본문 10pt, 표 테두리 0.5pt, 머리 칸 음영. 공개 자료만, 평가·추천 없음.
 */
import type { Block } from './pdf';

export async function buildDocx(blocks: Block[], title: string): Promise<Blob> {
  const D = await import('docx');
  const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, AlignmentType, BorderStyle, ShadingType, HeadingLevel } = D;
  const font = { name: '맑은 고딕', eastAsia: '맑은 고딕' } as const;
  const border = { style: BorderStyle.SINGLE, size: 4, color: '888888' };   // 0.5pt
  const borders = { top: border, bottom: border, left: border, right: border };
  const run = (t: string, o: { bold?: boolean; size?: number; color?: string } = {}) => new TextRun({ text: t, bold: o.bold, size: o.size ?? 20, color: o.color, font });
  const children: InstanceType<typeof Paragraph | typeof Table>[] = [];
  for (const b of blocks) {
    if ('table' in b) {
      const total = 9000;   // twips(DXA) — A4 세로 본문 폭 약 160mm
      const rowsIn = b.table.map(r => r.map(c => typeof c === 'string' ? c : Array.isArray(c) ? '' : c.t ?? ''));
      const widths = b.widths?.length ? b.widths : rowsIn[0].map(() => 1);
      const sum = widths.reduce((a, c) => a + c, 0) || 1;
      const w = widths.map(x => Math.round(total * x / sum));
      const rows = rowsIn.map((r, ri) => new TableRow({ tableHeader: ri === 0 && b.head !== false, children: r.map((c, ci) => new TableCell({
        borders, width: { size: w[ci] ?? Math.round(total / r.length), type: WidthType.DXA },
        shading: ri === 0 && b.head !== false ? { type: ShadingType.CLEAR, fill: 'EEF3FA', color: 'auto' } : undefined,
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: [new Paragraph({ alignment: ri > 0 && /^[\d,.%~\-–+−\s]+$/.test(c) && /\d/.test(c) ? AlignmentType.RIGHT : AlignmentType.LEFT, children: [run(c, { bold: ri === 0 && b.head !== false, size: 18 })] })] })) }));
      children.push(new Table({ rows, width: { size: total, type: WidthType.DXA }, columnWidths: w }));
      continue;
    }
    if (!('segs' in b)) continue;   // 그림 블록은 Word 판에 넣지 않는다
    const text = b.segs.map(x => x[0]).join(''), style = b.segs[0]?.[1] ?? 'body';
    if (!text && (b.p === 'rule' || b.p === 'spacer')) { children.push(new Paragraph({ spacing: { after: 80 }, children: [] })); continue; }
    if (style === 'title') { children.push(new Paragraph({ heading: HeadingLevel.TITLE, spacing: { after: 120 }, children: [run(text, { bold: true, size: 32 })] })); continue; }
    if (style === 'h3') { children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 80 }, children: [run(text, { bold: true, size: 24 })] })); continue; }
    if (style === 'kicker') { children.push(new Paragraph({ spacing: { after: 40 }, children: [run(text, { size: 18, color: '555555' })] })); continue; }
    if (style === 'note' || style === 'src' || style === 'caption') { children.push(new Paragraph({ spacing: { before: 60, after: 60 }, children: [run(text, { size: 16, color: '555555' })] })); continue; }
    children.push(new Paragraph({ spacing: { after: 100 }, children: [run(text)] }));
  }
  const doc = new Document({ creator: '다잇다(daitda.co.kr)', title, styles: { default: { document: { run: { font: '맑은 고딕', size: 20 } } } },
    sections: [{ properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } }, children }] });
  return Packer.toBlob(doc);
}
