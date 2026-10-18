// LLM 단계의 구조화 출력 스키마(zod). 분류기와 검수자는 JSON, 해석가·편집자는 마크다운 글.
import { z } from 'zod';

export const QUESTION_TYPES = ['재물', '직장·사업', '시험·학업', '혼인·연애', '건강', '이동·여행', '소송·분쟁', '분실물·사람찾기', '날씨', '일반'] as const;
export const SAFETY_FLAGS = ['none', 'health', 'legal', 'finance', 'self_harm', 'minor'] as const;

export const ClassificationSchema = z.object({
  question_type: z.enum(QUESTION_TYPES),
  time_horizon: z.enum(['오늘', '이번주', '이번달', '올해', '미정']),
  subject: z.enum(['본인', '상대방', '제3자']),
  method: z.enum(['meihua', 'qimen']),
  method_reason: z.string(),
  qimen_yongshin: z.array(z.string()),
  needs_more_input: z.array(z.string()),
  safety_flag: z.enum(SAFETY_FLAGS),
});
export type Classification = z.infer<typeof ClassificationSchema>;

export const ReviewSchema = z.object({
  text: z.string(),
  changes: z.array(z.string()),
});
export type Review = z.infer<typeof ReviewSchema>;
