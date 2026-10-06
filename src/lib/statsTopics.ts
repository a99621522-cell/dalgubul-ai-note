/** 통계 메뉴 구조(운영자 지적 2026-10-02: 통계가 복잡하고 분류가 없다). 통계를 주제 6개로 나누고 KOSIS 표·그래프(src/generated/kosis)를 주제에 배정한다.
 *  /stats/ 허브 카드, 각 주제 페이지 위 탭(StatsNav), 주제 페이지(KosisSections)가 이 목록을 읽는다. */
export type StatsTopic = { key: string; name: string; href: string; period: string; desc: string };
export const TOPICS: StatsTopic[] = [
  { key: 'monthly', name: '경기 동향', href: '/stats/monthly/', period: '월간', desc: '생산·고용·소비·투자·금융·경기지수를 한 화면에. 선행·동행·후행 구분과 1월부터 추세.' },
  { key: 'trade', name: '수출입', href: '/stats/trade/', period: '월간', desc: '대구·경북(세관)과 전국(산업통상부) 수출입을 같은 달로 비교. 품목·국가별.' },
  { key: 'manufacturing', name: '제조업', href: '/stats/manufacturing/', period: '월간·연간', desc: '업종별 생산·출하·재고지수, 업종별 출하액·부가가치, 사업체·종사자·취업자, 의료기기 생산·수출입.' },
  { key: 'services', name: '서비스업·자영업', href: '/stats/services/', period: '분기·월간', desc: '업종별 서비스업 생산지수, 대형소매점 판매, 자영업자 수·비중, 소상공인·전통시장 체감경기, 관광 방문자·소비.' },
  { key: 'industry', name: '산업 구조', href: '/stats/industry/', period: '연간', desc: '지역내총생산, 부문별 부가가치·입지계수, 17개 시도 산업구조 지표, 성장 계산기 바로가기.' },
  { key: 'business', name: '기업·사업체', href: '/stats/business/', period: '연간', desc: '산업별 사업체·종사자, 중소기업·소상공인, 수출입 활동기업.' },
  { key: 'population', name: '인구·고용', href: '/stats/population/', period: '연간', desc: '인구·취업자·고용률 연간 추이, 구·군별 인구·취업자, 연령별 순이동, 소매판매.' },
];

export type KosisSection = { key?: string; title: string; desc: string; tables: string[]; charts: string[] };   // key: 페이지가 절 뒤에 다른 컴포넌트를 끼울 때 슬롯 이름(after-<key>)
/** 주제별 KOSIS 묶음. 표 id·그래프 이름은 scripts/render_kosis.py 산출물(src/generated/kosis/index.json). */
export const KOSIS_TOPICS: Record<string, KosisSection[]> = {
  manufacturing: [
    { title: '업종별 생산·출하·재고지수 (월간)', desc: '광업제조업동향조사의 대구 업종별 생산·출하·재고지수(원지수, 2020=100)와 전년 같은 달 대비, 주요 업종 생산지수 추이.', tables: ['mfg_index_industry'], charts: ['mfg-index', 'mfg-index-industry'] },
    { title: '업종별 출하액·부가가치 (광업·제조업조사)', desc: '종사자 10명 이상 사업체의 제조업 중분류별 사업체 수·출하액·생산액·부가가치와 연도별 추이.', tables: ['mining_mfg_daegu'], charts: ['mfg-total-years', 'mfg-value-added'] },
    { title: '업종별 사업체·종사자 (전국사업체조사)', desc: '제조업 중분류별 사업체 수·종사자 수, 2020년부터 연도별.', tables: ['census_mfg_years'], charts: [] },
    { title: '업종별 취업자 (지역별고용조사)', desc: '제조업 중분류 취업자와 전국 대비 비중.', tables: ['employed_mfg'], charts: [] },
  ],
  industry: [
    { title: '경제활동별 지역내총생산', desc: '대구 경제활동별 명목·실질 지역내총생산과 실질 기여도.', tables: ['grdp_daegu'], charts: [] },
    { title: '부문별 부가가치와 입지계수', desc: '대구 총부가가치 24개 부문의 비중과 전국 대비 입지계수(2015년 대비), 고부가 3부문 비중 추이.', tables: ['daegu_sectors'], charts: ['lq-daegu', 'high-share'] },
    { title: '17개 시도 산업구조 지표', desc: '지역소득(시도별 경제활동별 총부가가치, 24개 부문)으로 이 사이트가 계산한 입지계수·산업집중도·산업구조 변화속도. 정의는 저장소 scripts/structure_index.py.', tables: ['structure17'], charts: ['hhi17'] },
  ],
  business: [
    { title: '산업별 사업체·종사자 (전국사업체조사)', desc: '대구 산업 대·중분류별 사업체 수·종사자 수와 종사자 비중의 전국 대비 입지계수.', tables: ['census_daegu'], charts: ['lq-employment'] },
    { title: '산업별 기업·종사자 (중소기업기본통계)', desc: '산업중분류별 전체 기업·중소기업·소상공인 수와 종사자 수. 행정통계라 개인사업자를 포함합니다.', tables: ['sme_daegu'], charts: [] },
    { key: 'startup', title: '창업기업 (중소벤처기업부 창업기업동향)', desc: '대구 월별 창업기업 수(전체·기술기반업종)와 전년동월비, 연도별 합계, 업종별. 사업자등록 기준 창업(법인·개인)이며, 스타트업 지원 대상인 기술기반업종을 따로 보여 줍니다.', tables: ['startup_monthly', 'startup_annual', 'startup_industry'], charts: ['startup-monthly'] },
    { title: '기업 신생·소멸 (기업생멸행정통계)', desc: '대구 활동기업·신생기업·소멸기업 수와 신생률·소멸률, 산업별·기업규모별. 신생기업은 개인사업자를 포함한 새로 생긴 기업 전체라 위 창업기업(스타트업) 통계와 기준이 다릅니다.', tables: ['biz_birth', 'biz_birth_industry', 'biz_birth_size'], charts: ['biz-birth'] },
    { title: '수출입 활동기업 (관세청 기업무역활동통계)', desc: '17개 시도 수출입 활동기업 수·교역액, 진입·퇴출 기업, 수출 기여율·기여도와 대구 교역액 추이.', tables: ['export17'], charts: ['export-daegu'] },
  ],
  population: [
    { title: '연간 주요 지표', desc: '주민등록인구, 경제활동인구조사(취업자·고용률·실업률), 지역내총생산, 수출입 활동기업의 대구 값을 연도별로.', tables: ['daegu_annual'], charts: ['population'] },
    { title: '월간 고용·인구이동', desc: '경제활동인구조사(취업자·고용률·실업률)와 국내인구이동통계의 대구 월간 값.', tables: [], charts: ['employed', 'rates', 'migration'] },
    { title: '구·군별 인구·취업자', desc: '구·군별 주민등록인구와 지역별고용조사 시군구 취업자(산업 대분류 묶음).', tables: ['gu_population', 'employment_gu'], charts: [] },
    { title: '연령별 순이동', desc: '국내인구이동통계의 대구 연령(5세)별 순이동(전입 − 전출)과 청년층 묶음.', tables: ['migration_age'], charts: [] },
    { title: '업태별 소매판매액지수', desc: '시도별 소매판매액지수(불변, 2020=100)의 대구 업태별 값.', tables: ['retail_daegu'], charts: [] },
  ],
};
