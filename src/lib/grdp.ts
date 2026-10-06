import fs from 'node:fs';
import { readCsv } from './csv';

/** 대구 GRDP 성장 계산기(/growth/ — 처음엔 /stats/industry/, 운영자 지시 2026-10-05) 데이터.
 *  KOSIS 「시도별 경제활동별 지역내총생산」(data/kosis/grdp-sido-industry-all.csv): 명목·실질·실질기여도.
 *  겹치지 않는 경제활동 19개 + 순생산물세. 비중은 최근 연도 명목, 추세는 최근 10년(실질 연평균 성장, 공표 실질기여도 평균). */
export const GRDP_COMP: [string, string][] = [
  ['농업 임업 및 어업', '농림어업'], ['광업', '광업'], ['제조업', '제조업'], ['전기 가스 증기 및 공기 조절 공급업', '전기·가스·증기'],
  ['수도 하수 및 폐기물 처리 원료 재생업', '수도·하수·폐기물'], ['건설업', '건설업'], ['도매 및 소매업', '도매·소매'], ['운수 및 창고업', '운수·창고'],
  ['숙박 및 음식점업', '숙박·음식점'], ['정보통신업', '정보통신'], ['금융 및 보험업', '금융·보험'], ['부동산업', '부동산'],
  ['전문 과학 및 기술 서비스업', '전문·과학·기술'], ['사업시설 관리 사업 지원 및 임대 서비스업', '사업시설관리·지원·임대'],
  ['공공 행정 국방 및 사회보장 행정', '공공행정·국방'], ['교육 서비스업', '교육'], ['보건업 및 사회복지 서비스업', '보건·사회복지'],
  ['예술 스포츠 및 여가관련 서비스', '예술·스포츠·여가'], ['협회 및 단체 수리 및 기타 개인 서비스업', '협회·수리·개인서비스'], ['순생산물세', '순생산물세(세금−보조금)'],
];
/** 지출 측(KOSIS DT_1C93 시도별 지역내총생산에 대한 지출): 겹치지 않는 최상위 항목. 모두 더하면 GRDP. */
export const GRDE_COMP: [string, string][] = [
  ['민간최종소비지출', '민간소비'], ['정부최종소비지출', '정부소비'], ['건설투자', '건설투자'], ['설비투자', '설비투자'],
  ['지식재산생산물투자', '지식재산투자(연구개발 등)'], ['재고증감 및 귀중품 순취득', '재고 증감'], ['재화와 서비스 순이출', '순이출(역외로 판 것 − 사 온 것)'],
  ['통계상 불일치', '통계상 불일치'],
];
export type GrdpItem = { key: string; name: string; share: number; cagr: number | null; avgc: number; last: number | null };
export function grdpCalcData(side: 'prod' | 'exp' = 'prod', region = '대구광역시') {
  const exp = side === 'exp';
  const TOT = exp ? '지역내총생산에대한지출' : '지역내총생산(시장가격)';
  const COMP = exp ? GRDE_COMP : GRDP_COMP;
  const f = exp ? 'data/kosis/grdp-sido-expenditure.csv' : 'data/kosis/grdp-sido-industry-all.csv';
  const V = new Map<string, number>();
  for (const r of readCsv(f)) if (r.C1_NM === region && r.DT !== '' && Number.isFinite(Number(r.DT))) V.set(`${r.ITM_NM}|${r.C2_NM}|${r.PRD_DE}`, Number(r.DT));
  const years = [...new Set([...V.keys()].map(k => Number(k.split('|')[2])))].sort();
  const y1 = years.at(-1) ?? 0, y0 = Math.max(years[0] ?? 0, y1 - 9);   // 2015→2024: 산업구조지수 리포트와 같은 기간
  const n = y1 - y0;
  const v = (i: string, k: string, y: number) => V.get(`${i}|${k}|${y}`);
  const nom = v('명목', TOT, y1) ?? 0;
  const items: GrdpItem[] = COMP.map(([k, name]) => {
    const r1 = v('실질', k, y1), r0 = v('실질', k, y0);
    const cs = Array.from({ length: n }, (_, j) => v('실질기여도', k, y0 + 1 + j) ?? 0);
    return { key: k, name, share: ((v('명목', k, y1) ?? 0) / nom) * 100, cagr: r1 && r0 && r1 > 0 && r0 > 0 ? ((r1 / r0) ** (1 / n) - 1) * 100 : null,
      avgc: cs.reduce((a, b) => a + b, 0) / n, last: v('실질기여도', k, y1) ?? null };
  });
  const growth = years.slice(1).filter(y => y > y0).map(y => ({ y, g: ((v('실질', TOT, y) ?? 0) / (v('실질', TOT, y - 1) ?? 1) - 1) * 100 }));
  const cagr = ((v('실질', TOT, y1) ?? 0) / (v('실질', TOT, y0) ?? 1)) ** (1 / n) * 100 - 100;
  const meta = (() => { try { return JSON.parse(fs.readFileSync(f.replace('.csv', '.json'), 'utf-8')); } catch { return {}; } })();
  if (!nom) return { items: [] as GrdpItem[], growth, cagr: 0, y0, y1, nomTrillion: 0, source: '', url: '' };
  return { items, growth, cagr, y0, y1, nomTrillion: nom / 1e6, source: `국가데이터처 「${meta.tbl_nm ?? (exp ? '시도별 지역내총생산에 대한 지출' : '시도별 경제활동별 지역내총생산')}」(KOSIS)`, url: meta.source_url ?? '' };
}

