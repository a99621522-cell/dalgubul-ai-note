/**
 * 지자체 부가가치세 점검기 — 공용 규칙·도구 모듈 (운영자 지시 2026-10-27, v2 1단계)
 * data/vat/rules.yml 을 페이지가 JSON(#vat-data, VatData.astro)으로 묻어 주면 여기서 읽는다.
 * judge(): 지출 한 건 판정(공제·안분·불공제·세액 없음·확인) — /vat/tools/ 판정기와 /vat/monthly/ 시설 기록이 같은 규칙을 쓴다.
 * 그 아래는 v2 의 기관 설정(org.json)·시설 월간 기록(ledger)·인계표(CSV)·신고 마감 D-day 도구. 서버 없음, localStorage 와 파일만. 개인정보(이름·전화)는 담지 않는다.
 */
export type Basis = { law: string; art: string };
export type Opt = { key: string; name: string };
export type FacilityRule = { key: string; name: string; status: 'taxable' | 'exempt' | 'check'; group: string; note: string; verify?: boolean; interp?: boolean; basis: Basis[]; contractor_status?: 'taxable' | 'exempt' | 'check' | 'none'; contractor_note?: string };
export type Data = {
  version: string; verified?: { date: string; act: string; decree: string; rule: string; basic?: string }; law_url: string; form_version?: string; laws: Record<string, string>;
  taxable_principle: { summary: string; basis: Basis[]; notes: string[] };
  facilities: FacilityRule[];
  rules: { nondeductible: { key: string; no: string; name: string; fix: string; basis: Basis[] }[]; card: { summary: string; not_allowed: string; verify?: boolean; practice?: string[] }; late_invoice: { summary: string; verify?: boolean };
    common: { summary: string; formula: string; skip: { key: string; name: string; cond: string; ratio_lt?: number; amount_lt?: number }[]; no_supply: string; prelim: string };
    recalc: { rates: { building: number; other: number }; threshold_pp: number };
    filing: { periods: { name: string; span: string; due: string }[]; notes: string[]; claim?: string; verify?: boolean };
    /** 세무회계법인 관점 검토(2026-10-27) — 면세비율 관리·신축 설계·조기환급·가산세 */
    ratio_mgmt?: { proof: { key: Evid; name: string; text: string }[]; exempt_supply: string[]; timing: string; basis: Basis[] };
    build?: { area: string; early_refund: string; refund_days: { file_within: number; refund_within: number; normal_within: number }; pre_reg: string; land: string; basis: Basis[] };
    penalty?: { under_report: number; no_report: number; late_pay_daily: number; late_pay_max_years: number; amend_relief: { months: number; rate: number }[]; late_file_relief: { months: number; rate: number }[]; invoice_late: number; list_missing: number; note: string; basis: Basis[] } };
  inputs: Record<'use' | 'kind' | 'proof' | 'supplier' | 'timing', Opt[]>;
  checklist: { stage: string; id: string; text: string; basis: Basis[] }[];
  revenue_items?: RevenueItem[];
  presets?: Preset[];
};
export type RevenueItem = { key: string; group: string; name: string; status: 'taxable' | 'exempt' | 'check' | 'none'; type?: string; basis: Basis[]; deduct: string; note?: string; only?: 'contractor' | 'gov'; contractor_status?: 'taxable' | 'exempt' | 'check' | 'none'; contractor_note?: string };
/** 기관 종류(운영자 2026-10-27 '시설관리공단 분야도 해야지'): gov = 지자체(제19호 면세 적용), contractor = 수탁기관(시설관리공단·재단 — 일반 사업자 기준, 군 대행사업은 군 명의) */
export type OrgKind = 'gov' | 'contractor';
export type Verdict = 'ok' | 'split' | 'no' | 'none' | 'check';
export const LABEL: Record<Verdict, string> = { ok: '공제', split: '안분 뒤 공제(공통)', no: '불공제', none: '매입세액 없음', check: '확인 필요' };
/** 시설 담당 화면의 신호등 이름(세법 용어 대신) */
export const SIGNAL: Record<Verdict, string> = { ok: '초록 · 공제됩니다', split: '파랑 · 공통 — 신고 때 나눕니다', no: '빨강 · 공제 안 됩니다', none: '회색 · 부가세가 없는 지출', check: '노랑 · 확인이 필요합니다' };
export type Input = { use: string; kind: string; proof: string; supplier: string; timing: string };
export type Out = { v: Verdict; title: string; why: string[]; todo: string[]; basis: Basis[]; verify?: boolean; recalc?: boolean; split?: boolean };
export const LAW: Record<string, string> = { act: '법', decree: '시행령', rule: '시행규칙', basic: '국세기본법' };

export const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T | null;
export const num = (s: string | undefined | null) => { const v = Number(String(s ?? '').replace(/[^0-9.\-]/g, '')); return Number.isFinite(v) ? v : 0; };
export const fmt = (n: number) => Math.round(n).toLocaleString('ko-KR');
export const pct = (r: number) => (r * 100).toFixed(2).replace(/\.?0+$/, '') + '%';
export const esc = (s: string) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' } as Record<string, string>)[c]);

export function loadData(): Data | null { const el = document.getElementById('vat-data'); if (!el) return null; try { return JSON.parse(el.textContent || '') as Data; } catch { return null; } }
export const lawUrl = (D: Data, b: Basis) => D.law_url.replace('{law}', D.laws[b.law]).replace('{art}', b.art);
export const lawText = (b: Basis) => `${LAW[b.law]} ${b.art}`;
export const lawLink = (D: Data, b: Basis) => `<a href="${lawUrl(D, b)}" target="_blank" rel="noopener">${lawText(b)}</a>`;
export function uniq(b: Basis[]) { const seen = new Set<string>(); return b.filter(x => { const k = x.law + x.art; if (seen.has(k)) return false; seen.add(k); return true; }); }
export const optName = (D: Data, g: keyof Data['inputs'], k: string) => D.inputs[g].find(o => o.key === k)?.name ?? k;

