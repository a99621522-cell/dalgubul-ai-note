/** /support-index.json — /support/ 검색·더 보기용 색인(처음 50곳만 HTML). 필드는 lib/supportFirms.ts supportIndex() */
import { supportIndex } from '../lib/supportFirms';
export async function GET() { return new Response(JSON.stringify(supportIndex()), { headers: { 'Content-Type': 'application/json; charset=utf-8' } }); }
