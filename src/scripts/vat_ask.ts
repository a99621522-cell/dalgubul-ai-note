/** 확인 질문 엔진(docs/design/vat-minimize.md 3절 — 운영자 2026-11-05 '공무원이 해야 할 일을 최대한 줄여야 돼' → '확인 질문을 최대한 줄일 수 있게 해. 절차가 많아지면 편리성이 없어').
 *  원칙 ① 기본값: 사례 조사로 남은 사실(예시 설정의 ask)은 조사로 확인된 답, 확인 못 한 것은 돌려받을 금액을 적게 잡는 답을 기본값으로 바로 적용한다(answers[id].auto).
 *       ② 묻는 것은 답에 따라 돌려받을 금액이 문턱 이상 달라지는 것만 — 매입 목록을 올렸으면 그 시설에 붙은 세액 기준 100만 원, 올리기 전에는 계약 어림 기준 1,000만 원.
 *       ③ 같은 종류(도시공원 여부, 매출 신고 여부)는 한 질문의 체크 목록으로 묶는다.
 *       ④ 화면에는 금액 큰 순 3개까지, 나머지는 '더 정확히(선택)'에 접는다. 기본값은 목록에서 언제든 바꿀 수 있다.
 *  새 판정 규칙 없음 — 답은 시설 설정(유형·운영 방식·과세 몫·매출 신고 여부)을 바꿀 뿐이고 판정은 judge·facilityStatus 그대로. 판정은 참고이며 기관의 판단이 아니다. */
import { esc, fmt, setOrg, facilityRule, facilityStatus, ymd, type Data, type Org, type OrgFacility, type AskDef, type AskOpt, type Run } from './vat_rules';

export type Member = { fid: string; fname: string; def: AskDef; value: number; yes: number };
export type Question = { key: string; kind: 'preset' | 'run' | 'sales'; group: boolean; q: string; why?: string; members: Member[]; value: number; forced?: boolean };
export const VISIBLE = 3, MAX_Q = 10, T_LIST = 1_000_000, T_EST = 10_000_000;
const RUN_OPTS: AskDef['opts'] = [
  { label: '군이 직접 운영(직영)', patch: { run: 'direct' } },
  { label: '공단·수탁기관이 군 이름으로 운영(사용료가 군 세입)', patch: { run: 'entrusted_org' } },
  { label: '수탁기관이 자기 사업으로 운영(사용료가 수탁기관 수입)', patch: { run: 'entrusted_own' } }];
const SALES_DEF: AskDef = { id: 'sales', q: '', opts: [{ label: '예 — 과세 매출로 신고해 왔음', patch: { salesTaxed: true } }, { label: '아니오 — 면세로 신고(또는 신고 안 함)', patch: { salesTaxed: false } }], gyes: 0 };
/** 시설 메모의 '[세입예산서 …] … N천원' 들을 더한 연간 세입(원) */
export const revenueOf = (f: OrgFacility) => { let t = 0; for (const m of (f.note ?? '').matchAll(/\[세입예산서[^\]]*\][^[]*?([\d,]+)천원/g)) t += Number(m[1].replace(/,/g, '')) * 1000; return t; };
const presetAsk = (D: Data, org: Org) => { const m = new Map<string, AskDef[]>(); const p = (D.presets ?? []).find(x => x.org === org.org || org.org.includes(x.org.replace(/^대구광역시\s*/, ''))); for (const f of p?.facilities ?? []) if (f.ask?.length) { m.set(f.name, f.ask); for (const a of f.alias ?? []) m.set(a, f.ask); } return m; };
/** 패치를 시설 사본에 */
const patched = (f: OrgFacility, p?: AskOpt['patch']): OrgFacility => { const g = { ...f }; if (p?.type) g.type = p.type; if (p?.run) g.run = p.run as Run; if (p && p.share !== undefined) { if (p.share === null) delete g.share; else g.share = p.share; } return g; };
/** 시설 지출 가운데 공제로 세는 몫(judgeRow 의 shareOn 과 같은 뜻: 과세면 과세 몫, 면세면 과세 몫만, 확인·수탁기관·대행은 세지 않음) */
const rateOf = (D: Data, f: OrgFacility) => { const st = facilityStatus(D, f); return st === 'taxable' ? (f.share ?? 1) : st === 'exempt' ? (f.share ?? 0) : 0; };
const swing = (D: Data, f: OrgFacility, def: AskDef) => { const r0 = rateOf(D, f); return Math.max(0, ...def.opts.map(o => Math.abs(rateOf(D, patched(f, o.patch)) - r0))); };
const setPatch = (f: OrgFacility, p?: AskOpt['patch']) => { if (!p) return; if (p.type) f.type = p.type; if (p.run) f.run = p.run as Run; if (p.salesTaxed !== undefined) f.salesTaxed = p.salesTaxed; if (p.share !== undefined) { if (p.share === null) delete f.share; else f.share = p.share; } };

