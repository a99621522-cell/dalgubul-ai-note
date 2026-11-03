/** 대구 비상장 외감·상장 제조업 재무 묶음 통계와 전국 비교(운영자 지시 2026-11-03 '대구 비상장 재무 현황표 조사해봐' → '전국과 비교하는 것도 구현해야지').
 *  scripts/audit_compare.py 가 만든 data/dart/audit_compare.json 만 읽는다(계산은 Python 한 곳 — 화면은 옮기기만).
 *  회사 이름·순위는 없다. 기업 수 5곳 미만 칸은 값이 비어 있다. */
import fs from 'node:fs';
import path from 'node:path';

export interface Cell { n: number; med?: number; q1?: number; q3?: number; ci?: [number, number]; pooled?: number | null }
export interface Scope { n: number; [key: string]: Cell | number }
export interface Row4 { daegu_listed: Scope; national_listed: Scope; daegu_unlisted: Scope; national_unlisted: Scope }
export interface BokCell { med?: number; q1?: number; q3?: number; mean?: number; name?: string }
export interface AuditCompare {
  updated: string; min_n: number;
  indicators: { key: string; name: string; unit: string }[];
  years: { daegu_unlisted: string; listed: string; national_unlisted: string };
  total: Row4;
  by_group: (Row4 & { group: string })[];
  by_ksic: (Row4 & { code: string; name: string; bok: Record<string, BokCell> })[];
  by_district: { district: string; daegu_unlisted: Scope }[];
  bok: { year?: string; table?: string; by?: Record<string, BokCell> };
  bok_year_ksic?: string;
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
