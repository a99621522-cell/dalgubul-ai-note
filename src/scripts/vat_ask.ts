/** 확인 질문 엔진(docs/design/vat-minimize.md 3절 — 운영자 2026-11-05 '공무원이 해야 할 일을 최대한 줄여야 돼').
 *  사실 공백을 예/아니오 질문으로 바꾸고, 걸린 금액이 큰 순서로 10개까지 하나씩 묻는다. 답하면 시설 유형·운영 방식·매출 신고 여부를 고쳐 저장하고 다시 계산한다.
 *  질문의 출처: ① 예시 설정 시설의 ask(조사로 남은 확인 사항) ② 운영 방식 '확인 필요'이고 돈이 걸린 시설 ③ 면세 유형인데 세입예산서 수입이 있는 시설(그 수입을 과세 매출로 신고해 왔는지 — 매출 쪽 과다 납부).
 *  새 판정 규칙 없음 — 답은 시설 설정을 바꿀 뿐이고 판정은 judge·facilityStatus 그대로. 판정은 참고이며 기관의 판단이 아니다. */
import { esc, fmt, setOrg, facilityRule, facilityStatus, ymd, type Data, type Org, type OrgFacility, type AskDef, type Run } from './vat_rules';

export type Question = { fid: string; fname: string; def: AskDef; stake: number; stakeNote: string; kind: 'preset' | 'run' | 'sales' };
const RUN_OPTS: AskDef['opts'] = [
  { label: '군이 직접 운영(직영)', patch: { run: 'direct' } },
  { label: '공단·수탁기관이 군 이름으로 운영(사용료가 군 세입)', patch: { run: 'entrusted_org' } },
  { label: '수탁기관이 자기 사업으로 운영(사용료가 수탁기관 수입)', patch: { run: 'entrusted_own' } }];
/** 시설 메모의 '[세입예산서 …] … N천원' 들을 더한 연간 세입(원) */
export const revenueOf = (f: OrgFacility) => { let t = 0; for (const m of (f.note ?? '').matchAll(/\[세입예산서[^\]]*\][^[]*?([\d,]+)천원/g)) t += Number(m[1].replace(/,/g, '')) * 1000; return t; };
const presetAsk = (D: Data, org: Org) => { const m = new Map<string, AskDef[]>(); const p = (D.presets ?? []).find(x => x.org === org.org || org.org.includes(x.org.replace(/^대구광역시\s*/, ''))); for (const f of p?.facilities ?? []) if (f.ask?.length) { m.set(f.name, f.ask); for (const a of f.alias ?? []) m.set(a, f.ask); } return m; };
/** 질문 목록 — stake: 시설별 { tax: 매입 목록 세액, est: 경정청구 기간 계약 세액 어림 } */
export function buildQuestions(D: Data, org: Org | null, stake: Map<string, { tax: number; est: number }>, years = 5): Question[] {
  if (!org) return []; const PA = presetAsk(D, org); const out: Question[] = [];
  for (const f of org.facilities) {
    if (f.track === false) continue; const s = stake.get(f.id) ?? { tax: 0, est: 0 }; const money = s.tax || s.est; const note = s.tax ? `이 시설에 붙은 매입 세액 ${fmt(s.tax)}원` : s.est ? `경정청구 기간 계약 세액 어림 ${fmt(s.est)}원(참고)` : '';
    for (const def of PA.get(f.name) ?? []) if (!f.answers?.[def.id]) out.push({ fid: f.id, fname: f.name, def, stake: money, stakeNote: note, kind: 'preset' });
    if (f.run === 'unknown' && money > 0 && !f.answers?.run && ['taxable', 'check'].includes(facilityStatus(D, f))) out.push({ fid: f.id, fname: f.name, kind: 'run', stake: money, stakeNote: note, def: { id: 'run', q: `「${f.name}」은 누가 운영하나요?`, why: '군 이름으로 운영하면(직영·대행) 그 시설 지출의 매입세액을 군이 공제하고, 수탁기관 자기 사업이면 수탁기관이 공제합니다 — 위·수탁 협약서와 세입예산서(사용료가 군 세입인지)로 확인.', opts: RUN_OPTS } });
    const rev = revenueOf(f); const st = facilityStatus(D, f);
    if (rev > 0 && st === 'exempt' && f.run !== 'entrusted_own' && !f.answers?.sales) { const over = Math.floor(rev * 10 / 110) * years; out.push({ fid: f.id, fname: f.name, kind: 'sales', stake: over, stakeNote: `매출세액 과다 납부 어림 ${fmt(over)}원(연 수입 ${fmt(rev)}원 × 10/110 × ${years}년)`, def: { id: 'sales', q: `「${f.name}」 수입(세입예산서 연 ${fmt(rev)}원)을 부가세 과세 매출로 신고해 왔나요?`, why: `이 시설은 '${facilityRule(D, f)?.name ?? f.type}' 유형으로 면세입니다. 과세 매출로 신고해 왔다면 낸 매출세액을 경정청구로 돌려받을 수 있습니다(다만 그 시설 지출 매입세액을 공제해 왔다면 그만큼은 불공제로 바뀝니다 — 순효과로 봄).`, opts: [{ label: '예 — 과세로 신고해 왔음', patch: { salesTaxed: true } }, { label: '아니오 — 면세로 신고(또는 신고 안 함)', patch: { salesTaxed: false } }] } }); }
  }
  return out.sort((a, b) => b.stake - a.stake).slice(0, 10);
}
/** 답 적용 — 이전 값은 answers[].prev 에 남겨 되돌릴 수 있게 */
export function answer(org: Org, fid: string, def: AskDef, i: number | null) {
  const f = org.facilities.find(x => x.id === fid); if (!f) return; const opt = i === null ? null : def.opts[i];
  (f.answers ??= {})[def.id] = { label: opt ? opt.label : '모름', at: ymd(new Date()), prev: { type: f.type, run: f.run, share: f.share } };
  if (opt?.patch) { const p = opt.patch; if (p.type) f.type = p.type; if (p.run) f.run = p.run as Run; if (p.salesTaxed !== undefined) f.salesTaxed = p.salesTaxed; if (p.share !== undefined) { if (p.share === null) delete f.share; else f.share = p.share; } f.note = `${f.note ?? ''} [확인 ${ymd(new Date())}] ${def.q} → ${opt.label}${p.note ? ` — ${p.note}` : ''}`.trim(); }
  setOrg(org);
}
export function undo(org: Org, fid: string, id: string) { const f = org.facilities.find(x => x.id === fid); const a = f?.answers?.[id]; if (!f || !a) return; if (a.prev) { f.type = a.prev.type; f.run = a.prev.run; if (a.prev.share === undefined) delete f.share; else f.share = a.prev.share; } if (id === 'sales') delete f.salesTaxed; delete f.answers![id]; setOrg(org); }
/** 매출 쪽 과다 납부 어림 합(답이 '예'인 시설) */
export const salesOver = (D: Data, org: Org | null, years = 5) => (org?.facilities ?? []).filter(f => f.salesTaxed && facilityStatus(D, f) === 'exempt').map(f => ({ f, over: Math.floor(revenueOf(f) * 10 / 110) * years }));

