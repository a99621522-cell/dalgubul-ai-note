import fs from 'node:fs';
import path from 'node:path';
/** 아주 단순한 CSV 파서(따옴표 필드 지원). scripts/data/*.csv 전용 */
export function readCsv(rel: string): Record<string, string>[] {
  const p = path.resolve(rel);
  if (!fs.existsSync(p)) return [];
  const text = fs.readFileSync(p, 'utf-8').replace(/^\uFEFF/, '');
  const rows: string[][] = []; let cur: string[] = []; let field = ''; let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i+1] === '"') { field += '"'; i++; } else q = false; } else field += c; }
    else if (c === '"') q = true;
    else if (c === ',') { cur.push(field); field = ''; }
    else if (c === '\n') { cur.push(field); rows.push(cur); cur = []; field = ''; }
    else if (c !== '\r') field += c;
  }
  if (field || cur.length) { cur.push(field); rows.push(cur); }
  const head = rows.shift() ?? [];
  return rows.filter(r => r.length > 1).map(r => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ''])));
}
import { siteType, isStartup } from './sites';
import { classify } from './industry';
export type Company = { id: string; name: string; complex: string; district: string; eupmyeon: string; sector_code: string; sector: string; sector_group: string; product: string; workers_band: string; workers: string; reg_type: string; first_registered: string; mfg_area_band: string; address: string; sites: string; source: string; as_of: string;
  founded: string; site_type: string; tags: string[] };
export const shortComplex = (s: string) => s.replace('일반산업단지','산단').replace('첨단산업단지','산단').replace('산업단지','산단').replace('지방산단','산단');
/** 개인 성명으로 보이는 공장명은 목록·페이지에서 뺀다 (CLAUDE.md 기업 사전 원칙).
 *  팩토리온 원자료에는 개인사업자가 대표자 성명을 공장명으로 등록한 행이 있다("김서규", "오연숙").
 *  규칙(보수적으로): 한글 3자 + 첫 글자가 성씨 + 외래어 음절 없음 + 상호 접미어 없음 + '○○사' 아님,
 *  또는 두 글자 성씨(남궁·선우 등)로 시작하는 4자. 공개 자료여도 개인정보 원칙을 우선한다.
 *  ※ "한글 2~4자 전부"로 잡으면 가람전기·고려철판 같은 4자 상호 1,375건이 함께 빠져 전수 원칙을 깬다(2026-09-23 측정). */
export const BIZ_SUFFIXES = ['산업', '공업', '기업', '테크', '정밀', '섬유', '식품', '상사', '상회', '공장', '제작소', '기계', '화학', '전자', '금속', '물산', '건설', '시스템', '코리아', '개발', '스틸', '패션', '인쇄', '유통', '에너지', '가공', '제조', '공사', '공방', '기공', '직물', '부동산', '유니온'];
const SURNAMES = new Set('강고공곽구국권금기길김나남노도라류마맹명모문민박반방배백변봉부사서석선설성소손송신심안양어엄여연염예오옥왕용우원위유육윤은이인임장전정제조주지진차채천최추탁편표하한함허현홍황');
const SURNAMES2 = ['남궁', '황보', '제갈', '선우', '독고', '사공', '서문', '동방'];
const LOAN_SYLLABLES = new Set('넷니닷드들디람랩룩링맥몰밀벡벤북샘샵센스앤엔엘온잉젠촌카캠컴코크텍토트팜팩폴프플홈');
const NOT_PERSON = new Set(['고운들', '고운홈', '신일신', '어울림', '오우이', '원일키', '위니아', '이지유', '인벤토', '지구촌', '한사람']);
export const looksLikePersonName = (raw: string) => {
  const n = raw.trim();
  if (NOT_PERSON.has(n) || BIZ_SUFFIXES.some(s => n.includes(s)) || n.endsWith('사')) return false;
  const hasLoan = (t: string) => [...t].some(ch => LOAN_SYLLABLES.has(ch));
  if (/^[가-힣]{3}$/.test(n)) return SURNAMES.has(n[0]) && !hasLoan(n.slice(1));
  if (/^[가-힣]{4}$/.test(n)) return SURNAMES2.some(s => n.startsWith(s)) && !hasLoan(n.slice(2));
  return false;
};
let _companies: Company[] | null = null;
/** 가나다순 정렬 키: '(주)·㈜·( 주 )·（재）·주식회사' 같은 법인 표기를 떼고 비교한다. 안 떼면 '(주)…' 가 전부 앞에 몰린다.
 *  글자로 시작하지 않는 이름('-', '.' 같은 등록값)은 뒤로 보낸다(rank 1). 클라이언트(companies/index.astro)와 같은 규칙. */