/* ---------- 지출 한 건 판정 (조문 번호·뜻만, 평가 아님) ---------- */
export function judge(D: Data, i: Input): Out {
const nd = (k: string) => D.rules.nondeductible.find(n => n.key === k)!;
const B = (law: string, art: string): Basis => ({ law, art });
  const why: string[] = [], todo: string[] = [], basis: Basis[] = []; let verify = false;
  const done = (v: Verdict, title: string, extra: Partial<Out> = {}): Out => ({ v, title, why, todo, basis, verify, ...extra });
  // 1. 부가가치세 거래가 아니거나 면세 거래 — 공제할 세액 자체가 없다
  if (i.kind === 'payroll' || i.kind === 'tax') { why.push('급여·세금·공과금·과태료는 재화·용역의 공급이 아니어서 부가가치세가 붙지 않습니다.'); return done('none', '매입세액이 없는 지출'); }
  if (i.kind === 'insurance' || i.kind === 'exempt_goods') { why.push('보험·금융 용역, 수돗물·도서·교육·의료 같은 면세 재화·용역에는 매입세액이 없습니다.'); basis.push(B('act', '제26조')); return done('none', '면세 거래 — 매입세액 없음'); }
  if (i.proof === 'bill') { why.push('계산서는 면세 거래의 증빙이라 공제할 세액이 없습니다.'); todo.push('과세 거래인데 계산서를 받았다면 공급자에게 세금계산서로 다시 발급을 요청합니다.'); basis.push(B('act', '제26조'), B('act', '제38조')); return done('none', '계산서(면세 거래) — 매입세액 없음'); }
  // 2. 증빙 요건
  if (i.proof === 'receipt') { const n = nd('no_invoice'); why.push(`세금계산서(또는 요건을 갖춘 신용카드매출전표)를 받지 않은 매입세액은 공제하지 않습니다(${n.no}).`); todo.push('공급자가 일반과세자면 공급받는 자를 우리 기관 사업자등록번호로 한 세금계산서를, 카드 결제면 부가가치세액이 따로 적힌 전표를 받습니다.'); todo.push('공급자가 세금계산서를 끊어 주지 않거나 부도·폐업했으면 매입자발행세금계산서(법 제34조의2 — 거래사실확인 신청, 세무서 확인 뒤 매입자가 발급)로 공제받는 길이 있습니다.'); basis.push(...n.basis, B('act', '제34조의2')); return done('no', '증빙 없음 — 불공제'); }
  if (i.proof === 'tax_invoice_other') { const n = nd('no_invoice'); why.push(`공급받는 자가 우리 기관이 아닌 세금계산서는 '사실과 다른 세금계산서'로 공제하지 않습니다(${n.no}).`); todo.push('공급자에게 공급받는 자를 지자체(과세사업 등록번호)로 한 수정세금계산서를 요청합니다. 기한이 있습니다 — 착오로 잘못 적힌 것이면 기한 없이(시행령 제70조 제1항 제5호), 착오가 아닌 사유면 공급일이 속한 과세기간의 확정신고기한 다음 날부터 1년 안에만(제6호) 수정세금계산서를 발급할 수 있고, 그 뒤에는 공제가 영구히 막힙니다. 그 시설이 수탁기관 자기 사업이라면 그 기관의 매입세액이지 우리 것이 아닙니다 — 위·수탁 계약에서 사업자가 누구인지 확인합니다.'); todo.push('공급자가 폐업·부도로 수정세금계산서를 못 끊어 주면 매입자발행세금계산서(법 제34조의2, 거래사실확인 신청)를 검토합니다.'); basis.push(...n.basis, B('decree', '제75조'), B('decree', '제70조'), B('act', '제34조의2')); return done('no', '다른 명의 세금계산서 — 불공제'); }
  if (i.proof === 'card_novat') { why.push('부가가치세액이 따로 적히지 않은 전표, 세금계산서를 발급할 수 없는 간이과세자·면세사업자의 전표는 공제 요건을 갖추지 못합니다.'); todo.push('공급자가 일반과세자면 부가가치세액이 구분된 전표 재발급 또는 세금계산서를 요청합니다. 간이(발급 불가)·면세 공급자면 공제할 수 없습니다.'); basis.push(B('act', '제46조')); verify = !!D.rules.card.verify; return done('no', '요건 못 갖춘 카드 전표 — 불공제'); }
  if (i.proof === 'card_vat') {
    if (i.supplier === 'simple_no') { why.push('세금계산서를 발급할 수 없는 간이과세자·면세사업자의 카드 전표는 공제하지 못합니다.'); basis.push(B('act', '제46조')); return done('no', '영수증 발급 기간 간이과세자·면세 공급자 카드 전표 — 불공제'); }
    if (i.supplier === 'unknown') { why.push('카드 전표로 공제하려면 공급자가 일반과세자(또는 세금계산서를 발급할 수 있는 간이과세자)여야 합니다.'); todo.push('홈택스 「사업자등록 상태 조회」로 공급자의 과세 유형을 확인한 뒤 다시 판정합니다.'); basis.push(B('act', '제46조')); return done('check', '공급자 과세 유형 확인 필요'); }
    todo.push('신고 때 「신용카드매출전표등 수령명세서」에 적고 전표를 5년 보관합니다. 목욕·이발·미용업, 여객운송업(전세버스 제외), 입장권 발행 사업, 비급여 미용 진료, 무도·자동차운전학원의 전표는 공제하지 못합니다(시행령 제88조 제5항).'); basis.push(B('decree', '제88조')); basis.push(B('act', '제46조'), B('act', '제71조')); verify = !!D.rules.card.verify;
  }
  // 3. 종류로 불공제
  if (i.kind === 'land') { const n = nd('land'); why.push(`토지 취득·조성·형질변경, 토지만 쓰려는 건물 철거비의 매입세액은 공제하지 않습니다(${n.no}, 시행령 제80조).`); todo.push('건물 신축·수선 몫이 섞여 있으면 계약·견적에서 토지 관련분과 나눠 적습니다 — 건물분은 공제 대상입니다.'); basis.push(...n.basis); return done('no', '토지 관련 매입세액 — 불공제'); }
  if (i.kind === 'car') { const n = nd('car'); why.push(`8인승 이하 비영업용 승용차의 구입·임차·유지(유류·수리) 매입세액은 공제하지 않습니다(${n.no}).`); todo.push('9인승 이상 승합차·화물차·경차·운수업 등 영업용이면 대상이 아니므로 차종을 확인합니다.'); basis.push(...n.basis); return done('no', '비영업용 승용차 — 불공제'); }
  if (i.kind === 'entertain') { const n = nd('entertain'); why.push(`기업업무추진비(접대비)와 이와 유사한 비용의 매입세액은 공제하지 않습니다(${n.no}).`); todo.push('직원 복리후생비·광고선전비는 여기 들지 않으므로 지출 성격을 서류에 적습니다.'); basis.push(...n.basis); return done('no', '접대·기념품 — 불공제'); }
  // 4. 시기
  if (i.timing === 'prereg') { const n = nd('pre_reg'); why.push(`사업자등록 신청 전의 매입세액은 공제하지 않습니다(${n.no}). 다만 공급시기가 속하는 과세기간이 끝난 뒤 20일 이내에 등록을 신청하면 그 과세기간 시작일까지의 매입세액은 공제됩니다.`); todo.push('등록 신청일과 공급시기가 속한 과세기간 종료일을 견주어 20일 이내인지 확인합니다. 새 과세사업은 시작 전에 등록(또는 업종 추가)합니다.'); basis.push(...n.basis); return done('check', '등록 전 매입세액 — 20일 요건 확인'); }
  if (i.timing === 'late') { why.push(D.rules.late_invoice.summary); todo.push('공급시기가 속한 과세기간의 확정신고기한까지 받았으면 그대로 공제(시행령 제75조 제3호). 그 뒤 1년 안에 받았으면 수정신고·경정청구서와 함께 내야 공제(제7호). 1년이 지났으면 공제할 수 없습니다.'); basis.push(B('decree', '제75조')); verify = verify || !!D.rules.late_invoice.verify; }
  // 5. 위탁수수료·복리후생 성격
  if (i.kind === 'outsource') { why.push('수탁기관(지방공단 등)은 지자체가 아니므로 그 기관이 지자체에 공급하는 용역은 과세이고 세금계산서를 받습니다. 다만 실비를 전달·정산하는 돈이면 용역 공급이 아니어서 세금계산서 대상이 아닙니다.'); todo.push('위·수탁 계약서에서 대행 수수료(용역)와 사업비 실비 정산을 나눠 보고, 용역분은 아래 귀속(과세·면세·공통)에 따라 공제·안분합니다.'); todo.push('민간위탁 사업비가 보조금 교부(수탁자 사업에 대한 지원)면 용역 대가가 아니어서 세금계산서 대상이 아니고, 수탁자가 문화원·재단·협의회 같은 공익 목적 단체면 그 용역이 면세(법 제26조 제1항 제18호, 시행령 제45조 — 주무관청 허가·등록 단체의 실비·무상 공급 등)일 수 있어 계산서가 옵니다. 어느 쪽인지 협약서의 대가 조항으로 가릅니다.'); basis.push(B('act', '제26조'), B('act', '제38조'), B('decree', '제75조')); if (i.use === 'unknown') return done('check', '위탁수수료 — 용역인지 실비 정산인지 확인'); }
  if (i.kind === 'welfare') { why.push('직원 복리후생비는 접대비가 아니며 사업 관련 지출입니다. 그 직원이 어느 사업(과세·면세) 일을 하는지에 따라 귀속이 정해집니다.'); }
  // 6. 귀속
  const cap = i.kind === 'building' || i.kind === 'equip';
  if (i.use === 'exempt') { const n = nd('exempt_use'); why.push(`면세사업·고유 행정사무에 쓰인 매입세액은 공제하지 않습니다(${n.no}).`); todo.push('과세 시설과 함께 쓰인 지출이라면 "면세"가 아니라 "공통"으로 다시 판정합니다.'); basis.push(...n.basis); return done('no', '면세사업 관련 — 불공제'); }
  if (i.use === 'taxable') { why.push('과세사업에만 쓰인 지출의 매입세액은 전액 공제합니다. 실지귀속이 분명하므로 안분하지 않습니다.'); todo.push('지출 원장·계약서에 어느 과세 시설인지 적어 실지귀속 근거를 남깁니다.'); if (cap) todo.push('감가상각자산은 뒤에 면세사업에도 쓰이게 되면 재계산 대상이 되므로 취득 과세기간·매입세액을 자산 대장에 적어 둡니다.'); basis.push(B('act', '제38조'), B('act', '제40조'), B('decree', '제81조')); return done('ok', '과세사업 실지귀속 — 전액 공제', { recalc: cap }); }
  if (i.use === 'common') { why.push('과세·면세에 함께 쓰여 실지귀속을 가를 수 없는 공통매입세액은 총공급가액 중 면세공급가액 비율로 안분해 면세분을 뺍니다.'); todo.push('아래 「공통매입세액 안분 계산기」로 불공제분을 구합니다(면세비율 5% 미만·공통매입세액 500만 원 미만, 5만 원 미만이면 안분 생략). 예정신고 때 안분한 것은 확정신고 때 정산합니다.'); todo.push('계량기·계약을 시설별로 나눌 수 있으면 나눠 실지귀속으로 바꿉니다 — 과세 시설분은 전액 공제됩니다.'); if (cap) todo.push('감가상각자산은 뒤 과세기간 면세비율이 5%p 이상 바뀌면 납부세액을 재계산합니다(법 제41조, 시행령 제83조).'); basis.push(B('act', '제40조'), B('decree', '제81조'), B('decree', '제82조')); if (cap) basis.push(B('act', '제41조'), B('decree', '제83조')); return done('split', '공통매입세액 — 안분 뒤 공제', { recalc: cap, split: true }); }
  why.push('어느 사업에 쓰였는지 모르면 공제 여부를 정할 수 없습니다. 실지귀속을 먼저 가릅니다.'); todo.push('지출 결의서·계약서·검수 조서에서 어느 시설(과세 시설/행정청사/겸용)에 쓰였는지 확인합니다. 시설이 과세사업인지는 「3. 우리 시설은 과세사업인가」 표로 봅니다.'); basis.push(B('act', '제40조'), B('decree', '제81조'));
  return done('check', '귀속(과세·면세·공통) 확인 필요');
}

