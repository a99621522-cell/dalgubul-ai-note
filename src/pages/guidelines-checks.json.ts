import type { APIRoute } from 'astro';
import fs from 'node:fs';
import path from 'node:path';

/** 예산서 검토기(/programs/guidelines/check/)가 받는 검토표+규칙 묶음. 빌드 때 /guidelines-checks.json 으로 생성된다.
 *  checks: data/guidelines/checks/<key>.json(검토표), rules: rules.json(자동 판정 규칙), index: 지침 이름·시행일·URL. */
export const GET: APIRoute = () => {
  const dir = path.join(process.cwd(), 'data', 'guidelines');
  const cdir = path.join(dir, 'checks');
  const checks = fs.existsSync(cdir) ? fs.readdirSync(cdir).filter(f => f.endsWith('.json') && f !== 'rules.json').map(f => JSON.parse(fs.readFileSync(path.join(cdir, f), 'utf-8'))) : [];
  const rules = fs.existsSync(path.join(cdir, 'rules.json')) ? JSON.parse(fs.readFileSync(path.join(cdir, 'rules.json'), 'utf-8')) : { doc_patterns: {}, stage_patterns: {}, items: {} };
  const idx = fs.existsSync(path.join(dir, 'index.json')) ? JSON.parse(fs.readFileSync(path.join(dir, 'index.json'), 'utf-8')) : { items: {} };
  const index: Record<string, { name: string; eff: string; url: string; issuer: string }> = {};
  for (const c of checks) {
    const e = (idx.items ?? {})[c.key] ?? {};
    index[c.key] = { name: e.found || e.name || c.name, eff: e.eff || '', url: e.url || '', issuer: e.found_issuer || e.issuer || '' };
  }
  const body = JSON.stringify({ checks, rules, index });
  return new Response(body, { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
};