const CORP_PFX = /^\s*([（(]\s*(주|유|사|재|자|합)\s*[)）]|㈜|주식회사|유한회사|사단법인|재단법인|농업회사법인|유한책임회사)\s*/g;
const CORP_SFX = /\s*([（(]\s*(주|유)\s*[)）]|㈜|주식회사|유한회사|유한책임회사)\s*$/g;
export const sortName = (s: string) => (s || '').replace(CORP_PFX, '').replace(CORP_SFX, '').trim() || s;
export const nameRank = (k: string) => (/^[0-9A-Za-z가-힣ㄱ-ㅎ]/.test(k) ? 0 : 1);
export const byName = (a: string, b: string) => { const ka = sortName(a), kb = sortName(b); return nameRank(ka) - nameRank(kb) || ka.localeCompare(kb, 'ko') || a.localeCompare(b, 'ko'); };

/** 기업 사전용 목록: 팩토리온 기업 + 산단 외 기업(extra_companies.csv). 개인 성명으로 보이는 공장명은 표시에서만 뺀다(통계는 전수). */
export const companies = () => {
  if (_companies) return _companies;
  const fo = readCsv('scripts/data/dalseong_companies.csv');
  const extra = readCsv('scripts/data/extra_companies.csv');
  const tagRows = readCsv('scripts/data/company_tags.csv');
  const tags = new Map<string, Set<string>>();
  for (const t of tagRows) if (t.id && t.tag) (tags.get(t.id) ?? tags.set(t.id, new Set()).get(t.id)!).add(t.tag);
  const all = [...fo, ...extra].map(r => {
    const t = new Set(tags.get(r.id) ?? []);
    for (const k of (r.tags ?? '').split(';')) if (k.trim()) t.add(k.trim());
    if (r.founded && isStartup(r.founded, r.as_of)) t.add('startup');
    return { ...r, founded: r.founded ?? '', complex: r.complex || '개별입지', sector_group: classify(r.sector_code, r.sector, r.product), site_type: siteType(r.complex, r.address), tags: [...t] } as Company;  // 산업 그룹은 항상 config/industry_groups.yml 규칙(11개)으로
  });
  _companies = all.filter(c => !looksLikePersonName(c.name));
  console.log(`[companies] 팩토리온 ${fo.length} + 산단 외 ${extra.length}, 개인 성명으로 보이는 공장명 ${all.length - _companies.length}건은 표시에서 제외 → ${_companies.length}`);
  return _companies;
};
export const complexes = () => readCsv('scripts/data/dalseong_complexes.csv');

