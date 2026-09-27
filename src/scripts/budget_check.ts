/**
 * 예산서·결산서 지침 검토기 — /programs/guidelines/check/
 * 사용자가 고른 PDF·HWPX·TXT 파일을 브라우저 안에서만 읽어(서버·AI 호출 없음, 파일은 밖으로 나가지 않는다)
 * 지침 검토표(data/guidelines/checks/*.json)의 항목마다 자동 판정 규칙(rules.json)을 돌리고
 * 확인됨 / 보완 필요 / 검토 필요 / 미확인 / 직접 확인 으로 나눠 '어디를 어떻게 고칠지'를 표로 보여 준다.
 * 규칙은 공백을 뺀 글자에 정규식을 맞추는 참고용이며 조문 대조는 담당자가 한다(평가·판단 아님).
 * PDF 글자 추출은 pdf.js(pdfjs-dist, 빌드에 묶임)를 파일을 고른 뒤에만 불러 쓴다. HWPX 는 zip 을 DecompressionStream 으로 풀어 section*.xml 의 글자를 모은다.
 */
import { attach } from './table_tools';
import { buildHwpx, download, p, table, safeName, today, type Block } from './hwpx';
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

type Item = { id: string; stage: string; item: string; check: string; basis: string; quote: string; doc: string };
type Check = { key: string; name: string; eff: string; status: string; items: Item[] };
type Rule = { type: string; patterns?: string[]; warn?: string[]; then?: string[]; cond?: string; pattern?: string; amount?: string; frm?: string; to?: string; min?: number; max?: number; max_days?: number; fix?: string };
type Data = { checks: Check[]; rules: { doc_patterns: Record<string, string[]>; stage_patterns: Record<string, string[]>; items: Record<string, Rule> }; index: Record<string, { name: string; eff: string; url: string; issuer: string }> };
type Verdict = 'ok' | 'fix' | 'review' | 'none' | 'manual' | 'na';
type Result = { item: Item; v: Verdict; found: string; how: string };

const LABEL: Record<Verdict, string> = { ok: '확인됨', fix: '보완 필요', review: '검토 필요', none: '미확인', manual: '직접 확인', na: '해당 없음' };
const STAGES = ['예산요구서', '집행', '결산서'];

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T | null;
const norm = (s: string) => s.replace(/\s+/g, '');
const re = (s: string) => new RegExp(s, 'i');
const num = (s: string) => Number(String(s).replace(/,/g, ''));
const excerpt = (t: string, m: RegExpMatchArray, w = 36) => {
  const i = m.index ?? 0; const a = Math.max(0, i - w); const b = Math.min(t.length, i + m[0].length + w);
  return (a > 0 ? '…' : '') + t.slice(a, b) + (b < t.length ? '…' : '');
};
const dateOf = (m: RegExpMatchArray) => { const g = m.slice(1).filter(x => x !== undefined).slice(-3).map(Number); return new Date(g[0], g[1] - 1, g[2]).getTime(); };

