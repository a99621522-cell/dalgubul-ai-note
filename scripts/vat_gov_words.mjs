// 지자체 전용 사이트에서 그 지자체 담당자가 헷갈릴 낱말(다른 지자체 구조 — 공단·대행·'군' 등)이 화면(접힌 펼침 포함)에 남았는지 찾는다.
// node scripts/vat_gov_words.mjs --base http://localhost:4401 [--words '공단|대행|…']  — 신고서 고정 자료를 놓은 뒤 main 의 모든 글자를 문장으로 나눠 찍는다(시험 아님, 점검용)
import { chromium } from 'playwright'; import fs from 'node:fs'; import path from 'node:path';
const args = process.argv.slice(2); const arg = (k, d) => (args.includes(k) ? args[args.indexOf(k) + 1] : d);
const base = arg('--base', 'http://localhost:4401'); const W = new RegExp(arg('--words', '공단|대행|(?<![가-힣])군(?=[ 이의은가을에·(])|군청|군 명의|군 세입|달성'), 'g');
const FX = path.join(path.dirname(new URL(import.meta.url).pathname), 'fixtures', 'hometax', 'dalseong5y'); const files = fs.readdirSync(FX).sort().map(f => path.join(FX, f));
const b = await chromium.launch(process.env.PLAYWRIGHT_BROWSERS_PATH ? {} : { executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
const pg = await (await b.newContext()).newPage();
await pg.goto(base + '/vat/review/');
for (let i = 0; i < 40; i++) { await pg.waitForTimeout(500); try { if (await pg.evaluate(() => !!localStorage.getItem('vat-org-v1') && document.readyState === 'complete')) break; } catch { /* */ } }
await pg.waitForTimeout(2000);
const dump = async tag => { await pg.evaluate(() => document.querySelectorAll('details').forEach(d => { d.open = true; })); await pg.waitForTimeout(500);
  const t = await pg.evaluate(() => { const m = document.querySelector('main').cloneNode(true); m.querySelectorAll('script,style,template').forEach(x => x.remove()); return m.textContent; }); const seen = new Map();
  for (const s of t.replace(/\s+/g, ' ').split(/(?<=[.다요])\s|(?=[①②③④⑤])/)) { if (W.test(s)) { const k = s.trim().slice(0, 220); seen.set(k, (seen.get(k) ?? 0) + 1); } W.lastIndex = 0; }
  console.log(`== ${tag}: ${seen.size}`); for (const [k, n] of seen) console.log(`${n}× ${k}`); };
await dump('파일 전');
await pg.setInputFiles('#rf-all-file', files); await pg.waitForTimeout(5000);
await dump('신고서 10개 놓은 뒤');
await b.close();
