/**
 * 브라우저에서 한글(HWPX) 파일 만들기 — 서버·라이브러리 없음.
 * public/hwpx/template.json(scripts/hwpx_template.py 가 양식에서 내보낸 header.xml·용지 문단·표 원형)을 받아
 * 본문(section0.xml)만 여기서 만들고 zip 으로 묶는다. 기업 카드(companies/[id])와 표 도구(table_tools)가 쓴다.
 * 문단·글자 모양 이름은 scripts/hwpx_report.py 의 PARA_SPECS / CHAR_SPECS 와 같다(kicker·title·rule·body·h2·h3·caption·note·th·td·src…).
 */
export type Seg = [text: string, char: string];
export type Cell = string | Block[];
export type Block =
  | { p: string; segs: Seg[] }
  | { table: Cell[][]; head?: boolean; widths?: number[]; fill?: string; margin?: number };

type Template = { ids: { para: Record<string, string>; char: Record<string, string>; border: Record<string, string> }; text_w: number; sec_open: string; sec_close: string; tbl_open: string; tbl_close: string; tc: string; lineseg: string; files: Record<string, string> };

let tpl: Promise<Template> | null = null;
const template = () => (tpl ??= fetch('/hwpx/template.json').then(r => { if (!r.ok) throw new Error('template'); return r.json(); }));

export const esc = (s: string) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const NUMERIC = /^[\d,.%~\-–\s곳명건개년월억원만천+]+$/;
let tblSeq = 0;

export const p = (p: string, ...segs: Seg[]): Block => ({ p, segs });
export const table = (rows: Cell[][], opt: { head?: boolean; widths?: number[]; fill?: string; margin?: number } = {}): Block => ({ table: rows, ...opt });

function paraXml(t: Template, b: { p: string; segs: Seg[] }): string {
  const pid = t.ids.para[b.p] ?? t.ids.para.body;
  const segs = b.segs.length ? b.segs : ([['', 'body']] as Seg[]);
  const runs = segs.map(([text, c]) => `<hp:run charPrIDRef="${t.ids.char[c] ?? t.ids.char.body}"><hp:t>${esc(text)}</hp:t></hp:run>`).join('');
  return `<hp:p id="0" paraPrIDRef="${pid}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">${runs}${t.lineseg}</hp:p>`;
}

