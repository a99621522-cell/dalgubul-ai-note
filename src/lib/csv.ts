import fs from 'node:fs';
import path from 'node:path';
/** 아주 단순한 CSV 파서(따옴표 필드 지원). scripts/data/*.csv 전용 */
export function readCsv(rel: string): Record<string, string>[] {
  const p = path.resolve(rel);
  if (!fs.existsSync(p)) return [];
  const text = fs.readFileSync(p, 'utf-8').replace(/^\uFEFF/, '');
  const rows: string[][] = []; let cur: string[] = []; let field = ''; let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i+1] === '"') { field += '"'; i++; } else q = false; } else field += c; }
    else if (c === '"') q = true;
    else if (c === ',') { cur.push(field); field = ''; }
    else if (c === '\n') { cur.push(field); rows.push(cur); cur = []; field = ''; }
    else if (c !== '\r') field += c;
  }
  if (field || cur.length) { cur.push(field); rows.push(cur); }
  const head = rows.shift() ?? [];
  return rows.filter(r => r.length > 1).map(r => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ''])));
}
export type Company = { id: string; name: string; complex: string; district: string; eupmyeon: string; sector_code: string; sector: string; sector_group: string; product: string; workers_band: string; workers: string; reg_type: string; first_registered: string; mfg_area_band: string; address: string; sites: string; source: string; as_of: string };
export const shortComplex = (s: string) => s.replace('일반산업단지','산단').replace('첨단산업단지','산단').replace('산업단지','산단').replace('지방산단','산단');
export const companies = () => readCsv('scripts/data/dalseong_companies.csv') as Company[];
export const complexes = () => readCsv('scripts/data/dalseong_complexes.csv');

/** 구·군별 집계 (기업 수·종사자) */
export function byDistrict() {
  const m = new Map<string, { firms: number; workers: number }>();
  for (const c of companies()) {
    const k = c.district || '기타'; const cur = m.get(k) ?? { firms: 0, workers: 0 };
    cur.firms++; cur.workers += Number(c.workers) || 0; m.set(k, cur);
  }
  return [...m.entries()].map(([name, v]) => ({ name, ...v })).sort((a, b) => b.workers - a.workers);
}
