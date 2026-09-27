/** /policy/download/<id>.docx — 정책제안 리포트를 Word 문서로. 빌드 때 발행된 리포트마다 하나씩 만든다. */
import type { APIRoute, GetStaticPaths } from 'astro';
import { policyReports, reportMeta } from '../../../lib/reports';
import { reportDocx } from '../../../lib/docx';

export const getStaticPaths: GetStaticPaths = async () => (await policyReports()).map(p => ({ params: { id: p.id }, props: { post: p } }));
export const GET: APIRoute = async ({ props }) => {
  const post = props.post;
  const buf = await reportDocx(reportMeta(post), post.body ?? '');
  return new Response(new Uint8Array(buf), { headers: { 'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' } });
};
