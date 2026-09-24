import fs from 'node:fs';
import yaml from 'js-yaml';

/** 입지 유형·태그. 규칙은 config/site_types.yml 에만 있다 (scripts/sites.py 와 같은 판정 순서). */
type SiteType = { key: string; name: string; complexes?: string[]; address?: string[]; buildings_file?: string; rule?: 'in_complex' | 'default' };
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

const _buildings = new Map<string, RegExp[]>();
/** 건물 주소 패턴: '구군 + 도로명 건물번호'(공백 제거) 뒤에 숫자·'-'가 오지 않아야 한다 (scripts/sites.py 와 같은 규칙). */
function buildings(t: SiteType): RegExp[] {
  if (!t.buildings_file) return [];
  if (!_buildings.has(t.buildings_file)) {
    const pats: RegExp[] = [];
    if (fs.existsSync(t.buildings_file)) {
      const lines = fs.readFileSync(t.buildings_file, 'utf-8').replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean);
      const head = lines[0].split(',');
      const di = head.indexOf('district'), ri = head.indexOf('road_address');
      for (const l of lines.slice(1)) {
        const c = l.split(',');
        const key = ((c[di] ?? '') + (c[ri] ?? '')).replace(/\s/g, '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        if (key) pats.push(new RegExp(key + '(?![\\d-])'));
      }
    }
    _buildings.set(t.buildings_file, pats);
  }
  return _buildings.get(t.buildings_file)!;
}
export function siteType(complex: string, address: string): string {
  const cx = (complex ?? '').trim();
  const addr = (address ?? '').replace(/\s/g, '');
  for (const t of cfg().types) {
    if (cx && (t.complexes ?? []).includes(cx)) return t.name;
    if ((t.address ?? []).some(p => addr.includes(p.replace(/\s/g, '')))) return t.name;
    if (buildings(t).some(b => b.test(addr))) return t.name;
    if (t.rule === 'in_complex' && cx && cx !== '개별입지' && cx !== cfg().outside_complex) return t.name;
    if (t.rule === 'default') return t.name;
  }
  return cfg().types.at(-1)!.name;
}
export function isStartup(founded: string, asOf: string): boolean {
  const y = /(\d{4})/.exec(founded ?? ''), a = /(\d{4})/.exec(asOf ?? '');
  return !!(y && a && Number(a[1]) - Number(y[1]) <= cfg().startup_years);
}
