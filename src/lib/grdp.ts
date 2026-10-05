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
  const y1 = years.at(-1) ?? 0, y0 = Math.max(years[0] ?? 0, y1 - 10);
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

/** 제조업 업종별 시나리오(지역소득 제조업 7개 업종). 기여(%p) = 최근 연도 GRDP 대비 명목 비중 × 가정한 실질 성장률.
 *  가정: 대구 10년 추세 / 감소 멈춤(마이너스 업종 0%) / 전국 같은 업종 10년 성장률 / 대구 추세·전국 중 높은 쪽(감소는 0) /
 *  17개 시도 가운데 그 업종 10년 성장률 상위 3곳 평균 / 대구 그 업종의 10년 중 가장 높았던 해. 순위·평가가 아니라 비교 기준이다. */
export const MFG_SUB: [string, string][] = [
  ['음식료품 및 담배제조업', '음식료품·담배'], ['섬유 의복 및 가죽 제품 제조업', '섬유·의복·가죽'], ['목재종이인쇄 및 복제업', '목재·종이·인쇄'],
  ['석탄 및 석유 화학제품 제조업', '석유·화학'], ['비금속광물 및 금속제품 제조업', '비금속광물·금속'], ['전기 전자 및 정밀기기 제조업', '전기·전자·정밀기기'],
  ['기계 운송장비 및 기타 제품 제조업', '기계·운송장비·기타'],
];
export function mfgScenarios(region = '대구광역시') {
  const V = new Map<string, number>();
  const regions = new Set<string>();
  for (const r of readCsv('data/kosis/grdp-sido-industry-all.csv')) {
    if (r.DT === '' || !Number.isFinite(Number(r.DT))) continue;
    V.set(`${r.ITM_NM}|${r.C1_NM}|${r.C2_NM}|${r.PRD_DE}`, Number(r.DT)); regions.add(r.C1_NM);
  }
  const years = [...new Set([...V.keys()].map(k => Number(k.split('|')[3])))].sort();
  const y1 = years.at(-1) ?? 0, y0 = Math.max(years[0] ?? 0, y1 - 10), n = y1 - y0;
  const v = (i: string, reg: string, k: string, y: number) => V.get(`${i}|${reg}|${k}|${y}`);
  const cagr = (reg: string, k: string) => { const a = v('실질', reg, k, y0), b = v('실질', reg, k, y1); return a && b ? ((b / a) ** (1 / n) - 1) * 100 : null; };
  const nom = v('명목', region, '지역내총생산(시장가격)', y1);
  if (!nom) return null;
  const sido = [...regions].filter(r => r !== '전국');
  const rows = MFG_SUB.map(([k, name]) => {
    const share = ((v('명목', region, k, y1) ?? 0) / nom) * 100;
    const g = cagr(region, k) ?? 0, gn = cagr('전국', k) ?? 0;
    const cs = sido.map(r => cagr(r, k)).filter((x): x is number => x != null).sort((a, b) => b - a);
    const top3 = cs.slice(0, 3).reduce((a, b) => a + b, 0) / Math.min(3, cs.length || 1);
    const yy = Array.from({ length: n }, (_, j) => { const a = v('실질', region, k, y0 + j), b = v('실질', region, k, y0 + j + 1); return a && b ? (b / a - 1) * 100 : -Infinity; });
    const best = Math.max(...yy);
    const c = (x: number) => share * x / 100;
    return { key: k, name, share, g, gn, top3, best, trend: c(g), stop: c(Math.max(g, 0)), nat: c(gn), mix: c(Math.max(g, gn, 0)), top: c(top3), bestC: c(best), need01: 0.1 / share * 100 };
  });
  const sum = (f: (r: typeof rows[number]) => number) => rows.reduce((a, r) => a + f(r), 0);
  const mfgShare = sum(r => r.share);
  return { rows, y0, y1, mfgShare, mfgCagr: cagr(region, '제조업') ?? 0, natMfgCagr: cagr('전국', '제조업') ?? 0,
    tot: { trend: sum(r => r.trend), stop: sum(r => r.stop), nat: sum(r => r.nat), mix: sum(r => r.mix), top: sum(r => r.top), bestC: sum(r => r.bestC) } };
}
