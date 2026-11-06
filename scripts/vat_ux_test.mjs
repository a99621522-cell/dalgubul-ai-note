// 지자체 부가세 절감 점검기 — 공무원 과업 8개 수용 시험(공무원 UX 재설계 2026-10-28, docs/design/vat-ux-spec.md §8).
// 빌드한 dist 를 띄운 뒤 실행: node scripts/vat_ux_test.mjs [--base http://localhost:4399] [--no-axe]   (base 가 없으면 dist 를 4398 에 직접 띄움)
// 2차(2026-11-03): W1~W8 — 이번 주 할 일·설정 깊은 링크·이름 일치·이번 달 끝 카드·지출 없음·매출 붙여넣기·경정청구 붙임 zip·인수인계 할 일(§11.11)
// 과업: T1 기관 설정(예시 → 그리드 → 일괄 적용 → org.json) + 키보드 변형 · T2 붙여넣기(열 교정·미확정만·일괄·즉시 신호등·검증·되돌리기·Ctrl+Enter) ·
//       T3 예정신고 저장 · T4 확정 정산 · T5 다음 기수 재계산 배지 · T6 지난 신고 점검 · T7 신축 설계 점검 · T8 인수인계 zip 복원 · 접근성(axe 5쪽·가로 스크롤) · 인쇄.
// 계산 값은 규칙(시행령 제81조·제82조·제83조)에서 식으로 세어 견준다 — 재설계는 화면만 바꾸고 계산은 바꾸지 않았다는 확인. 의존: playwright(+ @axe-core/playwright 는 있을 때만).
import { chromium } from 'playwright';
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path'; import os from 'node:os';
const args = process.argv.slice(2); let base = args.includes('--base') ? args[args.indexOf('--base') + 1] : ''; const noAxe = args.includes('--no-axe');
let srv = null; if (!base) { const root = path.resolve('dist'); srv = http.createServer((req, res) => { let p = decodeURIComponent(req.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html'; const f = path.join(root, p); if (!fs.existsSync(f)) { res.statusCode = 404; return res.end(); } res.setHeader('content-type', { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json' }[path.extname(f)] || 'application/octet-stream'); fs.createReadStream(f).pipe(res); }).listen(4398); base = 'http://localhost:4398'; }
const T = s => (s || '').replace(/\s+/g, ' ').trim(); let pass = 0, fail = 0; const ok = (n, c, x = '') => { console.log((c ? 'PASS' : 'FAIL') + ' ' + n + (x ? ' — ' + x : '')); c ? pass++ : fail++; };
const browser = await chromium.launch(process.env.PLAYWRIGHT_BROWSERS_PATH ? {} : { executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, acceptDownloads: true }); const pg = await ctx.newPage();
/* 세 걸음 판(2026-11-05): /vat/review/ 의 '자세히 보기'·'다른 방법'은 접혀 있다 — 기존 시나리오는 펼친 채로(접힌 첫 화면은 S 블록이 따로 본다) */
await ctx.addInitScript(() => { if (location.pathname.startsWith('/vat/review')) document.addEventListener('DOMContentLoaded', () => { for (const id of ['rf-detail', 'rf-files', 'rf-ref', 'rf-more', 'rf-other']) { const d = document.getElementById(id); if (d) d.open = true; } }); if (location.pathname.startsWith('/vat/review')) try { localStorage.setItem('vat-rv-supf', 'all'); } catch { /* */ } });
const errs = []; pg.on('pageerror', e => errs.push(String(e))); pg.on('console', m => { if (m.type() === 'error' && !/favicon|404/.test(m.text())) errs.push(m.text()); });
const ORG = { v: 1, org: '시험군', dept: '회계과', unit: 'entity', reg_no: '555-83-00001', facilities: [{ id: 'fA', type: 'sports', name: '군민체육관', run: 'direct', income: ['card'], deposit: false }, { id: 'fB', type: 'culture', name: '박물관', run: 'direct', income: ['card'], deposit: false }, { id: 'fC', type: 'lease', name: '상가 임대', run: 'direct', income: ['invoice'], deposit: true }], handover_day: 5, created: '2026-10-28', kind: 'gov', map: [{ pat: '체육관 운영', fid: 'fA', use: 'this' }] };
const ROW = (id, d, desc, amt, tax, use, what, extra = {}) => ({ id, d, desc, amt, tax, proof: 'e_invoice', payee: 'org', vat_sep: true, use, what, asset: false, late: false, evid: use === 'this' ? 'contract' : undefined, v: use === 'this' ? 'ok' : 'split', title: use === 'this' ? '공제' : '공통', todo: '', basis: '', done: false, ...extra });
const seed = async (ledger = null, filings = null) => { await pg.goto(base + '/vat/'); await pg.evaluate(([o, l, f]) => { localStorage.clear(); localStorage.setItem('vat-org-v1', JSON.stringify(o)); if (l) localStorage.setItem('vat-ledger-v1', JSON.stringify(l)); if (f) localStorage.setItem('vat-filings-v1', JSON.stringify(f)); }, [ORG, ledger, filings]); };
const lsJson = k => pg.evaluate(k => JSON.parse(localStorage.getItem(k) || 'null'), k);
const until = async (fn, ms = 3000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await fn()) return true; await pg.waitForTimeout(100); } return false; };

/* ── T1 기관 설정: 예시 → 그리드 → 전체 선택 → 운영 방식 일괄 → 결과 → org.json ── */
{
  let clicks = 0; const click = async s => { clicks++; await pg.click(s); };
  await pg.goto(base + '/vat/setup/'); await pg.evaluate(() => localStorage.clear()); await pg.reload(); await pg.waitForTimeout(300);
  await pg.fill('#st-org', '달성군'); await click('[data-next]'); await pg.waitForTimeout(200); await click('[data-preset]'); await pg.waitForTimeout(600);
  if (await pg.locator('#st-rev-add').isEnabled()) { await click('#st-rev-add'); await pg.waitForTimeout(800); }
  const total = await pg.locator('#st-grid tbody tr[data-fid]').count(); const pend = await pg.locator('#st-grid tbody tr[data-pending]').count();
  ok('T1 grid: imported rows pending(운영 방식을 근거로 채운 예시 시설은 빼고)', total > 40 && pend > total / 2 && pend <= total, `${pend}/${total}`);
  const fields = await pg.evaluate(() => [...document.querySelectorAll('.step[data-step="3"] input,.step[data-step="3"] select')].filter(e => e.offsetParent !== null && !e.closest('tr.sub')).length);
  const scroll = await pg.evaluate(() => document.documentElement.scrollHeight); console.log(`   T1 rows ${total} · visible fields ${fields} · scroll ${scroll}px (${(scroll / 768).toFixed(1)} screens)`);
  await click('[data-sel-all]'); await pg.selectOption('[data-bk=run]', 'direct'); clicks++; await click('[data-bulk=sel]'); await pg.waitForTimeout(300);
  ok('T1 bulk: no pending', await pg.locator('#st-grid tbody tr[data-pending]').count() === 0);
  await click('.step[data-step="3"] [data-next]'); await click('.step[data-step="4"] [data-next]'); await pg.waitForTimeout(400);
  const saved = await lsJson('vat-org-v1'); ok('T1 saved: 운영 방식 모두 정해짐(일괄 직영 + 예시의 대행 근거)', saved && saved.facilities.length === total && saved.facilities.every(f => f.run === 'direct' || f.run === 'entrusted_org') && saved.facilities.filter(f => f.run === 'direct').length > total / 2);
  const [dl] = await Promise.all([pg.waitForEvent('download'), click('#st-download')]); ok('T1 org.json download', !!dl);
  ok(`T1 clicks ≤ 20 (${clicks})`, clicks <= 20);
}
/* ── T1k 키보드만: Tab·Enter·Space·화살표 ── */
{
  await pg.goto(base + '/vat/setup/'); await pg.evaluate(() => localStorage.clear()); await pg.reload(); await pg.waitForTimeout(300);
  await pg.focus('#st-org'); await pg.keyboard.type('달성군'); await pg.focus('[data-next]'); await pg.keyboard.press('Enter'); await pg.waitForTimeout(200);
  await pg.focus('[data-preset]'); await pg.keyboard.press('Enter'); await pg.waitForTimeout(600); if (await pg.locator('#st-rev-add').isEnabled()) { await pg.focus('#st-rev-add'); await pg.keyboard.press('Enter'); await pg.waitForTimeout(800); }
  await pg.focus('[data-sel-all]'); await pg.keyboard.press('Space'); await pg.focus('[data-bk=run]'); await pg.keyboard.press('ArrowDown'); await pg.focus('[data-bulk=sel]'); await pg.keyboard.press('Enter'); await pg.waitForTimeout(300);
  ok('T1k keyboard bulk apply', await pg.locator('#st-grid tbody tr[data-pending]').count() === 0);
  await pg.keyboard.press('Alt+ArrowRight'); await pg.waitForTimeout(200); await pg.keyboard.press('Alt+ArrowRight'); await pg.waitForTimeout(400);
  ok('T1k Alt+→ to result', !(await pg.locator('.step[data-step="5"]').isHidden()));
}
/* ── T2 붙여넣기 ── */
{
  await seed({ 'fA:2026-10': [ROW('x1', '2026-10-13', '가상청소13 · 청소용역', 1300000, 130000, 'this', 'service', { sup: '가상청소13' })] });
  await pg.goto(base + '/vat/monthly/?fac=fA&month=2026-10&open=1'); await pg.waitForTimeout(400);
  ok('T2 deep link', await pg.inputValue('#m-fac') === 'fA' && await pg.inputValue('#m-month') === '2026-10' && await pg.locator('#mb-wrap').evaluate(d => d.open));
  const hdr = '작성일자\t공급자상호\t품목\t세부사업\t공급가액\t세액\t공급받는자등록번호'; const rows = [];
  for (let i = 1; i <= 12; i++) rows.push(`2026-10-${String(i).padStart(2, '0')}\t가상전력${i}\t전기요금\t체육관 운영\t${100000 * i}\t${10000 * i}\t555-83-00001`);
  for (let i = 13; i <= 19; i++) rows.push(`2026-10-${i}\t가상청소${i}\t청소용역\t\t${100000 * i}\t${10000 * i}\t${i === 19 ? '999-99-99999' : '555-83-00001'}`);
  rows.push('2026-10-20\t가상설비\t바닥 수선\t\t0\t0\t555-83-00001');
  let clicks = 0; const click = async s => { clicks++; await pg.click(s); };
  await pg.fill('#mb-text', [hdr, ...rows].join('\n')); await click('#mb-form button[type=submit]'); await pg.waitForTimeout(500);
  ok('T2 pending view 8/20', await pg.locator('#mb-table tbody tr:not([hidden])').count() === 8);
  const choices = await pg.evaluate(() => [...document.querySelectorAll('#mb-table tbody tr:not([hidden]) select')].reduce((s, e) => s + e.options.length, 0)); ok(`T2 visible choices ≤ 300 (${choices})`, choices <= 300);
  ok('T2 immediate verdict (다른 명의 → 불공제)', T(await pg.locator('#mb-table tbody tr[data-i="18"] td[data-v]').textContent()).includes('불공제'));
  ok('T2 flags unchecked', !(await pg.locator('#mb-table tbody tr[data-i="19"] [data-on]').isChecked()) && !(await pg.locator('#mb-table tbody tr[data-i="12"] [data-on]').isChecked()));
  await pg.locator('#mb-table select.colsel[data-col=desc]').selectOption(''); await pg.waitForTimeout(300); ok('T2 header remap rebuilds', !T(await pg.locator('#mb-table tbody tr[data-i="0"]').textContent()).includes('전기요금'));
  await pg.locator('#mb-table select.colsel[data-col=desc]').selectOption('2'); await pg.waitForTimeout(300);
  await click('#mb-table [data-on-all]'); await pg.selectOption('[data-mbk=use]', 'this'); clicks++; await pg.selectOption('[data-mbk=what]', 'utility'); clicks++; await click('[data-mbulk]'); await pg.waitForTimeout(200);
  ok('T2 bulk', await pg.locator('#mb-table tbody tr[data-i="15"] select[data-what]').inputValue() === 'utility');
  await pg.locator('#mb-table tbody tr[data-i="13"] [data-on]').focus(); await pg.keyboard.press('ArrowDown'); ok('T2 ArrowDown', await pg.evaluate(() => document.activeElement?.closest('tr')?.dataset.i) === '14');
  await click('[data-view=all]'); await pg.locator('[data-mbk=use]').focus(); await pg.keyboard.press('Control+Enter'); await pg.waitForTimeout(500);
  const led = (await lsJson('vat-ledger-v1'))['fA:2026-10']; ok('T2 added 18 (+1) = 19', led.length === 19); ok(`T2 clicks ≤ 25 (${clicks})`, clicks <= 25);
  await pg.click('#vat-toast [data-undo]'); await pg.waitForTimeout(300); ok('T2u undo → 1', (await lsJson('vat-ledger-v1'))['fA:2026-10'].length === 1);
}
/* ── T3·T4·T5 예정 → 확정 정산 → 다음 기수 재계산 (식으로 견줌) ── */
{
  const ledger = {
    'fA:2026-07': [ROW('a1', '2026-07-05', '7월 공용 전기', 1000000, 100000, 'multi', 'utility')],
    'fA:2026-08': [ROW('a2', '2026-08-05', '8월 체육관 전기', 500000, 50000, 'this', 'utility')],
    'fA:2026-09': [ROW('a3', '2026-09-05', '9월 공용 전기', 400000, 40000, 'multi', 'utility')],
    'fA:2026-10': [ROW('a4', '2026-10-05', '10월 공용 전기', 600000, 60000, 'multi', 'utility'), ROW('a5', '2026-10-20', '공용 승강기 수선', 10000000, 1000000, 'multi', 'repair', { asset: true })],
    'fA:2026-11': [ROW('a6', '2026-11-05', '11월 체육관 전기', 300000, 30000, 'this', 'utility')],
    'fA:2026-12': [ROW('a7', '2026-12-05', '12월 체육관 전기', 300000, 30000, 'this', 'utility')],
    'fA:2027-01': [ROW('a8', '2027-01-05', '1월 체육관 전기', 300000, 30000, 'this', 'utility')],
  };
  await seed(ledger);
  const prep = async (period, c3, ex) => { await pg.goto(base + '/vat/prepare/'); await pg.waitForTimeout(400); await pg.selectOption('#p-period', period); await pg.waitForTimeout(300); await pg.click('.pstep[data-pstep="1"] [data-pnext]'); await pg.waitForTimeout(100);
    await pg.fill('#p-sales [data-fid=fA] input[data-c=c3]', String(c3)); await pg.locator('#p-sales [data-fid=fA] input[data-c=c3]').dispatchEvent('change'); await pg.click('.pstep[data-pstep="2"] [data-pnext]'); await pg.waitForTimeout(100);
    const gb = pg.locator('#p-groups [data-g="entity"]'); await gb.locator('input[data-ex]').fill(String(ex)); await gb.locator('input[data-ex]').dispatchEvent('change'); await pg.waitForTimeout(100);
    await pg.click('#p-sum [data-psum-run]'); await until(async () => (await pg.locator('#p-result .unit').count()) > 0); };
  const cell = async no => T(await pg.locator(`#p-result table.form tbody tr:has(td:text-is("(${no})"))`).first().textContent());
  // T3 예정 2026-2P: 공통 140,000 × 1,000,000/(2,000,000+1,000,000) = 46,666
  await prep('2026-2P', 2000000, 1000000);
  ok('T3 wizard reached step 4', await pg.locator('#p-steps button[aria-current=step]').textContent() === '4 결과');
  ok('T3 처리할 것 card first', (await pg.locator('#p-result > *').nth(2).getAttribute('id')) === 'p-todo');
  ok('T3 (54) = 46,666', (await cell('54')).includes('46,666'));
  ok('T3 tabs default 신고서 only', await pg.locator('#p-result section.ftab:not([hidden])').count() === 1);
  await Promise.all([pg.waitForEvent('download'), pg.click('#p-save')]); ok('T3 saved', !!(await lsJson('vat-filings-v1'))['2026-2P']);
  // T4 확정 2026-2F: 전체 공통 140,000+1,060,000 = 1,200,000 × 1,500,000/4,500,000 = 400,000 − 예정 46,666 = 353,334
  await prep('2026-2F', 1000000, 500000);
  ok('T4 prelim prefilled from saved', await pg.locator('#p-groups [data-g="entity"] input[data-p=nondeduct]').inputValue() === '46,666');
  ok('T4 (54) = 400,000 − 46,666 = 353,334', (await cell('54')).includes('353,334'));
  ok('T4 (12) asset 10,000,000', (await cell('12')).includes('10,000,000'));
  await Promise.all([pg.waitForEvent('download'), pg.click('#p-save')]);
  // T5 2027-1P: 면세비율 100,000/1,100,000 = 9.09% → 취득 때 33.33% 와 24.24%p 차이, 승강기 1,000,000 × (1 − 0.05×1) × (0.0909 − 0.3333) = −230,304 (시행령 제83조)
  const rc = Math.floor(1000000 * 0.95 * (100000 / 1100000 - 1500000 / 4500000));
  await prep('2027-1P', 1000000, 100000);
  const todo = T(await pg.locator('#p-todo').textContent()); ok('T5 재계산 badge in 처리할 것', /재계산 1건/.test(todo), todo.slice(0, 160));
  ok(`T5 (54) = ${rc.toLocaleString('ko-KR')}`, (await cell('54')).includes(rc.toLocaleString('ko-KR')), await cell('54'));
  ok('T5 산출 근거 popover', (await pg.locator('#p-result button.help[data-text]').count()) > 5);
  await pg.locator('#p-result .tabs [role=tab]', { hasText: '신고서' }).first().click(); await pg.waitForTimeout(150);   /* 2차: 직접 신고 기관은 '홈택스 입력 순서' 탭이 먼저라 신고서 탭을 연 뒤 */
  await pg.locator('#p-result button.help[data-text]:visible').first().click(); ok('T5 popover text', T(await pg.locator('#p-result .pop').textContent()).includes('이번 값')); await pg.keyboard.press('Escape');
  // 인쇄: 탭 전부 펼침 + 머리글
  await pg.emulateMedia({ media: 'print' }); const shown = await pg.evaluate(() => [...document.querySelectorAll('#p-result section.ftab')].every(s => getComputedStyle(s).display !== 'none'));
  ok('print: all form tabs displayed', shown); ok('print: header attr', !!(await pg.evaluate(() => document.body.getAttribute('data-print-head')))); await pg.emulateMedia({ media: 'screen' });
}
/* ── T6 지난 신고 점검 ── */
{
  await pg.goto(base + '/vat/review/'); await pg.waitForTimeout(300); await pg.fill('#rv-reg', '555-83-00001');
  await pg.click('[data-rvsrc="paste"]'); await pg.fill('#rv-a', '작성일자\t공급자등록번호\t공급자상호\t품목\t공급가액\t세액\t공급받는자등록번호\n2024-03-05\t123-45-67890\t가상전력\t전기요금\t1,500,000\t150,000\t555-83-00001\n2024-09-05\t123-45-67890\t가상전력\t전기요금\t1,000,000\t100,000\t555-83-00001');
  await pg.evaluate(() => document.getElementById('rv-form').requestSubmit()); await pg.waitForTimeout(400); await pg.click('#rv-build'); await pg.waitForTimeout(500);
  const t = T(await pg.locator('#rv-result').textContent()); ok('T6 review result with 경정청구 기한', t.includes('2024') && /경정청구|기한/.test(t));
}
/* ── T7 신축·대수선 ── */
{
  await pg.goto(base + '/vat/build/'); await pg.waitForTimeout(300); await pg.fill('#b-name', '가상 체육관 신축'); await pg.fill('#b-cost', '10,000,000,000'); await pg.fill('#b-tax', '600'); await pg.fill('#b-ex', '300'); await pg.fill('#b-shared', '100');
  await pg.click('#b-run'); await pg.waitForTimeout(400); const t = T(await pg.locator('#b-result').textContent()); ok('T7 build result + checklist', t.includes('점검표') && await pg.locator('#b-result input[type=checkbox]').count() >= 10);
}
/* ── T8 인수인계 ── */
{
  await pg.goto(base + '/vat/handover/'); await pg.waitForTimeout(300); const inv = T(await pg.locator('#h-inv').textContent()); ok('T8 inventory lists filings', /신고 기록/.test(inv));
  const [dl] = await Promise.all([pg.waitForEvent('download'), pg.click('#h-zip')]); const zp = path.join(os.tmpdir(), 'vat-ux-handover.zip'); await dl.saveAs(zp);
  const c2 = await browser.newContext({ viewport: { width: 1366, height: 768 } }); const p2 = await c2.newPage(); await p2.goto(base + '/vat/handover/'); await p2.waitForTimeout(300); await p2.setInputFiles('#h-open', zp); await p2.waitForTimeout(500);
  const o2 = await p2.evaluate(() => [JSON.parse(localStorage.getItem('vat-org-v1') || 'null'), Object.keys(JSON.parse(localStorage.getItem('vat-filings-v1') || '{}')).length, Object.values(JSON.parse(localStorage.getItem('vat-ledger-v1') || '{}')).flat().length]);
  ok('T8 restored org·filings·ledgers', o2[0]?.org === '시험군' && o2[1] === 2 && o2[2] === 8, JSON.stringify([o2[0]?.org, o2[1], o2[2]])); await c2.close();
}
/* ── 접근성: axe(있을 때만) + 가로 스크롤, 5쪽 × 2 뷰포트 ── */
{
  let AxeBuilder = null; if (!noAxe) { try { ({ AxeBuilder } = await import('@axe-core/playwright')); } catch { console.log('   (axe 없음 — @axe-core/playwright 미설치, 가로 스크롤만 확인)'); } }
  for (const vp of [{ width: 390, height: 844 }, { width: 1366, height: 768 }]) {
    const c = await browser.newContext({ viewport: vp }); const p = await c.newPage(); await p.goto(base + '/vat/'); await p.evaluate(o => localStorage.setItem('vat-org-v1', JSON.stringify(o)), ORG);
    for (const u of ['/vat/', '/vat/setup/', '/vat/monthly/', '/vat/prepare/', '/vat/review/']) {
      await p.goto(base + u, { waitUntil: 'load' }); await p.waitForTimeout(300); if (u === '/vat/monthly/') { await p.selectOption('#m-fac', 'fA'); await p.waitForTimeout(200); }
      const hs = await p.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1); let v = [];
      if (AxeBuilder) v = (await new AxeBuilder({ page: p }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()).violations;
      ok(`a11y ${vp.width}px ${u}`, !hs && v.length === 0, (hs ? '가로 스크롤 ' : '') + v.map(x => `${x.id}×${x.nodes.length}`).join(' '));
    }
    await c.close();
  }
}

