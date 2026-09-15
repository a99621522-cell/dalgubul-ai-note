import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const posts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    category: z.enum(['economy', 'grants', 'ai-trends', 'gov-ai']),
    summary: z.string(),
    source: z.string().optional(),        // 원문 기관명
    sourceUrl: z.string().url().optional(),
    deadline: z.coerce.date().optional(), // 공모사업 마감일
    draft: z.boolean().default(false),
    auto: z.boolean().default(false),     // AI 자동 초안 여부
    tags: z.array(z.string()).default([]),
    seoTitle: z.string().optional(),      // 검색용 제목(없으면 title 사용)
    description: z.string().optional(),   // 메타 설명(없으면 summary 사용)
  }),
});

export const collections = { posts };
