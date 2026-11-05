import type { APIRoute, GetStaticPaths } from 'astro';
import { vatContractGovs } from '../../lib/vatContracts';
/** 지자체 하나의 나라장터 계약(조달청 계약정보서비스) — 돌려받기 '공개 지출 자료'의 받아 올 세금계산서 계약 목록 */
export const getStaticPaths: GetStaticPaths = () => vatContractGovs().map(g => ({ params: { gov: g.key } }));
export const GET: APIRoute = ({ params }) => new Response(JSON.stringify(vatContractGovs().find(x => x.key === params.gov) ?? {}), { headers: { 'content-type': 'application/json; charset=utf-8' } });
