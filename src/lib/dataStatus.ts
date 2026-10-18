/** /stats/status/ 자료 갱신 현황(운영자 지시 2026-10-17 '통계는 어떻게 해결해? → 진행해').
 *  출처마다 최근 시점·받은 날·다음 공표 예정(어림)을 빌드 때 데이터 파일에서 읽는다. 예정보다 늦으면 '갱신 지연' — 원 통계가 늦었는지 수집이 막혔는지는
 *  이 표가 가리지 않는다(확인할 곳을 알리는 표시일 뿐). 다음 공표 예정 = 다음 시점의 끝 + 공표까지 걸리는 날(LAG, 원 통계의 평소 공표 시기로 어림). */
import fs from 'node:fs';
import path from 'node:path';
import { readCsv } from './csv';
import type { Badge } from './keyIndicators';

export type Cycle = 'M' | 'Q' | 'H' | 'Y';
export type FeedStatus = '정상' | '갱신 지연' | '수시' | '끝난 표';
export type Feed = { group: string; name: string; table?: string; org: string; badge: Badge; cycle: Cycle | null; latest: string; latestLabel: string; fetched: string; next: string; status: FeedStatus; url?: string; href?: string; note?: string };

const GRACE = 10;   // 예정일 뒤 이만큼은 기다린다(일)
/** KOSIS 표별 공표까지 걸리는 날(다음 시점의 끝에서) — 원 통계의 평소 공표 시기. 없으면 주기 기본값. */
const LAG_KOSIS: Record<string, number> = {
  'labor-force-sido': 15, 'self-employed-sido': 15, 'population-sigungu-monthly': 12, 'migration-sido': 26,
  'mfg-production-index-industry': 31, 'mfg-production-index-sido': 31, 'large-retail-index-sido': 31, 'construction-orders-sido': 40,
  'market-bsi-sido': 5, 'smb-bsi-sido': 5, 'startup-trend-sido': 80, 'service-index-sido': 50,
  'labor-force-sido-annual-all': 20, 'population-sido': 20, 'migration-age-sido': 30, 'retail-sales-index-sido': 60, 'export-region': 60, 'export-region-index': 60,
  'grdp-sido-industry-all': 350, 'grdp-sido-industry': 350, 'grdp-sido-expenditure': 350, 'mining-mfg-survey-sido': 350, 'mfg-tangible-sido': 350,
  'biz-birth-death-sido': 350, 'biz-census-sido-industry-all': 350, 'sme-stats-sido': 245, 'sme-workers-sido': 245,   // 전국사업체조사는 9월 보도자료·12월 KOSIS 사업체·종사자, 중소기업기본통계 8월쯤
  'foreign-residents-sido': 320, 'mice-conference-sido': 365, 'mice-exhibition-sido': 365,
  'medical-use-sido-resident': 300, 'medical-use-sido-provider': 300, 'medical-use-sido-outside': 300, 'medical-use-sgg-provider-outside': 300,
  'employed-industry-sido': 110, 'regional-employment-sigungu': 110,
};
const LAG_DEFAULT: Record<Cycle, number> = { M: 45, Q: 60, H: 120, Y: 365 };
/** 더 이어지지 않는 표 — 지연으로 세지 않는다 */
const ENDED: Record<string, string> = {
  'startup-trend-sido-prev': '2025년까지의 표 — 2026년부터는 새 표(한국표준산업분류 11차)로 이어짐',
  'bsi-region': 'ECOS 의 대구 값이 2025년 9월에서 멈춤 — 그 뒤는 한국은행 대구경북본부 「대구경북지역 주요 경제지표」로 이음',
};

