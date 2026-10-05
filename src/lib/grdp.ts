import fs from 'node:fs';
import { readCsv } from './csv';

/** 대구 GRDP 성장 목표 계산기(/stats/industry/, 운영자 지시 2026-10-05) 데이터.
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
const TOT = '지역내총생산(시장가격)';
export type GrdpItem = { key: string; name: string; share: number; cagr: number; avgc: number; last: number | null };
export function grdpCalcData(region = '대구광역시') {
  const f = 'data/kosis/grdp-sido-industry-all.csv';
  const V = new Map<string, number>();
  for (const r of readCsv(f)) if (r.C1_NM === region && r.DT !== '' && Number.isFinite(Number(r.DT))) V.set(`${r.ITM_NM}|${r.C2_NM}|${r.PRD_DE}`, Number(r.DT));
  const years = [...new Set([...V.keys()].map(k => Number(k.split('|')[2])))].sort();
  const y1 = years.at(-1) ?? 0, y0 = Math.max(years[0] ?? 0, y1 - 10);
  const n = y1 - y0;
  const v = (i: string, k: string, y: number) => V.get(`${i}|${k}|${y}`);
  const nom = v('명목', TOT, y1) ?? 0;
  const items: GrdpItem[] = GRDP_COMP.map(([k, name]) => {
    const r1 = v('실질', k, y1), r0 = v('실질', k, y0);
    const cs = Array.from({ length: n }, (_, j) => v('실질기여도', k, y0 + 1 + j) ?? 0);
    return { key: k, name, share: ((v('명목', k, y1) ?? 0) / nom) * 100, cagr: r1 && r0 ? ((r1 / r0) ** (1 / n) - 1) * 100 : 0,
      avgc: cs.reduce((a, b) => a + b, 0) / n, last: v('실질기여도', k, y1) ?? null };
  });
  const growth = years.slice(1).filter(y => y > y0).map(y => ({ y, g: ((v('실질', TOT, y) ?? 0) / (v('실질', TOT, y - 1) ?? 1) - 1) * 100 }));
  const cagr = ((v('실질', TOT, y1) ?? 0) / (v('실질', TOT, y0) ?? 1)) ** (1 / n) * 100 - 100;
  const meta = (() => { try { return JSON.parse(fs.readFileSync('data/kosis/grdp-sido-industry-all.json', 'utf-8')); } catch { return {}; } })();
  return { items, growth, cagr, y0, y1, nomTrillion: nom / 1e6, source: `국가데이터처 「${meta.tbl_nm ?? '시도별 경제활동별 지역내총생산'}」(KOSIS)`, url: meta.source_url ?? '' };
}
