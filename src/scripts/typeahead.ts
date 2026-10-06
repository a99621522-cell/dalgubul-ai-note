/**
 * 검색창 자동완성(타입어헤드) + 최근 검색 — 첫 화면 큰 검색창(#home-q)과 통합 검색(#q)에 붙는다(디자인·UI 개선 2차 2026-10-06).
 * 색인은 /typeahead.json(기업 이름·구군, 글 제목, 부처 사업 이름)을 첫 글자를 칠 때 한 번만 받는다. 서버·AI 호출 없음.
 * ARIA combobox/listbox 패턴: 화살표로 이동, Enter 로 고른 항목 열기(없으면 검색), Esc 로 닫기. 최근 검색은 이 브라우저(localStorage)에만 8개.
 * 순서는 '이름이 검색어로 시작' → '포함', 그 안은 가나다순 — 추천·순위가 아니다.
 */
type Idx = { co: [string, string, string][]; posts: [string, string][]; pr: [string, string][] };
const KEY = 'ta-recent';
let idx: Promise<Idx> | null = null;
const load = () => (idx ??= fetch('/typeahead.json').then(r => r.json()));
const norm = (s: string) => (s || '').toLowerCase().replace(/\s+/g, '');
const esc = (s: string) => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!));
const recent = (): string[] => { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; } };
const saveRecent = (q: string) => { try { const r = [q, ...recent().filter(x => x !== q)].slice(0, 8); localStorage.setItem(KEY, JSON.stringify(r)); } catch { /* 저장 못 해도 검색은 된다 */ } };
const setRecent = (r: string[]) => { try { localStorage.setItem(KEY, JSON.stringify(r)); } catch { /* */ } };

type Item = { label: string; sub?: string; href?: string; q?: string; del?: string };

export function attachTypeahead(input: HTMLInputElement): void {
  if (input.dataset.ta) return;
  input.dataset.ta = '1';
  const form = input.closest('form');
  const box = document.createElement('div');
  const id = `${input.id}-ta`;
  box.id = id; box.className = 'ta'; box.setAttribute('role', 'listbox'); box.hidden = true;
  (form ?? input.parentElement!).insertAdjacentElement('afterend', box);
  input.setAttribute('role', 'combobox'); input.setAttribute('aria-autocomplete', 'list'); input.setAttribute('aria-expanded', 'false'); input.setAttribute('aria-controls', id);
  let items: Item[] = [], active = -1, seq = 0;

  const close = () => { box.hidden = true; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); active = -1; };
  const render = (groups: [string, Item[]][]) => {
    items = groups.flatMap(g => g[1]);
    if (!items.length) return close();
    let n = 0;
    box.innerHTML = groups.filter(g => g[1].length).map(([title, its]) => `<div class="ta-g"><div class="ta-h">${esc(title)}</div>` + its.map(it => {
      const i = n++;
      return `<div class="ta-i" role="option" id="${id}-${i}" data-i="${i}" aria-selected="false"><span class="ta-l">${esc(it.label)}</span>${it.sub ? `<span class="ta-s">${esc(it.sub)}</span>` : ''}${it.del != null ? `<button type="button" class="ta-x" data-del="${esc(it.del)}" aria-label="'${esc(it.del)}' 최근 검색에서 지우기">✕</button>` : ''}</div>`;
    }).join('') + '</div>').join('');
    box.hidden = false; input.setAttribute('aria-expanded', 'true'); active = -1;
  };
  const go = (it: Item) => { if (it.q != null) { input.value = it.q; saveRecent(it.q); form ? form.submit() : (location.href = `/search/?q=${encodeURIComponent(it.q)}`); } else if (it.href) { saveRecent(input.value.trim() || it.label); location.href = it.href; } };
  const showRecent = () => { const r = recent(); render([['최근 검색', r.map(q => ({ label: q, q, del: q }))]]); };
  const suggest = async () => {
    const q = input.value.trim(), my = ++seq;
    if (!q) return showRecent();
    const d = await load(); if (my !== seq) return;
    const nq = norm(q);
    const rank = (name: string) => { const nn = norm(name); return nn.startsWith(nq) ? 0 : nn.includes(nq) ? 1 : 2; };
    const pick = <T,>(arr: T[], name: (x: T) => string, lim: number) => arr.map(x => [rank(name(x)), x] as [number, T]).filter(p => p[0] < 2).sort((a, b) => a[0] - b[0] || name(a[1]).localeCompare(name(b[1]), 'ko')).slice(0, lim).map(p => p[1]);
    const co = pick(d.co, x => x[1], 5).map(x => ({ label: x[1], sub: x[2], href: `/companies/${x[0]}/` }));
    const po = pick(d.posts, x => x[0], 3).map(x => ({ label: x[0], sub: '글·리포트', href: x[1] }));
    const pr = pick(d.pr, x => x[0], 3).map(x => ({ label: x[0], sub: x[1], q: x[0] }));
    render([['기업', co], ['글·리포트', po], ['부처 사업', pr], ['', [{ label: `'${q}' 전체 검색`, q }]]]);
  };
  const setActive = (i: number) => {
    const els = box.querySelectorAll<HTMLElement>('.ta-i');
    els.forEach(e => e.setAttribute('aria-selected', 'false'));
    active = ((i % els.length) + els.length) % els.length;
    const el = els[active]; if (el) { el.setAttribute('aria-selected', 'true'); input.setAttribute('aria-activedescendant', el.id); el.scrollIntoView({ block: 'nearest' }); }
  };
  let timer = 0;
  input.addEventListener('input', () => { clearTimeout(timer); timer = window.setTimeout(suggest, 120); });
  input.addEventListener('focus', () => { if (!input.value.trim()) showRecent(); });
  input.addEventListener('keydown', e => {
    if (box.hidden) { if (e.key === 'ArrowDown') { e.preventDefault(); suggest(); } return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(active + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active - 1); }
    else if (e.key === 'Escape') { close(); }
    else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); go(items[active]); }
  });
  box.addEventListener('mousedown', e => {
    const t = e.target as HTMLElement;
    const del = t.closest<HTMLElement>('.ta-x');
    if (del) { e.preventDefault(); setRecent(recent().filter(x => x !== del.dataset.del)); showRecent(); return; }
    const it = t.closest<HTMLElement>('.ta-i'); if (it) { e.preventDefault(); go(items[Number(it.dataset.i)]); }
  });
  document.addEventListener('click', e => { if (!box.contains(e.target as Node) && e.target !== input) close(); });
  form?.addEventListener('submit', () => { const q = input.value.trim(); if (q) saveRecent(q); });
}

export function init(): void {
  document.querySelectorAll<HTMLInputElement>('input[type="search"][data-typeahead]').forEach(attachTypeahead);
}
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
}
