/** /explore/ 데이터 탐색 — 브라우저에서 질문을 조건으로 바꾸고(규칙), 기업 색인·월간 집계로 표와 SVG 그래프를 그린다.
 *  외부 라이브러리·서버·AI 호출 없음. 그래프는 dataviz 규칙: 막대 24px 이하·끝 4px 둥글게, 선 2px, 격자 hairline, 값 라벨은 12개 이하일 때만, 표는 항상 함께. */
type Row = { i: string; n: string; d: string; e: string; c: string; g: string; s: string; w: string; t: string; k?: string[]; p?: 1; m?: number };
type Lite = { firms: number; employment: number; covered: number; nps_gain: number | null; nps_loss: number | null; new_firms: number | null; closed_firms: number | null; support_firms: number | null; support_records: number | null };
type Data = {
  stats_month: string | null; basis_label: string; companies_as_of: string; total: Lite | null;
  dims: Record<'industry' | 'district' | 'complex' | 'site' | 'tag', string[]>;
  metrics: Record<'industry' | 'district' | 'complex' | 'site' | 'tag', Record<string, Lite>>;
  timeseries: { months: string[]; total: { employment: (number | null)[]; firms: (number | null)[] }; by_industry: any; by_district: any; by_complex: any; by_site: any } | null;
  tag_names: Record<string, string>;
};
type Metric = 'firms' | 'employment' | 'nps' | 'new_closed' | 'support_firms';
type Axis = 'industry' | 'district' | 'eupmyeon' | 'complex' | 'site' | 'size' | 'sector' | 'tag' | 'month';
type Q = { m: Metric; x: Axis; g: string; d: string; c: string; t: string; w: string; k: string; p: boolean; ch: 'auto' | 'bar' | 'hbar' | 'line' | 'table'; q: string };
type Result = { title: string; sub: string; series: string[]; rows: { label: string; v: (number | null)[] }[]; unit: string; kind: 'bar' | 'hbar' | 'line' | 'table'; read: string; source: string; extra?: string[][] };

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const fmt = (n: number | null | undefined) => (n == null || Number.isNaN(n) ? '—' : Math.round(n).toLocaleString('ko-KR'));
const SIZE_ORDER = ['1~9', '10~49', '50~299', '300+', '미기재'];
const SIZE_LABEL: Record<string, string> = { '1~9': '1~9명', '10~49': '10~49명', '50~299': '50~299명', '300+': '300명 이상', '미기재': '미기재' };
const band = (w: string) => (!w ? '미기재' : w.startsWith('1~9') ? '1~9' : w.startsWith('10~') ? '10~49' : w.startsWith('300') ? '300+' : '50~299');
const shortComplex = (s: string) => s.replace('일반산업단지', '산단').replace('첨단산업단지', '산단').replace('산업단지', '산단').replace('지방산단', '산단');
const INDUSTRY_SYN: [RegExp, string][] = [
  [/자동차|모빌리티|부품/, '자동차·부품'], [/로봇/, '로봇'], [/의료|바이오|헬스|제약/, '의료·바이오'], [/소프트웨어|SW|IT|정보통신|앱/i, '소프트웨어·IT'],
  [/섬유|패션|의류|염색/, '섬유·패션'], [/전기|전자/, '전기·전자'], [/화학|에너지|플라스틱/, '화학·에너지'], [/식품|음료/, '식품'], [/기계|금속|뿌리/, '기계·금속'],
  [/기타\s*제조/, '기타 제조'], [/서비스/, '기타 서비스'],
];
const SITE_SYN: [RegExp, string][] = [[/알파시티/, '수성알파시티'], [/지식산업센터|지산/, '지식산업센터'], [/특구/, '연구개발특구'], [/개별입지/, '개별입지']];
const TAG_SYN: [RegExp, string][] = [[/벤처/, 'venture'], [/창업|스타트업/, 'startup'], [/첨복|첨단의료/, 'kmedi'], [/이노비즈/, 'innobiz'], [/연구소기업/, 'labfirm'], [/창경/, 'ccei']];

let DATA: Data | null = null;
let ROWS: Row[] | null = null;
let last: Result | null = null;
let lastSvg: SVGSVGElement | null = null;

async function load() {
  if (!DATA) DATA = await (await fetch('/explore-data.json')).json();
  if (!ROWS) ROWS = (await (await fetch('/companies-index.json')).json()).rows;
  return { data: DATA!, rows: ROWS! };
}

