/** 세무대리인(회계사·세무사) 인계 꾸러미(운영자 2026-11-03 '회계사나 법무사에 신고를 의뢰하는 경우도 세입금액·면세액 근거는 공무원이 마련해야' → '둘 다 만드는 게 어때?'):
 *  신고서 서식 대신, 기관이 넘겨야 하는 근거 자료 5가지를 CSV 로 — ① 매출 과세·면세(시설별·등록 단위별) ② 매입 귀속 목록(건별 시설·용도·명의·증빙·판정) ③ 안분 근거 ④ 자산대장·재계산·전환 ⑤ 확인 필요 목록 + 안내문 + 신고서 칸 참고.
 *  계산은 신고 준비(vat_prepare.ts)의 같은 결과를 그대로 옮긴다(새 계산 없음). 담당자 이름·전화 없음. 장부 보관·신고 책임은 기관에 남는다는 것을 안내문에 적는다. */
import { fmt, pct, toCsv, zipStore, downloadBlob, downloadText, ymd, LABEL, PROOF_Q, PAYEE_Q, PAYEE_Q_C, USE_Q, WHAT_Q, EVID_Q, runName, esc, type Data, type Org, type OrgFacility, type LedgerRow, type Filing, type PeriodKey } from './vat_rules';
import type { UsedRow, ConvRow, RecalcRow } from './vat_forms';

