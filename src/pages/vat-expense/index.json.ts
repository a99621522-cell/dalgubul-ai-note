import type { APIRoute } from 'astro';
import { vatExpenseIndex } from '../../lib/vatExpense';
/** 대구 공개 지출 자료 집계 목록 — 돌려받기 '공개 지출 자료로 후보 찾기'의 지자체 선택 상자 */
export const GET: APIRoute = () => new Response(JSON.stringify({ v: 1, govs: vatExpenseIndex() }), { headers: { 'content-type': 'application/json; charset=utf-8' } });