/* ---------- v2: 기관 설정(org.json) · 시설 기록 · 인계표 ---------- */
export type Run = 'direct' | 'entrusted_org' | 'entrusted_own' | 'unknown';
/** 수탁기관(공단) 설정일 때 운영 방식 이름 — direct = 공단 자기 사업, entrusted_org = 군 대행(군 명의 사업), entrusted_own 은 쓰지 않음 */
export const RUN_NAME_C: Record<Run, string> = { direct: '공단 자기 사업(공단 이름으로 신고)', entrusted_org: '군·시 사업의 대행(군 명의 사업 — 공단 수입은 대행수수료)', entrusted_own: '(쓰지 않음)', unknown: '확인 필요 — 위탁계약으로 정하세요' };
export const runName = (kind: OrgKind | undefined, r: Run) => (kind === 'contractor' ? RUN_NAME_C : RUN_NAME)[r];
export const RUN_NAME: Record<Run, string> = { direct: '우리 기관이 직접 운영', entrusted_org: '위탁 — 우리 기관 명의 사업(수탁기관은 대행)', entrusted_own: '위탁 — 수탁기관 자기 사업(수탁기관이 신고)', unknown: '확인 필요 — 위·수탁 계약으로 정하세요' };
export type Fee = 'taxable' | 'paid_check' | 'free' | 'unknown';
/** 수탁기관 자기 사업 시설에서 우리 기관이 수탁기관에게 받는 것 — 군 부담 지출(수선·장비)의 매입세액 공제 여부를 가른다. 초록은 사용료를 과세로 신고하고 있을 때만(세무사 평가 2차) */
export const FEE_NAME: Record<Fee, string> = { taxable: '사용료·임대료를 받고, 그 사용료를 과세(부동산임대)로 신고하고 있다', paid_check: '사용료·임대료를 받지만 과세로 신고하는지 모름(면세로 보고 있음)', free: '받지 않는다(무상 사용허가·무상 임대)', unknown: '모름 — 위·수탁 계약·사용허가서로 확인' };
export type OrgFacility = { id: string; type: string; name: string; run: Run; contractor_dept?: string; reg_no?: string; income: string[]; deposit: boolean; note?: string; fee?: Fee; decision?: string; kind?: OrgKind };
export type Preset = { key: string; org: string; read: string; note: string; findings?: string[]; sources: { title: string; url: string; eff: string }[]; facilities: { name: string; type: string; op?: string; contractor?: string; term?: string; note?: string }[] };
/** 세출 사업·부서 글자 → 시설 자동 귀속 규칙(붙여넣기 때 사업명·부서 열로 '어디에'를 자동으로, 담당자가 고른 결과를 배워 쌓는다 — 세무회계법인 관점 3번) */
export type MapRule = { pat: string; fid: string; use?: UseQ };
export type Org = { v: 1; org: string; dept: string; unit: 'site' | 'entity'; reg_no?: string; facilities: OrgFacility[]; handover_day: number; created: string; kind?: OrgKind; parent?: string; map?: MapRule[] };
const normPat = (s: string) => String(s ?? '').replace(/\s/g, '').toLowerCase();
/** 사업명·부서 글자에 맞는 규칙 — 사업명 정확히 → 부서 정확히 → 4자 이상 규칙이 사업명에 포함 순 */
export function matchMap(org: Org | null, biz: string, dept: string): MapRule | undefined {
  const rules = org?.map ?? []; if (!rules.length) return undefined; const b = normPat(biz), d = normPat(dept);
  return (b && rules.find(r => normPat(r.pat) === b)) || (d && rules.find(r => normPat(r.pat) === d)) || (b && rules.find(r => normPat(r.pat).length >= 4 && b.includes(normPat(r.pat)))) || undefined;
}
export function learnMap(org: Org, pat: string, fid: string, use?: UseQ) { const p = String(pat ?? '').trim(); if (!p || !fid) return false; const rules = org.map ?? (org.map = []); const i = rules.findIndex(r => normPat(r.pat) === normPat(p)); const r = { pat: p, fid, use }; if (i >= 0) { if (rules[i].fid === fid && rules[i].use === use) return false; rules[i] = r; } else rules.push(r); return true; }
export type ProofQ = 'e_invoice' | 'p_invoice' | 'card' | 'cash' | 'bill' | 'none';
export type PayeeQ = 'org' | 'contractor' | 'person' | 'unknown';
export type UseQ = 'this' | 'multi' | 'admin' | 'unknown';
/** 전용(이 시설만) 지출의 실지귀속 근거 — rules.yml ratio_mgmt.proof 와 같은 키(세무회계법인 관점 4번: 증빙 없는 전용은 조사 때 공통으로 뒤집힐 수 있다) */
export type Evid = 'contract' | 'meter' | 'inspection' | 'none';
export const EVID_Q: Opt[] = [{ key: 'contract', name: '계약·발주서에 시설이 적혀 있다' }, { key: 'meter', name: '시설별 계량기·검침 기록' }, { key: 'inspection', name: '검수 조서·작업 일지에 시설 표시' }, { key: 'none', name: '아직 없음' }];
export type LedgerRow = { id: string; d: string; desc: string; amt: number; tax: number; proof: ProofQ; payee: PayeeQ; vat_sep: boolean; use: UseQ; what: string; asset: boolean; late: boolean; subsidy?: boolean; fix_due?: string; sup?: string; sreg?: string; evid?: Evid; biz?: string; v: Verdict; title: string; todo: string; basis: string; done: boolean };
export const PROOF_Q: Opt[] = [
  { key: 'e_invoice', name: '전자세금계산서(홈택스·메일로 온 것)' }, { key: 'p_invoice', name: '종이 세금계산서' },
  { key: 'card', name: '신용카드 전표(법인·클린카드)' }, { key: 'cash', name: '현금영수증(사업자 지출증빙)' },
  { key: 'bill', name: '계산서(세금계산서가 아닌 것, 면세)' }, { key: 'none', name: '간이영수증·없음' }];
