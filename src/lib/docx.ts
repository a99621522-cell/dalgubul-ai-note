/** 정책제안 리포트 → DOCX (내려받기용). 마크다운 본문을 제목·문단·목록·표·인용으로 옮긴다.
 *  글꼴 맑은 고딕 11pt, 제목은 Word 기본 제목 스타일(한글·Word 에서 열어 바로 편집). 외부 라이브러리 docx 만 사용. */
import {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, BorderStyle,
  AlignmentType, ExternalHyperlink, Footer, PageNumber, LevelFormat,
} from 'docx';

export type ReportMeta = {
  title: string; date: Date; area?: string; description?: string; summary?: string; url: string;
  faq: { q: string; a: string }[]; sources: { title: string; url: string; date?: string }[];
};

const FONT = '맑은 고딕';
const SIZE = 22; // half-points → 11pt

/** 인라인: **굵게**, *기울임*, `코드`, [글자](주소) */
function inline(text: string, base: { bold?: boolean; italics?: boolean; color?: string } = {}): (TextRun | ExternalHyperlink)[] {
  const out: (TextRun | ExternalHyperlink)[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  let last = 0; let m: RegExpExecArray | null;
  const push = (t: string, extra: Partial<{ bold: boolean; italics: boolean; font: string; color: string }> = {}) => {
    if (t) out.push(new TextRun({ text: t, font: FONT, size: SIZE, ...base, ...extra }));
  };
  while ((m = re.exec(text))) {
    push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('**')) push(tok.slice(2, -2), { bold: true });
    else if (tok.startsWith('`')) push(tok.slice(1, -1), { font: 'Consolas' });
    else if (tok.startsWith('[')) {
      const mm = tok.match(/^\[([^\]]+)\]\(([^)]+)\)$/)!;
      out.push(new ExternalHyperlink({ link: mm[2], children: [new TextRun({ text: mm[1], font: FONT, size: SIZE, style: 'Hyperlink', ...base })] }));
    } else push(tok.slice(1, -1), { italics: true });
    last = m.index + tok.length;
  }
  push(text.slice(last));
  return out;
}

const para = (text: string, opts: ConstructorParameters<typeof Paragraph>[0] = {}, base = {}) =>
  new Paragraph({ children: inline(text, base), spacing: { after: 120 }, ...(opts as object) });

function table(lines: string[]): Table {
  const rows = lines.filter(l => !/^\|?\s*:?-{2,}/.test(l)).map(l => l.replace(/^\||\|$/g, '').split('|').map(c => c.trim()));
  const width = Math.max(...rows.map(r => r.length));
  const border = { style: BorderStyle.SINGLE, size: 4, color: 'BFBFBF' };
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: rows.map((r, ri) => new TableRow({
      tableHeader: ri === 0,
      children: Array.from({ length: width }, (_, i) => new TableCell({
        borders: { top: border, bottom: border, left: border, right: border },
        shading: ri === 0 ? { fill: 'F2F2F2' } : undefined,
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({ children: inline(r[i] ?? '', ri === 0 ? { bold: true } : {}), spacing: { after: 0 } })],
      })),
    })),
  });
}

/** 마크다운 본문 → docx 요소 */
export function bodyToDocx(md: string): (Paragraph | Table)[] {
  const out: (Paragraph | Table)[] = [];
  const lines = md.replace(/\r/g, '').split('\n');
  let i = 0; let buf: string[] = [];
  const flush = () => { if (buf.length) { out.push(para(buf.join(' '))); buf = []; } };
  while (i < lines.length) {
    const l = lines[i];
    if (/^\s*$/.test(l)) { flush(); i++; continue; }
    if (/^---+\s*$/.test(l)) { flush(); i++; continue; }
    const h = l.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      flush();
      const lv = [HeadingLevel.HEADING_1, HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3][h[1].length - 1];
      out.push(new Paragraph({ heading: lv, spacing: { before: 280, after: 120 }, children: inline(h[2].replace(/\*\*/g, ''), { bold: true }) }));
      i++; continue;
    }
    if (/^\|/.test(l)) { flush(); const t: string[] = []; while (i < lines.length && /^\|/.test(lines[i])) t.push(lines[i++]); out.push(table(t)); out.push(new Paragraph({ spacing: { after: 60 } })); continue; }
    if (/^>\s?/.test(l)) { flush(); const q: string[] = []; while (i < lines.length && /^>\s?/.test(lines[i])) q.push(lines[i++].replace(/^>\s?/, '')); out.push(para(q.join(' '), { indent: { left: 400 }, spacing: { after: 160 } }, { italics: true, color: '595959' })); continue; }
    const li = l.match(/^(\s*)([-*]|\d+[.)])\s+(.*)$/);
    if (li) {
      flush();
      const level = Math.min(2, Math.floor(li[1].replace(/\t/g, '  ').length / 2));
      const numbered = /\d/.test(li[2]);
      let text = li[3];
      // 다음 줄이 같은 항목의 이어지는 줄(들여쓰기, 목록 표시 없음)이면 붙인다
      while (i + 1 < lines.length && /^\s+\S/.test(lines[i + 1]) && !/^\s*([-*]|\d+[.)])\s+/.test(lines[i + 1])) text += ' ' + lines[++i].trim();
      out.push(new Paragraph({ children: inline(text), numbering: { reference: numbered ? 'num' : 'bul', level }, spacing: { after: 60 } }));
      i++; continue;
    }
    buf.push(l.trim()); i++;
  }
  flush();
  return out;
}