/** 표별 비고 — 새 표 번호를 찾았거나 원 기관 발표와 KOSIS 수록이 어긋날 때(2026-10-17 확인) */
const NOTE: Record<string, string> = {
  'biz-census-sido-industry-all': '2026-10-17 부터 11차 산업분류 표(DT_1K52F01)로 받음',
  'employed-industry-sido': '2026-10-17 부터 11차 산업분류 표(DT_1ES3B05J, 2013년부터 소급)로 받음',
  'sme-stats-sido': '2024년 기준은 2026-08 발표 — KOSIS 표에는 아직 2023년까지',
  'sme-workers-sido': '2024년 기준은 2026-08 발표 — KOSIS 표에는 아직 2023년까지',
  'regional-employment-sigungu': '2026-10-17 부터 11차 산업분류 표(DT_1ES3A30S)로 받음',
};
/** 시점 문자열 → { y, i }(i: 월 1~12, 분기 1~4, 반기 1~2, 연 1) */
function parsePeriod(c: Cycle, s: string): { y: number; i: number } | null {
  const t = s.replace(/[^0-9Q]/g, '');
  if (c === 'Y') return /^\d{4}/.test(t) ? { y: Number(t.slice(0, 4)), i: 1 } : null;
  if (c === 'M') return /^\d{6}$/.test(t) ? { y: Number(t.slice(0, 4)), i: Number(t.slice(4)) } : null;
  if (c === 'Q') { const m = s.match(/^(\d{4})(?:0|Q|-)?([1-4])$/); return m ? { y: Number(m[1]), i: Number(m[2]) } : null; }
  const m = s.match(/^(\d{4})0?([12])$/); return m ? { y: Number(m[1]), i: Number(m[2]) } : null;
}
const PER: Record<Cycle, number> = { M: 12, Q: 4, H: 2, Y: 1 };
const endOf = (c: Cycle, y: number, i: number) => { const mo = (12 / PER[c]) * i; return new Date(Date.UTC(y, mo, 0)); };   // 그 시점 마지막 날
export const periodLabel = (c: Cycle, s: string) => {
  const p = parsePeriod(c, s);
  if (!p) return s;
  return c === 'Y' ? `${p.y}년` : c === 'M' ? `${p.y}년 ${p.i}월` : c === 'Q' ? `${p.y}년 ${p.i}분기` : `${p.y}년 ${p.i === 1 ? '상' : '하'}반기`;
};
const kstToday = () => new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Seoul' });
export const buildDate = kstToday;

function judge(c: Cycle | null, latest: string, lag: number | null, ended?: string): { next: string; status: FeedStatus } {
  if (ended) return { next: '—', status: '끝난 표' };
  const p = c && parsePeriod(c, latest);
  if (!c || !p || lag == null) return { next: '수시', status: '수시' };
  let { y, i } = p; i += 1; if (i > PER[c]) { y += 1; i = 1; }
  const due = new Date(endOf(c, y, i).getTime() + lag * 864e5);
  const today = new Date(`${kstToday()}T00:00:00Z`);
  const late = today.getTime() > due.getTime() + GRACE * 864e5;
  const nextLabel = c === 'Y' ? `${y}년` : c === 'M' ? `${y}년 ${i}월` : c === 'Q' ? `${y}년 ${i}분기` : `${y}년 ${i === 1 ? '상' : '하'}반기`;
  return { next: `${nextLabel}분 — ${due.getUTCFullYear()}년 ${due.getUTCMonth() + 1}월쯤`, status: late ? '갱신 지연' : '정상' };
}

const readJson = (p: string) => { try { return JSON.parse(fs.readFileSync(p, 'utf-8')); } catch { return null; } };
const latestFile = (dir: string, re: RegExp) => fs.existsSync(dir) ? fs.readdirSync(dir).filter(f => re.test(f)).sort().at(-1) ?? '' : '';
const maxOf = (vs: string[]) => vs.filter(Boolean).sort().at(-1) ?? '';