export const PAYEE_Q: Opt[] = [{ key: 'org', name: '우리 기관(군·시)' }, { key: 'contractor', name: '공단·수탁기관' }, { key: 'person', name: '직원 개인' }, { key: 'unknown', name: '모름·안 적혀 있음' }];
export const PAYEE_Q_C: Opt[] = [{ key: 'org', name: '우리 기관(공단·재단)' }, { key: 'contractor', name: '군·시(위탁기관)' }, { key: 'person', name: '직원 개인' }, { key: 'unknown', name: '모름·안 적혀 있음' }];
export const payeeQ = (kind: OrgKind | undefined) => kind === 'contractor' ? PAYEE_Q_C : PAYEE_Q;
export const USE_Q: Opt[] = [{ key: 'this', name: '이 시설만' }, { key: 'multi', name: '여러 시설이 같이' }, { key: 'admin', name: '사무실·행정 일과 함께' }, { key: 'unknown', name: '모름' }];
export const WHAT_Q: Opt[] = [
  { key: 'utility', name: '전기·가스·통신 요금' }, { key: 'service', name: '청소·경비·용역·인쇄' }, { key: 'repair', name: '수선·공사' }, { key: 'equip', name: '비품·장비·소모품' },
  { key: 'car_pass', name: '승용차(8인승 이하) 기름·수리·리스' }, { key: 'car_other', name: '승합·화물·경차 관련' }, { key: 'guest', name: '손님 접대·선물·기념품' }, { key: 'staff', name: '직원 식사·복리후생' },
  { key: 'payroll_tax', name: '급여·세금·공과금·과태료' }, { key: 'insurance', name: '보험료·금융 수수료' }, { key: 'land', name: '토지 매입·부지 조성' }, { key: 'water', name: '수도요금·도서·교육 등 면세' }, { key: 'other', name: '그 밖의 것' }];
export const ASSET_WHAT = new Set(['repair', 'equip', 'car_other']);
export const ORG_KEY = 'vat-org-v1', LEDGER_KEY = 'vat-ledger-v1';
const lsGet = <T,>(k: string): T | null => { try { const s = localStorage.getItem(k); return s ? JSON.parse(s) as T : null; } catch { return null; } };
const lsSet = (k: string, v: unknown) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* 저장 못 해도 계속 */ } };
export const getOrg = () => lsGet<Org>(ORG_KEY);
export const setOrg = (o: Org | null) => { if (o) lsSet(ORG_KEY, o); else { try { localStorage.removeItem(ORG_KEY); } catch { /* */ } } };
export const allLedgers = () => lsGet<Record<string, LedgerRow[]>>(LEDGER_KEY) ?? {};
export const getLedger = (fid: string, month: string) => allLedgers()[`${fid}:${month}`] ?? [];
export const setLedger = (fid: string, month: string, rows: LedgerRow[]) => { const a = allLedgers(); a[`${fid}:${month}`] = rows; lsSet(LEDGER_KEY, a); };
export const facilityRule = (D: Data, f: OrgFacility) => D.facilities.find(x => x.key === f.type);
export type FacStatus = 'taxable' | 'exempt' | 'check' | 'own' | 'agency';
export function facilityStatus(D: Data, f: OrgFacility): FacStatus {
  if (f.kind === 'contractor') { if (f.run === 'entrusted_org') return 'agency'; const r = facilityRule(D, f); const cs = r?.contractor_status ?? r?.status ?? 'check'; return cs === 'none' ? 'exempt' : cs; }
  if (f.run === 'entrusted_own') return 'own'; return facilityRule(D, f)?.status ?? 'check';
}
export const STATUS_LABEL_SHORT: Record<string, string> = { taxable: '과세', exempt: '면세', check: '확인 필요', own: '수탁기관 신고', agency: '군 대행' };
/** 신고 준비에 넣을 시설: 우리 기관 사업이거나, 수탁기관 자기 사업이어도 우리 기관이 사용료를 받아 과세(임대)로 신고하는 시설(군 부담 지출이 그 임대사업의 매입) */
export const inFiling = (D: Data, f: OrgFacility) => { const s = facilityStatus(D, f); return s === 'agency' ? false : s !== 'own' || f.fee === 'taxable'; };
/** 매출(1)(3)(4)을 묻는 시설: 과세·확인 필요 + 사용료를 받는 수탁 시설 */
export const salesFacility = (D: Data, f: OrgFacility) => { const s = facilityStatus(D, f); return s === 'taxable' || s === 'check' || (s === 'own' && f.fee === 'taxable'); };
/** 수정세금계산서 발급 기한(착오 외 사유, 시행령 제70조 제1항 제6호): 공급일이 속한 과세기간의 확정신고기한 다음 날부터 1년 */
export function fixDue(d: string, today = new Date()) { const y = Number(d.slice(0, 4)), m = Number(d.slice(5, 7)); if (!y || !m) return null; const due = m <= 6 ? new Date(y + 1, 6, 25) : new Date(y + 2, 0, 25); const t = new Date(today.getFullYear(), today.getMonth(), today.getDate()); return { due: ymd(due), days: Math.round((due.getTime() - t.getTime()) / 86400000) }; }
/** 과세기간(확정 기준)과 경정청구 기한(법정신고기한이 지난 후 5년, 국세기본법 제45조의2 제1항 — 2026-10-02 시행 판 대조) */
export function claimPeriod(d: string, today = new Date()) { const y = Number(d.slice(0, 4)), m = Number(d.slice(5, 7)); if (!y || !m) return null; const half = m <= 6 ? 1 : 2; const due = half === 1 ? new Date(y, 6, 25) : new Date(y + 1, 0, 25); const claim = new Date(due.getFullYear() + 5, due.getMonth(), due.getDate()); const t = new Date(today.getFullYear(), today.getMonth(), today.getDate()); return { key: `${y}-${half}`, name: `${y}년 제${half}기(${half === 1 ? '1~6' : '7~12'}월)`, due: ymd(due), claim: ymd(claim), days: Math.round((claim.getTime() - t.getTime()) / 86400000) }; }
export const STATUS_WORD: Record<string, string> = { agency: '군 대행 — 군 명의 사업(지출은 군 등록번호 세금계산서, 공단 수입은 대행수수료)', taxable: '과세 — 부가세를 신고하는 시설', exempt: '면세 — 매출세액도 매입세액 공제도 없음', check: '확인 필요 — 유권해석·분류에 따라 다름', own: '수탁기관 자기 사업 — 우리 신고 아님' };

