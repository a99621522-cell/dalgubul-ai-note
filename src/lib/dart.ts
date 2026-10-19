import fs from 'node:fs';
import path from 'node:path';
import { financials, companies, normName, byName, readCsv, type Financial, type Company } from './csv';
import { classify } from './industry';

/** DART 대구 본사 공시 기업 재무(scripts/collect_dart_fin.py → scripts/data/company_financials.csv, 운영자 지시 2026-10-05).
 *  사업보고서 주요계정(연결 우선) 값 그대로. 원 → 억 원은 나눗셈만, 비율·순위는 계산하지 않는다. */
export type DartCorp = {
  code: string; name: string; cls: string; stock: string; district: string; ksic: string; group: string; years: Record<string, Financial>;
  latest: Financial | undefined; companyId: string | null; url: string;
  /** 업종 이름(KSIC — 공장등록 자료에 같은 코드가 있을 때)·공장등록 생산품(기업 사전과 이름이 같을 때) */
  ksicName: string; factoryProduct: string;
};
export const eok = (won?: string) => { const n = Number(won); return won && Number.isFinite(n) ? n / 1e8 : null; };
/** 영업이익률(%) = 영업이익 ÷ 매출액 × 100, 매출액 증가율(%) = (올해 ÷ 전년 − 1) × 100 — 공시 값의 나눗셈만(운영자 지시 2026-10-05).
 *  매출액이 0 이하이거나 없으면, 증가율은 두 해의 재무제표 기준(연결·개별)이 다르면 계산하지 않는다(—). 순위·정렬에 쓰지 않는다. */
