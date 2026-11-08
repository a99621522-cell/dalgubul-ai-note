// 지자체 전용 사이트(VAT_SITE=1 VAT_GOV=<키> 빌드, deploy_vat_gov.yml) 확인 시험 — 열면 그 지자체로 바로 시작하는지, 다른 지자체 자료·고르기가 없는지, 신고서를 놓으면 금액이 나오는지.
// 쓰는 법: (cd out && python3 -m http.server 4401 &) ; node scripts/vat_gov_site_test.mjs --base http://localhost:4401 --gov suseong
import { chromium } from 'playwright'; import fs from 'node:fs'; import path from 'node:path';
const args = process.argv.slice(2); const arg = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);
const base = arg('--base', 'http://localhost:4401'); const gov = arg('--gov', 'suseong');
const FX = path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax', 'dalseong5y'); const files = fs.readdirSync(FX).sort().slice(0, 2).map(f => path.join(FX, f));
const browser = await chromium.launch(process.env.PLAYWRIGHT_BROWSERS_PATH ? {} : { executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
let fail = 0; const ok = (name, cond, info = '') => { console.log(`${cond ? 'PASS' : 'FAIL'} ${name}${info ? ' — ' + info : ''}`); if (!cond) fail++; };
const pg = await (await browser.newContext({ viewport: { width: 1366, height: 768 } })).newPage();
const bad = []; pg.on('response', r => { if (r.status() >= 400 && !/favicon/.test(r.url())) bad.push(`${r.status()} ${r.url()}`); });
const errs = []; pg.on('pageerror', e => errs.push(String(e)));
await pg.goto(base + '/vat/review/');   // 새 브라우저(저장 없음) — 열자마자 startFromLink 가 설정을 만들고 한 번 다시 연다
for (let i = 0; i < 40; i++) { await pg.waitForTimeout(500); try { if (await pg.evaluate(() => !!localStorage.getItem('vat-org-v1') && document.readyState === 'complete')) break; } catch { /* 다시 여는 중 */ } }
await pg.waitForLoadState('load'); await pg.waitForTimeout(2000);
const D = await pg.evaluate(() => JSON.parse(document.getElementById('vat-data')?.textContent || '{}'));
ok('G1 lock 값', D.lock === gov, D.lock);
ok('G2 지자체 프로필·예시 설정이 그 지자체만', (D.govs ?? []).length === 1 && D.govs[0].key === gov && (D.presets ?? []).every(p => p.key === gov), `govs ${(D.govs ?? []).map(g => g.key)} presets ${(D.presets ?? []).map(p => p.key)}`);
const org = await pg.evaluate(() => JSON.parse(localStorage.getItem('vat-org-v1') || 'null'));
const name = D.govs?.[0]?.name ?? '';
ok('G3 열자마자 그 지자체 기관 설정', !!org && org.org === name && org.facilities.length > 0, org ? `${org.org} 시설 ${org.facilities.length}곳` : '없음');
const h1 = await pg.textContent('h1'); ok('G4 제목에 지자체 이름', h1.includes(name.replace(/^대구광역시 /, '')), h1);
const sel = await pg.$$eval('[data-qs-sel] option', os => os.map(o => o.textContent)); ok('G5 다른 기관 고르기 없음', sel.every(t => !/그 밖의 기관/.test(t)) && sel.filter(t => /대구광역시|구 —|군 —/.test(t)).length <= 1, sel.join(' | '));
ok('G6 처음부터 다시 단추', (await pg.locator('[data-ctx-switch]').textContent()) === '처음부터 다시');
const idx = await pg.evaluate(async () => (await (await fetch('/vat-expense/index.json')).json()).govs.map(g => g.key));
ok('G7 공개 지출 목록이 그 지자체만', idx.every(k => k === gov), idx.join(','));
const rev = await pg.evaluate(async () => (await (await fetch('/vat-revenue.json')).json()).govs.map(g => g.key));
ok('G8 세입예산서가 그 지자체만', rev.every(k => k === gov), rev.join(','));
/* 지자체 맞춤 '먼저 볼 곳'(govs.yml focus) — 묶음이 있는 지자체만 */
if ((D.govs?.[0]?.focus ?? []).length) {
  const g = await pg.$$eval('#rf-focus .rf-focus-g', els => els.length);
  ok('G11 먼저 볼 곳 묶음', g >= 2 && await pg.locator('#rf-focus').isVisible(), `${g}묶음`);
  const own = await pg.evaluate(() => JSON.parse(localStorage.getItem('vat-org-v1') || '{}').facilities.filter(f => f.run === 'entrusted_own').length);
  const shown = await pg.$$eval('#rf-focus details li', els => els.length);
  ok('G12 신고에 넣지 않는 곳 = 수탁기관 자기 사업 시설', own > 0 && shown === own, `${shown}/${own}`);
  const box = pg.locator('#rf-focus .rf-area').first();
  if (await box.count()) {
    const fid = await box.getAttribute('data-fid');
    await box.locator('[data-area-tot]').fill('1000'); await box.locator('[data-area-tax]').fill('250');
    await Promise.all([pg.waitForLoadState('load'), box.locator('[data-area-go]').click()]); await pg.waitForTimeout(2500);
    const sh = await pg.evaluate(id => JSON.parse(localStorage.getItem('vat-org-v1') || '{}').facilities.find(f => f.id === id)?.share, fid);
    const lab = await pg.locator(`#rf-focus .rf-area[data-fid="${fid}"]`).evaluate(el => el.parentElement.textContent);
    ok('G13 면적 두 칸 → 과세 몫 25% 저장·표시', sh === 0.25 && /25%/.test(lab), `share ${sh}`);
  } else ok('G13 면적 칸', false, '없음');
}
await pg.setInputFiles('#rf-all-file', files); await pg.waitForTimeout(3500);
const amt = await pg.textContent('#rf-sum-amt').catch(() => ''); const sum = await pg.textContent('#rf-sum').catch(() => ''); ok('G9 신고서를 놓으면 결과 문장', /\d원/.test(amt ?? '') && (sum ?? '').includes(name.replace(/^대구광역시 /, '')), `${amt} · ${(sum ?? '').replace(/\s+/g, ' ').slice(0, 60)}`);
ok('G10 404·스크립트 오류 없음', bad.length === 0 && errs.length === 0, [...bad, ...errs].join(' ; '));
await browser.close();
console.log(fail ? `실패 ${fail}` : '모두 통과'); process.exit(fail ? 1 : 0);
