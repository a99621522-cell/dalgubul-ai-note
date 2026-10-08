import fs from 'node:fs';
import yaml from 'js-yaml';
/** 대구시가 출자·조성한 창업·벤처 펀드(data/funds/daegu_funds.yml, 운영자 지시 2026-10-08). 값 그대로, 평가 없음. */
export type Src = { title: string; url: string; date: string; press?: boolean };
/** 사이트에 보이는 출처만(기관 게시·사업개요). 언론 보도(press)는 조사 기록으로만 두고 매체 이름·링크를 싣지 않는다(운영자 지시 2026-10-08). */
export const publicSrc = (a?: Src[]) => (a ?? []).filter(s => !s.press);
export type Plan = { name: string; status: string; size: string; contributors?: string; target: string; note?: string; sources: Src[] };
export type Regional = { name: string; size_eok: number; gp: string; target: string; contact?: string; formed?: string; sources?: Src[] };
export type CityFund = { name: string; gp: string; target: string; ticket: string; formed?: string; sources?: Src[] };
export type Funds = { as_of: string; dash: { city: string; regional: string }; plans: Plan[]; plans_note: string; regional: Regional[]; city: CityFund[]; city_note: string };
let cache: Funds | null = null;
export function daeguFunds(): Funds | null {
  if (cache) return cache;
  const p = 'data/funds/daegu_funds.yml';
  if (!fs.existsSync(p)) return null;
  cache = yaml.load(fs.readFileSync(p, 'utf-8')) as Funds;
  return cache;
}
