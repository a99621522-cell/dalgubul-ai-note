/** /sme-index.json — 지역중소기업 명단 검색용(/sme/ 의 스크립트가 받는다). [이름, 업종, 묶음 키(;), 기업 사전 id] */
import { smeList } from '../lib/sme';
export async function GET() {
  const { rows } = smeList();
  return new Response(JSON.stringify(rows.map(r => [r.name, r.sector, r.groups.join(';'), r.id])), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
}
