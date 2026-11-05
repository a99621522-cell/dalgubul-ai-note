import fs from 'node:fs';
/** 조달청 나라장터 계약정보(data/vat/contracts/<gov>.json, scripts/fetch_g2b_contracts.py) → /vat-expense/contracts-<gov>.json.
 *  '지난 돈 돌려받기' 공개 지출 자료 탭의 '나라장터 계약' 표 — 받아 올 세금계산서를 계약(업체·등록번호) 단위로 적는다(운영자 2026-11-05 '조달청 api 연결 → 그렇게해').
 *  계약금액은 지출액과 겹쳐 공제 추정에 더하지 않는다. 담당자·대표자 이름은 수집 단계에서 저장하지 않는다. */
export type Corp = { nm: string; no: string; sh?: string };
export type Contract = { k: '공사' | '용역' | '물품'; no: string; nm: string; inst: string; dept: string; dmn: string[]; date: string; tot: number; amt: number; mth: string; lng: string; cls: string; corps: Corp[]; url: string };
export type ContractGov = { v: 1; key: string; name: string; fetched: string; from: string; to: string; source: string; note: string; rows: Contract[] };
const DIR = 'data/vat/contracts';
/** 같은 원계약번호(상세 주소의 ctrtNo)는 마지막 변경(ctrtChgOrd·변경일시) 한 줄만, 계약일은 처음 계약일 — 수집 스크립트 latest_by_contract 와 같은 규칙.
 *  변경계약마다 통합계약번호가 새로 붙어 같은 계약이 여러 줄이 되던 것(2026-11-05 달성군 25,319줄 → 12,176건). */
export function latestByContract<T extends { no: string; k: string; nm: string; date: string; url: string; chg?: string }>(rows: T[]): T[] {
  const id = (r: T) => { const m = /ctrtNo=([^&]+)/.exec(r.url), o = /ctrtChgOrd=([^&]+)/.exec(r.url); return [m?.[1] || r.no || `${r.k}|${r.nm}|${r.date}`, o?.[1] ?? ''] as const; };
  const best = new Map<string, T>(), first = new Map<string, string>();
  for (const r of rows) { const [k, o] = id(r); const cur = best.get(k); if (!cur || `${o}|${r.chg ?? ''}` > `${id(cur)[1]}|${cur.chg ?? ''}`) best.set(k, r); if (r.date && (!first.has(k) || r.date < first.get(k)!)) first.set(k, r.date); }
  return [...best.entries()].map(([k, r]) => ({ ...r, date: first.get(k) ?? r.date }));
}
let cache: ContractGov[] | null = null;
export function vatContractGovs(): ContractGov[] {
  if (cache) return cache;
  if (!fs.existsSync(DIR)) return (cache = []);
  return (cache = fs.readdirSync(DIR).filter(f => f.endsWith('.json') && f !== 'state.json').map(f => { try { return JSON.parse(fs.readFileSync(`${DIR}/${f}`, 'utf-8')) as ContractGov; } catch { return null; } })
    .filter((g): g is ContractGov => !!g && g.v === 1 && Array.isArray(g.rows))
    .map(g => ({ ...g, rows: latestByContract(g.rows).map(({ chg, prd, bgn, end, ...r }: Contract & { chg?: string; prd?: string; bgn?: string; end?: string }) => r) })));   // 변경일시(수집 때 병합용)·계약기간은 화면에 안 보냄 — 파일을 줄인다
}
