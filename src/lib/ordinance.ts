/** 대구 자치법규 정비 검토(/ordinance/) — scripts/ordin/signals.py 결과(data/ordinance)를 빌드 때 읽는다.
 *  판정이 아니라 '정비 검토 후보'. 순위·평가 표현 없음. 지자체 순서는 행정 순서(config/ordinance.yml). */
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import yaml from 'js-yaml';

const DIR = path.join(process.cwd(), 'data', 'ordinance');
const read = (f: string) => {
  const p = path.join(DIR, f);
  if (!fs.existsSync(p)) return null;
  const b = fs.readFileSync(p);
  return JSON.parse((f.endsWith('.gz') ? zlib.gunzipSync(b) : b).toString('utf-8'));
};
const memo = <T,>(fn: () => T) => { let v: T | undefined; return () => (v ??= fn()); };

export type Org = { key: string; name: string; count: number; listed: number };
export type Sig = { key: string; name: string; conf: 'auto' | 'check'; show: boolean; rule: string; how: string };
export type Cand = {
  id: string; org: string; oid: string; oname: string; kind: string; prom: string; dept: string; url: string;
  no: string; atitle: string; text: string; sig: string; conf: string; ev: Record<string, any>; fix?: { old: string; new: string } | null;
};
export type Summary = {
  fetched: string; built: string; orgs: Org[]; refs: number; refs_resolved: number; refs_unknown: number;
  law_status: Record<string, number>; laws_cited: number; by_signal: Record<string, Record<string, number>>; total: number; expc_held?: number; expc_linked?: number; expc_daegu?: number;
};

export const signals = memo((): Sig[] => {
  const y = yaml.load(fs.readFileSync(path.join(process.cwd(), 'config', 'ordinance_signals.yml'), 'utf-8')) as any;
  return Object.entries(y.signals).map(([key, v]: [string, any]) => ({ key, ...v }));
});
export const sigOf = (k: string) => signals().find(s => s.key === k)!;
export const summary = memo((): Summary | null => read('summary.json'));
export const allCands = memo((): Cand[] => (read('candidates.json.gz')?.items ?? []) as Cand[]);
/** 화면에 내는 후보 — 표본 검증을 통과한 신호(show: true)만 */
export const cands = memo((): Cand[] => { const ok = new Set(signals().filter(s => s.show).map(s => s.key)); return allCands().filter(c => ok.has(c.sig)); });
export const orgs = memo((): Org[] => summary()?.orgs ?? []);
export const orgName = (k: string) => orgs().find(o => o.key === k)?.name ?? k;
export const listItems = memo((): any[] => read('list.json')?.items ?? []);

/** 자치법규별 묶음(행정 순서 → 이름 가나다) */
export const byOrdin = memo(() => {
  const m = new Map<string, { org: string; oid: string; oname: string; kind: string; prom: string; dept: string; url: string; items: Cand[] }>();
  for (const c of cands()) {
    const k = `${c.org}-${c.oid}`;
    if (!m.has(k)) m.set(k, { org: c.org, oid: c.oid, oname: c.oname, kind: c.kind, prom: c.prom, dept: c.dept, url: c.url, items: [] });
    m.get(k)!.items.push(c);
  }
  return m;
});
export const ymd = (s?: string) => (s && s.length === 8 ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6)}` : s || '');

/** 신구조문대비표 초안 — 기계적 신호(fix)가 있는 조문만. 같은 조문의 여러 고침을 한 번에 적용 */
export function draftTable(items: Cand[]) {
  const byNo = new Map<string, { no: string; text: string; fixes: { old: string; new: string }[] }>();
  for (const c of items) {
    if (!c.fix || !c.fix.new) continue;
    if (!byNo.has(c.no)) byNo.set(c.no, { no: c.no, text: c.text, fixes: [] });
    const r = byNo.get(c.no)!;
    if (!r.fixes.some(f => f.old === c.fix!.old)) r.fixes.push(c.fix);
  }
  return [...byNo.values()].map(r => {
    let cur = r.text, neu = r.text;
    for (const f of r.fixes) {
      cur = cur.split(f.old).join(`⟦${f.old}⟧`);
      neu = neu.split(f.old).join(`⟪${f.new}⟫`);
    }
    return { no: r.no, cur, neu, fixes: r.fixes };
  });
}
/** ⟦…⟧(현행의 바뀌는 글자)·⟪…⟫(개정안의 새 글자)를 <u> 로 */
export const mark = (s: string) => s.replace(/[&<>]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[ch]!)).replace(/⟦(.*?)⟧|⟪(.*?)⟫/g, (_m, a, b) => `<u>${a ?? b}</u>`);
