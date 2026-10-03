import { kosis, kosisMeta, shift, type Series, type Pt } from './monthly';
import { readCsv } from './csv';

/** /stats/services/ 서비스업·자영업(운영자 지시 2026-10-02: 서비스업·관광·자영업 통계 추가, 1단계 KOSIS).
 *  KOSIS 서비스업동향조사(시도 서비스업생산지수 분기·대형소매점 판매액지수 월), 경제활동인구조사(종사상지위별 취업자 월),
 *  소상공인시장경기동향조사(전통시장 체감·전망 BSI 월). 값 그대로, 비중은 같은 표 안의 나눗셈. 평가 없음. */
const src = (key: string, org = '국가데이터처') => { const m = kosisMeta('data/kosis', key); return { source: `${org} 「${m.tbl_nm ?? ''}」(KOSIS)`, url: m.source_url ?? '' }; };

export const SVC_KEY = ['총지수', '도매 및 소매업', '숙박 및 음식점업', '보건업 및 사회복지 서비스업', '정보통신업', '예술 스포츠 및 여가관련 서비스업', '운수 및 창고업', '교육 서비스업'];

export function serviceSeries(): Series[] {
  const s = src('service-index-sido');
  return SVC_KEY.map((c2, i) => ({
    key: `svc${i}`, group: '서비스업 생산', name: c2 === '총지수' ? '서비스업 생산지수(총지수)' : c2, unit: '2020=100', change: '%' as const, digits: 1,
    pts: kosis('service-index-sido', r => r.ITM_NM === '불변지수' && r.C2_NM === c2, true), ...s, note: '불변지수, 분기', quarterly: true,
  })).filter(x => x.pts.length);
}

/** 최근 분기 업종별 불변지수와 전년 같은 분기 대비(같은 표 안의 나눗셈). */
export function serviceIndustryRows(): { q: string; rows: { name: string; v: number | null; yoy: number | null }[]; source: string; url: string } {
  const s = src('service-index-sido');
  const names = new Set<string>(['총지수']);   // 총지수 먼저, 나머지는 표의 행 순서
  const byName = new Map<string, Pt[]>();
  const rows = kosisRows('service-index-sido');
  for (const r of rows) if (r.ITM_NM === '불변지수') names.add(r.C2_NM);
  for (const n of names) byName.set(n, kosis('service-index-sido', r => r.ITM_NM === '불변지수' && r.C2_NM === n, true));
  const q = [...byName.values()].flatMap(p => p.map(x => x.m)).sort().at(-1) ?? '';
  const out = [...names].map(name => {
    const pts = byName.get(name) ?? [];
    const v = pts.find(p => p.m === q)?.v ?? null, v0 = pts.find(p => p.m === shift(q, -12))?.v ?? null;
    return { name, v, yoy: v != null && v0 ? (v / v0 - 1) * 100 : null };
  });
  return { q, rows: out, ...s };
}
const kosisRows = (key: string) => readCsv(`data/kosis/${key}.csv`);

export function retailSeries(): Series[] {
  const s = src('large-retail-index-sido');
  return [['대형소매점', '대형소매점 판매액지수'], ['백화점', '백화점 판매액지수'], ['대형마트', '대형마트 판매액지수']].map(([k, name], i) => ({
    key: `rt${i}`, group: '소매 판매', name, unit: '2020=100', change: '%' as const, digits: 1,
    pts: kosis('large-retail-index-sido', r => r.ITM_NM === `${k} 불변지수`), ...s, note: '불변지수',
  })).filter(x => x.pts.length);
}

export function selfEmployedSeries(): Series[] {
  const s = src('self-employed-sido');
  const get = (c2: string) => kosis('self-employed-sido', r => r.C2_NM === c2);
  const list: Series[] = [
    ['*자영업자', '자영업자'], ['-고용원이 있는 자영업자', '고용원이 있는 자영업자'], ['-고용원이 없는 자영업자', '고용원이 없는 자영업자'], ['-무급가족종사자', '무급가족종사자'],
  ].map(([c2, name], i) => ({ key: `se${i}`, group: '자영업', name, unit: '천 명', change: '%' as const, digits: 1, pts: get(c2), ...s }));
  // 자영업자 비중 = 자영업자 ÷ 취업자 계 × 100 (같은 표 안의 나눗셈)
  const tot = new Map(get('계').map(p => [p.m, p.v]));
  const share = get('*자영업자').filter(p => tot.get(p.m)).map(p => ({ m: p.m, v: Math.round((p.v / tot.get(p.m)!) * 1000) / 10 }));
  list.push({ key: 'seS', group: '자영업', name: '자영업자 비중(취업자 대비)', unit: '%', change: '%p', digits: 1, pts: share, ...s, note: '자영업자 ÷ 취업자 계, 이 사이트 계산' });
  return list.filter(x => x.pts.length);
}

/** 소상공인시장경기동향조사(소상공인 DT_S0001N_005·전통시장 DT_S0001N_006)의 대구 체감(이번 달)·전망(다음 달) BSI. */
export function marketSeries(): Series[] {
  const out: Series[] = [];
  for (const [key, who] of [['smb-bsi-sido', '소상공인'], ['market-bsi-sido', '전통시장']] as const) {
    const s = src(key, '소상공인시장진흥공단');
    for (const [itm, label] of [['체감', '체감경기'], ['전망', '다음 달 전망']] as const) {
      out.push({ key: `mk-${key}-${itm}`, group: '소상공인·전통시장', name: `${who} ${label}(BSI)`, unit: '지수', change: 'p', digits: 1,
        pts: kosis(key, r => r.ITM_NM === itm && r.C1_NM === '대구'), ...s, note: '100 넘으면 전월보다 좋다는 응답이 많음' });
    }
  }
  return out.filter(x => x.pts.length);
}
