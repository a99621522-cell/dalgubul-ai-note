/** 파일을 표(string[][])로 — 붙여넣기 대신 '파일 놓기'(운영자 2026-11-03 '홈택스 붙여넣는 것은 공무원이 안 할 것 같은데 방법을 찾아봐').
 *  라이브러리 없이 브라우저 안에서만 읽는다(서버·AI 없음, 파일은 밖으로 나가지 않는다):
 *  - .xlsx(Office Open XML): zip 을 DecompressionStream 으로 풀어 xl/sharedStrings.xml·xl/worksheets/sheet1.xml 의 <c r= t= s=><v>… 를 읽는다(날짜 서식 칸은 일련번호 그대로 → parseDateCell 이 읽음)
 *  - .xls(BIFF8, 홈택스·대구 재정 포털·e호조 내려받기): OLE2 복합 문서에서 Workbook 스트림을 찾아 SST·LABELSST·LABEL·NUMBER·RK·MULRK·FORMULA(캐시 값)·BOOLERR·BLANK 레코드만 읽는다(첫 시트)
 *  - 확장자가 .xls 인데 실제는 HTML 표(일부 누리집)·CSV(EUC-KR/UTF-8)인 파일도 첫 바이트로 가려 읽는다
 *  값은 글자 그대로(숫자는 소수점 없이) — 열 짐작·머리글 찾기는 vat_rules 의 guessColumns/findHeader 가 그대로 한다 */
import { unzip, parseTable } from './vat_rules';

export type FileTable = { name: string; kind: 'xlsx' | 'xls' | 'csv' | 'html' | 'text' | 'hwpx'; sheet?: string; rows: string[][] };

/* ── 한글(HWPX) ── 운영자 2026-11-24 '홈택스 파일 올리기에 엑셀·hwpx 도'
 *  zip 의 Contents/section*.xml 을 읽어 ① 글자(문단은 한 줄, 표는 행마다 칸을 띄어 한 줄 — 신고서 칸 '(9) … 금액' 이 한 줄에 오게) ② 표(행·칸 글자, 가장 큰 표가 매입 목록 후보) */
