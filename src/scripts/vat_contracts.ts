/** 나라장터 계약(조달청 계약정보서비스, /vat-expense/contracts-<gov>.json)을 '지난 돈 돌려받기' 세 걸음에 잇는 공용 모듈(2026-11-05 docs/prompts/vat_refund_3steps.md).
 *  ① 기관을 고르면 그 지자체 계약을 받아 과세기간별로 묶고, ② 신고 매입세액 옆에 '과세 시설일 법한 계약 세액 추정'을 놓아 먼저 볼 기간을 고르며,
 *  ③ 홈택스 매입 목록의 공급자 사업자등록번호를 계약 업체 번호와 맞춰 시설을 저절로 붙인다(사람이 고르는 건을 줄임).
 *  추정은 참고(계약금액 × 10/110) — 돌려받을 금액이 아니다. 시설 지정은 공개 지출 자료 탭과 같은 저장소(localStorage vat-pub-v1)를 쓴다. 새 판정 규칙 없음. */
import { matchMap, matchFacilityName, facilityStatus, bizType, bizTypeRank, claimPeriod, guessCw, type Data, type Org } from './vat_rules';

export type GovMeta = { key: string; name: string; contracts?: { from: string; to: string; rows: number; fetched: string } | null };
export type Ctr = { k: '공사' | '용역' | '물품'; no: string; nm: string; inst: string; dept: string; dmn: string[]; date: string; tot: number; amt: number; mth: string; lng: string; cls: string; corps: { nm: string; no: string; sh?: string }[]; url: string; fin?: string };
export type CGov = { key: string; name: string; fetched: string; from: string; to: string; rows: Ctr[] };
type Asg = { fid: string; use: 'this' | 'multi' | 'admin'; cw?: string };
export type CtrAsg = { a: Asg | undefined; how: '지정' | '자동' | ''; via?: '지정' | '매핑표' | '이름' };

