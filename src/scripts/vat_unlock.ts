/** 지난 신고서 → 자료 → 돌려받을 금액(운영자 2026-11-04 '홈택스에 지난번 올린 것을 올리면 어떤 자료를 추가로 올리면 환급을 얼마 받을 수 있다는 시스템' → 프롬프트 docs/prompts/vat_refund_unlock.md).
 *  ① 신고서 읽기: 홈택스 신고내역에서 저장한 일반과세자 부가가치세 신고서(별지 제21호서식)와 공제받지 못할 매입세액 명세서(제22호) PDF·글자를 브라우저에서 읽어
 *     칸 (1)~(18)·사유 ①~⑨·안분 ⑩~⑭ 를 뽑는다. 홈택스 출력 PDF 의 배치는 확인하지 못해(docs/design/vat-refund-unlock.md) 서식 순서가 아니라 줄마다 '(nn)' 옆 숫자를 읽는다.
 *  ② 엔진: 지난 돈 돌려받기의 건별 판정(judge 그대로, 새 규칙 없음)을 '지금 자료로 됨 / 자료를 올리면 됨 / 판단 필요 / 시설 정하기'로 나누고,
 *     자료별로 늘어나는 금액과 같이 드러나는 매출세액·가산세를 뺀 순액을 셈한다. 판정은 참고이며 기관의 판단이 아니다. 파일은 밖으로 나가지 않는다. */
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { esc, fmt, num, penaltyCalc, toCsv, type Data } from './vat_rules';

export type Cell = { amt: number | null; tax: number | null; n?: number | null };
export type Kind = '예정' | '확정' | '기한후' | '조기환급' | '모름';
export type FiledDoc = { file: string; reg: string; year: number; half: 1 | 2; kind: Kind; from: number; to: number; cells: Record<number, Cell>; nd: { reasons: Record<number, Cell>; common: { sup: number; tax: number; total: number; exempt: number; nd: number } | null } | null; warn: string[] };
export type FiledSum = { k: string; deduct: number | null; nondeduct: number | null; er: number | null; salesSup: number | null; salesTax: number | null; kinds: Kind[]; files: string[]; regs: string[]; exemptNd: number | null; warn: string[] };

/* ── 파일 → 글자 ── */
export async function readFiledText(file: File): Promise<string> {
  const buf = new Uint8Array(await file.arrayBuffer());
  const isPdf = buf[0] === 0x25 && buf[1] === 0x50 && buf[2] === 0x44 && buf[3] === 0x46;   // %PDF
  if (!isPdf) { const t = new TextDecoder('utf-8').decode(buf); return /�/.test(t) ? new TextDecoder('euc-kr').decode(buf) : t; }
  const lib: any = await import('pdfjs-dist'); lib.GlobalWorkerOptions.workerSrc = pdfWorker;
  const doc = await lib.getDocument({ data: buf }).promise; const pages: string[] = [];
  for (let p = 1; p <= doc.numPages; p++) {
    const c = await (await doc.getPage(p)).getTextContent(); const lines: { y: number; items: { x: number; s: string }[] }[] = [];
    for (const it of c.items as { str: string; transform: number[] }[]) { if (!it.str?.trim()) continue; const x = it.transform[4], y = it.transform[5]; let L = lines.find(l => Math.abs(l.y - y) < 2.5); if (!L) { L = { y, items: [] }; lines.push(L); } L.items.push({ x, s: it.str }); }
    lines.sort((a, b) => b.y - a.y); pages.push(lines.map(l => l.items.sort((a, b) => a.x - b.x).map(i => i.s).join(' ')).join('\n'));
  }
  return pages.join('\n\f\n');
}

