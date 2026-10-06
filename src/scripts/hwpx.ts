/**
 * 브라우저에서 한글(HWPX) 파일 만들기 — 서버·라이브러리 없음. v2 양식 복제 방식(docs/prompts/site_hwpx_skill.md 3절, 2026-10-06).
 * public/hwpx/template.json(scripts/hwpx_template.py: 양식의 header.xml·용지 문단·원형 XML 조각)을 받아 DOMParser 로 원형(문단·칸·표·그림)을
 * cloneNode 해 글자·속성만 바꾸고 XMLSerializer 로 section0.xml 을 쓴 뒤 zip 으로 묶는다. 문자열로 hp:p·hp:tc 를 새로 쓰지 않는다(스킬 원칙).
 * 입력 Block 은 scripts/hwpx_blocks.py(Python 판)와 같다. 문단·글자 모양 이름은 hwpx_report.py 의 PARA_SPECS / CHAR_SPECS.
 * 사이트 노출은 data/hwpx/compat.json 의 approved(운영자 실물 시험 통과) 뒤에만 — 그 전에는 단추를 그리지 않는다(2026-10-01 운영자 확인 유지).
 */
export type Seg = [text: string, char: string];
export type CellObj = { t: string; cs?: number; rs?: number; p?: string; char?: string };
export type Cell = string | CellObj | Block[];
export type Block =
  | { p: string; segs: Seg[] }
  | { table: Cell[][]; head?: boolean; headRows?: number; widths?: number[]; fill?: string; margin?: number }
  | { pic: Uint8Array; ext: 'png' | 'jpg'; w: number; h: number; caption?: string };

type Template = { version: number; ids: { para: Record<string, string>; char: Record<string, string>; border: Record<string, string> }; text_w: number; ns: Record<string, string>;
  sec_open: string; sec_close: string; proto: { p: string; tbl: string; tc: string; pic: string }; hpf: string; files: Record<string, string> };

let tpl: Promise<Template> | null = null;
const template = () => (tpl ??= fetch('/hwpx/template.json').then(r => { if (!r.ok) throw new Error('template'); return r.json(); }));
/** 시험 하네스(scripts/hwpx_browser.mjs)가 받은 JSON 을 바로 넣을 때 */
export function setTemplate(t: Template): void { tpl = Promise.resolve(t); }

const NUMERIC = /^[\d,.%~\-–\s곳명건개년월억원만천+]+$/;
export const p = (p: string, ...segs: Seg[]): Block => ({ p, segs });
export const table = (rows: Cell[][], opt: { head?: boolean; headRows?: number; widths?: number[]; fill?: string; margin?: number } = {}): Block => ({ table: rows, ...opt });

