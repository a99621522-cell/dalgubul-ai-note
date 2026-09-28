import fs from 'node:fs';
import path from 'node:path';

/** render_kosis.py 산출물(src/generated/kosis)을 빌드 때 읽는다. 표는 index.json 의 tables, 그래프는 charts{name: file}. */
export type KosisTable = { id: string; title: string; unit: string; columns: string[]; rows: (string | number | null)[][]; source: string; latest: string; note?: string };
export type KosisChart = { wide: string; narrow: string; table: { title?: string; columns?: string[]; rows?: (string | number | null)[][]; unit?: string; note?: string } | null };
const DIR = 'src/generated/kosis';
const readJson = (p: string) => (fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf-8')) : null);

export const kosisIndex = (): { tables: KosisTable[]; charts: Record<string, string>; generated: string } =>
  readJson(path.join(DIR, 'index.json')) ?? { tables: [], charts: {}, generated: '' };

export const kosisTable = (id: string): KosisTable | null => kosisIndex().tables.find(t => t.id === id) ?? null;

export const kosisChart = (name: string): KosisChart | null => {
  const fn = kosisIndex().charts[name];
  if (!fn) return null;
  const wide = path.join(DIR, `${fn}.svg`), narrow = path.join(DIR, `${fn}.m.svg`);
  if (!fs.existsSync(wide)) return null;
  return { wide: fs.readFileSync(wide, 'utf-8'), narrow: fs.existsSync(narrow) ? fs.readFileSync(narrow, 'utf-8') : '', table: readJson(path.join(DIR, `${fn}.json`)) };
};

export const fmtCell = (v: string | number | null): string => {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') return Number.isInteger(v) ? v.toLocaleString('ko-KR') : v.toLocaleString('ko-KR', { maximumFractionDigits: 4 });
  const n = Number(v);
  return Number.isFinite(n) && /^-?\d+(\.\d+)?$/.test(v) ? (Number.isInteger(n) ? n.toLocaleString('ko-KR') : v) : v;
};
