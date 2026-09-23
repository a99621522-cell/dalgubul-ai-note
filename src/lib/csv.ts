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
export type Company = { id: string; name: string; complex: string; district: string; eupmyeon: string; sector_code: string; sector: string; sector_group: string; product: string; workers_band: string; workers: string; reg_type: string; first_registered: string; mfg_area_band: string; address: string; sites: string; source: string; as_of: string };
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
export const companies = () => {
  if (_companies) return _companies;
  const all = readCsv('scripts/data/dalseong_companies.csv') as Company[];
  _companies = all.filter(c => !looksLikePersonName(c.name));
  console.log(`[companies] 개인 성명으로 보이는 공장명 ${all.length - _companies.length}건 제외 (전체 ${all.length} → ${_companies.length})`);
  return _companies;
};
export const complexes = () => readCsv('scripts/data/dalseong_complexes.csv');

/** 부처 사업설명자료 DB(scripts/data/programs_*.csv). 예산 단위는 백만 원(자료 그대로). */
export type Program = Record<string, string> & { src: string; b26: number; b25: number; isNew: boolean; newDerived: boolean; corp: boolean };
const PROGRAM_FILES = ['programs_motie.csv', 'programs_smba.csv', 'programs_ai.csv'];
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
