/** /welfare-index.json — /welfare/ (복지서비스 찾기) 스크립트가 받는 목록. 상세 본문까지 담는다(카드 펼침). */
import { welfareData, lifeKey } from '../lib/welfare';
export async function GET() {
  const d = welfareData();
  const items = (d?.items ?? []).map(s => ({
    i: s.id, sc: s.scope, g: s.sgg, n: s.name, o: s.org, dp: s.dept, sm: s.summary,
    l: s.life.map(lifeKey), t: s.target, th: s.theme, cy: s.cycle, pv: s.provision,
    ap: s.apply || '', ct: s.contact || '', v: s.views, u: s.link, d: s.detail ?? null,
  }));
  return new Response(JSON.stringify({ at: d?.fetchedAt ?? '', items }), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
}