/** 한국은행 「2020년 지역산업연관표」에서 뽑은 대구 유발계수(scripts/data/bok_io_daegu.json). 최종수요 전체(소비·투자·수출) 1단위 기준이며
 *  지출 항목별 계수는 책에 없다(ECOS 세부 계수표 몫). 계산기 '예산·사업 규모로 보기'가 쓴다. */
export function ioDaegu() {
  try {
    const d = JSON.parse(fs.readFileSync('scripts/data/bok_io_daegu.json', 'utf-8'));
    const pick = (type: string) => (d.final_demand as any[]).find(r => r.region === '대구' && r.type === type && r.year === 2020);
    const va = pick('부가가치유발계수'), emp = pick('취업유발계수');
    const fd = (d.facts as any[]).find(f => /표 IV-7.*대구/.test(f.text))?.text ?? '';
    const m = (re: RegExp) => { const x = fd.match(re); return x ? Number(x[1]) : null; };
    return { vaIn: va?.within ?? null, vaOut: va?.other ?? null, vaPage: va?.page, empIn: emp?.within ?? null, empOut: emp?.other ?? null, empPage: emp?.page,
      importShare: m(/수입\s*([\d.]+)%/), inflowShare: m(/타지역 이입\s*([\d.]+)%/), localShare: m(/지역내 생산\s*([\d.]+)%/), source: d.source as string, url: d.url as string };
  } catch { return null; }
}

/** 외지인 관광소비(한국관광 데이터랩, data/tourism/datalab_spend_share.csv 의 '외지인' 대구 값) — 12달이 다 있는 최근 해 합계.
 *  성장 계산기 시나리오(GrowthLevers)가 쓴다. 데이터랩은 총량보다 추세로 보라고 안내한다. */
export function tourismOutsider() {
  try {
    const by = new Map<string, { n: number; v: number; nat: number }>();
    for (const r of readCsv('data/tourism/datalab_spend_share.csv')) {
      if (r.group !== '외지인') continue;
      const y = r.ym.slice(0, 4), o = by.get(y) ?? { n: 0, v: 0, nat: 0 };
      o.n++; o.v += Number(r.region_mil_won) || 0; o.nat += Number(r.nation_mil_won) || 0; by.set(y, o);
    }
    const full = [...by.entries()].filter(([, o]) => o.n === 12).sort((a, b) => a[0].localeCompare(b[0]));
    const [y, o] = full.at(-1) ?? [];
    if (!y || !o) return null;
    const prev = full.at(-2);
    const meta = (() => { try { return JSON.parse(fs.readFileSync('data/tourism/datalab_meta.json', 'utf-8')); } catch { return {}; } })();
    return { year: y, eok: o.v / 100, share: (o.v / o.nat) * 100, prevYear: prev?.[0], prevEok: prev ? prev[1].v / 100 : null,
      source: (meta.source as string) ?? '한국관광공사 한국관광 데이터랩', url: (meta.page as string) ?? '' };
  } catch { return null; }
}

/** 산업구조와 성장 계산기(/growth/, 운영자 지시 2026-10-05: 산업구조지수 리포트와 논리적으로 같은 계산기).
 *  리포트(src/content/posts/2026-09-30-policy-structure-daegu.md, scripts/structure_index.py·structure_report.json)와 같은 정의:
 *  기간 2015→2024(리포트 years), 부문은 지역소득 경제활동별 말단 25개 부문(순생산물세 제외), 비중 = 부문 명목 총부가가치 ÷ 25개 부문 합,
 *  LQ = 대구 비중 ÷ 전국 비중, 특화 = LQ ≥ 1, 고부가 3부문 = 전기·전자·정밀기기·정보통신·금융보험, HHI = Σ(비중×100)², 변화속도 = ½Σ|비중 변화|.
 *  출발 성장률은 리포트의 대구 실질 GRDP 연평균 성장률(2015→2024)이고, 업종 가정의 변화분 = 비중 × (가정 성장률 − 업종 10년 연평균 실질 성장률). */
