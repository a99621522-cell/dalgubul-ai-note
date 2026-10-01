/**
 * 기업 카드 한 장 — 기업 페이지(/companies/<id>/)의 「기업 카드 PDF」「인쇄」 단추.
 * 페이지에 박힌 JSON(#card-data: 개요·고용·지원 이력·재무·협업 후보·출처)을 pdf.ts 로 PDF 한 장으로 만든다(HWPX 는 한글에서 깨져 바꿈, 2026-10-01).
 * 기업 방문·간담회·보고 전에 담당자가 만드는 한 장 자료를 대신한다(운영자 지시 2026-09-27). 공개 자료만, 평가·추천 없음.
 */
import { buildPdf, downloadPdf, p, table, safeName, today, type Block } from './pdf';

type Card = {
  id: string; name: string; district: string; desc: string; url: string;
  rows: [string, string][];                     // 개요 표 (항목, 값)
  support: string[][]; supportNote: string;     // 연도·사업명·지원기관·유형·금액
  fin: string[][]; finNote: string;
  partners: { stage: string; note: string; groups: [string, string[][]][] };   // [구분, [[기업, 단지, 업종, 규모]]]
  source: string;
};

function blocks(c: Card): Block[] {
  const out: Block[] = [
    p('kicker', [`기업 카드  ·  ${c.district}`, 'kicker']),
    p('title', [c.name, 'title']), p('rule', ['', 'caption']),
    p('body', [c.desc, 'body']),
    p('h3', ['개요', 'h3']),
    table(c.rows.map(([k, v]) => [k, v]), { head: false, widths: [11000, 37188] }),
    p('spacer', ['', 'caption']),
    p('h3', ['지원사업 이력 (최근 3년)', 'h3']),
  ];
  if (c.support.length) {
    out.push(table([['연도', '사업명', '지원기관', '유형', '금액'], ...c.support], { widths: [5000, 18000, 12000, 5500, 7688] }));
    out.push(p('spacer', ['', 'caption']));
  }
  out.push(p('note', [c.supportNote, 'note']));
  if (c.fin.length) {
    out.push(p('h3', ['재무 (DART 공시)', 'h3']));
    out.push(table([['사업연도', '매출액', '영업이익', '당기순이익'], ...c.fin], { widths: [9000, 13000, 13000, 13188] }));
    out.push(p('spacer', ['', 'caption']));
    out.push(p('note', [c.finNote, 'note']));
  }
  const rows: string[][] = [];
  for (const [g, list] of c.partners.groups) for (const r of list.slice(0, 4)) rows.push([g, ...r]);
  out.push(p('h3', [`협업 후보 (공정 단계: ${c.partners.stage})`, 'h3']));
  if (rows.length) {
    out.push(table([['구분', '기업', '단지', '업종', '규모'], ...rows], { widths: [7000, 14000, 10000, 11188, 6000] }));
    out.push(p('spacer', ['', 'caption']));
  } else out.push(p('body', ['같은 단지·구군 안에서 찾은 후보 없음.', 'body']));
  out.push(p('note', [c.partners.note, 'note']));
  out.push(p('src', [`출처: ${c.source}. ${c.url}, ${today()} 내려받음. 공개 자료를 그대로 옮긴 것으로 평가·추천이 아니며 비공개 자료는 싣지 않습니다.`, 'src']));
  return out;
}

export function init(): void {
  const el = document.getElementById('card-data');
  const hwp = document.getElementById('card-hwp') as HTMLButtonElement | null;
  const prt = document.getElementById('card-print') as HTMLButtonElement | null;
  if (!el || !hwp) return;
  const c: Card = JSON.parse(el.textContent || '{}');
  hwp.addEventListener('click', async () => {
    try {
      hwp.disabled = true; hwp.textContent = '만드는 중…';
      downloadPdf(`기업카드 ${safeName(c.name)}.pdf`, await buildPdf(blocks(c), `기업 카드 · ${c.name}`, { landscape: false }));
    } catch { hwp.textContent = '만들기 실패'; setTimeout(() => { hwp.textContent = '기업 카드 PDF'; }, 1800); }
    finally { hwp.disabled = false; if (hwp.textContent === '만드는 중…') hwp.textContent = '기업 카드 PDF'; }
  });
  prt?.addEventListener('click', () => window.print());
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
