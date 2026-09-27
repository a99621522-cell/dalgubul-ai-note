import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { programs, cityPrograms, fmtEok, fmtCheon } from '../lib/csv';
import { CATEGORIES } from '../categories';

/** 통합 검색(/search/)용 경량 색인. 기업은 /companies-index.json 을 따로 받는다.
 *  posts: t=제목 u=주소 d=핵심 문장 c=분류 g=태그 y=날짜 / programs: n=사업명 m=부처 e=수행기관 b=2026 예산(억 원) w=신규 / city: n=세부사업 o=실국 p=부서 s=상태 b=2026 예산(천 원→표시) */
export const GET: APIRoute = async () => {
  const posts = (await getCollection('posts', p => !p.data.draft)).sort((a, b) => b.data.date.getTime() - a.data.date.getTime())
    .map(p => ({ t: p.data.title.replace(/^\[정책제안\]\s*/, ''), u: `/posts/${p.id}/`, d: (p.data.description ?? p.data.summary ?? '').slice(0, 160), c: CATEGORIES[p.data.category]?.name ?? '', g: p.data.tags ?? [], y: p.data.date.toISOString().slice(0, 10) }));
  const nat = programs().filter(p => p.corp).map(p => ({ n: p.name, m: p.ministry, e: p.executor || '', b: p.b26 ? fmtEok(p.b26) : '', w: p.isNew ? 1 : 0 }));
  const city = cityPrograms().filter(p => !p.admin).map(p => ({ n: p.name, o: p.org || '', p: p.dept || '', s: p.status || '', b: fmtCheon(p.b26) ?? '' }));
  const body = JSON.stringify({ posts, programs: nat, city });
  return new Response(body, { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
};
