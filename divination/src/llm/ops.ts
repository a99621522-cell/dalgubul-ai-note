// 운영 보조: 요청 제한(IP별 분당·일별), 동시 실행 제한, 결과 캐시(LRU+TTL), 사용량 집계(질문 본문 없음). 외부 의존성 없음.
import { createHash } from 'node:crypto';
import { appendFileSync } from 'node:fs';

export interface RateLimitOpts { perMinute: number; perDay: number }
/** 고정 창 두 개(분·일)로 IP 하나의 호출 수를 센다. 메모리에만 두고 10분마다 오래된 키를 비운다 */
export class RateLimiter {
  private minute = new Map<string, { win: number; n: number }>();
  private day = new Map<string, { win: number; n: number }>();
  private lastSweep = Date.now();
  private opts: RateLimitOpts;
  constructor(opts: RateLimitOpts) { this.opts = opts; }
  /** 허용이면 null, 거절이면 몇 초 뒤 다시인지 */
  hit(key: string, now = Date.now()): { retryAfterSec: number; scope: 'minute' | 'day' } | null {
    this.sweep(now);
    const m = Math.floor(now / 60000), d = Math.floor(now / 86400000);
    const dm = this.day.get(key);
    if (dm && dm.win === d && dm.n >= this.opts.perDay) return { retryAfterSec: 86400 - Math.floor((now % 86400000) / 1000), scope: 'day' };
    const mm = this.minute.get(key);
    if (mm && mm.win === m && mm.n >= this.opts.perMinute) return { retryAfterSec: 60 - Math.floor((now % 60000) / 1000), scope: 'minute' };
    this.minute.set(key, mm && mm.win === m ? { win: m, n: mm.n + 1 } : { win: m, n: 1 });
    this.day.set(key, dm && dm.win === d ? { win: d, n: dm.n + 1 } : { win: d, n: 1 });
    return null;
  }
  private sweep(now: number) {
    if (now - this.lastSweep < 600000) return;
    this.lastSweep = now;
    const m = Math.floor(now / 60000), d = Math.floor(now / 86400000);
    for (const [k, v] of this.minute) if (v.win !== m) this.minute.delete(k);
    for (const [k, v] of this.day) if (v.win !== d) this.day.delete(k);
  }
}

/** 동시에 도는 비싼 작업 수를 제한한다 */
export class Gate {
  private n = 0;
  private max: number;
  constructor(max: number) { this.max = max; }
  get inFlight() { return this.n; }
  tryEnter(): boolean { if (this.n >= this.max) return false; this.n++; return true; }
  leave() { this.n = Math.max(0, this.n - 1); }
}

/** 같은 질문·시각·재료면 같은 결과를 돌려주는 캐시. 키는 해시만 두고 요청 본문은 저장하지 않는다 */
export class LruCache<V> {
  private map = new Map<string, { v: V; exp: number }>();
  private max: number; private ttlMs: number;
  constructor(max: number, ttlMs: number) { this.max = max; this.ttlMs = ttlMs; }
  get(key: string, now = Date.now()): V | undefined {
    const e = this.map.get(key);
    if (!e) return undefined;
    if (e.exp < now) { this.map.delete(key); return undefined; }
    this.map.delete(key); this.map.set(key, e); // 최근 사용으로
    return e.v;
  }
  set(key: string, v: V, now = Date.now()) {
    if (this.map.has(key)) this.map.delete(key);
    this.map.set(key, { v, exp: now + this.ttlMs });
    while (this.map.size > this.max) { const k = this.map.keys().next().value as string; this.map.delete(k); }
  }
  get size() { return this.map.size; }
}

/** 요청을 캐시 키로. 시각은 분 단위까지, 키 순서 고정 */
export function requestKey(req: Record<string, unknown>): string {
  const norm = (v: unknown): unknown => {
    if (Array.isArray(v)) return v.map(norm);
    if (v && typeof v === 'object') return Object.keys(v as object).sort().reduce((o, k) => { const x = (v as Record<string, unknown>)[k]; if (x !== undefined && x !== null) o[k] = norm(x); return o; }, {} as Record<string, unknown>);
    return v;
  };
  const q: Record<string, unknown> = { ...req, question: String(req.question ?? '').trim().replace(/\s+/g, ' ') };
  if (typeof q.datetime === 'string') q.datetime = q.datetime.slice(0, 16) + (q.datetime.match(/[+-]\d{2}:?\d{2}|Z$/)?.[0] ?? '');
  return createHash('sha256').update(JSON.stringify(norm(q))).digest('hex');
}

export interface UsageRecord { ts: string; kind: 'divine' | 'cast'; status: number; cached: boolean; model: string | null; input: number; output: number; cacheRead: number; cacheWrite: number; elapsedMs: number; safety: string; method: string; qtype: string }

/** 집계는 메모리, 선택적으로 JSONL 파일에 한 줄씩(질문 본문·IP 없음) */
export class UsageMeter {
  readonly startedAt = new Date().toISOString();
  counts = { divine: 0, cast: 0, cached: 0, refused: 0, errors: 0, rateLimited: 0, busy: 0 };
  tokens = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 };
  byDay = new Map<string, { divine: number; input: number; output: number }>();
  private logPath?: string;
  constructor(logPath?: string) { this.logPath = logPath; }
  record(r: UsageRecord) {
    if (r.kind === 'divine') this.counts.divine++; else this.counts.cast++;
    if (r.cached) this.counts.cached++;
    if (r.status >= 500) this.counts.errors++;
    this.tokens.input += r.input; this.tokens.output += r.output; this.tokens.cacheRead += r.cacheRead; this.tokens.cacheWrite += r.cacheWrite;
    const day = r.ts.slice(0, 10);
    const d = this.byDay.get(day) ?? { divine: 0, input: 0, output: 0 };
    if (r.kind === 'divine' && !r.cached) { d.divine++; d.input += r.input; d.output += r.output; }
    this.byDay.set(day, d);
    if (this.logPath) { try { appendFileSync(this.logPath, JSON.stringify(r) + '\n'); } catch { /* 로그 실패는 무시 */ } }
  }
  todayDivine(now = new Date()): number { return this.byDay.get(now.toISOString().slice(0, 10))?.divine ?? 0; }
  snapshot() {
    return { startedAt: this.startedAt, counts: this.counts, tokens: this.tokens, byDay: Object.fromEntries(this.byDay) };
  }
}

/** 클라이언트 IP: 프록시 뒤에서만 X-Forwarded-For 첫 값을 믿는다 */
export function clientIp(headers: Record<string, string | string[] | undefined>, remote: string | undefined, trustProxy: boolean): string {
  if (trustProxy) {
    const xf = headers['x-forwarded-for'];
    const first = (Array.isArray(xf) ? xf[0] : xf)?.split(',')[0]?.trim();
    if (first) return first;
  }
  return remote ?? 'unknown';
}

export function envInt(name: string, def: number): number {
  const v = process.env[name];
  const n = v === undefined ? NaN : Number(v);
  return Number.isFinite(n) && n >= 0 ? n : def;
}
