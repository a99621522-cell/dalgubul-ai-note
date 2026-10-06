/**
 * 브라우저에서 한글(HWPX) 파일 만들기 — 서버·라이브러리 없음. v3 공무원 양식 복제(운영자 지시 2026-10-06 '내가 올린 공무원 한글 파일 형식으로').
 * public/hwpx/template.json(scripts/hwpx_template.py: 양식의 header.xml 그대로 + 원형 XML 조각)을 받아 DOMParser 로 원형(절 머리표·□·○·-·※·표·표지·그림)을
 * cloneNode 해 글자·속성만 바꾸고 XMLSerializer 로 section0.xml 을 쓴 뒤 zip 으로 묶는다. 스타일을 덧붙이지 않는다(id 충돌 없음).
 * 입력 Block 은 scripts/hwpx_blocks.py(Python 판)와 같다. 문단 이름 → 양식 역할: title/h2 → 절 머리표(Ⅰ Ⅱ …), h3 → □, body → ○, bullet → -, note/caption/src → ※.
 * 사이트 노출은 data/hwpx/compat.json 의 approved(운영자 실물 시험 통과) 뒤에만.
 */
export type Seg = [text: string, char: string];
export type CellObj = { t: string; cs?: number; rs?: number; p?: string; char?: string };
export type Cell = string | CellObj | Block[];
export type Block =
  | { p: string; segs: Seg[] }
  | { table: Cell[][]; head?: boolean; headRows?: number; widths?: number[]; fill?: string; margin?: number }
  | { pic: Uint8Array; ext: 'png' | 'jpg'; w: number; h: number; caption?: string };

type Template = { version: number; text_w: number; ns: Record<string, string>; marks: Record<string, string>; roles: Record<string, string | null>; roman: string[];
  sec_open: string; sec_close: string; proto: Record<string, string>; hpf: string; files: Record<string, string> };

let tpl: Promise<Template> | null = null;
const template = () => (tpl ??= fetch('/hwpx/template.json').then(r => { if (!r.ok) throw new Error('template'); return r.json(); }));
/** 시험 하네스(scripts/hwpx_browser.mjs)가 받은 JSON 을 바로 넣을 때 */
export function setTemplate(t: Template): void { tpl = Promise.resolve(t); }

export const p = (p: string, ...segs: Seg[]): Block => ({ p, segs });
export const table = (rows: Cell[][], opt: { head?: boolean; headRows?: number; widths?: number[]; fill?: string; margin?: number } = {}): Block => ({ table: rows, ...opt });

