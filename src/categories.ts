export const CATEGORIES = {
  'economy': { name: '기업 동향',    desc: '대구 기업·산단 소식과 공시·투자·채용 신호' },
  'grants':  { name: '공모·지원사업', desc: '마감이 다가오는 공모와 기업·인력양성 지원사업' },
  'policy':  { name: '산업 정책',    desc: '중앙부처·대구시 산업 정책과 예산, 규제 변화' },
} as const;
export type CategoryKey = keyof typeof CATEGORIES;
