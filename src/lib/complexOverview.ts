import fs from 'node:fs';
import { readCsv } from './csv';

/** 대구 산업단지 전체 현황표(KOTRA 「대구 투자환경」 누리집 '전체 산업단지 현황', scripts/fetch_complex_overview.py → data/complexes/overview.csv·json).
 *  운영자 지시 2026-10-18 '다른 산단은 산단별 홈페이지 이런 곳을 찾아봐' — 관리기관 누리집에 생산 자료가 없는 단지(제3·서대구·검단·염색·테크노폴리스·농공단지 등)까지
 *  단지마다 연 매출액이 실린 표. 값은 표 그대로(면적 천㎡, 매출액 억 원), 행 순서도 표 그대로(순위 아님). '-' 는 빈 값. */
export type OvRow = { group: string; name: string; built: string; area: number | null; industrial: number | null; firms: number | null;
  employees: number | null; sales: number | null; agency: string };
export type OvMeta = { as_of: string; sales_year: string; source: string; url: string; fetched: string; total: Record<string, string> };
const num = (v: string | undefined) => (v == null || v === '' ? null : Number(v));
const FILE = 'data/complexes/overview.csv';
const META = 'data/complexes/overview.json';

export function complexOverview(): { rows: OvRow[]; meta: OvMeta } | null {
  if (!fs.existsSync(FILE) || !fs.existsSync(META)) return null;
  const rows = readCsv(FILE).map(r => ({
    group: r.group, name: r.name, built: r.built, area: num(r.area_k_m2), industrial: num(r.industrial_k_m2), firms: num(r.firms),
    employees: num(r.employees), sales: num(r.sales_eok), agency: r.agency,
  }));
  return { rows, meta: JSON.parse(fs.readFileSync(META, 'utf-8')) };
}
/** '’84~’12' → '1984~2012' (2000년 앞뒤는 두 자리로 가림: 60 이상이면 19xx) */
export const builtLabel = (s: string) => s.replace(/[’']\s*(\d\d)/g, (_, y) => `${Number(y) >= 60 ? '19' : '20'}${y}`);