/* ---------- 질문 → 조건 (규칙) ---------- */
function options(id: string): string[] { return [...$<HTMLSelectElement>(id).options].map(o => o.value).filter(Boolean); }
export function parse(text: string): Partial<Q> {
  const q: Partial<Q> = {};
  const t = text.replace(/\s+/g, ' ').trim();
  if (!t) return q;
  // 필터: 구·군 (달성 → 달성군)
  for (const d of options('f-d')) if (t.includes(d) || (d.length >= 3 && t.includes(d.slice(0, -1)))) { q.d = d; break; }
  // 단지: 옵션 이름 또는 '산단' 뗀 앞말 (긴 것부터)
  const cx = options('f-c').filter(c => c !== '개별입지' && c !== '산단 외').sort((a, b) => b.length - a.length);
  for (const c of cx) { const key = c.replace(/산단|농공단지|일반|지방|대구/g, ''); if (t.includes(c) || (key.length >= 2 && new RegExp(key + '(?![구군])').test(t))) { q.c = c; break; } }   // '달성군' 의 달성은 달성산단이 아니다 }
  for (const [re, v] of SITE_SYN) if (re.test(t)) { q.t = v; break; }
  if (!q.t && !q.c && /산업단지|산단\b|산단 /.test(t)) q.t = '산업단지';
  for (const [re, v] of TAG_SYN) if (re.test(t)) { q.k = v; break; }
  for (const [re, v] of INDUSTRY_SYN) if (re.test(t.replace(/(산업|업종)별/, ''))) { q.g = v; break; }
  const sz = t.match(/(\d+)\s*(인|명)\s*(이상|초과)/);
  if (sz) { const n = Number(sz[1]); q.w = n >= 300 ? '300+' : n >= 50 ? 'ge50' : n >= 10 ? 'ge10' : ''; }
  else if (/1~9인|10인 미만|소기업/.test(t)) q.w = '1~9';
  if (/지원\s*이력|수혜\s*기업만/.test(t)) q.p = true;
  // 지표
  q.m = /취득|상실/.test(t) ? 'nps' : /신규|폐업/.test(t) ? 'new_closed' : /지원|수혜/.test(t) ? 'support_firms'
    : /고용|인원|종사자|가입자|일자리/.test(t) && !/규모별/.test(t) ? 'employment' : 'firms';
  // 구분(가로축)
  const ax = t.match(/(산업|업종군|구군|구·군|구\/군|지역|읍면동|동|단지|입지|규모|종사자 규모|업종|세분류|태그|월)별/);
  const axisOf: Record<string, Axis> = { 산업: 'industry', 업종군: 'industry', 구군: 'district', '구·군': 'district', '구/군': 'district', 지역: 'district', 읍면동: 'eupmyeon', 동: 'eupmyeon', 단지: 'complex', 입지: 'site', 규모: 'size', '종사자 규모': 'size', 업종: 'sector', 세분류: 'sector', 태그: 'tag', 월: 'month' };
  if (ax) q.x = axisOf[ax[1]];
  else if (/추이|시계열|변화|흐름/.test(t)) q.x = 'month';
  if (/표만|표로만/.test(t)) q.ch = 'table'; else if (/선\s*그래프|꺾은선/.test(t)) q.ch = 'line'; else if (/가로\s*막대/.test(t)) q.ch = 'hbar'; else if (/세로\s*막대|막대/.test(t)) q.ch = 'bar';
  return q;
}
function defaults(q: Partial<Q>): Q {
  const x: Axis = q.x ?? (q.d ? 'industry' : q.g ? 'district' : q.c ? 'industry' : q.t ? 'industry' : 'industry');
  return { m: q.m ?? 'firms', x, g: q.g ?? '', d: q.d ?? '', c: q.c ?? '', t: q.t ?? '', w: q.w ?? '', k: q.k ?? '', p: q.p ?? false, ch: q.ch ?? 'auto', q: q.q ?? '' };
}