export const LEAVES: [string, string][] = [
  ['농업 임업 및 어업', '농림어업'], ['광업', '광업'], ['음식료품 및 담배제조업', '음식료품·담배'], ['섬유 의복 및 가죽 제품 제조업', '섬유·의복·가죽'],
  ['목재종이인쇄 및 복제업', '목재·종이·인쇄'], ['석탄 및 석유 화학제품 제조업', '석탄·석유·화학'], ['비금속광물 및 금속제품 제조업', '비금속·금속'],
  ['전기 전자 및 정밀기기 제조업', '전기·전자·정밀기기'], ['기계 운송장비 및 기타 제품 제조업', '기계·운송장비·기타'], ['전기 가스 증기 및 공기 조절 공급업', '전기·가스'],
  ['수도 하수 및 폐기물 처리 원료 재생업', '수도·폐기물'], ['건설업', '건설업'], ['도매 및 소매업', '도소매'], ['운수 및 창고업', '운수·창고'], ['숙박 및 음식점업', '숙박·음식점'],
  ['정보통신업', '정보통신'], ['금융 및 보험업', '금융·보험'], ['부동산업', '부동산'], ['전문 과학 및 기술 서비스업', '전문·과학·기술'],
  ['사업시설 관리 사업 지원 및 임대 서비스업', '사업시설·지원'], ['공공 행정 국방 및 사회보장 행정', '공공행정'], ['교육 서비스업', '교육'],
  ['보건업 및 사회복지 서비스업', '보건·사회복지'], ['예술 스포츠 및 여가관련 서비스', '예술·스포츠·여가'], ['협회 및 단체 수리 및 기타 개인 서비스업', '협회·수리·개인'],
];
export const HIGH = ['전기 전자 및 정밀기기 제조업', '정보통신업', '금융 및 보험업'];
const MFG = LEAVES.slice(2, 9).map(x => x[0]);
/** share = 25개 부문 부가가치 합 대비 비중(%; 리포트의 입지계수·산업집중도 정의). w = 성장 기여 가중치 — 2026-10-07 부터 share 와 같다(합 100%):
 *  순생산물세(GRDP 의 약 7%)는 부가가치에 비례해 함께 는다고 보아, 성장률 몫 = ΔVA ÷ 명목 총부가가치(기초가격) 로 모든 계산기가 같은 기준을 쓴다
 *  (운영자 평가 2026-10-07: 이전 w 는 명목 GRDP 대비라 합이 93% 여서 모든 업종을 1%p 더 키워도 0.93%p 만 올라 목표 계산기와 어긋났다). */
