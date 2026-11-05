import fs from 'node:fs';
/** 조달청 나라장터 계약정보(data/vat/contracts/<gov>.json, scripts/fetch_g2b_contracts.py) → /vat-expense/contracts-<gov>.json.
 *  '지난 돈 돌려받기' 공개 지출 자료 탭의 '나라장터 계약' 표 — 받아 올 세금계산서를 계약(업체·등록번호) 단위로 적는다(운영자 2026-11-05 '조달청 api 연결 → 그렇게해').
 *  계약금액은 지출액과 겹쳐 공제 추정에 더하지 않는다. 담당자·대표자 이름은 수집 단계에서 저장하지 않는다. */
export type Corp = { nm: string; no: string; sh?: string };
export type Contract = { k: '공사' | '용역' | '물품'; no: string; nm: string; inst: string; dept: string; dmn: string[]; date: string; prd: string; tot: number; amt: number; mth: string; lng: string; cls: string; corps: Corp[]; url: string; bgn: string; end: string };
export type ContractGov = { v: 1; key: string; name: string; fetched: string; from: string; to: string; source: string; note: string; rows: Contract[] };
const DIR = 'data/vat/contracts';
let cache: ContractGov[] | null = null;
export function vatContractGovs(): ContractGov[] {
  if (cache) return cache;
  if (!fs.existsSync(DIR)) return (cache = []);
  return (cache = fs.readdirSync(DIR).filter(f => f.endsWith('.json') && f !== 'state.json').map(f => { try { return JSON.parse(fs.readFileSync(`${DIR}/${f}`, 'utf-8')) as ContractGov; } catch { return null; } })
    .filter((g): g is ContractGov => !!g && g.v === 1 && Array.isArray(g.rows))
    .map(g => ({ ...g, rows: g.rows.map(({ chg, ...r }: Contract & { chg?: string }) => r) })));   // chg(변경일시)는 수집 때 병합용 — 화면에 안 보냄
}