/** 부처 사업설명자료 DB(scripts/data/programs_*.csv). 예산 단위는 백만 원(자료 그대로). */
export type Program = Record<string, string> & { src: string; b26: number; b25: number; isNew: boolean; newDerived: boolean; corp: boolean };
const PROGRAM_FILES = (() => {
  const dir = 'scripts/data';
  const all = fs.readdirSync(dir).filter(f => /^programs_.*\.csv$/.test(f)).sort();
  return [...all.filter(f => f !== 'programs_ai.csv'), ...all.filter(f => f === 'programs_ai.csv')];  // 부처 개별 자료 → AI 통합자료 순
})();
const num = (s: string) => { const n = Number((s || '').replace(/,/g, '')); return Number.isFinite(n) ? n : 0; };
let _programs: Program[] | null = null;
export const programs = () => {
  if (_programs) return _programs;
  const out: Program[] = []; const seen = new Set<string>(); let dup = 0;
  for (const f of PROGRAM_FILES) for (const r of readCsv('scripts/data/' + f)) {
    if (!r.name) continue;
    const key = `${r.ministry}|${r.code}|${r.name}`;
    if (seen.has(key)) { dup++; continue; }   // 같은 사업이 두 자료에 다 실린 경우
    seen.add(key);
    const b26 = num(r.budget_2026), b25 = num(r.budget_2025);
    const flagged = (r.new_or_continue || '').includes('신규');
    const newDerived = !flagged && b25 === 0 && b26 > 0;   // 자료에 신규 표기가 거의 없어 예산으로 추정
    out.push({ ...r, src: f.replace('programs_', '').replace('.csv', ''), b26, b25, isNew: flagged || newDerived, newDerived,
      corp: /기업|사업자|소상공인|스타트업|창업/.test(r.beneficiary || '') });
  }
  _programs = out;
  console.log(`[programs] 사업 ${out.length}건 (기업 수혜 ${out.filter(p => p.corp).length}, 중복 제거 ${dup})`);
  return out;
};
/** 대구시 본예산 사업설명서(부서별)에서 뽑은 세부사업(scripts/data/city_programs.csv, scripts/parse_city_budget.py). 금액 단위는 자료 그대로 천 원. */
export type CityProgram = Record<string, string> & { b26: number; b25: number; isNew: boolean; corp: boolean; admin: boolean; funds: { city: number; national: number; balanced: number; other: number } };
let _city: CityProgram[] | null = null;
export const cityPrograms = () => {
  if (_city) return _city;
  const p = 'scripts/data/city_programs.csv';
  const rows = fs.existsSync(p) ? readCsv(p) : [];
  _city = rows.filter(r => r.name).map(r => ({ ...r, b26: num(r.budget_2026), b25: num(r.budget_2025), isNew: r.status === '신규', corp: r.corp === 'Y', admin: r.admin === 'Y',
    funds: { city: num(r.fund_city), national: num(r.fund_national), balanced: num(r.fund_balanced), other: num(r.fund_other) } }));
  return _city;
};
/** 천 원 → '12.3억 원' / '1,234만 원'. 0이면 null. */
export const fmtCheon = (v: number): string | null => {
  if (!v) return null;
  const eok = v / 100000;
  if (Math.abs(eok) >= 1) return `${eok.toLocaleString('ko-KR', { maximumFractionDigits: 1 })}억 원`;
  return `${Math.round(v / 10).toLocaleString('ko-KR')}만 원`;
};

/** 백만 원 → '1,234.5억 원'. 값이 없거나 0이면 null. */
export const fmtEok = (mil: string | number) => {
  const n = typeof mil === 'number' ? mil : num(mil);
  return n > 0 ? `${(n / 100).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}억 원` : null;
};

/** 구·군별 집계 (기업 수·종사자) */
export function byDistrict() {
  const m = new Map<string, { firms: number; workers: number }>();
  for (const c of companies()) {
    const k = c.district || '기타'; const cur = m.get(k) ?? { firms: 0, workers: 0 };
    cur.firms++; cur.workers += Number(c.workers) || 0; m.set(k, cur);
  }
  return [...m.entries()].map(([name, v]) => ({ name, ...v })).sort((a, b) => b.workers - a.workers);
}