export type StructRow = { key: string; name: string; share: number; w: number; nat: number; lq: number; va: number; g: number; gn: number; t3: number; gmax: number; gmaxReg: string; high: boolean; spec: boolean; mfg: boolean };
/** 기준 기간 후보(운영자 평가 2026-10-06: 출발 성장률이 코로나 시기를 포함 — 기간을 바꿔 볼 수 있게). 리포트 기간이 기본 */
export const PERIODS: [number, number, string][] = [[2015, 2024, '2015→2024 (리포트 기준)'], [2015, 2019, '2015→2019 (코로나 전)'], [2021, 2024, '2021→2024 (코로나 후)']];
export function structureCalc(region = '대구광역시') {
  let rep: any = {};
  try { rep = JSON.parse(fs.readFileSync('data/kosis/structure_report.json', 'utf-8')); } catch { /* 없음 */ }
  const [y0, y1] = (rep.years as number[] | undefined) ?? [2015, 2024];
  const V = new Map<string, number>();
  const regions = new Set<string>();
  for (const r of readCsv('data/kosis/grdp-sido-industry-all.csv')) {
    if (r.DT === '' || !Number.isFinite(Number(r.DT))) continue;
    V.set(`${r.ITM_NM}|${r.C1_NM}|${r.C2_NM}|${r.PRD_DE}`, Number(r.DT)); regions.add(r.C1_NM);
  }
  const v = (i: string, reg: string, k: string, y: number) => V.get(`${i}|${reg}|${k}|${y}`);
  const n = y1 - y0;
  const cagr = (reg: string, k: string) => { const a = v('실질', reg, k, y0), b = v('실질', reg, k, y1); return a && b && a > 0 && b > 0 ? ((b / a) ** (1 / n) - 1) * 100 : null; };
  const sum = (reg: string) => LEAVES.reduce((a, [k]) => a + (v('명목', reg, k, y1) ?? 0), 0);
  const tot = sum(region), natTot = sum('전국');
  if (!tot) return null;
  const sido = [...regions].filter(r => r !== '전국');
  const gdpNom = v('명목', region, '지역내총생산(시장가격)', y1) ?? tot;
  const rows: StructRow[] = LEAVES.map(([k, name]) => {
    const va = v('명목', region, k, y1) ?? 0, share = va / tot * 100, nat = (v('명목', '전국', k, y1) ?? 0) / natTot * 100;
    const g = cagr(region, k) ?? 0;
    const pairs = sido.map(r => [r, cagr(r, k)] as [string, number | null]).filter((x): x is [string, number] => x[1] != null).sort((a, b) => b[1] - a[1]);
    const cs = pairs.map(x => x[1]);
    return { key: k, name, share, w: share, nat, lq: nat ? share / nat : 0, va: va / 100, g, gn: cagr('전국', k) ?? g,
      t3: cs.length ? cs.slice(0, 3).reduce((a, b) => a + b, 0) / Math.min(3, cs.length) : g,
      gmax: cs.length ? cs[0] : g, gmaxReg: pairs.length ? pairs[0][0].replace(/(특별자치|광역|특별)?(시|도)$/, '') : '',   // 실현 가능성 띠(2026-10-07): 17개 시도 가운데 그 업종 10년 성장률이 가장 높았던 값(관측된 범위의 위쪽)
      high: HIGH.includes(k), spec: nat > 0 && share / nat >= 1, mfg: MFG.includes(k) };
  }).filter(r => r.share > 0);
  // 기준 기간 후보별 업종·전체 성장률(같은 CSV, 같은 식). 리포트 기간은 리포트 값(base) 그대로
  const cagrP = (reg: string, k: string, a: number, b: number) => { const x = v('실질', reg, k, a), y = v('실질', reg, k, b); return x && y && x > 0 && y > 0 ? ((y / x) ** (1 / (b - a)) - 1) * 100 : null; };
  const periods = PERIODS.map(([a, b, label]) => ({ a, b, label, base: cagrP(region, '지역내총생산(시장가격)', a, b) ?? 0, nat: cagrP('전국', '지역내총생산(시장가격)', a, b) ?? 0,
    g: Object.fromEntries(rows.map(r => { const cs = sido.map(x => cagrP(x, r.key, a, b)).filter((x): x is number => x != null).sort((p, q) => q - p);
      return [r.key, { g: cagrP(region, r.key, a, b) ?? 0, gn: cagrP('전국', r.key, a, b) ?? 0, t3: cs.length ? cs.slice(0, 3).reduce((p, q) => p + q, 0) / Math.min(3, cs.length) : 0, gmax: cs.length ? cs[0] : 0 }]; })) }));
  // 대구 취업자(경제활동인구조사 연간, 천 명) — 고용 효과를 견줄 기준
  let employed: { year: string; thousand: number } | null = null;
  try { const e = readCsv('data/kosis/labor-force-sido-annual-all.csv').filter(r => r.C1_NM === '대구광역시' && r.ITM_NM === '취업자' && r.DT).sort((p, q) => p.PRD_DE.localeCompare(q.PRD_DE)).at(-1); if (e) employed = { year: e.PRD_DE, thousand: Number(e.DT) }; } catch { /* 없음 */ }
  // 노동 공급 점검(운영자 지시 2026-10-07 '2번 고쳐'): 실업자(경제활동인구조사 연간, 천 명)와 최근 12개월 순이동(국내인구이동통계, 명) — 취업 유발이 대구 안에서 채워지는지 견준다
  let unemployed: { year: string; thousand: number } | null = null;
  try { const e = readCsv('data/kosis/labor-force-sido-annual-all.csv').filter(r => r.C1_NM === '대구광역시' && r.ITM_NM === '실업자' && r.DT).sort((p, q) => p.PRD_DE.localeCompare(q.PRD_DE)).at(-1); if (e) unemployed = { year: e.PRD_DE, thousand: Number(e.DT) }; } catch { /* 없음 */ }
  let netMig: { from: string; to: string; persons: number } | null = null;
  try {
    const ms = readCsv('data/kosis/migration-sido.csv').filter(r => r.C1_NM === '대구광역시' && r.ITM_NM === '순이동' && r.DT !== '').sort((p, q) => p.PRD_DE.localeCompare(q.PRD_DE)).slice(-12);
    if (ms.length === 12) netMig = { from: `${ms[0].PRD_DE.slice(0, 4)}-${ms[0].PRD_DE.slice(4, 6)}`, to: `${ms[11].PRD_DE.slice(0, 4)}-${ms[11].PRD_DE.slice(4, 6)}`, persons: ms.reduce((a, r) => a + Number(r.DT), 0) };
  } catch { /* 없음 */ }
  // 1인당 GRDP 과거 참고(운영자 지시 2026-10-07 '다 해봐'): 주민등록 연말 인구(population-sido)로 y0→y1 인구 연평균 증감률을 구해 1인당 실질 GRDP 연평균 ≈ (1+g)/(1+p)−1. 미래 인구는 전망하지 않는다
  let perCapita: { popCagr: number; pcCagr: number; pop0: number; pop1: number } | null = null;
  try {
    const po = readCsv('data/kosis/population-sido.csv').filter(r => r.C1_NM === '대구광역시' && r.ITM_NM === '총인구수');
    const p0 = Number(po.find(r => r.PRD_DE === String(y0))?.DT), p1 = Number(po.find(r => r.PRD_DE === String(y1))?.DT);
    const gb = (rep.data?.grdp_growth?.['대구'] as number | undefined) ?? cagr(region, '지역내총생산(시장가격)') ?? 0;
    if (p0 > 0 && p1 > 0) { const pc = ((p1 / p0) ** (1 / n) - 1) * 100; perCapita = { popCagr: pc, pcCagr: ((1 + gb / 100) / (1 + pc / 100) - 1) * 100, pop0: p0, pop1: p1 }; }
  } catch { /* 없음 */ }
  let backtest: any = null;
  try { backtest = JSON.parse(fs.readFileSync('data/growth/backtest.json', 'utf-8')); } catch { /* 없음 */ }
  let k2015: number | null = null;
  try { const dd = JSON.parse(fs.readFileSync('scripts/data/bok_io_daegu.json', 'utf-8')); const r = (dd.final_demand as any[]).find(x => x.region === '대구' && x.type === '부가가치유발계수' && x.year === 2015); if (r) k2015 = r.within; } catch { /* 없음 */ }
  // 가중치 검산(운영자 지시 2026-10-07 '7번'): 국가데이터처 실질기여도 = 전년 명목 비중(GRDP 대비) × 실질 성장률. 같은 식으로 y1 을 계산해 공표 값과 견준다
  // (실질 비중으로 바꿔 보면 공표 값과 더 멀어진다 — 2024년 25부문 합: 공표 −0.52, 전년 명목 비중 −0.52, 실질 비중 −0.33). 순생산물세 기여는 해마다 크게 움직여 '비례' 가정은 근사
  let contribCheck: { year: number; grdp: number; official25: number; officialTax: number; calc25: number; calcTaxProp: number } | null = null;
  try {
    const yp = y1 - 1, gdpP = v('명목', region, '지역내총생산(시장가격)', yp) ?? 0;
    const sg = (k: string) => { const a = v('실질', region, k, yp), b = v('실질', region, k, y1); return a && b ? (b / a - 1) * 100 : 0; };
    const calc25 = LEAVES.reduce((a, [k]) => a + ((v('명목', region, k, yp) ?? 0) / gdpP) * sg(k), 0);
    const gvaP = LEAVES.reduce((a, [k]) => a + (v('명목', region, k, yp) ?? 0), 0);
    if (gdpP) contribCheck = { year: y1, grdp: sg('지역내총생산(시장가격)'), official25: LEAVES.reduce((a, [k]) => a + (v('실질기여도', region, k, y1) ?? 0), 0),
      officialTax: v('실질기여도', region, '순생산물세', y1) ?? 0, calc25, calcTaxProp: calc25 * (gdpP - gvaP) / gvaP };
  } catch { /* 없음 */ }
  const d = rep.data ?? {}, short = '대구';
  const io = ioDaegu();
  return {
    y0, y1, rows,
    base: d.grdp_growth?.[short] ?? cagr(region, '지역내총생산(시장가격)') ?? 0,
    natGrowth: d.grdp_growth?.['전국'] ?? cagr('전국', '지역내총생산(시장가격)') ?? 0,
    metro6: d.metro6_avg?.grdp ?? null,
    hhi: d.hhi_2024?.[short] ?? Math.round(rows.reduce((a, r) => a + r.share ** 2, 0)), hhiAvg: d.hhi_avg ?? null,
    high: d.daegu?.high_share?.[String(y1)] ?? rows.filter(r => r.high).reduce((a, r) => a + r.share, 0), highNat: d.daegu?.high_share_nat?.[String(y1)] ?? null,
    scih: d.scih_avg?.[short] ?? null, scihAvg: d.scih_avg_all ?? null,
    hhiCoef: d.panel?.GRDP?.['Δln(산업집중도)']?.coef ?? null,
    gdpEok: (v('명목', region, '지역내총생산(시장가격)', y1) ?? 0) / 100, gvaEok: tot / 100,
    // k: 한국은행 유발계수는 '국산품 최종수요 1단위' 기준(책자 58쪽, bok_io_daegu.json basis)이라 최종수요 가운데 수입품으로 바로 사는 몫(표 IV-7, 55쪽: 6.2%)을 뺀 뒤 곱한다.
    // 중간재 수입 누출은 계수 안에 이미 들어 있어(대구 안 0.442 + 다른 지역 0.406 + 수입 유발 ≈ 1) 두 번 빼는 것이 아니다 — 운영자 지시 2026-10-07 '8번' 확인
    k: io && io.vaIn != null ? (1 - (io.importShare ?? 0) / 100) * io.vaIn : null, io,
    /** 자료 차이로 본 계수 범위: 2015년 표 계수(수입품 몫 뺀 값). 취업유발계수(10억 원당, 대구 안) */
    kAlt: io && k2015 != null ? (1 - (io.importShare ?? 0) / 100) * k2015 : null, empIn: io?.empIn ?? null,
    periods, employed, unemployed, netMig, backtest, contribCheck, perCapita,
    report: '/posts/2026-09-30-policy-structure-daegu/',
  };
}

