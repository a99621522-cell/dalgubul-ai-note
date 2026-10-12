/** /support/ 와 /support-index.json 이 함께 쓰는 '지원받은 대구 기업' 묶음(리디자인 v3 감사 2026-10-12: 전체 명단을 HTML 로 내보내 812KB·DOM 16,765개 → 처음 50곳만 HTML, 나머지는 색인). */
import { companies, supportHistory, fmtAmount, type Support } from './csv';
export type Firm = { key: string; id: string; name: string; district: string; group: string; recs: Support[] };
let _memo: ReturnType<typeof build> | null = null;
function build() {
  const co = new Map(companies().map(c => [c.id, c]));
  const rows = supportHistory().filter(r => r.program);
  const firms = new Map<string, Firm>();
  for (const r of rows) {
    const key = r.id || `n:${r.name}`;
    const c = r.id ? co.get(r.id) : undefined;
    if (r.id && !c) continue; // 목록에서 제외된 기업(개인 성명 등)
    const f = firms.get(key) ?? { key, id: r.id, name: c?.name ?? r.name, district: c?.district ?? r.district, group: c?.sector_group ?? '', recs: [] };
    f.recs.push(r);
    firms.set(key, f);
  }
  const list = [...firms.values()].sort((a, b) => a.name.localeCompare(b.name, 'ko'));
  const funders = [...new Set(rows.map(r => r.funder).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ko'));
  const years = [...new Set(rows.map(r => r.year).filter(Boolean))].sort().reverse();
  const groupsList = [...new Set(list.map(f => f.group).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ko'));
  const PAGE = 50;
  const sources = [...new Set(rows.map(r => r.source))];
  const withAmount = rows.filter(r => r.amount).length;
  const sumRecs = (f: Firm) => { const a = f.recs.filter(r => r.amount); if (!a.length) return ''; const units = new Set(a.map(r => r.amount_unit || '원')); if (units.size > 1) return '단위 혼재'; return `${a.reduce((s, r) => s + Number(r.amount), 0).toLocaleString('ko-KR')} ${[...units][0]}`; };
  const row = (f: Firm) => { const recs = [...f.recs].sort((a, b) => b.year.localeCompare(a.year));
    return { f, recs, years: recs.at(-1)!.year !== recs[0].year ? `${recs.at(-1)!.year}~${recs[0].year}` : recs[0].year,
      top: recs.slice(0, 3).map(r => ({ head: `${r.year} ${r.program.length > 48 ? r.program.slice(0, 48) + '…' : r.program}`, meta: `· ${r.funder}${r.type ? ` · ${r.type}` : ''}${r.amount ? ` · ${fmtAmount(r)}` : ''}` })),
      sum: sumRecs(f) || '—' }; };
  return { rows, list, funders, years, groupsList, PAGE, sources, withAmount, row };
}
export const supportFirms = () => (_memo ??= build());
/** 색인 한 줄: [이름, id, 구군, 산업, 이력 수, 연도 범위, [[사업, 메타]…3], 금액 합, 기관|…, 연도|…, 사업명 낱말] */
export const supportIndex = () => { const { list, row } = supportFirms(); return list.map(f => { const r = row(f);
  return [f.name, f.id, f.district || '', f.group || '', r.recs.length, r.years, r.top.map(t => [t.head, t.meta]), r.sum,
    [...new Set(r.recs.map(x => x.funder))].join('|'), [...new Set(r.recs.map(x => x.year))].join('|'), r.recs.map(x => x.program.slice(0, 60)).join(' ')]; }); };
