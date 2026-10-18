// 최소 HTTP 서버(표준 node:http). 키는 서버에만 있고 브라우저로 나가지 않는다.
//   POST /api/divine  {question, datetime?, longitude?, material?, yearMing?, method?, options?}  → DivinationResult
//   POST /api/cast    같은 입력 → charts 만(LLM 없음)
//   GET  /health
//   GET  /, /app.js, /app.css  — public/ 의 화면 파일(정적, 화이트리스트)
// 실행: node src/llm/server.ts  (PORT 기본 8787). 개인정보(생년월일 등)는 저장하지 않는다.
import http from 'node:http';
import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runDivination, castOnly, type DivinationRequest } from './pipeline.ts';
import { AnthropicCaller, RefusalError } from './model.ts';

const PORT = Number(process.env.PORT ?? 8787);
const MAX_BODY = 64 * 1024;
const caller = new AnthropicCaller();
const PUBLIC_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../public');
const STATIC: Record<string, { file: string; type: string }> = {
  '/': { file: 'index.html', type: 'text/html; charset=utf-8' },
  '/index.html': { file: 'index.html', type: 'text/html; charset=utf-8' },
  '/app.js': { file: 'app.js', type: 'text/javascript; charset=utf-8' },
  '/app.css': { file: 'app.css', type: 'text/css; charset=utf-8' },
};
const CSP = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'";
function sendStatic(res: http.ServerResponse, key: string) {
  const s = STATIC[key];
  const full = path.join(PUBLIC_DIR, s.file);
  if (!existsSync(full)) { res.writeHead(404); return res.end('not found'); }
  res.writeHead(200, { 'content-type': s.type, 'content-security-policy': CSP, 'x-content-type-options': 'nosniff', 'referrer-policy': 'no-referrer', 'cache-control': 'no-cache' });
  res.end(readFileSync(full));
}

function readJson(req: http.IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks: Buffer[] = [];
    req.on('data', (c: Buffer) => { size += c.length; if (size > MAX_BODY) { reject(new Error('본문이 너무 큽니다')); req.destroy(); } else chunks.push(c); });
    req.on('end', () => { try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {}); } catch { reject(new Error('JSON 형식 오류')); } });
    req.on('error', reject);
  });
}
function send(res: http.ServerResponse, status: number, body: unknown) {
  const s = JSON.stringify(body);
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
  res.end(s);
}
function sanitize(b: unknown): DivinationRequest {
  if (!b || typeof b !== 'object') throw new Error('본문이 객체가 아닙니다');
  const o = b as Record<string, unknown>;
  if (typeof o.question !== 'string' || !o.question.trim()) throw new Error('question 이 필요합니다');
  if (o.question.length > 500) throw new Error('질문은 500자 이내로');
  const req: DivinationRequest = { question: o.question.trim() };
  if (typeof o.datetime === 'string') req.datetime = o.datetime;
  if (typeof o.longitude === 'number') req.longitude = o.longitude;
  if (typeof o.yearMing === 'string' && /^[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]$/.test(o.yearMing)) req.yearMing = o.yearMing;
  if (typeof o.externalSigns === 'string') req.externalSigns = o.externalSigns.slice(0, 300);
  if (o.method === 'auto' || o.method === 'meihua' || o.method === 'qimen' || o.method === 'both') req.method = o.method;
  if (o.material && typeof o.material === 'object') {
    const m = o.material as Record<string, unknown>;
    req.material = {};
    if (Array.isArray(m.numbers)) req.material.numbers = m.numbers.map(Number).filter((n) => Number.isInteger(n) && n >= 0).slice(0, 3);
    if (typeof m.text === 'string') req.material.text = m.text.slice(0, 20);
    if (typeof m.object === 'string') req.material.object = m.object.slice(0, 20);
    if (typeof m.direction === 'string') req.material.direction = m.direction.slice(0, 10);
  }
  if (o.options && typeof o.options === 'object') {
    const t = o.options as Record<string, unknown>;
    req.options = {};
    if (t.localSolar === 'none' || t.localSolar === 'longitude' || t.localSolar === 'longitude+eot') req.options.localSolar = t.localSolar;
    if (t.ziHour === '23' || t.ziHour === '00') req.options.ziHour = t.ziHour;
    if (typeof t.tzOffsetMin === 'number') req.options.tzOffsetMin = t.tzOffsetMin;
  }
  return req;
}

const server = http.createServer(async (req, res) => {
  try {
    const urlPath = (req.url ?? '/').split('?')[0];
    if ((req.method === 'GET' || req.method === 'HEAD') && urlPath in STATIC) return sendStatic(res, urlPath);
    if (req.method === 'GET' && urlPath === '/health') return send(res, 200, { ok: true, model: caller.model });
    if (req.method === 'POST' && urlPath === '/api/cast') {
      const body = sanitize(await readJson(req));
      return send(res, 200, { charts: castOnly(body, body.method === 'auto' ? 'both' : body.method ?? 'both') });
    }
    if (req.method === 'POST' && urlPath === '/api/divine') {
      const body = sanitize(await readJson(req));
      const result = await runDivination(body, caller);
      return send(res, 200, result);
    }
    return send(res, 404, { error: 'not found' });
  } catch (e) {
    if (e instanceof RefusalError) return send(res, 422, { error: e.message, stage: e.stage });
    const msg = e instanceof Error ? e.message : String(e);
    const status = /필요합니다|형식|이내|너무|객체|비어/.test(msg) ? 400 : 500;
    return send(res, status, { error: msg });
  }
});

server.listen(PORT, () => console.log(`divination server http://localhost:${PORT} (model ${caller.model})`));
