import { defineConfig } from 'astro/config';
import remarkGfm from 'remark-gfm';

// 바로 이어진 각주 번호([^1][^2]) 사이에 쉼표를 넣는다 — 붙어 있으면 "12" 로 읽힌다
const isRef = (n) => n?.type === 'element' && n.tagName === 'sup' && n.children?.some((c) => c.type === 'element' && c.tagName === 'a' && 'dataFootnoteRef' in (c.properties || {}));
function rehypeFootnoteComma() {
  const walk = (node) => {
    if (!node.children) return;
    for (let i = node.children.length - 1; i > 0; i--) {
      if (isRef(node.children[i]) && isRef(node.children[i - 1])) node.children.splice(i, 0, { type: 'element', tagName: 'sup', properties: { className: ['fn-sep'] }, children: [{ type: 'text', value: ',' }] });
    }
    node.children.forEach(walk);
  };
  return walk;
}

export default defineConfig({
  site: 'https://note.daitda.co.kr',
  output: 'static',
  // 기본 GFM 은 '10~49인' 의 물결표 하나를 취소선으로 읽는다 → 두 개(~~)일 때만 취소선
  markdown: { gfm: false, remarkPlugins: [[remarkGfm, { singleTilde: false }]], remarkRehype: { footnoteLabel: '각주', footnoteBackLabel: '본문으로' }, rehypePlugins: [rehypeFootnoteComma] },
});
