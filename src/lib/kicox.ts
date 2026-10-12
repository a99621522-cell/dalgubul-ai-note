import { readCsv } from './csv';
/** 한국산업단지공단 「전국산업단지 현황통계」(분기) 대구 단지 행 — scripts/import_kicox_stats.py → data/complexes/kicox_stats.csv(운영자 지시 2026-10-12).
 *  면적은 천㎡, 분양률은 통계표 값(%). fo_name 은 기업 사전(팩토리온) 단지 이름 — 여러 행이 한 이름이면 합(분양률은 분양 ÷ 분양대상 합). 값을 만들지 않는다. */
export type KicoxRow = { quarter: string; type: string; district: string; name: string; sub: string; status: string;
  designated_k_m2: string; managed_k_m2: string; industrial_k_m2: string; sale_target_k_m2: string; sold_k_m2: string; unsold_k_m2: string;
  sale_rate: string; firms_contracted: string; firms_operating: string; fo_name: string };
let cache: KicoxRow[] | null = null;
export const kicoxRows = () => (cache ??= readCsv('data/complexes/kicox_stats.csv') as KicoxRow[]);
export const kicoxQuarter = () => { const q = kicoxRows()[0]?.quarter ?? ''; return q ? `${q.slice(0, 4)}년 ${q.slice(5)}분기` : ''; };
const nz = (v: string) => (v === '' ? 0 : Number(v));
export type KicoxSum = { contracted: number; operating: number; rate: number | null; parts: string[] };
/** 기업 사전 단지 이름 → 산단공 값(이어진 행 합) */
export function kicoxByFo(): Map<string, KicoxSum> {
  const out = new Map<string, KicoxSum & { t: number; s: number }>();
  for (const r of kicoxRows()) {
    if (!r.fo_name) continue;
    const o = out.get(r.fo_name) ?? { contracted: 0, operating: 0, rate: null, parts: [], t: 0, s: 0 };
    o.contracted += nz(r.firms_contracted); o.operating += nz(r.firms_operating);
    o.t += nz(r.sale_target_k_m2); o.s += nz(r.sold_k_m2); o.parts.push(r.name);
    o.rate = o.parts.length === 1 ? (r.sale_rate === '' ? null : Number(r.sale_rate)) : (o.t ? (o.s / o.t) * 100 : null);
    out.set(r.fo_name, o);
  }
  return out;
}

/** 산업단지 관리기관이 누리집에 공개한 분기 생산·수출(scripts/fetch_complex_reports.py → parse_complex_reports.py, 운영자 지시 2026-10-12 '산단별 매출액').
 *  production.csv = 산단공 양식 「단지별 입주현황」(하위 단지별, 백만원·십억원), trend.csv = 관리기관 경기동향 보고서의 분기 합계(백만원). 값은 문서 그대로. */
export type ProdRow = { source: string; quarter: string; complex: string; total: string; fo_name: string; firms: string; operating: string; operating_rate: string;
  employment_prev: string; employment: string; prod_prev_bil: string; prod_bil: string; export_prev_bil: string; export_bil: string;
  prod_plan_mil: string; prod_q_mil: string; prod_cum_mil: string; export_plan_mil: string; export_q_mil: string; export_cum_mil: string; doc_url: string };
export type TrendRow = { source: string; quarter: string; operating_rate: string; prod_mil: string; domestic_mil: string; export_mil: string; firms: string; workers: string; doc_url: string };
let pc: ProdRow[] | null = null;
let tc: TrendRow[] | null = null;
export const complexProd = () => (pc ??= readCsv('data/complexes/production.csv') as ProdRow[]);
export const complexTrend = () => (tc ??= (readCsv('data/complexes/trend.csv') as TrendRow[]).sort((a, b) => a.quarter.localeCompare(b.quarter)));
/** 관리기관 이름 */
export const SOURCE_NAME: Record<string, string> = { seongseo: '대구성서산업단지관리공단' };
export const qLabelK = (q: string) => (q ? `${q.slice(0, 4)}년 ${q.slice(5)}분기` : '');
export type MonthRow = { source: string; month: string; prod_mil: string; export_kusd: string; workers: string; issue: string; doc_url: string };
let mc: MonthRow[] | null = null;
/** 월간 소식지(달성1차산업단지 뉴스)의 'N월 중 현황' — data/complexes/monthly.csv */
export const complexMonthly = () => (mc ??= (readCsv('data/complexes/monthly.csv') as MonthRow[]).sort((a, b) => a.month.localeCompare(b.month)));
/** 월간 자료 관리기관 → 기업 사전 단지 이름 */
const MONTHLY_FO: Record<string, string> = { dalin: '달성일반산업단지' };
SOURCE_NAME.dalin = '달성1차산업단지관리공단';
/** 기업 사전 단지 이름 → 가장 최근 생산(백만원, 하위 단지 합)과 그 기간 이름(분기 또는 월) */
export function prodByFo(): Map<string, { period: string; prod: number; parts: string[] }> {
  const rows = complexProd();
  const latest = rows.reduce((m, r) => (r.quarter > m ? r.quarter : m), '');
  const out = new Map<string, { period: string; prod: number; parts: string[] }>();
  for (const r of rows) {
    if (!r.fo_name || r.quarter !== latest) continue;
    const o = out.get(r.fo_name) ?? { period: `${r.quarter.slice(2, 4)}년 ${r.quarter.slice(5)}분기`, prod: 0, parts: [] };
    o.prod += Number(r.prod_q_mil); o.parts.push(r.complex);
    out.set(r.fo_name, o);
  }
  const mrows = complexMonthly();
  for (const [src, fo] of Object.entries(MONTHLY_FO)) {
    const last = mrows.filter(r => r.source === src).at(-1);
    if (last && !out.has(fo)) out.set(fo, { period: `${last.month.slice(2, 4)}년 ${Number(last.month.slice(5))}월`, prod: Number(last.prod_mil), parts: [src] });
  }
  return out;
}
