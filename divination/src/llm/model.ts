// 모델 호출 층. 파이프라인은 ModelCaller 만 알고, 실제 Anthropic 호출은 AnthropicCaller 가 맡는다(테스트는 가짜 호출자).
import Anthropic from '@anthropic-ai/sdk';
import { betaZodOutputFormat } from '@anthropic-ai/sdk/helpers/beta/zod';
import type { z } from 'zod';

export type Effort = 'low' | 'medium' | 'high' | 'xhigh' | 'max';
export type Stage = 'classifier' | 'meihua' | 'qimen' | 'synth' | 'reviewer';

export interface Usage { input: number; output: number; cacheRead: number; cacheWrite: number }
export const emptyUsage = (): Usage => ({ input: 0, output: 0, cacheRead: 0, cacheWrite: 0 });
export function addUsage(a: Usage, b: Usage): Usage {
  return { input: a.input + b.input, output: a.output + b.output, cacheRead: a.cacheRead + b.cacheRead, cacheWrite: a.cacheWrite + b.cacheWrite };
}

export interface TextCall { stage: Stage; system: string; user: string; effort: Effort; maxTokens: number }
export interface JsonCall<T> extends TextCall { schema: z.ZodType<T> }

export interface ModelCaller {
  text(call: TextCall): Promise<{ text: string; usage: Usage; model: string }>;
  json<T>(call: JsonCall<T>): Promise<{ data: T; usage: Usage; model: string }>;
}

export class RefusalError extends Error {
  stage: Stage;
  category: string | null;
  constructor(stage: Stage, category: string | null) {
    super(`모델이 ${stage} 단계 요청을 거절했습니다(${category ?? '분류 없음'})`);
    this.stage = stage; this.category = category;
  }
}

export const DEFAULT_MODEL = 'claude-opus-5-5';
const FALLBACK_BETA = 'server-side-fallback-2026-07-01';

function usageOf(u: Anthropic.Beta.BetaUsage): Usage {
  return { input: u.input_tokens, output: u.output_tokens, cacheRead: u.cache_read_input_tokens ?? 0, cacheWrite: u.cache_creation_input_tokens ?? 0 };
}

/** 실제 Anthropic API 호출. 시스템 프롬프트는 캐시 표시, 거절은 서버측 기본 대체 모델(fallbacks: "default")로 재시도 */
export class AnthropicCaller implements ModelCaller {
  private client: Anthropic;
  model: string;
  constructor(model: string = process.env.DIVINATION_MODEL ?? DEFAULT_MODEL, client?: Anthropic) {
    this.model = model;
    this.client = client ?? new Anthropic();
  }

  private params(call: TextCall) {
    return {
      model: this.model,
      max_tokens: call.maxTokens,
      betas: [FALLBACK_BETA],
      fallbacks: 'default' as const,
      output_config: { effort: call.effort },
      system: [{ type: 'text' as const, text: call.system, cache_control: { type: 'ephemeral' as const } }],
      messages: [{ role: 'user' as const, content: call.user }],
    };
  }

  async text(call: TextCall) {
    const res = await this.client.beta.messages.create(this.params(call));
    if (res.stop_reason === 'refusal') throw new RefusalError(call.stage, res.stop_details?.category ?? null);
    if (res.stop_reason === 'max_tokens') throw new Error(`${call.stage}: 출력이 max_tokens 에서 잘렸습니다`);
    const text = res.content.filter((b): b is Anthropic.Beta.BetaTextBlock => b.type === 'text').map((b) => b.text).join('\n').trim();
    return { text, usage: usageOf(res.usage), model: res.model };
  }

  async json<T>(call: JsonCall<T>) {
    const res = await this.client.beta.messages.parse({
      ...this.params(call),
      output_config: { effort: call.effort, format: betaZodOutputFormat(call.schema) },
    });
    if (res.stop_reason === 'refusal') throw new RefusalError(call.stage, res.stop_details?.category ?? null);
    if (res.parsed_output == null) throw new Error(`${call.stage}: 구조화 출력 파싱 실패`);
    return { data: res.parsed_output as T, usage: usageOf(res.usage), model: res.model };
  }
}
