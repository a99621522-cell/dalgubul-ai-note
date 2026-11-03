import type { APIRoute, GetStaticPaths } from 'astro';
import { vatExpenseGovs } from '../../lib/vatExpense';
/** 지자체 하나의 (과세기간·회계·부서·세부사업·통계목) 집계 — 돌려받기 화면이 지자체를 고르면 받는다. 원본 행·거래처 없음 */
export const getStaticPaths: GetStaticPaths = () => vatExpenseGovs().map(g => ({ params: { gov: g.key } }));
export const GET: APIRoute = ({ params }) => { const g = vatExpenseGovs().find(x => x.key === params.gov); return new Response(JSON.stringify(g ?? {}), { headers: { 'content-type': 'application/json; charset=utf-8' } }); };
