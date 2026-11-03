/** 대구 비상장 외감·상장 제조업 재무 묶음 통계와 전국 비교(운영자 지시 2026-11-03 '대구 비상장 재무 현황표 조사해봐' → '전국과 비교하는 것도 구현해야지').
 *  scripts/audit_compare.py 가 만든 data/dart/audit_compare.json 만 읽는다(계산은 Python 한 곳 — 화면은 옮기기만).
 *  회사 이름·순위는 없다. 기업 수 5곳 미만 칸은 값이 비어 있다. */
import fs from 'node:fs';
import path from 'node:path';
import { halfYear, dartQuarters, lastEndedQuarter, type DartQuarter } from './dart';
import { monthlySeries, latest, change, industryRows, type Series } from './monthly';

export interface Cell { n: number; med?: number; q1?: number; q3?: number; ci?: [number, number]; pooled?: number | null }
export interface IcrLow { n: number; k: number | null; share: number | null; n3: number; share3: number | null }
export interface Scope { n: number; icr_low?: IcrLow; [key: string]: Cell | number | IcrLow | undefined }
export interface Row4 { daegu_listed: Scope; national_listed: Scope; daegu_unlisted: Scope; national_unlisted: Scope }
export interface BokCell { med?: number; q1?: number; q3?: number; mean?: number; name?: string }
export interface EmpStat { n: number; n_both: number; med?: number; sum?: number; chg?: number | null; up?: number; down?: number }
export interface AuditCompare {
  updated: string; min_n: number;
  indicators: { key: string; name: string; unit: string }[];
  years: { daegu_unlisted: string; listed: string; national_unlisted: string };
  total: Row4;
  by_group: (Row4 & { group: string })[];
  by_ksic: (Row4 & { code: string; name?: string; bok: Record<string, BokCell>; bok_region?: Record<string, number> })[];
  by_district: { district: string; daegu_unlisted: Scope }[];
  bok: { year?: string; table?: string; by?: Record<string, BokCell> };
  bok_year_ksic?: string;
  min_share?: number; bands?: string[];
  by_band?: (Row4 & { band: string })[];
  trend?: Record<string, { years: string[]; all: Record<string, Scope>; same: Record<string, Scope>; same_n: number }>;
  employment?: { months: { last?: string; prev?: string; matched?: number }; total: EmpStat; by_band: (EmpStat & { band: string })[]; by_ksic: (EmpStat & { code: string })[] };
  bok_region?: { year?: string; table?: string; by_scale?: Record<string, Record<string, number>>; by_ksic?: Record<string, Record<string, number>>; sales?: Record<string, { value: number; unit: string }> };
  coverage?: { year: string; bok_sales_won: number; unlisted_sales_won: number; listed_sales_won: number; unlisted_n: number; listed_n: number; unlisted_share: number | null; listed_share: number | null };
  sample: { population?: number; seed?: number; looked?: number; cap_per_group?: number; rows?: number; filings_since?: string; note?: string };
  summary: { daegu?: { filers: number; name_matched: number; daegu: number; daegu_mfg: number; rows: number; filings_since?: string; updated?: string }; listed?: { year: string; target: number; rows: number } };
}

let memo: AuditCompare | null | undefined;
export function auditCompare(): AuditCompare | null {
  if (memo !== undefined) return memo;
  const p = path.resolve('data/dart/audit_compare.json');
  memo = fs.existsSync(p) ? (JSON.parse(fs.readFileSync(p, 'utf-8')) as AuditCompare) : null;
  return memo;
}

