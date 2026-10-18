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
  child = spawn(process.execPath, [server], { env: { ...process.env, PORT: String(PORT), RATE_CAST_PER_MIN: '8', METRICS_TOKEN: 'test-token' }, stdio: ['ignore', 'pipe', 'pipe'] });
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

test('POST /api/cast material.coins 왕복과 형식 오류 400', async () => {
  const r = await fetch(base + '/api/cast', { method: 'POST', body: JSON.stringify({ question: '테스트', datetime: '2026-10-19T06:00:00+09:00', method: 'meihua', material: { coins: { lower: [0, 1, 1], upper: [1, 1, 1] } } }) });
  assert.equal(r.status, 200);
  const d = await r.json() as { charts: { meihua: { benGua: { hanja: string }; meta: { method: string } } } };
  assert.equal(d.charts.meihua.benGua.hanja, '天風姤'); assert.equal(d.charts.meihua.meta.method, 'coins');
  const bad = await fetch(base + '/api/cast', { method: 'POST', body: JSON.stringify({ question: '테스트', material: { coins: { lower: [0, 1], upper: [1, 1, 1] } } }) });
  assert.equal(bad.status, 400);
});

test('GET /metrics 는 토큰이 있어야 열리고 집계에 질문이 없다', async () => {
  assert.equal((await fetch(base + '/metrics')).status, 404);
  const r = await fetch(base + '/metrics', { headers: { 'x-metrics-token': 'test-token' } });
  assert.equal(r.status, 200);
  const d = await r.json() as { counts: { cast: number }; limits: { maxDivinePerDay: number } };
  assert.ok(d.counts.cast >= 1); assert.equal(d.limits.maxDivinePerDay, 500);
  assert.ok(!JSON.stringify(d).includes('테스트'));
});

test('요청 제한: 분당 한도를 넘기면 429 와 retry-after', async () => {
  let last = 200; let retry = '';
  for (let i = 0; i < 12; i++) {
    const r = await fetch(base + '/api/cast', { method: 'POST', body: JSON.stringify({ question: 'x', datetime: '2026-10-19T07:00:00+09:00', method: 'meihua' }) });
    last = r.status; if (r.status === 429) { retry = r.headers.get('retry-after') ?? ''; break; }
  }
  assert.equal(last, 429); assert.ok(Number(retry) > 0);
  assert.ok((await fetch(base + '/health')).ok);
});
