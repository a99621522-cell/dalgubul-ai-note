/** 영속 문맥 바(#vat-ctx): 기관 · 등록 단위 · 시설 수 | 다음 신고·D-day | 마지막 저장 시각 — 모든 /vat/* 페이지(VatNav.astro). 용어 사전 ? 단추도 여기서 한 번 연결. 서버 없음 */
import { $, esc, getOrg, getSaved, nextFiling, ymd, loadData, helpWire, openItems } from './vat_rules';
const box = $('vat-ctx');
const hm = (iso?: string) => { if (!iso) return ''; const d = new Date(iso); const t = new Date(); const same = d.toDateString() === t.toDateString(); return (same ? '오늘 ' : ymd(d) + ' ') + `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
function render() {
  if (!box) return; const org = getOrg(); const f = nextFiling(); const s = getSaved();
  const last = (['filings', 'ledger', 'org'] as const).map(k => ({ k, t: s[k] })).filter(x => x.t).sort((a, b) => b.t!.localeCompare(a.t!))[0];
  const WHAT = { org: '기관 설정', ledger: '지출 기록', filings: '신고 기록' } as const;
  const oi = openItems();
  box.innerHTML = [
    org ? `<span><b>${esc(org.org || '(기관 이름 없음)')}</b> · ${org.unit === 'entity' ? '사업자 단위' : '사업장별'} · 시설 ${org.facilities.length}곳</span>` : `<span>기관 설정 없음 — <a href="/vat/setup/">설정하기</a></span>`,
    `<span>다음 신고 <b>${esc(f.name.replace(/\(.*\)/, '').trim())}</b> ${ymd(f.due)} · <b class="num">D-${f.days}</b></span>`,
    oi.total ? `<span>처리할 것 <b class="num">${oi.total}</b>건 — <a href="/vat/monthly/">보기</a></span>` : '',
    `<span class="vc-saved">${last ? `저장 ${hm(last.t)} (${WHAT[last.k]})` : '아직 저장한 것 없음'}</span>`,
  ].filter(Boolean).join('');
}
render();
document.addEventListener('vat:saved', render);
window.addEventListener('storage', render);
helpWire(document, loadData());
