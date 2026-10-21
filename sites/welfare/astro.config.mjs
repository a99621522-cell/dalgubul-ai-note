import { defineConfig } from 'astro/config';
// 대구 복지서비스 찾기 — 복지 공무원용 독립 사이트(운영자 지시 2026-10-21 '다잇다 말고 다른 사이트로').
// 다잇다 저장소 안에 있지만 따로 빌드·배포한다: npx astro build --root sites/welfare → sites/welfare/dist → Cloudflare Pages 프로젝트 daegu-welfare
export default defineConfig({ site: 'https://daegu-welfare.pages.dev', output: 'static' });