/** 시설 담당의 현장 질문 답 → 판정 입력. 조문은 judge 가 붙인다. */
export function toInput(D: Data, org: Org, f: OrgFacility, q: { proof: ProofQ; payee: PayeeQ; vat_sep: boolean; use: UseQ; what: string; asset: boolean; late: boolean; subsidy?: boolean }): { input: Input; override?: Out; note?: string } {
  const st = facilityStatus(D, f);
  if (st === 'agency') {   // 수탁기관 설정 + 군 대행 사업: 지출은 군 명의여야 군이 공제. 공단 명의면 재청구 구조인지 확인
    if (q.payee === 'contractor') return { input: { use: 'unknown', kind: 'general', proof: 'tax_invoice', supplier: 'general', timing: 'now' }, override: { v: 'none', title: '군 명의 세금계산서 — 군이 공제(공단 기록 아님)', why: ['군 대행 사업의 지출을 군 등록번호로 받았습니다. 그 매입세액은 군이 신고에 넣습니다.'], todo: ['이 영수증은 군 신고 담당에게 보냅니다(매입 인계표). 공단 장부에는 실비 정산 내역으로만.'], basis: [{ law: 'act', art: '제38조' }] } };
    return { input: { use: 'unknown', kind: 'general', proof: 'tax_invoice', supplier: 'general', timing: 'now' }, override: { v: 'check', title: '군 대행 사업 지출을 공단 명의로 받음 — 어느 쪽이 공제하는지 확인', why: ['군 명의 사업(대행)의 지출인데 세금계산서가 공단 이름입니다. 군은 자기 명의가 아니라 공제하지 못하고, 공단은 이 지출이 공단의 과세 용역(대행수수료)과 이어질 때만 공제합니다. 둘 다 아니면 이 매입세액은 누구도 받지 못합니다.'], todo: ['① 공급자에게 군 등록번호로 수정세금계산서를 요청해 군이 공제하거나(착오 외 사유는 확정신고기한 다음 날부터 1년), ② 공단이 군에 대행 용역으로 세금계산서를 발급(과세 매출)하는 재청구 구조라면 공단이 공제 — 위탁계약이 어느 쪽인지 확인해 하나로 맞춥니다.'], basis: [{ law: 'act', art: '제38조' }, { law: 'act', art: '제39조' }, { law: 'decree', art: '제70조' }] } };
  }
  if (st === 'own') {   // 수탁기관 자기 사업 시설 — 수탁기관이 낸 돈은 그 기관 것, 우리 기관이 직접 낸 돈(수선·장비 등)은 사용료를 받는 임대(과세)인지로 가른다
    if (q.payee === 'contractor') return { input: { use: 'unknown', kind: 'general', proof: 'receipt', supplier: 'unknown', timing: 'now' }, override: { v: 'check', title: '수탁기관 명의 지출 — 그 기관이 신고합니다', why: ['수탁기관 자기 사업으로 설정된 시설에서 수탁기관 이름으로 낸 돈입니다. 그 기관이 지자체가 아니므로 매입세액도 그 기관 것입니다.'], todo: ['이 지출은 수탁기관의 장부에 적습니다. 우리 기관이 낸 돈(수선·장비 등)만 여기에 적습니다. 설정이 틀렸으면 신고 담당 부서에 알려 기관 설정을 고칩니다.'], basis: [{ law: 'act', art: '제3조' }, { law: 'act', art: '제26조' }] } };
    if (f.fee === 'paid_check') return { input: { use: 'unknown', kind: 'general', proof: 'tax_invoice', supplier: 'general', timing: 'now' }, override: { v: 'check', title: '받는 사용료가 과세로 신고되는지 확인', why: ['우리 기관이 수탁기관에게 사용료·임대료를 받지만 그 사용료를 과세(부동산임대)로 신고하는지 정해지지 않았습니다. 행정재산 사용허가 사용료가 부동산임대업에 드는지는 유권해석·분류로 정해지며, 과세로 신고할 때만 이 시설에 우리 기관이 낸 돈의 매입세액을 공제할 수 있습니다.'], todo: ['신고 담당 부서가 그 사용료를 과세로 신고하는지(사업자등록·매출 신고) 확인해 기관 설정에서 "과세로 신고하고 있다"로 바꾸면 다시 판정됩니다. 면세로 보고 있다면 이 돈은 공제하지 못합니다.'], basis: [{ law: 'act', art: '제26조' }, { law: 'decree', art: '제46조' }, { law: 'act', art: '제39조' }] } };
    if ((f.fee ?? 'unknown') === 'unknown') return { input: { use: 'unknown', kind: 'general', proof: 'tax_invoice', supplier: 'general', timing: 'now' }, override: { v: 'check', title: '우리 기관이 수탁기관에게 사용료를 받는지 확인', why: ['수탁기관 자기 사업 시설에 우리 기관이 직접 낸 돈입니다. 우리 기관이 수탁기관에게 사용료·임대료를 받아 과세(부동산임대)로 신고하면 이 돈은 그 임대사업의 매입세액이라 공제할 수 있고, 무상으로 쓰게 하면 우리 기관의 과세사업이 아니어서 공제하지 못합니다.'], todo: ['위·수탁 계약서·사용허가서에서 사용료·임대료 조항을 보고 기관 설정(이 시설의 "수탁기관에게 받는 것")을 고르면 다시 판정됩니다.'], basis: [{ law: 'act', art: '제26조' }, { law: 'decree', art: '제46조' }, { law: 'act', art: '제39조' }] } };
    if (f.fee === 'free') return { input: { use: 'exempt', kind: 'general', proof: 'tax_invoice', supplier: 'general', timing: 'now' }, override: { v: 'no', title: '무상 사용 시설의 군 부담 지출 — 불공제', why: ['우리 기관이 수탁기관에게 사용료를 받지 않는 시설입니다. 무상으로 쓰게 하는 것은 우리 기관의 과세사업이 아니어서, 우리 기관이 낸 수선·장비 비용의 매입세액은 면세사업등 관련 매입세액으로 공제하지 못합니다(법 제39조 제1항 제7호).'], todo: ['앞으로 이 시설에 큰 수선·설비 지출이 예정돼 있으면, 사용료를 받는 유상 사용허가(과세)로 바꿀 수 있는지 재산 담당·세무대리인과 검토합니다 — 유상으로 바꾸면 그 뒤 지출을 공제할 수 있고, 그 전에 산 건물·설비의 불공제 매입세액도 과세사업 전환 매입세액(시행령 제85조)으로 일부 되살릴 수 있습니다(판단은 기관 몫).'], basis: [{ law: 'act', art: '제39조' }, { law: 'act', art: '제26조' }, { law: 'decree', art: '제46조' }] } };
  }
  let proof: string, supplier = 'general';
  if (q.proof === 'e_invoice' || q.proof === 'p_invoice') {
    if (q.payee === 'unknown') return { input: { use: 'unknown', kind: 'general', proof: 'tax_invoice', supplier: 'general', timing: 'now' }, override: { v: 'check', title: '세금계산서의 "공급받는 자"를 확인하세요', why: ['세금계산서는 공급받는 자가 우리 기관 등록번호로 돼 있어야 우리 매입세액입니다.'], todo: [`세금계산서 오른쪽 "공급받는 자" 칸의 등록번호가 ${org.unit === 'entity' ? (org.reg_no || '우리 기관 번호') : (f.reg_no || '이 시설의 등록번호')} 인지 봅니다. 수탁기관 번호면 수정세금계산서를 요청합니다.`], basis: [{ law: 'act', art: '제32조' }, { law: 'act', art: '제39조' }] } };
    proof = q.payee === 'org' ? 'tax_invoice' : 'tax_invoice_other';
  } else if (q.proof === 'card' || q.proof === 'cash') { proof = q.vat_sep ? 'card_vat' : 'card_novat'; supplier = q.vat_sep ? 'general' : 'unknown'; }
  else proof = q.proof === 'bill' ? 'bill' : 'receipt';
  const hasOther = org.facilities.some(x => x.id !== f.id && facilityStatus(D, x) !== 'taxable');
  const use = q.use === 'this' ? (st === 'taxable' || (st === 'own' && f.fee === 'taxable') ? 'taxable' : st === 'exempt' ? 'exempt' : 'unknown') : q.use === 'multi' ? (hasOther ? 'common' : 'taxable') : q.use === 'admin' ? 'common' : 'unknown';
  const kind = ({ utility: 'general', service: 'general', repair: q.asset ? 'building' : 'general', equip: q.asset ? 'equip' : 'general', car_pass: 'car', car_other: q.asset ? 'equip' : 'general', guest: 'entertain', staff: 'welfare', payroll_tax: 'payroll', insurance: 'insurance', land: 'land', water: 'exempt_goods', other: 'general' } as Record<string, string>)[q.what] ?? 'general';
  const notes = [st === 'check' && q.use === 'this' ? (f.kind === 'contractor' ? `이 시설 유형은 수탁기관 기준으로 확인이 필요합니다: ${facilityRule(D, f)?.contractor_note ?? '유권해석·분류'}.` : '이 시설 유형은 과세인지 면세인지 유권해석·분류로 정해야 합니다(기관 설정의 "확인 필요"). 신고 담당 부서가 정하면 다시 판정됩니다.') : '', f.run === 'unknown' ? '이 시설의 운영 방식(우리 기관 명의 대행인지 수탁기관 자기 사업인지)이 아직 정해지지 않았습니다. 수탁기관 자기 사업이면 이 매입세액은 우리 것이 아닙니다 — 기관 설정에서 위·수탁 계약대로 고르세요.' : '', st === 'own' ? '수탁기관 자기 사업 시설이지만 우리 기관이 사용료·임대료를 받아 과세(부동산임대)로 신고하는 시설이므로, 우리 기관이 직접 낸 이 돈은 그 임대사업의 지출로 봅니다 — 사용료가 과세로 신고되고 있어야 합니다.' : '', q.subsidy ? '국비·시비 보조금으로 집행한 지출이라도 공제 여부는 쓰임(과세·면세)으로만 정합니다 — 보조금이라서 공제가 안 되는 것이 아닙니다. 면세사업 보조금을 받았다면 신고 담당이 안분 때 면세공급가액에 넣습니다(시행령 제81조 제1항).' : ''].filter(Boolean); const note = notes.length ? notes.join(' ') : undefined;
  return { input: { use, kind, proof, supplier, timing: q.late ? 'late' : 'now' }, note };
}

