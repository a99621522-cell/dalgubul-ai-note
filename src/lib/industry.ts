import fs from 'node:fs';
import yaml from 'js-yaml';
import type { Company } from './csv';

/** 대구 주력산업 그룹 분류. 규칙은 config/industry_groups.yml 에만 있다 (scripts/industry.py 와 같은 판정 순서).
 *  1) 업종코드의 가장 긴 접두어 일치 → 2) 업종명+생산품 키워드(그룹 순서가 우선순위) → 3) 미분류.
 *  keyword_first 접두어(개정판이 섞인 34·36 등)는 키워드를 먼저 본다. */
type Group = { key: string; name: string; ksic: string[]; keywords: string[] };
type Config = { version: string; unclassified: string; keyword_first: string[]; service_patterns?: string[]; keep_service?: string[]; groups: Group[] };

let _cfg: Config | null = null;
let _prefixes: Map<string, string> | null = null;
function cfg(): Config {
  if (_cfg) return _cfg;
  _cfg = yaml.load(fs.readFileSync('config/industry_groups.yml', 'utf-8')) as Config;
  _cfg.keyword_first = (_cfg.keyword_first ?? []).map(String);
  _prefixes = new Map();
  for (const g of _cfg.groups) for (const p of g.ksic ?? []) _prefixes.set(String(p), g.name);
  return _cfg;
}

export const UNCLASSIFIED = () => cfg().unclassified;
/** 그룹 목록(우선순위 순). key 는 URL 슬러그(/industry/<key>/). */
export const industryGroups = () => cfg().groups.map(g => ({ key: g.key, name: g.name }));
export const industryKey = (name: string) => cfg().groups.find(g => g.name === name)?.key ?? null;
export const industryName = (key: string) => cfg().groups.find(g => g.key === key)?.name ?? null;

function byPrefix(code: string): string | null {
  cfg();
  code = (code ?? '').trim();
  for (let n = code.length; n > 0; n--) { const hit = _prefixes!.get(code.slice(0, n)); if (hit) return hit; }
  return null;
}
function byKeyword(text: string): string | null {
  const t = (text ?? '').replace(/\s/g, '');
  for (const g of cfg().groups) if ((g.keywords ?? []).some(k => t.includes(k))) return g.name;
  return null;
}
function serviceFirst(text: string): boolean {
  const c = cfg(); const t = (text ?? '').replace(/\s/g, '');
  if ((c.keep_service ?? []).some(k => t.includes(k.replace(/\s/g, '')))) return false;
  return (c.service_patterns ?? []).some(k => t.includes(k.replace(/\s/g, '')));
}
export function classify(code: string, sector = '', product = ''): string {
  const c = cfg(); code = (code ?? '').trim();
  const text = `${sector ?? ''} ${product ?? ''}`;
  if (!code && serviceFirst(text)) return '기타 서비스';
  if (c.keyword_first.some(p => code.startsWith(p))) return byKeyword(text) ?? byPrefix(code) ?? c.unclassified;
  return byPrefix(code) ?? byKeyword(text) ?? c.unclassified;
}
export const industryOf = (co: Company) => classify(co.sector_code, co.sector, co.product);