/** 지원사업 수혜 이력(scripts/data/support_history.csv, import_support.py). 공개 자료만, 금액은 원문 단위 그대로. */
export type Support = { id: string; name: string; district: string; year: string; layer: string; funder: string; program: string; type: string; amount: string; amount_unit: string; source: string; source_url: string; as_of: string };
let _support: Support[] | null = null;
export const supportHistory = () => (_support ??= readCsv('scripts/data/support_history.csv') as Support[]);
/** 공개 명단의 부가 정보(scripts/data/company_facts.csv, import_extra.py 가 씀): 벤처 확인 유형·유효 기간(date_from~date_to), 창업보육센터·입주일 등. 기업 페이지 '창업·벤처 정보'. 운영자 지시 2026-10-06 */
export type Fact = { id: string; tag: string; detail: string; date_from: string; date_to: string; source: string; source_url: string; as_of: string };
let _facts: Fact[] | null = null;
export const companyFacts = () => (_facts ??= (() => { try { return readCsv('scripts/data/company_facts.csv') as Fact[]; } catch { return [] as Fact[]; } })());
export const factsOf = (id: string) => companyFacts().filter(f => f.id === id).sort((a, b) => (b.date_from || '').localeCompare(a.date_from || ''));
/** 날짜(YYYY-MM-DD)부터 기준일까지 'N년 M개월' — 벤처 확인을 받은 지, 입주한 지. 기준일은 빌드 날짜가 아니라 자료 기준월(as_of)의 말일로 어림 */
export function sinceLabel(from: string, asOf: string): string {
  const m = /^(\d{4})-(\d{2})/.exec(from || ''); const a = /^(\d{4})-?(\d{2})/.exec(asOf || '');
  if (!m || !a) return '';
  const months = (Number(a[1]) - Number(m[1])) * 12 + (Number(a[2]) - Number(m[2]));
  if (months < 0) return '';
  return months < 12 ? `${months}개월` : `${Math.floor(months / 12)}년${months % 12 ? ` ${months % 12}개월` : ''}`;
}
export const supportOf = (id: string) => supportHistory().filter(s => s.id === id).sort((a, b) => b.year.localeCompare(a.year));
/** 최근 n년(올해 포함) 안의 이력만 */
export const recentSupport = (rows: Support[], years = 3) => { const y = new Date().getFullYear() - years + 1; return rows.filter(r => Number(r.year) >= y); };
/** 금액 표시: 원문 단위 그대로 (환산하지 않는다) */
export const fmtAmount = (s: Support) => (s.amount ? `${Number(s.amount).toLocaleString('ko-KR')} ${s.amount_unit || '원'}` : '금액 미공개');

/** DART 재무(scripts/data/company_financials.csv, collect_dart_fin.py). 상장·공시대상 기업만. */
export type Financial = { corp_code: string; name: string; year: string; fs: string; revenue: string; operating_income: string; net_income: string; unit: string; rcept_no: string; source_url: string; as_of: string;
  total_assets?: string; total_liabilities?: string; total_equity?: string; corp_cls?: string; stock_code?: string; induty_code?: string; region?: string;
  revenue_account?: string };   // 매출액 자리에 넣은 계정 이름(금융회사는 영업수익·순영업수익·이자수익, 운영자 지시 2026-10-06)
let _fin: Financial[] | null = null;
export const financials = () => (_fin ??= readCsv('scripts/data/company_financials.csv') as Financial[]);
export const normName = (s: string) => (s || '').replace(/\(주\)|㈜|\(유\)|주식회사|유한회사/g, '').replace(/[\s\-_.,·ㆍ&/()\[\]'"]/g, '').toLowerCase();
export const financialsOf = (name: string) => financials().filter(f => normName(f.name) === normName(name)).sort((a, b) => b.year.localeCompare(a.year));
/** 원 → 억 원 표시 (공시 값 그대로 나눈 것) */
export const fmtEokWon = (won: string) => { const n = Number(won); return won && Number.isFinite(n) ? `${(n / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}억 원` : '—'; };
