/** /vat/schedule/ 환급·기한 일정표(세무회계법인 관점 검토 2026-10-27, 5번): 이 브라우저의 설정·기록·신고 기록·신축 사업에서 날짜가 있는 것을 한 달력으로 —
 *  예정·확정 신고기한(법 제48조·제49조), 환급 예정일(법 제59조 제1항 30일 / 제2항 15일), 조기환급 신고기한(시행령 제107조), 수정세금계산서 기한(시행령 제70조), 경정청구 기한(국세기본법 제45조의2, 5년), 재계산·정산 확인(확정신고), 인계표 마감. 날짜 계산만, 평가 없음 */
import { $, esc, fmt, loadData, getOrg, allLedgers, getFilings, claimPeriod, periodInfo, earlyRefundSchedule, downloadText, toCsv, ymd, type Data, type PeriodKey } from './vat_rules';
import { getProjects } from './vat_build';
type Ev = { date: string; kind: string; what: string; link?: string; tax?: number };
const D = loadData();
if (D) init(D);
function init(D: Data) {
  const org = getOrg(); const today = ymd(new Date()); const now = new Date(); const evs: Ev[] = [];
  const horizon = (() => { const d = new Date(now.getFullYear() + 1, now.getMonth() + 6, 1); return ymd(d); })();
  const plus = (d: string, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return ymd(x); };
  const fd = D.rules.build?.refund_days ?? { file_within: 25, refund_within: 15, normal_within: 30 };
  /* 신고기한·환급 예정 */
  for (let y = now.getFullYear() - 1; y <= now.getFullYear() + 1; y++) for (const k of ['1P', '1F', '2P', '2F'] as const) { const key: PeriodKey = `${y}-${k}`; const P = periodInfo(key); const fl = getFilings()[key];
    evs.push({ date: P.due, kind: '신고', what: `${P.name} 신고·납부 기한${fl ? ` — 신고 기록 저장됨(${fl.saved})` : ''}`, link: '/vat/prepare/' });
    if (fl) { const pay = ['1', '3', '4'].reduce((t, n) => t + (fl.cells[n]?.tax ?? 0), 0) - (['10', '12', '13', '14', '44', '45', '48'].reduce((t, n) => t + (fl.cells[n]?.tax ?? 0), 0) - ['53', '54'].reduce((t, n) => t + (fl.cells[n]?.tax ?? 0), 0));
      if (pay < 0) evs.push({ date: plus(P.due, P.kind === 'F' ? fd.normal_within : fd.refund_within), kind: '환급', what: `${P.name} 환급 예정 상한 — ${P.kind === 'F' ? '확정신고기한 뒤 30일(설비 투자·영세율이면 15일)' : '예정신고기한 뒤 15일(조기환급 사유가 있을 때)'}`, tax: -pay, link: '/vat/trend/' }); }
    if (P.kind === 'F') { const assets = Object.values(getFilings()).filter(f => f.period !== key && f.period < key).flatMap(f => f.assets ?? []).filter(a => a.common); if (assets.length) evs.push({ date: P.due, kind: '확인', what: `${P.name} — 지난 기 취득 공통 자산 ${assets.length}건 면세비율 5%p 변동 재계산 확인(시행령 제83조)`, link: '/vat/prepare/' }); }
  }
  /* 경정청구 기한 — 신고 기록이 있는 과세기간 + 지난 5년 과세기간(안내) */
  for (const fl of Object.values(getFilings())) { if (!fl.period.endsWith('F')) continue; const P = periodInfo(fl.period); const c = claimPeriod(`${P.y}-${P.half === 1 ? '06' : '12'}-01`, now); if (c && c.days >= 0) evs.push({ date: c.claim, kind: '경정청구', what: `${c.name} 경정청구 기한(법정신고기한 ${c.due} + 5년, 국세기본법 제45조의2)`, link: '/vat/review/' }); }
  const oldest = claimPeriod(ymd(new Date(now.getFullYear() - 5, now.getMonth(), 1)), now); if (oldest && oldest.days >= 0) evs.push({ date: oldest.claim, kind: '경정청구', what: `가장 오래된 청구 가능 과세기간 ${oldest.name}의 경정청구 기한 — 지난 신고 점검으로 빠진 매입세액 확인`, link: '/vat/review/' });
  /* 수정세금계산서 기한(다른 명의 빨강) */
  for (const [k, rows] of Object.entries(allLedgers())) { const fid = k.split(':')[0]; const f = org?.facilities.find(x => x.id === fid); for (const r of rows) if (r.fix_due && r.v === 'no' && !r.done) evs.push({ date: r.fix_due, kind: '수정세금계산서', what: `${f?.name ?? fid} · ${r.d} ${r.desc} — 다른 명의 세금계산서 수정 발급 기한(시행령 제70조 제1항 제6호)`, tax: r.tax, link: '/vat/monthly/' }); }
  /* 조기환급(신축 사업) */
  for (const p of getProjects()) if (p.every) for (const r of earlyRefundSchedule(p.start, p.end, p.every, D)) { evs.push({ date: r.fileDue, kind: '조기환급', what: `${p.name} ${r.from}${r.to !== r.from ? `~${r.to}` : ''} 조기환급 신고기한(시행령 제107조 제4항)`, link: '/vat/build/' }); evs.push({ date: r.refundBy, kind: '환급', what: `${p.name} ${r.from}${r.to !== r.from ? `~${r.to}` : ''} 조기환급 환급 기한(신고기한 뒤 15일)`, link: '/vat/build/' }); }
  /* 인계표 마감(앞 6개월) */
  if (org?.handover_day) for (let i = 0; i < 6; i++) { const d = new Date(now.getFullYear(), now.getMonth() + i, org.handover_day); evs.push({ date: ymd(d), kind: '인계', what: `${ymd(new Date(d.getFullYear(), d.getMonth() - 1, 1)).slice(0, 7)} 매입 인계표 마감(기관 설정)`, link: '/vat/monthly/' }); }
  const showPast = $<HTMLInputElement>('sc-past'); const draw = () => {
    const list = evs.filter(e => e.date <= horizon && (showPast?.checked || e.date >= today)).sort((a, b) => a.date.localeCompare(b.date) || a.kind.localeCompare(b.kind));
    const dd = (d: string) => Math.round((new Date(d).getTime() - new Date(today).getTime()) / 86400000);
    $('sc-list')!.innerHTML = list.length ? `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table" id="sc-table" data-stack="off"><caption>환급·기한 일정표 — ${today} 기준 ${list.length}건(${showPast?.checked ? '지난 것 포함' : '오늘 이후'}, ${horizon.slice(0, 7)}월까지)</caption><thead><tr><th scope="col">날짜</th><th scope="col">D-day</th><th scope="col">종류</th><th scope="col">할 일</th><th scope="col">세액</th><th scope="col" class="no-print">화면</th></tr></thead><tbody>${list.map(e => { const n = dd(e.date); return `<tr class="${n < 0 ? 'done' : n <= 7 ? 'v-no' : ''}"><td>${e.date}</td><td>${n < 0 ? `${-n}일 지남` : `D-${n}`}</td><td><span class="verdict ${e.kind === '환급' ? 'ok' : e.kind === '수정세금계산서' ? 'no' : e.kind === '경정청구' ? 'split' : e.kind === '확인' || e.kind === '인계' ? 'none' : 'check'}">${e.kind}</span></td><td>${esc(e.what)}</td><td>${e.tax ? fmt(e.tax) : ''}</td><td class="no-print keep">${e.link ? `<a href="${e.link}">열기</a>` : ''}</td></tr>`; }).join('')}</tbody></table></div>` : '<p class="empty">일정이 없습니다.</p>';
    $('sc-sum')!.innerHTML = `신고 ${list.filter(e => e.kind === '신고').length} · 환급 ${list.filter(e => e.kind === '환급').length} · 조기환급 ${list.filter(e => e.kind === '조기환급').length} · 수정세금계산서 ${list.filter(e => e.kind === '수정세금계산서').length} · 경정청구 ${list.filter(e => e.kind === '경정청구').length}`;
    $('sc-csv')?.addEventListener('click', () => downloadText(`부가세일정-${today}.csv`, toCsv([['날짜', '종류', '할 일', '세액'], ...list.map(e => [e.date, e.kind, e.what, e.tax ?? ''])]), 'text/csv;charset=utf-8'), { once: true });
  };
  showPast?.addEventListener('change', draw); $('sc-print')?.addEventListener('click', () => window.print()); draw();
}