/** '몇 명 늘면 GRDP 얼마' 계산기(GrowthQuick, 운영자 지시 2026-10-05)의 1인당 값 — 공표 자료의 나눗셈만.
 *  외지인 관광: 데이터랩 외지인 관광소비(신용카드, 백만원) ÷ 외지인 방문자(이동통신, 연인원) — 12달이 다 있는 같은 해.
 *  데이터랩은 총량보다 추세로 보라고 안내하므로 1인당 값도 근사로 쓴다. */
export function tourismPerVisit() {
  const vis = new Map<string, { n: number; v: number }>(), sp = new Map<string, { n: number; v: number }>();
  for (const r of readCsv('data/tourism/datalab_visitors.csv')) {
    if (r.code !== '27') continue;
    const y = r.ym.slice(0, 4), o = vis.get(y) ?? { n: 0, v: 0 }; o.n++; o.v += Number(r.visitors) || 0; vis.set(y, o);
  }
  for (const r of readCsv('data/tourism/datalab_spend_share.csv')) {
    if (r.group !== '외지인') continue;
    const y = r.ym.slice(0, 4), o = sp.get(y) ?? { n: 0, v: 0 }; o.n++; o.v += Number(r.region_mil_won) || 0; sp.set(y, o);
  }
  const y = [...vis.keys()].filter(k => vis.get(k)!.n === 12 && sp.get(k)?.n === 12).sort().at(-1);
  if (!y) return null;
  const visitors = vis.get(y)!.v, spendEok = sp.get(y)!.v / 100;
  return { year: y, visitors, spendEok, perWon: spendEok * 1e8 / visitors };
}

