import { defineConfig } from 'astro/config';
import remarkGfm from 'remark-gfm';

export default defineConfig({
  site: 'https://note.daitda.co.kr',
  output: 'static',
  // 기본 GFM 은 '10~49인' 의 물결표 하나를 취소선으로 읽는다 → 두 개(~~)일 때만 취소선
  markdown: { gfm: false, remarkPlugins: [[remarkGfm, { singleTilde: false }]] },
});
