import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { companies, programs } from '../lib/csv';

/** 검색창 자동완성용 작은 색인(/typeahead.json, 디자인·UI 개선 2차 2026-10-06). 기업은 이름·구군만(/companies-index.json 2.7MB 대신),
 *  글은 제목·주소, 부처 사업은 이름·부처. 평가·순위 없음 — 자동완성은 이름이 검색어로 시작하는 것 먼저, 그다음 포함, 가나다순. */
export const GET: APIRoute = async () => {
  const co = companies().map(c => [c.id, c.name, c.district]);
  const posts = (await getCollection('posts', p => !p.data.draft)).sort((a, b) => b.data.date.getTime() - a.data.date.getTime())
    .map(p => [p.data.title.replace(/^\[정책제안\]\s*/, ''), `/posts/${p.id}/`]);
  const pr = programs().filter(p => p.corp).map(p => [p.name, p.ministry]);
  return new Response(JSON.stringify({ co, posts, pr }), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
};
