import { VAT_GOV } from './vatLock';
import { lockGov } from './vatLock';
import fs from 'node:fs';
import yaml from 'js-yaml';
/** 지자체 부가가치세 매입세액 점검기 규칙(data/vat/rules.yml, 운영자 지시 2026-10-27). 조문 번호·뜻만, 평가 없음. 브라우저 판정은 src/scripts/vat_check.ts */
export type Basis = { law: 'act' | 'decree' | 'rule' | 'basic' | 'special' | 'special_decree'; art: string };
export type Facility = { key: string; name: string; status: 'taxable' | 'exempt' | 'check'; group: string; note: string; verify?: boolean; interp?: boolean; cond?: string; rulings?: string[]; basis: Basis[] };
export type Opt = { key: string; name: string };
export type NonDed = { key: string; no: string; name: string; fix: string; basis: Basis[] };
export type Skip = { key: string; name: string; cond: string; ratio_lt?: number; amount_lt?: number };
export type CheckItem = { stage: string; id: string; text: string; basis: Basis[] };
export type Preset = { key: string; org: string; read: string; note: string; findings?: string[]; sources: { title: string; url: string; eff: string }[]; facilities: { name: string; type: string; op?: string; run?: string; share?: number; contractor?: string; term?: string; note?: string; alias?: string[]; ask?: unknown[] }[] };
export type VatRules = {
  version: string; verified?: { date: string; act: string; decree: string; rule: string }; law_url: string; laws: Record<string, string>;
  taxable_principle: { summary: string; basis: Basis[]; notes: string[] };
  facilities: Facility[];
  rules: {
    deductible: { summary: string; basis: Basis[] };
    nondeductible: NonDed[];
    card: { summary: string; not_allowed: string; basis: Basis[]; verify?: boolean };
    late_invoice: { summary: string; basis: Basis[]; verify?: boolean };
    common: { summary: string; formula: string; skip: Skip[]; no_supply: string; prelim: string; basis: Basis[] };
    recalc: { summary: string; formula: string; rates: { building: number; other: number }; threshold_pp: number; basis: Basis[] };
    convert: { summary: string; basis: Basis[]; verify?: boolean };
    filing: { periods: { name: string; span: string; due: string }[]; notes: string[]; basis: Basis[]; verify?: boolean };
  };
  inputs: Record<'use' | 'kind' | 'proof' | 'supplier' | 'timing', Opt[]>;
  common_items: { item: string; vat: string; tip: string }[];
  checklist: CheckItem[];
  glossary?: { key: string; term: string; plain: string; text: string; basis?: Basis[] }[];
};
let cache: VatRules | null = null;
export function vatRules(): VatRules | null {
  if (cache) return cache;
  const p = 'data/vat/rules.yml';
  if (!fs.existsSync(p)) return null;
  cache = yaml.load(fs.readFileSync(p, 'utf-8')) as VatRules;
  /* 유권해석·판례 원문(data/vat/rulings/<id>.txt, scripts/fetch_vat_rulings.py 가 국가법령정보센터·조세심판원·U-LEX 에서 받음 — 운영자 2026-10-28 '니가 받아서 붙여') */
  const dir = 'data/vat/rulings';
  for (const r of ((cache as unknown as { rulings?: { id: string; text?: string }[] }).rulings ?? [])) { const f = `${dir}/${r.id}.txt`; if (fs.existsSync(f)) r.text = fs.readFileSync(f, 'utf-8'); }
  return cache;
}
/** 국가법령정보센터 조문 링크: https://www.law.go.kr/법령/부가가치세법/제39조 */
export const lawUrl = (r: VatRules, b: Basis) => r.law_url.replace('{law}', r.laws[b.law]).replace('{art}', b.art);
export const lawName = (r: VatRules, b: Basis) => ({ act: '법', decree: '시행령', rule: '시행규칙', basic: '국세기본법', special: '조특법', special_decree: '조특법 시행령' } as Record<string, string>)[b.law] + ' ' + b.art;
/** 예시 설정(data/vat/presets/*.yml — 공개 자치법규로 만든 시설 목록, 운영 방식·등록번호 없음) */
export function vatPresets(): Preset[] {
  const dir = 'data/vat/presets'; if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter(f => f.endsWith('.yml')).sort().map(f => yaml.load(fs.readFileSync(`${dir}/${f}`, 'utf-8')) as Preset).filter(p => lockGov([{ key: p.key }]).length > 0);
}
/** 기관 사업자등록번호(data/vat/orgs — 나라장터 수요기관 CSV 가 있으면 먼저, 그다음 2차 자료 yml) */
export function vatOrgNumbers(): OrgNo[] {
  const out: OrgNo[] = []; const csvp = 'data/vat/orgs/daegu_g2b.csv', ymlp = 'data/vat/orgs/daegu_orgs.yml';
  if (fs.existsSync(csvp)) { const lines = fs.readFileSync(csvp, 'utf-8').replace(/\r/g, '').split('\n').filter(Boolean); const head = lines[0].split(','); const ix = (k: string) => head.indexOf(k);
    for (const l of lines.slice(1)) { const c = l.split(','); const bz = (c[ix('bizno')] ?? '').replace(/\D/g, ''); if (bz.length !== 10) continue; if (ix('kind') >= 0 && !/지방자치단체|지방공기업|출자출연/.test(c[ix('kind')] ?? '')) continue; /* 국가기관·준정부기관·우체국 등은 점검기 대상이 아니라 화면에 싣지 않는다 */ out.push({ name: c[ix('name')] ?? '', code: c[ix('code')] || undefined, bizno: `${bz.slice(0, 3)}-${bz.slice(3, 5)}-${bz.slice(5)}`, src: '나라장터 수요기관정보(조달청, 공공데이터포털 15129466)' }); } }
  if (fs.existsSync(ymlp)) { const y = yaml.load(fs.readFileSync(ymlp, 'utf-8')) as { orgs?: OrgNo[] }; for (const o of y.orgs ?? []) if (!out.some(x => x.bizno === o.bizno)) out.push(o); }
  return out;
}
/** 지자체별 특성(data/vat/govs.yml) + 자료 범위(예시 설정 시설 수·세입예산서 줄 수·나라장터 계약 기간과 건수) */
/** 지자체 맞춤 '먼저 볼 곳'(govs.yml focus — 2026-11-08 수성구 전용 사이트) */
export type GovFocus = { key: string; title: string; match: string; why: string; todo?: string; area?: boolean };
export type GovProfile = { key: string; name: string; level: string; status: string; corp: { name: string; bizno?: string; src?: string; note?: string }[]; traits: string[]; focus?: GovFocus[]; exclude_note?: string; preset?: number; revenue?: number; contracts?: { from: string; to: string; n: number } };
export function vatGovs(): GovProfile[] {
  const p = 'data/vat/govs.yml'; if (!fs.existsSync(p)) return []; const L = ((yaml.load(fs.readFileSync(p, 'utf-8')) as { govs?: GovProfile[] }).govs ?? []);
  const presets = vatPresets();
  return lockGov(L).map(g => { const out: GovProfile = { ...g, corp: g.corp ?? [], traits: g.traits ?? [] }; const pr = presets.find(x => x.key === g.key); if (pr) out.preset = pr.facilities.length;
    const rv = `data/vat/revenue/${g.key}_2026.csv`; if (fs.existsSync(rv)) out.revenue = fs.readFileSync(rv, 'utf-8').split('\n').filter(Boolean).length - 1;
    const ct = `data/vat/contracts/${g.key}.json`; if (fs.existsSync(ct)) { try { const j = JSON.parse(fs.readFileSync(ct, 'utf-8')) as { from?: string; to?: string; rows?: unknown[] }; out.contracts = { from: j.from ?? '', to: j.to ?? '', n: j.rows?.length ?? 0 }; } catch { /* */ } }
    return out; });
}
/** 감사·권익위·경정청구 공표 사례(data/vat/cases.yml) */
export type AuditCase = { id: string; kind: string; org: string; date: string; title: string; facts: string; amount?: string; keys: string[]; mistakes?: string[]; src: string; url?: string; verify?: boolean };
/** 공단이 없는 지자체 전용 사이트(VAT_GOV 빌드)에서는 공단·대행 사례를 빼 헷갈리지 않게(운영자 2026-11-08 '공단대행 등은 수성구 공무원이 헷갈릴 수 있잖아') */
const noCorpLock = () => { if (!VAT_GOV) return false; const g = ((fs.existsSync('data/vat/govs.yml') ? (yaml.load(fs.readFileSync('data/vat/govs.yml', 'utf-8')) as { govs?: { key: string; corp?: unknown[] }[] }).govs : []) ?? []).find(x => x.key === VAT_GOV); return !!g && !(g.corp ?? []).length; };
const CORP_RX = /공단|대행|지방공사|도시공사|도시관리공사/;
export function vatCases(): AuditCase[] { const p = 'data/vat/cases.yml'; if (!fs.existsSync(p)) return []; const L = ((yaml.load(fs.readFileSync(p, 'utf-8')) as { cases?: AuditCase[] }).cases ?? []); return noCorpLock() ? L.filter(c => !CORP_RX.test(`${c.org} ${c.title} ${c.facts}`) && !(c.keys ?? []).includes('agency')) : L; }
export type OrgNo = { key?: string; name: string; aliases?: string[]; bizno: string; src: string; verify?: boolean; code?: string };
export const STATUS_LABEL: Record<Facility['status'], string> = { taxable: '과세', exempt: '면세', check: '확인 필요' };

