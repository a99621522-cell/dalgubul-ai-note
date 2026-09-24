import fs from 'node:fs';
import path from 'node:path';

/** build_stats.py / render_charts.py 산출물을 빌드 때 읽는다. 값이 없는 지표는 null 이며 화면은 '자료 없음'으로 보인다. */
export type Delta = { diff: number | null; pct: number | null } | null;
export type Metrics = {
  firms: number; employment: number; covered: number; avg_employment: number | null;
  size_bands: Record<'1~9' | '10~49' | '50~299' | '300+', number>;
  nps_gain: number | null; nps_loss: number | null; new_firms: number | null; closed_firms: number | null;
  dart_firms: number | null; dart_revenue: number | null; projects_12m: number | null;
  mom: { firms: Delta; employment: Delta } | null; yoy: { firms: Delta; employment: Delta } | null;
};
export type Monthly = {
  month: string; generated: string; basis: 'nps' | 'factoryon'; basis_label: string;
  sources: { factoryon: { as_of: string; companies: number }; nps: { file: string; rows: number; matched: number } | null; dart: { corps_daegu: number; note: string } };
  total: Metrics; by_industry: Record<string, Metrics>; by_complex: Record<string, Metrics>; by_district: Record<string, Metrics>;
  cross: Record<string, Record<string, { firms: number; employment: number; covered: number }>>;
  open_programs: number;
};
export type Timeseries = {
  months: string[]; basis: string[]; note: string;
  total: { employment: (number | null)[]; firms: (number | null)[]; covered: (number | null)[] };
  by_industry: Record<string, { employment: (number | null)[]; firms: (number | null)[]; covered: (number | null)[] }>;
  by_complex: Record<string, { employment: (number | null)[]; firms: (number | null)[]; covered: (number | null)[] }>;
  by_district: Record<string, { employment: (number | null)[]; firms: (number | null)[]; covered: (number | null)[] }>;
};
export type ChartIndex = { months: string[]; latest: string; basis: string; compare_default: string[] } & Record<string, any>;
export type CompanyStat = { g: string; e: number | null; b: 'nps' | 'factoryon'; s?: (number | null)[] };

const STATS = 'data/stats';
const CHARTS = 'src/generated/charts';
const readJson = (p: string) => (fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf-8')) : null);

let _months: string[] | null = null;
/** 집계된 달 목록 (YYYYMM, 오름차순) */
export const statMonths = (): string[] => {
  if (_months) return _months;
  const dir = path.join(STATS, 'monthly');
  _months = fs.existsSync(dir) ? fs.readdirSync(dir).filter(f => /^\d{6}\.json$/.test(f)).map(f => f.slice(0, 6)).sort() : [];
  return _months;
};
export const latestMonth = () => statMonths().at(-1) ?? null;
const _monthly = new Map<string, Monthly | null>();
export const monthly = (ym?: string): Monthly | null => {
  const m = ym ?? latestMonth();
  if (!m) return null;
  if (!_monthly.has(m)) _monthly.set(m, readJson(path.join(STATS, 'monthly', `${m}.json`)));
  return _monthly.get(m) ?? null;
};
let _ts: Timeseries | null = null;
export const timeseries = (): Timeseries | null => (_ts ??= readJson(path.join(STATS, 'timeseries.json')));
let _idx: ChartIndex | null = null;
export const chartIndex = (): ChartIndex | null => (_idx ??= readJson(path.join(CHARTS, 'index.json')));
let _co: { months: string[]; companies: Record<string, CompanyStat> } | null = null;
export const companyStats = () => (_co ??= readJson(path.join(STATS, 'companies.json')));

/** 그래프 파일 세 개(넓은 판·좁은 판·표). 없으면 null. */
export function chart(kind: string, name: string) {
  const fn = chartIndex()?.[kind]?.[name];
  if (!fn) return null;
  const read = (ext: string) => { const p = path.join(CHARTS, fn + ext); return fs.existsSync(p) ? fs.readFileSync(p, 'utf-8') : null; };
  const wide = read('.svg'), narrow = read('.m.svg');
  if (!wide) return null;
  return { wide, narrow: narrow ?? wide, table: JSON.parse(read('.json') ?? 'null') as { title: string; columns: string[]; unit?: string; rows: (string | number | null)[][]; note?: string } | null };
}

/** 'YYYY-MM' → '2026년 8월' */
export const monthLabel = (ym: string) => { const [y, m] = ym.replace(/(\d{4})(\d{2})/, '$1-$2').split('-'); return `${y}년 ${Number(m)}월`; };
/** 숫자 → 천 단위 쉼표. null → '자료 없음' */
export const fmt = (n: number | null | undefined, unit = '') => (n === null || n === undefined ? '자료 없음' : `${n.toLocaleString('ko-KR')}${unit}`);
/** 증감 표시용: 기호(+/−)·부호 클래스 */
export const deltaParts = (d: Delta) => {
  if (!d || d.diff === null) return { text: '자료 없음', cls: 'none', pct: '' };
  const sign = d.diff > 0 ? '+' : d.diff < 0 ? '−' : '';
  const cls = d.diff > 0 ? 'up' : d.diff < 0 ? 'down' : 'none';
  return { text: `${sign}${Math.abs(d.diff).toLocaleString('ko-KR')}`, cls, pct: d.pct === null ? '' : `${sign}${Math.abs(d.pct)}%` };
};
