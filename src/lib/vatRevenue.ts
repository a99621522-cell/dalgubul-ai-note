import fs from 'node:fs';
import yaml from 'js-yaml';
/** 지자체 세입예산사업명세서(data/vat/revenue/<key>_<year>.csv, scripts/parse_revenue_docs.py) → /vat-revenue.json (운영자 지시 2026-10-27 '세입 자료부터 받아서 해').
 *  세외수입(장 200) 전부와 보조금(장 500) 가운데 시설 종류 낱말이 있는 행만. 값은 예산서 그대로(천원), 부가세 키는 낱말로 짐작한 참고 표시 */
export type RevRow = { mok_code: string; mok: string; dept: string; item: string; amount_k: number; vat_key: string; fac_key: string; grant: boolean; acct: string };
/** 세출 세부사업(사업명·부서·편성목만 — 금액 없음, 운영자 지시 2026-09-30 대구시 예산 미게시): 지출 자동 귀속 매핑표 밑그림·공통 지출(본청 공공운영비)·시설비·보조금 표시 */
export type ExpRow = { bureau: string; dept: string; detail: string; codes: string[]; facility: boolean; public_ops: boolean; grant: boolean; fac_key: string };   // 정책·단위는 JSON 에서 뺌(크기), CSV 에는 있음
export type RevGov = { key: string; code: string; name: string; year: string; source: string; fetched: string; acct: string; note?: string; sum_k: number; grant_k: number; check: { mok: string; diff_k: number }[]; rows: RevRow[]; expense: ExpRow[] };
let cache: RevGov[] | null = null;
function csvRows(p: string): Record<string, string>[] {
  const t = fs.readFileSync(p, 'utf-8').replace(/^﻿/, ''); const lines = t.split(/\r?\n/).filter(Boolean); const head = parseLine(lines[0]);
  return lines.slice(1).map(l => { const c = parseLine(l); const o: Record<string, string> = {}; head.forEach((h, i) => { o[h] = c[i] ?? ''; }); return o; });
}
function parseLine(l: string): string[] { const out: string[] = []; let cur = '', q = false; for (let i = 0; i < l.length; i++) { const ch = l[i]; if (q) { if (ch === '"' && l[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') q = false; else cur += ch; } else if (ch === '"') q = true; else if (ch === ',') { out.push(cur); cur = ''; } else cur += ch; } out.push(cur); return out; }
export function vatRevenue(): RevGov[] {
  if (cache) return cache;
  const idxP = 'data/vat/revenue/index.json'; if (!fs.existsSync(idxP)) return (cache = []);
  const idx = JSON.parse(fs.readFileSync(idxP, 'utf-8')) as Record<string, { gov: string; year: string; source: string; fetched: string; note?: string; sum_k: number; grant_k: number; check?: { mok: string; diff_k: number }[] }>;
  const cfg = fs.existsSync('config/revenue_docs.yml') ? (yaml.load(fs.readFileSync('config/revenue_docs.yml', 'utf-8')) as { govs: { key: string; code: string; name: string; acct?: string }[] }) : { govs: [] };
  const out: RevGov[] = [];
  for (const [k, m] of Object.entries(idx)) {
    if (k.endsWith('_exp')) continue;
    const key = k.replace(/_\d{4}$/, ''); const year = k.slice(-4); const p = `data/vat/revenue/${k}.csv`; if (!fs.existsSync(p)) continue;
    const g = cfg.govs.find(x => x.key === key); const rows = csvRows(p).filter(r => r.jang.startsWith('200') || (r.jang.startsWith('500') && r.fac_key))
      .map(r => ({ mok_code: r.mok_code, mok: r.mok, dept: r.dept || r.bureau, item: r.item, amount_k: Number(r.amount_k) || 0, vat_key: r.vat_key, fac_key: r.fac_key, grant: r.jang.startsWith('500'), acct: r.acct }));
    const ep = `data/vat/revenue/${k}_exp.csv`; const expense: ExpRow[] = fs.existsSync(ep) ? csvRows(ep).map(r => ({ bureau: r.bureau, dept: r.dept, detail: r.detail, codes: r.codes.split(' ').filter(Boolean).map(x => x.split(':')[0]), facility: Number(r.facility_k) > 0, public_ops: Number(r.public_ops_k) > 0, grant: Number(r.grant_k) > 0, fac_key: r.fac_key })) : [];
    out.push({ key, code: g?.code ?? '', name: m.gov, year, source: m.source, fetched: m.fetched, acct: g?.acct ?? '일반회계', ...(m.note ? { note: m.note } : {}), sum_k: m.sum_k, grant_k: m.grant_k, check: (m.check ?? []).map(c => ({ mok: c.mok, diff_k: c.diff_k })), rows, expense });
  }
  const order = (cfg.govs ?? []).map(g => g.key); out.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
  return (cache = out);
}
