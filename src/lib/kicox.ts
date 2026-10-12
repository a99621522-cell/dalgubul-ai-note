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
