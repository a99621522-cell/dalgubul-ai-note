import fs from 'node:fs';
import { readCsv } from './csv';
/** 한국은행 대구경북본부 「대구경북지역 주요 경제지표」의 대구 표(scripts/parse_bok_dg_daegu.py → data/bok/daegu_*.csv, 운영자 지시 2026-10-12 '한국은행자료 대구만 추출해서 올려').
 *  period: YYYY(연), YYYY-MM(월), YYYY-Qn(분기). 값은 표 그대로(억원 등), 잠정은 prelim='p'. */
export type BokTable = { key: string; title: string; source_title: string; unit: string; basis: string; columns: string[]; first: string; last: string };
export type BokMeta = { source: string; issue: string; region: string; tables: BokTable[] };
export function bokDaeguMeta(): BokMeta | null {
  const p = 'data/bok/daegu_tables.json';
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf-8')) : null;
}
export type BokRow = { period: string; prelim: boolean; vals: Record<string, string> };
/** 표 하나를 시점별 행으로 — 연간 최근 3개 + 월(또는 분기) 최근 n개, 최근이 위 */
export function bokDaeguRows(key: string, n = 13): { annual: BokRow[]; recent: BokRow[] } {
  const by = new Map<string, BokRow>();
  for (const r of readCsv(`data/bok/daegu_${key}.csv`)) {
    const o = by.get(r.period) ?? { period: r.period, prelim: false, vals: {} };
    o.vals[r.column] = r.value; if (r.prelim) o.prelim = true;
    by.set(r.period, o);
  }
  const all = [...by.values()].sort((a, b) => b.period.localeCompare(a.period));
  return { annual: all.filter(r => /^\d{4}$/.test(r.period)).slice(0, 3), recent: all.filter(r => !/^\d{4}$/.test(r.period)).slice(0, n) };
}
export const periodLabel = (p: string) => /^\d{4}$/.test(p) ? `${p}년` : /Q/.test(p) ? `${p.slice(0, 4)}년 ${p.slice(-1)}분기` : `${p.slice(0, 4)}.${p.slice(5)}`;
