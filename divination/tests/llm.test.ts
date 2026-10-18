// 파이프라인 검증(모델 호출은 가짜). 단계 순서·안전 분기·종합 조건·검수 반영·호출 내용에 계산 JSON 이 들어가는지 본다.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { runDivination, castOnly, prompt } from '../src/llm/pipeline.ts';
import type { ModelCaller, TextCall, JsonCall, Usage } from '../src/llm/model.ts';
import { ClassificationSchema, ReviewSchema } from '../src/llm/schemas.ts';

const u: Usage = { input: 10, output: 5, cacheRead: 0, cacheWrite: 0 };
const baseCls = { question_type: '취업·이직', time_horizon: '이번달', subject: '본인', method: 'qimen', method_reason: '시기 선택', qimen_yongshin: ['개문', '일간'], needs_more_input: [], safety_flag: 'none' };

function fake(overrides: { cls?: Partial<typeof baseCls>; review?: { text: string; changes: string[] } | null } = {}) {
  const calls: Array<TextCall | JsonCall<unknown>> = [];
  const caller: ModelCaller = {
    async text(call) {
      calls.push(call);
      const head = call.stage === 'meihua' ? '## 한 줄 판단\n소길' : call.stage === 'qimen' ? '## 한 줄 판단\n평' : '## 한 줄 답\n종합';
      return { text: `${head}\n[${call.stage}]\n## 유의\n이 풀이는 참고·오락용입니다.`, usage: u, model: 'fake' };
    },
    async json<T>(call: JsonCall<T>) {
      calls.push(call);
      if (call.stage === 'classifier') return { data: ClassificationSchema.parse({ ...baseCls, ...overrides.cls }) as T, usage: u, model: 'fake' };
      if (call.stage === 'reviewer') {
        const parsed = JSON.parse(call.user) as { text: string };
        const r = overrides.review === undefined ? { text: parsed.text, changes: [] } : overrides.review ?? { text: parsed.text, changes: [] };
        return { data: ReviewSchema.parse(r) as T, usage: u, model: 'fake' };
      }
      throw new Error('unexpected stage');
    },
  };
  return { caller, calls };
}

test('프롬프트 파일 5개 + 위기 문구가 읽힌다', () => {
  for (const n of ['classifier', 'meihua', 'qimen', 'synth', 'reviewer', 'crisis'] as const) assert.ok(prompt(n).length > 50, n);
  assert.match(prompt('crisis'), /109/);
});

test('both: 분류 → 매화·기문 해석 → 종합 → 검수 순서로 호출되고 계산 JSON 이 해석가에게 간다', async () => {
  const { caller, calls } = fake();
  const r = await runDivination({ question: '이번 달 이직 제안을 받아들여도 될까요', datetime: '2026-10-18T14:30:00+09:00' }, caller);
  assert.deepEqual(calls.map((c) => c.stage), ['classifier', 'meihua', 'qimen', 'synth', 'reviewer']);
  const mh = JSON.parse((calls[1] as TextCall).user);
  assert.equal(mh.chart.benGua.hanja, r.charts.meihua!.benGua.hanja);
  const qm = JSON.parse((calls[2] as TextCall).user);
  assert.equal(qm.chart.ju.number, r.charts.qimen!.ju.number);
  assert.deepEqual(qm.yongshinHint, ['개문', '일간']);
  assert.ok(r.charts.qimen!.yongshinPalaces.matter.some((m) => m.name === '개문'));
  const sy = JSON.parse((calls[3] as TextCall).user);
  assert.match(sy.meihua, /\[meihua\]/); assert.match(sy.qimen, /\[qimen\]/);
  assert.equal(r.methodUsed, 'both');
  assert.match(r.final, /종합/);
  assert.equal(r.usage.input, 50);
  assert.equal(r.safety.stopped, false);
});

test('auto: 분류기가 고른 술법 하나만 쓰고 종합 단계는 건너뛴다', async () => {
  const { caller, calls } = fake({ cls: { method: 'meihua' } });
  const r = await runDivination({ question: '잃어버린 지갑을 찾을 수 있을까', datetime: '2026-10-18T14:30:00+09:00', method: 'auto' }, caller);
  assert.deepEqual(calls.map((c) => c.stage), ['classifier', 'meihua', 'reviewer']);
  assert.equal(r.methodUsed, 'meihua');
  assert.equal(r.charts.qimen, undefined);
  assert.match(r.final, /\[meihua\]/);
});

test('self_harm: 계산·해석 없이 위기 안내만 돌려준다', async () => {
  const { caller, calls } = fake({ cls: { safety_flag: 'self_harm' } });
  const r = await runDivination({ question: '…', datetime: '2026-10-18T14:30:00+09:00' }, caller);
  assert.deepEqual(calls.map((c) => c.stage), ['classifier']);
  assert.equal(r.safety.stopped, true);
  assert.match(r.final, /109/);
  assert.deepEqual(r.charts, {});
});

test('검수자가 고친 글과 변경 목록이 결과에 반영된다', async () => {
  const { caller } = fake({ review: { text: '## 한 줄 답\n고친 글\n## 유의\n참고·오락용', changes: ['단정 표현 삭제'] } });
  const r = await runDivination({ question: '시험에 붙을까', datetime: '2026-10-18T14:30:00+09:00' }, caller);
  assert.equal(r.final, '## 한 줄 답\n고친 글\n## 유의\n참고·오락용');
  assert.deepEqual(r.review, { changes: ['단정 표현 삭제'] });
});

test('skipReview 면 검수자를 부르지 않고, 참고·오락용 문구가 없으면 덧붙인다', async () => {
  const { calls, caller } = fake();
  caller.text = async (call) => { calls.push(call); return { text: `## 한 줄 판단\n길\n[${call.stage}]`, usage: u, model: 'fake' }; };
  const r = await runDivination({ question: '계약이 성사될까', datetime: '2026-10-18T14:30:00+09:00', method: 'qimen', skipReview: true }, caller);
  assert.deepEqual(calls.map((c) => c.stage), ['classifier', 'qimen']);
  assert.match(r.final, /참고·오락용/);
});

test('castOnly 는 모델 없이 괘·국만 돌려주고 같은 입력이면 같은 결과', () => {
  const a = castOnly({ question: 'x', datetime: '2026-10-18T14:30:00+09:00', material: { numbers: [37, 58] } });
  const b = castOnly({ question: 'x', datetime: '2026-10-18T14:30:00+09:00', material: { numbers: [37, 58] } });
  assert.deepEqual(a, b);
  assert.equal(a.meihua!.meta.method, 'number');
  assert.equal(a.qimen!.palaces.length, 9);
});

test('빈 질문은 오류', async () => {
  const { caller } = fake();
  await assert.rejects(() => runDivination({ question: '  ' }, caller), /비어/);
});

test('eval: 한 줄 답에서 방향을 뽑고 금지어를 잡는다', async () => {
  const { direction, FORBIDDEN } = await import('../src/llm/eval.ts');
  assert.equal(direction('## 한 줄 답\n소길입니다. 늦더라도 성사됩니다.'), '소길');
  assert.equal(direction('## 한 줄 판단\n흉: 체가 극을 받습니다'), '흉');
  assert.equal(direction('## 한 줄 답\n평 — 아직 비어 있습니다'), '평');
  assert.ok(FORBIDDEN.test('반드시 오릅니다'));
  assert.ok(!FORBIDDEN.test('괘상은 좋게 읽힙니다'));
});