/* ---------- DOM 복제 ---------- */
class Doc {
  doc: XMLDocument; root: Element; hp: string; tblSeq = 0; secN = 0; coverOn = false; images: { id: string; data: Uint8Array; ext: string }[] = [];
  constructor(public t: Template) {
    this.hp = t.ns.hp;
    this.doc = new DOMParser().parseFromString(t.sec_open + t.sec_close, 'application/xml');
    if (this.doc.getElementsByTagName('parsererror').length) throw new Error('template xml');
    this.root = this.doc.documentElement;
  }
  proto(key: string): Element {
    const decl = Object.entries(this.t.ns).map(([k, v]) => `xmlns:${k}="${v}"`).join(' ');
    const d = new DOMParser().parseFromString(`<hs:sec ${decl}>${this.t.proto[key]}</hs:sec>`, 'application/xml');
    return this.doc.importNode(d.documentElement.firstElementChild!, true) as Element;
  }
  q(el: Element, local: string): Element | null { return el.getElementsByTagNameNS(this.hp, local)[0] ?? null; }
  qa(el: Element, local: string): Element[] { return Array.from(el.getElementsByTagNameNS(this.hp, local)); }
  /** 문단의 글 run 하나만 남기고 글자를 바꾼다(양식 글자 모양 유지) — hwpx_report.set_para_text 와 같은 규칙 */
  setText(para: Element, text: string): void {
    const runs = Array.from(para.children).filter(c => c.localName === 'run');
    let keep = runs.find(r => this.q(r, 't')) ?? runs[0];
    if (!keep) { keep = this.doc.createElementNS(this.hp, 'hp:run'); para.appendChild(keep); }
    for (const r of runs) if (r !== keep && this.q(r, 't') && !this.q(r, 'ctrl') && !this.q(r, 'tbl')) r.remove();
    const ts = this.qa(keep, 't'); ts.slice(1).forEach(x => x.remove());
    let tEl = ts[0]; if (!tEl) { tEl = this.doc.createElementNS(this.hp, 'hp:t'); keep.appendChild(tEl); }
    tEl.textContent = text;
  }
  para(role: string, text: string): Element {
    const el = this.proto(role);
    this.setText(el, text ? (this.t.marks[role] ?? '') + text : '');
    return el;
  }
  section(title: string, pageBreak = false): Element {
    this.secN++;
    const el = this.proto('sec'); const tbl = this.q(el, 'tbl')!; tbl.setAttribute('id', String(2085243000 + ++this.tblSeq));
    const tcs = this.qa(tbl, 'tc');
    this.setText(this.q(tcs[0], 'p')!, this.t.roman[(this.secN - 1) % this.t.roman.length]);
    this.setText(this.q(tcs[2], 'p')!, ' ' + title);
    el.setAttribute('pageBreak', pageBreak || this.secN > 1 ? '1' : '0');   // 양식처럼 절마다 새 쪽, 첫 절은 표지가 있을 때만
    return el;
  }
  cover(title: string, sub: string): Element {
    const el = this.proto('cover'); const tbl = this.q(el, 'tbl')!; tbl.setAttribute('id', String(2085243000 + ++this.tblSeq));
    const mid = this.qa(tbl, 'tr')[1]; const ps = this.qa(this.q(mid, 'tc')!, 'p');
    this.setText(ps[0], title); if (ps[1]) this.setText(ps[1], sub);
    return el;
  }
  table(b: { table: Cell[][]; head?: boolean; headRows?: number; widths?: number[] }): Element {
    const rows = b.table, nhead = b.headRows ?? (b.head !== false ? 1 : 0);
    const parts = (c: Cell): { text: string; cs: number; rs: number; blocks?: Block[] } =>
      typeof c === 'string' ? { text: c, cs: 1, rs: 1 } : Array.isArray(c) ? { text: '', cs: 1, rs: 1, blocks: c } : { text: c.t ?? '', cs: c.cs || 1, rs: c.rs || 1 };
    const occ = new Set<string>(); let ncol = 0;
    const placed = rows.map((row, ri) => { let col = 0; const rp: { ri: number; ci: number; cs: number; rs: number; cell: Cell }[] = [];
      for (const cell of row) { while (occ.has(`${ri},${col}`)) col++; const { cs, rs } = parts(cell);
        for (let dr = 0; dr < rs; dr++) for (let dc = 0; dc < cs; dc++) occ.add(`${ri + dr},${col + dc}`);
        rp.push({ ri, ci: col, cs, rs, cell }); col += cs; }
      ncol = Math.max(ncol, col); return rp; });
    placed.forEach((rp, ri) => { for (let ci = 0; ci < ncol; ci++) if (!occ.has(`${ri},${ci}`)) { rp.push({ ri, ci, cs: 1, rs: 1, cell: '' }); occ.add(`${ri},${ci}`); } rp.sort((a, b2) => a.ci - b2.ci); });
    const el = this.proto('tbl'); const tbl = this.q(el, 'tbl')!; tbl.setAttribute('id', String(2085243000 + ++this.tblSeq));
    const W = Number(this.q(tbl, 'sz')!.getAttribute('width'));
    let widths = b.widths && b.widths.length === ncol ? [...b.widths] : null;
    if (!widths) { const lens = Array.from({ length: ncol }, (_, c) => Math.max(4, ...placed.flat().filter(x => x.ci === c && x.cs === 1).map(x => parts(x.cell).text.length)));
      const tot = lens.reduce((a, x) => a + x, 0); widths = lens.map(l => Math.max(Math.floor((W * l) / tot), Math.floor(W * 0.08))); }
    const scale = W / widths.reduce((a, x) => a + x, 0); widths = widths.map(w => Math.floor(w * scale)); widths[ncol - 1] += W - widths.reduce((a, x) => a + x, 0);
    const trs = this.qa(tbl, 'tr'); const headTcs = this.qa(trs[0], 'tc'), bodyTcs = this.qa(trs[1], 'tc');
    trs.forEach(tr => tr.remove());
    const pick = (protos: Element[], ci: number, cs: number) => { const last = ci + cs >= ncol; return ci === 0 ? protos[0] : last ? protos[protos.length - 1] : protos[1]; };
    placed.forEach((rp, ri) => {
      const tr = this.doc.createElementNS(this.hp, 'hp:tr'); const isHead = ri < nhead;
      for (const { ci, cs, rs, cell } of rp) {
        const c = parts(cell);
        const tc = pick(isHead ? headTcs : bodyTcs, ci, cs).cloneNode(true) as Element;
        tc.setAttribute('header', isHead ? '1' : '0');
        const sl = this.q(tc, 'subList')!; const ps = this.qa(sl, 'p'); ps.slice(1).forEach(x => x.remove());
        if (c.blocks) { ps[0].remove(); for (const x of c.blocks) for (const e of this.blocks(x)) sl.appendChild(e); }
        else this.setText(ps[0], c.text);
        sl.setAttribute('vertAlign', 'CENTER');
        const addr = this.q(tc, 'cellAddr')!; addr.setAttribute('colAddr', String(ci)); addr.setAttribute('rowAddr', String(ri));
        const span = this.q(tc, 'cellSpan')!; span.setAttribute('colSpan', String(cs)); span.setAttribute('rowSpan', String(rs));
        const csz = this.q(tc, 'cellSz')!; csz.setAttribute('width', String(widths!.slice(ci, ci + cs).reduce((a, x) => a + x, 0))); csz.setAttribute('height', String(1800 * rs));
        tr.appendChild(tc);
      }
      tbl.appendChild(tr);
    });
    tbl.setAttribute('rowCnt', String(rows.length)); tbl.setAttribute('colCnt', String(ncol)); tbl.setAttribute('repeatHeader', nhead ? '1' : '0');
    this.q(tbl, 'sz')!.setAttribute('height', String(1800 * rows.length));
    return el;
  }
  pic(b: { pic: Uint8Array; ext: 'png' | 'jpg'; w: number; h: number; caption?: string }): Element[] {
    const id = `image${this.images.length + 2}`; this.images.push({ id, data: b.pic, ext: b.ext });
    const PX = 75, MAXW = 46000, MAXH = 60000;
    const scale = Math.min(1, MAXW / (b.w * PX), MAXH / (b.h * PX)); const w = Math.round(b.w * PX * scale), h = Math.round(b.h * PX * scale);
    const el = this.proto('pic');
    const pic = this.q(el, 'pic')!; pic.setAttribute('id', String(2000000000 + this.images.length)); pic.setAttribute('zOrder', String(10 + this.images.length)); pic.setAttribute('instid', String(1100000000 + this.images.length));
    for (const tag of ['orgSz', 'curSz', 'sz']) { const e = this.q(pic, tag); if (e) { e.setAttribute('width', String(w)); e.setAttribute('height', String(h)); } }
    const rot = this.q(pic, 'rotationInfo'); if (rot) { rot.setAttribute('centerX', String(w >> 1)); rot.setAttribute('centerY', String(h >> 1)); }
    const hc = this.t.ns.hc; const pts = ['pt0', 'pt1', 'pt2', 'pt3'].map(n => pic.getElementsByTagNameNS(hc, n)[0]);
    pts[1]?.setAttribute('x', String(w)); pts[2]?.setAttribute('x', String(w)); pts[2]?.setAttribute('y', String(h)); pts[3]?.setAttribute('y', String(h));
    const clip = this.q(pic, 'imgClip'); if (clip) { clip.setAttribute('right', String(b.w * PX)); clip.setAttribute('bottom', String(b.h * PX)); }
    pic.getElementsByTagNameNS(hc, 'img')[0]?.setAttribute('binaryItemIDRef', id);
    const cm = this.q(pic, 'shapeComment'); if (cm) cm.textContent = b.caption ?? '그림';
    return b.caption ? [el, this.para('note', b.caption)] : [el];
  }
  blocks(b: Block): Element[] {
    if ('table' in b) return [this.table(b)];
    if ('pic' in b) return this.pic(b);
    const text = b.segs.map(s => s[0]).join('');
    const role = this.t.roles[b.p] === undefined ? 'o' : this.t.roles[b.p];
    if (role === null || b.p === 'kicker') return [];
    if (role === 'sec') return [this.section(text, this.secN === 0 && this.coverOn)];
    if (role === 'blank' || !text) return [this.para('blank', '')];
    return [this.para(role, text)];
  }
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

/** 블록 목록 → HWPX Blob. preview 는 한글 파일 탐색기 미리보기 글. cover=true 면 표지(제목·부제) 뒤 새 쪽에서 본문 시작 */
export async function buildHwpx(blocks: Block[], preview = '', opt: { cover?: boolean } = {}): Promise<Blob> {
  const t = await template();
  if (t.version !== 3) throw new Error('template v3 필요');
  const d = new Doc(t);
  if (opt.cover) {
    const txt = (name: string) => { const b = blocks.find(x => 'p' in x && x.p === name) as { segs: Seg[] } | undefined; return b ? b.segs.map(s => s[0]).join('') : ''; };
    d.coverOn = true; d.root.appendChild(d.cover(txt('title'), txt('kicker')));
  }
  for (const b of blocks) for (const e of d.blocks(b)) d.root.appendChild(e);
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