/* ---------- 조건 ↔ 화면 ↔ URL ---------- */
function readControls(): Q {
  return defaults({ m: $<HTMLSelectElement>('metric').value as Metric, x: $<HTMLSelectElement>('axis').value as Axis, g: $<HTMLSelectElement>('f-g').value, d: $<HTMLSelectElement>('f-d').value,
    c: $<HTMLSelectElement>('f-c').value, t: $<HTMLSelectElement>('f-t').value, w: $<HTMLSelectElement>('f-w').value, k: $<HTMLSelectElement>('f-k').value, p: $<HTMLInputElement>('f-p').checked,
    ch: $<HTMLSelectElement>('chart').value as Q['ch'], q: $<HTMLInputElement>('q').value });
}
function writeControls(q: Q) {
  const set = (id: string, v: string) => { const el = $<HTMLSelectElement>(id); if ([...el.options].some(o => o.value === v)) el.value = v; else el.value = ''; };
  set('metric', q.m); set('axis', q.x); set('f-g', q.g); set('f-d', q.d); set('f-c', q.c); set('f-t', q.t); set('f-w', q.w); set('f-k', q.k); set('chart', q.ch);
  $<HTMLInputElement>('f-p').checked = q.p;
  if (q.q) $<HTMLInputElement>('q').value = q.q;
}
function toParams(q: Q): string {
  const p = new URLSearchParams();
  p.set('m', q.m); p.set('x', q.x);
  for (const k of ['g', 'd', 'c', 't', 'w', 'k'] as const) if (q[k]) p.set(k, q[k]);
  if (q.p) p.set('p', '1'); if (q.ch !== 'auto') p.set('ch', q.ch); if (q.q) p.set('q', q.q);
  return p.toString();
}
function fromParams(): Q | null {
  const p = new URLSearchParams(location.search);
  if (![...p.keys()].length) return null;
  if (p.get('q') && !p.get('m')) return defaults({ ...parse(p.get('q')!), q: p.get('q')! });
  return defaults({ m: (p.get('m') as Metric) || undefined, x: (p.get('x') as Axis) || undefined, g: p.get('g') ?? '', d: p.get('d') ?? '', c: p.get('c') ?? '', t: p.get('t') ?? '', w: p.get('w') ?? '', k: p.get('k') ?? '', p: p.get('p') === '1', ch: (p.get('ch') as Q['ch']) || 'auto', q: p.get('q') ?? '' });
}

