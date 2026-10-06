import { kosis, kosisMeta, shift, daeguRow, type Series, type Pt } from './monthly';
import fs from 'node:fs';
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
const kosisRows = (key: string) => readCsv(`data/kosis/${key}.csv`).filter(daeguRow);

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

/** 관광(운영자 지시 2026-10-03: '화면에서 볼 수 있으면 가져오라') — 한국관광 데이터랩 「지역별 관광 현황」 화면 값(scripts/fetch_datalab.py).
 *  방문자: 이동통신, 외지인(그 지역 밖 거주자) 연인원, 명 → 만 명(÷10,000). 관광소비: 신용카드, 천원 → 억 원(÷100,000).
 *  데이터랩 안내대로 총량이 아니라 추세용으로 적는다. 구·군 값은 그 구·군 밖 방문자 기준이라 더해도 대구 값이 아니다. */
export const DATALAB_URL = 'https://datalab.visitkorea.or.kr/datalab/portal/loc/getAreaDataForm.do';
export const DATALAB_SRC = '한국관광공사 한국관광 데이터랩 「지역별 관광 현황」';
export const SPEND_IND = ['쇼핑업', '식음료업', '운송업', '여가서비스업', '의료웰니스업', '숙박업', '여행업'];
const dlYm = (s: string) => `${s.slice(0, 4)}-${s.slice(4)}`;
const dlVisit = () => readCsv('data/tourism/datalab_visitors.csv');
const dlSpend = () => readCsv('data/tourism/datalab_spend.csv');
const toEok = (v: string) => Math.round(Number(v) / 1000) / 100;   // 천원 → 억 원(소수 둘째 자리)
/** 관광빅데이터 정보서비스 오픈API(scripts/fetch_tourism.py, 키 DATA_GO_KR_KEY) — 현지인·외지인·외국인 일별 방문자를 달마다 더한 값(연인원).
 *  그 달 날짜가 다 있는 달만 쓴다(덜 찬 달은 합계가 작게 나온다). */
export const TOUR_API_SRC = '한국관광공사 관광빅데이터 정보서비스(공공데이터포털 오픈API)';
export const TOUR_API_URL = 'https://www.data.go.kr/data/15101972/openapi.do';
const apiVisit = () => readCsv('data/tourism/visitors_monthly.csv').filter(r => {
  const [y, m] = r.month.split('-').map(Number);
  return Number(r.days) === new Date(y, m, 0).getDate();
});
const apiPts = (code: string, div: string): Pt[] => apiVisit().filter(r => r.code === code && r.tou_div.startsWith(div))
  .map(r => ({ m: r.month, v: Math.round(Number(r.visitors) / 1000) / 10 })).sort((a, b) => a.m.localeCompare(b.m));