/* ── W1~W8 (2차 UX, docs/design/vat-ux-spec.md §11.11, 2026-11-03): 이번 주 할 일·설정 깊은 링크·이름 일치·이번 달 끝·지출 없음·매출 붙여넣기·경정청구 붙임·인수인계 할 일 ── */
{
  const { execSync } = await import('node:child_process'); pg.removeAllListeners('dialog'); pg.on('dialog', d => d.accept());
// W1 quick start → dashboard
await pg.goto(base + '/vat/'); await pg.evaluate(() => localStorage.clear()); await pg.reload(); await pg.waitForFunction(() => document.querySelector('#d-qs [data-qs-sel]')?.options.length > 3, null, { timeout: 10000 }); await pg.click('#d-qs [data-qs-go]'); await pg.waitForTimeout(1500);
const cta = pg.locator('#vat-cta'); ok('W1 CTA = 기관 설정 마저 채우기 → step=3', T(await cta.textContent()) === '기관 설정 마저 채우기' && /\/vat\/setup\/\?step=3&filter=/.test(await cta.getAttribute('href') || ''));
const nW = await pg.locator('#vat-week li').count(); ok('W1 이번 주 할 일 1~5개', nW >= 1 && nW <= 5, String(nW));
await pg.check('#vat-week [data-week]:first-child, #vat-week li:first-child input'); await pg.reload(); await pg.waitForTimeout(800); ok('W1 체크가 새로 고침 뒤 남음', await pg.locator('#vat-week li:first-child input').isChecked());
// W2 setup deep link + warning
await pg.goto(base + '/vat/setup/?step=3&filter=noreg'); await pg.waitForTimeout(900);
// 바로 시작이 본청 번호를 시설마다 채우므로(2026-11-03) '등록번호 없음'은 0 → 칩이 '전체'로 돌아간다
const nNoReg = await pg.evaluate(() => JSON.parse(localStorage.getItem('vat-org-v1')).facilities.filter(f => !f.reg_no && f.run !== 'entrusted_own').length);
ok('W2 3단계로 열리고 noreg 0 → 전체 칩', !(await pg.locator('.step[data-step="3"]').isHidden()) && nNoReg === 0 && (await pg.locator('#st-fac [data-filter=all]').getAttribute('aria-pressed')) === 'true', String(nNoReg));
ok('W2 등록번호 열 출처 ? 단추', await pg.locator('#st-fac button.help.src').count() >= 1);
await pg.goto(base + '/vat/setup/'); await pg.waitForTimeout(800); ok('W2 5단계 경고 상자 + 단추 2개', await pg.locator('#st-gaps').count() === 1 && (await pg.locator('#st-gaps button').count()) >= 2);
await pg.click('#st-gaps [data-gofilter=pending]'); await pg.waitForTimeout(400); ok('W2 경고 단추 → 3단계 pending 필터', !(await pg.locator('.step[data-step="3"]').isHidden()) && (await pg.locator('#st-fac [data-filter=pending]').getAttribute('aria-pressed')) === 'true');
// make org usable: direct + reg no for all, dept
if (await pg.locator('#st-fac [data-filter="all"]').count()) { await pg.click('#st-fac [data-filter="all"]'); await pg.waitForTimeout(200); } await pg.click('#st-fac [data-sel-all]'); await pg.selectOption('#st-fac [data-bk=run]', 'direct'); await pg.fill('#st-fac [data-bk=reg_no]', '505-83-00001'); await pg.click('#st-fac [data-bulk=sel]'); await pg.waitForTimeout(300); await pg.click('.step[data-step="3"] [data-next]'); await pg.waitForTimeout(200); await pg.click('.step[data-step="4"] [data-next]'); await pg.waitForTimeout(400);
// W3 monthly paste 60 rows with facility names, no map
const FAC = (await pg.evaluate(() => JSON.parse(localStorage.getItem('vat-org-v1')).facilities.slice(0, 10).map(f => f.name.replace(/\(.*$/, '').trim())));   // 기관 설정의 시설 이름 10개(사업명에 들어감)
const rows = ['작성일자\t공급자상호\t품목\t공급가액\t세액\t공급받는자등록번호\t사업명\t부서']; for (let i = 0; i < 60; i++) { const f = FAC[i % FAC.length]; const kind = i % 6; const [item, amt] = kind === 0 ? [`${f} 전기요금`, 1200000] : kind === 1 ? [`${f} 청소용역`, 800000] : kind === 2 ? ['군 청사 복사용지', 150000] : kind === 3 ? [`${f} 승강기 수선`, 3000000] : kind === 4 ? ['직원 체육대회 기념품', 400000] : [`${f} 보험료`, 500000]; rows.push(`2026-01-${String((i % 28) + 1).padStart(2, '0')}\t업체${i}\t${item}\t${amt.toLocaleString()}\t${(amt / 10).toLocaleString()}\t${i % 11 === 0 ? '999-82-00000' : '505-83-00001'}\t${f} 운영\t재무과`); }
await pg.goto(base + '/vat/monthly/'); await pg.waitForTimeout(600); await pg.selectOption('#m-fac', { index: 1 }); await pg.fill('#m-month', '2026-01'); await pg.waitForTimeout(200);
ok('W3 붙여넣기 상자에 출처 ? 2개', await pg.locator('#mb-wrap button.help.src').count() === 2);
await pg.evaluate(() => { document.getElementById('mb-wrap').open = true; }); await pg.fill('#mb-text', rows.join('\n')); await pg.click('#mb-form button[type=submit]'); await pg.waitForTimeout(900);
const named = await pg.locator('#mb-table tbody tr .vbadge', { hasText: '이름 일치' }).count(); ok('W3 이름 일치 ≥ 50 / 60', named >= 50, String(named));
ok('W3 머리에 시설별 집계', /시설별:/.test(T(await pg.locator('#mb-facsum').textContent())));
ok('W3 칩 수선·장비 10', T(await pg.locator('#mb-preview [data-view=asset]').textContent()).replace(/\s/g, '') === '수선·장비10');
await pg.click('#mb-preview [data-view=asset]'); await pg.waitForTimeout(200); ok('W3 수선·장비 보기 → 10행', await pg.locator('#mb-table tbody tr:not([hidden])').count() === 10);
await pg.click('#mb-preview [data-view=all]'); await pg.waitForTimeout(200);
// W4 add → end-of-month card
await pg.click('#mb-add'); await pg.waitForTimeout(900);
const card = pg.locator('#mb-preview .mb-done'); ok('W4 이번 달 끝 카드: 시설별 표·신호등 5칸·다음 할 일', await card.count() === 1 && (await card.locator('tbody tr').count()) >= 2 && (await card.locator('.fsum span').count()) >= 5 && /다음 할 일/.test(T(await card.textContent())));
// W5 prepare: nolog bulk → no missing in todo
await pg.goto(base + '/vat/prepare/'); await pg.waitForTimeout(700); await pg.selectOption('#p-period', '2026-1P'); await pg.waitForTimeout(300);
const blankBefore = T(await pg.locator('#p-coverage').textContent()); ok('W5 빈 칸 수와 일괄 단추', /빈 칸 \d+개/.test(blankBefore) && await pg.locator('#p-nolog-all').count() === 1);
await pg.click('#p-nolog-all'); await pg.waitForTimeout(300); await pg.locator('dialog[open] button').filter({ hasText: '모두 표시' }).click(); await pg.waitForTimeout(500);
ok('W5 일괄 뒤 빈 칸 0', /빈 칸 0개/.test(T(await pg.locator('#p-coverage').textContent())));
await pg.click('.pstep[data-pstep="1"] [data-pnext]'); await pg.waitForTimeout(300);
// W6 sales paste
ok('W6 매출 붙여넣기 상자 + 출처 ?', await pg.locator('#p-sales-paste').count() === 1 && await pg.locator('#p-sales-paste button.help.src').count() === 1);
await pg.evaluate(() => { document.getElementById('p-sales-paste').open = true; });
const names = await pg.locator('#p-sales [data-fid] .q-title').allTextContents(); const pick = names.slice(0, 3).map(t => t.split(' ')[0]);
await pg.fill('#p-sales-text', ['시설\t세금계산서\t카드\t기타', ...pick.map((n, i) => `${n}\t0\t${(i + 1) * 1000000}\t0`), '없는시설이름\t0\t5\t0'].join('\n')); await pg.click('#p-sales-apply'); await pg.waitForTimeout(300);
const msg = T(await pg.locator('#p-sales-paste-msg').textContent()); ok('W6 3곳 채움 + 못 찾은 이름 1', /3곳을 채웠습니다/.test(msg) && /못 찾은 이름 1/.test(msg), msg);
ok('W6 (3) 칸 채워짐', (await pg.locator('#p-sales [data-fid] input[data-c=c3]').first().inputValue()) === '1,000,000');
await pg.click('.pstep[data-pstep="2"] [data-pnext]'); await pg.waitForTimeout(300); ok('W6 면세 공급가액 출처 ?', await pg.locator('#p-groups button.help.src').count() >= 1);
const g = pg.locator('#p-groups [data-g]').first(); await g.locator('input[data-ex]').fill('30,000,000'); await g.locator('input[data-ex]').dispatchEvent('change'); await pg.click('#p-run'); await pg.waitForTimeout(1200);
const todo = T(await pg.locator('#p-todo').textContent()); ok('W5 처리할 것에 기록 없는 시설·달 없음', !/기록 없는 시설·달/.test(todo), todo.slice(0, 120));
await pg.click('#p-save'); await pg.waitForTimeout(300);
// W7 review
await pg.goto(base + '/vat/review/'); await pg.waitForTimeout(700);
ok('W7 사업장별 org: 등록번호 선택 상자', await pg.locator('#rv-reg-sel').count() === 1 && (await pg.locator('#rv-reg').inputValue()) === '505-83-00001');
ok('W7 출처 ? 3개', await pg.locator('#rv-form button.help.src').count() === 3);
const rv = ['작성일자\t공급자등록번호\t공급자상호\t품목\t공급가액\t세액\t공급받는자등록번호']; for (let i = 0; i < 30; i++) rv.push(`2024-0${(i % 6) + 1}-1${i % 9}\t111-11-1111${i % 9}\t업체${i}\t체육관 전기\t${(500000 + i * 1000).toLocaleString()}\t${(50000 + i * 100).toLocaleString()}\t505-83-00001`);
await pg.click('[data-rvsrc="paste"]'); await pg.fill('#rv-a', rv.join('\n')); await pg.click('#rv-form button[type=submit]'); await pg.waitForTimeout(400); await pg.click('#rv-build'); await pg.waitForTimeout(600);
ok('W7 신고 값 표 + 공급자별 귀속 표', await pg.locator('#rv-filed').count() === 1 && (await pg.locator('#rv-sup tbody tr[data-sk]').count()) >= 9, String(await pg.locator('#rv-sup tbody tr[data-sk]').count()));
const [dl] = await Promise.all([pg.waitForEvent('download'), pg.click('#rv-zip')]); const zp = path.join(os.tmpdir(), 'vat-rv.zip'); await dl.saveAs(zp); const list = execSync(`unzip -Z1 "${zp}"`).toString().trim().split('\n'); ok('W7 붙임 zip 6파일 이상(근거·질의서 포함)', list.length >= 7, list.join('|'));
// W8 handover
await pg.goto(base + '/vat/handover/'); await pg.waitForTimeout(800); const doc = T(await pg.locator('#h-doc').textContent());
const todoLines = (doc.match(/다음 신고까지 할 일/) ? doc.split('4. 다음 신고까지 할 일')[1]?.split('5. 파일')[0] ?? '' : '').split(' - ').length - 1; ok('W8 README 다음 신고까지 할 일 ≥ 3줄', /다음 신고까지 할 일/.test(doc) && todoLines >= 3, String(todoLines));
const [dz] = await Promise.all([pg.waitForEvent('download'), pg.click('#h-zip')]); const hz = path.join(os.tmpdir(), 'vat-h.zip'); await dz.saveAs(hz); ok('W8 zip 에 nolog.json', execSync(`unzip -Z1 "${hz}"`).toString().includes('nolog.json'));
const ctx2 = await browser.newContext({ viewport: { width: 1366, height: 768 } }); const p2 = await ctx2.newPage(); await p2.goto(base + '/vat/handover/'); await p2.setInputFiles('#h-open', hz); await p2.waitForTimeout(1200);
ok('W8 복원 뒤 이제 할 일 단추 + nolog 복원', await p2.locator('#h-next').count() === 1 && Object.keys(await p2.evaluate(() => JSON.parse(localStorage.getItem('vat-nolog-v1') || '{}'))).length > 0);
await p2.goto(base + '/vat/'); await p2.waitForTimeout(800); ok('W8 후임자 대시보드 이번 주 할 일', await p2.locator('#vat-week li').count() >= 1);
}

/* ── N1~N4 (2차 다음 후보, 2026-11-03): 등록번호 붙여넣기 · 홈택스 입력 순서 첫 탭 · 홈택스 엑셀 머리글 · 대리인 꾸러미 기한 ── */
{
// ① 등록번호 붙여넣기 (site unit org from quick start)
await pg.goto(base + '/vat/'); await pg.evaluate(() => localStorage.clear()); await pg.reload(); await pg.waitForFunction(() => document.querySelector('#d-qs [data-qs-sel]')?.options.length > 3, null, { timeout: 10000 }); await pg.click('#d-qs [data-qs-go]'); await pg.waitForTimeout(1200);
await pg.goto(base + '/vat/setup/?step=3'); await pg.waitForTimeout(900); const names = await pg.evaluate(() => JSON.parse(localStorage.getItem('vat-org-v1')).facilities.slice(0, 3).map(f => f.name));
await pg.evaluate(() => { document.getElementById('st-reg-paste').open = true; }); await pg.fill('#st-reg-text', [`${names[0]}\t5058300001`, `${names[1]}\t505-83-00002`, `없는시설\t505-83-00009`].join('\n')); await pg.click('#st-reg-apply'); await pg.waitForTimeout(400);
const o = await pg.evaluate(() => JSON.parse(localStorage.getItem('vat-org-v1'))); ok('① 등록번호 2곳 채움(하이픈 정규화) + 못 찾은 이름 1', o.facilities[0].reg_no === '505-83-00001' && o.facilities[1].reg_no === '505-83-00002' && /못 찾은 이름 1/.test(T(await pg.locator('#st-reg-msg').textContent())));
// ② 직접 신고: 홈택스 입력 순서 탭이 첫 탭 / 대리인: 신고서 첫 탭
const ORG2 = { v: 1, org: '테스트군', dept: '세무과', unit: 'site', facilities: [{ id: 'fA', type: 'sports', name: '체육센터', run: 'direct', reg_no: '123-45-67890', income: ['card'], deposit: false }, { id: 'fB', type: 'culture', name: '박물관', run: 'direct', reg_no: '123-45-67890', income: ['card'], deposit: false }, { id: 'fC', type: 'lease', name: '상가 임대', run: 'entrusted_org', reg_no: '222-22-22222', income: ['invoice'], deposit: true }], handover_day: 5, created: '2026-10-27', kind: 'gov' };
const org = JSON.parse(JSON.stringify(ORG2)); org.unit = 'entity'; org.reg_no = '555-83-00001'; org.facilities.forEach(f => { delete f.reg_no; }); org.facilities[2].run = 'direct';
const run = async (filing) => { org.filing = filing; await pg.goto(base + '/vat/prepare/'); await pg.evaluate(o => { localStorage.clear(); localStorage.setItem('vat-org-v1', JSON.stringify(o)); }, org); await pg.reload(); await pg.waitForTimeout(500); await pg.selectOption('#p-period', '2026-2P'); await pg.click('.pstep[data-pstep="1"] [data-pnext]'); await pg.click('.pstep[data-pstep="2"] [data-pnext]'); await pg.waitForTimeout(100); await pg.click('#p-run'); await pg.waitForTimeout(900); return [await pg.locator('.tabs [role=tab]').first().textContent(), await pg.locator('section.ftab:not([hidden])').getAttribute('data-tab')]; };
const [t1, p1] = await run('self'); ok('② 직접 신고: 첫 탭 = 홈택스 입력 순서', /홈택스 입력 순서/.test(t1) && p1 === 'order', t1);
const [t2, p2] = await run('agent'); ok('② 대리인 의뢰: 첫 탭 = 신고서', /신고서/.test(t2) && p2 === 'form', t2);
// ③ 홈택스 머리글 사전(전자세금계산서 목록·사업용 카드 매입)
const hx = ['작성일자', '발급일자', '전송일자', '승인번호', '공급자사업자등록번호', '공급자상호', '공급자대표자명', '공급받는자사업자등록번호', '공급받는자상호', '합계금액', '공급가액', '세액', '전자세금계산서분류', '품목명'];
const cd = ['거래일자', '카드번호', '공급자사업자번호', '공급자상호', '합계금액', '공급가액', '부가세', '봉사료', '거래구분', '공제여부'];
await pg.goto(base + '/vat/monthly/'); await pg.waitForTimeout(600); await pg.selectOption('#m-fac', 'fA'); await pg.fill('#m-month', '2026-08'); await pg.evaluate(() => { document.getElementById('mb-wrap').open = true; });
await pg.fill('#mb-text', [hx.join('\t'), ['2026-08-03', '2026-08-03', '2026-08-04', 'A1', '111-11-11111', '가전력', '홍길동', '555-83-00001', '시험군', '1,100,000', '1,000,000', '100,000', '일반', '전기요금'].join('\t')].join('\n')); await pg.click('#mb-form button[type=submit]'); await pg.waitForTimeout(600);
const map1 = await pg.evaluate(() => Object.fromEntries([...document.querySelectorAll('#mb-table select.colsel')].map(s => [s.dataset.col, s.selectedOptions[0]?.textContent])));
ok('③ 전자세금계산서 목록 머리글: 날짜=작성일자·공급자=공급자상호·받는자=공급받는자사업자등록번호·금액·세액·품목', /작성일자/.test(map1.date) && /공급자상호$/.test(map1.supplier) && /공급받는자사업자등록번호/.test(map1.payee_reg) && /공급자사업자등록번호/.test(map1.supplier_reg) && /공급가액$/.test(map1.amt) && /세액$/.test(map1.tax) && /품목명/.test(map1.desc), JSON.stringify(map1));
ok('③ 행 판정: 우리 명의 전자세금계산서 → 공제', (await pg.locator('#mb-table tbody tr').first().getAttribute('class') || '').includes('v-ok'));
await pg.fill('#mb-text', [cd.join('\t'), ['2026-08-05', '1234-****', '222-22-22222', '마트', '55,000', '50,000', '5,000', '0', '승인', '공제'].join('\t')].join('\n')); await pg.check('input[name=mb-proof][value=card]'); await pg.click('#mb-form button[type=submit]'); await pg.waitForTimeout(600);
const map2 = await pg.evaluate(() => Object.fromEntries([...document.querySelectorAll('#mb-table select.colsel')].map(s => [s.dataset.col, s.selectedOptions[0]?.textContent])));
ok('③ 카드 매입 머리글: 날짜=거래일자·공급자=공급자상호·등록번호=공급자사업자번호·세액=부가세', /거래일자/.test(map2.date) && /공급자상호$/.test(map2.supplier) && /공급자사업자번호/.test(map2.supplier_reg) && /부가세/.test(map2.tax) && /공급가액$/.test(map2.amt), JSON.stringify(map2));
// ④ 대리인 의뢰 이번 주 할 일
org.filing = 'agent'; org.agent_org = '○○세무법인'; org.agent_days = 60; await pg.goto(base + '/vat/'); await pg.evaluate(o => { localStorage.clear(); localStorage.setItem('vat-org-v1', JSON.stringify(o)); }, org); await pg.reload(); await pg.waitForTimeout(800);
const wk = T(await pg.locator('#vat-week').textContent()); const days = Number((wk.match(/D-(\d+)\(신고기한 60일 전/) || [])[1]);
ok('④ 대리인 꾸러미 넘기기 항목(D-day = 신고 D-day − 60)', /세무대리인\(○○세무법인\)에게 인계 꾸러미 넘기기/.test(wk) && Number.isFinite(days), wk.slice(0, 160));
}
// H. 실제 홈택스 엑셀 배치로 붙여넣기(2026-11-03 운영자 '실제 홈텍스 엑셀 붙여서 테스트 해봐' — 고정 자료 scripts/fixtures/hometax/README.md)
{
  const FX = path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax'); const fx = f => fs.readFileSync(path.join(FX, f), 'utf8');
  const orgH = JSON.parse(JSON.stringify(ORG)); orgH.unit = 'entity'; orgH.reg_no = '555-83-00001'; orgH.facilities.forEach(f => { delete f.reg_no; });
  const pasteH = async (file, proof) => { await pg.goto(base + '/vat/monthly/'); await pg.evaluate(o => { localStorage.clear(); localStorage.setItem('vat-org-v1', JSON.stringify(o)); }, orgH); await pg.goto(base + '/vat/monthly/?fac=fA&month=2026-08&open=1'); await pg.waitForSelector('#mb-text', { state: 'visible' }); await pg.check(`input[name=mb-proof][value=${proof}]`); await pg.fill('#mb-text', fx(file)); await pg.evaluate(() => document.getElementById('mb-form').requestSubmit()); await pg.waitForTimeout(400);
    const map = await pg.evaluate(() => Object.fromEntries([...document.querySelectorAll('#mb-table select.colsel')].map(s => [s.dataset.col, s.selectedOptions[0]?.textContent.split('← ')[1] ?? ''])));
    const rows = await pg.evaluate(() => [...document.querySelectorAll('#mb-table tbody tr')].map(tr => ({ date: tr.children[1].textContent, desc: tr.children[2].textContent.trim(), amt: tr.children[5].textContent, tax: tr.children[6].textContent, payee: tr.children[7].textContent.trim(), on: tr.querySelector('[data-on]').checked, flags: [...tr.querySelectorAll('td:nth-child(3) .verdict')].map(e => e.textContent) })));
    return { map, rows }; };
  const F = await pasteH('pc_invoice_list.tsv', 'e_invoice');
  ok('H1 PC 매입 목록조회(조회조건·총계·제목 5줄 뒤 6행 머리글): 12행·작성일자 20260801→2026-08-01·상호(첫)·등록번호 둘·품목명·분류', F.rows.length === 12 && F.map.date === '작성일자' && F.map.supplier === '상호' && F.map.supplier_reg === '공급자사업자등록번호' && F.map.payee_reg === '공급받는자사업자등록번호' && F.map.desc === '품목명' && F.map.kind === '전자세금계산서 분류' && F.rows[0].date === '2026-08-01', `${F.rows.length}행 ${JSON.stringify(F.map)}`);
  ok('H2 하이픈 없는 공급받는자 번호(5558300001)도 우리 기관, 쉼표 금액, 계산서(면세) 행만 체크 해제', F.rows.every(r => r.payee === '우리 기관') && F.rows[0].amt === '1,000,000' && F.rows[0].tax === '100,000' && F.rows[5].flags.some(f => /계산서\(면세 매입\)/.test(f)) && F.rows.filter(r => !r.on).length === 1 && F.rows[0].desc === '가전력 · 전기요금', JSON.stringify([F.rows[0], F.rows[5].flags]));
  const F2 = await pasteH('invoice_list_2row.tsv', 'e_invoice');
  ok('H3 옛 2단 머리글([공급자]·[공급받는자] 걸침 + 탭 없는 제목 줄): 12행·공급자등록번호·공급받는자등록번호·공급자상호', F2.rows.length === 12 && F2.map.supplier_reg === '공급자등록번호' && F2.map.payee_reg === '공급받는자등록번호' && F2.map.supplier === '공급자상호' && F2.rows.every(r => r.payee === '우리 기관'), `${F2.rows.length}행 ${JSON.stringify(F2.map)}`);
  const G = await pasteH('pc_card_list.tsv', 'card');
  ok('H4 PC 사업용신용카드(총 사용금액 줄 + 줄바꿈 든 머리글): 12행·승인일자·가맹점명·"가맹점 사업자번호"·공제여부 결정', G.rows.length === 12 && G.map.date === '승인일자' && G.map.supplier === '가맹점명' && G.map.supplier_reg === '가맹점 사업자번호' && G.map.amt === '공급가액' && G.map.tax === '세액' && G.map.total === '합계' && G.map.deduct === '공제여부 결정', `${G.rows.length}행 ${JSON.stringify(G.map)}`);
  ok('H5 홈택스 불공제(간이·선택불공제) 2행 표시·체크 해제, 10행 체크', G.rows[1].flags.some(f => /불공제\(간이\)/.test(f)) && !G.rows[1].on && G.rows[2].flags.some(f => /불공제\(선택불공제\)/.test(f)) && !G.rows[2].on && G.rows.filter(r => r.on).length === 10, JSON.stringify(G.rows.map(r => [r.on, r.flags])));
  const H = await pasteH('old_card_list.tsv', 'card');
  ok('H6 옛 카드 건별내역(승인일자 엑셀 일련번호 46235·거래처사업자번호·부가세공제여부): 6행·2026-08-01·세액 열', H.rows.length === 6 && H.rows[0].date === '2026-08-01' && H.map.supplier === '가맹점명' && H.map.supplier_reg === '거래처사업자번호' && H.map.tax === '세액' && H.map.deduct === '부가세공제여부' && H.rows.every(r => r.on), `${H.rows.length}행 ${H.rows[0]?.date} ${JSON.stringify(H.map)}`);
  const I = await pasteH('paper_invoice_ledger.tsv', 'e_invoice');
  ok('H7 종이세금계산서 장부(제목 줄 + 거래처·등록번호·날짜·적요·공급가액·부가세): 5행', I.rows.length === 5 && I.map.supplier === '거래처' && I.map.supplier_reg === '등록번호' && I.map.date === '날짜' && I.map.desc === '적요' && I.map.tax === '부가세' && I.rows[0].date === '2026-08-01', `${I.rows.length}행 ${JSON.stringify(I.map)}`);
  await pg.goto(base + '/vat/review/'); await pg.waitForSelector('#rv-a', { state: 'attached' }); await pg.click('[data-rvsrc="paste"]'); await pg.fill('#rv-a', fx('pc_invoice_list.tsv')); await pg.evaluate(() => document.getElementById('rv-form').requestSubmit()); await pg.waitForTimeout(400);
  const rvNote = T(await pg.locator('#rv-colA .q-title').textContent().catch(() => '')); const rvMap = await pg.evaluate(() => Object.fromEntries([...document.querySelectorAll('#rv-colA select[data-col]')].map(s => [s.dataset.col, s.selectedOptions[0]?.textContent ?? ''])));
  await pg.evaluate(() => localStorage.removeItem('vat-review-v1')); await pg.click('#rv-build'); await pg.waitForTimeout(500); const rvTbl = T(await pg.locator('#rv-result table').first().textContent().catch(() => ''));
  ok('H8 지난 신고 점검 A 에 시트 전체 붙여넣기: 제목 줄 버리고 12행·열 짐작·2026년 제2기 수취 매입세액 합계', /12행/.test(rvNote) && rvMap.date === '작성일자' && rvMap.supplier_reg === '공급자사업자등록번호' && /2026년 제2기/.test(rvTbl) && /12/.test(rvTbl), rvNote + ' ' + JSON.stringify(rvMap) + ' ' + rvTbl.slice(0, 120));
}

/* ── R 지난 돈 돌려받기 v2(핵심 기능, 2026-11-03): 건별 시설 귀속 → 있어야 할 공제 세액 − 신고 공제 세액 ── */
{
  const { execSync } = await import('node:child_process');
  const ORG_R = { v: 1, org: '시험군', dept: '재무과', unit: 'entity', reg_no: '555-83-00001', handover_day: 10, created: '2026-01-01', facilities: [{ id: 'f1', type: 'sports', name: '시험체육센터', run: 'direct', income: [], deposit: false }, { id: 'f2', type: 'culture', name: '시험도서관', run: 'direct', income: [], deposit: false }] };
  await pg.goto(base + '/vat/review/'); await pg.evaluate(o => { localStorage.clear(); localStorage.setItem('vat-org-v1', JSON.stringify(o)); }, ORG_R); await pg.reload(); await pg.waitForSelector('#rv-a', { state: 'attached' });
  ok('R0 등록번호 미리 채움', (await pg.locator('#rv-reg').inputValue()) === '555-83-00001');
  const rows = ['작성일자\t공급자등록번호\t공급자상호\t품목\t공급가액\t세액\t공급받는자등록번호',
    '2025-02-10\t111-11-11111\t한전\t시험체육센터 전기\t1,000,000\t100,000\t555-83-00001', '2025-03-10\t222-22-22222\t청소업체\t시험도서관 청소\t500,000\t50,000\t555-83-00001',
    '2025-04-10\t333-33-33333\t문구사\t군청 복사용지\t300,000\t30,000\t555-83-00001', '2025-08-10\t444-44-44444\t건설사\t시험체육센터 지붕 수선\t2,000,000\t200,000\t555-83-00001',
    '2025-09-10\t555-55-55555\t가게\t물품\t100,000\t10,000\t999-82-00000'];
  await pg.click('[data-rvsrc="paste"]'); await pg.fill('#rv-a', rows.join('\n')); await pg.evaluate(() => document.getElementById('rv-form').requestSubmit()); await pg.waitForTimeout(400); await pg.click('#rv-build'); await pg.waitForTimeout(600);
  const supRows = await pg.$$eval('#rv-sup tbody tr[data-sk]', trs => trs.map(t => ({ k: t.dataset.sk, cls: t.className, fid: t.querySelector('[data-sf-fid]').value, txt: t.textContent.replace(/\s+/g, ' ') })));
  const byK = Object.fromEntries(supRows.map(r => [r.k, r]));
  ok('R1 이름 일치 자동 귀속: 한전·건설사 → 체육센터(초록), 청소업체 → 도서관(빨강), 문구사 미지정(노랑)', byK['1111111111']?.fid === 'f1' && /v-ok/.test(byK['1111111111'].cls) && byK['4444444444']?.fid === 'f1' && byK['2222222222']?.fid === 'f2' && /v-no/.test(byK['2222222222'].cls) && byK['3333333333']?.fid === '' && /v-check/.test(byK['3333333333'].cls), JSON.stringify(supRows.map(r => [r.k, r.fid, r.cls])));
  ok('R1 다른 명의 1건 따로', /우리 명의가 아닌 세금계산서 1건/.test(T(await pg.locator('#rv-result').textContent())));
  ok('R7 신고 값 넣기 전 맨 위 카드: 지금 0 · 상한 300,000(한전 100,000 + 건설사 200,000, 문구사는 미지정)', T(await pg.locator('#rv-total').textContent()).startsWith('0') && T(await pg.locator('#rv-cap').textContent()).startsWith('300,000'), T(await pg.locator('#rv-money').textContent()).slice(0, 200));
  await pg.selectOption('[data-filed="2025-1"]', 'filed'); await pg.waitForTimeout(300); await pg.fill('[data-fin="deduct:2025-1"]', '20000'); await pg.press('[data-fin="deduct:2025-1"]', 'Tab'); await pg.waitForTimeout(300); await pg.fill('[data-fin="er:2025-1"]', '40'); await pg.press('[data-fin="er:2025-1"]', 'Tab'); await pg.waitForTimeout(300);
  await pg.selectOption('[data-filed="2025-2"]', 'none'); await pg.waitForTimeout(300);
  const perA = await pg.$$eval('#rv-per tbody tr', trs => trs.map(t => [...t.querySelectorAll('th,td')].map(c => c.textContent.replace(/\s+/g, ' ').trim())));
  ok('R2 문구사 미지정 상태: 2025-1 있어야 할 공제 100,000 · 신고 20,000 · 차이 80,000 · 못 센 세액 30,000', perA[0][2] === '100,000' && perA[0][3] === '20,000' && perA[0][4].startsWith('80,000') && perA[0][6] === '30,000', JSON.stringify(perA[0]));
  await pg.selectOption('[data-sf-fid="3333333333"]', 'admin'); await pg.waitForTimeout(500);
  const perB = await pg.$$eval('#rv-per tbody tr', trs => trs.map(t => [...t.querySelectorAll('th,td')].map(c => c.textContent.replace(/\s+/g, ' ').trim())));
  ok('R3 문구사 → 본청·행정 공통(면세비율 40%): 2025-1 118,000 − 20,000 = 98,000 · 못 센 0', perB[0][2] === '118,000' && perB[0][4].startsWith('98,000') && perB[0][6] === '0', JSON.stringify(perB[0]));
  ok('R3 2025-2 신고 없음 → 기한후신고 · 차이 200,000(건설사 수선, 다른 명의 제외)', perB[1][2] === '200,000' && perB[1][4].startsWith('200,000') && /기한후신고/.test(perB[1][7] + perB[1][8]), JSON.stringify(perB[1]));
  ok('R4 합계 카드 298,000 · 사유 초안에 금액', T(await pg.locator('#rv-total').textContent()).startsWith('298,000') && /298,000/.test(await pg.locator('#rv-reason').inputValue()));
  ok('R7 가산세 빼면 281,500(= 298,000 − 공급가액 3,300,000 × 0.5%)', T(await pg.locator('#rv-net').textContent()).startsWith('281,500'), T(await pg.locator('#rv-net').textContent()));
  await pg.selectOption('[data-filed="2025-1"]', 'excluded'); await pg.waitForTimeout(400); ok('R7 \'함 — 이 목록은 안 넣었음\' → 2025-1 전액 118,000, 합계 318,000', T(await pg.locator('#rv-total').textContent()).startsWith('318,000')); await pg.selectOption('[data-filed="2025-1"]', 'filed'); await pg.waitForTimeout(400); await pg.fill('[data-fin="deduct:2025-1"]', '20000'); await pg.press('[data-fin="deduct:2025-1"]', 'Tab'); await pg.waitForTimeout(400);
  const [dz] = await Promise.all([pg.waitForEvent('download'), pg.click('#rv-zip')]); const zr = path.join(os.tmpdir(), 'vat-rv2.zip'); await dz.saveAs(zr); const zl = execSync(`unzip -Z1 "${zr}"`).toString().trim().split('\n'); const det = execSync(`unzip -p "${zr}" 02_건별_명세.csv`).toString();
  const basisTxt = T(await pg.locator('#rv-basis').textContent()); const basisN = execSync(`unzip -p "${zr}" 06_근거_조문_유권해석_판례.txt`).toString();
  ok('R8 근거 절: 경정청구 조문(국세기본법 제45조의2·영 제74조) · 체육시설 기준·유권해석(부가가치세제과-186) · 본청·행정 공통(2017두55329)·질의서 초안 · 건별 조문', /제45조의2/.test(basisTxt) && /제74조/.test(basisTxt) && /체육시설/.test(basisTxt) && /186/.test(basisTxt) && /본청·행정 공통 안분/.test(basisTxt) && /2017두55329/.test(basisTxt) && (await pg.locator('#rv-basis details.inquiry[data-inq="admin_common"]').count()) === 1 && /건별 판정에 걸린 조문/.test(basisTxt), basisTxt.slice(0, 300));
  ok('R8 건별 표 근거 칸 · 사유 초안에 근거 · zip 14파일(13 돌려받을 돈 + 06 근거 + 07 질의서 + 08·09 자료별·순액 + 10 엑셀 + 11 PDF + 12 진단)', /법 제38조/.test(T(await pg.locator('#rv-sup .rv-rows').first().textContent())) && /\[근거 법령·유권해석\]/.test(await pg.locator('#rv-reason').inputValue()) && zl.length >= 14 && zl.includes("13_돌려받을_돈_무엇_왜_어떻게_얼마.csv") && zl.includes('12_지난신고_진단.csv') && zl.includes('10_경정청구_자료.xlsx') && zl.includes('11_경정청구_요약.pdf') && /체육시설/.test(basisN) && zl.some(z => /07_국세청_질의서_초안_1_admin_common/.test(z)), zl.join('|'));
  ok('R5 zip 건별 명세에 본청·행정 공통 18,000', /본청·행정 공통/.test(det) && /18000/.test(det), zl.join('|'));
  { const sk = await pg.$$eval('#rv-sup tbody tr[data-sk]', trs => trs.filter(t => Number((t.querySelectorAll('td')[8]?.textContent || '').replace(/[^0-9]/g, '').slice(0, -2) || (t.querySelectorAll('td')[8]?.textContent || '').replace(/[^0-9]/g, '')) > 0).map(t => t.dataset.sk));
    const tot0 = T(await pg.locator('#rv-total').textContent()); let tot1 = '', lab = '', tot2 = '';
    if (sk.length) { await pg.selectOption(`[data-sf-cw="${sk[0]}"]`, 'c_land'); await pg.waitForTimeout(400); tot1 = T(await pg.locator('#rv-total').textContent()); lab = T(await pg.locator(`tr[data-sk="${sk[0]}"]`).textContent());
      await pg.selectOption(`[data-sf-cw="${sk[0]}"]`, ''); await pg.waitForTimeout(400); tot2 = T(await pg.locator('#rv-total').textContent()); }
    ok('C2 ③ 공급자 표 공사라면 칸 · 부지 토목으로 고르면 청구 후보가 줄고 판정에 갈래 이름 · 되돌리면 원래 금액', (await pg.locator('#rv-cw-note').count()) === 1 && sk.length > 0 && tot1 !== tot0 && /부지 토목|토지 관련/.test(lab) && tot2 === tot0, [tot0, tot1, tot2].join(' / ')); }
  await pg.reload(); await pg.waitForTimeout(700); ok('R6 새로 고침 뒤 자료·귀속·신고 값 유지(5건, 298,000)', /5건/.test(T(await pg.locator('#rv-stat').textContent())) && T(await pg.locator('#rv-total').textContent()).startsWith('298,000'));
  await pg.evaluate(() => localStorage.removeItem('vat-review-v1'));
  /* R9 파일 놓기(xlsx) — 붙여넣기 없이. 세 걸음 판(2026-11-05): 머리글이 분명하면 '목록에 더하기' 없이 바로 들어간다 */
  await pg.reload(); await pg.waitForSelector('#rv-a', { state: 'attached' }); await pg.setInputFiles('#rv-drop-zone input[type=file]', path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax', 'invoice_list.xlsx')); await pg.waitForTimeout(800);
  ok('R9 xlsx 파일 놓기 → 바로 2건(엑셀 일련번호 날짜 45700 → 2025-02-12)', /2건/.test(T(await pg.locator('#rv-stat').textContent())) && (await pg.evaluate(() => JSON.parse(localStorage.getItem('vat-review-v1')).rows.map(r => r.d).sort().join(','))) === '2025-02-10,2025-02-12' && (await pg.evaluate(() => JSON.parse(localStorage.getItem('vat-review-v1')).rows.map(r => r.desc).sort().join(','))).length > 0);
  await pg.setInputFiles('#rv-drop-zone input[type=file]', path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax', 'invoice_list_euckr.csv')); await pg.waitForTimeout(800); ok('R9 EUC-KR CSV 파일 놓기: 2행 읽음(csv) → 공급자상호 열로 1건 더함', /2행 읽음\(csv\)/.test(T(await pg.locator('#rv-drop-zone .vat-drop-msg').textContent())) && (await pg.evaluate(() => JSON.parse(localStorage.getItem('vat-review-v1')).rows.length)) === 3, T(await pg.locator('#rv-stat').textContent()));
  await pg.evaluate(() => localStorage.removeItem('vat-review-v1'));
  /* R10 공개 지출 자료로 후보 찾기 — 달성군(받은 만큼, 금액은 식으로 견줌) */
  await pg.evaluate(o => localStorage.setItem('vat-org-v1', JSON.stringify(o)), { ...ORG_R, facilities: [...ORG_R.facilities, { id: 'f3', type: 'lodging', name: '비슬산 유스호스텔', run: 'direct', income: [], deposit: false }, { id: 'f4', type: 'lodging', name: '비슬산 자연휴양림', run: 'direct', income: [], deposit: false }] }); await pg.reload(); await pg.waitForSelector('#rv-a', { state: 'attached' });
  await pg.click('[data-rvsrc="pub"]'); await pg.waitForSelector('#pub-gov'); await pg.selectOption('#pub-gov', 'dalseong'); await pg.click('#pub-load'); await pg.waitForSelector('#pub-biz', { timeout: 15000 }); await pg.waitForTimeout(300);
  const pubRows = await pg.$$eval('#pub-biz tbody tr', trs => trs.map(t => ({ k: t.dataset.bk, fid: t.querySelector('[data-pb-fid]').value, badge: !!t.querySelector('.vbadge') })));
  ok('R10 공개 자료 불러오기: 세부사업 표 · 비슬산 유스호스텔 관리 → 이름 일치(미지정 표에서 빠짐) · 휴양림도로 확포장은 지명만 같은 도로 공사라 미지정에 남음', pubRows.length > 20 && !pubRows.some(r => /비슬산 유스호스텔 관리/.test(r.k)) && pubRows.some(r => /비슬산 휴양림도로/.test(r.k) && !r.fid), String(pubRows.length));
  await pg.click('[data-pf="done"]'); await pg.waitForTimeout(300); const doneRows = await pg.$$eval('#pub-biz tbody tr', trs => trs.map(t => ({ k: t.dataset.bk, fid: t.querySelector('[data-pb-fid]').value })));
  /* 자료가 늘어도(표본 → 3년 전체) 맞는 식으로 견준다: 숙박(과세) 직영 시설은 공제 대상 = 세액 추정, 카드 합계 = 과세기간 표의 공제 대상 합 */
  const perSum = async () => pg.$$eval('#pub-per tbody tr', trs => { const n = s => Number((s || '').replace(/[^0-9]/g, '')) || 0; let all = 0, f3e = 0, f3c = 0; for (const t of trs) { const td = t.querySelectorAll('td'); const c = n(td[4]?.textContent); all += c; if (/비슬산 유스호스텔/.test(td[0]?.textContent || '')) { f3e += n(td[3]?.textContent); f3c += c; } } return { all, f3e, f3c }; });
  const claimN = async () => Number(T(await pg.locator('#pub-claim').textContent()).replace(/[^0-9]/g, ''));
  const ps1 = await perSum(); const c1 = await claimN();
  ok('R10 지정됨 표에 비슬산 유스호스텔(f3·이름 일치) · 숙박 과세라 공제 대상 추정 = 세액 추정(10/110) · 카드 = 표 합계', doneRows.some(r => /비슬산 유스호스텔 관리/.test(r.k) && r.fid === 'f3') && !doneRows.some(r => /휴양림도로|참꽃/.test(r.k)) && ps1.f3e > 0 && ps1.f3c === ps1.f3e && c1 === ps1.all, c1 + ' ' + JSON.stringify(ps1));
  ok('R10 받아올 사업 목록 메모에 정책사업과·비슬산 유스호스텔 · CSV 단추', /정책사업과/.test(await pg.locator('#pub-memo').inputValue()) && /비슬산 유스호스텔 관리/.test(await pg.locator('#pub-memo').inputValue()) && (await pg.locator('#pub-csv').count()) === 1);
  await pg.click('[data-pf="todo"]'); await pg.waitForTimeout(300); await pg.selectOption('[data-pb-fid="회계과|달성군 여성문화복지센터 증축"]', 'f2'); await pg.waitForTimeout(400);
  const learned = await pg.evaluate(() => (JSON.parse(localStorage.getItem('vat-org-v1')).map || []).map(r => r.pat + '>' + r.fid).join(','));
  ok('R10 시설을 고르면 매핑표에 남음(달성군 여성문화복지센터 증축 → f2) · 면세 시설이라 추정 그대로', /여성문화복지센터 증축>f2/.test(learned) && (await claimN()) === c1, learned + ' ' + (await claimN()) + ' vs ' + c1);
  /* C3 유형 칸(2026-11-05): 유형 있는 사업 먼저, 유형으로 거르기 */
  { const hd = await pg.$$eval('#pub-biz thead th', ths => ths.map(t => t.textContent.trim()));
    const first = await pg.$$eval('#pub-biz tbody tr', trs => trs.slice(0, 5).map(t => t.querySelectorAll('td')[2]?.textContent.trim()));
    await pg.selectOption('#pub-type', 'road'); await pg.waitForTimeout(300);
    const rd = await pg.$$eval('#pub-biz tbody tr', trs => trs.map(t => [t.dataset.bk, t.querySelectorAll('td')[2]?.textContent.trim()]));
    await pg.selectOption('#pub-type', 'parking'); await pg.waitForTimeout(300);
    const pk = await pg.$$eval('#pub-biz tbody tr', trs => trs.map(t => t.querySelectorAll('td')[2]?.textContent.trim()));
    await pg.selectOption('#pub-type', ''); await pg.waitForTimeout(300);
    ok('C3 공개 지출 표에 유형 칸 · 공제 가능성 있는 유형이 먼저(도로·주차장·시장 보조는 뒤) · 도로 공사·공영주차장으로 거르기 · 유형 설명 펼침', hd.includes('유형') && first.every(x => x && x !== '—' && !/도로 공사|공영주차장|전통시장/.test(x)) && rd.length > 0 && rd.every(([, t]) => t === '시설 이름이 든 도로 공사') && rd.some(([k]) => /휴양림도로/.test(k)) && pk.length > 0 && pk.every(t => t === '공영주차장') && (await pg.locator('#pub-type-help').count()) === 1, JSON.stringify(first) + ' road ' + rd.length + ' park ' + pk.length); }
  /* C4 위탁·대행 사업비는 공제 대상 추정에 넣지 않고 '확인'으로(2026-11-05 운영자 '민간경상보조나 출연금은 부가세 세입이 아닐 것 같아') */
  { await pg.click('[data-pf="todo"]'); await pg.waitForTimeout(300);
    const wk = await pg.$$eval('#pub-biz tbody tr', trs => trs.filter(t => (t.querySelectorAll('td')[5]?.textContent || '—').trim() !== '—').map(t => t.dataset.bk));
    const c0 = Number(T(await pg.locator('#pub-claim').textContent()).replace(/[^0-9]/g, ''));
    if (wk.length) { await pg.selectOption(`[data-pb-fid="${wk[0]}"]`, 'f3'); await pg.waitForTimeout(400); }
    const c1 = Number(T(await pg.locator('#pub-claim').textContent()).replace(/[^0-9]/g, ''));
    const chk = await pg.$$eval('#pub-per tbody tr', trs => trs.filter(t => /비슬산 유스호스텔/.test(t.querySelectorAll('td')[0]?.textContent || '')).map(t => (t.querySelectorAll('td')[5]?.textContent || '').trim()));
    const bkTxt = wk.length ? await pg.locator(`tr[data-bk="${wk[0]}"]`).count() : 0;
    const note = T(await pg.locator('#pub-body').textContent());
    ok('C4 위탁·대행 통계목이 있는 사업을 과세 시설에 지정 → 위탁·대행(확인) 칸에 세액, 공제 대상 추정에는 그 몫이 안 더해짐 · 보조금·출연금 제외 안내', wk.length > 0 && chk.some(x => x && x !== '—') && /보조금\(민간경상·자본보조/.test(note) && /출연금/.test(note), `${wk[0]} c0=${c0} c1=${c1} chk=${chk.join(',')} rows=${bkTxt}`);
    if (wk.length) { await pg.click('[data-pf="all"]'); await pg.waitForTimeout(300); await pg.selectOption(`[data-pb-fid="${wk[0]}"]`, ''); await pg.waitForTimeout(300); await pg.click('[data-pf="todo"]'); await pg.waitForTimeout(300); } }
  /* C5 나라장터 계약(조달청) — 자료가 없으면 안내 한 줄, 있으면 표·업체 목록(2026-11-05) */
  { const none = await pg.locator('#pub-c-none').count(); const tbl = await pg.locator('#pub-ctr').count();
    let detail = 'none=' + none + ' tbl=' + tbl, okC = none === 1 || tbl === 1;
    if (tbl === 1) { const k = await pg.$eval('#pub-ctr tbody tr', t => t.dataset.ck); await pg.selectOption(`[data-pc-fid="${k}"]`, 'f3'); await pg.waitForTimeout(300); const memo = await pg.locator('#pub-cmemo').inputValue().catch(() => ''); const href = await pg.$eval('#pub-ctr tbody tr a', a => a.href).catch(() => ''); okC = /세금계산서 확인 요청/.test(memo) && /■ /.test(memo) && !/○○○|대표/.test(memo) && (!href || /^https:\/\/www\.g2b\.go\.kr\/link\/FIUA027_01\/single\/\?ctrtNo=/.test(href)); detail += ' href=' + href.slice(0, 80) + ' memo=' + memo.slice(0, 120); await pg.selectOption(`[data-pc-fid="${k}"]`, ''); await pg.waitForTimeout(200); }
    ok('C5 나라장터 계약: 자료 없으면 활용신청 안내, 있으면 계약 표 · 시설 고르면 업체별 세금계산서 찾기 메모', okC, detail); }
  /* R11 2024년 이후 — 지방재정365 세부사업별 연간 지출액(통계목 없음, 2021~2022 건별 비중을 빌림) */
  await pg.waitForSelector('#pub-lbiz', { timeout: 10000 });
  const lh = await pg.$$eval('#pub-lbiz thead th', ths => ths.map(t => t.textContent.trim()).join('|'));
  const ln = await pg.$$eval('#pub-lbiz tbody tr', trs => trs.length);
  ok('R11 지방재정365 표: 2024·2025 지출액 열 · 세부사업 줄 · 앞 표에서 고른 여성문화복지센터 증축은 같은 사업으로 이어짐(미지정에서 빠짐)', /2024 지출액/.test(lh) && /2025 지출액/.test(lh) && ln > 20 && !(await pg.$$eval('#pub-lbiz tbody tr', trs => trs.some(t => /여성문화복지센터 증축/.test(t.dataset.lk)))), lh + ' ' + ln);
  await pg.fill('#pub-lq', '휴양림'); await pg.press('#pub-lq', 'Enter'); await pg.dispatchEvent('#pub-lq', 'change'); await pg.waitForTimeout(300);
  const lk = await pg.$$eval('#pub-lbiz tbody tr', trs => trs.map(t => t.dataset.lk));
  const memoL = async () => (await pg.locator('#pub-lmemo').count()) ? await pg.locator('#pub-lmemo').inputValue() : '';
  const road = lk.find(k => /휴양림도로/.test(k)), plain = lk.find(k => /휴양림 정비/.test(k));
  if (road) { await pg.selectOption(`[data-pl-fid="${road}"]`, 'f3'); await pg.waitForTimeout(400); }
  if (plain) { await pg.selectOption(`[data-pl-fid="${plain}"]`, 'f3'); await pg.waitForTimeout(400); }
  await pg.click('[data-lf="all"]'); await pg.waitForTimeout(300);
  const m1 = await memoL(); const roadOpt = road ? await pg.locator(`[data-pl-cw="${road}"] option:checked`).textContent() : '';
  ok('R11 휴양림 사업을 비슬산(과세)에 지정 → 연도별 추정 표·받아올 사업 메모에 휴양림 정비 · 휴양림도로 확포장은 공공 도로로 짐작해 빠짐', !!road && !!plain && (await pg.locator('#pub-lper').count()) === 1 && m1.includes('- 휴양림 정비 (') && !m1.includes('휴양림도로') && /짐작: 공공 도로/.test(roadOpt || ''), JSON.stringify(lk.slice(0, 3)) + ' ' + roadOpt);
  /* C1 공사 다섯 갈래(2026-11-05): '공사 아님'으로 고치면 도로가 다시 들어오고, '면세 부분 전용'이면 빠짐 */
  if (road) { await pg.selectOption(`[data-pl-cw="${road}"]`, 'no'); await pg.waitForTimeout(400); }
  if (plain) { await pg.selectOption(`[data-pl-cw="${plain}"]`, 'c_exempt'); await pg.waitForTimeout(400); }
  const m2 = await memoL(); const opts = plain ? await pg.$$eval(`[data-pl-cw="${plain}"] option`, os => os.map(o => o.value).join(',')) : '';
  ok('C1 공사라면 칸 7가지(고르기·공사 아님·5갈래) · 도로를 공사 아님으로 → 메모에 다시 · 휴양림 정비를 면세 부분 전용으로 → 메모에서 빠짐', opts === ',no,c_tax,c_shared,c_exempt,c_land,c_road' && m2.includes('휴양림도로') && !m2.includes('- 휴양림 정비 (') && (await pg.locator('#pub-cw-note').count()) === 1, opts + ' note=' + (await pg.locator('#pub-cw-note').count()) + ' memo=' + m2.split('\n').filter(l => /휴양림/.test(l)).join(' | '));
  await pg.evaluate(() => { localStorage.removeItem('vat-pub-v1'); localStorage.removeItem('vat-rv-src'); });
}

/* ── U 지난 신고서 → 자료 → 돌려받을 금액(2026-11-04, docs/design/vat-refund-unlock.md) ── */
{
  const FXU = path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax');
  const ORG_U = { v: 1, org: '시험군', dept: '재무과', unit: 'entity', reg_no: '555-83-00001', handover_day: 10, created: '2026-01-01', facilities: [{ id: 'f1', type: 'sports', name: '시험체육센터', run: 'direct', income: [], deposit: false }] };
  await pg.goto(base + '/vat/review/'); await pg.evaluate(o => { localStorage.clear(); localStorage.setItem('vat-org-v1', JSON.stringify(o)); localStorage.setItem('vat-rv-src', 'paste'); }, ORG_U); await pg.reload(); await pg.waitForSelector('#rv-a', { state: 'attached' });
  const rowsU = ['작성일자\t공급자등록번호\t공급자상호\t품목\t공급가액\t세액\t공급받는자등록번호', '2024-08-05\t777-77-77777\t시공사\t시험체육센터 수선 1\t5,000,000\t500,000\t555-83-00001', '2024-09-05\t777-77-77777\t시공사\t시험체육센터 수선 2\t5,000,000\t500,000\t555-83-00001', '2024-10-05\t777-77-77777\t시공사\t시험체육센터 수선 3\t5,000,000\t500,000\t555-83-00001', '2020-03-05\t888-88-88888\t옛 업체\t시험체육센터 전기\t3,000,000\t300,000\t555-83-00001'];
  await pg.click('[data-rvsrc="paste"]'); await pg.fill('#rv-a', rowsU.join('\n')); await pg.evaluate(() => document.getElementById('rv-form').requestSubmit()); await pg.waitForTimeout(400); await pg.click('#rv-build'); await pg.waitForTimeout(600);
  await pg.setInputFiles('#rv-fd-file', [path.join(FXU, 'filed_2024_2.txt'), path.join(FXU, 'filed_2020_1.txt')]); await pg.waitForSelector('#rv-fd-tbl', { state: 'attached', timeout: 10000 }); await pg.waitForTimeout(500);
  ok('U1 신고서 2건 읽기 → ② 표: 2024년 제2기 신고 함 · (18) 1,000,000 · (17) 200,000 · 면세비율 30(⑭ 90,000 ÷ ⑪ 300,000)', (await pg.locator('[data-filed="2024-2"]').inputValue()) === 'filed' && (await pg.locator('[data-fin="deduct:2024-2"]').inputValue()) === '1,000,000' && (await pg.locator('[data-fin="nondeduct:2024-2"]').inputValue()) === '200,000' && (await pg.locator('[data-fin="er:2024-2"]').inputValue()) === '30', await pg.locator('#rv-fd-tbl').textContent());
  ok('U2 시설 자료가 없으면 지금 0 · 자료를 올리면 500,000(= 1,500,000 − 1,000,000) · 자료 표에 시험체육센터 자료 묶음', T(await pg.locator('#ul-now').textContent()).startsWith('0') && T(await pg.locator('#ul-docs').textContent()).startsWith('500,000') && /시험체육센터 자료 묶음/.test(T(await pg.locator('#ul-docs-tbl').textContent())), T(await pg.locator('#rv-unlock').textContent()).slice(0, 300));
  await pg.click('[data-have="fac:f1"]'); await pg.waitForTimeout(500);
  ok('U2 자료 있음 표시 → 지금 자료로 500,000 · 자료를 올리면 0', T(await pg.locator('#ul-now').textContent()).startsWith('500,000') && T(await pg.locator('#ul-docs').textContent()).startsWith('0'));
  ok('U3 신고서 과세 매출 0 → 매출 신고 확인 안내', /매출 신고를 확인하세요/.test(T(await pg.locator('#rv-unlock').textContent())));
  await pg.fill('[data-sales="2024-2"]', '1000000'); await pg.press('[data-sales="2024-2"]', 'Tab'); await pg.waitForTimeout(500);
  const rowU = await pg.$$eval('#ul-per tbody tr', trs => trs.map(t => [...t.querySelectorAll('th,td')].map(c => c.textContent.replace(/\s+/g, ' ').trim())));
  const r24 = rowU.find(r => /2024년 제2기/.test(r[0])); const salesCell = Number((r24?.[7] ?? '').replace(/[^\d]/g, '')); const netNow = Number(T(await pg.locator('#ul-net-now').textContent()).replace(/[^\d-]/g, ''));
  ok('U3 신고에 없던 매출 1,000,000 → 매출세액 100,000 + 가산세 · 순액 = 500,000 − (매출세액+가산세) − 합계표 가산세 25,000(5,000,000 × 0.5%)', salesCell > 100000 && salesCell < 200000 && netNow === 500000 - salesCell - 25000, JSON.stringify(r24) + ' net ' + netNow);
  const r20 = rowU.find(r => /2020년 제1기/.test(r[0]));
  ok('U4 2020년 제1기(기한 지남)는 세 칸에서 빠지고 따로 — 300,000 − 신고 100,000 = 200,000', /기한 지남/.test(r20?.[1] ?? '') && /기한이 지난 과세기간 몫 200,000원/.test(T(await pg.locator('#rv-unlock').textContent())) && T(await pg.locator('#ul-now').textContent()).startsWith('500,000'), JSON.stringify(r20));
  /* U5 2025-07-04 전 서식 신고서 — (16) 불공제·(17) 차감계를 현행 (17)(18)로(법령 연혁 대조 2026-11-05) */
  await pg.setInputFiles('#rv-fd-file', [path.join(FXU, 'filed_2022_2_old.txt')]); await pg.waitForTimeout(800);
  const old22 = await pg.$$eval('#rv-fd-tbl tbody tr', trs => trs.map(t => [...t.querySelectorAll('th,td')].map(c => c.textContent.replace(/\s+/g, ' ').trim())).find(r => /2022년 제2기/.test(r[0])));
  ok('U5 옛 서식(2022년 제2기) — 공제받은 매입세액 700,000 · 불공제 100,000 · 옮겨 읽었다는 안내', !!old22 && old22[4] === '700,000' && old22[5] === '100,000' && /2025-07-04 전 서식/.test(old22.join(' ')), JSON.stringify(old22));
  await pg.evaluate(() => { localStorage.removeItem('vat-review-v1'); localStorage.removeItem('vat-rv-src'); });
}
/* ── S 지난 돈 돌려받기 세 걸음 판(2026-11-05 docs/prompts/vat_refund_3steps.md): 기관 → 신고서 → 매입 목록 여러 파일, 계약 업체 번호로 저절로 귀속, 할 일·엑셀·PDF ── */
{
  const { execSync } = await import('node:child_process');
  const c3 = await browser.newContext({ viewport: { width: 1366, height: 768 }, acceptDownloads: true }); const p3 = await c3.newPage(); await c3.addInitScript(() => { if (location.pathname.startsWith('/vat/review')) document.addEventListener('DOMContentLoaded', () => { for (const id of ['rf-detail', 'rf-files']) { const d = document.getElementById(id); if (d) d.open = true; } }); });   /* 쉬운 화면(2026-11-05): 자세히·파일별은 접힘 — 이 시나리오는 펼친 채로 */ p3.on('pageerror', e => errs.push('S: ' + e));
  const CR = (no, k, nm, date, tot, corp, cno) => ({ k, no, nm, inst: '대구광역시 달성군', dept: '시험과', dmn: [], date, tot, amt: tot, mth: '수의계약', lng: '신규', cls: '', corps: [{ nm: corp, no: cno, sh: '100' }], url: '' });
  const CTR = { key: 'dalseong', name: '대구광역시 달성군', fetched: '2026-11-05', from: '2020-07', to: '2026-11', rows: [CR('T1', '공사', '시험체육센터 지붕 방수 공사', '2024-08-01', 22000000, '(주)가나건설', '1112233333'), CR('T2', '용역', '시험도서관 청소 용역', '2024-07-15', 11000000, '다라청소', '2223344444'), CR('T3', '물품', '시험체육센터 운동기구 구입', '2024-09-01', 5500000, '마바스포츠', '3334455555')] };
  await p3.route('**/vat-expense/index.json', async r => { const res = await r.fetch(); const j = await res.json(); const g = (j.govs ?? []).find(x => x.key === 'dalseong'); if (g) g.contracts = { from: '2020-07', to: '2026-11', rows: 3, fetched: '2026-11-05' }; await r.fulfill({ json: j }); });
  await p3.route('**/vat-expense/contracts-dalseong.json', r => r.fulfill({ json: CTR }));
  const ORG_S = { v: 1, org: '시험군', dept: '재무과', unit: 'entity', reg_no: '555-83-00001', handover_day: 10, created: '2026-01-01', facilities: [{ id: 'f1', type: 'sports', name: '시험체육센터', run: 'direct', income: [], deposit: false }, { id: 'f2', type: 'culture', name: '시험도서관', run: 'direct', income: [], deposit: false }] };
  let acts = 0;
  await p3.goto(base + '/vat/review/'); await p3.evaluate(o => { localStorage.clear(); localStorage.setItem('vat-org-v1', JSON.stringify(o)); localStorage.setItem('vat-gov', 'dalseong'); }, ORG_S); await p3.reload(); await p3.waitForSelector('#rf-sum', { state: 'attached' }); await p3.waitForTimeout(1200);
  const s1 = await p3.evaluate(() => ({ steps: document.querySelectorAll('.rf-step').length, more: document.getElementById('rf-more').open, other: document.getElementById('rf-other').open, st1: document.getElementById('rf-s1-st').textContent, b1: document.getElementById('rf-s1-body').textContent }));
  ok('S1 세 걸음 · 자세히 보기·다른 방법 접힘 · ① 기관 완료 · 계약 3건을 붙였다고', s1.steps === 3 && !s1.more && !s1.other && /완료/.test(s1.st1) && /나라장터 계약 3건/.test(s1.b1), JSON.stringify(s1).slice(0, 300));
  { const cm = await p3.$$eval('#rf-diag details.rf-dg', ds => ds.map(d => [d.querySelector('summary').textContent.replace(/\s+/g, ' '), d.querySelectorAll('.rf-cases li').length]));
    ok('S12 자료 올리기 전 — 다른 지자체가 실제로 틀린 곳(과세 시설 불공제·안분 안 함·세금계산서 누락·신고 누락·세입 처리)과 사례', cm.length >= 4 && cm.every(([, n]) => n >= 1) && cm.some(([t]) => /과세 시설 지출을 공제하지 않음/.test(t)), JSON.stringify(cm).slice(0, 300)); }
  acts++; await p3.setInputFiles('#rv-fd-file', [path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax', 'filed_2024_2.txt')]); await p3.waitForTimeout(800);
  const cmp = await p3.$$eval('#rf-cmp tbody tr', trs => trs.map(t => [t.dataset.pk, ...[...t.querySelectorAll('th,td')].map(c => c.textContent.replace(/\s+/g, ' ').trim())]));
  const c24 = cmp.find(r => r[0] === '2024-2');
  ok('S2 신고서 → 2024년 제2기 신고 매입세액 1,000,000 · 계약 세액 추정 2,500,000(체육센터 공사·물품) → 먼저 볼 기간 · 받을 기간 안내', !!c24 && c24[2] === '1,000,000' && c24[3] === '2,500,000' && /먼저 볼 기간/.test(c24[6]) && /2024년 제2기/.test(T(await p3.locator('#rf-pick').textContent())), JSON.stringify(c24));
  const fA = { name: '매입목록_2024_3분기.tsv', mimeType: 'text/tab-separated-values', buffer: Buffer.from(['작성일자\t공급자등록번호\t공급자상호\t품목\t공급가액\t세액\t공급받는자등록번호', '2024-08-20\t111-22-33333\t(주)가나건설\t방수공사 기성\t20,000,000\t2,000,000\t555-83-00001', '2024-09-03\t333-44-55555\t마바스포츠\t운동기구\t5,000,000\t500,000\t555-83-00001', '2024-09-05\t999-88-77777\t미상상사\t소모품\t100,000\t10,000\t555-83-00001'].join('\n')) };
  const fB = { name: '매입목록_2024_7월.csv', mimeType: 'text/csv', buffer: Buffer.from(['작성일자,공급자등록번호,공급자상호,품목,공급가액,세액,공급받는자등록번호', '2024-07-30,222-33-44444,다라청소,청소,"10,000,000","1,000,000",555-83-00001', '2024-07-31,120-81-47521,한국전력공사,시험체육센터 전기요금,"1,000,000","100,000",555-83-00001'].join('\n')) };
  acts++; await p3.setInputFiles('#rv-drop-zone input[type=file]', [fA, fB]); await p3.waitForTimeout(1500);
  const files = T(await p3.locator('#rv-files').textContent().catch(() => ''));
  ok('S3 매입 목록 파일 2개를 한꺼번에 → 바로 5건(목록에 더하기 없음)', /매입목록_2024_3분기\.tsv — 3건 더함/.test(files) && /매입목록_2024_7월\.csv — 2건 더함/.test(files) && (await p3.evaluate(() => JSON.parse(localStorage.getItem('vat-review-v1')).rows.length)) === 5, files);
  const st3 = T(await p3.locator('#rf-s3-st').textContent()); const vis = await p3.$$eval('#rv-sup-box #rv-sup tbody tr[data-sk]', trs => trs.map(t => t.dataset.sk));
  ok('S4 계약 업체 번호로 저절로 귀속 3곳(+시설 이름 1곳) · 사람이 고를 공급자 1곳(20%)만 표에', /계약 업체 번호 일치 3곳/.test(st3) && /남은 1곳/.test(st3) && vis.length === 1 && vis[0] === '9998877777', st3 + ' ' + vis.join(','));
  await p3.click('[data-sf="all"]'); await p3.waitForTimeout(400);
  const badge = await p3.$$eval('#rv-sup tbody tr[data-sk]', trs => Object.fromEntries(trs.map(t => [t.dataset.sk, [t.querySelector('[data-sf-fid]').value, t.querySelector('.vbadge')?.textContent ?? '']])));
  ok('S5 가나건설·마바스포츠 → 체육센터, 다라청소 → 도서관 (계약 업체 번호 일치 표시)', badge['1112233333']?.[0] === 'f1' && /계약 업체 번호 일치/.test(badge['1112233333']?.[1]) && badge['3334455555']?.[0] === 'f1' && badge['2223344444']?.[0] === 'f2', JSON.stringify(badge));
  const amt = Number(T(await p3.locator('#rf-amt').textContent()).replace(/[^\d]/g, '')); const tot = Number(T(await p3.locator('#rv-total').textContent()).replace(/[^\d]/g, ''));
  ok('S6 금액 띠 = 지금 계산된 금액(있어야 할 공제 2,600,000 − 신고 1,000,000 = 1,600,000) · 첫 금액까지 행동 ≤ 5', amt === tot && amt === 1600000 && acts <= 5, `띠 ${amt} 결과 ${tot} 행동 ${acts}`);
  const todo = await p3.$$eval('#rf-todo li', ls => ls.map(l => l.textContent.replace(/\s+/g, ' ').trim()));
  ok('S7 할 일 목록 — 금액 큰 순, 기한 D-day, 못 정한 공급자 1곳', todo.length >= 2 && todo.some(t => /D-\d+/.test(t)) && todo.some(t => /시설을 못 정한 공급자 1곳/.test(t)), todo.join(' / ').slice(0, 300));
  /* 2026-11-05 운영자 '어떤 항목을 어떻게 해야 되는지 이유는 나와야 공무원이 납득' — 할 일·계약 줄마다 왜·할 일·근거 조문 */
  const whyTodo = await p3.$$eval('#rf-todo .rf-todo > li', ls => ls.map(l => [!!l.querySelector('.rf-why'), /왜/.test(l.textContent), l.querySelectorAll('.rf-why a[href*="law.go.kr"]').length]));
  const whyCtr = await p3.$$eval('#rf-why .rf-why-list > li', ls => ls.map(l => [/왜/.test(l.textContent), /할 일/.test(l.textContent), /공급자/.test(l.textContent), l.querySelectorAll('.rf-why a[href*="law.go.kr"]').length]));
  ok('S10 할 일 줄마다 왜·근거 조문, 계약 줄마다 왜·할 일(공급자 번호로 찾기)·근거', whyTodo.length >= 2 && whyTodo.every(([b, w, n]) => b && w && n >= 1) && whyCtr.length >= 1 && whyCtr.every(([w, h, c, n]) => w && h && c && n >= 1), JSON.stringify({ whyTodo, whyCtr }).slice(0, 300));
  /* 2026-11-05 운영자 '과거 신고할 때 무엇이 잘못되었는지·어떻게 고치면·고친 내용과 효과' — 과세기간별 진단 카드 */
  const dg = await p3.$$eval('#rf-diag details.rf-dg', ds => ds.map(d => ({ id: d.id, open: d.open, sum: d.querySelector('summary').textContent.replace(/\s+/g, ' '), cells: [...d.querySelectorAll('table tbody tr')].map(tr => [...tr.children].map(c => c.textContent.replace(/\s+/g, ' ').trim())), items: [...d.querySelectorAll('.rf-dg-list > li')].map(li => [li.querySelector('.rf-dg-t').textContent.replace(/\s+/g, ' '), /무엇이/.test(li.textContent), /고치기/.test(li.textContent), li.querySelectorAll('a[href*="law.go.kr"]').length, li.querySelectorAll('.rf-cases li').length]) })));
  const d24 = dg.find(d => d.id === 'rf-dg-2024-2'); const r18 = d24?.cells.find(c => c[0] === '(18)');
  ok('S11 지난 신고 진단 — 2024년 제2기: 돌려받을 돈 1,600,000 · 고친 신고서 (18) 1,000,000 → 2,600,000 · 잘못된 항목마다 무엇이·고치기·근거', !!d24 && d24.open && /1,600,000원/.test(d24.sum) && r18?.[2] === '1,000,000' && r18?.[3] === '2,600,000' && d24.items.length >= 1 && d24.items.every(([, w, h, n]) => w && h && n >= 1) && d24.items.some(([t]) => /과세 시설 지출을 공제하지 않음|세금계산서가 신고에서 빠짐/.test(t)) && d24.items.some(([t, , , , c]) => /과세 시설 지출을 공제하지 않음|세금계산서가 신고에서 빠짐/.test(t) && c >= 1), JSON.stringify(d24).slice(0, 400));
    const gate = await p3.evaluate(() => [...document.querySelectorAll('#rf-dg-2024-2 .rf-gate tbody tr')].map(tr => tr.textContent.replace(/\s+/g, ' ')));
    const inp = await p3.evaluate(() => document.querySelector('#rf-dg-2024-2 .rf-dg-how')?.textContent ?? '');
    ok('S15b 대조 관문(목록 ↔ 신고서 (10)+(12)·(16)−(17)=(18)·불공제 명세 합) · 홈택스 경정청구 입력값(당초→경정 후·출처·사유·붙임)', gate.length >= 3 && gate.some(t => /세금계산서/.test(t) && /목록이 많음/.test(t)) && gate.some(t => /칸 계산/.test(t) && /맞음/.test(t)) && /경정청구/.test(inp) && /사유/.test(inp) && /붙임/.test(inp), JSON.stringify({ gate, inp: inp.slice(0, 120) }));
  if (process.env.VAT_SHOT) { await p3.$eval('#rf-diag-wrap', e => e.scrollIntoView()); await p3.screenshot({ path: process.env.VAT_SHOT }); }
  /* 2026-11-05 운영자 '과거 국세청에 신고한 자료를 올리면 바로 계산되고 이유가 나와야' — 매입 목록 없이 신고서만 */
  { const c4 = await browser.newContext({ viewport: { width: 1366, height: 768 } }); const p4 = await c4.newPage();
    await p4.goto(base + '/vat/review/'); await p4.evaluate(o => { localStorage.clear(); localStorage.setItem('vat-org-v1', JSON.stringify(o)); }, ORG_S); await p4.reload(); await p4.waitForSelector('#rf-sum', { state: 'attached' }); await p4.waitForTimeout(800);
    await p4.setInputFiles('#rv-fd-file', [path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax', 'filed_2023_1_err.txt')]); await p4.waitForTimeout(1000);
    const c = await p4.evaluate(() => { const d = document.getElementById('rf-dg-2023-1'); return { r18: [...(d?.querySelectorAll('table tbody tr') ?? [])].map(tr => [...tr.children].map(x => x.textContent.trim())).find(r => r[0] === '(18)'), amt: document.getElementById('rf-amt')?.textContent, sum: d?.querySelector('summary')?.textContent.replace(/\s+/g, ' '), items: [...(d?.querySelectorAll('.rf-dg-list > li') ?? [])].map(li => [li.querySelector('.rf-dg-t').textContent.replace(/\s+/g, ' '), /무엇이/.test(li.textContent) && /고치기/.test(li.textContent), li.querySelectorAll('a[href*="law.go.kr"]').length]) }; });
    ok('S13 신고서만 올려도 바로 — 2023년 제1기: 총공급가액에 과세 매출이 빠져 면세비율 부풀림 → 공통매입세액 더 불공제 62,500원(금액 띠, 고친 (18) 1,250,000 → 1,312,500), ⑤ 면세사업 관련 최대 500,000원 확인, 항목마다 이유·고치기·근거', c.amt === '62,500' && c.r18?.[2] === '1,250,000' && c.r18?.[3] === '1,312,500' && /62,500원/.test(c.sum ?? '') && /최대 \+500,000원/.test(c.sum ?? '') && c.items.some(([t]) => /공통매입세액을 더 불공제함 → 62,500원/.test(t)) && c.items.some(([t]) => /면세사업등 관련/.test(t)) && c.items.every(([, w, n]) => w && n >= 1), JSON.stringify(c).slice(0, 400));
    const cc = await p4.evaluate(() => ({ sure: document.getElementById('rf-calc-sure')?.textContent ?? '', upto: document.getElementById('rf-calc-upto')?.textContent ?? '', rows: [...document.querySelectorAll('#rf-calc tbody tr')].map(tr => [...tr.children].map(td => td.textContent.replace(/\s+/g, ' ').trim())) }));
    ok('S17 신고서만 올리면 돌려받을 돈 표 — 쉬운 말(무엇이 문제·할 일)·검토자용 근거 조문·얼마: 확정 62,500원, 확인하면 최대 500,000원', cc.sure === '62,500원' && cc.upto === '500,000원' && cc.rows.length >= 2 && /나누는 계산/.test(cc.rows[0][1]) && /홈택스 경정청구/.test(cc.rows[0][2]) && /공통매입세액/.test(cc.rows[0][3]) && /시행령 제81조/.test(cc.rows[0][3]) && /62,500원/.test(cc.rows[0][4]) && cc.rows.some(r => /최대 500,000원/.test(r[4])), JSON.stringify(cc).slice(0, 500));
    await c4.close(); }
  /* 2026-11-05 운영자 '홈택스 결과 자료를 넣으면 자동으로 계산되는 시스템' — 신고서·매입 목록·카드 파일을 섞어 한 곳에 */
  { const c5 = await browser.newContext({ viewport: { width: 1366, height: 768 } }); const p5 = await c5.newPage(); const FX = path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax');
    await p5.goto(base + '/vat/review/'); await p5.evaluate(o => { localStorage.clear(); localStorage.setItem('vat-org-v1', JSON.stringify(o)); }, ORG_S); await p5.reload(); await p5.waitForSelector('#rf-all-file', { state: 'attached' });
    await p5.setInputFiles('#rf-all-file', [path.join(FX, 'filed_2024_2.txt'), path.join(FX, 'filed_2023_1_err.txt'), path.join(FX, 'invoice_list.xlsx'), path.join(FX, 'pc_card_list.tsv')]); await p5.waitForTimeout(2500);
    const r = await p5.evaluate(() => ({ msg: document.getElementById('rf-all-msg')?.textContent ?? '', cards: [...document.querySelectorAll('#rf-diag details.rf-dg')].map(d => d.id), amt: document.getElementById('rf-amt')?.textContent ?? '', st3: document.getElementById('rf-s3-st')?.textContent ?? '' }));
    ok('S14 홈택스 파일 섞어 한 곳에 — 신고서 2건·매입 목록 1·카드 1을 가려 넣고 바로 진단(2023-1·2024-2 카드)·금액 띠', /신고서 2건/.test(r.msg) && /목록 1개/.test(r.msg) && /카드 1개/.test(r.msg) && r.cards.includes('rf-dg-2023-1') && r.cards.includes('rf-dg-2024-2') && Number(r.amt.replace(/[^\d]/g, '')) > 0, JSON.stringify(r).slice(0, 400));
    const g5 = await p5.evaluate(() => [...document.querySelectorAll('#rf-dg-2023-1 .rf-gate tbody tr')].map(tr => tr.textContent.replace(/\s+/g, ' ')));
    ok('S15a 신고서만 있는 기간 대조 — 매입 목록 없음 안내·칸 계산 맞음', g5.some(t => /매입 목록이 없음/.test(t)) && g5.some(t => /칸 계산/.test(t) && /맞음/.test(t)), JSON.stringify(g5).slice(0, 300));
    await c5.close(); }
  { const c6 = await browser.newContext({ viewport: { width: 1366, height: 768 } }); const p6 = await c6.newPage();
    await p6.goto(base + '/vat/review/'); await p6.evaluate(() => localStorage.clear()); await p6.reload(); await p6.waitForFunction(() => document.querySelector('[data-qs-sel]')?.options.length > 3, null, { timeout: 15000 }); await p6.click('[data-qs-go]');
    await p6.waitForSelector('#rf-ask h2', { timeout: 15000 }).catch(() => {});
    const q1 = await p6.evaluate(() => ({ head: document.querySelector('#rf-ask h2')?.textContent ?? '', auto: document.querySelector('#rf-ask-auto summary')?.textContent ?? '', vis: document.querySelectorAll('#rf-ask > .rf-q').length }));
    ok('S16a 확인 질문 최소화 — 기본값을 묻지 않고 적용, 보이는 질문 3개 이하(금액이 크게 갈리는 것만)', q1.vis <= 3 && (/확인 질문 [0-3]개/.test(q1.head) || /확인할 것 없음/.test(q1.head)) && /기본값으로 계산한 것 \d+개/.test(q1.auto), JSON.stringify(q1));
    await p6.evaluate(() => { document.getElementById('rf-ask-auto').open = true; document.querySelector('#rf-ask-auto [data-reask]').click(); }); await p6.waitForTimeout(300);
    const forcedQ = await p6.evaluate(() => document.querySelector('#rf-ask .rf-q [data-ans="0"]') ? document.querySelector('#rf-ask .rf-q-t')?.textContent ?? '' : '');
    if (forcedQ) { await p6.click('#rf-ask .rf-q [data-ans="0"]'); await p6.waitForLoadState('load'); await p6.waitForSelector('#rf-ask', { timeout: 15000 }); await p6.waitForTimeout(1500); }
    const q2 = await p6.evaluate(() => ({ answered: [...document.querySelectorAll('#rf-ask details summary')].map(s => s.textContent).join('|') }));
    ok('S16b 기본값 바꾸기 → 그 질문만 열림 → 답하면 저장·다시 계산', !!forcedQ && /답한 질문 1개/.test(q2.answered), JSON.stringify({ forcedQ, q2 }).slice(0, 400));
    await c6.close(); }
  const zr = path.join(os.tmpdir(), 'vat-s-bundle.zip'); const [dl] = await Promise.all([p3.waitForEvent('download', { timeout: 60000 }), p3.click('#rf-zip')]); await dl.saveAs(zr);
  const zl = execSync(`unzip -Z1 "${zr}"`).toString().trim().split('\n'); execSync(`cd "${os.tmpdir()}" && rm -rf vat-s-x && mkdir vat-s-x && cd vat-s-x && unzip -q "${zr}" && unzip -q -o 10_경정청구_자료.xlsx -d xl`);
  const wb = fs.readFileSync(path.join(os.tmpdir(), 'vat-s-x', 'xl', 'xl', 'workbook.xml'), 'utf8'); const pdfHead = fs.readFileSync(path.join(os.tmpdir(), 'vat-s-x', '11_경정청구_요약.pdf')).subarray(0, 5).toString();
  ok('S8 경정청구 묶음 — 엑셀(시트 11개: 돌려받을 돈·고친 신고서·홈택스 입력값·지난 신고 진단·과세기간별·건별·공급자별·시설별·자료별·사유·근거)과 PDF 둘 다', zl.includes('10_경정청구_자료.xlsx') && zl.includes('11_경정청구_요약.pdf') && (wb.match(/<sheet /g) ?? []).length === 11 && /홈택스 입력값/.test(wb) && /돌려받을 돈/.test(wb) && /고친 신고서/.test(wb) && /건별 명세/.test(wb) && pdfHead === '%PDF-', zl.join('|'));
  const [dx] = await Promise.all([p3.waitForEvent('download', { timeout: 30000 }), p3.evaluate(() => { const d = document.getElementById('rf-more'); d.open = true; document.getElementById('rv-xlsx').click(); })]);
  const xp = path.join(os.tmpdir(), 'vat-s-only.xlsx'); await dx.saveAs(xp); const xl = execSync(`unzip -Z1 "${xp}"`).toString();   /* 헤드리스는 한글 파일 이름을 'download' 로 돌려줘 내용으로 본다 */
  ok('S9 엑셀만 내려받기 → xlsx(workbook·시트)', /xl\/workbook\.xml/.test(xl) && /xl\/worksheets\/sheet11\.xml/.test(xl), dx.suggestedFilename());
  await c3.close();
}
/* 2026-11-05 운영자 '달성군은 과거 5년치 신고 자료만 올리면' — docs/prompts/vat_dalseong_5y_filings.md, 고정 자료 scripts/fixtures/hometax/dalseong5y(심은 오류는 make_dalseong5y.py 머리) */
{ const c7 = await browser.newContext({ viewport: { width: 1366, height: 900 }, acceptDownloads: true }); const p7 = await c7.newPage(); const FX5 = path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax', 'dalseong5y');
  await p7.goto(base + '/vat/review/'); await p7.evaluate(() => localStorage.clear());
  await p7.goto(base + '/vat/review/?gov=dalseong'); await p7.waitForSelector('#rf-all-file', { state: 'attached', timeout: 20000 }); await p7.waitForTimeout(1500);
  const g = await p7.evaluate(() => ({ org: JSON.parse(localStorage.getItem('vat-org-v1') || 'null')?.org ?? '', prof: document.querySelector('#rf-s1-body .rf-gov summary')?.textContent ?? '' }));
  ok('F1 링크 한 번으로 시작 — ?gov=dalseong 이면 기관 고르기 없이 달성군 설정·특성(공단·상태)', g.org === '대구광역시 달성군' && /달성군시설관리공단/.test(g.prof), JSON.stringify(g));
  await p7.setInputFiles('#rf-all-file', fs.readdirSync(FX5).sort().map(f => path.join(FX5, f))); await p7.waitForTimeout(3000);
  const r = await p7.evaluate(() => ({ cover: document.querySelector('#rf-cover summary')?.textContent ?? '', sure: document.getElementById('rf-calc-sure')?.textContent ?? '', upto: document.getElementById('rf-calc-upto')?.textContent ?? '', rows: [...document.querySelectorAll('#rf-calc tbody tr')].map(tr => [tr.children[0].textContent, tr.textContent, tr.children[4].textContent].map(x => x.replace(/\s+/g, ' '))), next: document.querySelector('.rf-next li')?.textContent ?? '' }));
  const has = (re, amt) => r.rows.some(x => re.test(x[1]) && (!amt || x[2].includes(amt)));
  ok('F2 5년 신고서 한 번에 — 대상 10개 과세기간 중 확정 9개(2022년 제2기 없음·2023년 제1기 수정신고 한 번만)', /대상 10개 과세기간 가운데 확정 신고서 9개/.test(r.cover) && has(/신고서를 올리지 않은/) && r.rows.some(x => /2022년 제2기/.test(x.join(' '))), JSON.stringify(r).slice(0, 600));
  ok('F3 심은 오류 — 확정 460,000원(안분 300,000·정산 ⑲ 100,000·예정분 정산 60,000), 확인하면 최대 5,200,000원(⑤ 2,000,000·주차장 매출 3,000,000·① 200,000), 재계산 누락 안내', r.sure === '460,000원' && r.upto === '5,200,000원' && has(/공통매입세액을 더 불공제/, '300,000원') && has(/정산을 더 불공제/, '100,000원') && has(/6개월 비율로 정산하지 않음/, '60,000원') && has(/주차장/, '3,000,000원') && has(/재계산 내역이 없음/), JSON.stringify(r).slice(0, 900));
  ok('F4 다음에 받으면 금액이 커지는 자료 — 첫째가 2025년 제1기 주차장 수입 세입 결의(최대 3,000,000원)', /2025년 제1기/.test(r.next) && /세입 결의/.test(r.next) && /3,000,000원/.test(r.next), r.next);
  const { execSync } = await import('node:child_process'); const zr = path.join(os.tmpdir(), 'vat-f5y.zip'); const [dl] = await Promise.all([p7.waitForEvent('download', { timeout: 60000 }), p7.click('#rf-dl-submit')]); await dl.saveAs(zr);
  const zl = execSync(`unzip -Z1 "${zr}"`).toString();
  const cr = await p7.evaluate(() => { const d = document.getElementById('rf-dg-2022-1'); if (d) d.open = true; return { rows: [...(d?.querySelectorAll('.rf-corr tr.rf-chg') ?? [])].map(tr => tr.textContent.replace(/\s+/g, ' ').trim()), claim: d?.querySelector('.rf-claim')?.textContent ?? '' }; });
  ok('F6 고친 신고서 — 2022년 제1기 확정: (17) 800,000 → 500,000, (18) 2,200,000 → 2,500,000, 명세서 ⑫ 50,000,000 → 80,000,000·⑭ 800,000 → 500,000, 경정청구 돌려받을 세액 300,000원', cr.rows.some(t => /\(17\).*800,000.*500,000/.test(t)) && cr.rows.some(t => /\(18\).*2,200,000.*2,500,000/.test(t)) && cr.rows.some(t => /⑫.*50,000,000.*80,000,000/.test(t)) && cr.rows.some(t => /⑭.*800,000.*500,000/.test(t)) && /돌려받을 세액 300,000원/.test(cr.claim), JSON.stringify(cr).slice(0, 600));
  ok('F5 묶음에 결재용 검토 보고(Word, 한글에서 열림)와 돌려받을 돈 표', /14_경정청구_검토보고/.test(zl) && /13_돌려받을_돈/.test(zl) && /15_고친_신고서/.test(zl), zl.split('\n').join('|'));
  await p7.goto(base + '/vat/review/'); await p7.evaluate(() => localStorage.clear()); await p7.reload(); await p7.waitForFunction(() => document.querySelector('[data-qs-sel]')?.options.length > 3, null, { timeout: 15000 });
  const opts = await p7.$$eval('[data-qs-sel] option', os => os.map(o => o.textContent.split(' — ')[0]).filter(Boolean));
  ok('G1 지자체 선택 — 대구광역시·9개 구·군 행정 순서', JSON.stringify(opts.slice(1, 11)) === JSON.stringify(['대구광역시', '대구광역시 중구', '대구광역시 동구', '대구광역시 서구', '대구광역시 남구', '대구광역시 북구', '대구광역시 수성구', '대구광역시 달서구', '대구광역시 달성군', '대구광역시 군위군']), JSON.stringify(opts));
  await p7.goto(base + '/vat/review/'); await p7.evaluate(() => localStorage.clear()); await p7.goto(base + '/vat/review/?gov=suseong'); await p7.waitForSelector('#rf-all-file', { state: 'attached', timeout: 20000 }); await p7.waitForTimeout(1500);
  const sg = await p7.evaluate(() => { const o = JSON.parse(localStorage.getItem('vat-org-v1') || 'null'); return { org: o?.org ?? '', n: o?.facilities?.length ?? 0, direct: (o?.facilities ?? []).filter(f => /반다비|국민체육센터/.test(f.name) && f.run === 'direct').length, prof: document.querySelector('#rf-s1-body .rf-gov')?.textContent ?? '' }; });
  ok('G2 수성구 — 링크로 시작, 예시 설정(직영 체육시설·재단 위탁), 특성(시설관리공단 없음)', sg.org === '대구광역시 수성구' && sg.n >= 32 && sg.direct >= 2 && /시설관리공단이 없습니다/.test(sg.prof), JSON.stringify(sg).slice(0, 300));
  await c7.close(); }
/* ── E 쉬운 화면(2026-11-05 docs/prompts/vat_review_ux_easiest.md · 설계 docs/design/vat-review-ux-spec.md): 과업 A~D·순서·잠금·한국어 파일 단추·결과 요약·내려받기 둘·빈/실패 상태·390px ── */
{ const FX5 = path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax', 'dalseong5y'); const { execSync } = await import('node:child_process');
  for (const vp of [{ width: 1366, height: 768 }, { width: 390, height: 844 }]) {
    const ce = await browser.newContext({ viewport: vp, acceptDownloads: true }); const pe = await ce.newPage(); pe.on('pageerror', e => errs.push('E: ' + e));
    await pe.goto(base + '/vat/review/'); await pe.evaluate(() => localStorage.clear()); await pe.reload(); await pe.waitForFunction(() => document.querySelector('[data-qs-sel]')?.options.length > 3, null, { timeout: 15000 });
    const e0 = await pe.evaluate(() => { const y = id => document.getElementById(id)?.getBoundingClientRect().top ?? -1; return { order: y('rf-s1') < y('rf-go2') && y('rf-go2') < y('rf-go3'), lock: !document.getElementById('rf-lock').hidden, dis: document.getElementById('rf-all-pick')?.disabled, pick: document.getElementById('rf-all-pick')?.textContent, eng: /Choose File|No file chosen/.test(document.body.innerText), chars: document.querySelector('main').innerText.replace(/\s+/g, ' ').length, empty: document.querySelector('#rf-sum .rf-empty')?.textContent ?? '' }; });
    ok(`E1 ${vp.width}px 첫 화면 — 순서 ① 기관 → ② 파일 → ③ 결과, 기관 전엔 파일 잠김, 한국어 「파일 고르기」, 영어 단추 없음, 글자 1,285 이하(before 2,569 의 절반)`, e0.order && e0.lock && e0.dis && e0.pick === '파일 고르기' && !e0.eng && e0.chars <= 1285 && /기관을 고르고/.test(e0.empty), JSON.stringify(e0));
    let A = 0; const v = await pe.evaluate(() => [...document.querySelector('[data-qs-sel]').options].find(o => /달성군/.test(o.textContent))?.value); await pe.selectOption('[data-qs-sel]', v); A++; await Promise.all([pe.waitForLoadState('load'), pe.click('[data-qs-go]')]); A++;
    await pe.waitForSelector('#rf-all-file', { state: 'attached', timeout: 20000 }); await pe.waitForTimeout(1200);
    await pe.setInputFiles('#rf-all-file', fs.readdirSync(FX5).sort().map(f => path.join(FX5, f))); A++; await pe.waitForTimeout(3500);
    const e2 = await pe.evaluate(() => { const a = document.getElementById('rf-sum-amt'); const r = a?.getBoundingClientRect(); return { amt: a?.textContent ?? '', inView: !!r && r.top >= 0 && r.bottom <= innerHeight, sent: document.querySelector('.rf-sum-l')?.textContent ?? '', cells: [...document.querySelectorAll('.rf-sum-cells b')].map(b => b.textContent), rows: document.querySelectorAll('#rf-sum .rf-row').length, miss: document.querySelector('#rf-sum .rf-miss-l')?.textContent ?? '', files: [...document.querySelectorAll('#rf-all-list li')].map(l => l.textContent).join('|') + (document.getElementById('rf-all-files-sum')?.textContent ?? ''), hs: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 }; });
    ok(`E2 ${vp.width}px 과업 A — 행동 ${A}(4 이하)로 한 문장 '대구광역시 달성군은 … 460,000원 … 최대 5,200,000원', 금액이 화면 안, 기간 행·빠진 기간 안내, 파일마다 종류 배지, 가로 스크롤 없음`, A <= 4 && e2.amt === '460,000원' && e2.inView && /대구광역시 달성군은/.test(e2.sent) && /최대 5,200,000원/.test(e2.sent) && e2.cells[0] === '460,000원' && e2.cells[1] === '+5,200,000원' && e2.rows >= 3 && /2022년 제2기/.test(e2.miss) && /신고서/.test(e2.files) && !e2.hs, JSON.stringify(e2).slice(0, 500));
    await pe.click('#rf-sum .rf-row-why summary'); const e3 = await pe.evaluate(() => { const d = document.querySelector('#rf-sum .rf-row-why'); return { open: d.open, todo: /할 일/.test(d.textContent), law: d.querySelectorAll('a[href*="law.go.kr"]').length }; });
    ok(`E3 ${vp.width}px 과업 B — 기간 행 「왜 · 어떻게」 한 번 → 할 일·이유·근거 조문 링크`, e3.open && e3.todo && e3.law >= 1, JSON.stringify(e3));
    const jar = await pe.evaluate(() => { const J = /\(\d{1,2}\)|[⑤⑩⑪⑫⑭⑮⑯⑰⑱⑲⑳]|안분|면세비율|정산|재계산|과세표준|불공제|매입세액|경정청구|기한후신고/g; const P = /공제받은|공제받지|돌려받|빼고|나누어|다시 셈|미리 낸|낼 세금|산 물건/; const d = document.querySelector('#rf-sum .rf-row-why'); if (d) d.open = false; return document.getElementById('rf-sum').innerText.split('\n').filter(l => !P.test(l)).flatMap(l => l.match(J) ?? []); });
    ok(`E4 ${vp.width}px 결과 요약의 풀어 쓰지 않은 서식 칸·세법 용어 0`, jar.length === 0, jar.join(','));
    if (vp.width === 1366) {
      const zr = path.join(os.tmpdir(), 'vat-e-submit.zip'); const [dl] = await Promise.all([pe.waitForEvent('download', { timeout: 60000 }), pe.click('#rf-dl-submit')]); await dl.saveAs(zr); const zl = execSync(`unzip -Z1 "${zr}"`).toString();
      ok('E5 과업 C — 강조 단추 「세무서·홈택스에 낼 자료 받기」 한 번 → 엑셀·PDF 가 든 묶음', /10_경정청구_자료\.xlsx/.test(zl) && /11_경정청구_요약\.pdf/.test(zl), zl.replace(/\n/g, ' '));
      const big = await pe.evaluate(() => ({ n: document.querySelectorAll('#rf-sum .rf-dl > .btn').length, rep: !!document.getElementById('rf-dl-report') }));
      ok('E6 강조 내려받기 단추는 하나(결재용 보고 단추 없음 — 운영자 2026-11-05 \'지워\')', big.n === 1 && !big.rep, JSON.stringify(big));
    }
    await ce.close(); }
  /* E8 매입 목록 없이 더 찾기(운영자 2026-11-05) — 신고서 (16) 1,200,000 < 과세 시설(체육센터) 계약 부가세 어림 2,500,000 → 빠졌을 수 있는 1,300,000 + '면세사업 관련' 110,000 = 후보 1,410,000, 확인할 업체 2곳 */
  { const c8 = await browser.newContext({ viewport: { width: 1366, height: 768 }, acceptDownloads: true }); const p8 = await c8.newPage(); p8.on('pageerror', e => errs.push('E8: ' + e));
    const CR8 = (no, k, nm, date, tot, corp, cno) => ({ k, no, nm, inst: '대구광역시 달성군', dept: '시험과', dmn: [], date, tot, amt: tot, mth: '수의계약', lng: '신규', cls: '', corps: [{ nm: corp, no: cno, sh: '100' }], url: '' });
    const CTR8 = { key: 'dalseong', name: '대구광역시 달성군', fetched: '2026-11-05', from: '2020-07', to: '2026-11', rows: [CR8('T1', '공사', '시험체육센터 지붕 방수 공사', '2024-08-01', 22000000, '(주)가나건설', '1112233333'), CR8('T2', '용역', '시험도서관 청소 용역', '2024-07-15', 11000000, '다라청소', '2223344444'), CR8('T3', '물품', '시험체육센터 운동기구 구입', '2024-09-01', 5500000, '마바스포츠', '3334455555')] };
    await p8.route('**/vat-expense/index.json', async r => { const res = await r.fetch(); const j = await res.json(); const g = (j.govs ?? []).find(x => x.key === 'dalseong'); if (g) g.contracts = { from: '2020-07', to: '2026-11', rows: 3, fetched: '2026-11-05' }; await r.fulfill({ json: j }); });
    await p8.route('**/vat-expense/contracts-dalseong.json', r => r.fulfill({ json: CTR8 }));
    const O8 = { v: 1, org: '시험군', dept: '재무과', unit: 'entity', reg_no: '555-83-00001', created: '2026-01-01', facilities: [{ id: 'f1', type: 'sports', name: '시험체육센터', run: 'direct', income: [], deposit: false }, { id: 'f2', type: 'culture', name: '시험도서관', run: 'direct', income: [], deposit: false }] };
    await p8.goto(base + '/vat/review/'); await p8.evaluate(o => { localStorage.clear(); localStorage.setItem('vat-org-v1', JSON.stringify(o)); localStorage.setItem('vat-gov', 'dalseong'); }, O8); await p8.reload(); await p8.waitForSelector('#rf-all-file', { state: 'attached' }); await p8.waitForTimeout(1200);
    await p8.setInputFiles('#rf-all-file', [path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax', 'filed_2024_2.txt')]); await p8.waitForTimeout(1500);
    const e8 = await p8.evaluate(() => ({ amt: document.getElementById('rf-cand-amt')?.textContent ?? '', head: document.querySelector('.rf-sum-l2')?.textContent ?? '', row: document.querySelector('#rf-cand .rf-cand-row')?.textContent.replace(/\s+/g, ' ') ?? '', sups: [...document.querySelectorAll('#rf-cand .rf-row-why li')].map(l => l.textContent.replace(/\s+/g, ' ')), sure: document.getElementById('rf-sum-amt')?.textContent ?? '' }));
    ok('E8 매입 목록 없이 — 계약으로 찾은 후보 1,410,000원(빠졌을 수 있는 1,300,000 + 면세사업 관련 110,000), 확인할 업체 2곳(번호), 확정과 섞지 않음', e8.amt === '+1,410,000원' && /약 1,410,000원/.test(e8.head) && /업체 2곳/.test(e8.head) && /1,300,000원은 신고에 들어가지 않았을 수/.test(e8.row) && e8.sups.length === 2 && e8.sups.some(t => /111-22-33333/.test(t)) && e8.sups.some(t => /333-44-55555/.test(t)) && !e8.sups.some(t => /다라청소/.test(t)), JSON.stringify(e8).slice(0, 600));
    const [dc] = await Promise.all([p8.waitForEvent('download', { timeout: 20000 }), p8.click('#rf-cand-csv')]); const cp = path.join(os.tmpdir(), 'vat-e8.csv'); await dc.saveAs(cp); const csv = fs.readFileSync(cp, 'utf8');
    ok('E8b 확인할 업체 목록 CSV — 과세기간·업체·사업자등록번호·계약명·부가세 어림', /사업자등록번호/.test(csv) && /1112233333/.test(csv) && /시험체육센터 지붕 방수 공사/.test(csv) && csv.trim().split('\n').length === 3, csv.slice(0, 300));
    await c8.close(); }
  const cf = await browser.newContext({ viewport: { width: 1366, height: 768 } }); const pf = await cf.newPage();
  await pf.goto(base + '/vat/review/'); await pf.evaluate(o => { localStorage.clear(); localStorage.setItem('vat-org-v1', JSON.stringify(o)); }, ORG); await pf.reload(); await pf.waitForSelector('#rf-all-file', { state: 'attached' }); await pf.waitForTimeout(800);
  const e7a = await pf.evaluate(() => ({ empty: document.querySelector('#rf-sum .rf-empty')?.textContent ?? '', lock: document.getElementById('rf-lock').hidden, dis: document.getElementById('rf-all-pick').disabled }));
  await pf.setInputFiles('#rf-all-file', [{ name: '스캔본.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\n%이미지뿐\n') }]); await pf.waitForTimeout(1500);
  const e7 = await pf.evaluate(() => [...document.querySelectorAll('#rf-all-list li.rf-bad')].map(l => l.textContent).join('|'));
  ok('E7 빈 상태(기관만 → 「2에 … 신고서 PDF 를 놓으면」) · 못 읽은 파일은 이름·이유·어떻게', /신고서 PDF 를 놓으면/.test(e7a.empty) && e7a.lock && !e7a.dis && /스캔본\.pdf/.test(e7) && /못 읽음/.test(e7) && /(PDF 로 저장|만 읽습니다)/.test(e7), JSON.stringify({ e7a, e7 }));
  await cf.close();
}
ok('no console errors', errs.length === 0, errs.join(' | ').slice(0, 400));
console.log(`== ${pass} pass, ${fail} fail`);
await browser.close(); if (srv) srv.close(); if (fail) process.exitCode = 1;