/** 다른 지역 환자(국민건강보험공단 「지역별 의료이용통계」, KOSIS TX_35003_A004·A006·A007, 건강보험 급여 진료비):
 *  유입 = 대구 소재 의료기관 − (대구 거주자 − 대구 거주자의 대구 밖 이용). 진료비(천원)와 진료실인원(명) 각각 같은 식, 1인당 = 진료비 ÷ 인원.
 *  진료실인원은 의료기관 소재 시도마다 세므로 두 지역을 다닌 사람은 양쪽에 잡힌다(근사). */
export function medicalInflow() {
  const P = readCsv('data/kosis/medical-use-sido-provider.csv'), R = readCsv('data/kosis/medical-use-sido-resident.csv'), O = readCsv('data/kosis/medical-use-sido-outside.csv');
  if (!P.length || !R.length || !O.length) return null;
  const g = (rs: Record<string, string>[], y: string, it: string, c2: string) => { const r = rs.find(x => x.PRD_DE === y && x.ITM_NM === it && x.C1_NM === '대구광역시' && x.C2_NM === c2); return r ? Number(r.DT) : NaN; };
  const y = [...new Set(P.map(r => r.PRD_DE))].sort().at(-1)!;
  const f = (it: string) => g(P, y, it, '합계') - (g(R, y, it, '합계') - g(O, y, it, '계'));
  const costEok = f('진료비') / 1e5, persons = f('진료실인원수');
  if (!Number.isFinite(costEok) || !Number.isFinite(persons) || persons <= 0) return null;
  return { year: y, costEok, persons, perWon: costEok * 1e8 / persons, providerEok: g(P, y, '진료비', '합계') / 1e5 };
}

/** 정책 과제별 계산기(GrowthPolicy)에 쓰는 자료 — 공표 자료 그대로·나눗셈만.
 *  tourMix: 외지인 관광소비(데이터랩 업종별, 12달이 다 있는 최근 해)의 업종 구성 → 지역소득 부문으로 옮김(쇼핑→도소매, 식음료·숙박→숙박·음식점,
 *  운송→운수·창고, 여가서비스→예술·스포츠·여가, 의료웰니스→보건·사회복지, 여행업→사업시설·지원). vaRatio: 광업·제조업조사 대구 중분류 부가가치 ÷ 출하액(최근 해). */