export function tourismMeta(): { latest: string; fetched: string } {
  const f = 'data/tourism/datalab_meta.json';
  const m = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf-8')) : {};
  return { latest: m.latest_ym ? dlYm(m.latest_ym) : '', fetched: m.fetched_at ?? '' };
}
export function tourismSeries(): Series[] {
  const V = dlVisit().filter(r => r.code === '27');
  const S = dlSpend().filter(r => r.code === '27' && r.industry === '전체');
  const share = readCsv('data/tourism/datalab_spend_share.csv').filter(r => r.group === '내국인');
  const base = { group: '관광', source: DATALAB_SRC, url: DATALAB_URL };
  const spend = (g: string): Pt[] => S.filter(r => r.group === g).map(r => ({ m: dlYm(r.ym), v: toEok(r.amount_thousand_won) })).sort((a, b) => a.m.localeCompare(b.m));
  return [
    { ...base, key: 'tvis', name: '외지인 방문자 수', unit: '만 명', change: '%' as const, digits: 0, note: '이동통신, 연인원',
      pts: V.map(r => ({ m: dlYm(r.ym), v: Math.round(Number(r.visitors) / 1000) / 10, yoy: r.yoy_pct === '' ? null : Number(r.yoy_pct) })).sort((a, b) => a.m.localeCompare(b.m)) },
    { ...base, key: 'tfor', name: '외국인 방문자 수', unit: '만 명', change: '%' as const, digits: 1, note: '이동통신, 연인원', source: TOUR_API_SRC, url: TOUR_API_URL, pts: apiPts('27', '외국인') },
    { ...base, key: 'tloc', name: '현지인 방문자 수', unit: '만 명', change: '%' as const, digits: 0, note: '대구 주민의 대구 안 이동, 이동통신, 연인원', source: TOUR_API_SRC, url: TOUR_API_URL, pts: apiPts('27', '현지인') },
    { ...base, key: 'tsp', name: '관광소비(내국인)', unit: '억 원', change: '%' as const, digits: 0, note: '신용카드', pts: spend('내국인') },
    { ...base, key: 'tspo', name: '외지인 관광소비', unit: '억 원', change: '%' as const, digits: 0, note: '신용카드', pts: spend('외지인') },
    { ...base, key: 'tshare', name: '관광소비 전국 대비 비중', unit: '%', change: '%p' as const, digits: 1, note: '내국인, 데이터랩 계산값',
      pts: share.map(r => ({ m: dlYm(r.ym), v: Number(r.share_pct) })).sort((a, b) => a.m.localeCompare(b.m)) },
  ].filter(s => s.pts.length);
}
/** 업종별 관광소비(내국인, 최근 달): 억 원, 같은 달 전체 대비 비중, 전년 같은 달 대비 */
export function tourismIndustryRows(): { m: string; total: number | null; rows: { name: string; v: number | null; share: number | null; yoy: number | null }[] } {
  const S = dlSpend().filter(r => r.code === '27' && r.group === '내국인');
  const last = S.map(r => r.ym).sort().at(-1) ?? '';
  if (!last) return { m: '', total: null, rows: [] };
  const prev = `${Number(last.slice(0, 4)) - 1}${last.slice(4)}`;
  const get = (ym: string, ind: string) => { const r = S.find(x => x.ym === ym && x.industry === ind); return r ? toEok(r.amount_thousand_won) : null; };
  const total = get(last, '전체');
  const rows = SPEND_IND.map(name => { const v = get(last, name), v0 = get(prev, name);
    return { name, v, share: v != null && total ? (v / total) * 100 : null, yoy: v != null && v0 ? (v / v0 - 1) * 100 : null }; });
  return { m: dlYm(last), total, rows };
}
/** 구·군별(최근 달): 외지인 방문자(만 명, 전년 같은 달 대비는 데이터랩 값)·관광소비(내국인, 억 원) */
export function tourismDistrictRows(): { m: string; rows: { name: string; vis: number | null; visYoy: number | null; fr: number | null; sp: number | null; spYoy: number | null }[] } {
  const V = dlVisit(), S = dlSpend().filter(r => r.group === '내국인' && r.industry === '전체');
  const last = V.map(r => r.ym).sort().at(-1) ?? '';
  const prev = last ? `${Number(last.slice(0, 4)) - 1}${last.slice(4)}` : '';
  const codes = [...new Set(V.filter(r => r.code !== '27').map(r => r.code))].sort();
  const rows = codes.map(c => {
    const v = V.find(r => r.code === c && r.ym === last);
    const s = S.find(r => r.code === c && r.ym === last), s0 = S.find(r => r.code === c && r.ym === prev);
    const sp = s ? toEok(s.amount_thousand_won) : null, sp0 = s0 ? toEok(s0.amount_thousand_won) : null;
    const fr = last ? apiPts(c, '외국인').find(p => p.m === dlYm(last))?.v ?? null : null;
    return { name: v?.region ?? c, vis: v ? Math.round(Number(v.visitors) / 1000) / 10 : null, visYoy: v && v.yoy_pct !== '' ? Number(v.yoy_pct) : null, fr,
      sp, spYoy: sp != null && sp0 ? (sp / sp0 - 1) * 100 : null };
  });
  return { m: last ? dlYm(last) : '', rows };
}
