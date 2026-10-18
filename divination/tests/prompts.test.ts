// 프롬프트 내용 검증: 질문 유형마다 사안별 규칙이 있고, 분류기 용신 표의 이름이 모두 엔진에서 궁으로 풀린다.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { prompt } from '../src/llm/pipeline.ts';
import { QUESTION_TYPES } from '../src/llm/schemas.ts';
import { buildQimen } from '../src/qimen/index.ts';

test('매화 해석가 프롬프트에 질문 유형 10개의 사안별 규칙이 모두 있다', () => {
  const p = prompt('meihua');
  const sec = p.slice(p.indexOf('[사안별 규칙'));
  for (const t of QUESTION_TYPES) assert.ok(sec.includes(`- ${t}`), t);
  assert.match(sec, /失物占/); assert.match(sec, /약의 종류·귀신 설은 쓰지 않는다/);
});

test('분류기 용신 표의 이름은 모두 기문 엔진에서 궁으로 풀린다 (景門·驚門 한자 구분 포함)', () => {
  const p = prompt('classifier');
  const block = p.slice(p.indexOf('[기문둔갑 사안별 용신 표]'), p.indexOf('[safety_flag]'));
  const names = new Set<string>();
  const types: string[] = [];
  for (const line of block.split('\n')) {
    const m = /^- ([^:]+): (.+)$/.exec(line.trim());
    if (!m) continue;
    types.push(m[1]);
    for (const n of m[2].split(',')) names.add(n.trim());
  }
  assert.deepEqual(types, [...QUESTION_TYPES]);
  assert.ok(names.has('景門') && names.has('驚門'));
  const r = buildQimen({ pillars: { year: '丙午', month: '戊戌', day: '乙丑', hour: '癸未' }, term: { longitude: 195, name: '한로', at: '' }, matter: [...names] });
  for (const m of r.yongshinPalaces.matter) assert.ok(m.gong !== null && m.gong >= 1 && m.gong <= 9, `${m.name} 미해결`);
});

test('기문 해석가 프롬프트에 팔문·구성·팔신·삼기 뜻과 사안별 보기가 있다', () => {
  const p = prompt('qimen');
  for (const k of ['[팔문의 뜻', '[구성의 뜻', '[팔신의 뜻', '[삼기', '[사안별 보기]']) assert.ok(p.includes(k), k);
  for (const t of QUESTION_TYPES) assert.ok(p.includes(t), t);
});
