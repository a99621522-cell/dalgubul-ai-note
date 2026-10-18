// 서버·화면 연결 검증: 정적 파일, CSP, 계산 API, 잘못된 입력. 모델 호출은 하지 않는다(키 없이도 통과).
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const PORT = 8700 + Math.floor(Math.random() * 200);
const base = `http://localhost:${PORT}`;
let child: ChildProcess;

before(async () => {
  const server = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/llm/server.ts');
  child = spawn(process.execPath, [server], { env: { ...process.env, PORT: String(PORT) }, stdio: ['ignore', 'pipe', 'pipe'] });
  await new Promise<void>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('server start timeout')), 8000);
    child.stdout!.on('data', (d: Buffer) => { if (d.toString().includes('divination server')) { clearTimeout(t); resolve(); } });
    child.on('exit', (c) => reject(new Error(`server exited ${c}`)));
  });
});
after(() => { child?.kill(); });

test('정적 파일과 보안 헤더', async () => {
  const r = await fetch(base + '/');
  assert.equal(r.status, 200);
  assert.match(r.headers.get('content-type') ?? '', /text\/html/);
  assert.match(r.headers.get('content-security-policy') ?? '', /default-src 'self'/);
  const html = await r.text();
  assert.match(html, /참고·오락용/); assert.match(html, /109/);
  assert.equal((await fetch(base + '/app.js')).status, 200);
  assert.equal((await fetch(base + '/app.css')).status, 200);
  assert.equal((await fetch(base + '/nope')).status, 404);
  assert.equal((await fetch(base + '/../package.json')).status, 404);
});

test('POST /api/cast 는 괘·국을 돌려준다', async () => {
  const r = await fetch(base + '/api/cast', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ question: '테스트', datetime: '2026-10-18T14:30:00+09:00', material: { numbers: [37, 58] }, options: { tzOffsetMin: 540 } }) });
  assert.equal(r.status, 200);
  const d = await r.json() as { charts: { meihua: { benGua: { hanja: string } }; qimen: { palaces: unknown[]; ju: { number: number } } } };
  assert.ok(d.charts.meihua.benGua.hanja);
  assert.equal(d.charts.qimen.palaces.length, 9);
  assert.equal(d.charts.qimen.ju.number, 6);
});

test('잘못된 입력은 400, 큰 본문은 거절', async () => {
  const r = await fetch(base + '/api/cast', { method: 'POST', body: '{"nope":1}' });
  assert.equal(r.status, 400);
  const r2 = await fetch(base + '/api/cast', { method: 'POST', body: 'not json' });
  assert.equal(r2.status, 400);
  const r3 = await fetch(base + '/api/cast', { method: 'POST', body: JSON.stringify({ question: 'x'.repeat(600) }) });
  assert.equal(r3.status, 400);
});