function tableXml(t: Template, b: { table: Cell[][]; head?: boolean; widths?: number[]; fill?: string; margin?: number }): string {
  const rows = b.table; const head = b.head !== false; const margin = b.margin ?? 320;
  const ncol = Math.max(...rows.map(r => r.length));
  let widths = b.widths;
  if (!widths) {
    const lens = Array.from({ length: ncol }, (_, c) => Math.max(6, ...rows.map(r => (typeof r[c] === 'string' ? (r[c] as string).length : 12))));
    const tot = lens.reduce((a, x) => a + x, 0);
    widths = lens.map(l => Math.max(Math.floor((t.text_w * l) / tot), Math.floor(t.text_w * 0.12)));
  }
  const scale = t.text_w / widths.reduce((a, x) => a + x, 0); widths = widths.map(w => Math.floor(w * scale));
  let xml = t.tbl_open.replace(/<hp:tbl id="\d+"/, `<hp:tbl id="${2085242905 + ++tblSeq}"`).replace(/rowCnt="\d+"/, `rowCnt="${rows.length}"`).replace(/colCnt="\d+"/, `colCnt="${ncol}"`).replace(/repeatHeader="\d"/, `repeatHeader="${head ? 1 : 0}"`)
    .replace(/(<hp:inMargin left=")\d+(" right=")\d+/, `$1${margin}$2${margin}`);
  rows.forEach((row, ri) => {
    const isHead = head && ri === 0;
    xml += '<hp:tr>';
    for (let ci = 0; ci < ncol; ci++) {
      const cell = row[ci] ?? '';
      const bf = t.ids.border[b.fill ?? (isHead ? 'th' : ri % 2 === 0 ? 'td_alt' : 'td')];
      const paras = typeof cell === 'string'
        ? paraXml(t, { p: isHead ? 'th' : NUMERIC.test(cell || 'x') ? 'tdc' : 'td', segs: [[cell, isHead ? 'th' : 'td']] })
        : cell.map(x => blockXml(t, x)).join('');
      xml += t.tc.replace('@@H@@', isHead ? '1' : '0').replace('@@BF@@', bf).replace('@@VA@@', isHead ? 'CENTER' : 'TOP').replace('@@COL@@', String(ci)).replace('@@ROW@@', String(ri))
        .replace('@@W@@', String(widths[ci])).replace(/@@M@@/g, String(margin)).replace('@@PARAS@@', paras);
    }
    xml += '</hp:tr>';
  });
  return xml + t.tbl_close;
}

const blockXml = (t: Template, b: Block): string => ('table' in b ? tableXml(t, b) : paraXml(t, b));

/* ---------- zip (저장만, 압축 없음 — 한글은 stored 항목도 연다) ---------- */
const CRC = (() => { const tb = new Int32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; tb[n] = c; } return tb; })();
function crc32(d: Uint8Array): number { let c = -1; for (let i = 0; i < d.length; i++) c = CRC[(c ^ d[i]) & 0xff] ^ (c >>> 8); return (c ^ -1) >>> 0; }
function b64(s: string): Uint8Array { const bin = atob(s); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }

function zip(entries: [string, Uint8Array][]): Blob {
  const enc = new TextEncoder(); const parts: Uint8Array[] = []; const central: Uint8Array[] = []; let off = 0;
  const d = new Date(); const dosTime = (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1); const dosDate = ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate();
  for (const [name, data] of entries) {
    const n = enc.encode(name); const crc = crc32(data);
    const lh = new DataView(new ArrayBuffer(30));
    lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); lh.setUint16(8, 0, true); lh.setUint16(10, dosTime, true); lh.setUint16(12, dosDate, true);
    lh.setUint32(14, crc, true); lh.setUint32(18, data.length, true); lh.setUint32(22, data.length, true); lh.setUint16(26, n.length, true); lh.setUint16(28, 0, true);
    const ch = new DataView(new ArrayBuffer(46));
    ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true); ch.setUint16(10, 0, true); ch.setUint16(12, dosTime, true); ch.setUint16(14, dosDate, true);
    ch.setUint32(16, crc, true); ch.setUint32(20, data.length, true); ch.setUint32(24, data.length, true); ch.setUint16(28, n.length, true); ch.setUint16(30, 0, true); ch.setUint16(32, 0, true);
    ch.setUint16(34, 0, true); ch.setUint16(36, 0, true); ch.setUint32(38, 0, true); ch.setUint32(42, off, true);
    parts.push(new Uint8Array(lh.buffer), n, data); central.push(new Uint8Array(ch.buffer), n);
    off += 30 + n.length + data.length;
  }
  const cdSize = central.reduce((a, x) => a + x.length, 0);
  const eo = new DataView(new ArrayBuffer(22));
  eo.setUint32(0, 0x06054b50, true); eo.setUint16(4, 0, true); eo.setUint16(6, 0, true); eo.setUint16(8, entries.length, true); eo.setUint16(10, entries.length, true); eo.setUint32(12, cdSize, true); eo.setUint32(16, off, true); eo.setUint16(20, 0, true);
  return new Blob([...parts, ...central, new Uint8Array(eo.buffer)] as BlobPart[], { type: 'application/hwp+zip' });
}

/** 블록 목록 → HWPX Blob. preview 는 한글 파일 탐색기 미리보기 글(첫 줄들). */
export async function buildHwpx(blocks: Block[], preview = ''): Promise<Blob> {
  const t = await template();
  const enc = new TextEncoder();
  const sec = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' + t.sec_open + blocks.map(b => blockXml(t, b)).join('') + t.sec_close;
  const entries: [string, Uint8Array][] = [];
  for (const name of Object.keys(t.files)) entries.push([name, b64(t.files[name])]);   // mimetype 이 첫 항목
  entries.push(['Contents/section0.xml', enc.encode(sec)]);
  entries.push(['Preview/PrvText.txt', enc.encode(preview)]);
  return zip(entries);
}

export function download(name: string, blob: Blob): void {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

export const safeName = (s: string) => s.replace(/[\\/:*?"<>|\n]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80);

export const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