export async function readHwpx(file: File): Promise<{ text: string; tables: string[][][] }> {
  const buf = await file.arrayBuffer(); const b0 = new Uint8Array(buf);
  if (isOle(b0)) return readHwp5(b0);   /* 확장자가 .hwpx 여도 실제는 옛 한글(HWP 5.0)인 파일 — 운영자 2026-11-24 올린 파일 두 개가 그랬다 */
  const files = await unzip(buf); const dec = new TextDecoder('utf-8');
  const secs = files.filter(f => /^Contents\/section\d+\.xml$/i.test(f.name)).sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
  if (!secs.length) throw new Error('한글(HWPX) 본문을 찾지 못했습니다');
  const tx = (x: string) => xmlUnesc([...x.matchAll(/<hp:t\b[^>]*>([\s\S]*?)<\/hp:t>/g)].map(m => m[1].replace(/<[^>]+>/g, '')).join('')).replace(/\s+/g, ' ').trim();
  const lines: string[] = []; const tables: string[][][] = [];
  /* 표 안의 표까지 짝을 맞춰 자른다 */
  const cut = (xml: string, open: string, close: string): [number, number][] => { const out: [number, number][] = []; let i = 0; while ((i = xml.indexOf(open, i)) >= 0) { let d = 0, j = i; for (;;) { const o = xml.indexOf(open, j + 1), c = xml.indexOf(close, j + 1); if (c < 0) { j = xml.length; break; } if (o >= 0 && o < c) { d++; j = o; } else { if (d === 0) { j = c + close.length; break; } d--; j = c; } } out.push([i, j]); i = j; } return out; };
  const table = (t: string) => cut(t, '<hp:tr', '</hp:tr>').map(([a, b]) => cut(t.slice(a, b), '<hp:tc', '</hp:tc>').map(([c, d]) => tx(t.slice(a, b).slice(c, d))));
  for (const s of secs) { const xml = dec.decode(s.data); let at = 0;
    for (const [a, b] of cut(xml, '<hp:tbl', '</hp:tbl>')) { for (const p of xml.slice(at, a).split(/<\/hp:p>/)) { const t = tx(p); if (t) lines.push(t); } const rows = table(xml.slice(a, b)).filter(r => r.some(Boolean)); if (rows.length) { tables.push(rows); for (const r of rows) lines.push(r.filter(Boolean).join(' ')); } at = b; }
    for (const p of xml.slice(at).split(/<\/hp:p>/)) { const t = tx(p); if (t) lines.push(t); } }
  return { text: lines.join('\n'), tables };
}
const isOle = (b: Uint8Array) => b[0] === 0xd0 && b[1] === 0xcf && b[2] === 0x11 && b[3] === 0xe0;
/** 문서보안(DRM)으로 잠긴 파일인가 — 기관 PC 의 문서 암호화 프로그램이 원본을 감싸 확장자 뒤에 글자를 붙인다(예: .xlsx.pLDH, 첫 줄 'VER3.2P', 끝 'CRYPTO FILE END') */
export const isDrm = (b: Uint8Array) => { const head = latin(b.subarray(0, 16)), tail = latin(b.subarray(Math.max(0, b.length - 64))); return /^VER\d/.test(head) || /CRYPTO\s*FILE\s*END/.test(tail); };
/* ── 옛 한글(HWP 5.0) ── OLE2 복합 문서: FileHeader(압축·암호·배포용 표시) + BodyText/SectionN(raw deflate 레코드).
 *  레코드 머리 32비트 = 태그(10) · 단계(10) · 크기(12, 0xFFF 면 다음 4바이트). PARA_TEXT(67) = UTF-16LE 글자(제어 글자 0~31 은 1칸 또는 8칸),
 *  CTRL_HEADER(71) 'tbl ' → TABLE(77) → 칸마다 LIST_HEADER(72)(+8 열 주소·+10 행 주소). 칸은 행마다 띄어 한 줄로(readHwpx 와 같은 꼴) */
