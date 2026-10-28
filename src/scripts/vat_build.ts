/** /vat/build/ 신축·대수선 설계 단계 점검 + 조기환급 일정(세무회계법인 관점 검토 2026-10-27, 2번 — 운영 구조가 정해져 있어도 투자 주체는 지자체):
 *  공사비·예정사용면적·공사 기간을 넣으면 ① 공제·불공제 예상(예정사용면적 비율, 시행령 제81조 제4항 단서·토지분 불공제 법 제39조 제1항 제7호) ② 조기환급 일정(법 제59조 제2항 제2호·시행령 제107조: 매월/매 2월, 기간 끝 +25일 신고, +15일 환급)
 *  ③ 설계·계약·집행·완공 점검표(localStorage `vat-build-v1`). 조문·날짜 계산만, 평가 없음. 서버 없음 */
import { $, esc, num, fmt, pct, loadData, lawLink, getOrg, earlyRefundSchedule, downloadText, toCsv, ymd, monthStr, periodKeyOf, periodInfo, type Data } from './vat_rules';
export type BuildProject = { name: string; cost: number; land: number; taxArea: number; exArea: number; shared: number; start: string; end: string; every: 1 | 2 | 0; reg: 'yes' | 'no'; checks: Record<string, boolean>; saved: string };
export const BUILD_KEY = 'vat-build-v1';
export const getProjects = (): BuildProject[] => { try { const v = JSON.parse(localStorage.getItem(BUILD_KEY) || '[]'); return Array.isArray(v) ? v : []; } catch { return []; } };
const setProjects = (a: BuildProject[]) => { try { localStorage.setItem(BUILD_KEY, JSON.stringify(a)); } catch { /* */ } };
export const CHECKS: { stage: string; id: string; text: string; basis: { law: string; art: string } }[] = [
  { stage: '설계', id: 'd1', text: '용도별(과세·면세·공용) 예정사용면적표를 설계도 기준으로 확정했다 — 공급가액이 있어도 건물·구축물 신축·취득은 예정사용면적 비율이 먼저', basis: { law: 'decree', art: '제81조' } },
  { stage: '설계', id: 'd2', text: '전기·수도·가스 계량기를 용도(과세 시설 / 면세·행정)별로 나눠 설계했다 — 완공 뒤 운영비의 실지귀속 근거', basis: { law: 'decree', art: '제81조' } },
  { stage: '설계', id: 'd3', text: '과세 전용 구역과 면세·행정 구역의 출입·동선을 나눠, 공용 면적을 줄였다', basis: { law: 'decree', art: '제81조' } },
  { stage: '설계', id: 'd4', text: '토지 조성·형질변경·철거 비용을 건물 공사비와 분리해 산정했다 — 토지 관련 매입세액은 불공제', basis: { law: 'act', art: '제39조' } },
  { stage: '계약', id: 'c1', text: '공사 계약 내역서(또는 계약 분리)에 용도별·동별 금액이 나뉘어 있어 세금계산서 품목으로 과세·면세·공통을 가를 수 있다', basis: { law: 'decree', art: '제81조' } },
  { stage: '계약', id: 'c2', text: '세금계산서의 공급받는 자가 이 시설(사업장)의 우리 기관 등록번호다 — 수탁기관·시공사 명의가 아니다', basis: { law: 'act', art: '제39조' } },
  { stage: '계약', id: 'c3', text: '착공(첫 세금계산서) 전에 사업자등록 또는 사업장 추가를 마쳤다 — 등록 신청 전 매입세액은 공급시기 과세기간 끝 뒤 20일 안 등록 때만 공제', basis: { law: 'act', art: '제39조' } },
  { stage: '계약', id: 'c4', text: '설계·감리 용역 세금계산서도 같은 명의·같은 용도 구분으로 받는다', basis: { law: 'act', art: '제38조' } },
  { stage: '집행', id: 'e1', text: '조기환급 신고를 매월 또는 매 2월(조기환급기간 끝난 날부터 25일 안)에 낸다 — 예정·확정신고서로 내도 조기환급 신고로 본다', basis: { law: 'decree', art: '제107조' } },
  { stage: '집행', id: 'e2', text: '건물 등 감가상각자산 취득명세서(종류·용도·설비예정일자·설비일자, 공급받은 재화·용역과 매입세액)를 신고서에 붙인다', basis: { law: 'decree', art: '제107조' } },
  { stage: '집행', id: 'e3', text: '조기환급 신고에 매출·매입처별 세금계산서합계표를 붙인다(이것으로 합계표 제출을 갈음)', basis: { law: 'decree', art: '제107조' } },
  { stage: '집행', id: 'e4', text: '용도를 못 가르는 공사비(공통)는 예정사용면적 비율로 안분해 신고한다', basis: { law: 'decree', art: '제81조' } },
  { stage: '완공', id: 'f1', text: '사용면적이 확정되는 과세기간의 확정신고에서 예정사용면적 안분을 정산한다', basis: { law: 'decree', art: '제82조' } },
  { stage: '완공', id: 'f2', text: '자산대장에 취득 과세기간·안분 비율·세액을 적어 뒤 과세기간 면세사용면적 비율이 5%p 이상 달라지면 재계산한다', basis: { law: 'decree', art: '제83조' } },
  { stage: '완공', id: 'f3', text: '면세로 쓰던 부분을 과세사업에 쓰게 되면 과세사업 전환 매입세액을 그 과세기간 확정신고에 공제한다', basis: { law: 'decree', art: '제85조' } },
  { stage: '완공', id: 'f4', text: '준공 뒤 임대·사용허가·대관 계약은 사용료를 과세(부동산임대 등)로 신고하고, 면세 시설 운영비는 처음부터 전용으로 적는다', basis: { law: 'decree', art: '제46조' } }];
