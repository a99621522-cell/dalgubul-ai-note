// HTTP 서버(표준 node:http). 키는 서버에만 있고 브라우저로 나가지 않는다.
//   GET  /, /app.js, /app.css      화면(정적, 화이트리스트)
//   POST /api/cast                 괘·국만(LLM 없음)
//   POST /api/divine               분류·해석·종합·검수 → DivinationResult (같은 요청은 캐시)
//   GET  /health                   {ok, model, inFlight}
//   GET  /metrics                  사용량 집계(JSON). METRICS_TOKEN 이 있을 때만, 헤더 x-metrics-token
// 환경 변수는 .env.example 과 docs/ops.md 참고. 요청·결과·IP 는 저장하지 않는다(선택 사용량 로그는 토큰 수·상태만).
import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runDivination, castOnly, type DivinationRequest, type DivinationResult } from './pipeline.ts';
import { AnthropicCaller, RefusalError } from './model.ts';
import { RateLimiter, Gate, LruCache, UsageMeter, requestKey, clientIp, envInt } from './ops.ts';

const PORT = Number(process.env.PORT ?? 8787);
const MAX_BODY = 64 * 1024;
const TRUST_PROXY = process.env.TRUST_PROXY === '1';
const ALLOWED_ORIGIN = process.env.ALLOWED_ORIGIN ?? ''; // 다른 도메인의 화면에서 부를 때만
const METRICS_TOKEN = process.env.METRICS_TOKEN ?? '';
const MAX_DIVINE_PER_DAY = envInt('MAX_DIVINE_PER_DAY', 500); // 서버 전체 하루 상한(비용 보호)

const caller = new AnthropicCaller();
const castLimit = new RateLimiter({ perMinute: envInt('RATE_CAST_PER_MIN', 60), perDay: envInt('RATE_CAST_PER_DAY', 2000) });
const divineLimit = new RateLimiter({ perMinute: envInt('RATE_DIVINE_PER_MIN', 6), perDay: envInt('RATE_DIVINE_PER_DAY', 60) });
const gate = new Gate(envInt('MAX_INFLIGHT', 4));
const cache = new LruCache<DivinationResult>(envInt('CACHE_MAX', 500), envInt('CACHE_TTL_MIN', 1440) * 60000);
const meter = new UsageMeter(process.env.USAGE_LOG || undefined);

const PUBLIC_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../public');
const STATIC: Record<string, { file: string; type: string }> = {
  '/': { file: 'index.html', type: 'text/html; charset=utf-8' },
  '/index.html': { file: 'index.html', type: 'text/html; charset=utf-8' },
  '/app.js': { file: 'app.js', type: 'text/javascript; charset=utf-8' },
  '/app.css': { file: 'app.css', type: 'text/css; charset=utf-8' },
};
const CSP = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'";

function baseHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = { 'x-content-type-options': 'nosniff', 'referrer-policy': 'no-referrer', 'cache-control': 'no-store', ...extra };
  if (ALLOWED_ORIGIN) { h['access-control-allow-origin'] = ALLOWED_ORIGIN; h['vary'] = 'origin'; h['access-control-allow-headers'] = 'content-type'; h['access-control-allow-methods'] = 'POST, GET, OPTIONS'; }
  return h;
}
function sendStatic(res: http.ServerResponse, key: string) {
  const s = STATIC[key];
  const full = path.join(PUBLIC_DIR, s.file);
  if (!existsSync(full)) { res.writeHead(404); return res.end('not found'); }
  res.writeHead(200, baseHeaders({ 'content-type': s.type, 'content-security-policy': CSP, 'cache-control': 'no-cache' }));
  res.end(readFileSync(full));
}
function send(res: http.ServerResponse, status: number, body: unknown, extra: Record<string, string> = {}) {
  res.writeHead(status, baseHeaders({ 'content-type': 'application/json; charset=utf-8', ...extra }));
  res.end(JSON.stringify(body));
}
function readJson(req: http.IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks: Buffer[] = [];
    req.on('data', (c: Buffer) => { size += c.length; if (size > MAX_BODY) { reject(new Error('본문이 너무 큽니다')); req.destroy(); } else chunks.push(c); });
    req.on('end', () => { try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {}); } catch { reject(new Error('JSON 형식 오류')); } });
    req.on('error', reject);
  });
}