/* ── 글자 → 신고서 ── */
const CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭';
const NUM_RE = /△?-?\d{1,3}(?:,\d{3})+|△?-?\d+/g;
const nums = (s: string) => (s.replace(/\d+\s*\/\s*\d+/g, ' ').match(NUM_RE) ?? []).map(t => (t.startsWith('△') ? -1 : 1) * Math.abs(num(t.replace('△', ''))));
const PERIOD_RE = /(20\d{2})\s*년\s*제?\s*([12])\s*기\s*\(\s*(\d{1,2})\s*월\s*\d{1,2}\s*일\s*~\s*(\d{1,2})\s*월/;
const MARK = '[VvＶ√✓✔■●☑◉xXOo○]';
/** 한 파일 글자에서 신고서 여럿(예정·확정 등)을 읽는다. 22호 명세서는 바로 앞 신고서에 붙인다. */
export function parseFiledText(text: string, file = ''): FiledDoc[] {
  const t = text.replace(/\r/g, '');
  const starts: number[] = []; const re = /신\s*고\s*기\s*간/g; let m: RegExpExecArray | null; while ((m = re.exec(t))) starts.push(m.index);
  if (!starts.length) { const p = PERIOD_RE.exec(t); if (p) starts.push(Math.max(0, p.index - 20)); }
  const out: FiledDoc[] = [];
  starts.forEach((s, i) => { const seg = t.slice(i ? Math.max(starts[i - 1] + 1, s - 400) : 0, starts[i + 1] ?? t.length); const head = t.slice(Math.max(0, s - 600), s + 400); const d = parseOne(seg, head, file); if (d) out.push(d); });
  return out;
}
function parseOne(seg: string, head: string, file: string): FiledDoc | null {
  const warn: string[] = [];
  const p = PERIOD_RE.exec(seg) ?? PERIOD_RE.exec(head); if (!p) return null;
  const year = Number(p[1]); const half = Number(p[2]) === 2 ? 2 : 1; const from = Number(p[3]), to = Number(p[4]);
  const mk = new RegExp(`[\\[(]\\s*${MARK}\\s*[\\])]\\s*(예정|확정|기한후|영세율|조기환급)|${MARK}\\s*(예정|확정|기한후)`).exec(head);
  let kind: Kind = mk ? (((mk[1] ?? mk[2]) === '영세율' ? '조기환급' : (mk[1] ?? mk[2])) as Kind) : '모름';
  if (kind === '모름') { if (to === 3 || to === 9) kind = '예정'; else if (to === 6 || to === 12) kind = '확정'; }
  if (!mk) warn.push(`구분(예정·확정) 표시를 못 찾아 신고기간(${from}~${to}월)으로 '${kind}'으로 봤습니다`);
  const regM = /(\d{3})\s*-\s*(\d{2})\s*-\s*(\d{5})/.exec(seg); const reg = regM ? `${regM[1]}-${regM[2]}-${regM[3]}` : '';
  if (!reg) warn.push('사업자등록번호를 못 찾았습니다');
  const ndAt = seg.search(/공제\s*받지\s*못할\s*매입\s*세액\s*명세서/); const main0 = ndAt > 0 ? seg.slice(0, ndAt) : seg; const main = main0.split(/작\s*성\s*방\s*법/)[0];   // 서식 뒤쪽 작성방법의 '(10)란' 같은 글자는 읽지 않는다
  const cells: Record<number, Cell> = {};
  for (const line of main.split('\n')) {
    const marks = [...line.matchAll(/\((\d{1,2})\)/g)]; if (!marks.length) continue;
    marks.forEach((mm, j) => { const n = Number(mm[1]); if (n < 1 || n > 18 || cells[n]) return; const after = line.slice(mm.index! + mm[0].length, marks[j + 1]?.index ?? line.length); const v = nums(after); if (!v.length) return;
      if (v.length >= 2) cells[n] = { amt: v[0], tax: v[1] }; else if (n >= 10) cells[n] = { amt: null, tax: v[0] }; else cells[n] = { amt: v[0], tax: n <= 4 ? Math.floor(v[0] / 10) : 0 }; });
  }
  /* 2025-07-04 전 서식(2021-03-16 판 ~ 2025-03-21 판): (15) 합계 · (16) 공제받지못할매입세액 · (17) 차감계 · (18) 그 밖의 경감·공제세액 — 현행 (16)(17)(18)로 옮겨 읽는다
     (docs/design/vat-law-changes-2021.md 요약 B-1). 칸 이름 '공제받지 못할 매입세액'이 붙은 번호로 판을 가르고, 이름이 없으면 (15)−(16)=(17) 인지로 본다 */
  { const ndLbl = /\((1[67])\)[^\n(]{0,6}공\s*제\s*받\s*지\s*못\s*할/.exec(main) ?? /공\s*제\s*받\s*지\s*못\s*할\s*매\s*입\s*세\s*액[^\n(]{0,6}\((1[67])\)/.exec(main);
    const arith = cells[15]?.tax != null && cells[16]?.tax != null && cells[17]?.tax != null && cells[15].tax! - cells[16].tax! === cells[17].tax! && !(cells[18]?.tax != null && cells[16].tax! - cells[17].tax! === cells[18].tax!);
    if ((ndLbl && ndLbl[1] === '16') || (!ndLbl && arith)) { const c15 = cells[15], c16 = cells[16], c17 = cells[17]; delete cells[18]; delete cells[15]; delete cells[16]; delete cells[17]; if (c15) cells[16] = c15; if (c16) cells[17] = c16; if (c17) cells[18] = c17; warn.push('2025-07-04 전 서식 — (15)합계·(16)불공제·(17)차감계를 현행 (16)(17)(18)로 옮겨 읽었습니다'); } }
  if (cells[16]?.tax != null && cells[17]?.tax != null && cells[18]?.tax == null) cells[18] = { amt: null, tax: cells[16].tax! - cells[17].tax! };
  if (cells[18]?.tax != null && cells[16]?.tax != null && cells[17]?.tax != null && cells[16].tax! - cells[17].tax! !== cells[18].tax) warn.push(`(16) − (17) 과 (18) 이 맞지 않습니다 — 칸을 확인하세요`);
  if (cells[18]?.tax == null) warn.push('(18) 차감계(공제받은 매입세액)를 못 읽었습니다 — ② 표에 직접 넣으세요');
  let nd: FiledDoc['nd'] = null;
  if (ndAt > 0) { const part = seg.slice(ndAt); const reasons: Record<number, Cell> = {};
    for (const line of part.split('\n')) { const c = CIRC.indexOf(line.trim()[0]); if (c < 0 || c > 8) continue; const v = nums(line.slice(1).replace(/「[^」]*」|제\d+조(의\d+)?(제\d+항)?(제\d+호)?/g, ' ')); if (!v.length) continue; reasons[c + 1] = v.length >= 3 ? { n: v[0], amt: v[1], tax: v[2] } : v.length === 2 ? { amt: v[0], tax: v[1] } : { amt: null, tax: v[0] }; }
    let common: { sup: number; tax: number; total: number; exempt: number; nd: number } | null = null; const ca = part.search(/공통\s*매입\s*세액\s*안분/); const cb = part.search(/공통\s*매입\s*세액의\s*정산/);
    if (ca >= 0) { const sec = part.slice(ca, cb > ca ? cb : undefined); const sum = sec.split('\n').find(l => /^\s*합\s*계/.test(l) && nums(l).length >= 5); const rows = sum ? [nums(sum)] : sec.split('\n').filter(l => /^\s*[1-9]\s/.test(l)).map(l => nums(l).slice(1)).filter(v => v.length >= 5);
      if (rows.length) { const s = rows.reduce((a, v) => [a[0] + v[0], a[1] + v[1], a[2] + v[2], a[3] + v[3], a[4] + v[4]], [0, 0, 0, 0, 0]); common = { sup: s[0], tax: s[1], total: s[2], exempt: s[3], nd: s[4] }; } }
    nd = { reasons, common }; }
  return { file, reg, year, half: half as 1 | 2, kind, from, to, cells, nd, warn };
}
/** 신고서들 → 과세기간(확정 기준)별 합: (18)·(17)은 예정+확정, 같은 기간·구분·번호가 두 번이면 뒤 것이 앞 것을 바꿈(수정신고) */
export function filedSummary(docs: FiledDoc[]): Map<string, FiledSum> {
  const last = new Map<string, FiledDoc>(); const warns: Record<string, string[]> = {};
  for (const d of docs) { const k = `${d.year}-${d.half}`; const id = `${k}|${d.kind}|${d.reg}`; if (last.has(id)) (warns[k] ??= []).push(`${d.kind} 신고서가 두 번 들어와 뒤 파일(${d.file})로 바꿨습니다(수정신고면 맞음)`); last.set(id, d); }
  const out = new Map<string, FiledSum>();
  for (const d of last.values()) { const k = `${d.year}-${d.half}`; const s = out.get(k) ?? { k, deduct: null, nondeduct: null, er: null, salesSup: null, salesTax: null, kinds: [], files: [], regs: [], exemptNd: null, warn: [...(warns[k] ?? [])] };
    const add = (a: number | null, b: number | null | undefined) => b == null ? a : (a ?? 0) + b;
    s.deduct = add(s.deduct, d.cells[18]?.tax); s.nondeduct = add(s.nondeduct, d.cells[17]?.tax);
    for (const n of [1, 2, 3, 4]) { s.salesSup = add(s.salesSup, d.cells[n]?.amt); s.salesTax = add(s.salesTax, d.cells[n]?.tax); }
    if ([1, 2, 3, 4].every(n => !d.cells[n])) { s.salesSup = add(s.salesSup, 0); s.salesTax = add(s.salesTax, 0); }
    const c = d.nd?.common; if (c && (d.kind === '확정' || s.er === null)) s.er = c.tax > 0 ? Math.round(c.nd / c.tax * 10000) / 100 : c.total > 0 ? Math.round(c.exempt / c.total * 10000) / 100 : s.er;
    if (d.nd?.reasons[5]?.tax != null) s.exemptNd = (s.exemptNd ?? 0) + d.nd.reasons[5].tax!;
    s.kinds.push(d.kind); s.files.push(d.file); if (d.reg && !s.regs.includes(d.reg)) s.regs.push(d.reg); s.warn.push(...d.warn.map(w => `${d.kind}: ${w}`)); out.set(k, s); }
  return out;
}

/* ── 엔진 ── */
export type URow = { id: string; pkey: string; d: string; tax: number; amt: number; sup: string; sreg: string; cat: string; claim: number; fid?: string; fname?: string; fstatus?: string; ftype?: string; ftypeName?: string; other?: boolean; admin?: boolean; unassigned?: boolean; fixOk?: boolean };
export type UPer = { k: string; name: string; filed: 'filed' | 'excluded' | 'none' | 'unknown'; deduct: number | null; er: number | null; due: string; claim: string; days: number; future: boolean; salesSup: number | null; salesExtra: number | null };
export type Need = { key: string; label: string; what: string; tick: boolean };
type St = 'now' | 'docs' | 'judge' | 'assign';
export type UPerOut = { k: string; name: string; state: string; cov: number; now: number; docs: number; judge: number; assign: number; nowAmt: number; docsAmt: number; salesTax: number; salesPen: number; listPen: number; listPenNow: number; net: number; netNow: number; warnSales: boolean; expired: boolean; future: boolean; filed: UPer['filed']; due: string; claim: string; days: number };
export type UResult = { now: number; docs: number; judge: number; assign: number; expired: number; future: number; net: number; netNow: number; per: UPerOut[]; needs: { key: string; labels: string[]; whats: string[]; ticks: { key: string; label: string }[]; amount: number; n: number; byK: Map<string, number> }[]; judgeList: { label: string; amount: number; n: number; key: string }[]; anyUnknownFiled: boolean };

export function unlockCompute(D: Data, rows: URow[], pers: UPer[], have: Set<string>, today: string): UResult {
  const facNeed = (r: URow): Need => ({ key: `fac:${r.fid}`, label: `${r.fname ?? '시설'} 자료 묶음`, what: '지출이 이 시설 것이라는 증빙(계약서·검수조서·사업명) + 이 시설이 과세라는 근거(사업자등록·사용료 등 매출 신고 사실)', tick: true });
  type X = { r: URow; st: St; pot: number; needs: Need[]; jkey?: string; jlabel?: string };
  const xs: X[] = [];
  for (const r of rows) {
    const P = pers.find(p => p.k === r.pkey); if (!P) continue;
    if (r.other) { if (r.fixOk) xs.push({ r, st: 'docs', pot: r.tax, needs: [{ key: `fix:${r.sreg || r.sup}`, label: `수정세금계산서 — ${r.sup || r.sreg}`, what: '공급받는 자를 우리 등록번호로 고친 수정세금계산서(시행령 제70조 제1항 제6호, 확정신고기한 다음 날부터 1년 안)', tick: true }] }); continue; }
    if (r.unassigned) { xs.push({ r, st: 'assign', pot: r.tax, needs: [] }); continue; }
    if (r.admin) { xs.push({ r, st: 'judge', pot: r.cat === 'split' ? r.claim : r.tax, needs: [], jkey: 'admin', jlabel: '본청·행정 공통 지출의 안분 기준(시행령 제81조 제4항 — 고유사무는 공급가액이 없음)' }); continue; }
    if (r.cat === 'check') { if (r.fstatus === 'check') { xs.push({ r, st: 'judge', pot: r.tax, needs: [], jkey: `type:${r.ftype}`, jlabel: `${r.ftypeName ?? r.ftype} — 과세·면세가 운영 방식에 달린 시설 유형` }); } continue; }
    if (r.cat === 'noratio') { const needs: Need[] = [{ key: `ratio:${r.pkey}`, label: `${P.name} 면세비율`, what: '그 과세기간 과세·면세 공급가액(공제받지 못할 매입세액 명세서 ⑫·⑬) — ② 표에 넣으면 계산됩니다', tick: false }]; if (r.fid && !have.has(`fac:${r.fid}`)) needs.push(facNeed(r)); xs.push({ r, st: 'docs', pot: r.tax, needs }); continue; }
    if ((r.cat === 'ok' || r.cat === 'split') && r.claim > 0) { const needs = r.fid && !have.has(`fac:${r.fid}`) ? [facNeed(r)] : []; xs.push({ r, st: needs.length ? 'docs' : 'now', pot: r.claim, needs }); }
  }
  const penRate = D.rules.penalty?.list_missing ?? 0.005;
  const per: UPerOut[] = []; let anyUnknownFiled = false;
  const needAgg = new Map<string, UResult['needs'][number]>(); const judgeAgg = new Map<string, UResult['judgeList'][number]>();
  for (const P of pers) {
    const X = xs.filter(x => x.r.pkey === P.k); if (!X.length && P.salesExtra == null) continue;
    const sum = (s: St) => X.filter(x => x.st === s).reduce((a, x) => a + x.pot, 0); const amtOf = (s: St) => X.filter(x => x.st === s).reduce((a, x) => a + x.r.amt, 0);
    const cov = P.filed === 'filed' ? (P.deduct ?? 0) : 0; if (P.filed === 'unknown' || (P.filed === 'filed' && P.deduct === null)) anyUnknownFiled = true;
    const nowS = sum('now'), docS = sum('docs'), judS = sum('judge'), asg = sum('assign');
    const now = Math.max(0, nowS - cov); const L1 = Math.max(0, cov - nowS); const docs = Math.max(0, docS - L1); const L2 = Math.max(0, L1 - docS); const judge = Math.max(0, judS - L2);
    const expired = P.days < 0 && P.filed !== 'none'; const future = P.future;
    const salesTax = P.salesExtra ? Math.floor(P.salesExtra / 10) : 0; const salesPen = salesTax ? penaltyCalc(D, { tax: salesTax, due: P.due, payDate: today, kind: P.filed === 'none' ? 'none' : 'under' }).total : 0;
    const nowAmt = nowS ? amtOf('now') * now / nowS : 0; const docsAmt = docS ? amtOf('docs') * docs / docS : 0;
    const listPenNow = Math.floor(nowAmt * penRate), listPen = Math.floor((nowAmt + docsAmt) * penRate);
    const net = now + docs - salesTax - salesPen - listPen; const netNow = now - salesTax - salesPen - listPenNow;
    const warnSales = now + docs > 0 && X.some(x => (x.st === 'now' || x.st === 'docs') && x.r.fstatus === 'taxable') && (P.salesSup === null || P.salesSup === 0) && P.salesExtra == null;
    per.push({ k: P.k, name: P.name, state: expired ? '경정청구 기한 지남' : future ? '아직 신고 전 — 이번 신고에 넣기' : P.filed === 'none' ? '신고 없음 — 기한후신고' : `청구 가능 D-${P.days}`, cov, now, docs, judge, assign: asg, nowAmt, docsAmt, salesTax, salesPen, listPen, listPenNow, net, netNow, warnSales, expired, future, filed: P.filed, due: P.due, claim: P.claim, days: P.days });
    if (expired || future) continue;
    for (const x of X.filter(x => x.st === 'docs')) { const share = docS ? x.pot * docs / docS : 0; const key = x.needs.map(n => n.key).sort().join('+'); const a = needAgg.get(key) ?? { key, labels: x.needs.map(n => n.label), whats: x.needs.map(n => n.what), ticks: x.needs.filter(n => n.tick).map(n => ({ key: n.key, label: n.label })), amount: 0, n: 0, byK: new Map() }; a.amount += share; a.n++; a.byK.set(P.k, (a.byK.get(P.k) ?? 0) + share); needAgg.set(key, a); }
    for (const x of X.filter(x => x.st === 'judge')) { const share = judS ? x.pot * judge / judS : 0; const j = judgeAgg.get(x.jkey!) ?? { key: x.jkey!, label: x.jlabel!, amount: 0, n: 0 }; j.amount += share; j.n++; judgeAgg.set(x.jkey!, j); }
  }
  const live = per.filter(p => !p.expired && !p.future);
  const tot = (f: (p: UPerOut) => number, L = live) => Math.round(L.reduce((a, p) => a + f(p), 0));
  return { now: tot(p => p.now), docs: tot(p => p.docs), judge: tot(p => p.judge), assign: tot(p => p.assign), expired: tot(p => p.now + p.docs + p.judge, per.filter(p => p.expired)), future: tot(p => p.now + p.docs + p.judge, per.filter(p => p.future)), net: tot(p => p.net), netNow: tot(p => p.netNow), per,
    needs: [...needAgg.values()].map(n => ({ ...n, amount: Math.round(n.amount) })).sort((a, b) => b.amount - a.amount), judgeList: [...judgeAgg.values()].map(j => ({ ...j, amount: Math.round(j.amount) })).sort((a, b) => b.amount - a.amount), anyUnknownFiled };
}

/* ── 화면 ── */
export function unlockHtml(U: UResult, have: Record<string, { name?: string; at: string }>, pName: (k: string) => string): string {
  const wonCard = (id: string, h: string, v: number, note: string) => `<div class="vc-card"><h3>${h}</h3><p class="big" id="${id}">${fmt(v)}<span class="note">원</span></p><p class="note">${note}</p></div>`;
  const live = U.per.filter(p => !p.expired && !p.future);
  const covered = U.needs.filter(n => n.amount <= 0);
  const needRows = U.needs.filter(n => n.amount > 0).map((n, i) => `<tr><th scope="row">${n.labels.map(esc).join('<br>+ ')}<br><span class="note">${n.whats.map(esc).join('<br>')}</span></th><td>+${fmt(n.amount)}</td><td>${n.n}</td><td class="note">${[...n.byK.entries()].sort().map(([k, v]) => `${esc(pName(k))} ${fmt(Math.round(v))}`).join('<br>')}</td><td>${n.ticks.length ? n.ticks.map(t => `<label style="display:block"><input type="checkbox" data-have="${esc(t.key)}" ${have[t.key] ? 'checked' : ''} /> ${esc(t.label)} 있음${have[t.key]?.name ? ` <span class="note">(${esc(have[t.key].name!)})</span>` : ''}</label><label class="link-btn" style="cursor:pointer">파일 고르기<input type="file" data-havefile="${esc(t.key)}" hidden multiple /></label>`).join('') : '<a href="#rv-filed">② 표에 면세비율 넣기</a>'}${n.labels.length > n.ticks.length && n.ticks.length ? '<br><a href="#rv-filed" class="note">면세비율도 ② 표에</a>' : ''}<span hidden data-need-i="${i}"></span></td></tr>`).join('');
  const judgeRows = U.judgeList.map(j => `<li><strong>${esc(j.label)}</strong> — ${fmt(j.amount)}원(${j.n}건) · <a href="#rv-basis-h">근거·질의서 초안</a></li>`).join('');
  const perRows = U.per.map(p => `<tr class="${p.expired || p.future ? 'muted' : ''}"><th scope="row">${esc(pName(p.k))}</th><td>${esc(p.state)}</td><td>${p.filed === 'filed' ? fmt(p.cov) : p.filed === 'unknown' ? '<span class="vbadge">모름(상한)</span>' : '0'}</td><td>${fmt(Math.round(p.now))}</td><td>${fmt(Math.round(p.docs))}</td><td>${fmt(Math.round(p.judge))}</td><td><input type="text" inputmode="numeric" data-sales="${p.k}" value="" placeholder="공급가액" style="width:9em" aria-label="${esc(pName(p.k))} 신고에 없던 과세 시설 매출" />${p.warnSales ? '<br><span class="vbadge">매출 신고 확인</span>' : ''}</td><td>${p.salesTax ? `−${fmt(p.salesTax + p.salesPen)}` : '—'}</td><td>${p.listPen ? `−${fmt(p.listPen)}` : '—'}</td><td><strong>${p.expired || p.future ? '—' : fmt(Math.round(p.net))}</strong></td></tr>`).join('');
  const warnSales = live.some(p => p.warnSales);
  return `<div class="vc-card" id="rv-unlock"><h2 style="margin-top:0">돌려받을 금액 — 자료별 <span class="meta">신고서·매입 목록으로 다시 셈 · 판정은 참고이며 기관의 판단이 아닙니다</span></h2>
    <div class="vc-cards">${wonCard('ul-now', '지금 자료로 돌려받을 수 있는 금액', U.now, '시설·명의·증빙이 갖춰진 건 − 신고한 공제 세액(18)')}${wonCard('ul-docs', '자료를 올리면 늘어나는 금액', U.docs, '아래 표의 자료를 올리면 왼쪽 칸으로 옮겨집니다')}${wonCard('ul-judge', '판단이 필요한 금액', U.judge, '시설 유형·본청 공통 안분처럼 기준을 정해야 셈하는 몫')}</div>
    <p class="q-title">같이 드러나는 것을 뺀 순액: 지금 자료로 <strong id="ul-net-now">${fmt(U.netNow)}</strong>원 · 자료를 다 올리면 <strong id="ul-net">${fmt(U.net)}</strong>원</p>
    <p class="note">순액 = 돌려받을 금액 − 신고에 없던 과세 시설 매출의 매출세액·가산세(과소신고·납부지연, 오늘 납부 가정) − 합계표에 없던 분의 가산세 0.5%. ${U.assign ? `시설을 정하지 않은 건의 세액 <strong>${fmt(U.assign)}원</strong>은 아직 어느 칸에도 넣지 않았습니다(③에서 정하기). ` : ''}${U.expired ? `경정청구 기한이 지난 과세기간 몫 ${fmt(U.expired)}원은 빼었습니다(권익위 직권 시정 사례는 아래 사례 참고). ` : ''}${U.future ? `아직 신고 전인 과세기간 몫 ${fmt(U.future)}원은 이번 신고에 넣습니다. ` : ''}${U.anyUnknownFiled ? '신고한 공제 세액(18)을 모르는 과세기간은 0 으로 보고 셌으므로 상한입니다 — ⓪에 신고서를 올리거나 ② 표에 넣으세요.' : ''}</p>
    ${warnSales ? '<p class="callout warn"><strong>매출 신고를 확인하세요.</strong> 과세 시설의 매입세액을 공제받으려면 그 시설의 매출(사용료·대관료·입장료 등)도 그 과세기간에 과세로 신고돼 있어야 합니다. 신고서에서 읽은 과세 매출이 0 이거나 없는 과세기간이 있습니다 — 신고에 없던 매출이 있으면 아래 표에 공급가액을 넣으세요. 매출세액과 가산세가 순액에서 빠집니다.</p>' : ''}
    <h3>자료를 올리면 +얼마 <span class="meta">늘어나는 금액 순 — 순서는 금액일 뿐 평가가 아닙니다</span></h3>
    ${needRows ? `<div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table" data-stack="off" id="ul-docs-tbl"><caption>자료마다 풀리는 금액 — 신고한 공제 세액(18)이 근거가 갖춰진 건부터 덮었다고 보고 남는 몫을 나눔</caption><thead><tr><th scope="col">올릴 자료</th><th scope="col">늘어나는 금액</th><th scope="col">건</th><th scope="col">과세기간별</th><th scope="col">자료 있음 표시 <span class="note">(파일은 이름만 기록, 밖으로 안 나감)</span></th></tr></thead><tbody>${needRows}</tbody></table></div>` : '<p class="note">자료를 더 올려서 늘어나는 금액이 없습니다.</p>'}${covered.length ? `<p class="note">자료가 없는 ${covered.map(n => esc(n.labels.join(' + '))).join(', ')} 건(${covered.reduce((a, n) => a + n.n, 0)}건)은 신고한 공제 세액(18)이 이미 덮은 것으로 보아 금액이 없습니다. 자료를 갖춰 두면 신고한 공제의 근거가 됩니다.</p>` : ''}
    ${judgeRows ? `<h3>판단이 필요한 것</h3><ul class="meta-list" id="ul-judge-list">${judgeRows}</ul>` : ''}
    <h3>과세기간별 — 순액</h3><div class="scroll-x" tabindex="0" role="region" aria-label="표 가로 스크롤"><table class="data-table vat-table" data-stack="off" id="ul-per"><caption>과세기간별 돌려받을 금액과 같이 드러나는 것</caption><thead><tr><th scope="col">과세기간</th><th scope="col">상태</th><th scope="col">신고한 공제 세액 (18)</th><th scope="col">지금 자료로</th><th scope="col">자료를 올리면</th><th scope="col">판단 필요</th><th scope="col">신고에 없던 과세 시설 매출</th><th scope="col">매출세액·가산세</th><th scope="col">합계표 가산세</th><th scope="col">순액(지금+자료)</th></tr></thead><tbody>${perRows}</tbody></table></div></div>`;
}
export function unlockFiles(U: UResult, pName: (k: string) => string, today: string) {
  const csv = toCsv([['올릴 자료', '무엇', '늘어나는 금액', '건', '과세기간별'], ...U.needs.map(n => [n.labels.join(' + '), n.whats.join(' / '), n.amount, n.n, [...n.byK.entries()].sort().map(([k, v]) => `${pName(k)} ${Math.round(v)}`).join('; ')]), ...U.judgeList.map(j => [`[판단 필요] ${j.label}`, '', j.amount, j.n, ''])]);
  const txt = `돌려받을 금액 — 자료별 (${today}, 지자체 부가세 절감 점검기 — 참고 계산, 신고 책임은 신고인)\n\n지금 자료로: ${fmt(U.now)}원\n자료를 올리면 늘어나는 금액: ${fmt(U.docs)}원\n판단이 필요한 금액: ${fmt(U.judge)}원\n시설 미지정(세지 않음): ${fmt(U.assign)}원\n기한 지난 과세기간(뺌): ${fmt(U.expired)}원\n\n순액(지금 자료로): ${fmt(U.netNow)}원\n순액(자료를 다 올리면): ${fmt(U.net)}원\n\n과세기간별\n` +
    U.per.map(p => `- ${pName(p.k)} [${p.state}] 신고한 (18) ${p.filed === 'filed' ? fmt(p.cov) : p.filed} · 지금 ${fmt(Math.round(p.now))} · 자료 ${fmt(Math.round(p.docs))} · 판단 ${fmt(Math.round(p.judge))} · 매출세액 ${fmt(p.salesTax)} · 매출 가산세 ${fmt(p.salesPen)} · 합계표 가산세 ${fmt(p.listPen)} · 순액 ${fmt(Math.round(p.net))}`).join('\n') +
    `\n\n셈하는 법\n- 건마다 지난 돈 돌려받기의 판정(시설·용도·명의)을 그대로 쓰고, 과세 시설 지출은 그 시설 자료 묶음(지출 귀속 증빙 + 과세 근거)이 있으면 '지금 자료로', 없으면 '자료를 올리면'.\n- 과세기간마다 신고한 공제 세액(18)이 '지금 자료로' 건부터 덮었다고 보고 남는 몫을 셈한다(보수적). 신고를 안 했거나 이 목록을 넣지 않았으면 (18)을 0 으로.\n- 매출세액 = 신고에 없던 과세 시설 매출 × 10%, 가산세는 과소신고(무신고)·납부지연(국세기본법 제47조의2~4), 합계표 가산세 0.5%(법 제60조).\n- 경정청구 기한 = 법정신고기한 + 5년(국세기본법 제45조의2).`;
  return { csv, txt };
}