/* ---------- DOM 복제 ---------- */
class Doc {
  doc: XMLDocument; root: Element; hp: string; tblSeq = 0; images: { id: string; data: Uint8Array; ext: string }[] = [];
  constructor(public t: Template) {
    this.hp = t.ns.hp;
    this.doc = new DOMParser().parseFromString(t.sec_open + t.sec_close, 'application/xml');
    if (this.doc.getElementsByTagName('parsererror').length) throw new Error('template xml');
    this.root = this.doc.documentElement;
  }
  /** 원형 조각을 양식 네임스페이스 안에서 파싱해 이 문서로 들여온다 */
  proto(xml: string): Element {
    const decl = Object.entries(this.t.ns).map(([k, v]) => `xmlns:${k}="${v}"`).join(' ');
    const d = new DOMParser().parseFromString(`<hs:sec ${decl}>${xml}</hs:sec>`, 'application/xml');
    const el = d.documentElement.firstElementChild!;
    return this.doc.importNode(el, true) as Element;
  }
  q(el: Element, local: string): Element | null { return el.getElementsByTagNameNS(this.hp, local)[0] ?? null; }
  qa(el: Element, local: string): Element[] { return Array.from(el.getElementsByTagNameNS(this.hp, local)); }
  para(b: { p: string; segs: Seg[] }): Element {
    const ids = this.t.ids;
    const el = this.proto(this.t.proto.p);
    el.setAttribute('paraPrIDRef', ids.para[b.p] ?? ids.para.body);
    const runProto = this.q(el, 'run')!; runProto.remove();
    for (const [text, c] of (b.segs.length ? b.segs : ([['', 'body']] as Seg[]))) {
      const r = runProto.cloneNode(true) as Element;
      r.setAttribute('charPrIDRef', ids.char[c] ?? ids.char.body);
      this.q(r, 't')!.textContent = text;
      el.appendChild(r);
    }
    return el;
  }
  table(b: { table: Cell[][]; head?: boolean; headRows?: number; widths?: number[]; fill?: string; margin?: number }): Element {
    const t = this.t, ids = t.ids, rows = b.table, margin = b.margin ?? 320;
    const nhead = b.headRows ?? (b.head !== false ? 1 : 0), head = nhead > 0;
    const parts = (c: Cell): { text: string; cs: number; rs: number; p?: string; char?: string; blocks?: Block[] } =>
      typeof c === 'string' ? { text: c, cs: 1, rs: 1 } : Array.isArray(c) ? { text: '', cs: 1, rs: 1, blocks: c } : { text: c.t ?? '', cs: c.cs || 1, rs: c.rs || 1, p: c.p, char: c.char };
    // 격자 배치(HTML 규칙: 덮이지 않은 칸만 나열)
    const occ = new Set<string>(); let ncol = 0;
    const placed: { ri: number; ci: number; cs: number; rs: number; cell: Cell }[][] = rows.map((row, ri) => {
      let col = 0; const rp: { ri: number; ci: number; cs: number; rs: number; cell: Cell }[] = [];
      for (const cell of row) { while (occ.has(`${ri},${col}`)) col++; const { cs, rs } = parts(cell);
        for (let dr = 0; dr < rs; dr++) for (let dc = 0; dc < cs; dc++) occ.add(`${ri + dr},${col + dc}`);
        rp.push({ ri, ci: col, cs, rs, cell }); col += cs; }
      ncol = Math.max(ncol, col); return rp; });
    placed.forEach((rp, ri) => { for (let ci = 0; ci < ncol; ci++) if (!occ.has(`${ri},${ci}`)) { rp.push({ ri, ci, cs: 1, rs: 1, cell: '' }); occ.add(`${ri},${ci}`); } rp.sort((a, b2) => a.ci - b2.ci); });
    let widths = b.widths && b.widths.length === ncol ? [...b.widths] : null;
    if (!widths) {
      const lens = Array.from({ length: ncol }, (_, c) => Math.max(6, ...placed.flat().filter(x => x.ci === c && x.cs === 1).map(x => parts(x.cell).text.length)));
      const tot = lens.reduce((a, x) => a + x, 0); widths = lens.map(l => Math.max(Math.floor((t.text_w * l) / tot), Math.floor(t.text_w * 0.08)));
    }
    const scale = t.text_w / widths.reduce((a, x) => a + x, 0); widths = widths.map(w => Math.floor(w * scale)); widths[ncol - 1] += t.text_w - widths.reduce((a, x) => a + x, 0);
    const el = this.proto(t.proto.tbl);
    el.setAttribute('paraPrIDRef', ids.para.body);
    const tbl = this.q(el, 'tbl')!;
    tbl.setAttribute('id', String(2085242905 + ++this.tblSeq));
    this.qa(tbl, 'tr').forEach(tr => tr.remove());
    tbl.setAttribute('borderFillIDRef', ids.border.none); tbl.setAttribute('repeatHeader', head ? '1' : '0');
    tbl.setAttribute('rowCnt', String(rows.length)); tbl.setAttribute('colCnt', String(ncol));
    const sz = this.q(tbl, 'sz')!; sz.setAttribute('width', String(t.text_w)); sz.setAttribute('height', String(Math.max(1, rows.length) * 1460));
    const im = this.q(tbl, 'inMargin'); if (im) { im.setAttribute('left', String(margin)); im.setAttribute('right', String(margin)); im.setAttribute('top', '230'); im.setAttribute('bottom', '230'); }
    const tcProto = this.proto(t.proto.tc);
    placed.forEach((rp, ri) => {
      const tr = this.doc.createElementNS(this.hp, 'hp:tr'); const isHead = ri < nhead;
      for (const { ci, cs, rs, cell } of rp) {
        const c = parts(cell);
        const tc = tcProto.cloneNode(true) as Element;
        tc.setAttribute('header', isHead ? '1' : '0');
        tc.setAttribute('borderFillIDRef', ids.border[b.fill ?? (isHead ? 'th' : ri % 2 === 0 ? 'td_alt' : 'td')]);
        const sl = this.q(tc, 'subList')!; this.qa(sl, 'p').forEach(x => x.remove()); sl.setAttribute('vertAlign', isHead || rs > 1 ? 'CENTER' : 'TOP');
        if (c.blocks) for (const x of c.blocks) sl.appendChild(this.block(x));
        else sl.appendChild(this.para({ p: c.p ?? (isHead ? 'th' : NUMERIC.test(c.text || 'x') ? 'tdc' : 'td'), segs: [[c.text, c.char ?? (isHead ? 'th' : 'td')]] }));
        const addr = this.q(tc, 'cellAddr')!; addr.setAttribute('colAddr', String(ci)); addr.setAttribute('rowAddr', String(ri));
        const span = this.q(tc, 'cellSpan')!; span.setAttribute('colSpan', String(cs)); span.setAttribute('rowSpan', String(rs));
        const csz = this.q(tc, 'cellSz')!; csz.setAttribute('width', String(widths!.slice(ci, ci + cs).reduce((a, x) => a + x, 0))); csz.setAttribute('height', String(1460 * rs));
        const cm = this.q(tc, 'cellMargin'); if (cm) { cm.setAttribute('left', String(margin)); cm.setAttribute('right', String(margin)); cm.setAttribute('top', '230'); cm.setAttribute('bottom', '230'); }
        tr.appendChild(tc);
      }
      tbl.appendChild(tr);
    });
    return el;
  }
  pic(b: { pic: Uint8Array; ext: 'png' | 'jpg'; w: number; h: number; caption?: string }): Element {
    const id = `image${this.images.length + 2}`; this.images.push({ id, data: b.pic, ext: b.ext });
    const PX = 75, MAXW = 46000, MAXH = 60000;
    const scale = Math.min(1, MAXW / (b.w * PX), MAXH / (b.h * PX)); const w = Math.round(b.w * PX * scale), h = Math.round(b.h * PX * scale);
    const el = this.proto(this.t.proto.pic);
    const pic = this.q(el, 'pic')!; pic.setAttribute('id', String(2000000000 + this.images.length)); pic.setAttribute('zOrder', String(10 + this.images.length)); pic.setAttribute('instid', String(1100000000 + this.images.length));
    for (const tag of ['orgSz', 'curSz', 'sz']) { const e = this.q(pic, tag); if (e) { e.setAttribute('width', String(w)); e.setAttribute('height', String(h)); } }
    const rot = this.q(pic, 'rotationInfo'); if (rot) { rot.setAttribute('centerX', String(w >> 1)); rot.setAttribute('centerY', String(h >> 1)); }
    const hc = this.t.ns.hc; const pts = ['pt0', 'pt1', 'pt2', 'pt3'].map(n => pic.getElementsByTagNameNS(hc, n)[0]);
    pts[1]?.setAttribute('x', String(w)); pts[2]?.setAttribute('x', String(w)); pts[2]?.setAttribute('y', String(h)); pts[3]?.setAttribute('y', String(h));
    const clip = this.q(pic, 'imgClip'); if (clip) { clip.setAttribute('right', String(b.w * PX)); clip.setAttribute('bottom', String(b.h * PX)); }
    pic.getElementsByTagNameNS(hc, 'img')[0]?.setAttribute('binaryItemIDRef', id);
    const cm = this.q(pic, 'shapeComment'); if (cm) cm.textContent = b.caption ?? '그림';
    return el;
  }
  block(b: Block): Element { return 'table' in b ? this.table(b) : 'pic' in b ? this.pic(b) : this.para(b); }
  serialize(): string { return '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' + new XMLSerializer().serializeToString(this.root); }
}

