// 해석 파이프라인: 분류 → 계산(코드) → 해석(매화·기문 병렬) → 종합 → 검수.
// 모델 호출은 ModelCaller 로 주입한다. 계산 JSON 밖의 값은 프롬프트 규칙과 검수자가 거른다.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { castMeihua, castQimen, type MeihuaChart, type QimenChart, type TimeOptions } from '../index.ts';
import { ClassificationSchema, ReviewSchema, type Classification } from './schemas.ts';
import { addUsage, emptyUsage, type ModelCaller, type Usage } from './model.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const promptCache = new Map<string, string>();
export function prompt(name: 'classifier' | 'meihua' | 'qimen' | 'synth' | 'reviewer' | 'crisis'): string {
  let p = promptCache.get(name);
  if (!p) { p = readFileSync(path.join(here, 'prompts', `${name}.md`), 'utf8').trim(); promptCache.set(name, p); }
  return p;
}

export type Method = 'auto' | 'meihua' | 'qimen' | 'both';

export interface DivinationRequest {
  question: string;
  /** ISO 8601. 없으면 지금(KST) */
  datetime?: string;
  longitude?: number;
  latitude?: number;
  material?: { numbers?: number[]; text?: string; strokeTable?: Record<string, number>; object?: string; direction?: string };
  /** 질문자 생년 간지(년명). 선택 */
  yearMing?: string | null;
  externalSigns?: string | null;
  /** 기본 both. auto 는 분류기가 고른 술법 하나 */
  method?: Method;
  options?: TimeOptions;
  /** 검수 단계 생략(디버그) */
  skipReview?: boolean;
}

export interface DivinationResult {
  question: string;
  classification: Classification;
  methodUsed: Exclude<Method, 'auto'>;
  charts: { meihua?: MeihuaChart; qimen?: QimenChart };
  readings: { meihua?: string; qimen?: string; synth?: string };
  review: { changes: string[] } | null;
  final: string;
  safety: { flag: Classification['safety_flag']; stopped: boolean };
  usage: Usage;
  model: string | null;
  elapsedMs: number;
}

export function nowIso(tzOffsetMin = 540): string {
  const d = new Date(Date.now() + tzOffsetMin * 60000);
  const p = (n: number) => String(n).padStart(2, '0');
  const sign = tzOffsetMin >= 0 ? '+' : '-';
  const a = Math.abs(tzOffsetMin);
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}T${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}${sign}${p(Math.floor(a / 60))}:${p(a % 60)}`;
}

/** 계산만(LLM 없음). 화면에서 괘·국을 먼저 보여 줄 때 */
export function castOnly(req: DivinationRequest, method: Exclude<Method, 'auto'> = 'both'): DivinationResult['charts'] {
  const datetime = req.datetime ?? nowIso(req.options?.tzOffsetMin ?? 540);
  const base = { datetime, longitude: req.longitude, latitude: req.latitude, options: req.options };
  const charts: DivinationResult['charts'] = {};
  if (method !== 'qimen') charts.meihua = castMeihua({ ...base, material: req.material });
  if (method !== 'meihua') charts.qimen = castQimen({ ...base, yearMing: req.yearMing ?? null });
  return charts;
}

export async function runDivination(req: DivinationRequest, caller: ModelCaller): Promise<DivinationResult> {
  const t0 = Date.now();
  let usage = emptyUsage();
  let model: string | null = null;
  if (!req.question || !req.question.trim()) throw new Error('질문이 비어 있습니다');

  // 1. 분류
  const cls = await caller.json({
    stage: 'classifier', system: prompt('classifier'), effort: 'low', maxTokens: 1024,
    schema: ClassificationSchema, user: `질문: ${req.question.trim()}`,
  });
  usage = addUsage(usage, cls.usage); model = cls.model;
  const classification = cls.data;

  // 안전: 자해·자살 암시는 점 풀이를 멈춘다
  if (classification.safety_flag === 'self_harm') {
    return {
      question: req.question, classification, methodUsed: 'both', charts: {}, readings: {}, review: null,
      final: prompt('crisis'), safety: { flag: 'self_harm', stopped: true }, usage, model, elapsedMs: Date.now() - t0,
    };
  }

  // 2. 계산
  const methodUsed: Exclude<Method, 'auto'> = (req.method ?? 'both') === 'auto' ? classification.method : (req.method ?? 'both') as Exclude<Method, 'auto'>;
  const datetime = req.datetime ?? nowIso(req.options?.tzOffsetMin ?? 540);
  const base = { datetime, longitude: req.longitude, latitude: req.latitude, options: req.options };
  const charts: DivinationResult['charts'] = {};
  if (methodUsed !== 'qimen') charts.meihua = castMeihua({ ...base, material: req.material });
  if (methodUsed !== 'meihua') charts.qimen = castQimen({ ...base, yearMing: req.yearMing ?? null, matter: classification.qimen_yongshin });

  // 3. 해석(병렬)
  const common = { question: req.question.trim(), questionType: classification.question_type, timeHorizon: classification.time_horizon, subject: classification.subject, safetyFlag: classification.safety_flag };
  const jobs: Array<Promise<void>> = [];
  const readings: DivinationResult['readings'] = {};
  if (charts.meihua) {
    jobs.push(caller.text({
      stage: 'meihua', system: prompt('meihua'), effort: 'medium', maxTokens: 4000,
      user: JSON.stringify({ ...common, externalSigns: req.externalSigns ?? null, chart: charts.meihua }, null, 1),
    }).then((r) => { readings.meihua = r.text; usage = addUsage(usage, r.usage); }));
  }
  if (charts.qimen) {
    jobs.push(caller.text({
      stage: 'qimen', system: prompt('qimen'), effort: 'medium', maxTokens: 5000,
      user: JSON.stringify({ ...common, yongshinHint: classification.qimen_yongshin, chart: charts.qimen }, null, 1),
    }).then((r) => { readings.qimen = r.text; usage = addUsage(usage, r.usage); }));
  }
  await Promise.all(jobs);

  // 4. 종합(둘 다 있을 때만)
  let draft: string;
  if (readings.meihua && readings.qimen) {
    const s = await caller.text({
      stage: 'synth', system: prompt('synth'), effort: 'medium', maxTokens: 4000,
      user: JSON.stringify({ question: common.question, questionType: common.questionType, meihua: readings.meihua, qimen: readings.qimen }, null, 1),
    });
    usage = addUsage(usage, s.usage); readings.synth = s.text; draft = s.text;
  } else {
    draft = readings.meihua ?? readings.qimen ?? '';
  }

  // 5. 검수
  let review: DivinationResult['review'] = null;
  let final = draft;
  if (!req.skipReview) {
    const r = await caller.json({
      stage: 'reviewer', system: prompt('reviewer'), effort: 'low', maxTokens: 6000, schema: ReviewSchema,
      user: JSON.stringify({ charts, text: draft }, null, 1),
    });
    usage = addUsage(usage, r.usage);
    review = { changes: r.data.changes };
    if (r.data.text && r.data.text.trim()) final = r.data.text.trim();
  }
  if (!/참고|오락/.test(final)) final += '\n\n## 유의\n이 풀이는 참고·오락용입니다.';

  return {
    question: req.question, classification, methodUsed, charts, readings, review, final,
    safety: { flag: classification.safety_flag, stopped: false }, usage, model, elapsedMs: Date.now() - t0,
  };
}