const TOUR_TO_LEAF: Record<string, string> = { 쇼핑업: '도매 및 소매업', 식음료업: '숙박 및 음식점업', 숙박업: '숙박 및 음식점업', 운송업: '운수 및 창고업',
  여가서비스업: '예술 스포츠 및 여가관련 서비스', 의료웰니스업: '보건업 및 사회복지 서비스업', 여행업: '사업시설 관리 사업 지원 및 임대 서비스업' };
/** 공장 유치 항목 → 한국은행 지역산업연관표 통합대분류 33부문(scripts/data/bok_io_daegu_sectors.csv, 운영자 지시 2026-10-06 '업종별 유발계수로 간접분').
 *  의료기기는 통합대분류에서 '컴퓨터, 전자 및 광학기기'(의료·정밀·광학기기 포함), 의약품은 '화학제품'에 든다. */
export const PLANT_IO_SECTOR: Record<string, string> = {
  semi: '컴퓨터, 전자 및 광학기기', medtech: '컴퓨터, 전자 및 광학기기', auto: '운송장비', battery: '전기장비', robotplant: '기계 및 장비',
  pharma: '화학제품', chem: '화학제품', metal: '금속가공제품', food: '음식료품', textileplant: '섬유 및 가죽제품',
};
export type IoSector = { sector: string; va: number | null; k: number | null; kOther: number | null; emp: number | null; empNat: number | null; empNatDirect: number | null };
/** 대구 33부문 산업연관 계수(bok_io_daegu_sectors.csv): va = 산업연관표 기준 직접 부가가치율(표 V-2-11 나눗셈), k = 대구 지역내 부가가치유발계수(통계표 엑셀을 받아 채우기 전에는 null), empNat·empNatDirect = 전국 2020년 고용표 품목별 취업유발계수(총)·취업계수(직접, 명/10억 원 — 대구 업종별 값은 공개 자료에 없어 참고로만). */
export function ioSectors(): Record<string, IoSector> {
  const out: Record<string, IoSector> = {};
  const num = (v: string) => { const n = Number(v); return v !== '' && v != null && Number.isFinite(n) ? n : null; };
  try {
    for (const r of readCsv('scripts/data/bok_io_daegu_sectors.csv')) out[r.sector] = { sector: r.sector, va: num(r.va_ratio_io), k: num(r.k_va_within), kOther: num(r.k_va_other), emp: num(r.emp_within), empNat: num(r.emp_nat_total_2020), empNatDirect: num(r.emp_nat_direct_2020) };
  } catch { /* 없음 */ }
  return out;
}