const GZ = /^[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]$/;
function sanitize(b: unknown): DivinationRequest {
  if (!b || typeof b !== 'object') throw new Error('본문이 객체가 아닙니다');
  const o = b as Record<string, unknown>;
  if (typeof o.question !== 'string' || !o.question.trim()) throw new Error('question 이 필요합니다');
  if (o.question.length > 500) throw new Error('질문은 500자 이내로');
  const req: DivinationRequest = { question: o.question.trim() };
  if (typeof o.datetime === 'string' && o.datetime.length <= 40) req.datetime = o.datetime;
  if (typeof o.longitude === 'number' && Math.abs(o.longitude) <= 180) req.longitude = o.longitude;
  if (typeof o.yearMing === 'string' && GZ.test(o.yearMing)) req.yearMing = o.yearMing;
  if (typeof o.externalSigns === 'string') req.externalSigns = o.externalSigns.slice(0, 300);
  if (o.method === 'auto' || o.method === 'meihua' || o.method === 'qimen' || o.method === 'both') req.method = o.method;
  if (o.material && typeof o.material === 'object') {
    const m = o.material as Record<string, unknown>;
    req.material = {};
    if (Array.isArray(m.numbers)) req.material.numbers = m.numbers.map(Number).filter((n) => Number.isInteger(n) && n >= 0 && n < 1e9).slice(0, 3);
    if (typeof m.text === 'string') req.material.text = m.text.slice(0, 20);
    if (typeof m.object === 'string') req.material.object = m.object.slice(0, 20);
    if (typeof m.direction === 'string') req.material.direction = m.direction.slice(0, 10);
    if (m.coins && typeof m.coins === 'object') {
      const c = m.coins as Record<string, unknown>;
      const ok = (a: unknown): a is [0 | 1, 0 | 1, 0 | 1] => Array.isArray(a) && a.length === 3 && a.every((x) => x === 0 || x === 1);
      if (!ok(c.lower) || !ok(c.upper)) throw new Error('coins 형식 오류(0|1 세 개씩)');
      req.material.coins = { lower: c.lower, upper: c.upper };
    }
  }
  if (o.options && typeof o.options === 'object') {
    const t = o.options as Record<string, unknown>;
    req.options = {};
    if (t.localSolar === 'none' || t.localSolar === 'longitude' || t.localSolar === 'longitude+eot') req.options.localSolar = t.localSolar;
    if (t.ziHour === '23' || t.ziHour === '00') req.options.ziHour = t.ziHour;
    if (typeof t.tzOffsetMin === 'number' && Math.abs(t.tzOffsetMin) <= 840) req.options.tzOffsetMin = t.tzOffsetMin;
  }
  return req;
}

