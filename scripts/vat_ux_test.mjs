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
  ok('T1 grid: imported rows pending', total > 40 && pend === total);
  const fields = await pg.evaluate(() => [...document.querySelectorAll('.step[data-step="3"] input,.step[data-step="3"] select')].filter(e => e.offsetParent !== null && !e.closest('tr.sub')).length);
  const scroll = await pg.evaluate(() => document.documentElement.scrollHeight); console.log(`   T1 rows ${total} · visible fields ${fields} · scroll ${scroll}px (${(scroll / 768).toFixed(1)} screens)`);
  await click('[data-sel-all]'); await pg.selectOption('[data-bk=run]', 'direct'); clicks++; await click('[data-bulk=sel]'); await pg.waitForTimeout(300);
  ok('T1 bulk: no pending', await pg.locator('#st-grid tbody tr[data-pending]').count() === 0);
  await click('.step[data-step="3"] [data-next]'); await click('.step[data-step="4"] [data-next]'); await pg.waitForTimeout(400);
  const saved = await lsJson('vat-org-v1'); ok('T1 saved: all direct', saved && saved.facilities.length === total && saved.facilities.every(f => f.run === 'direct'));
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
  await pg.locator('#p-result button.help[data-text]').first().click(); ok('T5 popover text', T(await pg.locator('#p-result .pop').textContent()).includes('이번 값')); await pg.keyboard.press('Escape');
  // 인쇄: 탭 전부 펼침 + 머리글
  await pg.emulateMedia({ media: 'print' }); const shown = await pg.evaluate(() => [...document.querySelectorAll('#p-result section.ftab')].every(s => getComputedStyle(s).display !== 'none'));
  ok('print: all form tabs displayed', shown); ok('print: header attr', !!(await pg.evaluate(() => document.body.getAttribute('data-print-head')))); await pg.emulateMedia({ media: 'screen' });
}
/* ── T6 지난 신고 점검 ── */
{
  await pg.goto(base + '/vat/review/'); await pg.waitForTimeout(300); await pg.fill('#rv-reg', '555-83-00001');
  await pg.fill('#rv-a', '작성일자\t공급자등록번호\t공급자상호\t품목\t공급가액\t세액\t공급받는자등록번호\n2024-03-05\t123-45-67890\t가상전력\t전기요금\t1,500,000\t150,000\t555-83-00001\n2024-09-05\t123-45-67890\t가상전력\t전기요금\t1,000,000\t100,000\t555-83-00001');
  await pg.evaluate(() => document.getElementById('rv-form').requestSubmit()); await pg.waitForTimeout(400);
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
ok('W2 3단계로 열리고 noreg 칩이 눌림', !(await pg.locator('.step[data-step="3"]').isHidden()) && (await pg.locator('#st-fac [data-filter=noreg]').getAttribute('aria-pressed')) === 'true');
ok('W2 등록번호 열 출처 ? 단추', await pg.locator('#st-fac button.help.src').count() >= 1);
await pg.goto(base + '/vat/setup/'); await pg.waitForTimeout(800); ok('W2 5단계 경고 상자 + 단추 2개', await pg.locator('#st-gaps').count() === 1 && (await pg.locator('#st-gaps button').count()) >= 2);
await pg.click('#st-gaps [data-gofilter=pending]'); await pg.waitForTimeout(400); ok('W2 경고 단추 → 3단계 pending 필터', !(await pg.locator('.step[data-step="3"]').isHidden()) && (await pg.locator('#st-fac [data-filter=pending]').getAttribute('aria-pressed')) === 'true');
// make org usable: direct + reg no for all, dept
await pg.click('#st-fac [data-sel-all]'); await pg.selectOption('#st-fac [data-bk=run]', 'direct'); await pg.fill('#st-fac [data-bk=reg_no]', '505-83-00001'); await pg.click('#st-fac [data-bulk=sel]'); await pg.waitForTimeout(300); await pg.click('.step[data-step="3"] [data-next]'); await pg.waitForTimeout(200); await pg.click('.step[data-step="4"] [data-next]'); await pg.waitForTimeout(400);
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
await pg.fill('#rv-a', rv.join('\n')); await pg.click('#rv-form button[type=submit]'); await pg.waitForTimeout(400); await pg.click('#rv-build'); await pg.waitForTimeout(600);
ok('W7 신고 내역 없음 안내', /신고 내역을 아직 넣지 않았습니다/.test(T(await pg.locator('#rv-result').textContent())));
const [dl] = await Promise.all([pg.waitForEvent('download'), pg.click('#rv-zip')]); const zp = path.join(os.tmpdir(), 'vat-rv.zip'); await dl.saveAs(zp); const list = execSync(`unzip -Z1 "${zp}"`).toString().trim().split('\n'); ok('W7 붙임 zip 3파일', list.length === 3, list.join('|'));
// W8 handover
await pg.goto(base + '/vat/handover/'); await pg.waitForTimeout(800); const doc = T(await pg.locator('#h-doc').textContent());
const todoLines = (doc.match(/다음 신고까지 할 일/) ? doc.split('4. 다음 신고까지 할 일')[1]?.split('5. 파일')[0] ?? '' : '').split(' - ').length - 1; ok('W8 README 다음 신고까지 할 일 ≥ 3줄', /다음 신고까지 할 일/.test(doc) && todoLines >= 3, String(todoLines));
const [dz] = await Promise.all([pg.waitForEvent('download'), pg.click('#h-zip')]); const hz = path.join(os.tmpdir(), 'vat-h.zip'); await dz.saveAs(hz); ok('W8 zip 에 nolog.json', execSync(`unzip -Z1 "${hz}"`).toString().includes('nolog.json'));
const ctx2 = await browser.newContext({ viewport: { width: 1366, height: 768 } }); const p2 = await ctx2.newPage(); await p2.goto(base + '/vat/handover/'); await p2.setInputFiles('#h-open', hz); await p2.waitForTimeout(1200);
ok('W8 복원 뒤 이제 할 일 단추 + nolog 복원', await p2.locator('#h-next').count() === 1 && Object.keys(await p2.evaluate(() => JSON.parse(localStorage.getItem('vat-nolog-v1') || '{}'))).length > 0);
await p2.goto(base + '/vat/'); await p2.waitForTimeout(800); ok('W8 후임자 대시보드 이번 주 할 일', await p2.locator('#vat-week li').count() >= 1);
}
ok('no console errors', errs.length === 0, errs.join(' | ').slice(0, 400));
console.log(`== ${pass} pass, ${fail} fail`);
await browser.close(); if (srv) srv.close(); if (fail) process.exitCode = 1;
