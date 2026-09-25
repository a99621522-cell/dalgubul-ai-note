/** 헤더 메뉴 5개. current 값은 Base.astro 의 current prop 과 맞춘다. */
export const NAV = [
  { key: 'dashboard', name: '현황', href: '/dashboard/' },
  { key: 'industry', name: '산업별', href: '/industry/' },
  { key: 'companies', name: '기업 사전', href: '/companies/' },
  { key: 'programs', name: '사업·예산', href: '/programs/' },
  { key: 'posts', name: '글', href: '/posts/' },
] as const;