async function readHwp5(b: Uint8Array): Promise<{ text: string; tables: string[][][] }> {
  const fh = oleStream(b, ['FileHeader']); if (!fh || latin(fh.subarray(0, 17)) !== 'HWP Document File') throw new Error('한글(HWP) 문서가 아닙니다');
  const flags = new DataView(fh.buffer, fh.byteOffset, fh.byteLength).getUint32(36, true);
  if (flags & 2) throw new Error('암호가 걸린 한글 파일입니다 — 한글에서 암호를 풀고 저장해 다시 올리세요');
  if (flags & 4) throw new Error('배포용 한글 문서라 글자를 읽을 수 없습니다 — 한글에서 「다른 이름으로 저장 → HWPX」로 바꿔 올리세요');
  const lines: string[] = []; const tables: string[][][] = [];
  for (let n = 0; n < 64; n++) { const raw = oleStream(b, [`Section${n}`]); if (!raw) break;
    const d = flags & 1 ? await inflateRaw(raw) : raw; const dv = new DataView(d.buffer, d.byteOffset, d.byteLength);
    type T = { lvl: number; grid: Map<number, Map<number, string[]>>; cur: string[] | null };
    const stack: T[] = []; let pendTbl = -1;
    const endTo = (lvl: number) => { while (stack.length && lvl <= stack[stack.length - 1].lvl) { const t = stack.pop()!; const rows = [...t.grid.keys()].sort((x, y) => x - y).map(r => { const cs = t.grid.get(r)!; const mx = Math.max(...cs.keys()); return Array.from({ length: mx + 1 }, (_, c) => (cs.get(c) ?? []).join(' ').replace(/\s+/g, ' ').trim()); }).filter(r => r.some(Boolean)); if (rows.length) { tables.push(rows); const line = rows.map(r => r.filter(Boolean).join(' ')); if (stack.length && stack[stack.length - 1].cur) stack[stack.length - 1].cur!.push(...line); else lines.push(...line); } } };
    let i = 0; while (i + 4 <= d.length) { const h = dv.getUint32(i, true); const tag = h & 0x3ff, lvl = (h >>> 10) & 0x3ff; let sz = h >>> 20; i += 4; if (sz === 0xfff) { sz = dv.getUint32(i, true); i += 4; } const at = i; i += sz; if (i > d.length) break;
      if (stack.length && lvl <= stack[stack.length - 1].lvl) endTo(lvl);
      if (tag === 71 && sz >= 4 && latin(d.subarray(at, at + 4)) === ' lbt') pendTbl = lvl;   /* 'tbl ' 이 거꾸로 저장됨 */
      else if (tag === 77 && pendTbl >= 0) { stack.push({ lvl: pendTbl, grid: new Map(), cur: null }); pendTbl = -1; }
      else if (tag === 72 && stack.length && sz >= 12) { const t = stack[stack.length - 1]; const col = dv.getUint16(at + 8, true), row = dv.getUint16(at + 10, true); const rm = t.grid.get(row) ?? new Map<number, string[]>(); t.grid.set(row, rm); const c: string[] = rm.get(col) ?? []; rm.set(col, c); t.cur = c; }
      else if (tag === 67) { let s = ''; for (let j = at; j + 1 < at + sz;) { const c = dv.getUint16(j, true); if (c < 32) { if ([0, 10, 13, 24, 25, 26, 27, 28, 29, 30, 31].includes(c)) { if (c === 10 || c === 13) s += ' '; j += 2; } else { if (c === 9) s += ' '; j += 16; } continue; } s += String.fromCharCode(c); j += 2; }
        s = s.replace(/\s+/g, ' ').trim(); if (!s) continue; const t = stack[stack.length - 1]; if (t?.cur) t.cur.push(s); else lines.push(s); } }
    endTo(-1); }
  if (!lines.length && !tables.length) throw new Error('한글(HWP) 본문 글자를 찾지 못했습니다');
  return { text: lines.join('\n'), tables };
}
/* 한글 본문 스트림은 deflate 끝 뒤에 채움 바이트가 붙는 일이 있어 브라우저 DecompressionStream 이 끝에서 오류를 낸다 — 그때까지 푼 것을 쓴다 */
async function inflateRaw(b: Uint8Array): Promise<Uint8Array> { const ds = new DecompressionStream('deflate-raw'); const w = ds.writable.getWriter(); void w.write(b).catch(() => { /* */ }); void w.close().catch(() => { /* */ }); const rd = ds.readable.getReader(); const parts: Uint8Array[] = []; let n = 0;
  try { for (;;) { const { done, value } = await rd.read(); if (done) break; parts.push(value); n += value.length; } } catch (e) { if (!n) throw e; }
  const out = new Uint8Array(n); let o = 0; for (const p of parts) { out.set(p, o); o += p.length; } return out; }
/** 표 → 줄 글자(엑셀·한글로 저장한 신고서를 신고서 판독기에 넣을 때 — 행마다 칸을 띄어 한 줄) */
export const tableText = (rows: string[][]) => rows.map(r => r.filter(c => c !== '').join(' ')).filter(Boolean).join('\n');
/** 신고서로 보이는 글자인가(부가가치세 신고서 제목·과세표준 칸) — 엑셀·한글 파일이 신고서인지 매입 목록인지 가를 때 */
export const looksFiled = (text: string) => /부\s*가\s*가\s*치\s*세/.test(text) && /신\s*고\s*서/.test(text) && /\(\s*9\s*\)|과\s*세\s*표\s*준/.test(text);

