/** /listed/audit.json — 비상장 외감·전국 비교 집계 전체(회사별 값 없음) */
import { auditCompare } from '../../lib/dartAudit';
export function GET() {
  return new Response(JSON.stringify(auditCompare() ?? {}), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
}