/** 감사원 감사결과 공개문에서 부가가치세·매입세액·경정청구·세금계산서가 나온 문단(data/vat/audits/bai, scripts/fetch_bai_vat.py — 운영자 2026-11-03 '감사원 감사 지적사항도 포함시켜'). 발췌 그대로, 평가 없음 */
export type BaiHit = { page: number; kw: string; rel?: 'core' | 'mention'; head: string; text: string; file?: string };
const BAI_CORE = (t: string) => (/부가가치세|부가세|매입세액|매출세액/.test(t) && /매입세액|경정청구|환급|신고|납부|공제|가산세|합계표|안분|납세|과세표준|불공제|과세사업|면세사업|세금계산서/.test(t)) || /매입세액|부가가치세\s*(신고|환급|공제|납부|가산세|경정|예수)/.test(t);
export type BaiReport = { srno: number; title: string; openDt: string; field: string; kind: string; url: string; files: string[]; fetched?: string; hits: BaiHit[]; core: number };
export function vatBai(): { reports: BaiReport[]; scanned: number; noPdf: number; fetched: string } {
  const dir = 'data/vat/audits/bai'; const ip = `${dir}/index.json`; if (!fs.existsSync(ip)) return { reports: [], scanned: 0, noPdf: 0, fetched: '' };
  const idx = JSON.parse(fs.readFileSync(ip, 'utf-8')) as Record<string, { status: string; hits?: number; openDt?: string }>;
  const reports: BaiReport[] = []; let fetched = '';
  for (const [srno, m] of Object.entries(idx)) { if (!m.hits) continue; const p = `${dir}/${srno}.json`; if (!fs.existsSync(p)) continue; const r = JSON.parse(fs.readFileSync(p, 'utf-8')) as BaiReport; r.hits = r.hits.map(h => ({ ...h, rel: h.rel ?? (BAI_CORE(h.text) ? 'core' : 'mention') })).sort((a, b) => (a.rel === 'core' ? 0 : 1) - (b.rel === 'core' ? 0 : 1) || a.page - b.page); r.core = r.hits.filter(h => h.rel === 'core').length; reports.push(r); if ((r.fetched ?? '') > fetched) fetched = r.fetched ?? ''; }
  reports.sort((a, b) => (b.core > 0 ? 1 : 0) - (a.core > 0 ? 1 : 0) || b.openDt.localeCompare(a.openDt));
  return { reports: noCorpLock() ? reports.filter(r => !CORP_RX.test(r.title)) : reports, scanned: Object.values(idx).filter(m => m.status === 'done').length, noPdf: Object.values(idx).filter(m => m.status === 'hwp').length, fetched };
}
