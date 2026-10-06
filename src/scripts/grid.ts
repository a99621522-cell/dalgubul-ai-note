/**
 * 데이터 그리드(opt-in: table.data-table[data-grid]) — 데스크톱에서 표를 꺼내 쓰는 공무원용(docs/prompts/site_desktop_hwp_ui.md, 2026-10-06).
 * 정적 DOM 그대로에 ① 머리 고정(표를 높이 제한 상자에 넣고 thead sticky) ② 열 머리 클릭 정렬(오름→내림→해제, Shift 다중, aria-sort)
 * ③ 열 선택기(체크 목록, 숨긴 열은 복사·CSV·PDF 에서도 빠짐) ④ 표 안 검색(행 거르기·하이라이트) ⑤ 행 체크(선택 행만 복사)
 * ⑥ 밀도 토글 ⑦ 단축키('/' 검색, Ctrl+C 선택 행 복사는 표 도구 메뉴로). 정렬은 사용자의 작업이며 사이트가 매기는 순위가 아니다 — '순위'·'TOP' 라벨을 쓰지 않는다.
 * 머리가 두 줄(colspan)인 표는 아래 줄 칸을 열 기준으로 삼는다(rowspan 칸은 위 줄에서 찾음).
 */
const clean = (s: string) => s.replace(/\s+/g, ' ').trim();
const num = (s: string) => { const t = s.replace(/[,\s%억원명곳건개]/g, '').replace('−', '-'); const v = Number(t); return t !== '' && Number.isFinite(v) ? v : null; };

/** 머리 칸 → 열 번호(열 폭 colspan 을 펼쳐서). 두 줄 머리면 맨 아래 줄 칸이 열 머리, rowspan 으로 위 줄에만 있는 칸은 그대로 열 머리 */
function headerCols(tbl: HTMLTableElement): { th: HTMLTableCellElement; col: number; span: number }[] {
  const head = tbl.tHead; if (!head) return [];
  const rows = Array.from(head.rows);
  const occupied: Record<number, number> = {};   // col → 남은 rowspan
  const out: { th: HTMLTableCellElement; col: number; span: number; row: number }[] = [];
  rows.forEach((tr, ri) => {
    let col = 0;
    for (const th of Array.from(tr.cells)) {
      while (occupied[col] > 0) col++;
      out.push({ th, col, span: th.colSpan || 1, row: ri });
      for (let i = 0; i < (th.colSpan || 1); i++) { if ((th.rowSpan || 1) > 1) occupied[col + i] = (th.rowSpan || 1) - 1 + 1; col++; }
    }
    Object.keys(occupied).forEach(k => { occupied[+k] = Math.max(0, occupied[+k] - 1); });
  });
  // 열 머리 = 아래 줄 칸 + 위 줄에서 rowspan 으로 끝까지 내려온 칸(아래 줄에 같은 열이 없는 것)
  const last = rows.length - 1;
  const leafCols = new Set(out.filter(c => c.row === last).map(c => c.col));
  return out.filter(c => c.row === last || (!leafCols.has(c.col) && (c.th.rowSpan || 1) + c.row - 1 >= last)).map(({ th, col, span }) => ({ th, col, span }));
}