export function askHtml(D: Data, org: Org | null, qs: Question[], idx: number): string {
  if (!org) return '';
  const answered = org.facilities.flatMap(f => Object.entries(f.answers ?? {}).map(([id, a]) => ({ f, id, a }))); const so = salesOver(D, org);
  if (!qs.length && !answered.length) return '';
  const q = qs[Math.min(idx, qs.length - 1)];
  return `<section class="rf-ask" aria-labelledby="rf-ask-h"><div class="rf-h"><h2 id="rf-ask-h">확인 질문 ${qs.length ? `<span class="meta">${qs.length}개 남음 — 걸린 금액 큰 순, 답하면 바로 다시 계산</span>` : '<span class="meta">모두 답함</span>'}</h2></div>
    ${q ? `<div class="rf-q" data-fid="${esc(q.fid)}" data-qid="${esc(q.def.id)}"><p class="rf-q-t"><b>${esc(q.def.q)}</b></p>${q.stakeNote ? `<p class="note">이 답에 걸린 금액: <b>${esc(q.stakeNote)}</b></p>` : ''}${q.def.why ? `<p class="note">${esc(q.def.why)}</p>` : ''}
      <div class="actions">${q.def.opts.map((o, i) => `<button type="button" class="btn${i ? ' secondary' : ''}" data-ans="${i}">${esc(o.label)}</button>`).join('')}<button type="button" class="btn secondary" data-ans="x">모름(나중에)</button>${qs.length > 1 ? `<button type="button" class="link-btn" data-qnext>다음 질문 보기</button>` : ''}</div></div>` : ''}
    ${so.length ? `<p class="note">매출 쪽 과다 납부 어림(판단 필요): ${so.map(x => `${esc(x.f.name)} ${fmt(x.over)}원`).join(' · ')} — 신고서 과세표준 명세로 확정합니다.</p>` : ''}
    ${answered.length ? `<details class="vat-more"><summary>답한 질문 ${answered.length}개</summary><ul class="meta-list">${answered.map(x => `<li>${esc(x.f.name)} — ${esc(x.a.label)} <span class="meta">${esc(x.a.at)}</span> <button type="button" class="link-btn" data-undo="${esc(x.f.id)}|${esc(x.id)}">되돌리기</button></li>`).join('')}</ul></details>` : ''}</section>`;
}