const D = loadData();
if (D && $('b-form')) init(D);   // 일정표 화면이 getProjects 를 import 해도 여기 init 은 신축 화면에서만
function init(D: Data) {
  const org = getOrg(); const B = D.rules.build; const g = (k: string) => $<HTMLInputElement | HTMLSelectElement>(k)!;
  const stIn = g('b-start') as HTMLInputElement, enIn = g('b-end') as HTMLInputElement; if (!stIn.value) { stIn.value = monthStr(); const e = new Date(); e.setMonth(e.getMonth() + 11); enIn.value = monthStr(e); }
  const read = (): BuildProject => { const cur = getProjects().find(p => p.name === g('b-name').value.trim()); return { name: g('b-name').value.trim() || '(이름 없음)', cost: num(g('b-cost').value), land: num(g('b-land').value), taxArea: num(g('b-tax').value), exArea: num(g('b-ex').value), shared: num(g('b-shared').value), start: stIn.value, end: enIn.value, every: Number(g('b-every').value) as 0 | 1 | 2, reg: g('b-reg').value as 'yes' | 'no', checks: cur?.checks ?? {}, saved: ymd(new Date()) }; };
  const fill = (p: BuildProject) => { g('b-name').value = p.name; g('b-cost').value = p.cost ? fmt(p.cost) : ''; g('b-land').value = p.land ? fmt(p.land) : ''; g('b-tax').value = p.taxArea ? String(p.taxArea) : ''; g('b-ex').value = p.exArea ? String(p.exArea) : ''; g('b-shared').value = p.shared ? String(p.shared) : ''; stIn.value = p.start; enIn.value = p.end; g('b-every').value = String(p.every); g('b-reg').value = p.reg; };
  const renderSaved = () => { const ps = getProjects(); const sel = $<HTMLSelectElement>('b-saved')!; sel.innerHTML = '<option value="">— 저장된 사업 —</option>' + ps.map(p => `<option value="${esc(p.name)}">${esc(p.name)} (${p.start}~${p.end}, ${p.saved})</option>`).join(''); };
  $<HTMLSelectElement>('b-saved')?.addEventListener('change', e => { const p = getProjects().find(x => x.name === (e.target as HTMLSelectElement).value); if (p) { fill(p); run(); } });
  $('b-run')?.addEventListener('click', run); $('b-save')?.addEventListener('click', () => { const p = read(); const ps = getProjects().filter(x => x.name !== p.name); ps.push(p); setProjects(ps); renderSaved(); run(); $('b-msg')!.textContent = `'${p.name}' 저장 — 환급·기한 일정표에 조기환급 신고 기한이 올라갑니다.`; });
  $('b-del')?.addEventListener('click', () => { const n = g('b-name').value.trim(); if (!n || !confirm(`'${n}' 저장을 지웁니다.`)) return; setProjects(getProjects().filter(x => x.name !== n)); renderSaved(); $('b-msg')!.textContent = '지웠습니다.'; });
  $('b-print')?.addEventListener('click', () => window.print());
  function run() {
    const p = read(); const out = $('b-result')!; const bld = Math.max(0, p.cost - p.land); const taxAll = Math.floor(p.cost * 0.1), taxLand = Math.floor(p.land * 0.1), taxBld = taxAll - taxLand;
    const ta = p.taxArea, ea = p.exArea, sh = p.shared; const base = ta + ea; const exRatio = base ? ea / base : 0;   // 공용 면적은 전용 면적 비율로 배분 → 결국 면세 전용 ÷ (과세 전용 + 면세 전용)
    const totalArea = ta + ea + sh; const exAreaAll = base ? ea + sh * exRatio : 0;
    const nondeduct = Math.floor(taxBld * exRatio), deduct = taxBld - nondeduct;
    const months = (() => { const a = Number(p.start.slice(0, 4)) * 12 + Number(p.start.slice(5, 7)), b = Number(p.end.slice(0, 4)) * 12 + Number(p.end.slice(5, 7)); return b >= a ? b - a + 1 : 0; })();
    const perMonth = months ? deduct / months : 0;
    const sched = p.every ? earlyRefundSchedule(p.start, p.end, p.every, D) : [];
    const qOnly = earlyRefundSchedule(p.start, p.end, 2, D).reduce((m, r) => { const k = r.quarterDue; const x = m.get(k) ?? { from: r.from, to: r.to, due: k }; x.to = r.to; m.set(k, x); return m; }, new Map<string, { from: string; to: string; due: string }>());
    const rw = B?.refund_days.refund_within ?? 15; const plus = (d: string, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return ymd(x); };
    const monthsIn = (a: string, b: string) => (Number(b.slice(0, 4)) * 12 + Number(b.slice(5, 7))) - (Number(a.slice(0, 4)) * 12 + Number(a.slice(5, 7))) + 1;
    const dayDiff = (a: string, b: string) => Math.round((new Date(b).getTime() - new Date(a).getTime()) / 86400000);
    const regWarn = p.reg === 'no' ? `<div class="callout warn"><strong>사업자등록(사업장 추가) 전입니다.</strong> ${esc(B?.pre_reg ?? '')} 등록 신청일 전 공급시기의 세금계산서는 공급시기 과세기간이 끝난 뒤 20일 안에 등록해야 공제됩니다 — 착공 전에 등록을 마치세요.</div>` : '';
    const unitWarn = org && org.unit === 'site' && !org.facilities.some(f => f.reg_no) ? '<p class="meta">기관 설정이 사업장별 등록인데 등록번호가 없는 시설만 있습니다 — 이 시설의 등록번호(또는 사업자 단위 과세)로 세금계산서를 받습니다.</p>' : '';
    out.innerHTML = `<div class="section-head"><h2>결과 — ${esc(p.name)}</h2><span class="meta">참고용 계산 · 공사비 균등 집행 가정</span></div>${regWarn}${unitWarn}
      <div class="vc-card"><h3>공제·불공제 예상 (예정사용면적 비율, 시행령 제81조 제4항 단서)</h3>
      ${tbl('매입세액 갈래', ['구분', '금액', '세액', '설명'], `
        <tr><th scope="row">공사비 전체</th><td>${fmt(p.cost)}</td><td>${fmt(taxAll)}</td><td class="note">공급가액 × 10%</td></tr>
        <tr><th scope="row">토지 관련(조성·철거 등)</th><td>${fmt(p.land)}</td><td>${fmt(taxLand)}</td><td class="note">불공제 — 법 제39조 제1항 제7호</td></tr>
        <tr><th scope="row">건물·구축물·설비</th><td>${fmt(bld)}</td><td>${fmt(taxBld)}</td><td class="note">면세 예정사용면적 비율 ${pct(exRatio)}${sh ? ` (공용 ${fmt(sh)}㎡는 전용 비율로 배분 → 면세 ${fmt(Math.round(exAreaAll))}㎡ ÷ 전체 ${fmt(totalArea)}㎡)` : ''}</td></tr>
        <tr class="total"><th scope="row">공제 예상</th><td></td><td>${fmt(deduct)}</td><td class="note">과세 몫 ${pct(1 - exRatio)} — 조기환급 대상</td></tr>
        <tr class="total"><th scope="row">불공제 예상</th><td></td><td>${fmt(nondeduct + taxLand)}</td><td class="note">면세 몫 ${fmt(nondeduct)} + 토지 ${fmt(taxLand)} — 공사비(원가)에 들어감</td></tr>`)}
      <ul class="meta-list"><li>면세 면적 ${fmt(ea)}㎡를 ${fmt(Math.round(base * 0.01))}㎡(1%p)만큼 과세 용도로 설계하면 공제가 약 ${fmt(Math.floor(taxBld * 0.01))}원 늘어납니다 — 면적표가 비율을 정합니다.</li><li>${esc(B?.area ?? '')}</li></ul></div>
      <div class="vc-card"><h3>조기환급 일정 — 법 제59조 제2항 제2호 · 시행령 제107조 제4항</h3>
      ${p.every ? tbl(`조기환급 신고 ${sched.length}회(매 ${p.every}개월) — 기간 끝난 날부터 25일 안 신고, 신고기한 뒤 15일 안 환급`, ['조기환급기간', '집행 가정 공제 세액', '신고기한', '환급 기한', '분기 신고로만 하면(예정·확정 + 15일)', '앞당겨지는 날'], sched.map(r => { const n = monthsIn(r.from, r.to); const alt = plus(r.quarterDue, rw); return `<tr><th scope="row">${r.from}${r.to !== r.from ? `~${r.to}` : ''}</th><td>${fmt(Math.floor(perMonth * n))}</td><td>${r.fileDue}</td><td>${r.refundBy}</td><td>${alt}</td><td>${dayDiff(r.refundBy, alt)}일</td></tr>`; }).join('')) : tbl('예정·확정신고로만 환급(조기환급 신고 안 함) — 설비 투자는 신고기한 뒤 15일 안 환급', ['신고 대상 기간', '집행 가정 공제 세액', '신고기한', '환급 기한'], [...qOnly.values()].map(r => `<tr><th scope="row">${r.from}~${r.to}</th><td>${fmt(Math.floor(perMonth * monthsIn(r.from, r.to)))}</td><td>${r.due}</td><td>${plus(r.due, rw)}</td></tr>`).join(''))}
      <ul class="meta-list"><li>${esc(B?.early_refund ?? '')}</li><li>환급은 과세 몫(공제 예상 ${fmt(deduct)}원)에만 생깁니다. 같은 기간 매출세액이 있으면 그만큼 상계된 뒤 남는 금액이 환급됩니다.</li><li>조기환급 신고를 한 기간은 예정·확정신고 때 다시 넣지 않습니다(이미 신고한 매입).</li></ul></div>
      <div class="vc-card"><h3>설계 → 계약 → 집행 → 완공 점검표</h3><p class="meta">체크는 이 브라우저에 사업 이름으로 저장됩니다(「저장」). 조문은 국가법령정보센터 링크.</p>
      ${['설계', '계약', '집행', '완공'].map(st => `<h4>${st}</h4><ul class="checks">${CHECKS.filter(c => c.stage === st).map(c => `<li><label><input type="checkbox" data-chk="${c.id}" ${p.checks[c.id] ? 'checked' : ''}/> <span>${esc(c.text)}</span> <span class="note">${lawLink(D, c.basis as { law: 'act' | 'decree'; art: string })}</span></label></li>`).join('')}</ul>`).join('')}
      <p class="meta">근거: ${(B?.basis ?? []).map(b => lawLink(D, b)).join(' · ')} · 토지분 ${lawLink(D, { law: 'act', art: '제39조' })}</p></div>
      <div class="actions no-print"><button type="button" class="btn secondary" id="b-csv">일정·점검표 CSV</button></div>`;
    out.querySelectorAll<HTMLInputElement>('[data-chk]').forEach(c => c.addEventListener('change', () => { const ps = getProjects(); const cur = ps.find(x => x.name === p.name); if (!cur) { $('b-msg')!.textContent = '체크를 남기려면 먼저 「저장」을 누르세요.'; return; } cur.checks[c.dataset.chk!] = c.checked; setProjects(ps); }));
    $('b-csv')?.addEventListener('click', () => { const rows: (string | number)[][] = [['사업', p.name], ['공사비', p.cost, '토지분', p.land, '면세 면적 비율', pct(exRatio)], ['공제 예상', deduct, '불공제 예상', nondeduct + taxLand], [], ['조기환급기간', '집행 가정 공제 세액', '신고기한', '환급 기한'], ...sched.map(r => [`${r.from}~${r.to}`, Math.floor(perMonth * monthsIn(r.from, r.to)), r.fileDue, r.refundBy]), [], ['단계', '점검 항목', '근거', '확인'], ...CHECKS.map(c => [c.stage, c.text, `${c.basis.law === 'act' ? '법' : '시행령'} ${c.basis.art}`, p.checks[c.id] ? '예' : ''])]; downloadText(`신축점검-${p.name}.csv`, toCsv(rows), 'text/csv;charset=utf-8'); });
    void periodKeyOf; void periodInfo;
  }
  renderSaved();
}
const tbl = (cap: string, head: string[], body: string) => `<div class="scroll-x"><table class="data-table vat-table form" data-stack="off"><caption>${cap}</caption><thead><tr>${head.map(h => `<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;
