// 운영 보조 모듈: 요청 제한·동시 실행·캐시·키·사용량·IP
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { RateLimiter, Gate, LruCache, requestKey, UsageMeter, clientIp } from '../src/llm/ops.ts';

test('RateLimiter: 분당·일별 창, 창이 바뀌면 풀린다', () => {
  const rl = new RateLimiter({ perMinute: 2, perDay: 3 });
  const t0 = Date.UTC(2026, 9, 19, 0, 0, 10);
  assert.equal(rl.hit('a', t0), null); assert.equal(rl.hit('a', t0), null);
  const r = rl.hit('a', t0)!; assert.equal(r.scope, 'minute'); assert.ok(r.retryAfterSec > 0 && r.retryAfterSec <= 60);
  assert.equal(rl.hit('b', t0), null); // 다른 IP 는 독립
  assert.equal(rl.hit('a', t0 + 60000), null); // 다음 분
  const d = rl.hit('a', t0 + 120000)!; assert.equal(d.scope, 'day'); // 하루 3번째를 넘김
  assert.equal(rl.hit('a', t0 + 86400000), null); // 다음 날
});

test('Gate: 동시 실행 수 제한', () => {
  const g = new Gate(2);
  assert.ok(g.tryEnter()); assert.ok(g.tryEnter()); assert.ok(!g.tryEnter()); g.leave(); assert.ok(g.tryEnter()); assert.equal(g.inFlight, 2);
});

test('LruCache: TTL 과 최대 항목, 최근 사용 우선', () => {
  const c = new LruCache<number>(2, 1000);
  c.set('a', 1, 0); c.set('b', 2, 0);
  assert.equal(c.get('a', 10), 1); // a 를 최근으로
  c.set('c', 3, 20); // b 가 밀려남
  assert.equal(c.get('b', 30), undefined); assert.equal(c.get('a', 30), 1); assert.equal(c.get('c', 30), 3);
  assert.equal(c.get('a', 2000), undefined); // TTL 지남
});

test('requestKey: 공백·키 순서·초 단위 차이는 같은 키, 질문이 다르면 다른 키', () => {
  const a = requestKey({ question: '이직  할까요', datetime: '2026-10-19T07:30:15+09:00', method: 'both', options: { ziHour: '23', tzOffsetMin: 540 } });
  const b = requestKey({ options: { tzOffsetMin: 540, ziHour: '23' }, method: 'both', datetime: '2026-10-19T07:30:59+09:00', question: ' 이직 할까요 ' });
  assert.equal(a, b);
  assert.notEqual(a, requestKey({ question: '이직 할까요', datetime: '2026-10-19T07:31:00+09:00', method: 'both' }));
  assert.notEqual(a, requestKey({ question: '결혼 할까요', datetime: '2026-10-19T07:30:15+09:00', method: 'both' }));
});

test('UsageMeter: 집계에 질문·IP 가 없고 하루 건수가 센다', () => {
  const m = new UsageMeter();
  m.record({ ts: '2026-10-19T01:00:00Z', kind: 'divine', status: 200, cached: false, model: 'x', input: 100, output: 20, cacheRead: 0, cacheWrite: 0, elapsedMs: 10, safety: 'none', method: 'both', qtype: '재물·투자' });
  m.record({ ts: '2026-10-19T02:00:00Z', kind: 'divine', status: 200, cached: true, model: 'x', input: 0, output: 0, cacheRead: 0, cacheWrite: 0, elapsedMs: 1, safety: 'none', method: 'both', qtype: '재물·투자' });
  const s = m.snapshot();
  assert.equal(s.counts.divine, 2); assert.equal(s.counts.cached, 1); assert.equal(s.tokens.input, 100);
  assert.equal(m.todayDivine(new Date('2026-10-19T05:00:00Z')), 1);
  assert.ok(!JSON.stringify(s).includes('question'));
});

test('clientIp: 프록시 신뢰 여부', () => {
  assert.equal(clientIp({ 'x-forwarded-for': '1.2.3.4, 10.0.0.1' }, '10.0.0.9', true), '1.2.3.4');
  assert.equal(clientIp({ 'x-forwarded-for': '1.2.3.4' }, '10.0.0.9', false), '10.0.0.9');
});