/* ---------- 글자 추출 ---------- */
async function pdfText(buf: ArrayBuffer): Promise<string> {
  const lib: any = await import('pdfjs-dist');
  lib.GlobalWorkerOptions.workerSrc = pdfWorker;
  const doc = await lib.getDocument({ data: buf }).promise;
  const parts: string[] = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const c = await page.getTextContent();
    parts.push(c.items.map((it: any) => it.str ?? '').join(' '));
  }
  return parts.join('\n');
}
async function inflateRaw(data: Uint8Array): Promise<Uint8Array> {
  const ds = new DecompressionStream('deflate-raw');
  const w = ds.writable.getWriter(); w.write(data); w.close();
  return new Uint8Array(await new Response(ds.readable).arrayBuffer());
}
/** 최소 zip 읽기(중앙 디렉터리) — HWPX 의 Contents/section*.xml 만 */
async function hwpxText(buf: ArrayBuffer): Promise<string> {
  const b = new Uint8Array(buf); const dv = new DataView(buf);
  let eocd = -1;
  for (let i = b.length - 22; i >= Math.max(0, b.length - 70000); i--) if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  if (eocd < 0) throw new Error('zip');
  const n = dv.getUint16(eocd + 10, true); let off = dv.getUint32(eocd + 16, true);
  const out: string[] = []; const dec = new TextDecoder();
  for (let k = 0; k < n; k++) {
    if (dv.getUint32(off, true) !== 0x02014b50) break;
    const method = dv.getUint16(off + 10, true), csize = dv.getUint32(off + 20, true);
    const nlen = dv.getUint16(off + 28, true), elen = dv.getUint16(off + 30, true), clen = dv.getUint16(off + 32, true);
    const lho = dv.getUint32(off + 42, true); const name = dec.decode(b.subarray(off + 46, off + 46 + nlen));
    off += 46 + nlen + elen + clen;
    if (!/^Contents\/section\d+\.xml$/i.test(name)) continue;
    const ln = dv.getUint16(lho + 26, true), le = dv.getUint16(lho + 28, true); const start = lho + 30 + ln + le;
    const raw = b.subarray(start, start + csize);
    const xml = dec.decode(method === 8 ? await inflateRaw(raw) : raw);
    out.push(xml.replace(/<hp:t\b[^>]*>/g, '').replace(/<\/hp:t>/g, ' ').replace(/<\/hp:p>/g, '\n').replace(/<[^>]+>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/&quot;/g, '"'));
  }
  if (!out.length) throw new Error('section');
  return out.join('\n');
}
async function extract(file: File): Promise<string> {
  const ext = (file.name.split('.').pop() || '').toLowerCase();
  if (ext === 'pdf') return pdfText(await file.arrayBuffer());
  if (ext === 'hwpx') return hwpxText(await file.arrayBuffer());
  if (ext === 'hwp') throw new Error('HWP(구 형식)는 읽을 수 없습니다. 한글에서 「다른 이름으로 저장 → HWPX」 또는 PDF 로 바꿔 주세요.');
  return file.text();
}

