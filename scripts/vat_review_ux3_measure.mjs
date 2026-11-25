// 3차 UX 측정(docs/prompts/vat_review_ux_round3.md 2절 표) — 지어낸 신고서 20장 + e호조 지출 3만 건 붙여넣기로 '처음 열기 → 첫 파일 받기'.
// 쓰는 법: node scripts/vat_review_ux3_measure.mjs --base https://vat-suseong.pages.dev [--label before|after] > docs/design/vat-review-ux3-<label>.tsv
// 전용 사이트(VAT_GOV=suseong 빌드)에서 잰다. 일반 빌드면 --base 에 ?gov=suseong 을 붙이는 대신 --gov suseong.
import { chromium } from 'playwright'; import fs from 'node:fs'; import path from 'node:path';
import { ehojoTsv } from './fixtures/hometax/ux3_ehojo.mjs';
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const base = arg('--base', 'http://localhost:4402'), label = arg('--label', 'now'), gov = arg('--gov', '');
const FX = path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax', 'ux3'); const filed = fs.readdirSync(FX).sort().map(f => path.join(FX, f));
const tsv = ehojoTsv(30000);
const JARGON = /\(\d{1,2}\)|[⑤⑩⑪⑫⑭⑮⑯⑰⑱⑲⑳]|안분|면세비율|정산|재계산|과세표준|불공제|매입세액|경정청구|기한후신고/g; const PLAIN = /공제받은|공제받지|돌려받|빼고|나누어|다시 셈|미리 낸|낼 세금|산 물건/;
const jargon = t => t.split('\n').reduce((n, l) => n + (PLAIN.test(l) ? 0 : (l.match(JARGON) ?? []).length), 0);
const vis = (pg, sel) => pg.evaluate(s => [...document.querySelectorAll(s)].filter(e => e.checkVisibility({ checkVisibilityCSS: true }) && e.getBoundingClientRect().height > 0).length, sel);
const browser = await chromium.launch();
console.log(['label', 'viewport', 'actions_to_first_file', 'first_file', 'chars_first_screen', 'strong_buttons_first', 'drop_to_result_s', 'paste_to_result_s', 'progress_shown', 'chars_until_download', 'result_jargon', 'controls_after', 'biz_to_decide', 'reupload_after_reopen', 'page_screens'].join('\t'));
for (const vp of [{ width: 1920, height: 1080 }, { width: 1366, height: 768 }]) {
  const c = await browser.newContext({ viewport: vp, acceptDownloads: true }); const pg = await c.newPage();
  await pg.goto(base + '/vat/review/' + (gov ? `?gov=${gov}` : ''), { waitUntil: 'load' }); await pg.waitForTimeout(4000); await pg.waitForLoadState('load'); await pg.evaluate(() => { localStorage.clear(); try { indexedDB.deleteDatabase('vat-store'); } catch { /* */ } }); await pg.reload({ waitUntil: 'load' }); await pg.waitForTimeout(3000); await pg.waitForSelector('#rf-all-file', { state: 'attached', timeout: 30000 }); await pg.waitForLoadState('load'); await pg.waitForTimeout(2000);
  const chars0 = (await pg.evaluate(() => document.querySelector('main').innerText)).replace(/\s+/g, ' ').length;
  const strong0 = await vis(pg, 'main .btn:not(.secondary):not(.link-btn)');
  let A = 0; let t0 = Date.now();
  await pg.setInputFiles('#rf-all-file', filed); A++;
  await pg.waitForFunction(() => /\d원/.test(document.getElementById('rf-sum-amt')?.textContent ?? ''), null, { timeout: 120000 }).catch(() => {});
  const dropS = ((Date.now() - t0) / 1000).toFixed(1);
  t0 = Date.now(); await pg.evaluate(t => { const dt = new DataTransfer(); dt.setData('text/plain', t); document.body.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true })); }, tsv); A++;
  const prog = await pg.evaluate(() => new Promise(res => { const until = Date.now() + 1500; const tick = () => { const t = document.body.innerText; if (/읽는 중|정리 중|처리 중|계산 중/.test(t)) return res(true); if (Date.now() > until) return res(false); setTimeout(tick, 50); }; tick(); }));
  await pg.waitForFunction(() => /30,?000건/.test(document.getElementById('rv-stat')?.textContent ?? ''), null, { timeout: 300000 }).catch(() => {});
  await pg.waitForTimeout(1500); const pasteS = ((Date.now() - t0) / 1000).toFixed(1);
  /* 첫 파일: 결과에서 보이는 받기 단추를 위에서부터 */
  const cands = ['#rf-dl-get', '#rf-dl-p', '#rf-dl-submit', '#rf-dl-cases'];
  let first = ''; for (const s of cands) { if (await pg.locator(s).first().isVisible().catch(() => false)) { first = s; break; } }
  const untilDl = first ? await pg.evaluate(s => { const sum = document.getElementById('rf-go3') ?? document.getElementById('rf-sum'); const b = document.querySelector(s); const r = document.createRange(); r.setStartBefore(sum); r.setEndBefore(b); return r.toString().replace(/\s+/g, ' ').length; }, first) : -1;
  const resTxt = await pg.evaluate(() => document.getElementById('rf-sum')?.innerText ?? '');
  const ctl = await vis(pg, 'main button, main select, main input:not([type=hidden]), main textarea, main summary');
  const bizTxt = await pg.evaluate(() => document.getElementById('rf-biz-go')?.textContent ?? document.getElementById('rf-ask')?.textContent ?? '');
  const biz = (/사업 ([\d,]+)개를 먼저/.exec(bizTxt) ?? /([\d,]+)개 사업/.exec(bizTxt))?.[1]?.replace(/,/g, '') ?? '0';
  let got = ''; if (first) { const [dl] = await Promise.all([pg.waitForEvent('download', { timeout: 60000 }).catch(() => null), pg.click(first)]); A++; if (dl) got = 'yes'; }
  const screens = (await pg.evaluate(() => document.documentElement.scrollHeight) / vp.height).toFixed(1);
  await pg.reload({ waitUntil: 'load' }); await pg.waitForTimeout(8000);
  const kept = await pg.evaluate(() => /\d원/.test(document.getElementById('rf-sum-amt')?.textContent ?? '') && /30,?000건/.test(document.getElementById('rv-stat')?.textContent ?? ''));
  console.log([label, `${vp.width}x${vp.height}`, A, got || 'no', chars0, strong0, dropS, pasteS, prog ? 'yes' : 'no', untilDl, jargon(resTxt), ctl, biz, kept ? 0 : 2, screens].join('\t'));
  await c.close();
}
await browser.close();
