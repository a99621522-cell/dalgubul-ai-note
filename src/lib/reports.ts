/** 정책제안 리포트 목록과 내려받기 주소. 발행(draft:false)·category policy·태그 '정책제안' 인 글만. */
import { getCollection, type CollectionEntry } from 'astro:content';
import type { ReportMeta } from './docx';
import fs from 'node:fs';

export const SITE = 'https://note.daitda.co.kr';
export async function policyReports(): Promise<CollectionEntry<'posts'>[]> {
  const all = await getCollection('posts', p => !p.data.draft && p.data.category === 'policy' && (p.data.tags ?? []).includes('정책제안'));
  return all.sort((a, b) => b.data.date.getTime() - a.data.date.getTime());
}
export const isReport = (p: CollectionEntry<'posts'>) => !p.data.draft && p.data.category === 'policy' && (p.data.tags ?? []).includes('정책제안');
/** 분야 = 태그 두 번째 값(첫 번째는 '정책제안') */
export const reportArea = (p: CollectionEntry<'posts'>) => (p.data.tags ?? []).find(t => t !== '정책제안');
/** HWPX 는 scripts/hwpx_report.py 가 public/hwpx/ 에 미리 만들어 둔 것만 링크한다(빌드 때 파일 유무 확인). */
export const downloadUrls = (id: string) => ({
  docx: `/policy/download/${id}.docx`, md: `/policy/download/${id}.md`,
  hwpx: fs.existsSync(`public/hwpx/${id}.hwpx`) ? `/hwpx/${id}.hwpx` : '',
  hwpxSummary: fs.existsSync(`public/hwpx/${id}-요약.hwpx`) ? `/hwpx/${encodeURIComponent(id + '-요약')}.hwpx` : '',
});
export const reportMeta = (p: CollectionEntry<'posts'>): ReportMeta => ({
  title: p.data.title, date: p.data.date, area: reportArea(p), description: p.data.description, summary: p.data.summary,
  url: `${SITE}/posts/${p.id}/`, faq: p.data.faq, sources: p.data.sources,
  format: p.data.format, outline: p.data.outline, hero: p.data.hero ? { caption: p.data.hero.caption, path: `public/figures/${p.id}/hero.png` } : undefined,
});
