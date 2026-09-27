/** /policy/download/<id>.md — 정책제안 리포트 마크다운(머리말+본문+FAQ+출처). */
import type { APIRoute, GetStaticPaths } from 'astro';
import { policyReports, reportMeta } from '../../../lib/reports';
import { reportMarkdown } from '../../../lib/docx';

export const getStaticPaths: GetStaticPaths = async () => (await policyReports()).map(p => ({ params: { id: p.id }, props: { post: p } }));
export const GET: APIRoute = async ({ props }) => new Response(reportMarkdown(reportMeta(props.post), props.post.body ?? ''), { headers: { 'Content-Type': 'text/markdown; charset=utf-8' } });
