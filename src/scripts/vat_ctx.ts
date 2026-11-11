/** 영속 문맥 바(#vat-ctx): 기관 · 등록 단위 · 시설 수 | 다음 신고·D-day | 마지막 저장 시각 — 모든 /vat/* 페이지(VatNav.astro). 용어 사전 ? 단추도 여기서 한 번 연결. 서버 없음 */
import { $, esc, getOrg, getSaved, ymd, loadData, helpWire, vatConfirm, toast, ORG_KEY, LEDGER_KEY, FILINGS_KEY } from './vat_rules';
import { mountQuickStart } from './vat_org';
const box = $('vat-ctx');
const D0 = loadData();   // lock(지자체 전용 사이트)이면 '기관 바꾸기' 대신 '처음부터 다시'
const hm = (iso?: string) => { if (!iso) return ''; const d = new Date(iso); const t = new Date(); const same = d.toDateString() === t.toDateString(); return (same ? '오늘 ' : ymd(d) + ' ') + `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
function render() {
  if (!box) return; const org = getOrg(); const s = getSaved();
  const last = (['filings', 'ledger', 'org'] as const).map(k => ({ k, t: s[k] })).filter(x => x.t).sort((a, b) => b.t!.localeCompare(a.t!))[0];
  const WHAT = { org: '기관 설정', ledger: '지출 기록', filings: '신고 기록' } as const;
  box.innerHTML = [
    org ? `<span><b>${esc(org.org || '(기관 이름 없음)')}</b> · ${org.unit === 'entity' ? '사업자 단위' : '사업장별'} · 시설 ${org.facilities.length}곳 · <button type="button" class="link-btn" data-ctx-switch>${D0?.lock ? '처음부터 다시' : '기관 바꾸기'}</button></span>` : `<span>기관을 아직 고르지 않았습니다 — 아래 ①에서 고르세요</span>`,
    `<span class="vc-saved">${last ? `저장 ${hm(last.t)} (${WHAT[last.k]})` : '아직 저장한 것 없음'}</span>`,
  ].filter(Boolean).join('');
}
/* 기관 바꾸기(운영자 2026-10-28 '한번 선택한 기관이 변경이 안 돼'): 지금 설정·기록·신고 기록을 백업 키에 두고 비운 뒤 문맥 바 아래에 '기관 선택 → 바로 시작'을 연다 */
box?.addEventListener('click', async (e) => {   // 문맥 바는 render() 마다 다시 그리므로 위임
    if (!(e.target as HTMLElement).closest('[data-ctx-switch]')) return;
    const o = getOrg(); if (!o) return;
    if (!(await vatConfirm(D0?.lock ? `'${o.org}' 설정(확인 질문 답 포함)과 이 브라우저의 기록을 비우고 처음 상태로 다시 시작합니다. 올린 신고서는 다시 놓아야 합니다.` : `'${o.org}' 설정과 이 브라우저의 지출 기록·신고 기록을 비우고 다른 기관으로 시작합니다. 10초 안에 되돌릴 수 있습니다.`, D0?.lock ? '비우고 다시' : '비우고 바꾸기'))) return;
    const snap: Record<string, string | null> = {}; for (const k of [ORG_KEY, LEDGER_KEY, FILINGS_KEY]) { try { snap[k] = localStorage.getItem(k); localStorage.removeItem(k); } catch { /* */ } }
    try { if (snap[ORG_KEY]) localStorage.setItem('vat-org-backup-v1', snap[ORG_KEY]!); } catch { /* */ }
    toast(`'${o.org}' 설정·기록을 비웠습니다`, { fn: () => { for (const [k, v] of Object.entries(snap)) { try { if (v) localStorage.setItem(k, v); } catch { /* */ } } location.reload(); } });
    if (D0?.lock) { try { localStorage.removeItem('vat-review-v1'); } catch { /* */ } location.reload(); return; }   // 전용 사이트: 다시 열면 그 지자체로 새로 만든다(startFromLink)
    render(); let qs = document.getElementById('ctx-qs'); if (!qs) { qs = document.createElement('div'); qs.id = 'ctx-qs'; box!.after(qs); }
    const D = loadData(); if (D) mountQuickStart(qs, D, () => location.reload(), 'ctx-qs-box'); 
    qs.scrollIntoView({ block: 'start' });
});
render();
document.addEventListener('vat:saved', render);
window.addEventListener('storage', render);
helpWire(document, loadData());

/* 글자 크기 토글(공무원 UX 재설계 §5): html[data-fs] 0/1/2 → --text-base 18/20/22px, /vat/* 에서만 */
const fsBtns = [...document.querySelectorAll<HTMLButtonElement>('.vat-fs button')];
const fsApply = (v: string) => { if (v === '0') document.documentElement.removeAttribute('data-fs'); else document.documentElement.setAttribute('data-fs', v); fsBtns.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.fs === v))); try { localStorage.setItem('vat-fs', v); } catch { /* */ } };
fsBtns.forEach(b => b.addEventListener('click', () => fsApply(b.dataset.fs ?? '0')));
{ const cur = document.documentElement.getAttribute('data-fs') ?? '0'; fsBtns.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.fs === cur))); }
/* 인쇄 머리글(기관 · 화면 · 만든 날) + 인쇄 때 결과의 펼침·탭을 모두 열고 끝나면 되돌림 */
const head = () => { const org = getOrg(); document.body.setAttribute('data-print-head', `${org ? org.org + ' · ' : ''}${document.title.replace(/ — .*$/, '')} · ${ymd(new Date())} · 참고용 계산(판정은 기관의 판단이 아님)`); };
head(); document.addEventListener('vat:saved', head);
let opened: HTMLDetailsElement[] = [];
window.addEventListener('beforeprint', () => { opened = [...document.querySelectorAll<HTMLDetailsElement>('main details:not([open])')].filter(d => !d.closest('.no-print')); opened.forEach(d => { d.open = true; }); });
window.addEventListener('afterprint', () => { opened.forEach(d => { d.open = false; }); opened = []; });
