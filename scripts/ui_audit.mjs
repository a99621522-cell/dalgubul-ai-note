// 접근성·성능 자동 측정(디자인·UI 개선 2차 2026-10-06): axe-core(WCAG 2.x A/AA 규칙)와 Lighthouse(모바일)를 대표 페이지에 돌려
// data/ui_audit/latest.json 과 요약 마크다운(stdout, CI 는 Job Summary)을 낸다. axe 위반이 있으면 종료 코드 1(CI 실패), Lighthouse 점수는 보고만(러너 성능이 흔들려 기준으로 쓰지 않음).
// 사용: node scripts/ui_audit.mjs [--base http://localhost:4399] [--no-lh]   (dist 를 띄운 뒤). 의존: @axe-core/playwright, lighthouse, playwright(설치는 CI 에서 --no-save)
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const base = args.includes('--base') ? args[args.indexOf('--base') + 1] : 'http://localhost:4399';
const noLh = args.includes('--no-lh');
const PAGES = ['/', '/companies/', '/listed/', '/stats/', '/growth/', '/search/?q=자동차', '/listed/00102353/', '/programs/'];
const out = { generated: new Date().toISOString().slice(0, 10), base, pages: [] };
const browser = await chromium.launch(process.env.PLAYWRIGHT_BROWSERS_PATH ? {} : { executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
let fail = 0;
for (const u of PAGES) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });   // @axe-core/playwright 는 newContext 의 page 만 받는다
  const page = await context.newPage();
  await page.goto(base + u, { waitUntil: 'load' });
  await page.waitForTimeout(400);
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
  const viol = axe.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length, sample: v.nodes[0]?.target?.join(' ') ?? '' }));
  const hscroll = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  const header = await page.$eval('.site-head .row', e => Math.round(e.getBoundingClientRect().height)).catch(() => null);
  out.pages.push({ url: u, axe_violations: viol, h_scroll: hscroll, header_px: header });
  if (viol.length || hscroll) fail++;
  await context.close();
}
await browser.close();
if (!noLh) {
  try {
    const { default: lighthouse } = await import('lighthouse');
    const { launch } = await import('chrome-launcher');
    const chrome = await launch({ chromeFlags: ['--headless=new', '--no-sandbox'], chromePath: process.env.CHROME_PATH || '/opt/pw-browsers/chromium' });
    for (const u of PAGES.slice(0, 4)) {
      const r = await lighthouse(base + u, { port: chrome.port, output: 'json', logLevel: 'error', onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'], formFactor: 'mobile', screenEmulation: { mobile: true, width: 390, height: 844, deviceScaleFactor: 2, disabled: false } });
      const c = r.lhr.categories, a = r.lhr.audits;
      const p = out.pages.find(x => x.url === u);
      p.lighthouse = { performance: Math.round(c.performance.score * 100), accessibility: Math.round(c.accessibility.score * 100), best: Math.round(c['best-practices'].score * 100), seo: Math.round(c.seo.score * 100),
        lcp_s: +(a['largest-contentful-paint'].numericValue / 1000).toFixed(2), cls: +a['cumulative-layout-shift'].numericValue.toFixed(3), tbt_ms: Math.round(a['total-blocking-time'].numericValue) };
    }
    await chrome.kill();
  } catch (e) { out.lighthouse_error = String(e).slice(0, 200); }
}
fs.mkdirSync('data/ui_audit', { recursive: true });
fs.writeFileSync(path.join('data/ui_audit', 'latest.json'), JSON.stringify(out, null, 1) + '\n');
const md = ['# UI 감사 ' + out.generated, '', '| 페이지 | axe 위반 | 가로 스크롤 | 헤더(px) | 성능 | 접근성 | LCP(s) | CLS |', '|---|---:|---|---:|---:|---:|---:|---:|',
  ...out.pages.map(p => `| ${p.url} | ${p.axe_violations.length} | ${p.h_scroll ? '있음' : '없음'} | ${p.header_px ?? '—'} | ${p.lighthouse?.performance ?? '—'} | ${p.lighthouse?.accessibility ?? '—'} | ${p.lighthouse?.lcp_s ?? '—'} | ${p.lighthouse?.cls ?? '—'} |`),
  '', ...out.pages.flatMap(p => p.axe_violations.map(v => `- ${p.url} · **${v.id}**(${v.impact}) ${v.help} — ${v.nodes}곳, 예: \`${v.sample}\``)), out.lighthouse_error ? `\nLighthouse 실패: ${out.lighthouse_error}` : ''].join('\n');
console.log(md);
if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, md + '\n');
process.exit(fail ? 1 : 0);
