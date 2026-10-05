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
export type StructRow = { key: string; name: string; share: number; nat: number; lq: number; va: number; g: number; gn: number; t3: number; high: boolean; spec: boolean; mfg: boolean };
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
  const rows: StructRow[] = LEAVES.map(([k, name]) => {
    const va = v('명목', region, k, y1) ?? 0, share = va / tot * 100, nat = (v('명목', '전국', k, y1) ?? 0) / natTot * 100;
    const g = cagr(region, k) ?? 0;
    const cs = sido.map(r => cagr(r, k)).filter((x): x is number => x != null).sort((a, b) => b - a);
    return { key: k, name, share, nat, lq: nat ? share / nat : 0, va: va / 100, g, gn: cagr('전국', k) ?? g,
      t3: cs.length ? cs.slice(0, 3).reduce((a, b) => a + b, 0) / Math.min(3, cs.length) : g, high: HIGH.includes(k), spec: nat > 0 && share / nat >= 1, mfg: MFG.includes(k) };
  }).filter(r => r.share > 0);
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
    k: io && io.vaIn != null ? (1 - (io.importShare ?? 0) / 100) * io.vaIn : null, io,
    report: '/posts/2026-09-30-policy-structure-daegu/',
  };
}