/* ---------- 마감 ---------- */
export const DEADLINES = [{ m: 1, d: 25, name: '제2기 확정신고(지난해 7~12월)' }, { m: 4, d: 25, name: '제1기 예정신고(1~3월)' }, { m: 7, d: 25, name: '제1기 확정신고(1~6월)' }, { m: 10, d: 25, name: '제2기 예정신고(7~9월)' }];
export function nextFiling(today = new Date()) {
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  for (let y = t.getFullYear(); y <= t.getFullYear() + 1; y++) for (const x of DEADLINES) { const due = new Date(y, x.m - 1, x.d); if (due >= t) return { name: x.name, due, days: Math.round((due.getTime() - t.getTime()) / 86400000) }; }
  return { name: '', due: t, days: 0 };
}
export function handoverDue(day: number, today = new Date()) { const t = new Date(today.getFullYear(), today.getMonth(), today.getDate()); let due = new Date(t.getFullYear(), t.getMonth(), day); if (due < t) due = new Date(t.getFullYear(), t.getMonth() + 1, day); return { due, days: Math.round((due.getTime() - t.getTime()) / 86400000) }; }
export const ymd = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export const monthStr = (d = new Date()) => ymd(d).slice(0, 7);
export const periodOf = (month: string) => { const m = Number(month.slice(5, 7)); return m <= 3 ? '제1기 예정' : m <= 6 ? '제1기 확정' : m <= 9 ? '제2기 예정' : '제2기 확정'; };

/* ---------- 파일 ---------- */
export function toCsv(rows: (string | number)[][]) { return '\ufeff' + rows.map(r => r.map(c => { const s = String(c ?? ''); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }).join(',')).join('\r\n'); }
export function downloadText(name: string, text: string, mime = 'text/plain;charset=utf-8') { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: mime })); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0); }
export function readJsonFile(file: File): Promise<unknown> { return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => { try { res(JSON.parse(String(r.result))); } catch (e) { rej(e); } }; r.onerror = rej; r.readAsText(file, 'utf-8'); }); }
export const uid = () => Math.random().toString(36).slice(2, 8) + Date.now().toString(36).slice(-4);

/* ---------- v2 2단계: 신고 준비(/vat/prepare/) — 기간·칸·신고 기록 ---------- */
export type PeriodKey = string; // '2026-1P' 제1기 예정 · '2026-1F' 제1기 확정 · '2026-2P' · '2026-2F'
export function periodInfo(key: PeriodKey) {
  const y = Number(key.slice(0, 4)); const half = Number(key[5]) as 1 | 2; const kind = key[6] as 'P' | 'F';
  const mm = (a: number, b: number) => Array.from({ length: b - a + 1 }, (_, i) => `${y}-${String(a + i).padStart(2, '0')}`);
  const own = kind === 'P' ? (half === 1 ? mm(1, 3) : mm(7, 9)) : (half === 1 ? mm(4, 6) : mm(10, 12));
  const prelim = kind === 'F' ? (half === 1 ? mm(1, 3) : mm(7, 9)) : [];
  const full = half === 1 ? mm(1, 6) : mm(7, 12);
  const due = kind === 'P' ? (half === 1 ? `${y}-04-25` : `${y}-10-25`) : (half === 1 ? `${y}-07-25` : `${y + 1}-01-25`);
  return { y, half, kind, own, prelim, full, due, name: `${y}년 제${half}기 ${kind === 'P' ? '예정' : '확정'}신고`, prelimKey: kind === 'F' ? `${y}-${half}P` : null };
}
export const periodKeyOf = (month: string): PeriodKey => { const y = month.slice(0, 4); const m = Number(month.slice(5, 7)); return `${y}-${m <= 3 ? '1P' : m <= 6 ? '1F' : m <= 9 ? '2P' : '2F'}`; };
/** 일반과세자 부가가치세 신고서(시행규칙 별지 제21호서식, 2026-04-01 시행 판에서 확인) 칸 */
export const CELLS: { no: string; name: string; group: string }[] = [
  { no: '1', name: '과세 — 세금계산서 발급분', group: '매출' }, { no: '3', name: '과세 — 신용카드·현금영수증 발행분', group: '매출' }, { no: '4', name: '과세 — 기타(정규영수증 외 매출분, 간주임대료 포함)', group: '매출' },
  { no: '10', name: '세금계산서 수취분 — 일반매입', group: '매입' }, { no: '12', name: '세금계산서 수취분 — 고정자산매입', group: '매입' }, { no: '13', name: '예정신고 누락분', group: '매입' },
  { no: '44', name: '그 밖의 공제매입세액 — 신용카드매출전표등 수령명세서 제출분 일반매입', group: '매입(15)' }, { no: '45', name: '그 밖의 공제매입세액 — 신용카드매출전표등 수령명세서 제출분 고정자산매입', group: '매입(15)' },
  { no: '53', name: '공제받지 못할 매입세액', group: '불공제(17)' }, { no: '54', name: '공통매입세액 중 면세사업등 해당 세액', group: '불공제(17)' }];
