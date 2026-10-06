#!/usr/bin/env node
/**
 * 브라우저 경로(src/scripts/hwpx.ts)로 HWPX 시험 파일 만들기 — 실제 크로미움에서 DOMParser·XMLSerializer·Blob 을 써서 사이트와 같은 코드가 돈다.
 * esbuild 로 hwpx.ts 를 한 파일로 묶고 Playwright 로 빈 페이지에 넣어 buildHwpx(blocks) 를 부른 뒤 base64 로 받아 저장한다. hwpx_test.py 가 호출.
 * 사용: node scripts/hwpx_browser.mjs <blocks.json> <out.hwpx> [preview]
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [blocksPath, outPath, preview = ''] = process.argv.slice(2);
if (!blocksPath || !outPath) { console.error('사용: node scripts/hwpx_browser.mjs <blocks.json> <out.hwpx> [preview]'); process.exit(1); }

const bundle = path.join(ROOT, 'node_modules', '.cache', 'hwpx_browser.js');
fs.mkdirSync(path.dirname(bundle), { recursive: true });
execFileSync(path.join(ROOT, 'node_modules', '.bin', 'esbuild'), [path.join(ROOT, 'src/scripts/hwpx.ts'), '--bundle', '--format=iife', '--global-name=HWPX', '--target=es2020', `--outfile=${bundle}`], { stdio: 'inherit' });

const { chromium } = await import(fs.existsSync(path.join(ROOT, 'node_modules', 'playwright')) ? 'playwright' : '/opt/node22/lib/node_modules/playwright/index.mjs');
// 이 세션 환경은 미리 깔린 크로미움(/opt/pw-browsers/chromium), 러너는 `npx playwright install chromium` 이 깐 것(executablePath 생략)
const exe = process.env.PW_CHROMIUM || (fs.existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined);
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const page = await browser.newPage();
await page.setContent('<!doctype html><html><body></body></html>');
await page.addScriptTag({ content: fs.readFileSync(bundle, 'utf8') });
const template = JSON.parse(fs.readFileSync(path.join(ROOT, 'public/hwpx/template.json'), 'utf8'));
const blocks = JSON.parse(fs.readFileSync(blocksPath, 'utf8'));
// 그림 블록은 {pic: 파일 경로} 로 받아 바이트로 바꾼다
for (const b of blocks) if (b.pic && typeof b.pic === 'string') { const f = b.pic.startsWith('/') ? path.join(ROOT, 'public', b.pic) : b.pic; const buf = fs.readFileSync(f); b.pic = Array.from(buf); b.ext = f.endsWith('.jpg') || f.endsWith('.jpeg') ? 'jpg' : 'png';
  if (b.ext === 'png') { b.w = buf.readUInt32BE(16); b.h = buf.readUInt32BE(20); } else { b.w = b.w || 800; b.h = b.h || 600; } }
const b64 = await page.evaluate(async ({ template, blocks, preview }) => {
  // @ts-ignore
  const H = window.HWPX; H.setTemplate(template);
  for (const b of blocks) if (b.pic) b.pic = new Uint8Array(b.pic);
  const blob = await H.buildHwpx(blocks, preview);
  const buf = new Uint8Array(await blob.arrayBuffer()); let s = ''; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  return btoa(s);
}, { template, blocks, preview });
await browser.close();
fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, Buffer.from(b64, 'base64'));
console.log('→', outPath, fs.statSync(outPath).size, 'bytes');