/** 기본값 적용(묻지 않고) — 아직 답이 없는 예시 질문에 default 답을 넣는다. 바뀐 것이 있으면 true */
export function applyAskDefaults(f: OrgFacility, defs: AskDef[] | undefined): boolean {
  let ch = false;
  for (const def of defs ?? []) { if (def.default == null || f.answers?.[def.id]) continue; const o = def.opts[def.default]; if (!o) continue;
    (f.answers ??= {})[def.id] = { label: o.label, at: ymd(new Date()), auto: true, prev: { type: f.type, run: f.run, share: f.share } }; setPatch(f, o.patch); ch = true; }
  return ch;
}
export function applyDefaults(D: Data, org: Org | null): boolean { if (!org) return false; const PA = presetAsk(D, org); let ch = false; for (const f of org.facilities) if (applyAskDefaults(f, PA.get(f.name))) ch = true; if (ch) setOrg(org); return ch; }

/** 질문 목록 — stake: 시설별 { tax: 매입 목록 세액, est: 경정청구 기간 계약 세액 어림 }. hasList 면 tax 기준(문턱 100만 원), 아니면 est 기준(1,000만 원). forced: '바꾸기'를 누른 질문 key */
export function buildQuestions(D: Data, org: Org | null, stake: Map<string, { tax: number; est: number }>, o: { hasList: boolean; salesFiled: number | null; years?: number; forced?: Set<string> } = { hasList: false, salesFiled: null }): Question[] {
  if (!org) return []; const PA = presetAsk(D, org); const years = o.years ?? 5; const T = o.hasList ? T_LIST : T_EST; const forced = o.forced ?? new Set<string>();
  const single: Question[] = []; const groups = new Map<string, Question>();
  const money = (f: OrgFacility) => { const s = stake.get(f.id) ?? { tax: 0, est: 0 }; return o.hasList ? s.tax : s.est; };
  const sales: Member[] = [];
  for (const f of org.facilities) {
    if (f.track === false) continue; const m = money(f);
    for (const def of PA.get(f.name) ?? []) { const a = f.answers?.[def.id]; if (a && !a.auto) continue; const v = Math.round(m * swing(D, f, def)); const key = `${f.id}|${def.id}`;
      const mem: Member = { fid: f.id, fname: f.name, def, value: v, yes: def.gyes ?? 0 };
      if (def.group && !forced.has(key)) { const g = groups.get(def.group) ?? { key: `g:${def.group}`, kind: 'preset', group: true, q: def.gq ?? def.q, why: def.why, members: [], value: 0 }; if (v > 0) { g.members.push(mem); g.value += v; } if (forced.has(g.key) && !g.members.includes(mem)) g.members.push(mem); groups.set(def.group, g); }
      else single.push({ key, kind: 'preset', group: false, q: def.q, why: def.why, members: [mem], value: v, forced: forced.has(key) }); }
    const st = facilityStatus(D, f);
    if (f.run === 'unknown' && !f.answers?.run && ['taxable', 'check'].includes(st)) { const def: AskDef = { id: 'run', q: `「${f.name}」은 누가 운영하나요?`, why: '군 이름으로 운영하면(직영·대행) 그 시설 지출의 매입세액을 군이 공제하고, 수탁기관 자기 사업이면 수탁기관이 공제합니다 — 위·수탁 협약서와 세입예산서(사용료가 군 세입인지)로 확인.', opts: RUN_OPTS };
      const v = Math.round(m * Math.max(rateOf(D, patched(f, { run: 'direct' })), st === 'check' ? 1 : 0)); const key = `${f.id}|run`; single.push({ key, kind: 'run', group: false, q: def.q, why: def.why, members: [{ fid: f.id, fname: f.name, def, value: v, yes: 0 }], value: v, forced: forced.has(key) }); }
    const rev = revenueOf(f);
    if (o.salesFiled && rev > 0 && st === 'exempt' && f.run !== 'entrusted_own' && !f.answers?.sales) sales.push({ fid: f.id, fname: f.name, def: SALES_DEF, value: Math.floor(rev * 10 / 110) * years, yes: 0 });
  }
  /* 매출: 신고서에 과세 매출이 있을 때만(없으면 면세 수입을 과세로 신고했을 수 없음) 한 질문으로 */
  const out: Question[] = [...single, ...groups.values()].filter(q => q.members.length && (q.forced || forced.has(q.key) || q.value >= T));
  const sv = sales.reduce((s, x) => s + x.value, 0);
  if (sales.length && (sv >= T || forced.has('g:sales'))) out.push({ key: 'g:sales', kind: 'sales', group: true, q: `신고서에 과세 매출(${fmt(o.salesFiled ?? 0)}원)이 있습니다. 다음 면세 시설 수입을 그 과세 매출에 넣어 신고해 왔다면 표시하세요`, why: '면세 시설(주차·농기계 임대·체육공원 운동시설 등) 수입을 과세로 신고했다면 낸 매출세액을 경정청구로 돌려받을 수 있습니다(그 시설 매입세액을 공제받아 왔다면 그만큼은 불공제로 바뀝니다 — 순효과로 봄). 시설별 금액은 연 수입 × 10/110 × 5년 어림.', members: sales, value: sv });
  return out.sort((a, b) => Number(!!b.forced || forced.has(b.key)) - Number(!!a.forced || forced.has(a.key)) || b.value - a.value).slice(0, MAX_Q);
}
/** 답 적용 — 이전 값은 answers[].prev 에 남겨 되돌릴 수 있게. i=null 은 '모름'(기본값 그대로) */
export function answer(org: Org, fid: string, def: AskDef, i: number | null) {
  const f = org.facilities.find(x => x.id === fid); if (!f) return; const opt = i === null ? null : def.opts[i]; const prevA = f.answers?.[def.id];
  (f.answers ??= {})[def.id] = { label: opt ? opt.label : `모름 — ${prevA?.auto ? `기본값(${prevA.label}) 그대로` : '바꾸지 않음'}`, at: ymd(new Date()), prev: prevA?.prev ?? { type: f.type, run: f.run, share: f.share } };
  if (opt) { if (prevA?.prev) { f.type = prevA.prev.type; f.run = prevA.prev.run; if (prevA.prev.share === undefined) delete f.share; else f.share = prevA.prev.share; } setPatch(f, opt.patch); f.note = `${f.note ?? ''} [확인 ${ymd(new Date())}] ${def.q || def.id} → ${opt.label}${opt.patch?.note ? ` — ${opt.patch.note}` : ''}`.trim(); }
  setOrg(org);
}
export function undo(org: Org, fid: string, id: string) { const f = org.facilities.find(x => x.id === fid); const a = f?.answers?.[id]; if (!f || !a) return; if (a.prev) { f.type = a.prev.type; f.run = a.prev.run; if (a.prev.share === undefined) delete f.share; else f.share = a.prev.share; } if (id === 'sales') delete f.salesTaxed; delete f.answers![id]; setOrg(org); }
/** 매출 쪽 과다 납부 어림 합(답이 '예'인 시설) */
export const salesOver = (D: Data, org: Org | null, years = 5) => (org?.facilities ?? []).filter(f => f.salesTaxed && facilityStatus(D, f) === 'exempt').map(f => ({ f, over: Math.floor(revenueOf(f) * 10 / 110) * years }));

