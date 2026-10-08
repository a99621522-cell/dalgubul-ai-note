/** /ordinance-lawrefs.json — 법령 → 그 법령을 인용한 대구 자치법규(역색인). /ordinance/law/ 가 브라우저에서 거른다. */
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
export async function GET() {
  const p = path.join(process.cwd(), 'data', 'ordinance', 'lawrefs.json.gz');
  const raw = fs.existsSync(p) ? JSON.parse(zlib.gunzipSync(fs.readFileSync(p)).toString('utf-8')) : {};
  // 짧은 꼴: [법령ID, 이름, 시행일, [[org, 자치법규ID, 이름, [조...]], ...]]
  const rows = Object.entries(raw).map(([id, v]: [string, any]) => [id, v.name, v.eff, v.refs.map((e: any) => [e.org, e.oid, e.oname, e.arts])]);
  rows.sort((a: any, b: any) => a[1].localeCompare(b[1], 'ko'));
  return new Response(JSON.stringify(rows), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
}
