import { getCollection } from 'astro:content';
import type { APIContext } from 'astro';
export async function GET(ctx: APIContext) {
  const posts = (await getCollection('posts', p => !p.data.draft)).sort((a, b) => b.data.date.getTime() - a.data.date.getTime()).slice(0, 30);
  const site = ctx.site?.toString().replace(/\/$/, '') ?? '';
  const esc = (s: string) => s.replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]!));
  const items = posts.map(p => `<item><title>${esc(p.data.title)}</title><link>${site}/posts/${p.id}/</link><guid>${site}/posts/${p.id}/</guid><pubDate>${p.data.date.toUTCString()}</pubDate><description>${esc(p.data.summary)}</description></item>`).join('');
  return new Response(`<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>다잇다 노트</title><link>${site}</link><description>대구 경제와 공무원 AI 활용 기록</description>${items}</channel></rss>`, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
}