const isOn = (m: Member, org: Org) => { const f = org.facilities.find(x => x.id === m.fid); if (!f) return false; if (m.def.id === 'sales') return f.salesTaxed === true; const a = f.answers?.[m.def.id]; return !!a && a.label === m.def.opts[m.yes]?.label; };
function qHtml(q: Question, org: Org, hasList: boolean): string {
  const amt = q.value ? `<p class="note">이 답에 따라 돌려받을 금액이 ${hasList ? '' : '(계약 어림, 참고) '}최대 <b>${fmt(q.value)}원</b> 달라집니다.</p>` : '';
  if (q.group) return `<div class="rf-q" data-qkey="${esc(q.key)}"><p class="rf-q-t"><b>${esc(q.q)}</b></p>${amt}${q.why ? `<p class="note">${esc(q.why)}</p>` : ''}
    <ul class="rf-q-list">${q.members.map(m => `<li><label><input type="checkbox" data-gm="${esc(q.key)}" data-fid="${esc(m.fid)}"${isOn(m, org) ? ' checked' : ''}> ${esc(m.fname)}${m.value ? ` <span class="meta">${fmt(m.value)}원</span>` : ''}</label></li>`).join('')}</ul>
    <div class="actions"><button type="button" class="btn" data-gsub="${esc(q.key)}">이대로 확인</button><button type="button" class="btn secondary" data-gsub-x="${esc(q.key)}">모름(기본값 그대로)</button></div></div>`;
  const m = q.members[0];
  return `<div class="rf-q" data-qkey="${esc(q.key)}" data-fid="${esc(m.fid)}" data-qid="${esc(m.def.id)}"><p class="rf-q-t"><b>${esc(q.q)}</b></p>${amt}${q.why ? `<p class="note">${esc(q.why)}</p>` : ''}
    <div class="actions">${m.def.opts.map((o, i) => `<button type="button" class="btn${i ? ' secondary' : ''}" data-ans="${i}">${esc(o.label)}</button>`).join('')}<button type="button" class="btn secondary" data-ans="x">모름(${m.def.default != null ? '기본값 그대로' : '나중에'})</button></div></div>`;
}
export function askHtml(D: Data, org: Org | null, qs: Question[], hasList: boolean): string {
  if (!org) return '';
  const auto = org.facilities.flatMap(f => Object.entries(f.answers ?? {}).filter(([, a]) => a.auto).map(([id, a]) => ({ f, id, a })));
  const answered = org.facilities.flatMap(f => Object.entries(f.answers ?? {}).filter(([, a]) => !a.auto).map(([id, a]) => ({ f, id, a }))); const so = salesOver(D, org);
  if (!qs.length && !answered.length && !auto.length) return '';
  const vis = qs.slice(0, VISIBLE), more = qs.slice(VISIBLE);
  const head = qs.length ? `확인 질문 ${vis.length}개 <span class="meta">답에 따라 금액이 크게 달라지는 것만 — 나머지는 기본값으로 계산했습니다</span>` : `확인할 것 없음 <span class="meta">${hasList ? `답에 따라 ${fmt(T_LIST)}원 넘게 달라지는 사실이 없어 기본값으로 계산했습니다` : '홈택스 매입 목록을 올리면 금액이 크게 갈리는 것만 묻습니다 — 지금은 기본값으로 계산'}</span>`;
  return `<section class="rf-ask" aria-labelledby="rf-ask-h"><div class="rf-h"><h2 id="rf-ask-h">${head}</h2></div>
    ${vis.map(q => qHtml(q, org, hasList)).join('')}
    ${more.length ? `<details class="vat-more"><summary>더 정확히(선택) ${more.length}개</summary>${more.map(q => qHtml(q, org, hasList)).join('')}</details>` : ''}
    ${so.length ? `<p class="note">매출 쪽 과다 납부 어림(판단 필요): ${so.map(x => `${esc(x.f.name)} ${fmt(x.over)}원`).join(' · ')} — 신고서 과세표준 명세로 확정합니다.</p>` : ''}
    ${auto.length ? `<details class="vat-more" id="rf-ask-auto"><summary>기본값으로 계산한 것 ${auto.length}개 <span class="meta">조사로 확인된 사실, 확인 못 한 것은 돌려받을 금액을 적게 잡는 쪽</span></summary><ul class="meta-list">${auto.map(x => `<li>${esc(x.f.name)} — ${esc(x.a.label)} <button type="button" class="link-btn" data-reask="${esc(x.f.id)}|${esc(x.id)}">바꾸기</button></li>`).join('')}</ul></details>` : ''}
    ${answered.length ? `<details class="vat-more"><summary>답한 질문 ${answered.length}개</summary><ul class="meta-list">${answered.map(x => `<li>${esc(x.f.name)} — ${esc(x.a.label)} <span class="meta">${esc(x.a.at)}</span> <button type="button" class="link-btn" data-undo="${esc(x.f.id)}|${esc(x.id)}">되돌리기</button></li>`).join('')}</ul></details>` : ''}</section>`;
}
/** 그룹 질문 제출 — 표시한 곳은 yes 답, 안 한 곳은 다른 답. x=true 면 모두 '모름' */
export function answerGroup(org: Org, q: Question, checked: Set<string>, x = false) {
  for (const m of q.members) answer(org, m.fid, m.def, x ? null : checked.has(m.fid) ? m.yes : (m.def.opts.length === 2 ? 1 - m.yes : (m.def.default ?? null)));
}
export { facilityRule };
