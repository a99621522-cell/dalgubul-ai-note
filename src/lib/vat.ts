import fs from 'node:fs';
import yaml from 'js-yaml';
/** 지자체 부가가치세 매입세액 점검기 규칙(data/vat/rules.yml, 운영자 지시 2026-10-27). 조문 번호·뜻만, 평가 없음. 브라우저 판정은 src/scripts/vat_check.ts */
export type Basis = { law: 'act' | 'decree' | 'rule' | 'basic'; art: string };
export type Facility = { key: string; name: string; status: 'taxable' | 'exempt' | 'check'; group: string; note: string; verify?: boolean; interp?: boolean; basis: Basis[] };
export type Opt = { key: string; name: string };
export type NonDed = { key: string; no: string; name: string; fix: string; basis: Basis[] };
export type Skip = { key: string; name: string; cond: string; ratio_lt?: number; amount_lt?: number };
export type CheckItem = { stage: string; id: string; text: string; basis: Basis[] };
export type Preset = { key: string; org: string; read: string; note: string; sources: { title: string; url: string; eff: string }[]; facilities: { name: string; type: string; note?: string }[] };
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
};
let cache: VatRules | null = null;
export function vatRules(): VatRules | null {
  if (cache) return cache;
  const p = 'data/vat/rules.yml';
  if (!fs.existsSync(p)) return null;
  cache = yaml.load(fs.readFileSync(p, 'utf-8')) as VatRules;
  return cache;
}
/** 국가법령정보센터 조문 링크: https://www.law.go.kr/법령/부가가치세법/제39조 */
export const lawUrl = (r: VatRules, b: Basis) => r.law_url.replace('{law}', r.laws[b.law]).replace('{art}', b.art);
export const lawName = (r: VatRules, b: Basis) => ({ act: '법', decree: '시행령', rule: '시행규칙', basic: '국세기본법' } as Record<string, string>)[b.law] + ' ' + b.art;
/** 예시 설정(data/vat/presets/*.yml — 공개 자치법규로 만든 시설 목록, 운영 방식·등록번호 없음) */
export function vatPresets(): Preset[] {
  const dir = 'data/vat/presets'; if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter(f => f.endsWith('.yml')).sort().map(f => yaml.load(fs.readFileSync(`${dir}/${f}`, 'utf-8')) as Preset);
}
export const STATUS_LABEL: Record<Facility['status'], string> = { taxable: '과세', exempt: '면세', check: '확인 필요' };
