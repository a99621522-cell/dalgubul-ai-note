import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const posts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    category: z.enum(['economy', 'grants', 'policy']),
    summary: z.string(),
    source: z.string().optional(),        // 원문 기관명
    sourceUrl: z.string().url().optional(),
    deadline: z.coerce.date().optional(), // 공모사업 마감일
    draft: z.boolean().default(false),
    auto: z.boolean().default(false),     // AI 자동 초안 여부
    tags: z.array(z.string()).default([]),
    seoTitle: z.string().optional(),      // 검색용 제목(없으면 title 사용)
    description: z.string().optional(),   // 메타 설명 = 핵심 문장(없으면 summary 사용)
    faq: z.array(z.object({ q: z.string(), a: z.string() })).default([]), // AI 답변용 Q&A
    // 예산 원천: collect.py 가 공고 제목·소관부처를 부처 사업설명자료 DB(programs_*.csv)와 대조해 유사도 0.85 이상일 때 채움
    program_code: z.string().optional(),
    program_name: z.string().optional(),
    program_ministry: z.string().optional(),
    program_budget_2026: z.string().optional(), // 백만 원, 자료 값 그대로
    program_score: z.number().optional(),       // 대조 유사도 — 글에서 '자동 대조'임을 밝히는 데 씀
    // 정책제안 리포트 등 근거 목록. 실제로 확인한 페이지만
    sources: z.array(z.object({ title: z.string(), url: z.string(), date: z.string().optional(), kind: z.string().optional() })).default([]),   // kind: official/law/gov/report/news (brief 신뢰성 검사)
    // 정책제안 리포트 형식. report = 1~9절 개조식(2026-09-27 까지), insight = 산문형 인사이트 리포트(대표 그림·요약 상자·절 4~6개·그림, 2026-09-28 부터)
    format: z.enum(['report', 'insight', 'brief', 'full']).default('report'),   // full = 보고서형(2026-09-29, 브리프 논리 규칙 + 절·방안 수 확대) / brief = 대구정책 브리프식 개조식 정책 브리프(2026-09-29 부터, .claude/agents/policy-brief.md)
    outline: z.array(z.string()).default([]),            // insight: 요약 상자에 보이는 절 제목 4~6개
    hero: z.object({ prompt: z.string(), caption: z.string(), alt: z.string().optional() }).optional(), // insight: 대표 그림(Gemini 생성, scripts/gen_hero.py)
    authors: z.string().optional(),
  }),
});

export const collections = { posts };