export async function reportDocx(meta: ReportMeta, bodyMd: string): Promise<Buffer> {
  const dateStr = meta.date.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });
  const children: (Paragraph | Table)[] = [
    new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun({ text: meta.title.replace(/^\[정책제안\]\s*/, ''), font: FONT, size: 36, bold: true })], spacing: { after: 160 } }),
    new Paragraph({ children: [new TextRun({ text: `정책제안 리포트${meta.area ? ` · ${meta.area}` : ''} · ${dateStr} · 다잇다 노트`, font: FONT, size: 20, color: '595959' })], spacing: { after: 60 } }),
    new Paragraph({ children: [new TextRun({ text: '원문: ', font: FONT, size: 20, color: '595959' }), new ExternalHyperlink({ link: meta.url, children: [new TextRun({ text: meta.url, font: FONT, size: 20, style: 'Hyperlink' })] })], spacing: { after: 240 } }),
  ];
  if (meta.description) children.push(new Paragraph({ children: inline(meta.description, { bold: true }), shading: { fill: 'F2F2F2' }, spacing: { after: 240 }, indent: { left: 200, right: 200 } }));
  children.push(...bodyToDocx(bodyMd));
  if (meta.faq.length) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 280, after: 120 }, children: [new TextRun({ text: '자주 묻는 질문', font: FONT, size: SIZE, bold: true })] }));
    for (const f of meta.faq) { children.push(para(`Q. ${f.q}`, {}, { bold: true })); children.push(para(`A. ${f.a}`)); }
  }
  if (meta.sources.length) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 280, after: 120 }, children: [new TextRun({ text: `출처 (${meta.sources.length}건)`, font: FONT, size: SIZE, bold: true })] }));
    meta.sources.forEach((s, n) => children.push(new Paragraph({
      spacing: { after: 40 },
      children: [new TextRun({ text: `${n + 1}. `, font: FONT, size: 20 }), new ExternalHyperlink({ link: s.url, children: [new TextRun({ text: s.title, font: FONT, size: 20, style: 'Hyperlink' })] }), new TextRun({ text: s.date ? ` (${s.date})` : '', font: FONT, size: 20, color: '595959' })],
    })));
  }
  children.push(new Paragraph({ spacing: { before: 360 }, children: [new TextRun({ text: '이 문서는 다잇다 노트(note.daitda.co.kr)의 정책제안 리포트를 내려받은 것입니다. 공개 자료를 근거로 작성했고 평가·순위·추천은 하지 않습니다. 수치는 출처의 원문 확인을 권합니다. 개인 의견은 소속 기관의 입장이 아닙니다.', font: FONT, size: 18, color: '595959' })] }));

  const doc = new Document({
    creator: '다잇다 노트', title: meta.title, description: meta.description ?? meta.summary ?? '',
    styles: { default: { document: { run: { font: FONT, size: SIZE } } } },
    numbering: {
      config: [
        { reference: 'bul', levels: [0, 1, 2].map(l => ({ level: l, format: LevelFormat.BULLET, text: ['•', '–', '·'][l], alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360 + l * 360, hanging: 240 } } } })) },
        { reference: 'num', levels: [0, 1, 2].map(l => ({ level: l, format: LevelFormat.DECIMAL, text: '%' + (l + 1) + '.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360 + l * 360, hanging: 300 } } } })) },
      ],
    },
    sections: [{
      properties: { page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '다잇다 노트 · ', font: FONT, size: 18, color: '595959' }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18, color: '595959' })] })] }) },
      children,
    }],
  });
  return Packer.toBuffer(doc);
}

/** 내려받기용 마크다운(프론트매터 대신 사람이 읽는 머리말) */
export function reportMarkdown(meta: ReportMeta, bodyMd: string): string {
  const dateStr = meta.date.toISOString().slice(0, 10);
  const head = [`# ${meta.title}`, '', `정책제안 리포트${meta.area ? ` · ${meta.area}` : ''} · ${dateStr} · 다잇다 노트 · ${meta.url}`, ''];
  if (meta.description) head.push(`> ${meta.description}`, '');
  const faq = meta.faq.length ? ['', '## 자주 묻는 질문', '', ...meta.faq.flatMap(f => [`**Q. ${f.q}**`, '', f.a, ''])] : [];
  const src = meta.sources.length ? ['', `## 출처 (${meta.sources.length}건)`, '', ...meta.sources.map((s, n) => `${n + 1}. [${s.title}](${s.url})${s.date ? ` (${s.date})` : ''}`)] : [];
  return [...head, bodyMd.trim(), ...faq, ...src, '', '---', '공개 자료를 근거로 작성했고 평가·순위·추천은 하지 않습니다. 수치는 출처의 원문 확인을 권합니다.', ''].join('\n');
}