/* ---------- 계산 ---------- */
const AXIS_NAME: Record<Axis, string> = { industry: '산업', district: '구·군', eupmyeon: '읍면동', complex: '단지', site: '입지 유형', size: '종사자 규모', sector: '업종(세분류)', tag: '태그', month: '월' };
const METRIC_NAME: Record<Metric, string> = { firms: '기업 수', employment: '고용 인원', nps: '국민연금 취득·상실', new_closed: '신규 등록·폐업', support_firms: '지원사업 수혜 기업(최근 3년)' };
function filterDesc(q: Q, data: Data): string[] {
  const f: string[] = [];
  if (q.d) f.push(q.d); if (q.g) f.push(q.g); if (q.c) f.push(q.c); if (q.t) f.push(q.t);
  if (q.w) f.push(q.w === 'ge10' ? '10인 이상' : q.w === 'ge50' ? '50인 이상' : SIZE_LABEL[q.w] ?? q.w);
  if (q.k) f.push(data.tag_names[q.k] ?? q.k); if (q.p) f.push('지원 이력 있음');
  return f;
}
function applyFilters(rows: Row[], q: Q): Row[] {
  return rows.filter(r => (!q.d || r.d === q.d) && (!q.g || r.g === q.g) && (!q.c || r.c === q.c) && (!q.t || r.t === q.t) && (!q.k || (r.k ?? []).includes(q.k)) && (!q.p || r.p === 1)
    && (!q.w || (q.w === 'ge10' ? ['10~49', '50~299', '300+'].includes(band(r.w)) : q.w === 'ge50' ? ['50~299', '300+'].includes(band(r.w)) : band(r.w) === q.w)));
}
function keyOf(r: Row, x: Axis): string[] {
  switch (x) {
    case 'industry': return [r.g || '미분류']; case 'district': return [r.d || '미상']; case 'eupmyeon': return [r.e || '(읍면동 없음)']; case 'complex': return [r.c];
    case 'site': return [r.t]; case 'size': return [band(r.w)]; case 'sector': return [r.s || '미상']; case 'tag': return r.k?.length ? r.k : ['태그 없음']; default: return [''];
  }
}
export function compute(q: Q, data: Data, rows: Row[]): Result {
  const filt = filterDesc(q, data);
  const scope = filt.length ? filt.join(' · ') : '대구 전체';
  const src = (co: boolean, st: boolean) => [co ? `기업 사전 ${data.companies_as_of}(팩토리온 공장등록 + 산단 외 목록)` : '', st ? `월간 통계 ${data.stats_month}(고용 = ${data.basis_label})` : ''].filter(Boolean).join(' · ');
  const aggDims: Axis[] = ['industry', 'district', 'complex', 'site', 'tag'];

  if (q.x === 'month') {
    const ts = data.timeseries;
    if (!ts) return { title: '월별 추이', sub: '', series: [], rows: [], unit: '', kind: 'table', read: '시계열 자료가 아직 없습니다.', source: '' };
    const key = q.m === 'employment' ? 'employment' : 'firms';
    const pick = (): { name: string; arr: (number | null)[] } => {
      if (q.g && ts.by_industry?.[q.g]) return { name: q.g, arr: ts.by_industry[q.g][key] };
      if (q.d && ts.by_district?.[q.d]) return { name: q.d, arr: ts.by_district[q.d][key] };
      if (q.c) { const full = Object.keys(ts.by_complex ?? {}).find(k => shortComplex(k) === q.c); if (full) return { name: q.c, arr: ts.by_complex[full][key] }; }
      if (q.t && ts.by_site?.[q.t]) return { name: q.t, arr: ts.by_site[q.t][key] };
      return { name: '대구 전체', arr: ts.total[key] };
    };
    const s = pick();
    const name = q.m === 'employment' ? '고용 인원' : '기업 수';
    return { title: `${s.name} ${name} 월별 추이`, sub: `${ts.months[0]} ~ ${ts.months[ts.months.length - 1]} · ${ts.months.length}개월`, series: [name], unit: q.m === 'employment' ? '명' : '곳',
      rows: ts.months.map((mo, i) => ({ label: mo, v: [s.arr[i] ?? null] })), kind: ts.months.length > 1 ? 'line' : 'bar',
      read: ts.months.length < 3 ? `자료가 ${ts.months.length}개월뿐이라 추세를 말하기 어렵습니다. 국민연금 월별 파일이 쌓이면 24개월까지 늘어납니다.` : `월별 값은 ${data.basis_label} 기준(집계 대상 기업만).`, source: src(false, true) };
  }
  if (q.m === 'nps' || q.m === 'new_closed' || q.m === 'support_firms') {
    const ax: Axis = aggDims.includes(q.x) ? q.x : 'industry';
    const table = data.metrics[ax as 'industry'];
    const selfFilter = ax === 'industry' ? q.g : ax === 'district' ? q.d : ax === 'complex' ? q.c : ax === 'site' ? q.t : ax === 'tag' ? (data.tag_names[q.k] ?? q.k) : '';
    const names = Object.keys(table).filter(n => !selfFilter || n === selfFilter || shortComplex(n) === selfFilter);
    const series = q.m === 'nps' ? ['취득', '상실'] : q.m === 'new_closed' ? ['신규 등록', '폐업'] : ['수혜 기업'];
    const get = (l: Lite) => q.m === 'nps' ? [l.nps_gain, l.nps_loss] : q.m === 'new_closed' ? [l.new_firms, l.closed_firms] : [l.support_firms];
    const rows2 = names.map(n => ({ label: ax === 'complex' ? shortComplex(n) : ax === 'tag' ? n : n, v: get(table[n]) })).filter(r => r.v.some(v => v != null)).sort((a, b) => (b.v[0] ?? 0) - (a.v[0] ?? 0));
    const ignored = filt.filter(f => f !== selfFilter && !(ax === 'complex' && f === selfFilter));
    const note = (ax !== q.x ? `이 지표는 산업·구군·단지·입지·태그 단위로만 집계돼 있어 '${AXIS_NAME[q.x]}별' 대신 산업별로 보여 줍니다. ` : '') + (ignored.length ? `조건(${ignored.join(', ')})은 이 지표에 적용되지 않습니다. ` : '');
    return { title: `${AXIS_NAME[ax]}별 ${METRIC_NAME[q.m]}`, sub: `${data.stats_month} 기준`, series, unit: q.m === 'support_firms' ? '곳' : q.m === 'nps' ? '명' : '곳',
      rows: rows2, kind: 'bar', read: note + (q.m === 'nps' ? '취득·상실은 국민연금 가입자 기준(집계 대상 기업만), 전달 고지 대비 비교라 실제 입·퇴사와 다를 수 있습니다.' : q.m === 'support_firms' ? 'NTIS 과제·대구시 보조금 공개·기관 선정 공고에 이름이 있는 기업 수. 비공개 지원은 없습니다.' : '팩토리온 등록 기준, 전월 파일과 비교.'), source: src(false, true) };
  }
  // 기업 단위: 기업 수 / 고용 인원
  const sub = applyFilters(rows, q);
  const acc = new Map<string, { firms: number; emp: number; covered: number }>();
  for (const r of sub) for (const k of keyOf(r, q.x)) { const a = acc.get(k) ?? { firms: 0, emp: 0, covered: 0 }; a.firms++; if (r.m != null) { a.emp += r.m; a.covered++; } acc.set(k, a); }
  let entries = [...acc.entries()];
  const isEmp = q.m === 'employment';
  if (q.x === 'size') entries.sort((a, b) => SIZE_ORDER.indexOf(a[0]) - SIZE_ORDER.indexOf(b[0]));
  else entries.sort((a, b) => (isEmp ? b[1].emp - a[1].emp : b[1].firms - a[1].firms));
  let extraNote = '';
  if ((q.x === 'sector' || q.x === 'eupmyeon') && entries.length > 20) {
    const rest = entries.slice(20); entries = entries.slice(20 - 20, 20);
    const o = rest.reduce((a, [, v]) => ({ firms: a.firms + v.firms, emp: a.emp + v.emp, covered: a.covered + v.covered }), { firms: 0, emp: 0, covered: 0 });
    entries.push([`기타 (${rest.length}개 ${AXIS_NAME[q.x]})`, o]);
    extraNote = `상위 20개만 그래프에 그리고 나머지는 '기타'로 묶었습니다(CSV 에는 전부 들어 있습니다). `;
  }
  const label = (k: string) => (q.x === 'size' ? SIZE_LABEL[k] ?? k : q.x === 'tag' ? data.tag_names[k] ?? k : k);
  const rows2 = entries.map(([k, v]) => ({ label: label(k), v: [isEmp ? v.emp : v.firms] }));
  const totalFirms = sub.length, totalEmp = sub.reduce((s, r) => s + (r.m ?? 0), 0), covered = sub.filter(r => r.m != null).length;
  const title = `${scope} ${AXIS_NAME[q.x]}별 ${isEmp ? '고용 인원' : '기업 수'}`;
  const read = isEmp
    ? `${scope} 기업 ${fmt(totalFirms)}곳 중 고용 값이 있는 ${fmt(covered)}곳(${totalFirms ? Math.round(covered / totalFirms * 100) : 0}%)의 합 ${fmt(totalEmp)}명(${data.basis_label} ${data.stats_month}). 값 없는 기업은 0 으로 셉니다. ${extraNote}`
    : `${scope} 기업 ${fmt(totalFirms)}곳(고용 값 있는 곳 ${fmt(covered)}곳). ${q.x === 'tag' ? '태그가 여럿인 기업은 각 태그에 한 번씩 셉니다. ' : ''}${extraNote}`;
  const kind: Result['kind'] = q.x === 'size' ? 'bar' : rows2.length > 8 || rows2.some(r => r.label.length > 7) ? 'hbar' : 'bar';
  return { title, sub: `기업 사전 ${data.companies_as_of}`, series: [isEmp ? '고용 인원' : '기업 수'], unit: isEmp ? '명' : '곳', rows: rows2, kind, read, source: src(true, isEmp), extra: undefined };
}

