/** 한국산업단지공단 「전국산업단지현황통계」 대구 단지 행(data/complex_stats/, scripts/fetch_complex_stats.py). 운영자 지적 2026-10-12 '산단별 생산액이 안나와'.
 *  분기 파일의 생산·수출은 그해 1월부터의 누계(백만원·천달러, 2018년 1분기 파일만 '생산'·'수출' 이름 — 1분기라 같은 값)이고,
 *  2025년 3분기부터 생산·수출·고용 공표가 중지되어(포털 안내) 그 뒤 파일엔 면적·입주·가동업체만 있다.
 *  같은 단지가 해마다 이름이 조금씩 다르고(달성2차 ①·②·(①+②), 대성하이스코 구 이름 등), 한 파일에 합계 행과 세부 행이 함께 있어
 *  단지 열쇠(key)로 묶고 같은 분기에 같은 열쇠가 여럿이면 입주업체가 가장 많은 행(합계 행)만 쓴다. 값은 원본 그대로, 단위 바꿈만. 평가·순위 없음. */
import fs from 'node:fs';
import path from 'node:path';

const DIR = 'data/complex_stats';

function parseCsv(text: string): string[][] {
  const out: string[][] = []; let row: string[] = []; let cell = ''; let q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) { if (ch === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += ch; }
    else if (ch === '"') q = true;
    else if (ch === ',') { row.push(cell); cell = ''; }
    else if (ch === '\n' || ch === '\r') { if (ch === '\r' && text[i + 1] === '\n') i++; row.push(cell); out.push(row); row = []; cell = ''; }
    else cell += ch;
  }
  if (cell || row.length) { row.push(cell); out.push(row); }
  return out.filter(r => r.some(c => c.trim()));
}

const num = (v: string | undefined) => { if (v == null) return null; const s = v.replace(/,/g, '').trim(); return /^-?\d+(\.\d+)?$/.test(s) ? Number(s) : null; };

/** 단지 열쇠·표시 이름. */
export function complexKey(name: string): { key: string; label: string } {
  const n = name.replace(/\s+/g, '');
  if (/하이스코/.test(n)) return { key: '대성하이스코', label: '대성하이스코' };
  if (/^달성(2?차|\+|①|②)/.test(n) || /^달성2차/.test(n) || /^달성차/.test(n)) return { key: '달성2차', label: '달성2차(외국인투자지역 포함)' };
  const label = n.replace(/\[[^\]]*\]/g, '');
  return { key: label, label };
}

export interface CxRow { key: string; label: string; type: string; district: string; tenants: number | null; operating: number | null;
  emp: number | null; prod: number | null; exp: number | null }

type FileInfo = { quarter: string; type: string; file: string };
let memo: Map<string, CxRow[]> | null = null;

/** 분기 → 대구 단지 행(열쇠마다 한 행). */
export function complexQuarters(): Map<string, CxRow[]> {
  if (memo) return memo;
  memo = new Map();
  const ip = path.join(DIR, 'index.json');
  if (!fs.existsSync(ip)) return memo;
  let files: FileInfo[] = [];
  try { files = JSON.parse(fs.readFileSync(ip, 'utf8')).files ?? []; } catch { return memo; }
  for (const f of files) {
    if (f.type.startsWith('외국인')) continue;   // 외국인투자지역 파일의 대구 행은 달성2차(외국인) 하나뿐 — 일반 파일 달성2차 합계 행에 이미 들어 있다
    const p = path.join(DIR, f.file);
    if (!fs.existsSync(p)) continue;
    const [head, ...rows] = parseCsv(fs.readFileSync(p, 'utf8'));
    const h = head.map(s => s.trim());
    const col = (...w: string[]) => h.findIndex(k => w.every(x => k.includes(x)));
    const c = { name: col('단지명'), type: col('유형'), sg: col('시군'), ten: col('입주'), op: col('가동업체'),
      emp: col('고용', '계'), prod: col('생산'), exp: col('수출') };
    const byKey = new Map<string, CxRow>();
    for (const r of rows) {
      const nm = (r[c.name] ?? '').trim(); if (!nm) continue;
      const { key, label } = complexKey(nm);
      const row: CxRow = { key, label, type: (r[c.type] ?? f.type).trim(), district: (r[c.sg] ?? '').trim(),
        tenants: num(r[c.ten]), operating: num(r[c.op]), emp: c.emp >= 0 ? num(r[c.emp]) : null,
        prod: c.prod >= 0 ? num(r[c.prod]) : null, exp: c.exp >= 0 ? num(r[c.exp]) : null };
      const prev = byKey.get(key);
      if (!prev || (row.tenants ?? -1) > (prev.tenants ?? -1)) byKey.set(key, row);
    }
    const list = memo.get(f.quarter) ?? [];
    list.push(...byKey.values());
    memo.set(f.quarter, list);
  }
  return memo;
}

export const qLabel = (q: string) => q.replace(/^(\d{4})Q(\d)$/, '$1년 $2분기');
export const qRange = (q: string) => { const m = q.match(/^(\d{4})Q(\d)$/); return m ? `${m[1]}년 1~${Number(m[2]) * 3}월` : q; };

/** 화면용 묶음: 최신 분기(입주·가동), 생산 마지막 분기(누계), 그 전년 같은 분기, 연간(4분기 누계) 연도별. */
export function complexOutput() {
  const qs = complexQuarters();
  const quarters = [...qs.keys()].sort();
  if (!quarters.length) return null;
  const latest = quarters.at(-1)!;
  const hasProd = (q: string) => (qs.get(q) ?? []).some(r => r.prod != null);
  const prodQ = [...quarters].reverse().find(hasProd) ?? null;
  const prevQ = prodQ ? `${Number(prodQ.slice(0, 4)) - 1}${prodQ.slice(4)}` : null;
  const years = quarters.filter(q => q.endsWith('Q4') && hasProd(q)).map(q => q.slice(0, 4));
  const lastYear = years.at(-1) ?? null;
  const get = (q: string | null, key: string) => (q ? (qs.get(q) ?? []).find(r => r.key === key) : undefined);
  // 행 목록: 최신 분기 단지 순서(원본 순서, 순위 아님). 최신 분기에 없는 옛 단지는 생산 분기에 있으면 뒤에 붙인다
  const base = [...(qs.get(latest) ?? [])];
  for (const r of (prodQ ? qs.get(prodQ) ?? [] : [])) if (!base.some(b => b.key === r.key)) base.push(r);
  const TYPE_ORDER = ['국가', '일반', '도시첨단', '농공', '외국인'];
  const tIdx = (t: string) => { const i = TYPE_ORDER.findIndex(x => t.startsWith(x)); return i < 0 ? 9 : i; };
  base.sort((a, b) => tIdx(a.type) - tIdx(b.type));
  const rows = base.map(b => {
    const L = get(latest, b.key), P = get(prodQ, b.key), V = get(prevQ, b.key), Y = get(lastYear ? `${lastYear}Q4` : null, b.key);
    return { key: b.key, label: b.label, type: b.type, district: b.district,
      tenants: L?.tenants ?? null, operating: L?.operating ?? null,
      emp: P?.emp ?? null, prod: P?.prod ?? null, exp: P?.exp ?? null, prodPrev: V?.prod ?? null,
      yProd: Y?.prod ?? null, yExp: Y?.exp ?? null, yEmp: Y?.emp ?? null,
      annual: years.map(y => get(`${y}Q4`, b.key)?.prod ?? null) };
  });
  return { latest, prodQ, prevQ, lastYear, years, rows };
}
