import type { APIRoute } from 'astro';
import { vatRevenue } from '../lib/vatRevenue';
/** 지자체 세입예산서(세외수입·시설 관련 보조금) — /vat/discover/·/vat/setup/ 가 지자체를 고르면 받는다. 공개 예산서 값 그대로(천원) */
export const GET: APIRoute = () => new Response(JSON.stringify({ v: 1, govs: vatRevenue() }), { headers: { 'content-type': 'application/json; charset=utf-8' } });