export const cell = (s: Scope | undefined, key: string): Cell | undefined => (s ? (s[key] as Cell | undefined) : undefined);
export const f1 = (v: number | null | undefined) => (v == null || !Number.isFinite(v) ? '—' : v.toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
/** 차이(대구 − 전국, %p). 둘 다 있을 때만 */
export function diff(a?: number, b?: number): string {
  if (a == null || b == null) return '—';
  const d = Math.round((a - b) * 10) / 10;
  return `${d > 0 ? '+' : ''}${d.toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`;
}
/** 대구 중앙값이 전국 표본 중앙값의 부트스트랩 95% 범위 안인지 */
export const inRange = (v?: number, ci?: [number, number]) => v != null && !!ci && v >= ci[0] && v <= ci[1];

/** KSIC 10차·11차 제조업 중분류 짧은 이름(그림·표 머리용) */
export const KSIC2: Record<string, string> = {
  C10: '식료품', C11: '음료', C12: '담배', C13: '섬유제품', C14: '의복', C15: '가죽·신발', C16: '목재', C17: '펄프·종이',
  C18: '인쇄', C19: '석유정제', C20: '화학', C21: '의약품', C22: '고무·플라스틱', C23: '비금속광물', C24: '1차 금속',
  C25: '금속가공', C26: '전자부품·통신', C27: '의료·정밀·광학', C28: '전기장비', C29: '기타 기계', C30: '자동차·트레일러',
  C31: '기타 운송장비', C32: '가구', C33: '기타 제품', C34: '산업용 기계 수리',
};
export const ksicName = (code: string) => `${code} ${KSIC2[code] ?? ''}`.trim();

export const ym = (m?: string) => (m && m.length === 6 ? `${m.slice(0, 4)}년 ${Number(m.slice(4))}월` : m ?? '');
export const eokJo = (won?: number) => (won == null ? '—' : won >= 1e12 ? `${(won / 1e12).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}조 원` : `${Math.round(won / 1e8).toLocaleString('ko-KR')}억 원`);

// ── 최근 신호(운영자 지시 2026-11-03 '2024년이 최신 값이야? 지금은 경제 상황이 많이 변했는데' → '그것도 넣어') ──
// 결산 재무(1년에 한 번) 옆에 이미 받고 있는 빠른 지표를 시점과 함께 둔다. 값은 각 출처 그대로, 해석 문장 없음.

const med = (xs: number[]) => { if (!xs.length) return null; const s = [...xs].sort((a, b) => a - b); const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
/** 대구 본사 유가증권·코스닥 제조업(기업개황 업종 10~34) 고유번호 */
function daeguListedMfg(): Set<string> {
  const p = path.resolve('scripts/state/dart_corp.json');
  if (!fs.existsSync(p)) return new Set();
  const m = JSON.parse(fs.readFileSync(p, 'utf-8')) as Record<string, { daegu?: boolean; corp_cls?: string; induty_code?: string }>;
  return new Set(Object.entries(m).filter(([, v]) => v.daegu && (v.corp_cls === 'Y' || v.corp_cls === 'K') && /^(1\d|2\d|3[0-4])/.test(v.induty_code ?? '')).map(([k]) => k));
}
export interface ListedSignal { label: string; period: string; n: number; growth: number | null; opm: number | null; opmPrev: number | null; up: number | null }
function sig(label: string, period: string, pairs: { cur: DartQuarter; prev?: DartQuarter }[], cum: boolean): ListedSignal {
  const rv = (q?: DartQuarter) => Number(cum ? q?.revenue_cum : q?.revenue), op = (q?: DartQuarter) => Number(cum ? q?.operating_income_cum : q?.operating_income);
  const g: number[] = [], o: number[] = [], op0: number[] = [];
  for (const { cur, prev } of pairs) {
    const a = rv(cur), b = rv(prev);
    if (a > 0 && b > 0) g.push((a / b - 1) * 100);
    if (a > 0 && Number.isFinite(op(cur))) o.push(op(cur) / a * 100);
    if (b > 0 && Number.isFinite(op(prev))) op0.push(op(prev) / b * 100);
  }
  return { label, period, n: pairs.length, growth: g.length >= 5 ? med(g) : null, opm: o.length >= 5 ? med(o) : null, opmPrev: op0.length >= 5 ? med(op0) : null,
    up: g.length >= 5 ? g.filter(x => x > 0).length / g.length * 100 : null };
}
export function recentSignals(): { listed: ListedSignal[]; monthly: { s: Series; m: string; v: number; yoy: number | null }[] } {
  const codes = daeguListedMfg();
  const listed: ListedSignal[] = [];
  const H = halfYear(codes);
  if (H.year) listed.push(sig('상반기(1~6월 누적)', `${H.year}년 상반기`, H.rows.filter(r => r.prev).map(r => ({ cur: r.cur, prev: r.prev })), true));
  const lq = lastEndedQuarter();
  for (const { year, quarter } of [lq, lq.quarter === 1 ? { year: lq.year - 1, quarter: 4 } : { year: lq.year, quarter: lq.quarter - 1 }]) {
    if (quarter === 4) continue;
    const qs = dartQuarters().filter(q => codes.has(q.corp_code));
    const cur = qs.filter(q => Number(q.year) === year && Number(q.quarter) === quarter);
    const pairs = cur.map(c => ({ cur: c, prev: qs.find(q => q.corp_code === c.corp_code && Number(q.year) === year - 1 && Number(q.quarter) === quarter && q.fs === c.fs) }));
    if (cur.length) { listed.push(sig(`${quarter}분기(3개월)`, `${year}년 ${quarter}분기`, pairs, false)); break; }
  }
  const want = ['ip', 'ship', 'mbsi', 'exp', 'cod', 'smed'];
  const S = monthlySeries();
  const monthly = want.map(k => S.find(s => s.key === k)).filter((s): s is Series => !!s && s.pts.length > 0)
    .map(s => { const p = latest(s); return { s, m: p.m, v: p.v, yoy: change(s, p, 12) }; });
  return { listed, monthly };
}

/** 업종별 최근 신호(운영자 지시 2026-11-03 '업종별로 나누어야되') — 업종(KSIC 중분류)마다 ① 대구 광공업 생산지수 전년 같은 달 대비(KOSIS, 월)
 *  ② 대구 상장 제조업 상반기 매출액 전년 대비 중앙값(회사 5곳 이상일 때) ③ 대구 비상장 외감 국민연금 가입자 합계 증감률(audit_compare.json). 출처·시점이 서로 달라 더하지 않는다. */
const IP_NAME: Record<string, string> = {
  C10: '식료품 제조업', C11: '음료 제조업', C13: '섬유제품 제조업; 의복 제외', C14: '의복 의복액세서리 및 모피제품 제조업', C17: '펄프 종이 및 종이제품 제조업',
  C18: '인쇄 및 기록매체 복제업', C20: '화학 물질 및 화학제품 제조업; 의약품 제외', C21: '의료용 물질 및 의약품 제조업', C22: '고무 및 플라스틱제품 제조업',
  C23: '비금속 광물제품 제조업', C24: '1차 금속 제조업', C25: '금속 가공제품 제조업; 기계 및 가구 제외', C26: '전자 부품 컴퓨터 영상 음향 및 통신장비 제조업',
  C27: '의료 정밀 광학 기기 및 시계 제조업', C28: '전기장비 제조업', C29: '기타 기계 및 장비 제조업', C30: '자동차 및 트레일러 제조업', C32: '가구 제조업', C33: '기타 제품 제조업',
};
export interface KsicSignal { code: string; ipMonth: string; ip: number | null; ipYoy: number | null; shYoy: number | null; half: string; halfN: number; halfGrowth: number | null; empN: number; empChg: number | null }
export function recentByKsic(): KsicSignal[] {
  const ind = industryRows();
  const byName = new Map(ind.rows.map(r => [r.name, r]));
  const p = path.resolve('scripts/state/dart_corp.json');
  const meta = fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf-8')) as Record<string, { induty_code?: string }> : {};
  const H = halfYear(daeguListedMfg());
  const halfBy = new Map<string, number[]>();
  const halfN = new Map<string, number>();
  for (const r of H.rows) {
    const code = 'C' + (meta[r.code]?.induty_code ?? '').slice(0, 2);
    halfN.set(code, (halfN.get(code) ?? 0) + 1);
    const a = Number(r.cur.revenue_cum), b = Number(r.prev?.revenue_cum);
    if (a > 0 && b > 0) halfBy.set(code, [...(halfBy.get(code) ?? []), (a / b - 1) * 100]);
  }
  const emp = new Map((auditCompare()?.employment?.by_ksic ?? []).map(e => [e.code, e]));
  const codes = [...new Set([...Object.keys(IP_NAME), ...halfN.keys(), ...emp.keys()])].filter(c => /^C\d\d$/.test(c)).sort();
  return codes.map(code => {
    const ip = byName.get(IP_NAME[code] ?? '');
    const g = halfBy.get(code) ?? [];
    const e = emp.get(code);
    return { code, ipMonth: ind.latest, ip: ip?.ip ?? null, ipYoy: ip?.ipYoy ?? null, shYoy: ip?.shYoy ?? null, half: H.year,
      halfN: halfN.get(code) ?? 0, halfGrowth: g.length >= 5 ? med(g) : null, empN: e?.n_both ?? 0, empChg: e?.chg ?? null };
  }).filter(r => r.ip != null || r.halfN > 0 || r.empN > 0);
}
