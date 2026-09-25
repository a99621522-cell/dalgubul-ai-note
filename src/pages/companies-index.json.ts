import type { APIRoute } from 'astro';
import { companies, shortComplex, supportHistory } from '../lib/csv';

/** 기업 사전 검색용 경량 색인. 빌드 때 /companies-index.json 으로 생성된다.
 *  /companies/ 목록 페이지는 처음 200곳만 HTML 로 내보내고, 검색·필터를 쓰는 순간 이 파일을 한 번 받아
 *  클라이언트에서 전체를 거른다(11,000곳을 한 페이지에 넣으면 4.5MB 라 휴대폰에서 느렸다).
 *  키를 한 글자로 줄여 크기를 아낀다. companies() 를 그대로 쓰므로 개인 성명 제외 규칙도 같이 적용된다.
 *  i=id n=회사명 d=구군 e=읍면동 c=단지(약칭) g=업종군 s=업종 w=종사자 규모 t=입지 유형 k=태그(있을 때만) p=지원 이력 있음(있을 때만) */
export const GET: APIRoute = () => {
  const list = companies();
  const supported = new Set(supportHistory().filter(r => r.id).map(r => r.id));
  const rows = list.map(c => ({
    i: c.id,
    n: c.name,
    d: c.district,
    e: c.eupmyeon,
    c: shortComplex(c.complex),
    g: c.sector_group,
    s: c.sector.replace(/ 외 \d+ 종/, ''),
    w: c.workers_band,
    t: c.site_type,
    ...(c.tags.length ? { k: c.tags } : {}),
    ...(supported.has(c.id) ? { p: 1 } : {}),
  }));
  const body = JSON.stringify({ as_of: list[0]?.as_of ?? '', total: rows.length, rows });
  return new Response(body, { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
};
