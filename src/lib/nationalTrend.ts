import fs from 'node:fs';
import { readCsv } from './csv';

/** 대구국가산업단지 산업동향(한국산업단지공단 「주요국가산업단지 산업동향」, 공공데이터포털 파일데이터) — 운영자 지적 2026-10-18 '국가산단은 산업단지관리공단에 자료가 있잖아'.
 *  scripts/fetch_national_trend.py → data/complex_trend/daegu_national.csv(시점 하나 = 한 줄). 2018년 1월~2024년 1분기는 월간 판, 2024년 2분기부터 분기 판.
 *  값은 원 파일 그대로(생산 억 원·수출 백만 달러·고용 명·가동률 %), 같은 시점은 연간보정 판. 생산·수출·가동률은 제조업 가동업체 조사(포털 안내). 평가 없음. */
export type NtRow = {
  period: string; freq: 'M' | 'Q'; production: number | null; productionCum: number | null; export: number | null; exportCum: number | null;
  employment: number | null; empMale: number | null; empFemale: number | null; mfgFirms: number | null; opRate: number | null;
  firmsIn: number | null; firmsOp: number | null; tenants: number | null; rateLt50: number | null; rate50: number | null; rateGe300: number | null; revised: boolean;
};
const num = (v: string | undefined) => { if (v == null || v.trim() === '') return null; const n = Number(v.replace(/,/g, '')); return Number.isFinite(n) ? n : null; };
const FILE = 'data/complex_trend/daegu_national.csv';

export function nationalTrend(): NtRow[] {
  if (!fs.existsSync(FILE)) return [];
  return readCsv(FILE).map(r => ({
    period: r.period, freq: r.freq as 'M' | 'Q', production: num(r.production_eok), productionCum: num(r.production_cum_eok),
    export: num(r.export_musd), exportCum: num(r.export_cum_musd), employment: num(r.employment), empMale: num(r.emp_male), empFemale: num(r.emp_female),
    mfgFirms: num(r.mfg_firms), opRate: num(r.op_rate), firmsIn: num(r.firms_in), firmsOp: num(r.firms_op), tenants: num(r.tenants),
    rateLt50: num(r.rate_lt50), rate50: num(r.rate_50_300), rateGe300: num(r.rate_ge300), revised: r.revised === '1',
  }));
}
export const ntLabel = (p: string) => p.includes('Q') ? `${p.slice(0, 4)}년 ${p.slice(-1)}분기` : `${p.slice(0, 4)}년 ${Number(p.slice(5))}월`;

/** 연도별: 그해 마지막 시점(12월 또는 4분기, 진행 중인 해는 최근 시점)의 누계 생산·수출과 그 시점 고용·입주·가동. */
export function ntYears(rows: NtRow[]) {
  const by = new Map<string, NtRow>();
  for (const r of rows) if (r.productionCum != null || r.employment != null) by.set(r.period.slice(0, 4), r);   // 시점 순이라 마지막이 남는다
  return [...by.entries()].map(([y, r]) => ({
    year: y, last: r.period, full: r.period.endsWith('-12') || r.period.endsWith('Q4'),
    production: r.productionCum, export: r.exportCum, employment: r.employment, firmsIn: r.firmsIn, firmsOp: r.firmsOp,
  }));
}
