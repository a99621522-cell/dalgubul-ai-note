import fs from 'node:fs';
/** 대구 공개 지출 자료 집계(data/vat/expense/<gov>.json, scripts/fetch_daegu_expense.py) → /vat-expense/index.json·/vat-expense/<gov>.json.
 *  지자체 부가세 절감 점검기 '공개 지출 자료로 후보 찾기'(운영자 2026-11-03 '홈택스 붙여넣는 것은 공무원이 안 할 것 같은데 방법을 찾아봐'). 값 그대로, 세액 없음(화면이 통계목 성격으로 추정) */
export type ExpAgg = { p: string; acct: string; dept: string; biz: string; mok: string; n: number; amt: number; card: number; petty: number; max: number; memo: string[] };
export type ExpGov = { v: 1; key: string; code: string; name: string; source: string; fetched: string; years: string[]; periods: string[]; days: string[]; failed_days: string[]; note: string; rows: ExpAgg[] };
const DIR = 'data/vat/expense';
let cache: ExpGov[] | null = null;
export function vatExpenseGovs(): ExpGov[] {
  if (cache) return cache;
  if (!fs.existsSync(DIR)) return (cache = []);
  const order = ['daegu', 'jung', 'dong', 'seo', 'nam', 'buk', 'suseong', 'dalseo', 'dalseong', 'gunwi'];
  const out = fs.readdirSync(DIR).filter(f => f.endsWith('.json') && f !== 'index.json').map(f => JSON.parse(fs.readFileSync(`${DIR}/${f}`, 'utf-8')) as ExpGov).filter(g => g && g.v === 1 && Array.isArray(g.rows));
  out.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
  return (cache = out);
}
/** 목록(행 없이): 지자체 선택 상자용 */
export const vatExpenseIndex = () => vatExpenseGovs().map(g => ({ key: g.key, code: g.code, name: g.name, fetched: g.fetched, years: g.years, periods: g.periods, days: g.days.length, failed: g.failed_days.length, rows: g.rows.length, note: g.note, source: g.source }));
