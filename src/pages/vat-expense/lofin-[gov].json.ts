import type { APIRoute, GetStaticPaths } from 'astro';
import { vatLofinGovs } from '../../lib/vatLofinBiz';
/** 지자체 하나의 지방재정365 세부사업별 연간 지출액(2021~) — 돌려받기 '공개 지출 자료'의 2024년 이후 몫 */
export const getStaticPaths: GetStaticPaths = () => vatLofinGovs().map(g => ({ params: { gov: g.key } }));
export const GET: APIRoute = ({ params }) => new Response(JSON.stringify(vatLofinGovs().find(x => x.key === params.gov) ?? {}), { headers: { 'content-type': 'application/json; charset=utf-8' } });
