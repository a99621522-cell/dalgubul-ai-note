/** 헤더 메뉴 10개('성장 계산기' /growth/·'상장기업' /listed/(DART 대구 본사 상장 회사)는 운영자 지시 2026-10-05 로 추가)('글' 목록·'공급망'은 메뉴에서 뺌, 운영자 지시 2026-09-27 — /posts/ 는 첫 화면 '전체 글' 링크로만). current 값은 Base.astro 의 current prop 과 맞춘다. '통계'(/stats/ 허브, 주제 6개 — 2026-10-02)는 운영자 지시 2026-10-01 로 메뉴에 올림. */
export const NAV = [
  { key: 'dashboard', name: '현황', href: '/dashboard/' },
  { key: 'explore', name: '탐색', href: '/explore/' },
  { key: 'industry', name: '산업별', href: '/industry/' },
  { key: 'stats', name: '통계', href: '/stats/' },
  { key: 'growth', name: '성장 계산기', href: '/growth/' },
  { key: 'companies', name: '기업 사전', href: '/companies/' },
  { key: 'listed', name: '상장기업', href: '/listed/' },
  { key: 'programs', name: '사업·예산', href: '/programs/' },
  { key: 'support', name: '지원 기업', href: '/support/' },
  { key: 'policy', name: '리포트', href: '/policy/' },
] as const;