/* ---------- zip (저장만, 압축 없음 — 한글은 stored 항목도 연다) ---------- */
const CRC = (() => { const tb = new Int32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; tb[n] = c; } return tb; })();
function crc32(d: Uint8Array): number { let c = -1; for (let i = 0; i < d.length; i++) c = CRC[(c ^ d[i]) & 0xff] ^ (c >>> 8); return (c ^ -1) >>> 0; }
function b64(s: string): Uint8Array { const bin = atob(s); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }

export function zip(entries: [string, Uint8Array][]): Blob {
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
  if (t.version !== 2) throw new Error('template v2 필요');
  const d = new Doc(t);
  for (const b of blocks) d.root.appendChild(d.block(b));
  const enc = new TextEncoder();
  const entries: [string, Uint8Array][] = [];
  const manifest = d.images.map(i => `<opf:item id="${i.id}" href="BinData/${i.id}.${i.ext}" media-type="image/${i.ext === 'jpg' ? 'jpeg' : i.ext}" isEmbeded="1"/>`).join('');
  for (const name of Object.keys(t.files)) {   // mimetype 이 첫 항목
    if (name === 'Contents/content.hpf' && manifest) entries.push([name, enc.encode(t.hpf.replace('</opf:manifest>', manifest + '</opf:manifest>'))]);
    else entries.push([name, b64(t.files[name])]);
  }
  entries.push(['Contents/section0.xml', enc.encode(d.serialize())]);
  entries.push(['Preview/PrvText.txt', enc.encode(preview)]);
  for (const i of d.images) entries.push([`BinData/${i.id}.${i.ext}`, i.data]);
  return zip(entries);
}

export function download(name: string, blob: Blob): void {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

export const safeName = (s: string) => s.replace(/[\\/:*?"<>|\n]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80);

export const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };

/** 사이트 노출 관문: data/hwpx/compat.json 의 approved 를 Base 가 <html data-hwpx="1"> 로 내보낸다 */
export const hwpxEnabled = () => typeof document !== 'undefined' && document.documentElement.dataset.hwpx === '1';
