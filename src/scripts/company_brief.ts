/**
 * 기업 방문 브리핑 — 기업 페이지(/companies/<id>/)의 「방문 브리핑 Word」「방문 브리핑 PDF」 단추(운영자 지시 2026-10-25 '1부터해').
 * 공무원이 기업 방문·간담회 전에 손으로 모으던 자료(개요·고용 변화·실적·회사가 공시한 경영 방향·최근 공시·지원 이력·업종 현황)를
 * 페이지에 박힌 JSON(#brief-data)으로 한두 장에 묶는다. '방문 때 확인해 볼 점'은 공개 자료의 변화에서 뽑은 질문 거리일 뿐 평가가 아니다.
 * 공개 자료만, 평가·추천·순위 없음, 대표자 등 개인정보 없음. HWPX 는 data/hwpx/compat.json 승인 전까지 내지 않는다.
 */
import { buildPdf, downloadPdf, p, table, safeName, type Block } from './pdf';

type Brief = {
  name: string; date: string; url: string;
  head: [string, string][];
  emp: { months: string[]; vals: number[]; note: string } | null;
  fin: string[][]; finNote: string; qtr: string; debt: string; dartEmp: string;
  mgmt: [string, string][]; mgmtSrc: string;
  disc: string[][];
  support: string[][]; supportNote: string;
  ctx: [string, string][]; ctxNote: string;
  asks: string[];
  partners: [string, string][];
  source: string;
};

const ym = (s: string) => { const [y, m] = s.split('-'); return `${y.slice(2)}.${Number(m)}`; };
const W = 48188;

export function blocks(b: Brief): Block[] {
  const out: Block[] = [
    p('kicker', [`기업 방문 브리핑  ·  ${b.date} 작성`, 'kicker']),
    p('title', [b.name, 'title']), p('rule', ['', 'caption']),
    p('h3', ['1. 한눈에 보기', 'h3']),
    table(b.head.map(([k, v]) => [k, v]), { head: false, widths: [10000, W - 10000] }),
    p('spacer', ['', 'caption']),
  ];
  let n = 2;
  if (b.emp) {
    // 달이 많으면 처음·중간·끝 위주로 6칸까지만
    const idx = b.emp.months.map((_, i) => i);
    const pick = idx.length <= 7 ? idx : [...new Set([0, ...[1, 2, 3, 4, 5].map(k => Math.round(k * (idx.length - 1) / 6)), idx.length - 1])];
    out.push(p('h3', [`${n++}. 고용 인원 변화`, 'h3']));
    out.push(table([pick.map(i => ym(b.emp!.months[i])), pick.map(i => `${b.emp!.vals[i].toLocaleString('ko-KR')}명`)], { widths: pick.map(() => Math.floor(W / pick.length)) }));
    out.push(p('note', [`※ ${b.emp.note}`, 'note']));
  }
  if (b.fin.length || b.qtr) {
    out.push(p('h3', [`${n++}. 실적 (DART 공시)`, 'h3']));
    if (b.fin.length) out.push(table([['사업연도', '매출액', '영업이익', '영업이익률', '매출 증감'], ...b.fin], { widths: [8000, 11000, 11000, 9000, 9188] }));
    for (const t of [b.qtr && `최근 분기: ${b.qtr}`, b.debt, b.dartEmp].filter(Boolean) as string[]) out.push(p('body', [t, 'body']));
    if (b.finNote) out.push(p('note', [`※ ${b.finNote}`, 'note']));
  }
  if (b.mgmt.length) {
    out.push(p('h3', [`${n++}. 회사가 공시한 경영 방향`, 'h3']));
    out.push(table(b.mgmt.map(([k, v]) => [k, v]), { head: false, widths: [9000, W - 9000] }));
    out.push(p('note', [`※ ${b.mgmtSrc}. 요약·해석하지 않았습니다.`, 'note']));
  }
  if (b.disc.length) {
    out.push(p('h3', [`${n++}. 최근 공시`, 'h3']));
    out.push(table([['접수일', '공시', '분야·내용'], ...b.disc], { widths: [8000, 20000, 20188] }));
  }
  out.push(p('h3', [`${n++}. 지원사업 이력 (최근 3년, 공개 자료)`, 'h3']));
  if (b.support.length) out.push(table([['연도', '사업명', '지원기관', '금액'], ...b.support], { widths: [5000, 22000, 13000, 8188] }));
  out.push(p('note', [`※ ${b.supportNote}`, 'note']));
  if (b.ctx.length) {
    out.push(p('h3', [`${n++}. 대구 같은 업종·같은 단지`, 'h3']));
    out.push(table(b.ctx.map(([k, v]) => [k, v]), { head: false, widths: [14000, W - 14000] }));
    out.push(p('note', [`※ ${b.ctxNote}`, 'note']));
  }
  out.push(p('h3', [`${n++}. 방문 때 확인해 볼 점`, 'h3']));
  for (const a of b.asks) out.push(p('body', [`- ${a}`, 'body']));
  out.push(p('note', ['※ 공개 자료에 나타난 변화에서 뽑은 질문 거리이며 기업에 대한 평가가 아닙니다.', 'note']));
  if (b.partners.length) {
    out.push(p('h3', [`${n++}. 협업 후보 (규칙으로 찾은 후보, 거래 관계 아님)`, 'h3']));
    out.push(table(b.partners.map(([k, v]) => [k, v]), { head: false, widths: [9000, W - 9000] }));
  }
  out.push(p('src', [`출처: ${b.source}. ${b.url}, ${b.date} 내려받음. 공개 자료를 옮긴 것으로 평가·추천이 아니며 비공개 자료·개인정보는 싣지 않습니다.`, 'src']));
  return out;
}

function wire(id: string, label: string, run: () => Promise<void>): void {
  const btn = document.getElementById(id) as HTMLButtonElement | null;
  btn?.addEventListener('click', async () => {
    try { btn.disabled = true; btn.textContent = '만드는 중…'; await run(); btn.textContent = label; }
    catch (e) { console.error(e); btn.textContent = '만들기 실패'; setTimeout(() => { btn.textContent = label; }, 1800); }
    finally { btn.disabled = false; }
  });
}

export function init(): void {
  const el = document.getElementById('brief-data');
  if (!el) return;
  const b: Brief = JSON.parse(el.textContent || '{}');
  const title = `기업 방문 브리핑 · ${b.name}`;
  const file = `방문브리핑 ${safeName(b.name)} ${b.date}`;
  wire('brief-pdf', '방문 브리핑 PDF', async () => downloadPdf(`${file}.pdf`, await buildPdf(blocks(b), title, { landscape: false })));
  wire('brief-docx', '방문 브리핑 Word', async () => {
    const { buildDocx } = await import('./company_docx');
    const blob = await buildDocx(blocks(b), title);
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${file}.docx`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  });
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
