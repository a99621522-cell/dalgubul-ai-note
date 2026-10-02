import fs from 'node:fs';
import path from 'node:path';
import { readCsv } from './csv';

/** /stats/monthly/ 월간 대구 경제지표(운영자 지시 2026-10-02).
 *  원 통계로 받는 지표는 원 통계에서 직접 읽는다: KOSIS(data/kosis — 광공업생산지수·경제활동인구·인구이동), ECOS(data/ecos — 소비자심리·연체율·어음부도율·대출금).
 *  원 통계를 아직 받지 않는 지표(경기종합지수·자동차 등록·건설수주·창업기업·BSI 등)만 대구정책연구원 「월간 대구경제동향」 요약(data/refs/dpi-*.json 의 indicators)을 쓴다.
 *  같은 달 값이 여러 호에 실리면 가장 늦은 호의 값. 전년 같은 달·전월 대비는 같은 계열 안의 나눗셈·뺄셈이거나 자료에 적힌 값이다. 평가 없음. */

export type Pt = { m: string; v: number; yoy?: number | null; mom?: number | null };
export type Series = {
  key: string; group: string; name: string; unit: string; change: '%' | '%p' | 'p'; digits: number;
  pts: Pt[]; source: string; url: string; note?: string; quarterly?: boolean; compiled?: boolean;
};

const ym = (s: string) => (/^\d{6}$/.test(s) ? `${s.slice(0, 4)}-${s.slice(4)}` : s);
const meta = (dir: string, key: string): { source_url?: string; tbl_nm?: string; stat_name?: string; fetched?: string } => {
  const p = path.join(dir, `${key}.json`);
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf-8')) : {};
};

function kosis(key: string, pick: (r: Record<string, string>) => boolean): Pt[] {
  return readCsv(`data/kosis/${key}.csv`).filter(pick).map(r => ({ m: ym(r.PRD_DE), v: Number(r.DT) }))
    .filter(p => /^\d{4}-\d{2}$/.test(p.m) && Number.isFinite(p.v)).sort((a, b) => a.m.localeCompare(b.m));
}
function ecos(key: string, pick: (r: Record<string, string>) => boolean): Pt[] {
  return readCsv(`data/ecos/${key}.csv`).filter(pick).map(r => ({ m: ym(r.TIME), v: Number(r.DATA_VALUE) }))
    .filter(p => /^\d{4}-\d{2}$/.test(p.m) && Number.isFinite(p.v)).sort((a, b) => a.m.localeCompare(b.m));
}

