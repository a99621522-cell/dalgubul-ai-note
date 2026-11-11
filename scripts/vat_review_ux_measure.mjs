// '지난 돈 돌려받기' 쉬운 화면 측정(docs/prompts/vat_review_ux_easiest.md 4-1) — 과업 A~D 를 고정 자료(dalseong5y)로 재어 TSV 한 줄씩.
// 빌드한 dist 를 띄운 뒤: node scripts/vat_review_ux_measure.mjs [--base http://localhost:4398] [--label before|after] > docs/design/vat-review-ux-<label>.tsv
// 재는 것: 클릭·입력 수(과업 흐름대로 실제로 누른 수), 첫 금액까지 스크롤 화면 수(페이지 맨 위에서 금액 칸까지 ÷ 화면 높이),
// 파일 전 첫 화면 글자 수(펼쳐 보이는 글자만), 결과 화면의 풀어 쓰지 않은 서식 칸·세법 용어 수, 결정 지점(보이는 단추·선택 상자·입력 칸) 수, axe 위반 수(설치돼 있을 때).
import { chromium } from 'playwright'; import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
const args = process.argv.slice(2); let base = args.includes('--base') ? args[args.indexOf('--base') + 1] : ''; const label = args.includes('--label') ? args[args.indexOf('--label') + 1] : 'now';
let srv = null; if (!base) { const root = path.resolve('dist'); srv = http.createServer((req, res) => { let p = decodeURIComponent(req.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html'; const f = path.join(root, p); if (!fs.existsSync(f)) { res.statusCode = 404; return res.end(); } const ext = path.extname(f); res.setHeader('content-type', { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.ttf': 'font/ttf' }[ext] || 'application/octet-stream'); fs.createReadStream(f).pipe(res); }).listen(4397); base = 'http://localhost:4397'; }
const FX = path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax', 'dalseong5y'); const files = fs.readdirSync(FX).sort().map(f => path.join(FX, f));
let AxeBuilder = null; try { ({ AxeBuilder } = await import('@axe-core/playwright')); } catch { /* 없음 */ }
const browser = await chromium.launch(process.env.PLAYWRIGHT_BROWSERS_PATH ? {} : { executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
/* 풀어 쓰지 않은 서식 칸·세법 용어 — 괄호 칸 번호 '(18)'·원문자 칸 '⑭'·세법 낱말. 같은 줄에 쉬운 말 풀이(공제받은·안 받은·빼고)가 붙어 있으면 센다에서 뺀다 */
const JARGON = /\(\d{1,2}\)|[⑤⑩⑪⑫⑭⑮⑯⑰⑱⑲⑳]|안분|면세비율|정산|재계산|과세표준|불공제|매입세액|경정청구|기한후신고/g;
const PLAIN = /공제받은|공제받지|돌려받|빼고|나누어|다시 셈|미리 낸|낼 세금|산 물건/;
const visibleText = (pg, sel) => pg.evaluate(s => { const m = document.querySelector(s); return m ? m.innerText : ''; }, sel);
const controls = pg => pg.evaluate(() => [...document.querySelectorAll('main button, main select, main input:not([type=hidden]), main textarea, main summary')].filter(e => e.checkVisibility({ checkVisibilityCSS: true, contentVisibilityAuto: true }) && e.getBoundingClientRect().width > 0).length);   /* 접힌 펼침 안은 content-visibility 로 숨어 있어 checkVisibility 로 거른다 */
const yOf = (pg, sels) => pg.evaluate(ss => { for (const s of ss) { const e = document.querySelector(s); if (e && e.checkVisibility({ checkVisibilityCSS: true, contentVisibilityAuto: true }) && e.getBoundingClientRect().height > 0) return e.getBoundingClientRect().top + scrollY; } return -1; }, sels);
const jargon = txt => txt.split('\n').reduce((n, line) => n + (PLAIN.test(line) ? 0 : (line.match(JARGON) ?? []).length), 0);
const AMT = ['#rf-sum-amt', '#rf-calc-sure']; const WHY = ['#rf-sum .rf-row-why summary', '#rf-calc tbody tr td details summary']; const RES = ['#rf-sum', '#rf-calc']; const ZIP = ['#rf-dl-submit', '#rf-calc-zip']; const WORD = ['#rf-dl-report'];
console.log(['label', 'viewport', 'A_actions', 'A_scroll_screens', 'A_amount_in_view_after_drop', 'pre_chars', 'pre_controls', 'post_chars_visible', 'post_jargon', 'result_chars', 'result_jargon', 'post_controls', 'B_scroll_screens', 'C_actions', 'C_scroll_screens', 'D_actions', 'axe_pre', 'axe_post', 'page_screens_post'].join('\t'));
for (const vp of [{ width: 1366, height: 768 }, { width: 390, height: 844 }]) {
  const c = await browser.newContext({ viewport: vp, acceptDownloads: true }); const pg = await c.newPage();
  await pg.goto(base + '/vat/review/'); await pg.evaluate(() => localStorage.clear()); await pg.reload(); await pg.waitForTimeout(1500);
  const preChars = (await visibleText(pg, 'main')).replace(/\s+/g, ' ').length; const preCtl = await controls(pg);
  const axePre = AxeBuilder ? (await new AxeBuilder({ page: pg }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()).violations.length : '';
  let A = 0;
  /* ① 기관 고르기: 선택 상자 → (단추) */
  await pg.waitForFunction(() => document.querySelector('[data-qs-sel]')?.options.length > 3, null, { timeout: 15000 });
  const v = await pg.evaluate(() => [...document.querySelector('[data-qs-sel]').options].find(o => /달성군/.test(o.textContent))?.value); await pg.selectOption('[data-qs-sel]', v); A++;
  if (await pg.locator('[data-qs-go]').isEnabled().catch(() => false) && await pg.locator('[data-qs-go]').isVisible().catch(() => false)) { await Promise.all([pg.waitForLoadState('load'), pg.click('[data-qs-go]')]); A++; }
  await pg.waitForSelector('#rf-all-file', { state: 'attached', timeout: 20000 }); await pg.waitForTimeout(1200);
  /* ② 파일 고르기(파일 대화상자 한 번) */
  await pg.setInputFiles('#rf-all-file', files); A++; await pg.waitForTimeout(3500);
  const inView = await pg.evaluate(ss => { for (const s of ss) { const e = document.querySelector(s); if (e && e.getBoundingClientRect().height > 0) { const r = e.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; } } return false; }, AMT);
  const amtY = await yOf(pg, AMT); const H = vp.height;
  const postTxt = await visibleText(pg, 'main'); const postCtl = await controls(pg);
  let resTxt = ''; for (const s of RES) { resTxt = await visibleText(pg, s); if (resTxt.trim()) break; }   /* 결과 첫 화면 = 결과 요약(없으면 돌려받을 돈 표) */
  const whyY = await yOf(pg, WHY); const zipY = await yOf(pg, ZIP); const hasWord = (await yOf(pg, WORD)) >= 0;
  const pageH = await pg.evaluate(() => document.documentElement.scrollHeight);
  const axePost = AxeBuilder ? (await new AxeBuilder({ page: pg }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()).violations.length : '';
  const sc = y => y < 0 ? 'NA' : (Math.max(0, y - H * 0.5) / H).toFixed(1);   /* 화면 가운데까지 오게 하려면 몇 화면 내려야 하나 */
  console.log([label, `${vp.width}x${vp.height}`, A, sc(amtY), inView ? 'yes' : 'no', preChars, preCtl, postTxt.replace(/\s+/g, ' ').length, jargon(postTxt), resTxt.replace(/\s+/g, ' ').length, jargon(resTxt), postCtl, sc(whyY), 1, sc(zipY), hasWord ? 1 : '2(zip 풀기)', axePre, axePost, (pageH / H).toFixed(1)].join('\t'));
  await c.close();
}
await browser.close(); if (srv) srv.close();