/* ---------- 판정 ---------- */
function score(t: string, pats: Record<string, string[]>): [string, number][] {
  return Object.entries(pats).map(([k, ps]) => [k, ps.reduce((s, x) => s + (t.match(new RegExp(x, 'gi'))?.length ?? 0), 0)] as [string, number]).sort((a, b) => b[1] - a[1]);
}
function judge(t: string, it: Item, r: Rule | undefined): Result {
  const how = r?.fix || it.check;
  if (!r || r.type === 'manual') return { item: it, v: 'manual', found: '', how };
  const hit = (ps: string[]) => ps.map(x => t.match(re(x))).filter(Boolean) as RegExpMatchArray[];
  const warnHits = r.warn ? hit(r.warn) : [];
  if (warnHits.length) return { item: it, v: 'review', found: '문서에서 발견: ' + warnHits.map(m => `「${excerpt(t, m)}」`).join(' '), how };
  switch (r.type) {
    case 'any': { const h = hit(r.patterns!); return h.length ? { item: it, v: 'ok', found: excerpt(t, h[0]), how } : { item: it, v: 'none', found: '문서에서 관련 낱말을 찾지 못함', how }; }
    case 'all': {
      const miss: string[] = []; const got: RegExpMatchArray[] = [];
      for (const x of r.patterns!) { const m = t.match(re(x)); if (m) got.push(m); else miss.push(x.split('|')[0].replace(/[\\.{}()\[\]?*+^$]/g, '')); }
      if (!miss.length) return { item: it, v: 'ok', found: excerpt(t, got[0]), how };
      if (miss.length === r.patterns!.length) return { item: it, v: 'none', found: '문서에서 관련 낱말을 찾지 못함', how };
      return { item: it, v: 'fix', found: '빠진 항목: ' + miss.join(', '), how };
    }
    case 'absent': { const h = hit(r.patterns!); return h.length ? { item: it, v: 'review', found: '문서에서 발견: ' + h.map(m => `「${excerpt(t, m)}」`).join(' '), how } : { item: it, v: 'ok', found: '해당 낱말 없음', how }; }
    case 'flag': { const h = hit(r.patterns!); return h.length ? { item: it, v: 'review', found: '조건 확인 필요: ' + excerpt(t, h[0]), how } : { item: it, v: 'na', found: '해당 항목 없음', how }; }
    case 'if_then': {
      const c = t.match(re(r.cond!)); if (!c) return { item: it, v: 'na', found: '해당 사항 없음(' + r.cond!.split('|')[0] + ' 없음)', how };
      const miss = r.then!.filter(x => !t.match(re(x))).map(x => x.split('|')[0]);
      return miss.length ? { item: it, v: 'fix', found: `「${excerpt(t, c, 20)}」 있음, 빠진 것: ${miss.join(', ')}`, how } : { item: it, v: 'ok', found: excerpt(t, c, 20), how };
    }
    case 'number': {
      const m = t.match(re(r.pattern!)); if (!m) return { item: it, v: 'none', found: '비율(%)을 찾지 못함', how };
      const v = Number(m[1]); const f = `${excerpt(t, m, 20)} → ${v}%`;
      if (r.min !== undefined && v < r.min) return { item: it, v: 'review', found: `${f} (기준 ${r.min}% 이상)`, how };
      if (r.max !== undefined && v > r.max) return { item: it, v: 'review', found: `${f} (기준 ${r.max}% 이하)`, how };
      if (r.min === undefined && r.max === undefined) return { item: it, v: 'manual', found: f, how };
      return { item: it, v: 'ok', found: f, how };
    }
    case 'amount_then': {
      let best: [number, RegExpMatchArray] | null = null;
      for (const m of t.matchAll(new RegExp(r.amount!, 'gi'))) { const v = num(m[1]); if (!best || v > best[0]) best = [v, m]; }
      if (!best) return { item: it, v: 'none', found: '금액을 찾지 못함', how };
      const f = `${excerpt(t, best[1], 16)} (${best[0].toLocaleString('ko-KR')}원)`;
      if (best[0] < (r.min ?? 0)) return { item: it, v: 'na', found: f + ` — 기준 ${(r.min ?? 0).toLocaleString('ko-KR')}원 미만`, how };
      const miss = r.then!.filter(x => !t.match(re(x))).map(x => x.split('|')[0]);
      return miss.length ? { item: it, v: 'fix', found: f + ', 빠진 것: ' + miss.join(', '), how } : { item: it, v: 'ok', found: f, how };
    }
    case 'days': {
      const a = t.match(re(r.frm!)), b = t.match(re(r.to!));
      if (!a || !b) return { item: it, v: 'none', found: '날짜(기준일·제출일)를 찾지 못함', how };
      const d = Math.round((dateOf(b) - dateOf(a)) / 86400000);
      const f = `${a[0].slice(0, 30)} → ${b[0].slice(0, 30)} = ${d}일`;
      return d > (r.max_days ?? 0) || d < 0 ? { item: it, v: 'review', found: f + ` (기한 ${r.max_days}일)`, how } : { item: it, v: 'ok', found: f, how };
    }
  }
  return { item: it, v: 'manual', found: '', how };
}

/* ---------- 화면 ---------- */
let data: Data | null = null; let text = ''; let fileName = ''; let results: Record<string, Result[]> = {};
async function load(): Promise<Data> { if (!data) data = await (await fetch('/guidelines-checks.json')).json(); return data!; }