export type Filing = { v: 1; org: string; period: PeriodKey; saved: string; cells: Record<string, { amt: number; tax: number }>; row_ids: string[];
  groups: { key: string; name: string; taxable: number; exempt: number; ratio: number; common_tax: number; nondeduct: number; skipped?: string; basis?: string; oneoff?: number }[];
  assets: { id: string; facility: string; desc: string; period: PeriodKey; tax: number; kind: 'building' | 'other'; common: boolean; ratio0: number; group: string }[];
  sales: Record<string, { c1: number; c3: number; c4: number; dep?: number; days?: number; rate?: number; deem?: number }>;
  /** 등록 단위(사업장)별 신고서 값 — 사업장별 등록이면 등록번호마다 신고서 한 장(세무사 평가 3차) */
  units?: { key: string; name: string; cells: Record<string, { amt: number; tax: number }>; supply: number; pay: number }[] };
/** 직전 과세기간(확정 기준) 열쇠 — 예정고지 판단(법 제48조 제3항·영 제90조 제4항: 직전 과세기간 공급가액 합계 1억5천만 원 미만 법인은 예정고지) */
export const prevPeriodKey = (k: PeriodKey): PeriodKey => { const y = Number(k.slice(0, 4)); const half = Number(k[5]); return half === 1 ? `${y - 1}-2F` : `${y}-1F`; };
export const PRELIM_NOTICE_LIMIT = 150_000_000;
export const FILINGS_KEY = 'vat-filings-v1';
export const getFilings = (): Record<PeriodKey, Filing> => lsGet<Record<PeriodKey, Filing>>(FILINGS_KEY) ?? {};
export const saveFiling = (f: Filing) => { const a = getFilings(); a[f.period] = f; lsSet(FILINGS_KEY, a); };
/** 과세사업 전환 매입세액(시행령 제85조): 면세사업용으로 불공제됐던 감가상각자산을 과세사업에 쓰기 시작하면 불공제 매입세액 × (1 − 체감률(건물 5%·그 밖 25%) × 경과 과세기간 수)를 전환한 과세기간 확정신고에 공제. 공통으로 쓰면 × 그 과세기간 과세공급가액 비율(5% 미만이면 없음, 제2항). 취득이 과세기간 개시일 뒤면 개시일 취득으로 봄(제6항) */
export function convertCredit(tax: number, kind: 'building' | 'other', acquired: PeriodKey, convertTo: PeriodKey, taxableRatio = 1) { const hi = (k: PeriodKey) => Number(k.slice(0, 4)) * 2 + (Number(k[5]) - 1); const n = Math.max(0, hi(convertTo) - hi(acquired)); const remain = Math.max(0, 1 - (kind === 'building' ? 0.05 : 0.25) * n); const ratio = taxableRatio < 0.05 ? 0 : taxableRatio; return { n, remain, credit: Math.floor(tax * remain * ratio) }; }
/** 간주임대료 공급가액(시행령 제65조 제1항): 보증금 × 과세대상 기간 일수 × 이자율 ÷ 365(윤년 366). 이자율은 기획재정부령 정기예금 이자율 — 사용자가 넣는다 */
export const deemedRent = (deposit: number, days: number, rate: number, year: number) => Math.floor(deposit * days * rate / ((year % 4 === 0 && year % 100 !== 0) || year % 400 === 0 ? 366 : 365));

