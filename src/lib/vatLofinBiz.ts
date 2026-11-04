import fs from 'node:fs';
/** 지방재정365 세부사업별 세출 현황 대구 행(data/vat/lofin_biz/<연도>.csv, scripts/fetch_lofin_bizexp.py) → /vat-expense/lofin-<gov>.json.
 *  돌려받기 '공개 지출 자료로 후보 찾기'의 2024년 이후 몫(운영자 2026-11-04 '연결해봐') — 주민참여 재정 포털 건별 자료는 2023년까지라 그 뒤는 세부사업 한 해 지출액만 있다.
 *  통계목·거래처·세액 없음. 값 그대로(원). */
export type LofinBiz = { acct: string; biz: string; f: string; s: string; y: Record<string, number> };
export type LofinGov = { v: 1; key: string; name: string; years: string[]; source: string; rows: LofinBiz[] };
const DIR = 'data/vat/lofin_biz';
const GOV: Record<string, [string, string]> = { 본청: ['daegu', '대구광역시'], 중구: ['jung', '중구'], 동구: ['dong', '동구'], 서구: ['seo', '서구'], 남구: ['nam', '남구'], 북구: ['buk', '북구'], 수성구: ['suseong', '수성구'], 달서구: ['dalseo', '달서구'], 달성군: ['dalseong', '달성군'], 군위군: ['gunwi', '군위군'] };
function parseCsv(t: string): string[][] {
  const out: string[][] = []; let row: string[] = [], cell = '', q = false;
  for (let i = 0; i < t.length; i++) { const c = t[i]; if (q) { if (c === '"') { if (t[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += c; } else if (c === '"') q = true; else if (c === ',') { row.push(cell); cell = ''; } else if (c === '\n') { row.push(cell.replace(/\r$/, '')); out.push(row); row = []; cell = ''; } else cell += c; }
  if (cell || row.length) { row.push(cell); out.push(row); }
  return out;
}
let cache: LofinGov[] | null = null;
export function vatLofinGovs(): LofinGov[] {
  if (cache) return cache;
  if (!fs.existsSync(DIR)) return (cache = []);
  const by = new Map<string, { years: Set<string>; m: Map<string, LofinBiz> }>();
  for (const f of fs.readdirSync(DIR).filter(f => /^\d{4}\.csv$/.test(f)).sort()) {
    const rows = parseCsv(fs.readFileSync(`${DIR}/${f}`, 'utf-8')); const h = rows[0] ?? []; const ix = (n: string) => h.indexOf(n);
    const [iY, iG, iA, iB, iX, iF, iS] = [ix('연도'), ix('자치단체'), ix('회계'), ix('세부사업명'), ix('지출액'), ix('분야'), ix('부문')];
    if ([iY, iG, iA, iB, iX].some(i => i < 0)) continue;
    for (const r of rows.slice(1)) {
      const g = GOV[r[iG]]; if (!g) continue; const amt = Number(r[iX] || 0); if (!amt) continue;
      const e = by.get(g[0]) ?? { years: new Set<string>(), m: new Map() }; e.years.add(r[iY]);
      const k = `${r[iA]}|${r[iB]}`; const b = e.m.get(k) ?? { acct: r[iA], biz: r[iB], f: r[iF] ?? '', s: r[iS] ?? '', y: {} };
      b.y[r[iY]] = (b.y[r[iY]] ?? 0) + amt; e.m.set(k, b); by.set(g[0], e);
    }
  }
  const order = Object.values(GOV).map(g => g[0]);
  cache = [...by.entries()].map(([key, e]) => ({ v: 1 as const, key, name: Object.values(GOV).find(g => g[0] === key)![1], years: [...e.years].sort(), source: '행정안전부 지방재정365 통합자료실 「N 회계연도 세부사업별 세출 현황」(공공데이터포털 15138684), 회계연도 말일 기준 세부사업별 지출액', rows: [...e.m.values()] }));
  cache.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
  return cache;
}
