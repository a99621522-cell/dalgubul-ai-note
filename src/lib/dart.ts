import { financials, companies, normName, byName, readCsv, type Financial, type Company } from './csv';
import { classify } from './industry';

/** DART 대구 본사 공시 기업 재무(scripts/collect_dart_fin.py → scripts/data/company_financials.csv, 운영자 지시 2026-10-05).
 *  사업보고서 주요계정(연결 우선) 값 그대로. 원 → 억 원은 나눗셈만, 비율·순위는 계산하지 않는다. */
export type DartCorp = {
  code: string; name: string; cls: string; district: string; group: string; years: Record<string, Financial>;
  latest: Financial; companyId: string | null; url: string;
};
export const eok = (won?: string) => { const n = Number(won); return won && Number.isFinite(n) ? n / 1e8 : null; };

export function dartCorps(): { corps: DartCorp[]; years: string[]; asOf: string } {
  const rows = financials().filter(r => r.region || r.corp_cls);   // 새 형식(본사 시군구·상장 구분이 있는 행)
  const years = [...new Set(rows.map(r => r.year))].sort().slice(-3);
  const byCode = new Map<string, Financial[]>();
  for (const r of rows) byCode.set(r.corp_code, [...(byCode.get(r.corp_code) ?? []), r]);
  const coByName = new Map<string, Company>();
  for (const c of companies()) { const k = normName(c.name); const o = coByName.get(k); if (!o || Number(c.workers || 0) > Number(o.workers || 0)) coByName.set(k, c); }
  const corps = [...byCode.entries()].map(([code, rs]) => {
    const ys = Object.fromEntries(rs.map(r => [r.year, r]));
    const latest = [...rs].sort((a, b) => b.year.localeCompare(a.year))[0];
    const co = coByName.get(normName(latest.name));
    return {
      code, name: latest.name, cls: latest.corp_cls || '', district: (latest.region || '').split(' ')[1] ?? '',
      group: classify(latest.induty_code || '', '', ''), years: ys, latest, companyId: co?.id ?? null,
      url: latest.source_url || `https://dart.fss.or.kr/dsab007/main.do?option=corp&textCrpNm=${encodeURIComponent(latest.name)}`,
    };
  }).sort((a, b) => byName(a.name, b.name));
  const asOf = rows.map(r => r.as_of).sort().at(-1) ?? '';
  return { corps, years, asOf };
}

/** 개수 세기(구분·산업·구군) — 순위가 아니라 분포 */
export const countBy = <T,>(xs: T[], f: (x: T) => string) => {
  const m = new Map<string, number>();
  for (const x of xs) { const k = f(x) || '미상'; m.set(k, (m.get(k) ?? 0) + 1); }
  return [...m.entries()];
};

/** 미래 산업 관련 공시(scripts/collect_dart_future.py → data/dart/future.csv): 대구 본사 기업의 투자·계약·지분·특허 공시 중
 *  원문에 미래 산업 낱말이 나온 것. 공시 사실·제목·링크와 근거 구절만. */
export type FutureDisclosure = { rcept_dt: string; corp_code: string; name: string; report_nm: string; event: string; fields: string; keywords: string; excerpt: string; rcept_no: string; url: string };
export const futureDisclosures = () => readCsv('data/dart/future.csv') as FutureDisclosure[];
export const ymd = (s: string) => (s && s.length === 8 ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6)}` : s);