export const opMargin = (f?: Financial) => { const r = Number(f?.revenue), o = Number(f?.operating_income); return f?.revenue && f?.operating_income && r > 0 && Number.isFinite(o) ? (o / r) * 100 : null; };
export const revGrowth = (cur?: Financial, prev?: Financial) => { const a = Number(cur?.revenue), b = Number(prev?.revenue); return cur?.revenue && prev?.revenue && b > 0 && a > 0 && cur.fs === prev.fs ? (a / b - 1) * 100 : null; };
/** 부채비율(%) = 부채총계 ÷ 자본총계 × 100 — 자본총계가 0 이하(자본잠식)면 계산하지 않는다 */
export const debtRatio = (f?: Financial) => { const l = Number(f?.total_liabilities), e = Number(f?.total_equity); return f?.total_liabilities && f?.total_equity && e > 0 && Number.isFinite(l) ? (l / e) * 100 : null; };
export const pct1 = (v: number | null) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(1)}`);
export const pct1n = (v: number | null) => (v == null ? '—' : v.toFixed(1));

/** 기업개황 상장 구분(corp_cls) → 이름. 코넥스도 상장(시장)으로 센다 */
export const CLS_NAME: Record<string, string> = { Y: '유가증권', K: '코스닥', N: '코넥스', E: '기타' };
export const isListed = (cls: string) => cls === '유가증권' || cls === '코스닥' || cls === '코넥스';

/** 대구 본사 공시 기업 전체: 기업개황 캐시(scripts/state/dart_corp.json, daegu: true)를 기준으로 재무가 없는 회사도 넣는다
 *  (사업보고서 재무를 못 받은 코넥스·비상장 회사도 직원·연구개발비·출자 자료가 있을 수 있다). */
export const dartCorps = (() => { let v: { corps: DartCorp[]; years: string[]; asOf: string } | undefined; return () => (v ??= build()); })();
function build() {
  const rows = financials().filter(r => r.region || r.corp_cls);   // 새 형식(본사 시군구·상장 구분이 있는 행)
  const years = [...new Set(rows.map(r => r.year))].sort().slice(-3);
  const byCode = new Map<string, Financial[]>();
  for (const r of rows) byCode.set(r.corp_code, [...(byCode.get(r.corp_code) ?? []), r]);
  const cache = path.resolve('scripts/state/dart_corp.json');
  const meta: Record<string, { name: string; corp_cls: string; stock_code: string; region: string; induty_code: string; daegu: boolean }> =
    fs.existsSync(cache) ? JSON.parse(fs.readFileSync(cache, 'utf-8')) : {};
  const codes = new Set([...byCode.keys(), ...Object.entries(meta).filter(([, m]) => m.daegu).map(([k]) => k)]);
  const coByName = new Map<string, Company>();
  const ksicNames = new Map<string, string>();
  for (const c of companies()) {
    const k = normName(c.name); const o = coByName.get(k); if (!o || Number(c.workers || 0) > Number(o.workers || 0)) coByName.set(k, c);
    if (c.sector_code && !ksicNames.has(c.sector_code)) ksicNames.set(c.sector_code, c.sector.replace(/\s*외\s*\d+\s*종$/, '').trim());
  }
  const corps = [...codes].map(code => {
    const rs = byCode.get(code) ?? [];
    const m = meta[code];
    const ys = Object.fromEntries(rs.map(r => [r.year, r]));
    const latest = [...rs].sort((a, b) => b.year.localeCompare(a.year))[0];
    const name = (latest?.name || m?.name || code).replace(/\s+/g, ' ').trim();
    const ksic = latest?.induty_code || m?.induty_code || '';
    const co = coByName.get(normName(name));
    return {
      code, name, cls: latest?.corp_cls || CLS_NAME[m?.corp_cls ?? ''] || '', stock: latest?.stock_code || m?.stock_code || '',
      district: (latest?.region || m?.region || '').split(' ')[1] ?? '', ksic,
      group: classify(ksic, '', ''), years: ys, latest, companyId: co?.id ?? null,
      ksicName: ksicNames.get(ksic) ?? '', factoryProduct: (co?.product ?? '').trim(),
      url: latest?.source_url || `https://dart.fss.or.kr/dsab007/main.do?option=corp&textCrpNm=${encodeURIComponent(name)}`,
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
/** 기업 페이지 1만여 곳이 빌드 때 같은 CSV 를 부르므로 한 번만 읽는다 */
const memo = <T,>(f: () => T) => { let v: T | undefined; return () => (v ??= f()); };
export const futureDisclosures = memo(() => readCsv('data/dart/future.csv') as FutureDisclosure[]);
export const ymd = (s: string) => (s && s.length === 8 ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6)}` : s);

/** 직원 현황(scripts/collect_dart_emp.py → scripts/data/company_employees.csv): 사업보고서 '직원 등의 현황' 회사 단위 집계.
 *  직원 수·정규직·기간제·남녀·평균 근속연수 값 그대로, 1인 평균 급여는 연간 급여 총액 ÷ 직원 수(avg_method). 순위·평가 없음. */
export type DartEmployee = { corp_code: string; name: string; year: string; employees: string; regular: string; contract: string; male: string; female: string;
  avg_tenure: string; salary_total: string; avg_salary: string; avg_salary_reported: string; avg_method: string; unit_note: string; rcept_no: string; source_url: string; as_of: string };
export const dartEmployees = memo(() => readCsv('scripts/data/company_employees.csv') as DartEmployee[]);
/** 반기보고서 직원 현황(collect_dart_emp.py --half → company_employees_half.csv, 운영자 지시 2026-10-19 '직원 현황도 반기보고서로 업데이트해'):
 *  6월 말 직원 수·정규직·기간제·남녀·평균 근속, 급여 총액·1인 평균 급여는 1~6월 누적이라 연간 값과 견주지 않는다 */
export const dartEmpHalf = memo(() => readCsv('scripts/data/company_employees_half.csv') as DartEmployee[]);
export const empHalfByCode = (code: string) => dartEmpHalf().find(e => e.corp_code === code);
export const employeesOf = (name: string) => dartEmployees().filter(e => normName(e.name) === normName(name)).sort((a, b) => b.year.localeCompare(a.year));
/** 숫자 칸 → 표시(빈칸·0 은 —) */
export const n0 = (s?: string) => { const v = Number(s); return s && Number.isFinite(v) && v !== 0 ? Math.round(v).toLocaleString('ko-KR') : '—'; };
export const mil = (s?: string) => { const v = Number(s); return s && Number.isFinite(v) && v > 0 ? (v / 1e6).toLocaleString('ko-KR', { maximumFractionDigits: 0 }) : '—'; };

/** 연구개발비(scripts/collect_dart_extra.py → scripts/data/company_rnd.csv): 사업보고서 원문 '연구개발 활동' 표의 연구개발비용 계(원으로 환산)와
 *  매출액 대비 비율(공시 값). 표를 못 찾은 회사는 없다. 비율이 50% 를 넘는 값은 표 읽기 오류로 보고 비운다. */
export type DartRnd = { corp_code: string; name: string; report_year: string; year: string; rnd_won: string; ratio_pct: string; unit: string; source_url: string };
export const dartRnd = memo(() => (readCsv('scripts/data/company_rnd.csv') as DartRnd[]).map(r => ({ ...r, ratio_pct: Number(r.ratio_pct) > 50 ? '' : r.ratio_pct })));
export const rndOf = (name: string) => dartRnd().filter(r => normName(r.name) === normName(name)).sort((a, b) => b.year.localeCompare(a.year));

/** 타법인 출자 현황(scripts/data/company_investments.csv): 사업보고서 '타법인 출자 현황'. 장부가액 등 금액은 공시 표 단위가 회사마다 달라 페이지에 싣지 않고
 *  피출자 법인·출자 목적(공시 문구를 경영참여·사업 관련·단순·일반투자·조합 출자·지분 취득·출자로 묶음)·최초 취득일·기말 지분율만. */
export type DartInvest = { corp_code: string; name: string; year: string; inv_name: string; purpose: string; first_acq_date: string; end_share_pct: string; source_url: string };
export const purposeOf = (p: string) => {
  const t = (p || '').replace(/\s+/g, '');
  if (!t) return '미기재';
  if (/경영|종속/.test(t)) return '경영참여';
  if (/조합/.test(t)) return '조합 출자';
  if (/사업|전략|협력|관계|시장|진출|거점|점유율|생산|개발|마케팅|경쟁력|운영|제조|연구|업$|업등/.test(t)) return '사업 관련';
  if (/단순|일반|투자/.test(t)) return '단순·일반투자';
  if (/지분|증자|출자|주식|분할|전환/.test(t)) return '지분 취득·출자';
  return '기타';
};
export const dartInvest = memo(() => readCsv('scripts/data/company_investments.csv') as DartInvest[]);
export const investOf = (name: string) => dartInvest().filter(r => normName(r.name) === normName(name)).sort((a, b) => (Number(b.end_share_pct) || 0) - (Number(a.end_share_pct) || 0));

/** 회사 코드(corp_code)로 고르기 — 상장기업 상세 페이지(/listed/<code>/) */
export const empByCode = (code: string) => dartEmployees().filter(e => e.corp_code === code).sort((a, b) => b.year.localeCompare(a.year));
export const rndByCode = (code: string) => dartRnd().filter(r => r.corp_code === code).sort((a, b) => b.year.localeCompare(a.year));
export const invByCode = (code: string) => dartInvest().filter(r => r.corp_code === code).sort((a, b) => (Number(b.end_share_pct) || 0) - (Number(a.end_share_pct) || 0));
export const futByCode = (code: string) => futureDisclosures().filter(d => d.corp_code === code).sort((a, b) => b.rcept_dt.localeCompare(a.rcept_dt));

/** 주요 제품(scripts/collect_dart_extra.py → scripts/data/company_products.csv): 사업보고서 '주요 제품(및 서비스)' 표의 사업부문·품목·용도·매출 비율 — 표 글자 그대로 */
export type DartProduct = { corp_code: string; name: string; year: string; segment: string; product: string; use: string; share_pct: string; source_url: string };
/** 표 머리 글자(품목·제품명)·합계·문장처럼 품목이 아닌 행은 뺀다(collect_dart_extra.good_product 와 같은 규칙) */
const BAD_PROD = /^(합\s*계|총\s*계|소\s*계|계|단순합계|매출\s*총계|총\s*매\s*출.*|차감.*|품\s*목.*|제\s*품\s*명|주\s*요\s*제\s*품.*|구\s*분|사\s*업\s*부\s*문|부\s*문|제\s*품|상\s*품|용\s*역|기\s*타|매출\s*액)$/;
const okProduct = (p: DartProduct) => { const t = p.product.trim(); return !!t && t.length <= 60 && !BAD_PROD.test(t) && !/품\s*목|제\s*품\s*명|주\s*요\s*제\s*품|구체적\s*용도/.test(t) && !BAD_PROD.test((p.segment || 'x').trim())
  && !/^[\d,.\s%()-]+$/.test(t) && !t.startsWith('-') && !t.endsWith('.') && !/(습니다|입니다|있음|진행\s*중)/.test(t); };
export const dartProducts = memo(() => (readCsv('scripts/data/company_products.csv') as DartProduct[]).filter(okProduct));
export const productsByCode = (code: string) => dartProducts().filter(p => p.corp_code === code);
/** 목록에 쓰는 '무엇을 만드나' 한 줄: 사업보고서 품목(매출 비율 큰 순 3개) → 없으면 공장등록 생산품. 출처 표시용 kind 를 함께 */
export function makesOf(c: DartCorp): { text: string; kind: 'dart' | 'factory' | '' } {
  const ps = productsByCode(c.code);
  if (ps.length) {
    const sorted = [...ps].sort((a, b) => (Number(b.share_pct) || 0) - (Number(a.share_pct) || 0));
    const names = [...new Set(sorted.map(p => p.product.replace(/\s+/g, ' ').trim()))].slice(0, 3);
    return { text: names.join(' · ') + (new Set(ps.map(p => p.product)).size > 3 ? ' 등' : ''), kind: 'dart' };
  }
  if (c.factoryProduct) { const t = c.factoryProduct.replace(/\s+/g, ' '); const cut = t.length > 50 ? t.slice(0, 50).replace(/[,\s]+[^,\s]*$/, '').replace(/\s*등$/, '') + ' 등' : t; return { text: cut, kind: 'factory' }; }
  return { text: '', kind: '' };
}

/** 분기 실적(scripts/collect_dart_qtr.py → scripts/data/company_financials_q.csv, 운영자 지시 2026-10-12): 대구 본사 유가증권·코스닥 상장회사의
 *  분기·반기·사업보고서 주요계정(연결 우선). 1~3분기는 공시된 3개월 값, 4분기는 '연간 − 3분기 누적'(derived=1, 이 사이트 계산).
 *  *_prev 는 같은 보고서의 전년 같은 분기 값(공시). 순위·평가 없음. */
export type DartQuarter = { corp_code: string; name: string; corp_cls: string; stock_code: string; year: string; quarter: string; fs: string;
  revenue: string; operating_income: string; net_income: string; revenue_cum: string; operating_income_cum: string; net_income_cum: string;
  revenue_prev: string; operating_income_prev: string; net_income_prev: string;
  /** 분기 말 재무상태(자산·부채·자본총계)와 같은 보고서의 비교 시점 값(*_prev: 분기·반기는 전기말) — 2026-10-19 부터 받음, 그 전 행은 빈 칸 */
  total_assets?: string; total_liabilities?: string; total_equity?: string; total_assets_prev?: string; total_liabilities_prev?: string; total_equity_prev?: string;
  derived: string; unit: string; rcept_no: string; source_url: string; as_of: string };
export const dartQuarters = memo(() => readCsv('scripts/data/company_financials_q.csv') as DartQuarter[]);
export const qKey = (q: Pick<DartQuarter, 'year' | 'quarter'>) => `${q.year}-${q.quarter}`;
export const qLabel = (k: string) => { const [y, q] = k.split('-'); return `${y.slice(2)}.${q}Q`; };
export const qByCode = (code: string) => dartQuarters().filter(q => q.corp_code === code).sort((a, b) => qKey(a).localeCompare(qKey(b)));
/** 전년 같은 분기 값: 1~3분기는 공시 행의 *_prev, 4분기는 전년 4분기 행(같은 연결·개별 기준일 때만) */
export const qPrev = (q: DartQuarter, col: 'revenue' | 'operating_income' | 'net_income') => {
  if (q.quarter !== '4') return q[`${col}_prev`];
  const p = dartQuarters().find(x => x.corp_code === q.corp_code && x.quarter === '4' && Number(x.year) === Number(q.year) - 1 && x.fs === q.fs);
  return p?.[col] ?? '';
};
/** 상반기(반기보고서) 재무(운영자 지시 2026-10-19 '대구시 상장기업들 올해 상반기 재무제표 업데이트해'): 가장 최근 반기(2분기 행)의 누적 손익과
 *  6월 말 재무상태, 전년 상반기 누적(전년 2분기 행, 같은 연결·개별 기준일 때만), 반기보고서의 전기말 재무상태. 값은 공시 그대로, 나눗셈만 이 사이트 계산 */
export type HalfRow = { code: string; name: string; cls: string; fs: string; cur: DartQuarter; prev?: DartQuarter };
export function halfYear(codes?: Set<string>): { year: string; rows: HalfRow[] } {
  const qs = dartQuarters().filter(q => q.quarter === '2' && (!codes || codes.has(q.corp_code)));
  const year = qs.map(q => q.year).sort().at(-1) ?? '';
  const rows = qs.filter(q => q.year === year).map(cur => {
    const prev = qs.find(q => q.corp_code === cur.corp_code && Number(q.year) === Number(year) - 1 && q.fs === cur.fs);
    return { code: cur.corp_code, name: cur.name, cls: cur.corp_cls, fs: cur.fs, cur, prev };
  }).sort((a, b) => a.name.localeCompare(b.name, 'ko'));
  return { year, rows };
}
/** 두 원 단위 값의 증감률(%) — 둘 다 0 보다 클 때만 */
export const growth = (a?: string, b?: string) => { const x = Number(a), y = Number(b); return a && b && x > 0 && y > 0 ? (x / y - 1) * 100 : null; };
/** 부채비율(%) = 부채 ÷ 자본 × 100, 자본이 0 이하면 null */
export const ratio = (l?: string, e?: string) => { const x = Number(l), y = Number(e); return l && e && y > 0 && Number.isFinite(x) ? (x / y) * 100 : null; };
/** 매출액 전년 같은 분기 대비 증감률(%) — 두 값이 모두 0 보다 클 때만 */
export const qYoY = (q?: DartQuarter) => { if (!q) return null; const a = Number(q.revenue), b = Number(qPrev(q, 'revenue')); return q.revenue && b > 0 && a > 0 ? (a / b - 1) * 100 : null; };

/** 영업(잠정)실적 공시의 분기 숫자(collect_dart_qtr.py 가 공시 원문 표에서 읽음 → data/dart/prelim.csv, 운영자 지시 2026-10-20
 *  '3분기 실적 발표한 기업과 안한 기업 조사하고 발표한 기업은 반영해'). 값은 공시 단위(대개 백만 원)를 원으로 바꾼 것 — 잠정치라 분기보고서와 다를 수 있다. */
export type DartPrelim = { rcept_dt: string; corp_code: string; name: string; year: string; quarter: string; fs: string;
  revenue: string; operating_income: string; net_income: string; revenue_prev: string; operating_income_prev: string; net_income_prev: string;
  revenue_cum: string; operating_income_cum: string; net_income_cum: string; unit_note: string; report_nm: string; rcept_no: string; url: string };
export const dartPrelim = memo(() => readCsv('data/dart/prelim.csv') as DartPrelim[]);
const Q_END: Record<number, [number, number]> = { 1: [3, 31], 2: [6, 30], 3: [9, 30], 4: [12, 31] };
/** 분기 보고서 제출 마감(분기·반기 45일, 사업보고서 90일 — 자본시장법 제159·160조) */
export const qDue = (y: number, q: number) => { const [m, d] = Q_END[q]; const t = new Date(Date.UTC(y, m - 1, d)); t.setUTCDate(t.getUTCDate() + (q === 4 ? 90 : 45)); return t; };
/** 빌드 날 기준 가장 최근에 끝난 분기 */
export function lastEndedQuarter(today = new Date()): { year: number; quarter: number } {
  for (let y = today.getUTCFullYear(); y >= today.getUTCFullYear() - 1; y--)
    for (const q of [4, 3, 2, 1]) { const [m, d] = Q_END[q]; if (Date.UTC(y, m - 1, d) < today.getTime()) return { year: y, quarter: q }; }
  return { year: today.getUTCFullYear() - 1, quarter: 4 };
}
export type QStatusRow = { code: string; name: string; cls: string; state: '보고서' | '잠정실적' | '아직'; date: string; fs: string; offFy?: boolean;
  revenue: string; revenue_prev: string; op: string; op_prev: string; net: string; url: string; report_nm: string; prelim?: DartPrelim };
/** 그 분기 실적 발표 현황: 분기·반기·사업보고서가 있으면 '보고서', 없고 잠정실적 공시가 있으면 '잠정실적', 둘 다 없으면 '아직'(마감 전이면 낼 차례) */
export function quarterStatus(corps: { code: string; name: string; cls: string }[], year: number, quarter: number): QStatusRow[] {
  const qs = dartQuarters(), pre = dartPrelim();
  return corps.filter(c => c.cls === '유가증권' || c.cls === '코스닥').map(c => {
    // 분기 끝 전에 낸 보고서는 결산월이 12월이 아닌 회사의 사업연도 분기라 달력 분기로 보지 않는다(예: 세원정공 6월 결산)
    const end = `${year}${String(Q_END[quarter][0]).padStart(2, '0')}${Q_END[quarter][1]}`;
    const r = qs.find(q => q.corp_code === c.code && Number(q.year) === year && Number(q.quarter) === quarter && q.rcept_no.slice(0, 8) > end);
    const p = pre.filter(x => x.corp_code === c.code && Number(x.year) === year && Number(x.quarter) === quarter)
      .sort((a, b) => (a.fs === '연결' ? 0 : 1) - (b.fs === '연결' ? 0 : 1) || b.rcept_no.localeCompare(a.rcept_no))[0];
    if (r) return { code: c.code, name: c.name, cls: c.cls, state: '보고서' as const, date: r.rcept_no.slice(0, 8), fs: r.fs, revenue: r.revenue, revenue_prev: qPrev(r, 'revenue'),
      op: r.operating_income, op_prev: qPrev(r, 'operating_income'), net: r.net_income, url: r.source_url, report_nm: quarter === 4 ? '사업보고서' : quarter === 2 ? '반기보고서' : '분기보고서', prelim: p };
    if (p) return { code: c.code, name: c.name, cls: c.cls, state: '잠정실적' as const, date: p.rcept_dt, fs: p.fs, revenue: p.revenue, revenue_prev: p.revenue_prev,
      op: p.operating_income, op_prev: p.operating_income_prev, net: p.net_income, url: p.url, report_nm: p.report_nm, prelim: p };
    // 1~3분기 보고서가 그 달력 분기 끝보다 먼저 접수됐으면 결산월이 12월이 아닌 회사(사업보고서는 정정본 접수일이 늦을 수 있어 보지 않음)
    const offFy = qs.some(q => q.corp_code === c.code && q.quarter !== '4' && q.rcept_no.slice(0, 8) <= `${q.year}${String(Q_END[Number(q.quarter)][0]).padStart(2, '0')}${Q_END[Number(q.quarter)][1]}`);
    return { code: c.code, name: c.name, cls: c.cls, state: '아직' as const, offFy, date: '', fs: '', revenue: '', revenue_prev: '', op: '', op_prev: '', net: '', url: '', report_nm: '' };
  }).sort((a, b) => a.name.localeCompare(b.name, 'ko'));
}

/** 실적 관련 공시(data/dart/performance.csv): 영업(잠정)실적 · 매출액 또는 손익구조 30%(대규모법인 15%) 이상 변동(공시된 주요원인 문구) ·
 *  영업실적 등에 대한 전망(공정공시). excerpt 는 회사가 공시한 문구 그대로(120자 안). 해석·평가 없음. */
export type DartPerf = { rcept_dt: string; corp_code: string; name: string; kind: string; report_nm: string; excerpt: string; rcept_no: string; url: string };
export const dartPerf = memo(() => readCsv('data/dart/performance.csv') as DartPerf[]);
export const perfByCode = (code: string) => dartPerf().filter(p => p.corp_code === code).sort((a, b) => b.rcept_dt.localeCompare(a.rcept_dt));

/** 경영진 진단·방향(scripts/collect_dart_mgmt.py → data/dart/mgmt.csv, 운영자 지시 2026-10-12): 최근 사업보고서 '이사의 경영진단 및 분석의견'의
 *  개요(overview)·전망·계획 문장(outlook)과 사업의 내용·경영진단에서 신규사업·진출 낱말이 든 문장(new_biz) — 회사 공시 문구 그대로(220자 안), 이 사이트의 요약·평가 아님 */
export type DartMgmt = { corp_code: string; name: string; report_year: string; rcept_dt: string; overview: string; outlook: string; new_biz: string; rcept_no: string; url: string };
export const dartMgmt = memo(() => readCsv('data/dart/mgmt.csv') as DartMgmt[]);
export const mgmtByCode = (code: string) => dartMgmt().find(m => m.corp_code === code);

/** 실적 이유·전망 문구(scripts/collect_dart_notes.py, 운영자 지시 2026-10-12 '실적이유와 가이던스 — 1 2 다해봐'):
 *  ① data/dart/report_notes.csv — 정기보고서 본문(경영진단·사업의 내용)에서 실적 낱말+증감+원인(이유) 또는 시점+전망 표현(전망)이 든 문장.
 *     mdna = 경영진단 장이 '있음'·'생략'(분기보고서는 생략 많음)·'없음'. 문장 없는 보고서는 kind 가 빈 행 하나.
 *  ② data/dart/ir.csv — 기업설명회(IR) 공시의 목적·내용 구절과 첨부 IR 자료 PDF 의 전망·목표 낱말 줄(guidance, ' / ' 로 이음).
 *  모두 회사 문구 그대로(낱말 규칙으로 고른 것)이며 해석·평가 없음. */
export type DartNote = { corp_code: string; name: string; year: string; quarter: string; report_nm: string; mdna: string; kind: string; section: string; sentence: string; rcept_no: string; url: string; as_of: string };
export const dartNotes = memo(() => readCsv('data/dart/report_notes.csv') as DartNote[]);
export const notesByCode = (code: string) => dartNotes().filter(n => n.corp_code === code && n.kind);
export type DartIR = { rcept_dt: string; corp_code: string; name: string; report_nm: string; purpose: string; content: string; posted: string; ir_page: string; pdf: string; guidance: string; rcept_no: string; url: string; att_url: string; as_of: string };
export const dartIR = memo(() => readCsv('data/dart/ir.csv') as DartIR[]);
export const irByCode = (code: string) => dartIR().filter(r => r.corp_code === code).sort((a, b) => b.rcept_dt.localeCompare(a.rcept_dt));