export function dataFeeds(): Feed[] {
  const out: Feed[] = [];
  const push = (f: Omit<Feed, 'latestLabel' | 'next' | 'status'> & { lag: number | null; ended?: string }) => {
    const { lag, ended, ...rest } = f;
    const j = judge(f.cycle, f.latest, lag, ended);
    out.push({ ...rest, latestLabel: f.cycle ? periodLabel(f.cycle, f.latest) : f.latest, ...j, note: ended ?? f.note });
  };
  // 국가데이터처 KOSIS(다른 부처 승인통계 포함) — 받은 표 전부
  for (const fn of fs.readdirSync('data/kosis').filter(f => f.endsWith('.json')).sort()) {
    const d = readJson(path.join('data/kosis', fn));
    if (!d?.tbl_nm || !d.prd_se || !d.latest) continue;
    const c = d.prd_se as Cycle;
    push({ group: 'KOSIS 통계표', name: String(d.name ?? d.tbl_nm).split(' — ')[0], table: d.tbl_nm, org: 'KOSIS', badge: '국가통계', cycle: c, latest: d.latest, fetched: d.fetched ?? '', url: d.source_url, note: NOTE[d.key], lag: LAG_KOSIS[d.key] ?? LAG_DEFAULT[c], ended: ENDED[d.key] });
  }
  // 한국은행 ECOS
  for (const fn of fs.readdirSync('data/ecos').filter(f => f.endsWith('.json')).sort()) {
    const d = readJson(path.join('data/ecos', fn));
    if (!d?.stat_name || !d.cycle || !d.latest) continue;
    const c = d.cycle as Cycle;
    push({ group: '한국은행 ECOS', name: String(d.name ?? d.stat_name).split(' — ')[0], table: String(d.stat_name).replace(/^[\d.]+\s*/, ''), org: '한국은행', badge: '국가통계', cycle: c, latest: d.latest, fetched: d.fetched ?? '', url: d.source_url, lag: c === 'Q' ? 75 : d.key === 'ccsi-region' ? 20 : 70, ended: ENDED[d.key] });
  }
  // 기관 자료 — 보도자료·간행물·공시
  const tr = latestFile('data/trade', /^\d{6}\.json$/);
  if (tr) push({ group: '기관 자료·공시', name: '대구·경북지역 수출입 현황(월간)', org: '대구본부세관', badge: '기관 자료', cycle: 'M', latest: tr.slice(0, 6), fetched: '', href: '/stats/trade/', url: 'https://www.customs.go.kr/daegu/na/ntt/selectNttList.do?mi=3867&bbsId=1525', lag: 18 });
  const dpis = fs.existsSync('data/refs') ? fs.readdirSync('data/refs').filter(f => /^dpi-\d{4}-\d{2}-daegu-economic-trends\.json$/.test(f)).sort().map(f => readJson(path.join('data/refs', f))).filter(Boolean) : [];
  const dpiLatest = maxOf(dpis.flatMap((x: { indicators?: { name: string; ref_month: string }[] }) => (x.indicators ?? []).filter(i => i.name === '경기동행지수').map(i => i.ref_month)));
  if (dpiLatest) push({ group: '기관 자료·공시', name: '경기종합지수·자동차 신규등록·자본재 수입(월간)', org: '대구 경기종합지수(대구정책연구원)·국토교통부·관세청', badge: '기관 자료', cycle: 'M', latest: dpiLatest.replace('-', ''), fetched: maxOf(dpis.map((x: { published?: string }) => x.published ?? '')), href: '/stats/monthly/', note: '운영자가 받은 월간 자료에서 옮김', lag: 50 });
  const dg = readJson('data/bok/daegu_tables.json');
  const bsiLatest = maxOf(readCsv('data/bok/dg_bsi.csv').filter(r => r.actual !== '').map(r => r.month));
  if (dg) push({ group: '기관 자료·공시', name: '대구경북지역 주요 경제지표(기업경기실사지수·대구 금융 표)', org: '한국은행 대구경북본부', badge: '기관 자료', cycle: 'M', latest: bsiLatest.replace('-', ''), fetched: dg.issue ? `${dg.issue} 호` : '', href: '/stats/monthly/#bok-daegu', note: '운영자가 받은 PDF 에서 옮김 — 새 호가 오면 갱신', lag: null });
  const rr = readJson('data/bok/regional_report_daegu.json');
  if (rr) push({ group: '기관 자료·공시', name: '지역경제보고서(대구 값)', org: '한국은행', badge: '기관 자료', cycle: null, latest: String(rr.title ?? '').replace(/^.*\((.*)\)$/, '$1'), fetched: rr.made ? `${rr.made} 발간` : '', href: '/stats/monthly/#bok-report', note: '운영자가 받은 PDF 에서 옮김', lag: null });
  const q = readCsv('scripts/data/company_financials_q.csv');
  const qLatest = maxOf(q.map(r => `${r.year}${r.quarter}`));
  if (qLatest) push({ group: '기관 자료·공시', name: '상장회사 분기 실적(주요계정)', org: '금융감독원 DART', badge: '기관 자료', cycle: 'Q', latest: qLatest, fetched: maxOf(q.map(r => r.as_of)), href: '/listed/quarter/', url: 'https://dart.fss.or.kr', lag: 50 });
  const tm = readJson('data/tourism/datalab_meta.json');
  if (tm?.latest_ym) push({ group: '기관 자료·공시', name: '외지인 방문자·관광소비(월간)', org: '한국관광공사 한국관광 데이터랩', badge: '기관 자료', cycle: 'M', latest: tm.latest_ym, fetched: String(tm.fetched_at ?? '').slice(0, 10), href: '/stats/services/', url: tm.page, lag: 55 });
  const cs = readJson('data/complex_stats/index.json');
  const csLatest = maxOf((cs?.files ?? []).map((f: { quarter: string }) => f.quarter));
  if (csLatest) push({ group: '기관 자료·공시', name: '전국산업단지현황통계(대구 단지별 입주·가동)', org: '한국산업단지공단', badge: '기관 자료', cycle: 'Q', latest: csLatest, fetched: '', href: '/dashboard/#complex-output', note: '생산·수출·고용은 2025년 3분기부터 공표 중지', lag: 75 });
  const nt = readCsv('data/complex_trend/daegu_national.csv').filter(r => r.freq === 'Q').map(r => r.period).at(-1);
  if (nt) push({ group: '기관 자료·공시', name: '주요국가산업단지 산업동향(대구국가산단)', org: '한국산업단지공단', badge: '기관 자료', cycle: 'Q', latest: nt, fetched: '', href: '/dashboard/#national-trend', note: '생산·수출·고용·가동률 — 2025년 3분기 뒤에도 공표', lag: 75 });
  const ss = maxOf(readCsv('data/complexes/trend.csv').map(r => r.quarter));
  if (ss) push({ group: '기관 자료·공시', name: '성서산단 입주업체 경기동향(분기)', org: '대구성서산업단지관리공단', badge: '기관 자료', cycle: 'Q', latest: ss, fetched: '', href: '/dashboard/#h-prod', lag: 75 });
  const dl = maxOf(readCsv('data/complexes/monthly.csv').map(r => r.month));
  if (dl) push({ group: '기관 자료·공시', name: '달성1차산업단지 생산·수출(월간)', org: '달성1차산업단지관리공단', badge: '기관 자료', cycle: 'M', latest: dl.replace('-', ''), fetched: '', href: '/dashboard/#h-prod', lag: 75 });
  const md = maxOf(readCsv('data/mfds/device_region.csv').map(r => r.year));
  if (md) push({ group: '기관 자료·공시', name: '의료기기 생산·수출입 실적(지역별)', org: '식품의약품안전처', badge: '기관 자료', cycle: 'Y', latest: md, fetched: '', href: '/stats/manufacturing/', lag: 200 });
  // 행정자료 — 이 사이트가 명단·등록 자료를 모아 센 값
  const ms = latestFile('data/stats/monthly', /^\d{6}\.json$/);
  const mj = ms ? readJson(path.join('data/stats/monthly', ms)) : null;
  if (mj?.sources?.factoryon?.as_of) push({ group: '행정자료', name: '공장등록 현황(기업 사전)', org: '한국산업단지공단 팩토리온', badge: '행정자료', cycle: 'M', latest: mj.sources.factoryon.as_of.replace('-', ''), fetched: '', href: '/companies/', lag: 8 });
  const np = latestFile('data/nps', /^\d{6}\.csv$/);
  if (np) push({ group: '행정자료', name: '국민연금 가입 사업장(고용 인원)', org: '국민연금공단(공공데이터포털)', badge: '행정자료', cycle: 'M', latest: np.slice(0, 6), fetched: String(mj?.generated ?? '').slice(0, 10), href: mj ? `/stats/${mj.month}/` : '/dashboard/', note: '달마다 기업 사전과 이어 고용·취득·상실을 셈', lag: 40 });
  return out;
}