export function policyLeversData() {
  const by = new Map<string, Map<string, number>>(), months = new Map<string, Set<string>>();
  for (const r of readCsv('data/tourism/datalab_spend.csv')) {
    if (r.code !== '27' || r.group !== '외지인' || r.industry === '전체') continue;
    const y = r.ym.slice(0, 4);
    const m = by.get(y) ?? new Map<string, number>(); m.set(r.industry, (m.get(r.industry) ?? 0) + (Number(r.amount_thousand_won) || 0)); by.set(y, m);
    (months.get(y) ?? months.set(y, new Set()).get(y)!).add(r.ym);
  }
  const ty = [...by.keys()].filter(y => months.get(y)!.size === 12).sort().at(-1);
  const tourMix: Record<string, number> = {};
  if (ty) {
    const m = by.get(ty)!, t = [...m.values()].reduce((a, b) => a + b, 0);
    for (const [k, v] of m) { const leaf = TOUR_TO_LEAF[k]; if (leaf && t) tourMix[leaf] = (tourMix[leaf] ?? 0) + v / t; }
  }
  const mm = readCsv('data/kosis/mining-mfg-survey-sido.csv').filter(r => r.C1_NM === '대구광역시');
  const myears = [...new Set(mm.map(r => r.PRD_DE))].sort();
  const my = myears.at(-1) ?? '';
  const gy = (mid: string, it: string, y: string) => { const r = mm.find(x => x.PRD_DE === y && x.C2_NM === mid && x.ITM_NM === it); return r ? Number(r.DT) : NaN; };
  const g = (mid: string, it: string) => gy(mid, it, my);
  const ratio = (mid: string) => { const v = g(mid, '부가가치') / g(mid, '출하액 계'); return Number.isFinite(v) && v > 0 ? v : null; };
  // 민감도(2026-10-07): 부가가치율의 조사 연도별 최저·최고(광업·제조업조사 대구, 받은 해 전부 — 2020~2024)
  const ratioRange = (mid: string): [number, number] | null => { const vs = myears.map(y => gy(mid, '부가가치', y) / gy(mid, '출하액 계', y)).filter(v => Number.isFinite(v) && v > 0); return vs.length ? [Math.min(...vs), Math.max(...vs)] : null; };
  // 투자액 → 연 매출(2026-10-07): 자본회전율 = 출하액 ÷ 유형자산(연말잔액). 유형자산 표(mfg-tangible-sido)는 kosis_tables.yml 에 넣었고 tbl_id 를 채워 받으면 여기서 읽힌다
  let turnover: Record<string, number | null> = {}, turnoverYear = '';
  try {
    const ta = readCsv('data/kosis/mfg-tangible-sido.csv').filter(r => r.C1_NM === '대구광역시' && /유형자산/.test(r.ITM_NM));
    const ty = [...new Set(ta.map(r => r.PRD_DE))].filter(y => myears.includes(y)).sort().at(-1);
    if (ty) { turnoverYear = ty; const tv = (mid: string) => { const r = ta.find(x => x.PRD_DE === ty && x.C2_NM === mid); const v = r ? gy(mid, '출하액 계', ty) / Number(r.DT) : NaN; return Number.isFinite(v) && v > 0 ? v : null; };
      turnover = { semi: tv('전자부품 컴퓨터 영상 음향 및 통신장비 제조업'), auto: tv('자동차 및 트레일러 제조업'), med: tv('의료 정밀 광학기기 및 시계 제조업'), mach: tv('기타 기계 및 장비 제조업'), elec: tv('전기장비 제조업'),
        pharma: tv('의료용 물질 및 의약품 제조업'), chem: tv('화학물질 및 화학제품 제조업; 의약품 제외'), metal: tv('금속가공제품 제조업; 기계 및 가구 제외'), food: tv('식료품 제조업'), textile: tv('섬유제품 제조업; 의복제외') }; }
  } catch { /* 표 없음 */ }
  const MIDS: Record<string, string> = { semi: '전자부품 컴퓨터 영상 음향 및 통신장비 제조업', auto: '자동차 및 트레일러 제조업', med: '의료 정밀 광학기기 및 시계 제조업', mach: '기타 기계 및 장비 제조업', elec: '전기장비 제조업',
    pharma: '의료용 물질 및 의약품 제조업', chem: '화학물질 및 화학제품 제조업; 의약품 제외', metal: '금속가공제품 제조업; 기계 및 가구 제외', food: '식료품 제조업', textile: '섬유제품 제조업; 의복제외' };
  const vaRange = Object.fromEntries(Object.entries(MIDS).map(([k, mid]) => [k, ratioRange(mid)])) as Record<string, [number, number] | null>;
  const vaRatio = {
    semi: ratio('전자부품 컴퓨터 영상 음향 및 통신장비 제조업'), auto: ratio('자동차 및 트레일러 제조업'),
    med: ratio('의료 정밀 광학기기 및 시계 제조업'), mach: ratio('기타 기계 및 장비 제조업'),
    // 투자유치 항목 확장(운영자 지시 2026-10-06: 반도체·미래차 대기업 말고도 유치 항목을) — 광업·제조업조사 대구 중분류 부가가치 ÷ 출하액
    elec: ratio('전기장비 제조업'), pharma: ratio('의료용 물질 및 의약품 제조업'), chem: ratio('화학물질 및 화학제품 제조업; 의약품 제외'),
    metal: ratio('금속가공제품 제조업; 기계 및 가구 제외'), food: ratio('식료품 제조업'), textile: ratio('섬유제품 제조업; 의복제외'), mfg: ratio('제조업(10~34)'),
  };
  let panel: Record<string, number | null> = {};
  try {
    const P = JSON.parse(fs.readFileSync('data/kosis/structure_report.json', 'utf-8')).data?.panel ?? {};
    const c = (dep: string) => P?.[dep]?.['Δln(산업집중도)']?.coef ?? null;
    panel = { grdp: c('GRDP'), prod: c('노동생산성'), exp: c('수출'), grdpSe: P?.GRDP?.['Δln(산업집중도)']?.se ?? null };
  } catch { /* 없음 */ }
  const io = ioSectors();
  const ioByItem: Record<string, IoSector> = {};
  for (const [id, sec] of Object.entries(PLANT_IO_SECTOR)) if (io[sec]) ioByItem[id] = io[sec];
  return { tourYear: ty ?? '', tourMix, mfgYear: my, mfgYears: myears, vaRatio, vaRange, turnover, turnoverYear, panel, tour: tourismPerVisit(), med: medicalInflow(), ioByItem, ioFilled: Object.values(io).some(x => x.k != null) };
}