export function attachGrid(tbl: HTMLTableElement): void {
  if (tbl.dataset.gridOn) return; tbl.dataset.gridOn = '1';
  const bodies = Array.from(tbl.tBodies);
  const rows = () => bodies.flatMap(b => Array.from(b.rows));
  const cols = headerCols(tbl);
  const wrap = tbl.closest<HTMLElement>('.scroll-x') ?? tbl.parentElement!;
  // 툴바
  const bar = document.createElement('div'); bar.className = 'grid-bar'; bar.setAttribute('role', 'toolbar'); bar.setAttribute('aria-label', '표 다루기');
  wrap.insertAdjacentElement('beforebegin', bar);
  // ① 머리 고정: 높이 제한 상자 + sticky thead(.scroll-x 안에서는 세로 스크롤도 상자 안에서)
  wrap.classList.add('grid-scroll');
  const h1 = tbl.tHead?.rows[0]; if (h1 && tbl.tHead!.rows.length > 1) wrap.style.setProperty('--grid-h1', h1.getBoundingClientRect().height + 'px');   // 두 줄 머리의 둘째 줄 sticky 위치
  tbl.classList.add('grid');
  // ⑤ 행 체크 열
  const selTh = document.createElement('th'); selTh.className = 'grid-sel'; selTh.setAttribute('aria-label', '행 선택');
  const all = document.createElement('input'); all.type = 'checkbox'; all.title = '보이는 행 모두 선택'; selTh.appendChild(all);
  const headRows = tbl.tHead ? Array.from(tbl.tHead.rows) : [];
  headRows.forEach((tr, i) => { if (i === 0) { selTh.rowSpan = headRows.length; tr.insertBefore(selTh, tr.firstChild); } });
  rows().forEach(tr => { const td = document.createElement('td'); td.className = 'grid-sel'; const cb = document.createElement('input'); cb.type = 'checkbox'; cb.setAttribute('aria-label', '이 행 선택'); cb.addEventListener('change', () => tr.setAttribute('aria-selected', String(cb.checked))); td.appendChild(cb); tr.insertBefore(td, tr.firstChild); });
  all.addEventListener('change', () => rows().forEach(tr => { if (tr.hidden) return; const cb = tr.querySelector<HTMLInputElement>('td.grid-sel input'); if (cb) { cb.checked = all.checked; tr.setAttribute('aria-selected', String(all.checked)); } }));
  const off = 1;   // 체크 열만큼 열 번호가 밀린다
  // ② 정렬
  const state: { col: number; dir: 1 | -1 }[] = [];
  const cellText = (tr: HTMLTableRowElement, col: number) => clean((tr.cells[col + off] as HTMLElement | undefined)?.innerText ?? '');
  const cmp = (a: HTMLTableRowElement, b: HTMLTableRowElement) => {
    for (const s of state) {
      const x = cellText(a, s.col), y = cellText(b, s.col); const nx = num(x), ny = num(y);
      let d = 0;
      if (nx != null && ny != null) d = nx - ny; else if (nx != null) d = -1; else if (ny != null) d = 1; else d = x.localeCompare(y, 'ko');
      if (d) return d * s.dir;
    }
    return 0;
  };
  const original = rows().map((r, i) => [r, i] as const);
  const render = () => {
    const sorted = state.length ? [...original].sort((a, b) => cmp(a[0], b[0]) || a[1] - b[1]) : original;
    const body = bodies[0]; sorted.forEach(([r]) => body.appendChild(r));
    cols.forEach(c => { const s = state.find(x => x.col === c.col); c.th.setAttribute('aria-sort', s ? (s.dir > 0 ? 'ascending' : 'descending') : 'none'); c.th.classList.toggle('sorted', !!s); const n = state.findIndex(x => x.col === c.col); c.th.dataset.sortN = state.length > 1 && n >= 0 ? String(n + 1) : ''; });
  };
  cols.forEach(c => {
    if (c.span > 1) return;   // 묶음 머리(colspan)는 정렬하지 않는다
    const th = c.th; th.classList.add('sortable'); th.tabIndex = 0; th.setAttribute('role', 'columnheader'); th.setAttribute('aria-sort', 'none');
    th.title = '누르면 정렬(오름 → 내림 → 해제), Shift 로 여러 열';
    const go = (e: MouseEvent | KeyboardEvent) => {
      const i = state.findIndex(x => x.col === c.col);
      if (!(e as MouseEvent).shiftKey) { const cur = i >= 0 ? state[i] : null; state.length = 0; if (!cur) state.push({ col: c.col, dir: 1 }); else if (cur.dir === 1) state.push({ col: c.col, dir: -1 }); }
      else { if (i < 0) state.push({ col: c.col, dir: 1 }); else if (state[i].dir === 1) state[i].dir = -1; else state.splice(i, 1); }
      render();
    };
    th.addEventListener('click', go);
    th.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(e); } });
  });
  // ③ 열 선택기
  const picker = document.createElement('details'); picker.className = 'grid-menu';
  picker.innerHTML = `<summary class="btn secondary">열 선택 ▾</summary><div class="grid-list" role="group" aria-label="보일 열"></div>`;
  const plist = picker.querySelector('.grid-list')!;
  const setCol = (c: { col: number; span: number }, on: boolean) => {
    for (let k = 0; k < c.span; k++) { const idx = c.col + k + off; tbl.querySelectorAll<HTMLTableRowElement>('tbody tr, tfoot tr').forEach(tr => { const cell = tr.cells[idx]; if (cell) cell.classList.toggle('col-off', !on); }); }
    c.th.classList.toggle('col-off', !on);
    // 위 줄 묶음 머리(colspan)는 아래 열이 모두 꺼지면 함께 숨김 — 단순화: 그대로 둔다
  };
  cols.forEach(c => { const l = document.createElement('label'); const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = true; cb.addEventListener('change', () => setCol(c, cb.checked)); l.append(cb, ' ' + clean(c.th.innerText)); plist.appendChild(l); });
  const reset = document.createElement('button'); reset.type = 'button'; reset.className = 'tt-item'; reset.textContent = '모두 보이기'; reset.addEventListener('click', () => { plist.querySelectorAll<HTMLInputElement>('input').forEach(cb => { cb.checked = true; }); cols.forEach(c => setCol(c, true)); }); plist.appendChild(reset);
  // ④ 검색
  const q = document.createElement('input'); q.type = 'search'; q.placeholder = '표 안 검색'; q.className = 'grid-q'; q.setAttribute('aria-label', '표 안 검색');
  const count = document.createElement('span'); count.className = 'meta grid-count';
  const filter = () => {
    const t = q.value.trim().toLowerCase(); let n = 0;
    rows().forEach(tr => { const hit = !t || (tr as HTMLElement).innerText.toLowerCase().includes(t); tr.hidden = !hit; if (hit) n++; tr.classList.toggle('hit', !!t && hit); });
    count.textContent = t ? `${n.toLocaleString('ko-KR')}행 일치` : '';
  };
  q.addEventListener('input', filter);
  // ⑥ 밀도
  const dens = document.createElement('button'); dens.type = 'button'; dens.className = 'btn secondary'; dens.textContent = '촘촘히'; dens.setAttribute('aria-pressed', 'false');
  dens.addEventListener('click', () => { const on = tbl.classList.toggle('dense'); dens.setAttribute('aria-pressed', String(on)); dens.textContent = on ? '넓게' : '촘촘히'; });
  bar.append(q, count, picker, dens);
  const hint = document.createElement('span'); hint.className = 'tiny muted'; hint.textContent = '열 머리를 누르면 정렬(사용자 작업, 순위 아님) · 행 앞 체크로 골라 「선택 행만」 복사'; bar.appendChild(hint);
  document.addEventListener('click', e => { if (!picker.contains(e.target as Node)) picker.open = false; });
  tbl.addEventListener('keydown', e => { if (e.key === '/' && !(e.target as HTMLElement).matches('input')) { e.preventDefault(); q.focus(); } });
}

export function init(): void {
  document.querySelectorAll<HTMLTableElement>('table.data-table[data-grid]').forEach(attachGrid);
}
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
}
