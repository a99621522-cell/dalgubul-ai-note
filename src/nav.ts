/** 헤더 메뉴 11개('창업·벤처' /startups/ 는 2026-10-06)('성장 계산기' /growth/·'상장기업' /listed/(DART 대구 본사 상장 회사)는 운영자 지시 2026-10-05 로 추가)('글' 목록·'공급망'은 메뉴에서 뺌, 운영자 지시 2026-09-27 — /posts/ 는 첫 화면 '전체 글' 링크로만). current 값은 Base.astro 의 current prop 과 맞춘다. '통계'(/stats/ 허브, 주제 6개 — 2026-10-02)는 운영자 지시 2026-10-01 로 메뉴에 올림. */
export const NAV = [
  { key: 'dashboard', name: '현황', href: '/dashboard/' },
  { key: 'explore', name: '탐색', href: '/explore/' },
  { key: 'industry', name: '산업별', href: '/industry/' },
  { key: 'stats', name: '통계', href: '/stats/' },
  { key: 'growth', name: '성장 계산기', href: '/growth/' },
  { key: 'companies', name: '기업 사전', href: '/companies/' },
  { key: 'startups', name: '창업·벤처', href: '/startups/' },   // 운영자 지시 2026-10-06 '벤처기업은 어디 있어?' → 기업 묶음에 바로가기
  { key: 'listed', name: '상장기업', href: '/listed/' },
  { key: 'programs', name: '사업·예산', href: '/programs/' },
  { key: 'support', name: '지원 기업', href: '/support/' },
  { key: 'policy', name: '리포트', href: '/policy/' },
] as const;

/** 헤더 묶음 4개(디자인·UI 개선 2026-10-06: 1단 메뉴 10개 → 묶음 4개 + 펼침, 모바일은 드로어). current 키가 든 묶음이 열린 표시 */
export const NAV_GROUPS: { key: string; name: string; items: (typeof NAV)[number]['key'][]; href?: string }[] = [
  { key: 'data', name: '현황·통계', items: ['dashboard', 'explore', 'industry', 'stats'] },
  { key: 'firms', name: '기업', items: ['companies', 'startups', 'listed', 'support'] },
  { key: 'biz', name: '사업·리포트', items: ['programs', 'policy'] },
  { key: 'growth', name: '성장 계산기', items: ['growth'], href: '/growth/' },
];
export const navItem = (key: string) => NAV.find(n => n.key === key)!;
