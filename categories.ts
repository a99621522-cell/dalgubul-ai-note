export const CATEGORIES = {
  'economy':   { name: '대구 경제',   desc: '대구 기업 현황과 시·국가 정책' },
  'grants':    { name: '공모·지원사업', desc: '마감이 다가오는 공모와 지원사업' },
  'ai-trends': { name: 'AI 동향',    desc: '한 주간의 AI·로봇 산업 소식과 중앙부처 발표' },
  'gov-ai':    { name: '공무원 AI',   desc: '업무별 AI 사용법과 AI 정부 실험실 기록' },
} as const;
export type CategoryKey = keyof typeof CATEGORIES;
