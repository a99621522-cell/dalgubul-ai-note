/** 헤더 메뉴 13개('지침 검토기' /programs/guidelines/check/ 는 리디자인 v3 2026-10-12, '지역중소기업' /sme/ 는 2026-10-12)('창업·벤처' /startups/ 는 2026-10-06)('성장 계산기' /growth/·'상장기업' /listed/(DART 대구 본사 상장 회사)는 운영자 지시 2026-10-05 로 추가)('글' 목록·'공급망'은 메뉴에서 뺌, 운영자 지시 2026-09-27 — /posts/ 는 첫 화면 '전체 글' 링크로만). current 값은 Base.astro 의 current prop 과 맞춘다. '통계'(/stats/ 허브, 주제 6개 — 2026-10-02)는 운영자 지시 2026-10-01 로 메뉴에 올림. */
export const NAV = [
  { key: 'stats', name: '통계 주제별', href: '/stats/' },
  { key: 'dashboard', name: '현황판', href: '/dashboard/' },
  { key: 'industry', name: '산업별 현황', href: '/industry/' },
  { key: 'explore', name: '자료 찾기(한 줄 질문)', href: '/explore/' },
  { key: 'companies', name: '기업 사전', href: '/companies/' },
  { key: 'startups', name: '창업·벤처', href: '/startups/' },   // 운영자 지시 2026-10-06 '벤처기업은 어디 있어?' → 기업 묶음에 바로가기
  { key: 'listed', name: '상장기업', href: '/listed/' },
  { key: 'sme', name: '지역중소기업', href: '/sme/' },   // 운영자 지시 2026-10-12 — 대구시 지역중소기업 명단(이름·업종뿐, 기업 사전과 따로)
  { key: 'support', name: '지원받은 기업', href: '/support/' },
  { key: 'programs', name: '부처 사업·예산', href: '/programs/' },
  { key: 'check', name: '사업계획서 지침 검토기', href: '/programs/guidelines/check/' },
  { key: 'policy', name: '리포트', href: '/policy/' },
  { key: 'growth', name: '성장 계산기', href: '/growth/' },
  { key: 'welfare', name: '복지서비스 찾기', href: '/welfare/' },   // 운영자 지시 2026-10-21 '복지분야 … 일단 해봐' — 복지로 오픈API, 창구용 후보 찾기
] as const;

/** 대메뉴 5개(리디자인 v3 2026-10-12, 운영자 '모두해' — 감사 보고서 docs/design/redesign-v3/01-audit.md 의 과업 이름 안: 통계 · 기업 · 사업·지원 · 리포트 · 성장 계산기).
 *  href 가 있는 묶음은 펼침 없이 바로 간다. current 키가 든 묶음이 선택 표시 */
export const NAV_GROUPS: { key: string; name: string; items: (typeof NAV)[number]['key'][]; href?: string }[] = [
  { key: 'data', name: '통계', items: ['stats', 'dashboard', 'industry', 'explore'] },
  { key: 'firms', name: '기업', items: ['companies', 'startups', 'listed', 'sme'] },
  { key: 'biz', name: '사업·지원', items: ['programs', 'check', 'support'] },
  { key: 'report', name: '리포트', items: ['policy'], href: '/policy/' },
  { key: 'growth', name: '성장 계산기', items: ['growth'], href: '/growth/' },
  { key: 'welfare', name: '복지', items: ['welfare'], href: '/welfare/' },
];
export const navItem = (key: string) => NAV.find(n => n.key === key)!;
/** 출처 기관 바로가기(유틸리티 바) — 다잇다가 자료를 받는 공공 누리집 */
export const UTIL_LINKS = [
  { name: '국가통계포털(KOSIS)', href: 'https://kosis.kr/' },
  { name: '전자공시(DART)', href: 'https://dart.fss.or.kr/' },
  { name: '공공데이터포털', href: 'https://www.data.go.kr/' },
  { name: '팩토리온', href: 'https://www.factoryon.go.kr/' },
];
