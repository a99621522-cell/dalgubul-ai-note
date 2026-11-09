/** 경정청구서 — 국세기본법 시행규칙 별지 제16호의2서식(1) 「과세표준 및 세액의 결정(경정)청구서」 칸 배치 그대로, 숫자를 채운 인쇄용 HTML
 *  (운영자 지시 2026-11-09 '경정청구 서식도 국세청 서식에 맞게 숫자로 채워서 만들어'). 서식 원문: 국가법령정보센터 국세기본법 시행규칙 [시행 2026. 3. 20.] 별지 제16호의2서식(1) <개정 2025. 3. 21.> PDF.
 *  고친 신고서 한 장(CorrDoc)마다 한 쪽. 새 계산 없음 — 값은 신고서에서 읽은 숫자와 진단(correctedFilings)의 고친 값 그대로.
 *  부가가치세는 서식의 '산출세액' 칸을 신고서의 납부(환급)세액(매출세액 − 매입세액)으로, '납부할 세액'을 차감·가감하여 납부할 세액으로 옮긴다(작성 안내에 적음).
 *  성명·주민등록번호·주소·전화·계좌·최초신고일·서명은 비워 둔다(기관이 적음 — 이 앱은 사람 이름·전화를 다루지 않음). 판정은 참고이며 기관의 판단이 아니다. */
import { esc, fmt } from './vat_rules';
import { corrReason, type CorrDoc } from './vat_diag';