let metasP: Promise<GovMeta[]> | null = null;
export const govMetas = () => (metasP ??= fetch('/vat-expense/index.json').then(r => r.json()).then((j: { govs?: GovMeta[] }) => j.govs ?? []).catch(() => [] as GovMeta[]));
const cache = new Map<string, Promise<CGov | null>>();
export const loadContracts = (gov: string) => { if (!cache.has(gov)) cache.set(gov, fetch(`/vat-expense/contracts-${gov}.json`).then(r => r.ok ? r.json() as Promise<CGov> : null).catch(() => null)); return cache.get(gov)!; };
const pubAsg = (): Record<string, Asg> => { try { const j = JSON.parse(localStorage.getItem('vat-pub-v1') || 'null'); return j?.asg ?? {}; } catch { return {}; } };
/** 이 기관의 지자체 키 — 공개 지출 자료 탭에서 고른 것 > 기관 선택 때 고른 것 > 기관 이름 */
export async function govOf(org: Org | null): Promise<GovMeta | undefined> {
  const metas = await govMetas(); let g = '';
  try { g = JSON.parse(localStorage.getItem('vat-pub-v1') || 'null')?.gov || localStorage.getItem('vat-gov') || ''; } catch { /* */ }
  const byKey = metas.find(m => m.key === g); if (byKey) return byKey;
  const nm = (org?.org ?? '').replace(/\s/g, ''); if (!nm) return undefined;
  return metas.find(m => m.name.replace(/\s/g, '') === nm) ?? metas.find(m => nm.includes(m.name.replace(/\s|대구광역시/g, '')) && m.name.replace(/\s|대구광역시/g, '')) ?? (/^대구광역시(청)?$/.test(nm) ? metas.find(m => m.key === 'daegu') : undefined);
}
export const ctrKey = (c: Ctr) => 'C|' + (c.no || `${c.k}|${c.nm}|${c.date}`);
/** 계약 → 시설(공개 지출 자료 탭 '나라장터 계약' 표와 같은 순서: 사람이 고른 것 > 매핑표 > 시설 이름 일치) */
export function ctrAssign(org: Org | null, c: Ctr, asg = pubAsg()): CtrAsg {
  const k = ctrKey(c); if (asg[k]) return { a: asg[k], how: '지정', via: '지정' }; if (!org) return { a: undefined, how: '' };
  const m = matchMap(org, c.nm, c.dept); if (m) return { a: { fid: m.fid, use: m.use === 'multi' || m.use === 'admin' ? m.use : 'this' }, how: '자동', via: '매핑표' };
  const f = matchFacilityName(org, c.nm); return f ? { a: { fid: f.id, use: 'this' }, how: '자동', via: '이름' } : { a: undefined, how: '' };
}
export const ctrPeriod = (c: Ctr) => claimPeriod(c.date)?.key ?? '';
/** 금차 계약금액 먼저 — 장기계속·계속비는 총계약금액이 차수 계약마다 되풀이되어 더하면 몇 배가 된다(2026-11-05 달성군) */
export const ctrMoney = (c: Ctr) => c.amt || c.tot;
export type CtrCtx = { gov: GovMeta; cg: CGov; rows: { ck: string; span: string; c: Ctr; p: string; a: Asg | undefined; how: CtrAsg['how']; via?: CtrAsg['via']; cw?: string; taxable: boolean; likely: boolean; est: number }[]; biz: Map<string, { a: Asg; nm: string; n: number }> };
/** 공사·용역의 세액 어림을 계약일 ~ 끝나는 날(fin) 사이 과세기간(1~6월·7~12월)에 날수대로 나눈다 — 기성·준공 세금계산서가 기간 내내 나오므로(2026-11-05 달성군 교육문화복지센터 건립공사 641일이 계약일 기간 하나로 몰려 경정청구 기한 밖으로 빠지던 것) */
function spread(date: string, fin: string | undefined, est: number): { p: string; est: number }[] {
  const p0 = claimPeriod(date)?.key ?? ''; if (!fin || fin <= date) return [{ p: p0, est }];
  const a = +new Date(date), b = +new Date(fin); const out: { p: string; d: number }[] = []; let t = a;
  while (t < b) { const d = new Date(t); const y = d.getFullYear(), h = d.getMonth() < 6 ? 1 : 2; const end = +new Date(h === 1 ? `${y}-07-01` : `${y + 1}-01-01`); const e = Math.min(end, b); out.push({ p: `${y}-${h}`, d: e - t }); t = e; }
  const tot = out.reduce((s, x) => s + x.d, 0) || 1; let left = est;
  return out.map((x, i) => { const v = i === out.length - 1 ? left : Math.floor(est * x.d / tot); left -= v; return { p: x.p, est: v }; });
}
/** 계약 묶음 — taxable: 과세 시설(또는 공통)에 붙은 계약, likely: 시설은 못 붙었지만 공제 가능성 있는 사업 유형(rules.yml biz_types, low 아님) */
export async function contractsCtx(D: Data, org: Org | null): Promise<CtrCtx | null> {
  const gov = await govOf(org); if (!gov?.contracts) return null; const cg = await loadContracts(gov.key); if (!cg?.rows?.length) return null;
  const asg = pubAsg();
  const rows = cg.rows.map(c => { const { a, how, via } = ctrAssign(org, c, asg); const f = a && org ? org.facilities.find(x => x.id === a.fid) : undefined; const fs = f ? facilityStatus(D, f) : undefined;
    /* 공사 갈래가 도로·부지 토목이면(고른 값 > 짐작) 공제 없음으로 본다 — '파크골프장 진입도로 개설공사'·'임대주택단지간 도시계획도로' */
    const cw = c.k === '공사' ? (a?.cw || guessCw(c.nm)) : undefined; const gc = guessCw(c.nm); const zero = cw === 'c_road' || cw === 'c_land' || cw === 'c_exempt' || (c.k !== '공사' && gc === 'c_road');   /* 도로 확장 타당성·설계 용역도 시설 지출이 아니다 */
    const taxable = !!a && !zero && (a.fid === 'admin' || a.use !== 'this' || fs === 'taxable' || fs === 'check' || (fs === 'exempt' && typeof f?.share === 'number' && f.share > 0)); const likely = !a && !zero && bizTypeRank(bizType(D, c.nm)) === 0;
    const sh = f && typeof f.share === 'number' && a?.use === 'this' ? f.share : 1; const est = Math.floor(ctrMoney(c) * 10 / 110 * (taxable ? sh : 1)); const parts = spread(c.date, c.fin, est); const span = parts.length > 1 ? `${parts[0].p}~${parts[parts.length - 1].p}` : '';
    return parts.map(x => ({ ck: ctrKey(c), span, c, p: x.p, a, how, via, cw, taxable, likely, est: x.est })); }).flat();
  /* 업체 등록번호 → 시설: 그 업체의 시설이 붙은 계약이 모두 같은 시설일 때만(여러 시설과 계약한 업체는 사람이 고른다) */
  const by = new Map<string, { a: Asg; nm: string; n: number; bad: boolean }>();
  const seenCk = new Set<string>(); for (const r of rows) { if (!r.a || r.a.fid === 'none' || seenCk.has(r.ck)) continue; seenCk.add(r.ck); for (const p of r.c.corps) { if (!/^\d{10}$/.test(p.no)) continue; const cur = by.get(p.no); if (!cur) by.set(p.no, { a: r.a, nm: r.c.nm, n: 1, bad: false }); else { cur.n++; if (cur.a.fid !== r.a.fid || cur.a.use !== r.a.use) cur.bad = true; } } }
  const biz = new Map<string, { a: Asg; nm: string; n: number }>(); for (const [k, v] of by) if (!v.bad) biz.set(k, { a: v.a, nm: v.nm, n: v.n });
  return { gov, cg, rows, biz };
}
