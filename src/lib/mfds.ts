import fs from 'node:fs';
import { readCsv } from './csv';
import type { Series } from './monthly';

/** 식약처 「의료기기 생산 및 수·출입 실적 통계 자료」 지역별 표(scripts/fetch_mfds_device.py → data/mfds/device_region.csv).
 *  운영자 지시 2026-10-05: 보건산업 지역 통계 연결. 값은 원문 그대로이고 단위만 바꾼다(천 원 ÷100,000 = 억 원, USD ÷1,000,000 = 백만 달러).
 *  비율은 원문의 전국 대비 비율. 지역 구분은 원문대로(경기는 북부·남부). 평가·순위 없음. */
type Row = Record<string, string>;
const rows: Row[] = readCsv('data/mfds/device_region.csv');
const idx = (() => { try { return JSON.parse(fs.readFileSync('data/mfds/raw/index.json', 'utf-8')); } catch { return {}; } })() as Record<string, { view?: string }>;

const n = (v?: string) => (v == null || v === '' ? null : Number(v));
const pick = (y: number, scope: string, kind: string, region: string) =>
  rows.find(r => Number(r.year) === y && r.scope === scope && r.kind === kind && r.region === region);
export const DEVICE_YEARS = [...new Set(rows.map(r => Number(r.year)))].sort();
export const deviceLatest = DEVICE_YEARS.at(-1) ?? 0;
const latestPub = Object.keys(idx).sort().at(-1) ?? '';
export const DEVICE_SRC = `식품의약품안전처 「${latestPub}년도 의료기기 생산 및 수·출입 실적 통계 자료」 외 연도별 자료`;
export const DEVICE_URL = idx[latestPub]?.view ?? 'https://www.mfds.go.kr/brd/m_386/list.do';
/** 금액 단위 바꿈: 생산 천 원 → 억 원, 수출입 USD → 백만 달러 */
export const amt = (r: Row | undefined) => { const v = n(r?.amount); return v == null ? null : r!.unit === '천원' ? v / 100000 : v / 1e6; };

export function deviceSeries(region = '대구'): Series[] {
  const base = { group: '의료기기', change: '%' as const, source: DEVICE_SRC, url: DEVICE_URL };
  const mk = (key: string, name: string, unit: string, digits: number, f: (y: number) => number | null, note?: string): Series => ({
    ...base, key, name, unit, digits, note,
    pts: DEVICE_YEARS.map(y => ({ m: `${y}-12`, v: f(y) })).filter((p): p is { m: string; v: number } => p.v != null),
  });
  return [
    mk('dev-prod', '의료기기 생산액', '억 원', 0, y => amt(pick(y, '전체', '생산', region))),
    mk('dev-prod-share', '생산액 전국 대비 비율', '%', 2, y => n(pick(y, '전체', '생산', region)?.amount_share), '원문의 비율'),
    mk('dev-exp', '의료기기 수출액', '백만 달러', 1, y => amt(pick(y, '전체', '수출', region))),
    mk('dev-firms', '생산실적 보고 업체', '개소', 0, y => n(pick(y, '전체', '생산', region)?.firms)),
  ].filter(s => s.pts.length);
}

/** 대구 연도별 표(전체 = 체외진단 포함). */
export function deviceYearRows(region = '대구', scope = '전체') {
  return DEVICE_YEARS.map(y => {
    const p = pick(y, scope, '생산', region), e = pick(y, scope, '수출', region), i = pick(y, scope, '수입', region);
    return { y, pf: n(p?.firms), ps: n(p?.staff), pa: amt(p), psh: n(p?.amount_share), ef: n(e?.firms), ea: amt(e), esh: n(e?.amount_share), ia: amt(i), ish: n(i?.amount_share) };
  }).filter(r => r.pf != null || r.ef != null || r.ia != null).reverse();
}

/** 최근 해 지역별 표(원문 지역 순서, 순위 아님). */
export function deviceRegionRows(y = deviceLatest) {
  const regions = [...new Set(rows.filter(r => Number(r.year) === y && r.scope === '전체').map(r => r.region))];
  return regions.map(region => {
    const p = pick(y, '전체', '생산', region), e = pick(y, '전체', '수출', region);
    return { region, pf: n(p?.firms), ps: n(p?.staff), pa: amt(p), psh: n(p?.amount_share), ef: n(e?.firms), ea: amt(e), esh: n(e?.amount_share) };
  });
}