export async function readTableFile(file: File): Promise<FileTable> {
  const buf = await file.arrayBuffer(); const b = new Uint8Array(buf); const name = file.name;
  if (isDrm(b)) throw new Error('문서보안(DRM)으로 잠긴 파일입니다 — 기관 PC 의 문서보안 프로그램에서 「암호 해제(반출)」한 뒤 올리세요');
  if (/\.hwpx?$/i.test(name) || (isOle(b) && oleStream(b, ['FileHeader']))) { const h = await readHwpx(file); const big = [...h.tables].sort((x, y) => y.length - x.length)[0]; if (!big?.length) throw new Error('한글 파일에 표가 없습니다'); return { name, kind: 'hwpx', rows: big }; }   /* 한글로 정리한 매입 목록 — 가장 큰 표 */
  if (b[0] === 0x50 && b[1] === 0x4b) { const t = await readXlsx(buf); return { name, kind: 'xlsx', ...t }; }
  if (b[0] === 0xd0 && b[1] === 0xcf && b[2] === 0x11 && b[3] === 0xe0) { const t = readXls(b); return { name, kind: 'xls', ...t }; }
  const text = decodeText(b);
  if (/<table[\s>]/i.test(text.slice(0, 200000))) return { name, kind: 'html', rows: htmlTable(text) };
  return { name, kind: /\.csv$/i.test(name) ? 'csv' : 'text', rows: parseTable(text) };
}

/** UTF-8(BOM 포함) 먼저, 깨진 글자(U+FFFD)가 많으면 EUC-KR 로 */
function decodeText(b: Uint8Array): string {
  if (b[0] === 0xef && b[1] === 0xbb && b[2] === 0xbf) return new TextDecoder('utf-8').decode(b.subarray(3));
  if (b[0] === 0xff && b[1] === 0xfe) return new TextDecoder('utf-16le').decode(b.subarray(2));
  const u = new TextDecoder('utf-8').decode(b); const bad = (u.match(/�/g) ?? []).length;
  if (bad === 0) return u;
  try { const k = new TextDecoder('euc-kr').decode(b); if ((k.match(/�/g) ?? []).length < bad) return k; } catch { /* euc-kr 미지원 브라우저 */ }
  return u;
}

function htmlTable(html: string): string[][] {
  const doc = new DOMParser().parseFromString(html, 'text/html'); const tbl = [...doc.querySelectorAll('table')].sort((a, b) => b.rows.length - a.rows.length)[0]; if (!tbl) return [];
  return [...tbl.rows].map(tr => [...tr.cells].map(td => (td.textContent ?? '').replace(/\s+/g, ' ').trim()));
}