export type AgentCtx = {
  D: Data; org: Org; period: PeriodKey; P: { y: number; half: number; kind: 'P' | 'F'; name: string; due: string; own: string[]; prelim: string[] };
  facs: OrgFacility[]; sales: Record<string, { c1: number; c3: number; c4: number; dep?: number; days?: number; rate?: number; deem?: number }>;
  exemptIn: Record<string, number>; oneoffIn: Record<string, number>; prelimIn: Record<string, { taxable: number; exempt: number; common: number; nondeduct: number }>;
  groups: Filing['groups']; groupKey: (f: OrgFacility) => string; used: UsedRow[]; excluded: { f: OrgFacility; m: string; r: LedgerRow }[]; unresolved: { f: OrgFacility; m: string; r: LedgerRow }[];
  missing: { f: OrgFacility; m: string }[]; adminNote: string[]; subsidyRows: { f: OrgFacility; r: LedgerRow; ded: number }[]; lateRows: UsedRow[]; risky: { u: UsedRow; ratio: number }[];
  assets: Filing['assets']; recalc: RecalcRow[]; conv: ConvRow[]; cells: Record<string, { amt: number; tax: number }>; cellName: (no: string) => string;
};
const nm = (opts: { key: string; name: string }[], k: string) => opts.find(o => o.key === k)?.name ?? k;
const BASIS_NAME: Record<string, string> = { supply: '공급가액 비율', purchase: '매입가액 비율', planned: '예정공급가액 비율', area: '예정사용면적 비율' };
const safe = (s: string) => s.replace(/[\\/:*?"<>|]/g, '_');

/** 꾸러미 파일 목록(이름·내용). 금액은 원, CSV 는 BOM 포함(엑셀·한글에서 바로 열림) */
export function agentFiles(x: AgentCtx): { name: string; data: string }[] {
  const { D, org, P } = x; const today = ymd(new Date()); const payees = org.kind === 'contractor' ? PAYEE_Q_C : PAYEE_Q;
  const regOf = (f: OrgFacility) => org.unit === 'entity' ? (org.reg_no ?? '') : (f.reg_no ?? '');
  /* ① 매출 — 시설별 과세 공급가액(신고서 (1)(3)(4))·간주임대료 */
  const s1: (string | number)[][] = [['시설', '시설 유형', '운영 방식', '등록번호', '과세 공급가액 — 세금계산서 발급분 (1)', '과세 공급가액 — 신용카드·현금영수증 (3)', '과세 공급가액 — 기타 (4)', '과세 공급가액 합계', '매출세액(10%)', '임대 보증금', '보증금 일수', '적용 이자율', '간주임대료((4)에 포함)', '비고']];
  for (const f of x.facs) { const s = x.sales[f.id]; const t = D.facilities.find(t => t.key === f.type)?.name ?? f.type; const tot = s ? s.c1 + s.c3 + s.c4 : 0;
    s1.push([f.name, t, runName(org.kind, f.run), regOf(f), s?.c1 ?? 0, s?.c3 ?? 0, s?.c4 ?? 0, tot, Math.floor(tot * 0.1), s?.dep ?? '', s?.days ?? '', s?.rate != null ? s.rate : '', s?.deem ?? '', f.run === 'unknown' ? '운영 방식 확인 필요' : (f.decision ?? '')]); }
  /* ①-2 등록 단위별 면세 공급가액·안분 입력 */
  const s2: (string | number)[][] = [['등록 단위', '이번 기 과세 공급가액', '이번 기 면세 공급가액(면세사업 보조금 포함)', '그중 일회성 면세 공급(토지 매각 등, 참고)', P.kind === 'F' ? '예정신고 때 과세 공급가액' : '', P.kind === 'F' ? '예정신고 때 면세 공급가액' : '', '면세비율(계산)', '안분 기준', '비고'].filter(h => h !== '')];
  for (const g of x.groups) { const pi = x.prelimIn[g.key]; const row: (string | number)[] = [g.name, g.taxable, g.exempt, g.oneoff ?? 0]; if (P.kind === 'F') row.push(pi?.taxable ?? 0, pi?.exempt ?? 0); row.push(pct(g.ratio), BASIS_NAME[g.basis ?? 'supply'] ?? g.basis ?? '', g.skipped ?? ''); s2.push(row); }
  /* ② 매입 귀속 목록 — 신고서에 넣은 것 + 뺀 것(이유) */
  const h2 = ['상태', '신고서 칸', '시설', '등록번호', '날짜', '내용', '공급자', '공급자 등록번호', '공급가액', '세액', '증빙', '받는 사람(명의)', '부가세 구분 표시', '용도(귀속)', '종류', '여러 해 쓰는 것', '실지귀속 근거', '보조사업', '지연 수취', '판정', '할 일', '수정세금계산서 기한'];
  const rowOf = (st: string, cell: string, f: OrgFacility, r: LedgerRow): (string | number)[] => [st, cell, f.name, regOf(f), r.d, r.desc, r.sup ?? '', r.sreg ?? '', r.amt, r.tax, nm(PROOF_Q, r.proof), nm(payees, r.payee), r.vat_sep ? '예' : '아니오', nm(USE_Q, r.use), nm(WHAT_Q, r.what), r.asset ? '예' : '', r.evid ? nm(EVID_Q, r.evid) : '', r.subsidy ? '예' : '', r.late ? '예' : '', LABEL[r.v], r.todo, r.fix_due ?? ''];
  const s3: (string | number)[][] = [h2];
  for (const u of x.used) { const cell = u.isPre ? '(13) 예정신고 누락분' : u.inv ? (u.r.asset ? '(12) 고정자산' : '(10) 일반') : (u.r.asset ? '(45) 고정자산' : '(44) 일반'); s3.push(rowOf(u.r.v === 'no' ? '신고서 포함 — (53) 불공제 명세' : u.r.v === 'split' ? '신고서 포함 — 공통(안분)' : '신고서 포함', cell, u.f, u.r)); }
  for (const e of x.unresolved) s3.push(rowOf('뺌 — 확인 필요(노랑)', '', e.f, e.r));
  for (const e of x.excluded) s3.push(rowOf(e.r.v === 'no' && e.r.payee !== 'org' ? '뺌 — 다른 명의' : '뺌 — 증빙 요건 미달·불공제', '', e.f, e.r));
  /* ③ 안분 근거 */
  const s4: (string | number)[][] = [['등록 단위', '공통매입세액(이번 기)', P.kind === 'F' ? '예정 때 공통매입세액' : '', P.kind === 'F' ? '예정 때 불공제분' : '', '면세비율', '안분 기준', '불공제 계산액 → (54)', '생략·기준 비고', '본청·행정 공통 세액', '본청 안분 기준', '본청 면세분(분자)', '본청 합계(분모)', '본청 비율', '본청 불공제 → (54)'].filter(h => h !== '')];
  for (const g of x.groups) { const pi = x.prelimIn[g.key]; const row: (string | number)[] = [g.name, g.common_tax]; if (P.kind === 'F') row.push(pi?.common ?? 0, pi?.nondeduct ?? 0); row.push(pct(g.ratio), BASIS_NAME[g.basis ?? 'supply'] ?? '', g.nondeduct, g.skipped ?? '', g.admin_tax ?? 0, g.admin_basis ? BASIS_NAME[g.admin_basis] ?? g.admin_basis : (g.admin_tax ? '기준 없음 — (54) 미반영' : ''), g.admin_ex ?? '', g.admin_tot ?? '', g.admin_ratio != null ? pct(g.admin_ratio) : '', g.admin_nondeduct ?? ''); s4.push(row); }
  /* ④ 자산대장·재계산·전환 */
  const s5: (string | number)[][] = [['구분', '시설', '내용', '취득(기준) 과세기간', '세액', '종류(체감률)', '공통 여부', '취득 때 면세비율', '이번 기 면세비율', '경과 과세기간 수', '재계산액·전환 공제액 → (54)/(48)']];
  for (const a of x.assets) s5.push(['이번 기 취득', a.facility, a.desc, a.period, a.tax, a.kind === 'building' ? '건물·구축물(5%)' : '그 밖(25%)', a.common ? '공통' : '과세 전용', a.common ? pct(a.ratio0) : '', '', '', '']);
  for (const r of x.recalc) s5.push(['지난 기 공통 자산 재계산', r.a.facility, r.a.desc, r.a.period, r.a.tax, r.a.kind === 'building' ? '건물·구축물(5%)' : '그 밖(25%)', '공통', pct(r.a.ratio0), pct(r.ratio), r.n, r.amt]);
  for (const c of x.conv) s5.push(['과세사업 전환', '', c.desc, c.acq, c.tax, c.kind === 'building' ? '건물·구축물(5%)' : '그 밖(25%)', c.common ? '공통' : '전용', '', '', c.n, c.credit]);
  /* ⑤ 확인 필요 */
  const s6: (string | number)[][] = [['종류', '시설', '달·날짜', '내용', '세액', '사유·할 일', '기한']];
  for (const e of x.excluded.filter(e => e.r.v === 'no' && e.r.payee !== 'org')) s6.push(['다른 명의 세금계산서', e.f.name, e.r.d, e.r.desc, e.r.tax, '공급자에게 수정세금계산서 요청 — 받으면 다음 신고 또는 경정청구', e.r.fix_due ?? '']);
  for (const e of x.excluded.filter(e => !(e.r.v === 'no' && e.r.payee !== 'org'))) s6.push(['증빙 미달·불공제', e.f.name, e.r.d, e.r.desc, e.r.tax, e.r.title + (e.r.todo ? ' — ' + e.r.todo : ''), '']);
  for (const e of x.unresolved) s6.push(['확인 필요(노랑)', e.f.name, e.r.d, e.r.desc, e.r.tax, e.r.todo, '']);
  for (const r of x.risky) s6.push(['실지귀속 근거 없는 전용 지출', r.u.f.name, r.u.r.d, r.u.r.desc, r.u.r.tax, `계약·계량·검수 기록이 없으면 공통으로 볼 수 있음 — 면세비율 ${pct(r.ratio)}만큼 ${fmt(Math.floor(r.u.r.tax * r.ratio))}원 노출`, '']);
  for (const m of x.missing) s6.push(['기록 없는 시설·달', m.f.name, m.m, '', '', '지출 기록(인계표) 없음 — 없으면 "없음"으로 확인', '']);
  for (const n of x.adminNote) s6.push(['본청·행정 공통 안분 기준 없음', '', '', n, '', '기준(매입가액·예정공급가액·예정사용면적)을 정해 알려 줄 것 — 유권해석 확인', '']);
  for (const s of x.subsidyRows) s6.push(['보조사업 지출', s.f.name, s.r.d, s.r.desc, s.r.tax, `공제받는 부가세 ${fmt(s.ded)}원 — 보조금 정산 지침 확인`, '']);
  for (const l of x.lateRows) s6.push(['지연 수취', l.f.name, l.r.d, l.r.desc, l.r.tax, '(66) 지연수취 가산세 5/1,000', '']);
  for (const f of x.facs.filter(f => f.run === 'unknown')) s6.push(['시설 운영 방식 확인', f.name, '', f.note ?? '', '', '직영·위탁(기관 명의/수탁기관 자기 사업)을 위·수탁 계약으로 확인', '']);
  /* ⑥ 신고서 칸 참고 */
  const s7: (string | number)[][] = [['칸', '이름', '금액', '세액']];
  for (const no of Object.keys(x.cells).sort((a, b) => Number(a) - Number(b))) s7.push([`(${no})`, x.cellName(no), x.cells[no].amt, x.cells[no].tax]);
  const nUsed = x.used.length, nOut = x.unresolved.length + x.excluded.length;
  const guide = `${org.org} 부가가치세 ${P.name} — 세무대리인 인계 자료 (${today} 작성, 지자체 부가세 절감 점검기)

이 꾸러미는 신고서가 아니라 신고서를 만들 근거 자료입니다. 판정·금액은 참고용 계산이며 기관의 판단이 아니고, 장부 기록·보관(부가가치세법 제71조)·세금계산서 수취·합계표 제출과 신고 책임은 ${org.org}에 남습니다.

1. 기관
- 신고 주체: ${org.org}${org.kind === 'contractor' ? `(수탁기관${org.parent ? ', 위탁기관 ' + org.parent : ''})` : ''} · 담당 부서 ${org.dept || '미입력'}
- 등록: ${org.unit === 'entity' ? '사업자 단위 과세, 등록번호 ' + (org.reg_no || '미입력') : '시설(사업장)마다 등록 — 등록번호는 01·02 파일의 열'}
- 과세기간: ${P.name}, 법정신고기한 ${P.due}${P.kind === 'F' ? ' (확정 — 예정신고분을 뺀 정산)' : ''}
- 세무대리인: ${org.agent_org || '(기관 이름 미입력)'}

2. 파일
- 01_매출_과세면세_시설별.csv — 시설 ${x.facs.length}곳의 과세 공급가액 (1)(3)(4)·매출세액·간주임대료. 면세 공급(지자체 고유 업무·열거되지 않은 용역)은 02 파일에 등록 단위로.
- 02_면세공급가액_등록단위.csv — 등록 단위 ${x.groups.length}개의 과세·면세 공급가액(면세사업 보조금 포함), 일회성 면세 공급, 안분 기준.
- 03_매입_귀속목록.csv — 지출 ${nUsed + nOut}건: 신고서에 넣은 ${nUsed}건(칸 번호), 뺀 ${nOut}건(이유). 건마다 시설·용도(전용/공통/본청)·명의·증빙·실지귀속 근거.
- 04_안분_근거.csv — 등록 단위별 공통매입세액·면세비율·안분 기준·불공제 계산액(시행령 제81조~제82조), 본청·행정 공통은 따로.
- 05_자산대장.csv — 이번 기 취득 ${x.assets.length}건, 지난 기 공통 자산 재계산 ${x.recalc.length}건(시행령 제83조), 과세사업 전환 ${x.conv.length}건(제85조).
- 06_확인필요.csv — ${s6.length - 1}건: 다른 명의·증빙 미달·노랑·근거 없는 전용·기록 없는 시설·달·안분 기준·보조사업·지연 수취·운영 방식.
- 07_신고서칸_참고.csv — 점검기가 계산한 칸별 금액·세액(별지 제21호서식 ${D.form_version ?? '2026-04-01'} 판 번호). 대리인이 다시 계산해 견주는 용도.

3. 대리인에게 부탁할 것
- 06 파일의 항목을 함께 정리한 뒤 신고서를 작성(노랑·다른 명의는 뺀 상태).
- 안분 기준과 면세비율(04)은 기관이 정한 값 — 바꾸면 기관에 알려 자산대장(05)의 취득 비율을 맞춤.
- 신고 뒤 접수증·신고서 사본을 기관에 돌려주고, 기관은 점검기 '신고 기록 저장'으로 남겨 다음 기 재계산·인수인계에 씀.

4. 기관이 보관할 것
- 세금계산서·카드 전표 원본, 계약·계량·검수 기록(실지귀속 근거), 세외수입 징수 자료, 이 꾸러미와 신고서 사본.
`;
  return [
    { name: '00_안내.txt', data: guide },
    { name: '01_매출_과세면세_시설별.csv', data: toCsv(s1) }, { name: '02_면세공급가액_등록단위.csv', data: toCsv(s2) }, { name: '03_매입_귀속목록.csv', data: toCsv(s3) },
    { name: '04_안분_근거.csv', data: toCsv(s4) }, { name: '05_자산대장.csv', data: toCsv(s5) }, { name: '06_확인필요.csv', data: toCsv(s6) }, { name: '07_신고서칸_참고.csv', data: toCsv(s7) },
  ];
}

/** 결과 화면 카드. 신고 방식이 '세무대리인 의뢰'면 펼친 카드(첫 행동), 아니면 접힌 펼침 */
export function agentHtml(x: AgentCtx): string {
  const agent = x.org.filing === 'agent'; const nOut = x.unresolved.length + x.excluded.length; const nChk = nOut + x.risky.length + x.missing.length + x.adminNote.length + x.subsidyRows.length + x.lateRows.length + x.facs.filter(f => f.run === 'unknown').length;
  const body = `<p class="meta">회계사·세무사에게 신고를 맡겨도 세입(매출) 과세·면세 금액, 지출의 시설·용도 귀속, 안분 기준은 기관만 알 수 있어 기관이 넘깁니다. 신고서 서식 대신 근거 표 7개와 안내문을 CSV(엑셀·한글에서 열림)로 묶습니다. 장부 보관·신고 책임은 기관에 남습니다.</p>
    <ul class="meta-list"><li>01 매출 과세·면세 — 시설 ${x.facs.length}곳 · 02 면세 공급가액 — 등록 단위 ${x.groups.length}개</li><li>03 매입 귀속 목록 — 신고서 포함 ${x.used.length}건 · 뺀 ${nOut}건(이유 표시)</li><li>04 안분 근거 — 공통매입세액 ${fmt(x.groups.reduce((s, g) => s + g.common_tax + (g.admin_tax ?? 0), 0))}원 · 05 자산대장 — 취득 ${x.assets.length}·재계산 ${x.recalc.length}·전환 ${x.conv.length}</li><li>06 확인 필요 — ${nChk}건 · 07 신고서 칸 참고</li></ul>
    <div class="actions no-print"><button type="button" class="btn${agent ? '' : ' secondary'}" data-agent-zip>세무대리인 인계 꾸러미(zip)</button><button type="button" class="btn secondary" data-agent-txt>안내문만(txt)</button></div>`;
  return agent
    ? `<section class="vc-card" id="p-agent"><h3>세무대리인 인계 꾸러미 — ${esc(x.org.agent_org || '대리인')}에게 넘길 근거 자료</h3>${body}</section>`
    : `<details class="vat-more" id="p-agent"><summary><strong>세무대리인 인계 꾸러미</strong> — 신고를 회계사·세무사에게 맡길 때 넘길 근거 자료 7개</summary>${body}</details>`;
}
export function wireAgent(root: ParentNode, x: AgentCtx) {
  const base = `부가세-대리인인계-${safe(x.org.org)}-${x.period}`;
  root.querySelector('[data-agent-zip]')?.addEventListener('click', () => downloadBlob(`${base}.zip`, zipStore(agentFiles(x))));
  root.querySelector('[data-agent-txt]')?.addEventListener('click', () => downloadText(`${base}-안내.txt`, agentFiles(x)[0].data));
}