type DpiInd = { name: string; ref_month: string; value: number | null; unit: string; yoy: number | null; mom: number | null; change_unit?: string; note?: string };
type DpiRef = { slug: string; title: string; published: string; public_url: string; indicators?: DpiInd[] };
export const dpiIssues = (): DpiRef[] => {
  const dir = 'data/refs';
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter(f => /^dpi-\d{4}-\d{2}-daegu-economic-trends\.json$/.test(f)).sort()
    .map(f => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf-8')) as DpiRef);
};
/** 연구원 자료의 한 지표 계열 — 같은 기준월은 가장 늦은 호의 값. */
function dpi(name: string): Pt[] {
  const by = new Map<string, Pt>();
  for (const iss of dpiIssues()) {   // published 오름차순이라 뒤 호가 덮어쓴다
    for (const i of iss.indicators ?? []) {
      if (i.name !== name || i.value == null) continue;
      by.set(i.ref_month, { m: i.ref_month, v: i.value, yoy: i.yoy, mom: i.mom });
    }
  }
  return [...by.values()].sort((a, b) => a.m.localeCompare(b.m));
}


export function monthlySeries(): Series[] {
  const mi = meta('data/kosis', 'mfg-production-index-industry');
  const lf = meta('data/kosis', 'labor-force-sido');
  const mg = meta('data/kosis', 'migration-sido');
  const cs = meta('data/ecos', 'ccsi-region');
  const dq = meta('data/ecos', 'bank-delinquency-region');
  const df = meta('data/ecos', 'default-rate-region');
  const ln = meta('data/ecos', 'bank-loans-region');
  const kSrc = (m: typeof mi) => `국가데이터처 KOSIS 「${m.tbl_nm ?? ''}」`;
  const eSrc = (m: typeof cs) => `한국은행 ECOS 「${(m.stat_name ?? '').replace(/^[\d.]+\s*/, '')}」`;
  const mfg = (itm: string) => kosis('mfg-production-index-industry', r => r.ITM_NM === itm && r.C2_NM === '총지수' && r.C1_NM.startsWith('대구'));
  const lab = (itm: string) => kosis('labor-force-sido', r => r.ITM_NM === itm && r.C1_NM.startsWith('대구'));
  const dlq = (itm: string) => ecos('bank-delinquency-region', r => r.ITEM_NAME1 === itm && r.ITEM_NAME2 === '대구');
  const S: Series[] = [
    { key: 'ip', group: '생산', name: '광공업 생산지수', unit: '2020=100', change: '%', digits: 1, pts: mfg('생산지수(원지수)'), source: kSrc(mi), url: mi.source_url ?? '', note: '총지수, 원지수' },
    { key: 'ship', group: '생산', name: '광공업 출하지수', unit: '2020=100', change: '%', digits: 1, pts: mfg('생산자제품 출하지수(원지수)'), source: kSrc(mi), url: mi.source_url ?? '', note: '총지수, 원지수' },
    { key: 'inv', group: '생산', name: '광공업 재고지수', unit: '2020=100', change: '%', digits: 1, pts: mfg('생산자제품 재고지수(원지수)'), source: kSrc(mi), url: mi.source_url ?? '', note: '총지수, 원지수' },
    { key: 'svc', group: '생산', name: '서비스업 생산지수(분기)', unit: '2020=100', change: '%', digits: 1, pts: dpi('대구 서비스업 생산지수(분기)'), compiled: true, source: '국가데이터처 서비스업동향조사', url: '', note: '분기 값, 기준월은 분기 끝 달', quarterly: true },
    { key: 'emp', group: '고용·인구', name: '취업자', unit: '천 명', change: '%', digits: 1, pts: lab('취업자'), source: kSrc(lf), url: lf.source_url ?? '' },
    { key: 'er', group: '고용·인구', name: '고용률', unit: '%', change: '%p', digits: 1, pts: lab('고용률'), source: kSrc(lf), url: lf.source_url ?? '', note: '15세 이상' },
    { key: 'ur', group: '고용·인구', name: '실업률', unit: '%', change: '%p', digits: 1, pts: lab('실업률'), source: kSrc(lf), url: lf.source_url ?? '' },
    { key: 'mig', group: '고용·인구', name: '순이동(전입−전출)', unit: '명', change: 'p', digits: 0, pts: kosis('migration-sido', r => r.ITM_NM === '순이동' && r.C1_NM === '대구광역시'), source: kSrc(mg), url: mg.source_url ?? '', note: '증감은 명' },
    { key: 'csi', group: '소비·투자', name: '소비자심리지수(대구경북)', unit: '지수', change: 'p', digits: 1, pts: ecos('ccsi-region', r => r.ITEM_NAME1 === '소비자심리지수'), source: eSrc(cs), url: cs.source_url ?? '' },
    { key: 'retail', group: '소비·투자', name: '대형소매점 판매액지수', unit: '2020=100', change: '%', digits: 1, pts: dpi('대형소매점 판매액지수'), compiled: true, source: '국가데이터처 서비스업동향조사', url: '', note: '불변지수' },
    { key: 'car', group: '소비·투자', name: '자동차 신규등록', unit: '대', change: '%', digits: 0, pts: dpi('자동차 신규등록대수'), compiled: true, source: '국토교통부 자동차 등록 통계', url: '' },
    { key: 'capm', group: '소비·투자', name: '자본재 수입액', unit: '백만 달러', change: '%', digits: 1, pts: dpi('자본재 수입액'), compiled: true, source: '국가데이터처', url: '' },
    { key: 'cons', group: '소비·투자', name: '건설수주액', unit: '억 원', change: '%', digits: 0, pts: dpi('건설수주액'), compiled: true, source: '국가데이터처 건설경기동향조사', url: '' },
    { key: 'exp', group: '수출입', name: '수출액', unit: '백만 달러', change: '%', digits: 1, pts: dpi('수출액'), compiled: true, source: '한국무역협회', url: '' },
    { key: 'imp', group: '수출입', name: '수입액', unit: '백만 달러', change: '%', digits: 1, pts: dpi('수입액'), compiled: true, source: '한국무역협회', url: '' },
    { key: 'bal', group: '수출입', name: '무역수지', unit: '백만 달러', change: 'p', digits: 1, pts: dpi('무역수지'), compiled: true, source: '한국무역협회', url: '', note: '증감은 백만 달러 차' },
    { key: 'hhd', group: '금융', name: '가계대출 연체율', unit: '%', change: '%p', digits: 2, pts: dlq('가계대출 연체율(전체1M)'), source: eSrc(dq), url: dq.source_url ?? '', note: '국내은행' },
    { key: 'cod', group: '금융', name: '기업대출 연체율', unit: '%', change: '%p', digits: 2, pts: dlq('기업대출 연체율(전체1M)'), source: eSrc(dq), url: dq.source_url ?? '', note: '국내은행' },
    { key: 'smed', group: '금융', name: '중소기업대출 연체율', unit: '%', change: '%p', digits: 2, pts: dlq('중소기업대출 연체율(전체1M)'), source: eSrc(dq), url: dq.source_url ?? '', note: '국내은행' },
    { key: 'loan', group: '금융', name: '원화대출금(예금은행)', unit: '조 원', change: '%', digits: 1, pts: ecos('bank-loans-region', r => r.ITEM_NAME1 === '원화대출금' && r.ITEM_NAME2 === '대구').map(p => ({ ...p, v: p.v / 1000 })), source: eSrc(ln), url: ln.source_url ?? '' },
    { key: 'dft', group: '금융', name: '어음부도율', unit: '%', change: '%p', digits: 2, pts: ecos('default-rate-region', r => r.ITEM_NAME1 === '대구'), source: eSrc(df), url: df.source_url ?? '' },
    { key: 'biz', group: '창업·경기', name: '창업기업 수', unit: '개', change: '%', digits: 0, pts: dpi('창업기업 수'), compiled: true, source: '중소벤처기업부 창업기업동향', url: '' },
    { key: 'cci', group: '창업·경기', name: '경기동행지수', unit: '2020=100', change: '%', digits: 1, pts: dpi('경기동행지수'), compiled: true, source: '대구 경기종합지수(대구정책연구원)', url: '' },
    { key: 'cli', group: '창업·경기', name: '경기선행지수', unit: '2020=100', change: '%', digits: 1, pts: dpi('경기선행지수'), compiled: true, source: '대구 경기종합지수(대구정책연구원)', url: '' },
    { key: 'mbsi', group: '창업·경기', name: '제조업 업황 BSI', unit: '지수', change: 'p', digits: 0, pts: dpi('제조업 업황 BSI'), compiled: true, source: '한국은행 대구경북본부 기업경기조사', url: '' },
    { key: 'nbsi', group: '창업·경기', name: '비제조업 업황 BSI', unit: '지수', change: 'p', digits: 0, pts: dpi('비제조업 업황 BSI'), compiled: true, source: '한국은행 대구경북본부 기업경기조사', url: '' },
  ];
  return S.filter(s => s.pts.length);
}

const shift = (m: string, k: number) => {
  const [y, mo] = m.split('-').map(Number);
  const t = y * 12 + (mo - 1) + k;
  return `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, '0')}`;
};
/** 증감: '%' 는 증감률, '%p'·'p' 는 차. 같은 계열에 비교 달 값이 없으면 자료에 적힌 값(yoy·mom). */
export function change(s: Series, p: Pt, lag: 12 | 1): number | null {
  if (s.quarterly && lag === 1) return null;   // 분기 계열은 전월 대비가 없다
  const given = lag === 12 ? p.yoy : p.mom;
  if (given != null) return given;   // 연구원 자료 계열: 그 호에 적힌 증감을 먼저(앞 달 값은 다른 호에서 와 고쳐진 값과 섞일 수 있다)
  const prev = s.pts.find(q => q.m === shift(p.m, -lag));
  if (prev) return s.change === '%' ? (prev.v ? (p.v / prev.v - 1) * 100 : null) : p.v - prev.v;
  return null;
}

export const latest = (s: Series) => s.pts[s.pts.length - 1];
export const groups = (S: Series[]) => [...new Set(S.map(s => s.group))];
export const fmt = (v: number | null | undefined, d: number) => v == null || !Number.isFinite(v) ? '—' : v.toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d });
export const fmtChg = (v: number | null, unit: string, d = 1) => {
  if (v == null || !Number.isFinite(v)) return '—';
  const k = unit === '명' ? 0 : d, f = 10 ** k;
  const r = Math.round(v * f) / f;
  const n = Math.abs(r).toLocaleString('ko-KR', { minimumFractionDigits: k, maximumFractionDigits: k });
  return `${r > 0 ? '+' : r < 0 ? '△' : ''}${n}`;
};
export const ymLabel = (m: string) => `${m.slice(2, 4)}.${m.slice(5)}`;