const won = (v: number | null | undefined) => v == null ? '' : v < 0 ? `△${fmt(-v)}` : fmt(v);
/** 법정신고기한(예정 4·10월 25일, 확정 7월·다음 해 1월 25일). 토·일이면 다음 월요일(공휴일은 반영하지 않음 — 안내에 적음) */
function dueDate(y: number, h: number, kind: string): string {
  const pre = /예정/.test(kind); const [yy, mm] = h === 1 ? (pre ? [y, 4] : [y, 7]) : (pre ? [y, 10] : [y + 1, 1]);
  const d = new Date(yy, mm - 1, 25); while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}. ${d.getMonth() + 1}. ${d.getDate()}.`;
}
const CSS = `@page{size:A4;margin:12mm}*{box-sizing:border-box}body{font-family:'Malgun Gothic','맑은 고딕',sans-serif;font-size:10pt;color:#000;margin:0;background:#eee}
.page{background:#fff;width:186mm;min-height:270mm;margin:8mm auto;padding:6mm;page-break-after:always}.page:last-child{page-break-after:auto}
.top{display:flex;justify-content:space-between;font-size:8.5pt}h1{text-align:center;font-size:16pt;margin:4mm 0 1mm;letter-spacing:1px}.sub{text-align:center;font-size:9pt;margin-bottom:2mm}
table{width:100%;border-collapse:collapse;table-layout:fixed}td,th{border:.6pt solid #000;padding:1.6mm 2mm;vertical-align:middle;font-weight:normal;text-align:left;word-break:keep-all}
th{background:#f2f2f2}.c{text-align:center}.r{text-align:right;font-variant-numeric:tabular-nums}.v{font-weight:bold}.hint{color:#777;font-size:8.5pt}.thick{border-top:1.4pt solid #000}
.side{width:9mm;text-align:center;writing-mode:vertical-rl;letter-spacing:4px}.stmt{padding:3mm 2mm;line-height:1.7}.sig{text-align:right;padding:2mm 6mm}.to{font-size:12pt;padding:3mm 2mm}
.note{font-size:9pt;line-height:1.6}.note li{margin:1mm 0}.bar{max-width:186mm;margin:6mm auto 0;display:flex;gap:8px;align-items:center}.bar button{font:inherit;padding:6px 12px}
@media print{body{background:#fff}.page{margin:0;width:auto;min-height:auto;padding:0}.no-print{display:none}}`;

function one(c: CorrDoc, orgName: string, orgReg: string): string {
  const [y, h] = c.k.split('-').map(Number); const P = `${y}년 제${h}기 ${c.kind}`;
  const reg = c.reg || orgReg;
  const credit = c.payBefore != null && c.pen != null && c.due != null ? c.payBefore + c.pen - c.due : null;   // ⑭ = ⑫ + ⑬ − ⑮ (서식 작성방법 5의 식을 거꾸로)
  const row = (n: string, label: string, a: string, b: string, hint = '') => `<tr><th>${n} ${label}</th><td class="r v">${a}</td><td class="r v">${b}${hint ? `<div class="hint">${hint}</div>` : ''}</td></tr>`;
  const blank = (t: string) => `<span class="hint">${esc(t)}</span>`;
  return `<section class="page">
  <div class="top"><span>[별지 제16호의2서식(1)] &lt;개정 2025. 3. 21.&gt;</span><span>(앞쪽)</span></div>
  <h1>과세표준 및 세액의 결정(경정)청구서</h1>
  <table><tr><td class="sub" style="border:0">[「국세기본법」 제45조의2 또는 「소득세법」 제118조의15에 따른 결정(경정) 청구]</td><td style="width:22mm" class="c">처리기간<br>2개월</td></tr></table>
  <table class="thick">
    <colgroup><col style="width:9mm"><col style="width:30mm"><col><col style="width:32mm"><col></colgroup>
    <tr><td class="side" rowspan="3">청구인</td><th>① 성 명</th><td>${blank('기관장 성명')}</td><th>② 주민등록번호</th><td>${blank('(기관은 적지 않음)')}</td></tr>
    <tr><th>④ 주소(거소) 또는 영업소</th><td>${blank('기관 소재지')}</td><th>③ 사업자등록번호</th><td class="v">${esc(reg) || blank('신고서의 사업자등록번호')}</td></tr>
    <tr><th>⑥ 상 호</th><td class="v">${esc(orgName)}</td><th>⑤ 전화번호</th><td>${blank('담당 부서 전화')}</td></tr>
  </table>
  <table class="thick"><tr><th class="c" colspan="4">신 고 내 용</th></tr>
    <tr><th style="width:32mm">⑦ 법정신고일</th><td class="v">${dueDate(y, h, c.kind)}</td><th style="width:32mm">⑧ 최초신고일</th><td>${blank('홈택스 신고내역의 접수일')}</td></tr>
    <tr><th>⑨ 결정(경정)<br>청구이유</th><td colspan="3">${esc(corrReason(c))}<div class="hint">과세기간: ${esc(P)} · 신고서 파일 ${esc(c.file)}</div></td></tr>
  </table>
  <table><colgroup><col style="width:46mm"><col><col></colgroup>
    <tr><th class="c">구 분</th><th class="c">최 초 신 고</th><th class="c">결 정(경 정) 청 구</th></tr>
    ${row('⑩', '세 목', '부가가치세', '부가가치세')}
    ${row('⑪', '과세표준금액', won(c.tb), won(c.tb), c.tb == null ? '신고서 (9) 합계 금액' : '')}
    ${row('⑫', '산출세액', won(c.payBefore), won(c.payAfter), '부가가치세: 납부(환급)세액 = 매출세액 − 공제받는 매입세액')}
    ${row('⑬', '가산세액', won(c.pen), won(c.pen), c.pen == null ? '신고서 가산세액 계(당초와 같음)' : '당초와 같음')}
    ${row('⑭', '공제 및 감면세액', won(credit), won(credit), credit == null ? '신고서 경감·공제세액·예정신고 미환급·예정고지 등(당초와 같음)' : '⑫ + ⑬ − ⑮ (당초와 같음)')}
    ${row('⑮', '납부할 세액', won(c.due), c.due == null ? '' : won(c.due - c.delta), c.due == null ? `신고서 차감·가감하여 납부할 세액 − ${fmt(c.delta)}` : '')}
    <tr><th>⑯ 국세환급금 계좌신고</th><td colspan="2">거래은행 ${blank('         ')} 은행 ${blank('      ')} 지점 &nbsp; 계좌번호 ${blank('기관 세입 계좌')}</td></tr>
    <tr class="thick"><th>⑰ 환급받을 세액</th><td colspan="2" class="r v" style="font-size:12pt">${fmt(c.delta)} 원</td></tr>
  </table>
  <table><tr><td class="stmt">「국세기본법」 제45조의2, 같은 법 시행령 제25조의3, 「소득세법」 제118조의15 및 같은 법 시행령 제178조의11에 따라 위와 같이 청구합니다.</td></tr>
    <tr><td class="sig">년 &nbsp;&nbsp;&nbsp; 월 &nbsp;&nbsp;&nbsp; 일<br><br>청구인 &nbsp; ${esc(orgName)} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; (서명 또는 인)</td></tr>
    <tr><td class="to">${blank('관할')} 세무서장 귀하</td></tr></table>
  <table><colgroup><col style="width:30mm"><col><col style="width:26mm"></colgroup>
    <tr><th>첨부서류</th><td>결정(경정)청구 사유 증명자료 — 최초 신고서 사본, 고친 신고서(이 묶음의 '고친 신고서'), 공제받지 못할 매입세액 명세서(고친 값)${c.parts.length ? ', 공통매입세액 안분·정산 계산 근거' : ''}</td><td class="c">수수료<br>없음</td></tr></table>
</section>`;
}

/** 고친 신고서들 → 경정청구서 서식 HTML 문서(인쇄·PDF 저장용). 없으면 빈 문자열 */
export function claimFormHtml(M: Map<string, CorrDoc[]>, orgName: string, orgReg = ''): string {
  const L = [...M].sort().flatMap(([, v]) => v).filter(c => c.delta > 0);
  if (!L.length) return '';
  const total = L.reduce((s, c) => s + c.delta, 0);
  const guide = `<section class="page note"><h1 style="font-size:13pt">경정청구서 작성 안내 (이 쪽은 제출하지 않음)</h1>
  <ul>
    <li>국세기본법 시행규칙 별지 제16호의2서식(1) 「과세표준 및 세액의 결정(경정)청구서」 칸 배치대로, 신고서에서 읽은 숫자와 고친 값을 채웠습니다. 고친 신고서 한 장마다 한 쪽, 모두 ${L.length}쪽 · 환급받을 세액 합계 ${fmt(total)}원입니다.</li>
    <li>채운 칸: ③ 사업자등록번호(신고서), ⑥ 상호(기관 이름), ⑦ 법정신고일(토·일이면 다음 월요일 — 공휴일은 확인하세요), ⑨ 청구이유, ⑩~⑮ 최초 신고·경정 청구 값, ⑰ 환급받을 세액.</li>
    <li>기관이 적을 칸: ① 성명(기관장), ④ 주소, ⑤ 전화번호, ⑧ 최초신고일(홈택스 신고내역 접수일), ⑯ 환급 계좌(기관 세입 계좌), 날짜·서명, 관할 세무서. 회색 글씨는 안내이므로 지우고 적습니다.</li>
    <li>부가가치세는 서식의 '산출세액'을 신고서의 납부(환급)세액(매출세액 − 공제받는 매입세액)으로 적었습니다. 가산세·경감공제세액은 이번 청구로 바뀌지 않아 당초와 같은 값입니다. 신고서에서 그 칸을 못 읽은 경우는 비워 두었으니 홈택스 신고서 값을 적으세요.</li>
    <li>홈택스로 청구할 때는 신고/납부 → 세금신고 → 부가가치세 → 경정청구 화면에 같은 값을 넣고, 이 서식은 결재·보관용으로 씁니다. 서면으로 낼 때는 이 서식에 최초 신고서 사본과 고친 신고서·증명자료를 붙여 관할 세무서에 냅니다(국세기본법 시행규칙 제12조의2).</li>
    <li>숫자는 올린 신고서로 다시 계산한 참고값입니다. 판정은 참고이며 기관의 판단이 아닙니다 — 제출 전 담당자가 신고서와 대조하세요.</li>
  </ul></section>`;
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>경정청구서(별지 제16호의2서식) — ${esc(orgName)}</title><style>${CSS}</style></head><body>
<div class="bar no-print"><button type="button" onclick="window.print()">인쇄 · PDF로 저장</button><span>A4 세로로 인쇄됩니다. PDF는 인쇄 창에서 'PDF로 저장'을 고르세요.</span></div>
${guide}${L.map(c => one(c, orgName, orgReg)).join('\n')}</body></html>`;
}

/** 같은 서식을 PDF 로(운영자 지시 2026-11-09 'pdf로 다운 받을 수 있게 해야되') — 칸 배치·값은 claimFormHtml 과 같다. A4 세로, 고친 신고서 한 장마다 한 쪽, 작성 안내는 맨 뒤 쪽(제출하지 않음).
 *  글꼴·그리기는 pdf.ts pdfKit(Pretendard 통째로). 회색 글씨는 기관이 적을 칸의 안내. */
export async function claimFormPdf(M: Map<string, CorrDoc[]>, orgName: string, orgReg = ''): Promise<Blob | null> {
  const L = [...M].sort().flatMap(([, v]) => v).filter(c => c.delta > 0);
  if (!L.length) return null;
  const K = await import('./pdf').then(m => m.pdfKit());
  const { doc, text, width, lines, MM, INK, MUTED } = K; const BG = K.rgb(0.95, 0.95, 0.95);
  doc.setTitle(`경정청구서(별지 제16호의2서식) — ${orgName}`);
  const PW = 210 * MM, PH = 297 * MM, X0 = 12 * MM, W = 186 * MM, PAD = 1.8 * MM;
  type Seg = { t: string; size?: number; bold?: boolean; hint?: boolean };
  type C = { w: number; segs: Seg[]; align?: 'l' | 'c' | 'r'; th?: boolean; vert?: boolean };
  let pg = doc.addPage([PW, PH]); let y = PH - 12 * MM;
  const segLines = (s: Seg, w: number) => lines(s.t, s.size ?? 9.5, w);
  const lh = (s: Seg) => (s.size ?? 9.5) * 1.4;
  /** 칸 한 줄 그리기 — 칸마다 글을 줄로 나눠 가장 높은 칸에 맞추고, 위아래 가운데. 반환: 높이 */
  const row = (cells: C[], minH = 8 * MM, top = 0.6) => {
    const ws = cells.map(c => c.w * MM);
    const laid = cells.map((c, i) => c.vert ? { L: [] as { s: Seg; t: string }[], h: [...c.segs.map(s => s.t).join('')].length * 11 } : (() => { const out: { s: Seg; t: string }[] = []; c.segs.forEach(s => segLines(s, ws[i] - 2 * PAD).forEach(t => out.push({ s, t }))); return { L: out, h: out.reduce((a, o) => a + lh(o.s), 0) }; })());
    const h = Math.max(minH, ...laid.map(l => l.h + 2 * PAD));
    let x = X0;
    cells.forEach((c, i) => {
      const w = ws[i];
      pg.drawRectangle({ x, y: y - h, width: w, height: h, color: c.th ? BG : undefined, borderColor: INK, borderWidth: 0.6 });
      if (c.vert) { const ch = [...c.segs.map(s => s.t).join('')]; let yy = y - (h - ch.length * 11) / 2 - 9; ch.forEach(t => { text(pg, t, { x: x + (w - width(t, 9.5)) / 2, y: yy, size: 9.5 }); yy -= 11; }); }
      else { let yy = y - (h - laid[i].h) / 2; laid[i].L.forEach(({ s, t }) => { const sz = s.size ?? 9.5; const tw = width(t, sz); const a = c.align ?? (c.th ? 'l' : 'l');
        const tx = a === 'c' ? x + (w - tw) / 2 : a === 'r' ? x + w - PAD - tw : x + PAD; text(pg, t, { x: tx, y: yy - sz * 1.05, size: sz, color: s.hint ? MUTED : INK }, !!s.bold); yy -= lh(s); }); }
      x += w;
    });
    if (top > 0.6) pg.drawLine({ start: { x: X0, y }, end: { x: X0 + W, y }, thickness: top, color: INK });
    y -= h; return h;
  };
  const v = (t: string, bold = true): Seg[] => [{ t, bold }];
  const hint = (t: string): Seg[] => [{ t, size: 8, hint: true }];
  const th = (t: string, w: number, align: 'l' | 'c' = 'l'): C => ({ w, segs: [{ t }], th: true, align });
  for (const c of L) {
    if (y < PH - 13 * MM) { pg = doc.addPage([PW, PH]); y = PH - 12 * MM; }
    const [yr, hf] = c.k.split('-').map(Number); const P = `${yr}년 제${hf}기 ${c.kind}`; const reg = c.reg || orgReg;
    const credit = c.payBefore != null && c.pen != null && c.due != null ? c.payBefore + c.pen - c.due : null;
    text(pg, '[별지 제16호의2서식(1)] <개정 2025. 3. 21.>', { x: X0, y: y - 8, size: 8 }); text(pg, '(앞쪽)', { x: X0 + W - width('(앞쪽)', 8), y: y - 8, size: 8 }); y -= 8 * MM;
    const T = '과세표준 및 세액의 결정(경정)청구서'; text(pg, T, { x: (PW - width(T, 16)) / 2, y: y - 16, size: 16 }, true); y -= 9 * MM;
    { const s = '[「국세기본법」 제45조의2 또는 「소득세법」 제118조의15에 따른 결정(경정) 청구]'; const yt = y;
      text(pg, s, { x: X0 + (164 * MM - width(s, 8.5)) / 2, y: y - 6 * MM, size: 8.5 }); y = yt; const x2 = X0 + 164 * MM;
      pg.drawRectangle({ x: x2, y: y - 10 * MM, width: 22 * MM, height: 10 * MM, borderColor: INK, borderWidth: 0.6 });
      ['처리기간', '2개월'].forEach((t, i) => text(pg, t, { x: x2 + (22 * MM - width(t, 8.5)) / 2, y: y - 4 * MM - i * 4 * MM, size: 8.5 })); y -= 12 * MM; }
    const R = 57.5;
    const y1 = y; row([{ w: 9, segs: [{ t: '' }] }, th('① 성 명', 30), { w: R, segs: hint('기관장 성명') }, th('② 주민등록번호', 32), { w: R, segs: hint('(기관은 적지 않음)') }], 9 * MM, 1.4);
    row([{ w: 9, segs: [{ t: '' }] }, th('④ 주소(거소) 또는 영업소', 30), { w: R, segs: hint('기관 소재지') }, th('③ 사업자등록번호', 32), { w: R, segs: reg ? v(reg) : hint('신고서의 사업자등록번호') }], 9 * MM);
    row([{ w: 9, segs: [{ t: '' }] }, th('⑥ 상 호', 30), { w: R, segs: v(orgName) }, th('⑤ 전화번호', 32), { w: R, segs: hint('담당 부서 전화') }], 9 * MM);
    { const hh = y1 - y; pg.drawRectangle({ x: X0, y, width: 9 * MM, height: hh, color: K.rgb(1, 1, 1), borderColor: INK, borderWidth: 0.6 });
      const ch = [...'청구인']; let yy = y + hh / 2 + ch.length * 6 - 9; ch.forEach(t => { text(pg, t, { x: X0 + (9 * MM - width(t, 9.5)) / 2, y: yy, size: 9.5 }); yy -= 12; }); }
    y -= 2 * MM;
    row([{ ...th('신 고 내 용', 186, 'c') }], 7 * MM, 1.4);
    row([th('⑦ 법정신고일', 32), { w: 61, segs: v(dueDate(yr, hf, c.kind)) }, th('⑧ 최초신고일', 32), { w: 61, segs: hint('홈택스 신고내역의 접수일') }]);
    row([th('⑨ 결정(경정) 청구이유', 32), { w: 154, segs: [{ t: corrReason(c), size: 8.5 }, { t: `과세기간: ${P} · 신고서 파일 ${c.file}`, size: 7.5, hint: true }] }], 14 * MM);
    y -= 2 * MM;
    row([th('구 분', 46, 'c'), th('최 초 신 고', 70, 'c'), th('결 정(경 정) 청 구', 70, 'c')], 7 * MM, 1.4);
    const num = (n: string, label: string, a: string, b: string, hn = '') => row([th(`${n} ${label}`, 46), { w: 70, segs: a ? v(a) : [{ t: '' }], align: 'r' }, { w: 70, segs: [...(b ? v(b) : []), ...(hn ? hint(hn) : [])].length ? [...(b ? v(b) : []), ...(hn ? hint(hn) : [])] : [{ t: '' }], align: 'r' }], 9 * MM);
    num('⑩', '세 목', '부가가치세', '부가가치세');
    num('⑪', '과세표준금액', won(c.tb), won(c.tb), c.tb == null ? '신고서 (9) 합계 금액' : '');
    num('⑫', '산출세액', won(c.payBefore), won(c.payAfter), '납부(환급)세액 = 매출세액 − 공제 매입세액');
    num('⑬', '가산세액', won(c.pen), won(c.pen), c.pen == null ? '신고서 가산세액 계(당초와 같음)' : '당초와 같음');
    num('⑭', '공제 및 감면세액', won(credit), won(credit), credit == null ? '신고서 경감·공제세액 등(당초와 같음)' : '⑫ + ⑬ − ⑮ (당초와 같음)');
    num('⑮', '납부할 세액', won(c.due), c.due == null ? '' : won(c.due - c.delta), c.due == null ? `신고서 차감·가감하여 납부할 세액 − ${fmt(c.delta)}` : '');
    row([th('⑯ 국세환급금 계좌신고', 46), { w: 140, segs: [{ t: '거래은행             은행           지점    계좌번호 ' }, { t: '(기관 세입 계좌)', size: 8, hint: true }] }], 9 * MM);
    row([th('⑰ 환급받을 세액', 46), { w: 140, segs: [{ t: `${fmt(c.delta)} 원`, size: 12, bold: true }], align: 'r' }], 10 * MM, 1.4);
    y -= 2 * MM;
    row([{ w: 186, segs: [{ t: '「국세기본법」 제45조의2, 같은 법 시행령 제25조의3, 「소득세법」 제118조의15 및 같은 법 시행령 제178조의11에 따라 위와 같이 청구합니다.' }] }], 12 * MM);
    { const top = y; row([{ w: 186, segs: [{ t: '년        월        일' }, { t: ' ' }, { t: `청구인  ${orgName}            (서명 또는 인)` }], align: 'r' }], 20 * MM); void top; }
    row([{ w: 186, segs: [{ t: '관할', size: 8, hint: true }, { t: '세무서장 귀하', size: 12 }] }], 12 * MM);
    y -= 2 * MM;
    row([th('첨부서류', 30), { w: 130, segs: [{ t: `결정(경정)청구 사유 증명자료 — 최초 신고서 사본, 고친 신고서(이 묶음의 '고친 신고서'), 공제받지 못할 매입세액 명세서(고친 값)${c.parts.length ? ', 공통매입세액 안분·정산 계산 근거' : ''}`, size: 8.5 }] }, { w: 26, segs: [{ t: '수수료' }, { t: '없음' }], align: 'c' }], 14 * MM);
    text(pg, `${location.host} · 판정은 참고이며 기관의 판단이 아닙니다`, { x: X0, y: 7 * MM, size: 7, color: MUTED });
  }
  /* 작성 안내 쪽(맨 뒤 — 제출하지 않음) */
  pg = doc.addPage([PW, PH]); y = PH - 14 * MM;
  const total = L.reduce((s, c) => s + c.delta, 0);
  text(pg, '경정청구서 작성 안내 (이 쪽은 제출하지 않음)', { x: X0, y: y - 13, size: 13 }, true); y -= 10 * MM;
  const G = [`국세기본법 시행규칙 별지 제16호의2서식(1) 「과세표준 및 세액의 결정(경정)청구서」 칸 배치대로, 신고서에서 읽은 숫자와 고친 값을 채웠습니다. 고친 신고서 한 장마다 한 쪽, 모두 ${L.length}쪽 · 환급받을 세액 합계 ${fmt(total)}원입니다.`,
    '채운 칸: ③ 사업자등록번호(신고서), ⑥ 상호(기관 이름), ⑦ 법정신고일(토·일이면 다음 월요일 — 공휴일은 확인하세요), ⑨ 청구이유, ⑩~⑮ 최초 신고·경정 청구 값, ⑰ 환급받을 세액.',
    '기관이 적을 칸: ① 성명(기관장), ④ 주소, ⑤ 전화번호, ⑧ 최초신고일(홈택스 신고내역 접수일), ⑯ 환급 계좌(기관 세입 계좌), 날짜·서명, 관할 세무서. 회색 글씨는 안내입니다.',
    "부가가치세는 서식의 '산출세액'을 신고서의 납부(환급)세액(매출세액 − 공제받는 매입세액)으로 적었습니다. 가산세·경감공제세액은 이번 청구로 바뀌지 않아 당초와 같은 값입니다. 신고서에서 그 칸을 못 읽은 경우는 비워 두었으니 홈택스 신고서 값을 적으세요.",
    '홈택스로 청구할 때는 신고/납부 → 세금신고 → 부가가치세 → 경정청구 화면에 같은 값을 넣고, 이 서식은 결재·보관용으로 씁니다. 서면으로 낼 때는 이 서식에 최초 신고서 사본과 고친 신고서·증명자료를 붙여 관할 세무서에 냅니다(국세기본법 시행규칙 제12조의2).',
    '숫자는 올린 신고서로 다시 계산한 참고값입니다. 판정은 참고이며 기관의 판단이 아닙니다 — 제출 전 담당자가 신고서와 대조하세요.'];
  for (const g of G) { lines(g, 10, W - 6 * MM).forEach((t, i) => { if (i === 0) text(pg, '•', { x: X0, y: y - 10, size: 10 }); text(pg, t, { x: X0 + 5 * MM, y: y - 10, size: 10 }); y -= 15; }); y -= 5; }
  return K.save();
}