const server = http.createServer(async (req, res) => {
  const t0 = Date.now();
  const reqId = randomUUID().slice(0, 8);
  res.setHeader('x-request-id', reqId);
  const urlPath = (req.url ?? '/').split('?')[0];
  const ip = clientIp(req.headers, req.socket.remoteAddress, TRUST_PROXY);
  try {
    if (req.method === 'OPTIONS' && ALLOWED_ORIGIN) { res.writeHead(204, baseHeaders()); return res.end(); }
    if ((req.method === 'GET' || req.method === 'HEAD') && urlPath in STATIC) return sendStatic(res, urlPath);
    if (req.method === 'GET' && urlPath === '/health') return send(res, 200, { ok: true, model: caller.model, inFlight: gate.inFlight, cache: cache.size });
    if (req.method === 'GET' && urlPath === '/metrics') {
      if (!METRICS_TOKEN || req.headers['x-metrics-token'] !== METRICS_TOKEN) return send(res, 404, { error: 'not found' });
      return send(res, 200, { ...meter.snapshot(), inFlight: gate.inFlight, cacheSize: cache.size, limits: { maxDivinePerDay: MAX_DIVINE_PER_DAY } });
    }
    if (req.method === 'POST' && urlPath === '/api/cast') {
      const rl = castLimit.hit(ip);
      if (rl) { meter.counts.rateLimited++; return send(res, 429, { error: '요청이 너무 잦습니다. 잠시 뒤 다시 시도해 주세요.' }, { 'retry-after': String(rl.retryAfterSec) }); }
      const body = sanitize(await readJson(req));
      const charts = castOnly(body, body.method === 'auto' ? 'both' : body.method ?? 'both');
      meter.record({ ts: new Date().toISOString(), kind: 'cast', status: 200, cached: false, model: null, input: 0, output: 0, cacheRead: 0, cacheWrite: 0, elapsedMs: Date.now() - t0, safety: 'none', method: body.method ?? 'both', qtype: '' });
      return send(res, 200, { charts });
    }
    if (req.method === 'POST' && urlPath === '/api/divine') {
      const rl = divineLimit.hit(ip);
      if (rl) { meter.counts.rateLimited++; return send(res, 429, { error: rl.scope === 'day' ? '오늘 풀이 횟수를 다 썼습니다. 내일 다시 와 주세요.' : '풀이 요청이 너무 잦습니다. 1분 뒤 다시 시도해 주세요.' }, { 'retry-after': String(rl.retryAfterSec) }); }
      const body = sanitize(await readJson(req));
      const key = requestKey(body as unknown as Record<string, unknown>);
      const hit = cache.get(key);
      if (hit) {
        meter.record({ ts: new Date().toISOString(), kind: 'divine', status: 200, cached: true, model: hit.model, input: 0, output: 0, cacheRead: 0, cacheWrite: 0, elapsedMs: Date.now() - t0, safety: hit.safety.flag, method: hit.methodUsed, qtype: hit.classification.question_type });
        return send(res, 200, { ...hit, cached: true });
      }
      if (meter.todayDivine() >= MAX_DIVINE_PER_DAY) { meter.counts.rateLimited++; return send(res, 503, { error: '오늘 서비스 한도에 닿았습니다. 내일 다시 와 주세요.' }, { 'retry-after': '3600' }); }
      if (!gate.tryEnter()) { meter.counts.busy++; return send(res, 503, { error: '지금 풀이가 몰려 있습니다. 잠시 뒤 다시 시도해 주세요.' }, { 'retry-after': '15' }); }
      try {
        const result = await runDivination(body, caller);
        if (!result.safety.stopped) cache.set(key, result);
        meter.record({ ts: new Date().toISOString(), kind: 'divine', status: 200, cached: false, model: result.model, ...result.usage, elapsedMs: Date.now() - t0, safety: result.safety.flag, method: result.methodUsed, qtype: result.classification.question_type });
        return send(res, 200, result);
      } finally { gate.leave(); }
    }
    return send(res, 404, { error: 'not found' });
  } catch (e) {
    if (e instanceof RefusalError) { meter.counts.refused++; return send(res, 422, { error: '이 질문은 모델이 풀이를 거절했습니다. 표현을 바꿔 다시 물어봐 주세요.', stage: e.stage }); }
    const msg = e instanceof Error ? e.message : String(e);
    const status = /필요합니다|형식|이내|너무|객체|비어|물상 사전|방위/.test(msg) ? 400 : 500;
    if (status >= 500) { meter.counts.errors++; console.error(`[${reqId}] ${urlPath} 500: ${msg}`); }
    return send(res, status, { error: status >= 500 ? '서버 오류로 풀이를 만들지 못했습니다. 잠시 뒤 다시 시도해 주세요.' : msg, requestId: reqId });
  }
});

server.keepAliveTimeout = 65000;
server.listen(PORT, () => console.log(`divination server http://localhost:${PORT} (model ${caller.model}, inflight≤${envInt('MAX_INFLIGHT', 4)}, divine/day≤${MAX_DIVINE_PER_DAY})`));
for (const sig of ['SIGTERM', 'SIGINT'] as const) process.on(sig, () => { console.log(`${sig}: closing`); server.close(() => process.exit(0)); setTimeout(() => process.exit(0), 5000).unref(); });
