/** 라이브러리 없는 엑셀(.xlsx) 쓰기 — 시트 여러 개, 첫 줄 머리글(굵게·틀 고정), 숫자는 숫자 칸, 글자는 인라인 문자열.
 *  경정청구 묶음을 엑셀로도 내기 위해(운영자 2026-11-05 '파일은 엑셀과 pdf 둘 다 — 홈택스에 어떤 파일 양식을 올리는지 모르니'). zip 은 vat_rules.zipStore(저장 방식). */
import { zipStore } from './vat_rules';

export type Sheet = { name: string; rows: (string | number | null | undefined)[][]; widths?: number[] };
const X = (s: string) => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!)).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '');
const col = (i: number) => { let s = ''; i++; while (i > 0) { const m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = Math.floor((i - 1) / 26); } return s; };
const sheetName = (n: string, used: Set<string>) => { let b = n.replace(/[[\]:*?/\\]/g, ' ').slice(0, 31) || '시트'; let x = b, i = 2; while (used.has(x)) x = `${b.slice(0, 28)} ${i++}`; used.add(x); return x; };

function sheetXml(sh: Sheet): string {
  const w = sh.widths ?? (sh.rows[0] ?? []).map((_, j) => Math.min(60, Math.max(8, ...sh.rows.slice(0, 200).map(r => String(r[j] ?? '').length * 1.6 + 2))));
  const rows = sh.rows.map((r, i) => `<row r="${i + 1}">${r.map((v, j) => { const ref = `${col(j)}${i + 1}`; const s = i === 0 ? ' s="1"' : ''; if (v === null || v === undefined || v === '') return ''; if (typeof v === 'number' && Number.isFinite(v)) return `<c r="${ref}"${s}><v>${v}</v></c>`; return `<c r="${ref}" t="inlineStr"${s}><is><t xml:space="preserve">${X(String(v))}</t></is></c>`; }).join('')}</row>`).join('');
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>${w.map((x, j) => `<col min="${j + 1}" max="${j + 1}" width="${Math.round(x)}" customWidth="1"/>`).join('')}</cols><sheetData>${rows}</sheetData></worksheet>`;
}

/** 시트들 → .xlsx Blob */
export function xlsxBlob(sheets: Sheet[]): Blob {
  const used = new Set<string>(); const names = sheets.map(s => sheetName(s.name, used));
  const files: { name: string; data: string }[] = [
    { name: '[Content_Types].xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${sheets.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}</Types>` },
    { name: '_rels/.rels', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>` },
    { name: 'xl/workbook.xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${names.map((n, i) => `<sheet name="${X(n)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('')}</sheets></workbook>` },
    { name: 'xl/_rels/workbook.xml.rels', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${sheets.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join('')}<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>` },
    { name: 'xl/styles.xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="10"/><name val="맑은 고딕"/></font><font><b/><sz val="10"/><name val="맑은 고딕"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0"/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>` },
    ...sheets.map((s, i) => ({ name: `xl/worksheets/sheet${i + 1}.xml`, data: sheetXml(s) }))];
  return new Blob([zipStore(files)], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
}

/** CSV 글자(toCsv 결과, BOM 가능) → 행 — 숫자처럼 보이는 칸은 숫자로 */
export function csvRows(csv: string): (string | number)[][] {
  const t = csv.replace(/^﻿/, ''); const out: string[][] = []; let row: string[] = [], cur = '', q = false;
  for (let i = 0; i < t.length; i++) { const c = t[i]; if (q) { if (c === '"' && t[i + 1] === '"') { cur += '"'; i++; } else if (c === '"') q = false; else cur += c; continue; }
    if (c === '"') q = true; else if (c === ',') { row.push(cur); cur = ''; } else if (c === '\n' || c === '\r') { if (c === '\r' && t[i + 1] === '\n') i++; row.push(cur); out.push(row); row = []; cur = ''; } else cur += c; }
  if (cur || row.length) { row.push(cur); out.push(row); }
  const txt = (out[0] ?? []).map(h => /번호|코드|날짜|일자|기한/.test(h));   // 등록번호·날짜는 글자 그대로
  return out.map((r, i) => r.map((v, j) => i > 0 && !txt[j] && /^-?\d+(\.\d+)?$/.test(v) && v.length < 16 && !/^0\d/.test(v) ? Number(v) : v));
}