/* ── xlsx ── */
const xmlUnesc = (s: string) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n))).replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16))).replace(/&amp;/g, '&');
const colIndex = (ref: string) => { let n = 0; for (const ch of ref.replace(/\d+$/, '')) n = n * 26 + (ch.charCodeAt(0) - 64); return n - 1; };
async function readXlsx(buf: ArrayBuffer): Promise<{ sheet?: string; rows: string[][] }> {
  const files = await unzip(buf); const dec = new TextDecoder('utf-8'); const get = (n: string) => { const f = files.find(x => x.name === n); return f ? dec.decode(f.data) : ''; };
  const sst: string[] = []; const ss = get('xl/sharedStrings.xml');
  if (ss) for (const m of ss.matchAll(/<si>([\s\S]*?)<\/si>/g)) sst.push([...m[1].matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map(t => xmlUnesc(t[1])).join(''));
  /* 첫 시트: workbook.xml 의 첫 <sheet> → rels 로 경로, 없으면 sheet1.xml */
  let sheetPath = 'xl/worksheets/sheet1.xml', sheetName: string | undefined;
  const wb = get('xl/workbook.xml'); const first = wb.match(/<sheet\b[^>]*name="([^"]*)"[^>]*r:id="([^"]+)"/) ?? wb.match(/<sheet\b[^>]*r:id="([^"]+)"[^>]*name="([^"]*)"/);
  if (first) { sheetName = xmlUnesc(first[1].startsWith('rId') ? first[2] : first[1]); const rid = first[1].startsWith('rId') ? first[1] : first[2]; const rels = get('xl/_rels/workbook.xml.rels'); const rm = rels.match(new RegExp(`<Relationship\\b[^>]*Id="${rid}"[^>]*Target="([^"]+)"`)) ?? rels.match(new RegExp(`<Relationship\\b[^>]*Target="([^"]+)"[^>]*Id="${rid}"`)); if (rm) sheetPath = (rm[1].startsWith('/') ? rm[1].slice(1) : 'xl/' + rm[1].replace(/^\.\//, '')); }
  const xml = get(sheetPath) || get(files.find(f => /^xl\/worksheets\/sheet\d+\.xml$/.test(f.name))?.name ?? '');
  const rows: string[][] = [];
  for (const rm of xml.matchAll(/<row\b[^>]*>([\s\S]*?)<\/row>/g)) {
    const row: string[] = [];
    for (const cm of rm[1].matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
      const attrs = cm[1]; const ref = attrs.match(/\br="([A-Z]+)\d+"/)?.[1] ?? ''; const t = attrs.match(/\bt="([^"]+)"/)?.[1] ?? ''; const inner = cm[2] ?? '';
      let v = '';
      if (t === 's') { const i = Number(inner.match(/<v>([^<]*)<\/v>/)?.[1] ?? -1); v = sst[i] ?? ''; }
      else if (t === 'inlineStr') v = [...inner.matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map(x => xmlUnesc(x[1])).join('');
      else { const raw = inner.match(/<v>([^<]*)<\/v>/)?.[1]; v = raw === undefined ? '' : (t === 'b' ? (raw === '1' ? 'TRUE' : 'FALSE') : numStr(raw)); }
      const ci = ref ? colIndex(ref) : row.length; while (row.length < ci) row.push(''); row[ci] = v;
    }
    if (row.some(c => c !== '')) rows.push(row.map(c => c.trim()));
  }
  return { sheet: sheetName, rows };
}
const numStr = (raw: string) => { const n = Number(raw); if (!Number.isFinite(n)) return xmlUnesc(raw); return Number.isInteger(n) ? String(n) : String(Math.round(n * 1e6) / 1e6); };

/* ── xls(BIFF8) ── */
function readXls(b: Uint8Array): { sheet?: string; rows: string[][] } {
  const wbStream = oleStream(b, ['Workbook', 'Book']); if (!wbStream) throw new Error('xls Workbook 스트림 없음');
  const dv = new DataView(wbStream.buffer, wbStream.byteOffset, wbStream.byteLength); const n = wbStream.byteLength;
  const sst: string[] = []; const sheets: { name: string; off: number }[] = []; let pos = 0; let globalsEnd = -1;
  /* 1) 전역 블록: SST(0x00FC)+CONTINUE(0x003C), BOUNDSHEET(0x0085) */
  const u16 = (o: number) => dv.getUint16(o, true), u32 = (o: number) => dv.getUint32(o, true);
  const readStr = (o: number, len: number, hasLenField: 'u8' | 'u16'): { s: string; next: number } => {   // XLUnicodeString
    const cch = hasLenField === 'u16' ? u16(o) : wbStream[o]; o += hasLenField === 'u16' ? 2 : 1; const flags = wbStream[o++]; const rich = flags & 8 ? u16(o) : 0; if (flags & 8) o += 2; const ext = flags & 4 ? u32(o) : 0; if (flags & 4) o += 4;
    let s = ''; if (flags & 1) { s = new TextDecoder('utf-16le').decode(wbStream.subarray(o, o + cch * 2)); o += cch * 2; } else { s = latin(wbStream.subarray(o, o + cch)); o += cch; }
    o += rich * 4 + ext; return { s, next: o }; void len;
  };
  let depth = 0;
  while (pos + 4 <= n) {
    const id = u16(pos), len = u16(pos + 2); const body = pos + 4;
    if (id === 0x0809) { depth++; if (depth === 2) { globalsEnd = pos; break; } }
    if (id === 0x0085) { const off = u32(body); const cch = wbStream[body + 6]; const flags = wbStream[body + 7]; const name = flags & 1 ? new TextDecoder('utf-16le').decode(wbStream.subarray(body + 8, body + 8 + cch * 2)) : latin(wbStream.subarray(body + 8, body + 8 + cch)); sheets.push({ name, off }); }
    if (id === 0x00fc) {   // SST — CONTINUE 블록을 이어 붙인 뒤 읽는다(이어지는 곳에서 글자 폭 플래그가 다시 온다)
      const parts: { start: number; end: number }[] = [{ start: body, end: body + len }]; let p2 = body + len;
      while (p2 + 4 <= n && u16(p2) === 0x003c) { const l2 = u16(p2 + 2); parts.push({ start: p2 + 4, end: p2 + 4 + l2 }); p2 += 4 + l2; }
      const total = u32(body + 4); let pi = 0; let o = body + 8; let count = 0;
      const bytesLeft = () => parts[pi].end - o; const nextPart = () => { pi++; o = parts[pi].start; };
      while (count < total && pi < parts.length) {
        if (bytesLeft() <= 0) { if (pi + 1 >= parts.length) break; nextPart(); continue; }
        const cch = u16(o); o += 2; let flags = wbStream[o++]; const rich = flags & 8 ? u16(o) : 0; if (flags & 8) o += 2; const ext = flags & 4 ? u32(o) : 0; if (flags & 4) o += 4;
        let s = '', left = cch;
        while (left > 0) {
          const wide = flags & 1; const avail = bytesLeft(); const take = Math.min(left, Math.floor(avail / (wide ? 2 : 1)));
          s += wide ? new TextDecoder('utf-16le').decode(wbStream.subarray(o, o + take * 2)) : latin(wbStream.subarray(o, o + take)); o += take * (wide ? 2 : 1); left -= take;
          if (left > 0) { if (pi + 1 >= parts.length) break; nextPart(); flags = wbStream[o++]; }
        }
        let skip = rich * 4 + ext; while (skip > 0) { const avail = bytesLeft(); if (avail >= skip) { o += skip; skip = 0; } else { skip -= avail; if (pi + 1 >= parts.length) break; nextPart(); } }
        sst.push(s); count++;
      }
      pos = p2; continue;
    }
    pos = body + len;
  }
  if (!sheets.length) throw new Error('xls 시트 없음');
  /* 2) 첫 시트 블록의 셀 레코드 */
  const start = sheets[0].off; const cells = new Map<number, Map<number, string>>(); const put = (r: number, c: number, v: string) => { let row = cells.get(r); if (!row) cells.set(r, (row = new Map())); row.set(c, v); };
  const rk = (v: number) => { const frac = v & 2; let x: number; if (v & 1) { x = v >> 2; } else { const b8 = new ArrayBuffer(8); const d8 = new DataView(b8); d8.setUint32(4, (v & 0xfffffffc) >>> 0, true); d8.setUint32(0, 0, true); x = d8.getFloat64(0, true); } return frac ? x / 100 : x; };
  pos = start; let seenBof = false;
  while (pos + 4 <= n) {
    const id = u16(pos), len = u16(pos + 2); const body = pos + 4;
    if (id === 0x0809) { if (seenBof) break; seenBof = true; }
    else if (id === 0x000a) { if (seenBof) break; }
    else if (id === 0x00fd) put(u16(body), u16(body + 2), sst[u32(body + 6)] ?? '');
    else if (id === 0x0204) { const r = u16(body), c = u16(body + 2); put(r, c, readStr(body + 6, 0, 'u16').s); }
    else if (id === 0x0203) put(u16(body), u16(body + 2), fmtNum(dv.getFloat64(body + 6, true)));
    else if (id === 0x027e) put(u16(body), u16(body + 2), fmtNum(rk(u32(body + 6))));
    else if (id === 0x00bd) { const r = u16(body), c0 = u16(body + 2); const cnt = (len - 6) / 6; for (let i = 0; i < cnt; i++) put(r, c0 + i, fmtNum(rk(u32(body + 4 + i * 6 + 4)))); }
    else if (id === 0x0006) { const r = u16(body), c = u16(body + 2); const b6 = body + 6; if (u16(b6 + 6) === 0xffff) { const kind = wbStream[b6]; if (kind === 0) { /* 문자열 — 다음 STRING 레코드 */ const p2 = body + len; if (u16(p2) === 0x0207) put(r, c, readStr(p2 + 4, 0, 'u16').s); } else if (kind === 1) put(r, c, wbStream[b6 + 2] ? 'TRUE' : 'FALSE'); else put(r, c, ''); } else put(r, c, fmtNum(dv.getFloat64(b6, true))); }
    else if (id === 0x0205) { const r = u16(body), c = u16(body + 2); put(r, c, wbStream[body + 7] ? '' : (wbStream[body + 6] ? 'TRUE' : 'FALSE')); }
    pos = body + len;
  }
  const maxR = Math.max(-1, ...cells.keys()); const rows: string[][] = [];
  for (let r = 0; r <= maxR; r++) { const row = cells.get(r); if (!row) continue; const maxC = Math.max(...row.keys()); const arr: string[] = []; for (let c = 0; c <= maxC; c++) arr.push((row.get(c) ?? '').trim()); if (arr.some(x => x)) rows.push(arr); }
  void globalsEnd; return { sheet: sheets[0].name, rows };
}
const fmtNum = (x: number) => Number.isInteger(x) ? String(x) : String(Math.round(x * 1e6) / 1e6);
const latin = (b: Uint8Array) => { let s = ''; for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]); return s; };

/** OLE2 복합 문서에서 이름이 맞는 스트림의 바이트(FAT·miniFAT 모두) */
function oleStream(b: Uint8Array, names: string[]): Uint8Array | null {
  const dv = new DataView(b.buffer, b.byteOffset, b.byteLength); const u16 = (o: number) => dv.getUint16(o, true), u32 = (o: number) => dv.getUint32(o, true);
  const secSize = 1 << u16(0x1e), miniSize = 1 << u16(0x20); const numFat = u32(0x2c), dirStart = u32(0x30), miniCut = u32(0x38), miniFatStart = u32(0x3c), numMiniFat = u32(0x40), difStart = u32(0x44), numDif = u32(0x48);
  const secOff = (s: number) => 512 + s * secSize;
  const fatSecs: number[] = []; for (let i = 0; i < 109 && i < numFat; i++) fatSecs.push(u32(0x4c + i * 4));
  let dif = difStart; for (let k = 0; k < numDif && dif < 0xfffffffe; k++) { const o = secOff(dif); for (let i = 0; i < secSize / 4 - 1; i++) { const s = u32(o + i * 4); if (s < 0xfffffffe) fatSecs.push(s); } dif = u32(o + secSize - 4); }
  const fat: number[] = []; for (const s of fatSecs) { const o = secOff(s); for (let i = 0; i < secSize / 4; i++) fat.push(u32(o + i * 4)); }
  const chain = (s: number, table: number[]) => { const out: number[] = []; let guard = 0; while (s < 0xfffffffe && guard++ < 1e6) { out.push(s); s = table[s]; } return out; };
  const readChain = (s: number) => { const secs = chain(s, fat); const out = new Uint8Array(secs.length * secSize); secs.forEach((x, i) => out.set(b.subarray(secOff(x), secOff(x) + secSize), i * secSize)); return out; };
  const dir = readChain(dirStart); const dd = new DataView(dir.buffer);
  const entries: { name: string; type: number; start: number; size: number }[] = [];
  for (let o = 0; o + 128 <= dir.length; o += 128) { const nl = dd.getUint16(o + 64, true); if (!nl) continue; const name = new TextDecoder('utf-16le').decode(dir.subarray(o, o + nl - 2)); entries.push({ name, type: dir[o + 66], start: dd.getUint32(o + 116, true), size: dd.getUint32(o + 120, true) }); }
  const root = entries.find(e => e.type === 5); const e = entries.find(x => names.includes(x.name)); if (!e) return null;
  if (e.size >= miniCut || !root) return readChain(e.start).subarray(0, e.size);
  const mini = readChain(root.start); const miniFat: number[] = []; for (const s of chain(miniFatStart, fat)) { const o = secOff(s); for (let i = 0; i < secSize / 4; i++) miniFat.push(u32(o + i * 4)); } void numMiniFat;
  const secs = chain(e.start, miniFat); const out = new Uint8Array(secs.length * miniSize); secs.forEach((x, i) => out.set(mini.subarray(x * miniSize, (x + 1) * miniSize), i * miniSize)); return out.subarray(0, e.size);
}

/** 파일 놓기 상자 — <div data-drop> 안에 안내와 <input type=file>; 파일을 읽으면 onTable(표, 파일 정보) */
/** 파일 놓기. onMany 를 주면 여러 파일을 한꺼번에(홈택스 목록조회는 법인 3개월씩이라 5년이면 20개 — 운영자 2026-11-05 '분기별로 하면 여러 번 해야 하잖아') */
export function mountDrop(el: HTMLElement, onTable: (t: FileTable) => void, label = '엑셀 파일을 여기에 놓거나 고르기', onMany?: (ts: FileTable[], fails: string[]) => void) {
  el.classList.add('vat-drop'); el.innerHTML = `<label class="vat-drop-in"><strong>${label}</strong><span class="note">.xlsx · .xls(홈택스·e호조·재정 포털 내려받기) · .csv · 한글 .hwpx·.hwp(표) — 파일은 이 브라우저 안에서만 읽고 밖으로 나가지 않습니다</span><input type="file" accept=".xlsx,.xls,.hwpx,.hwp,.csv,.txt,.tsv,.htm,.html,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"${onMany ? ' multiple' : ''} hidden /></label><p class="note vat-drop-msg" aria-live="polite"></p>`;
  const input = el.querySelector<HTMLInputElement>('input[type=file]')!; const msg = el.querySelector<HTMLElement>('.vat-drop-msg')!;
  const handle = async (f: File | undefined) => { if (!f) return; msg.textContent = `${f.name} 읽는 중…`; try { const t = await readTableFile(f); msg.textContent = `${f.name}: ${t.rows.length}행 읽음(${t.kind}${t.sheet ? ' · 시트 ' + t.sheet : ''})`; onTable(t); } catch (e) { msg.textContent = `${f.name}: 읽지 못했습니다 — ${(e as Error).message}. 엑셀에서 '다른 이름으로 저장 → CSV UTF-8' 로 바꿔 다시 놓거나 시트를 복사해 붙여넣으세요.`; } };
  const handleMany = async (fs: File[]) => { if (!onMany || fs.length < 2) return handle(fs[0]); const ts: FileTable[] = [], fails: string[] = []; for (const [i, f] of fs.entries()) { msg.textContent = `${i + 1}/${fs.length} ${f.name} 읽는 중…`; try { ts.push(await readTableFile(f)); } catch (e) { fails.push(`${f.name}(${(e as Error).message})`); } } msg.textContent = `파일 ${fs.length}개 — 읽음 ${ts.length}개 · ${ts.reduce((n, t) => n + t.rows.length, 0)}행${fails.length ? ` · 못 읽음 ${fails.length}개` : ''}`; onMany(ts, fails); };
  input.addEventListener('change', () => handleMany([...(input.files ?? [])]));
  el.addEventListener('dragover', e => { e.preventDefault(); el.classList.add('over'); }); el.addEventListener('dragleave', () => el.classList.remove('over'));
  el.addEventListener('drop', e => { e.preventDefault(); el.classList.remove('over'); void handleMany([...(e.dataTransfer?.files ?? [])]); });
}