/* ---------- 그래프 ---------- */
const NS = 'http://www.w3.org/2000/svg';
const el = (tag: string, attrs: Record<string, string | number> = {}, text?: string) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v)); if (text != null) e.textContent = text; return e; };
const css = (v: string, fb: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || fb;
const niceMax = (v: number) => { if (v <= 0) return 1; const p = 10 ** Math.floor(Math.log10(v)); const n = v / p; const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10; return m * p; };
function barPath(x: number, y: number, w: number, h: number, horizontal: boolean, r = 4): string {
  if (horizontal) { const rr = Math.min(r, w / 2, h / 2); return `M${x},${y} h${Math.max(0, w - rr)} a${rr},${rr} 0 0 1 ${rr},${rr} v${Math.max(0, h - 2 * rr)} a${rr},${rr} 0 0 1 -${rr},${rr} h-${Math.max(0, w - rr)} z`; }
  const rr = Math.min(r, w / 2, h / 2); return `M${x},${y + h} v-${Math.max(0, h - rr)} a${rr},${rr} 0 0 1 ${rr},-${rr} h${Math.max(0, w - 2 * rr)} a${rr},${rr} 0 0 1 ${rr},${rr} v${Math.max(0, h - rr)} z`;
}
function tooltip(box: HTMLElement) {
  let tip = box.querySelector<HTMLElement>('.tip');
  if (!tip) { tip = document.createElement('div'); tip.className = 'tip'; tip.setAttribute('role', 'status'); box.appendChild(tip); }
  return { show(x: number, y: number, lines: [string, string][]) { tip!.replaceChildren(...lines.map(([v, l]) => { const d = document.createElement('div'); const s = document.createElement('strong'); s.textContent = v; d.append(s, ' ', l); return d; })); tip!.style.display = 'block'; const bw = box.clientWidth; tip!.style.left = `${Math.min(x + 12, bw - tip!.offsetWidth - 4)}px`; tip!.style.top = `${Math.max(0, y - 40)}px`; }, hide() { tip!.style.display = 'none'; } };
}
export function draw(res: Result, box: HTMLElement): SVGSVGElement | null {
  box.replaceChildren();
  if (res.kind === 'table' || !res.rows.length) return null;
  const W = Math.max(320, box.clientWidth || 720);
  const c1 = css('--chart-1', '#1B4F9B'), c2 = css('--chart-2', '#E69F00'), ink = css('--muted', '#595959'), ink2 = css('--muted-2', '#767676'), line = css('--line', '#e0e0e0'), bg = css('--bg', '#fff');
  const colors = [c1, c2, css('--chart-3', '#009E73')];
  const nS = res.series.length;
  const vals = res.rows.flatMap(r => r.v.map(v => v ?? 0));
  const max = niceMax(Math.max(...vals, 0));
  const tp = tooltip(box);
  const svg = el('svg', { role: 'img', 'aria-label': `${res.title} 그래프. 값은 아래 표에 있습니다.` }) as SVGSVGElement;
  const font = 'font-family: inherit; font-size: 13px';
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => f * max);
  if (res.kind === 'hbar') {
    const rowH = 28 * nS + 8, padL = Math.min(220, Math.max(90, Math.max(...res.rows.map(r => r.label.length)) * 12)), padR = 64, top = 8, bottom = 28;
    const H = top + res.rows.length * rowH + bottom;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('height', String(H));
    const plotW = W - padL - padR;
    for (const t of ticks) { const x = padL + (t / max) * plotW; svg.append(el('line', { x1: x, x2: x, y1: top, y2: H - bottom, stroke: line, 'stroke-width': 1 })); svg.append(el('text', { x, y: H - 8, fill: ink2, 'text-anchor': 'middle', style: font }, fmt(t))); }
    res.rows.forEach((r, i) => {
      const y0 = top + i * rowH;
      svg.append(el('text', { x: padL - 8, y: y0 + rowH / 2 + 4, fill: ink, 'text-anchor': 'end', style: font }, r.label.length > 18 ? r.label.slice(0, 17) + '…' : r.label));
      r.v.forEach((v, si) => {
        const bh = Math.min(24, (rowH - 8) / nS - 2), y = y0 + 4 + si * ((rowH - 8) / nS) + ((rowH - 8) / nS - bh) / 2, w = ((v ?? 0) / max) * plotW;
        const p = el('path', { d: barPath(padL, y, Math.max(0, w), bh, true), fill: colors[si], tabindex: 0, role: 'img', 'aria-label': `${r.label} ${res.series[si]} ${fmt(v)}${res.unit}` });
        const show = (ev?: PointerEvent) => tp.show(ev ? ev.offsetX : padL + w, ev ? ev.offsetY : y, r.v.map((vv, k) => [`${fmt(vv)}${res.unit}`, nS > 1 ? `${res.series[k]} · ${r.label}` : r.label]));
        p.addEventListener('pointermove', show); p.addEventListener('focus', () => show()); p.addEventListener('pointerleave', tp.hide); p.addEventListener('blur', tp.hide);
        svg.append(p);
        if (res.rows.length <= 12 || i < 5) svg.append(el('text', { x: padL + w + 6, y: y + bh / 2 + 4, fill: ink, style: font }, fmt(v)));
      });
    });
  } else if (res.kind === 'bar') {
    const H = 300, padL = 56, padR = 12, top = 16, bottom = 56, plotW = W - padL - padR, plotH = H - top - bottom;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('height', String(H));
    for (const t of ticks) { const y = top + plotH - (t / max) * plotH; svg.append(el('line', { x1: padL, x2: W - padR, y1: y, y2: y, stroke: line, 'stroke-width': 1 })); svg.append(el('text', { x: padL - 6, y: y + 4, fill: ink2, 'text-anchor': 'end', style: font }, fmt(t))); }
    const slot = plotW / res.rows.length, bw = Math.min(24, (slot - 6) / nS - 2);
    res.rows.forEach((r, i) => {
      const cx = padL + slot * i + slot / 2;
      const lab = r.label.length > 6 && res.rows.length > 6 ? r.label.slice(0, 5) + '…' : r.label;
      svg.append(el('text', { x: cx, y: H - bottom + 18, fill: ink, 'text-anchor': 'middle', style: font, transform: res.rows.length > 8 ? `rotate(-30 ${cx} ${H - bottom + 18})` : '' }, lab));
      r.v.forEach((v, si) => {
        const h = ((v ?? 0) / max) * plotH, x = cx - (nS * bw + (nS - 1) * 2) / 2 + si * (bw + 2), y = top + plotH - h;
        const p = el('path', { d: barPath(x, y, bw, Math.max(0, h), false), fill: colors[si], tabindex: 0, role: 'img', 'aria-label': `${r.label} ${res.series[si]} ${fmt(v)}${res.unit}` });
        const show = (ev?: PointerEvent) => tp.show(ev ? ev.offsetX : x, ev ? ev.offsetY : y, r.v.map((vv, k) => [`${fmt(vv)}${res.unit}`, nS > 1 ? `${res.series[k]} · ${r.label}` : r.label]));
        p.addEventListener('pointermove', show); p.addEventListener('focus', () => show()); p.addEventListener('pointerleave', tp.hide); p.addEventListener('blur', tp.hide);
        svg.append(p);
        if (res.rows.length * nS <= 12) svg.append(el('text', { x: x + bw / 2, y: y - 4, fill: ink, 'text-anchor': 'middle', style: font }, fmt(v)));
      });
    });
    svg.append(el('line', { x1: padL, x2: W - padR, y1: top + plotH, y2: top + plotH, stroke: css('--line-strong', '#bdbdbd'), 'stroke-width': 1 }));
  } else {
    const H = 300, padL = 56, padR = 72, top = 16, bottom = 40, plotW = W - padL - padR, plotH = H - top - bottom;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('height', String(H));
    for (const t of ticks) { const y = top + plotH - (t / max) * plotH; svg.append(el('line', { x1: padL, x2: W - padR, y1: y, y2: y, stroke: line, 'stroke-width': 1 })); svg.append(el('text', { x: padL - 6, y: y + 4, fill: ink2, 'text-anchor': 'end', style: font }, fmt(t))); }
    const n = res.rows.length, xs = res.rows.map((_, i) => padL + (n > 1 ? (i / (n - 1)) * plotW : plotW / 2));
    res.rows.forEach((r, i) => { if (i % Math.ceil(n / 8) === 0 || i === n - 1) svg.append(el('text', { x: xs[i], y: H - 12, fill: ink, 'text-anchor': 'middle', style: font }, r.label)); });
    res.series.forEach((s, si) => {
      const pts = res.rows.map((r, i) => (r.v[si] == null ? null : [xs[i], top + plotH - ((r.v[si] as number) / max) * plotH] as [number, number]));
      const d = pts.map((p, i) => (p ? `${i && pts[i - 1] ? 'L' : 'M'}${p[0]},${p[1]}` : '')).join(' ');
      svg.append(el('path', { d, fill: 'none', stroke: colors[si], 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
      pts.forEach((p, i) => { if (!p) return; const g = el('g', { tabindex: 0, role: 'img', 'aria-label': `${res.rows[i].label} ${s} ${fmt(res.rows[i].v[si])}${res.unit}` });
        g.append(el('circle', { cx: p[0], cy: p[1], r: 12, fill: 'transparent' }), el('circle', { cx: p[0], cy: p[1], r: 4, fill: colors[si], stroke: bg, 'stroke-width': 2 }));
        const show = () => tp.show(p[0], p[1], res.rows[i].v.map((vv, k) => [`${fmt(vv)}${res.unit}`, `${res.series[k]} · ${res.rows[i].label}`]));
        g.addEventListener('pointermove', show); g.addEventListener('focus', show); g.addEventListener('pointerleave', tp.hide); g.addEventListener('blur', tp.hide); svg.append(g); });
      const lastP = [...pts].reverse().find(Boolean); if (lastP) svg.append(el('text', { x: lastP[0] + 8, y: lastP[1] + 4, fill: ink, style: font }, fmt(res.rows[res.rows.length - 1].v[si])));
    });
  }
  box.append(svg);
  if (nS > 1) { const lg = document.createElement('ul'); lg.className = 'legend'; res.series.forEach((s, i) => { const li = document.createElement('li'); const sw = document.createElement('span'); sw.className = 'sw'; sw.style.background = colors[i]; li.append(sw, s); lg.append(li); }); box.append(lg); }
  return svg;
}

/* ---------- 표·내보내기 ---------- */
function renderTable(res: Result) {
  const t = $<HTMLTableElement>('r-table'); t.replaceChildren();
  const th = (s: string, n = false) => { const e = document.createElement('th'); e.textContent = s; if (n) e.className = 'n'; e.scope = 'col'; return e; };
  const td = (s: string, n = false) => { const e = document.createElement('td'); e.textContent = s; if (n) e.className = 'n'; return e; };
  const single = res.series.length === 1 && !res.extra;
  const total = single ? res.rows.reduce((a, r) => a + (r.v[0] ?? 0), 0) : 0;
  const head = document.createElement('tr'); head.append(th('구분'), ...res.series.map(s => th(`${s}${res.unit ? `(${res.unit})` : ''}`, true)));
  if (single) head.append(th('비율', true)); if (res.extra) head.append(...res.extra[0].map(h => th(h, true)));
  const thead = document.createElement('thead'); thead.append(head); t.append(thead);
  const tb = document.createElement('tbody');
  res.rows.forEach((r, i) => { const tr = document.createElement('tr'); tr.append(td(r.label), ...r.v.map(v => td(fmt(v), true))); if (single) tr.append(td(total ? `${((r.v[0] ?? 0) / total * 100).toFixed(1)}%` : '—', true)); if (res.extra) tr.append(...res.extra[i + 1].map(v => td(v, true))); tb.append(tr); });
  if (single && res.rows.length > 1 && !/월별/.test(res.title)) { const tr = document.createElement('tr'); tr.className = 'total'; tr.append(td('합계'), td(fmt(total), true), td('100%', true)); tb.append(tr); }
  t.append(tb);
}
function tsv(res: Result, sep = '\t') {
  const head = ['구분', ...res.series.map(s => `${s}${res.unit ? `(${res.unit})` : ''}`), ...(res.extra ? res.extra[0] : [])];
  const lines = [head, ...res.rows.map((r, i) => [r.label, ...r.v.map(v => (v == null ? '' : String(Math.round(v)))), ...(res.extra ? res.extra[i + 1] : [])])];
  return lines.map(l => l.map(c => (sep === ',' && /[",\n]/.test(c) ? `"${c.replace(/"/g, '""')}"` : c)).join(sep)).join('\n') + `\n\n출처${sep}${res.source}\n`;
}
function download(name: string, blob: Blob) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000); }
function png(svg: SVGSVGElement, title: string) {
  const vb = svg.viewBox.baseVal, scale = 2; const c = document.createElement('canvas'); c.width = vb.width * scale; c.height = (vb.height + 40) * scale;
  const ctx = c.getContext('2d')!; ctx.scale(scale, scale); ctx.fillStyle = css('--bg', '#fff'); ctx.fillRect(0, 0, vb.width, vb.height + 40);
  ctx.fillStyle = css('--ink', '#1a1a1a'); ctx.font = 'bold 15px sans-serif'; ctx.fillText(title, 8, 22);
  const clone = svg.cloneNode(true) as SVGSVGElement; clone.setAttribute('width', String(vb.width)); clone.setAttribute('height', String(vb.height)); clone.setAttribute('xmlns', NS);
  clone.querySelectorAll('text').forEach(t => t.setAttribute('font-family', 'sans-serif'));
  const img = new Image(); img.onload = () => { ctx.drawImage(img, 0, 34); c.toBlob(b => b && download(`${title}.png`, b), 'image/png'); };
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(clone));
}

/* ---------- 실행 ---------- */
async function run(q: Q, push = true) {
  const { data, rows } = await load();
  writeControls(q);
  const res = compute(q, data, rows);
  if (q.ch !== 'auto') res.kind = q.ch;
  last = res;
  $('r-empty').hidden = true; $('result').hidden = false;
  $('r-title').textContent = res.title; $('r-meta').textContent = res.sub; $('r-read').textContent = res.read;
  lastSvg = draw(res, $('r-chart'));
  $('r-cap').textContent = res.rows.length ? `${res.title} · ${res.sub}${res.kind === 'table' ? ' (표만)' : ''}` : '조건에 맞는 기업이 없습니다.';
  $<HTMLButtonElement>('dl-png').disabled = !lastSvg;
  renderTable(res);
  $('r-src').textContent = `출처: ${res.source}. 공개 자료를 같은 형식으로 집계한 것이며 평가·순위·추천이 아닙니다.`;
  if (push) history.replaceState(null, '', `/explore/?${toParams(q)}`);
}
export function init() {
  const form = $<HTMLFormElement>('ask');
  form.addEventListener('submit', e => { e.preventDefault(); const text = $<HTMLInputElement>('q').value; run(defaults({ ...parse(text), q: text })); });
  for (const id of ['metric', 'axis', 'f-g', 'f-d', 'f-c', 'f-t', 'f-w', 'f-k', 'f-p', 'chart']) $(id).addEventListener('change', () => { const q = readControls(); q.q = ''; $<HTMLInputElement>('q').value = ''; run(q); });
  document.querySelectorAll<HTMLAnchorElement>('.examples a').forEach(a => a.addEventListener('click', e => { e.preventDefault(); history.replaceState(null, '', `/explore/?${a.dataset.qs}`); $<HTMLInputElement>('q').value = a.textContent ?? ''; const q = fromParams(); if (q) { q.q = a.textContent ?? ''; run(q); } }));
  $('dl-csv').addEventListener('click', () => last && download(`${last.title}.csv`, new Blob(['﻿' + tsv(last, ',')], { type: 'text/csv;charset=utf-8' })));
  $('copy-tsv').addEventListener('click', async () => { if (last) { await navigator.clipboard.writeText(tsv(last)); ($('copy-tsv') as HTMLButtonElement).textContent = '복사됨'; } });
  $('copy-link').addEventListener('click', async () => { await navigator.clipboard.writeText(location.href); ($('copy-link') as HTMLButtonElement).textContent = '링크 복사됨'; });
  $('dl-png').addEventListener('click', () => lastSvg && last && png(lastSvg, last.title));
  const q = fromParams();
  if (q) { $<HTMLDetailsElement>('controls').open = false; run(q, false); }   // 결과가 있으면 조건 상자는 접어 두고 결과를 위로
  addEventListener('resize', () => { if (last) lastSvg = draw(last, $('r-chart')); });
}