function render(): void {
  const d = data!; const key = ($<HTMLSelectElement>('bc-key')!).value; const check = d.checks.find(c => c.key === key)!;
  const stages = STAGES.filter(s => ($<HTMLInputElement>(`bc-stage-${s}`)!).checked);
  const out = $('bc-result')!; out.innerHTML = ''; results = {};
  const meta = d.index[key];
  const counts: Record<Verdict, number> = { ok: 0, fix: 0, review: 0, none: 0, manual: 0, na: 0 };
  const sections: string[] = [];
  for (const s of stages) {
    const rows = check.items.filter(i => i.stage === s).map(i => judge(text, i, d.rules.items[`${key}/${i.id}`]));
    results[s] = rows; rows.forEach(r => counts[r.v]++);
    sections.push(`<h3>${s} 검토 (${rows.length})</h3><div class="scroll-x"><table class="data-table check-table"><thead><tr><th>번호</th><th>판정</th><th>검토 항목</th><th>문서에서 찾은 것</th><th>고칠 방법</th><th>근거</th></tr></thead><tbody>` +
      rows.map((r, n) => `<tr class="v-${r.v}"><td class="n">${n + 1}</td><td><span class="verdict ${r.v}">${LABEL[r.v]}</span></td><td>${esc(r.item.item)}</td><td class="found">${esc(r.found)}</td><td>${esc(r.how)}<div class="meta">서류: ${esc(r.item.doc)}</div></td><td>${esc(r.item.basis)}<div class="quote">${esc(r.item.quote)}</div></td></tr>`).join('') + '</tbody></table></div>');
  }
  const todo = counts.fix + counts.review;
  out.innerHTML = `<div class="section-head"><h2>검토 결과 · ${esc(fileName)}</h2><span class="meta">${esc(meta?.name || check.name)} · 시행 ${esc(meta?.eff || check.eff)} · ${stages.join('·')} ${check.items.filter(i => stages.includes(i.stage)).length}항목</span></div>
    <p class="summary"><strong>고칠 곳 ${todo}건</strong>(보완 필요 ${counts.fix}, 검토 필요 ${counts.review}) · 확인됨 ${counts.ok} · 미확인 ${counts.none} · 직접 확인 ${counts.manual} · 해당 없음 ${counts.na}</p>
    <p class="meta">판정은 문서 글자에 규칙을 맞춘 참고용입니다. 「미확인」은 문서에서 관련 낱말을 못 찾은 것이므로 다른 서류에 있을 수 있고, 「직접 확인」은 문서만으로 판정할 수 없는 항목입니다. 조문(근거 열)은 지침 본문을 그대로 옮긴 것이며 최종 판단은 담당자가 합니다.</p>
    <div class="tools co-actions"><button class="btn" id="bc-hwp" type="button">검토 의견서 HWP</button><button class="btn secondary" id="bc-print" type="button">인쇄·PDF</button></div>` + sections.join('');
  out.querySelectorAll<HTMLTableElement>('table.data-table').forEach(attach);
  $('bc-hwp')!.addEventListener('click', hwp); $('bc-print')!.addEventListener('click', () => window.print());
  out.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
const esc = (s: string) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

async function hwp(): Promise<void> {
  const btn = $<HTMLButtonElement>('bc-hwp')!; const key = ($<HTMLSelectElement>('bc-key')!).value; const meta = data!.index[key]; const check = data!.checks.find(c => c.key === key)!;
  try {
    btn.disabled = true; btn.textContent = '만드는 중…';
    const blocks: Block[] = [p('kicker', [`지침 검토 의견서  ·  ${today()}  ·  다잇다 노트`, 'kicker']), p('title', [`「${meta?.name || check.name}」 대조 결과`, 'title']), p('rule', ['', 'caption']),
      p('body', [`검토 문서: ${fileName}. 대조 지침: ${meta?.name || check.name}(시행 ${meta?.eff || check.eff}). 브라우저 규칙 검토 결과이며 최종 판단은 담당자가 한다.`, 'body'])];
    for (const [s, rows] of Object.entries(results)) {
      const todo = rows.filter(r => r.v === 'fix' || r.v === 'review');
      blocks.push(p('h3', [`${s} — 고칠 곳 ${todo.length}건 / 확인됨 ${rows.filter(r => r.v === 'ok').length} / 미확인 ${rows.filter(r => r.v === 'none').length} / 직접 확인 ${rows.filter(r => r.v === 'manual').length}`, 'h3']));
      const list = todo.length ? todo : rows.filter(r => r.v !== 'na');
      blocks.push(table([['판정', '검토 항목', '문서에서 찾은 것', '고칠 방법', '근거'], ...list.map(r => [LABEL[r.v], r.item.item, r.found, r.how, `${r.item.basis} — ${r.item.quote}`])], { widths: [5000, 12000, 10000, 13188, 8000] }));
      blocks.push(p('spacer', ['', 'caption']));
    }
    blocks.push(p('src', [`출처: ${meta?.name || check.name} 본문(국가법령정보센터). 다잇다 노트 /programs/guidelines/check/ 에서 ${today()} 만듦. 파일은 브라우저 안에서만 읽었고 서버로 보내지 않았다.`, 'src']));
    download(`지침검토 ${safeName(fileName.replace(/\.[^.]+$/, ''))}.hwpx`, await buildHwpx(blocks, `지침 검토 의견서 · ${fileName}`));
  } catch { btn.textContent = '만들기 실패'; setTimeout(() => { btn.textContent = '검토 의견서 HWP'; }, 1800); }
  finally { btn.disabled = false; if (btn.textContent === '만드는 중…') btn.textContent = '검토 의견서 HWP'; }
}

async function onFile(file: File): Promise<void> {
  const st = $('bc-status')!; st.textContent = '파일을 읽는 중… (브라우저 안에서만 처리)';
  try {
    const d = await load(); const raw = await extract(file);
    text = norm(raw); fileName = file.name;
    if (text.length < 50) { st.textContent = '글자를 거의 찾지 못했습니다. 스캔 이미지 PDF 면 글자가 없어 검토할 수 없습니다(한글 원본을 PDF 로 다시 내보내 주세요).'; return; }
    const docS = score(text, d.rules.doc_patterns); const stS = score(text, d.rules.stage_patterns);
    const sel = $<HTMLSelectElement>('bc-key')!;
    if (!sel.dataset.user && docS[0][1] > 0) sel.value = docS[0][0];
    if (!sel.dataset.stageUser) {
      const top = stS.filter(s => s[1] > 0).map(s => s[0]);
      STAGES.forEach(s => { ($<HTMLInputElement>(`bc-stage-${s}`)!).checked = top.length ? top.slice(0, 2).includes(s) : true; });
    }
    st.textContent = `글자 ${text.length.toLocaleString('ko-KR')}자 읽음 · 지침 판정: ${docS.filter(x => x[1] > 0).slice(0, 3).map(x => `${d.index[x[0]]?.name || x[0]}(${x[1]})`).join(', ') || '단서 없음(직접 고르세요)'} · 문서 종류 단서: ${stS.filter(x => x[1] > 0).map(x => `${x[0]}(${x[1]})`).join(', ') || '없음'}`;
    render();
  } catch (e) { st.textContent = '읽기 실패: ' + ((e as Error).message || '지원하지 않는 파일'); }
}

export function init(): void {
  const input = $<HTMLInputElement>('bc-file'); if (!input) return;
  load().then(d => {
    const sel = $<HTMLSelectElement>('bc-key')!; sel.innerHTML = d.checks.map(c => `<option value="${c.key}">${esc(d.index[c.key]?.name || c.name)}</option>`).join('');
    sel.addEventListener('change', () => { sel.dataset.user = '1'; if (text) render(); });
    STAGES.forEach(s => $<HTMLInputElement>(`bc-stage-${s}`)!.addEventListener('change', () => { sel.dataset.stageUser = '1'; if (text) render(); }));
  }).catch(() => { $('bc-status')!.textContent = '검토표를 불러오지 못했습니다.'; });
  input.addEventListener('change', () => { const f = input.files?.[0]; if (f) onFile(f); });
  const drop = $('bc-drop')!;
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', e => { e.preventDefault(); drop.classList.remove('over'); const f = e.dataTransfer?.files?.[0]; if (f) onFile(f); });
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
