/** 지자체 한 곳 전용 사이트(운영자 지시 2026-11-08 '수성구만의 별도의 사이트 만들어'): 빌드 때 VAT_GOV=suseong 이면
 *  예시 설정·지자체 프로필·세입예산서·공개 지출·나라장터 계약을 그 지자체 것만 내보낸다(.github/workflows/deploy_vat_gov.yml). 비우면 전부. */
export const VAT_GOV = (process.env.VAT_GOV || '').trim();
export const lockGov = <T extends { key: string }>(L: T[]): T[] => (VAT_GOV ? L.filter(x => x.key === VAT_GOV) : L);
