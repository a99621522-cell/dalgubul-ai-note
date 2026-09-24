import fs from 'node:fs';
import yaml from 'js-yaml';

/** 입지 유형·태그. 규칙은 config/site_types.yml 에만 있다 (scripts/sites.py 와 같은 판정 순서). */
type SiteType = { key: string; name: string; complexes?: string[]; address?: string[]; rule?: 'in_complex' | 'default' };
type Config = { version: string; types: SiteType[]; outside_complex: string; tags: Record<string, { name: string; desc: string }>; startup_years: number };
let _cfg: Config | null = null;
const cfg = () => (_cfg ??= yaml.load(fs.readFileSync('config/site_types.yml', 'utf-8')) as Config);

export const siteTypes = () => cfg().types.map(t => ({ key: t.key, name: t.name }));
export const siteKey = (name: string) => cfg().types.find(t => t.name === name)?.key ?? null;
export const siteName = (key: string) => cfg().types.find(t => t.key === key)?.name ?? null;
export const OUTSIDE = () => cfg().outside_complex;
export const tagName = (key: string) => cfg().tags[key]?.name ?? key;
export const tagDesc = (key: string) => cfg().tags[key]?.desc ?? '';
export const allTags = () => Object.entries(cfg().tags).map(([key, v]) => ({ key, ...v }));

export function siteType(complex: string, address: string): string {
  const cx = (complex ?? '').trim();
  const addr = (address ?? '').replace(/\s/g, '');
  for (const t of cfg().types) {
    if (cx && (t.complexes ?? []).includes(cx)) return t.name;
    if ((t.address ?? []).some(p => addr.includes(p.replace(/\s/g, '')))) return t.name;
    if (t.rule === 'in_complex' && cx && cx !== '개별입지' && cx !== cfg().outside_complex) return t.name;
    if (t.rule === 'default') return t.name;
  }
  return cfg().types.at(-1)!.name;
}
export function isStartup(founded: string, asOf: string): boolean {
  const y = /(\d{4})/.exec(founded ?? ''), a = /(\d{4})/.exec(asOf ?? '');
  return !!(y && a && Number(a[1]) - Number(y[1]) <= cfg().startup_years);
}
