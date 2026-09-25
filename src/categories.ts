export const CATEGORIES = {
  'economy': { name: '기업 동향',    desc: '대구 기업·산단 소식과 공시·투자·채용 신호', hidden: false },
  'grants':  { name: '공모·지원사업', desc: '(보관) 공고는 글이 아니라 data/notices 에 데이터로만 남긴다', hidden: true },
  'policy':  { name: '산업 정책',    desc: '중앙부처·대구시 산업 정책과 예산, 정책제안 리포트', hidden: false },
} as const;
export type CategoryKey = keyof typeof CATEGORIES;
