import type { APIRoute } from 'astro';
import { companies, shortComplex, supportHistory } from '../lib/csv';
import { companyStats } from '../lib/stats';
import { zonesOf } from '../lib/sites';

/** 기업 사전 검색용 경량 색인. 빌드 때 /companies-index.json 으로 생성된다.
 *  /companies/ 목록 페이지는 처음 200곳만 HTML 로 내보내고, 검색·필터를 쓰는 순간 이 파일을 한 번 받아
 *  클라이언트에서 전체를 거른다(11,000곳을 한 페이지에 넣으면 4.5MB 라 휴대폰에서 느렸다).
 *  키를 한 글자로 줄여 크기를 아낀다. companies() 를 그대로 쓰므로 개인 성명 제외 규칙도 같이 적용된다.
 *  i=id n=회사명 d=구군 e=읍면동 c=단지(약칭) g=업종군 s=업종 w=종사자 규모 t=입지 유형 k=태그(있을 때만) p=지원 이력 있음(있을 때만)
 *  z=특구 key 목록(있을 때만, config/site_types.yml zones)  x=업종 코드 앞 2자리(있을 때만 — /stats/industry/ 고부가 3부문 → ?ksic=26,27,28 필터)
 *  m=고용 인원(통계 기준월의 국민연금 가입자수 또는 팩토리온 종사자, 없으면 생략 — /explore/ 데이터 탐색이 합산에 쓴다) */
export const GET: APIRoute = () => {
  const list = companies();
  const supported = new Set(supportHistory().filter(r => r.id).map(r => r.id));
  const emp = (companyStats()?.companies ?? {}) as Record<string, { e: number | null; d?: 1 }>;
  // v2 형식(리디자인 v3 3단계 2026-10-12): 되풀이되는 글자(구군·읍면동·단지·업종군·업종·규모·입지·태그·특구)를 사전(dict)으로 빼고 행은 배열로 —
  // 2.9MB → 약 1MB. 브라우저는 src/scripts/companyIndex.ts decodeCompanyIndex()(기업 사전 목록은 같은 식을 인라인으로)로 예전과 같은 객체 행을 되살린다.
  // 행 = [i, n, d, e, c, g, s, w, t, x, m, f, k, z] — d~t 는 dict 번호, x 는 업종 코드 앞 2자리(없으면 ''), m 은 고용(없으면 -1), f 비트(1=p 지원 이력, 2=md 겹치는 기록), k·z 는 번호 배열 또는 0
  const DK = ['d', 'e', 'c', 'g', 's', 'w', 't', 'k', 'z'] as const;
  const dict: Record<string, string[]> = Object.fromEntries(DK.map(k => [k, []]));
  const pos: Record<string, Map<string, number>> = Object.fromEntries(DK.map(k => [k, new Map()]));
  const ix = (k: string, v: string) => { const m = pos[k]; let i = m.get(v); if (i == null) { i = dict[k].length; dict[k].push(v); m.set(v, i); } return i; };
  const rows = list.map(c => {
    const z = zonesOf(c), x = (c.sector_code || '').trim().slice(0, 2);
    return [c.id, c.name, ix('d', c.district), ix('e', c.eupmyeon), ix('c', shortComplex(c.complex)), ix('g', c.sector_group), ix('s', c.sector.replace(/ 외 \d+ 종/, '')),
      ix('w', c.workers_band), ix('t', c.site_type), x.length === 2 ? x : '', emp[c.id]?.e ?? -1, (supported.has(c.id) ? 1 : 0) | (emp[c.id]?.d ? 2 : 0),
      c.tags.length ? c.tags.map(t => ix('k', t)) : 0, z.length ? z.map(t => ix('z', t)) : 0];
  });
  const body = JSON.stringify({ v: 2, as_of: list[0]?.as_of ?? '', total: rows.length, dict, rows });
  return new Response(body, { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
};
