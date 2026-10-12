/** /companies-index.json v2(사전 + 배열 행)를 예전 객체 행({i,n,d,e,c,g,s,w,t,k?,p?,z?,x?,m?,md?})으로 되살린다 — 통합 검색·데이터 탐색이 쓴다.
 *  형식은 src/pages/companies-index.json.ts 머리 주석. 기업 사전 목록(companies/index.astro)은 인라인 스크립트라 같은 식을 따로 둔다. */
export type CompanyRow = { i: string; n: string; d: string; e: string; c: string; g: string; s: string; w: string; t: string; k?: string[]; p?: 1; z?: string[]; x?: string; m?: number; md?: 1 };
export function decodeCompanyIndex(j: any): { as_of: string; total: number; rows: CompanyRow[] } {
  if (j.v !== 2) return j;   // 옛 형식(객체 행)
  const D = j.dict;
  const rows = (j.rows as any[]).map(([i, n, d, e, c, g, s, w, t, x, m, f, k, z]) => {
    const r: CompanyRow = { i, n, d: D.d[d], e: D.e[e], c: D.c[c], g: D.g[g], s: D.s[s], w: D.w[w], t: D.t[t] };
    if (k) r.k = k.map((v: number) => D.k[v]);
    if (f & 1) r.p = 1;
    if (z) r.z = z.map((v: number) => D.z[v]);
    if (x) r.x = x;
    if (m >= 0) r.m = m;
    if (f & 2) r.md = 1;
    return r;
  });
  return { as_of: j.as_of, total: j.total, rows };
}
let _p: Promise<ReturnType<typeof decodeCompanyIndex>> | null = null;
export const loadCompanyIndex = () => (_p ??= fetch('/companies-index.json').then(r => r.json()).then(decodeCompanyIndex));