/* ---------- v2 3단계: 표 붙여넣기(엑셀·홈택스·카드 명세) · zip(라이브러리 없음) ---------- */
/** TSV/CSV 글자 → 행렬. 탭이 있으면 탭, 없으면 쉼표(따옴표 처리) */
export function parseTable(text: string): string[][] {
  const t = text.replace(/\r\n?/g, '\n').replace(/^﻿/, ''); const lines = t.split('\n').filter(l => l.trim());
  if (!lines.length) return [];
  if (lines[0].includes('\t')) return lines.map(l => l.split('\t').map(c => c.trim()));
  return lines.map(l => { const out: string[] = []; let cur = '', q = false; for (let i = 0; i < l.length; i++) { const ch = l[i]; if (q) { if (ch === '"') { if (l[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += ch; } else if (ch === '"') q = true; else if (ch === ',') { out.push(cur.trim()); cur = ''; } else cur += ch; } out.push(cur.trim()); return out; });
}
/** 머리글 낱말로 열 짐작(홈택스 전자세금계산서 목록·카드사 이용내역·엑셀 장부 공통) */
export const COL_GUESS: { key: string; name: string; re: RegExp }[] = [
  { key: 'date', name: '날짜', re: /작성일|거래일|발급일|승인일|이용일|일자|날짜|date/i },
  { key: 'desc', name: '내용(품목)', re: /품목|내용|적요|품명|비고|메모|사용처/ },
  { key: 'payee_reg', name: '공급받는자 등록번호', re: /공급받는자.*등록번호|공급받는자등록|매입자.*등록번호/ },
  { key: 'supplier_reg', name: '공급자 등록번호', re: /^(?!.*공급받는자)(?!.*매입자).*(공급자.*등록번호|공급자등록|사업자등록번호|사업자번호|등록번호)/ },   // 등록번호 열은 상호보다 먼저 — '공급자등록번호' 가 상호로 잡히지 않게(2026-10-27 경정청구 집계 비교 오류)
  { key: 'supplier', name: '공급자(상호·가맹점)', re: /^(?!.*번호)(?!.*등록).*(공급자상호|공급자|상호|가맹점|거래처|판매자|업체)/ },
  { key: 'biz', name: '사업명(세부사업·예산과목)', re: /세부사업|단위사업|사업명|사업코드|예산과목|과목|사업$/ },   // 세출 사업 → 시설 자동 귀속(세무회계법인 관점 3번)
  { key: 'dept', name: '부서(실·과·팀)', re: /부서|실과|담당과|^과$|^팀$|소속/ },
  { key: 'amt', name: '공급가액', re: /공급가액|공급가|과세금액|순금액/ },
  { key: 'tax', name: '세액(부가세)', re: /세액|부가세|부가가치세|vat/i },
  { key: 'total', name: '합계(부가세 포함)', re: /합계금액|합계|총액|총금액|승인금액|결제금액|이용금액/ }];
export function guessColumns(header: string[]) { const m: Record<string, number> = {}; for (const g of COL_GUESS) { const i = header.findIndex(h => g.re.test(h.replace(/\s/g, ''))); if (i >= 0 && !Object.values(m).includes(i)) m[g.key] = i; } return m; }
export const WHAT_GUESS: { re: RegExp; key: string }[] = [
  { re: /전기|한전|한국전력|가스|도시가스|통신|KT|SKT|LGU|인터넷|전화|수도|상하수도/i, key: 'utility' }, { re: /수도요금|상수도|도서|교육|진료/, key: 'water' }, { re: /청소|경비|용역|인쇄|홍보|방역|소독|위탁/, key: 'service' },
  { re: /수선|공사|보수|교체|도장|방수|설치/, key: 'repair' }, { re: /비품|장비|소모품|사무용품|물품|구입|구매/, key: 'equip' }, { re: /주유|유류|휘발유|경유|세차|정비|타이어|렌트|리스/, key: 'car_pass' },
  { re: /식대|회식|다과|간식|커피|음료|식사/, key: 'staff' }, { re: /선물|기념품|화환|경조|접대/, key: 'guest' }, { re: /보험/, key: 'insurance' }, { re: /토지|부지|조성/, key: 'land' }];
export const guessWhat = (s: string) => { for (const g of WHAT_GUESS) if (g.re.test(s)) return g.key; return 'other'; };
const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
export const crc32 = (b: Uint8Array) => { let c = 0xffffffff; for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
const enc = new TextEncoder(), dec = new TextDecoder();
/** 저장 전용(압축 없음) zip — 파일 이름은 UTF-8 */
export function zipStore(files: { name: string; data: string | Uint8Array }[]): Blob {
  const parts: Uint8Array[] = []; const cd: Uint8Array[] = []; let off = 0; const now = new Date();
  const dosTime = ((now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1)) & 0xffff, dosDate = (((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate()) & 0xffff;
  const u16 = (v: number) => [v & 0xff, (v >> 8) & 0xff], u32 = (v: number) => [v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff, (v >>> 24) & 0xff];
  for (const f of files) {
    const data = typeof f.data === 'string' ? enc.encode(f.data) : f.data; const name = enc.encode(f.name); const crc = crc32(data);
    const lh = new Uint8Array([...u32(0x04034b50), ...u16(20), ...u16(0x0800), ...u16(0), ...u16(dosTime), ...u16(dosDate), ...u32(crc), ...u32(data.length), ...u32(data.length), ...u16(name.length), ...u16(0), ...name]);
    cd.push(new Uint8Array([...u32(0x02014b50), ...u16(20), ...u16(20), ...u16(0x0800), ...u16(0), ...u16(dosTime), ...u16(dosDate), ...u32(crc), ...u32(data.length), ...u32(data.length), ...u16(name.length), ...u16(0), ...u16(0), ...u16(0), ...u16(0), ...u32(0), ...u32(off), ...name]));
    parts.push(lh, data); off += lh.length + data.length;
  }
  const cdSize = cd.reduce((s, c) => s + c.length, 0);
  const eocd = new Uint8Array([...u32(0x06054b50), ...u16(0), ...u16(0), ...u16(files.length), ...u16(files.length), ...u32(cdSize), ...u32(off), ...u16(0)]);
  return new Blob([...parts, ...cd, eocd] as BlobPart[], { type: 'application/zip' });
}
/** zip 풀기 — 저장(0)과 deflate(8, DecompressionStream) */
export async function unzip(buf: ArrayBuffer): Promise<{ name: string; data: Uint8Array }[]> {
  const b = new Uint8Array(buf); const dv = new DataView(buf); let e = b.length - 22; while (e >= 0 && dv.getUint32(e, true) !== 0x06054b50) e--; if (e < 0) throw new Error('zip 아님');
  const n = dv.getUint16(e + 10, true); let p = dv.getUint32(e + 16, true); const out: { name: string; data: Uint8Array }[] = [];
  for (let i = 0; i < n; i++) {
    if (dv.getUint32(p, true) !== 0x02014b50) break; const method = dv.getUint16(p + 10, true), csize = dv.getUint32(p + 20, true), nl = dv.getUint16(p + 28, true), xl = dv.getUint16(p + 30, true), cl = dv.getUint16(p + 32, true), lo = dv.getUint32(p + 42, true);
    const name = dec.decode(b.subarray(p + 46, p + 46 + nl)); const lnl = dv.getUint16(lo + 26, true), lxl = dv.getUint16(lo + 28, true); const start = lo + 30 + lnl + lxl; let data = b.slice(start, start + csize);
    if (method === 8) { const ds = new Blob([data as BlobPart]).stream().pipeThrough(new DecompressionStream('deflate-raw')); data = new Uint8Array(await new Response(ds).arrayBuffer()); }
    if (!name.endsWith('/')) out.push({ name, data }); p += 46 + nl + xl + cl;
  }
  return out;
}
export const utf8 = (d: Uint8Array) => dec.decode(d);
export function downloadBlob(name: string, blob: Blob) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0); }
export const setAllLedgers = (a: Record<string, LedgerRow[]>) => lsSet(LEDGER_KEY, a);
export const setFilings = (a: Record<PeriodKey, Filing>) => lsSet(FILINGS_KEY, a);

/* ── 세무회계법인 관점 검토(2026-10-27) 도우미 ── */
/** 조기환급 일정(법 제59조 제2항 제2호·시행령 제107조 제4항): 공사 기간을 매월 또는 매 2월 조기환급기간으로 끊고, 기간 끝 +25일 신고기한, 신고기한 +15일 환급 기한. 예정·확정신고기간 경계는 넘기지 않는다 */
export function earlyRefundSchedule(startMonth: string, endMonth: string, every: 1 | 2, D?: Data | null) {
  const fw = D?.rules.build?.refund_days.file_within ?? 25, rw = D?.rules.build?.refund_days.refund_within ?? 15;
  const toN = (m: string) => Number(m.slice(0, 4)) * 12 + Number(m.slice(5, 7)) - 1; const toM = (n: number) => `${Math.floor(n / 12)}-${String(n % 12 + 1).padStart(2, '0')}`;
  const a = toN(startMonth), b = toN(endMonth); const out: { from: string; to: string; fileDue: string; refundBy: string; quarterDue: string }[] = []; if (!(a <= b) || b - a > 60) return out;
  let i = a; while (i <= b) { const q = Math.floor((i % 12) / 3); const qEnd = Math.floor(i / 12) * 12 + q * 3 + 2; let j = Math.min(i + every - 1, b, qEnd);
    const last = new Date(Math.floor(j / 12), j % 12 + 1, 0); const fileDue = new Date(last.getFullYear(), last.getMonth(), last.getDate() + fw); const refundBy = new Date(fileDue.getFullYear(), fileDue.getMonth(), fileDue.getDate() + rw);
    const qd = new Date(Math.floor(qEnd / 12), qEnd % 12 + 1, 25);
    out.push({ from: toM(i), to: toM(j), fileDue: ymd(fileDue), refundBy: ymd(refundBy), quarterDue: ymd(qd) }); i = j + 1; }
  return out;
}
/** 가산세 어림(국세기본법 제47조의2·제47조의3·제47조의4·제48조, 부정행위 아님): 과소(또는 무)신고 세액, 법정신고기한, 수정신고·납부일 → 신고 가산세(감면 뒤)·납부지연 가산세 */
export function penaltyCalc(D: Data | null, p: { tax: number; due: string; payDate: string; kind: 'under' | 'none' }) {
  const R = D?.rules.penalty; const rateFile = p.kind === 'none' ? (R?.no_report ?? 0.2) : (R?.under_report ?? 0.1); const daily = R?.late_pay_daily ?? 0.00022; const maxY = R?.late_pay_max_years ?? 5;
  const d0 = new Date(p.due), d1 = new Date(p.payDate); const days = Math.max(0, Math.min(Math.round((d1.getTime() - d0.getTime()) / 86400000), maxY * 365));
  const months = (d1.getFullYear() - d0.getFullYear()) * 12 + (d1.getMonth() - d0.getMonth()) - (d1.getDate() <= d0.getDate() ? 1 : 0) + 1;   // 경과 개월(이하 기준)
  const relief = (p.kind === 'none' ? R?.late_file_relief : R?.amend_relief) ?? []; const rl = relief.find(r => months <= r.months)?.rate ?? 0;
  const file = Math.floor(p.tax * rateFile); const fileAfter = Math.floor(file * (1 - rl)); const late = Math.floor(p.tax * days * daily);
  return { days, months, rateFile, file, relief: rl, fileAfter, late, total: fileAfter + late };
}
