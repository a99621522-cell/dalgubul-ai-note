import type { APIRoute } from 'astro';
import fs from 'node:fs';
import { monthly, timeseries } from '../lib/stats';
import { allTags } from '../lib/sites';

/** /explore/ 데이터 탐색이 받는 집계 묶음(빌드 때 생성, /explore-data.json).
 *  monthly(YYYYMM.json) 의 산업·구군·단지·입지·태그별 지표 + 24개월 시계열. 기업 단위 계산은 /companies-index.json 으로 한다. */
type Lite = { firms: number; employment: number; covered: number; avg_employment: number | null; size_bands: Record<string, number>;
  nps_gain: number | null; nps_loss: number | null; new_firms: number | null; closed_firms: number | null; support_firms: number | null; support_records: number | null };
const lite = (m: any): Lite => ({
  firms: m.firms, employment: m.employment, covered: m.covered, avg_employment: m.avg_employment ?? null, size_bands: m.size_bands ?? {},
  nps_gain: m.nps_gain ?? null, nps_loss: m.nps_loss ?? null, new_firms: m.new_firms ?? null, closed_firms: m.closed_firms ?? null,
  support_firms: m.support_3y?.firms ?? null, support_records: m.support_3y?.records ?? null,
});
const mapLite = (o: Record<string, any> | undefined) => Object.fromEntries(Object.entries(o ?? {}).map(([k, v]) => [k, lite(v)]));

export const GET: APIRoute = () => {
  const m = monthly();
  const ts = timeseries();
  const body = {
    stats_month: m?.month ?? null, basis_label: m?.basis_label ?? '', companies_as_of: m?.sources?.factoryon?.as_of ?? '',
    total: m ? lite(m.total) : null,
    dims: {
      industry: Object.keys(m?.by_industry ?? {}), district: Object.keys(m?.by_district ?? {}), complex: Object.keys(m?.by_complex ?? {}),
      site: Object.keys(m?.by_site ?? {}), tag: Object.keys(m?.by_tag ?? {}),
    },
    metrics: { industry: mapLite(m?.by_industry), district: mapLite(m?.by_district), complex: mapLite(m?.by_complex), site: mapLite(m?.by_site), tag: mapLite(m?.by_tag) },
    cross: m?.cross ?? {}, cross_site: m?.cross_site ?? {},
    timeseries: ts ? { months: ts.months, basis: ts.basis, total: { employment: ts.total.employment, firms: ts.total.firms },
      by_industry: ts.by_industry, by_district: ts.by_district, by_complex: ts.by_complex, by_site: ts.by_site ?? {} } : null,
    tag_names: Object.fromEntries(allTags().map(t => [t.key, t.name])),
  };
  return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
};