/** 최근 n개월 막대 없는 작은 선(인라인 SVG). 값은 표에 함께 있으므로 그림은 흐름만. */
export function spark(s: Series, n = 13): string {
  const pts = s.pts.slice(-n);
  if (pts.length < 2) return '';
  const W = 104, H = 28, P = 3;
  const vs = pts.map(p => p.v), lo = Math.min(...vs), hi = Math.max(...vs), span = hi - lo || 1;
  const x = (i: number) => P + (i * (W - 2 * P)) / (pts.length - 1);
  const y = (v: number) => H - P - ((v - lo) * (H - 2 * P)) / span;
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join('');
  const last = pts.length - 1;
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true" focusable="false"><path d="${d}" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${x(last).toFixed(1)}" cy="${y(pts[last].v).toFixed(1)}" r="3" fill="currentColor"/></svg>`;
}

/** 업종별 생산·출하·재고(KOSIS) — 최근 달 값과 전년 같은 달 대비. */
export function industryRows(): { latest: string; rows: { name: string; ip: number | null; ipYoy: number | null; sh: number | null; shYoy: number | null; inv: number | null; invYoy: number | null }[]; source: string; url: string } {
  const mi = meta('data/kosis', 'mfg-production-index-industry');
  const all = readCsv('data/kosis/mfg-production-index-industry.csv').filter(r => r.C1_NM.startsWith('대구') && r.ITM_NM.endsWith('(원지수)'));
  const lastM = all.map(r => r.PRD_DE).sort().at(-1) ?? '';
  const prevY = lastM ? String(Number(lastM) - 100) : '';
  const val = (itm: string, c2: string, m: string) => { const r = all.find(x => x.ITM_NM === itm && x.C2_NM === c2 && x.PRD_DE === m); return r && r.DT !== '' && Number.isFinite(Number(r.DT)) ? Number(r.DT) : null; };
  const yoy = (a: number | null, b: number | null) => a != null && b ? (a / b - 1) * 100 : null;
  const SKIP = new Set(['총지수', '광업 및 제조업', '제조업', '전기업 및 가스업', '전기 가스 증기 및 공기 조절 공급업']);
  const names = [...new Set(all.filter(r => r.PRD_DE === lastM).map(r => r.C2_NM))].filter(n => !SKIP.has(n));
  const rows = names.map(name => {
    const ip = val('생산지수(원지수)', name, lastM), sh = val('생산자제품 출하지수(원지수)', name, lastM), inv = val('생산자제품 재고지수(원지수)', name, lastM);
    return { name, ip, ipYoy: yoy(ip, val('생산지수(원지수)', name, prevY)), sh, shYoy: yoy(sh, val('생산자제품 출하지수(원지수)', name, prevY)), inv, invYoy: yoy(inv, val('생산자제품 재고지수(원지수)', name, prevY)) };
  });
  return { latest: ym(lastM), rows, source: `국가데이터처 KOSIS 「${mi.tbl_nm ?? ''}」`, url: mi.source_url ?? '' };
}

/** 추세 그림(운영자 지시 2026-10-02: 1월부터, 값 표시). 한 지표 = 한 그림, 선 + 점 + 점마다 값. 가로축은 from~to 의 모든 달(값 없는 달은 비움).
 *  색은 currentColor(페이지 CSS 가 --primary), 글자는 잉크 색. 세로축은 값 범위에 맞춰 위아래 여백을 둔다(0 기준 아님 — 막대가 아니라 선이라). */
export function trendChart(s: Series, from: string, to: string): string {
  const months: string[] = [];
  for (let m = from; m <= to; m = shift(m, 1)) months.push(m);
  const pts = months.map((m, i) => ({ i, m, p: s.pts.find(q => q.m === m) })).filter(x => x.p) as { i: number; m: string; p: Pt }[];
  if (!pts.length) return '';
  const W = 340, H = 180, L = 14, R = 14, T = 26, B = 26;
  const vs = pts.map(x => x.p.v);
  let lo = Math.min(...vs), hi = Math.max(...vs);
  if (hi === lo) { lo -= Math.abs(lo) * 0.05 || 1; hi += Math.abs(hi) * 0.05 || 1; }
  const pad = (hi - lo) * 0.12; lo -= pad; hi += pad;
  const x = (i: number) => L + (months.length === 1 ? (W - L - R) / 2 : (i * (W - L - R)) / (months.length - 1));
  const y = (v: number) => T + ((hi - v) * (H - T - B)) / (hi - lo);
  const label = (v: number) => {
    const d = Math.abs(v) >= 1000 ? 0 : s.digits;
    return v.toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d });
  };
  // 이어진 달끼리만 선으로 잇는다(빈 달은 끊는다)
  let d = '';
  pts.forEach((x0, k) => { d += `${k && pts[k - 1].i === x0.i - 1 ? 'L' : 'M'}${x(x0.i).toFixed(1)},${y(x0.p.v).toFixed(1)}`; });
  const esc = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const axis = months.map((m, i) => `<text x="${x(i).toFixed(1)}" y="${H - 8}" text-anchor="middle" class="tc-ax">${Number(m.slice(5))}월</text>`).join('');
  const dots = pts.map((x0, k) => {
    const cx = x(x0.i), cy = y(x0.p.v);
    // 값 글자는 점 위에, 앞 점보다 낮으면(=선이 내려오면) 아래로 — 선과 겹침을 줄인다
    const prev = pts[k - 1]?.p.v, next = pts[k + 1]?.p.v;
    const valley = (prev == null || x0.p.v <= prev) && (next == null || x0.p.v <= next) && pts.length > 2;
    const ty = valley ? cy + 17 : cy - 9;
    const anchor = x0.i === 0 ? 'start' : x0.i === months.length - 1 ? 'end' : 'middle';
    const tx = anchor === 'start' ? cx - 4 : anchor === 'end' ? cx + 4 : cx;
    return `<g><title>${esc(`${x0.m} ${label(x0.p.v)} ${s.unit}`)}</title><circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="4" class="tc-dot"/><text x="${tx.toFixed(1)}" y="${ty.toFixed(1)}" text-anchor="${anchor}" class="tc-val">${label(x0.p.v)}</text></g>`;
  }).join('');
  return `<svg viewBox="0 0 ${W} ${H}" class="trend" role="img" aria-label="${esc(`${s.name} ${from}~${to} 추이`)}"><line x1="${L}" x2="${W - R}" y1="${H - B + 4}" y2="${H - B + 4}" class="tc-base"/>${axis}<path d="${d}" class="tc-line"/>${dots}</svg>`;
}
