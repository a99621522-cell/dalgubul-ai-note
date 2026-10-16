/** 리포트 자료(운영자가 올린 보고서 PDF·Word). 파일은 public/files/ 에 두고 여기 한 줄씩 더한다.
 *  한글(HWPX)판은 `scripts/docx_to_hwpx.py`(Word → 공무원 양식 복제, hwpx_check PASS)로 `public/hwpx/` 에 만든다(운영자 지시 2026-10-06 '옮긴 리포트도 한글로').
 *  /policy/ 목록과 첫 화면 리포트 회전 카드(ReportCarousel)가 같이 읽는다(운영자 지시 2026-10-06: 봉제 AI 브리프를 내리고 이 자료 2건을 첫 화면 카드로). */
export type ReportFile = { slug: string; summary: string; topics: string[]; pages?: number; title: string; name: string; href?: string; size?: string; pdf?: string; pdfSize?: string; hwpx?: string; hwpxSize?: string; date: string };
export const REPORT_FILES: ReportFile[] = [
  { slug: 'daesung-hitech-robot-cdmo', summary: '대구 달성군 코스닥 상장사 대성하이텍의 로봇 CDMO 진출 선언과 방산 정밀부품·AI 데이터센터 냉각·카테터 사업을 증권사 리포트 원문 3건(유안타증권·키움증권)과 DART 공시로 정리한 자료. 투자의견·목표주가·애널리스트 이름은 싣지 않음.', topics: ['상장기업', '로봇', '증권사 리포트'],
    title: '대성하이텍 진출 선언 — 정밀가공에서 로봇 CDMO로', name: '대성하이텍 진출 선언 — 정밀가공에서 로봇 CDMO로',
    hwpx: '/hwpx/daesung-hitech-robot-cdmo.hwpx', hwpxSize: '276KB', date: '2026-10-16' },
  { slug: 'china-robot-training-grounds', summary: '중국정보통신연구원(CAICT) 「체화지능 훈련장 연구보고서(2026년)」 등 공개 자료로 정리한 중국 휴머노이드 로봇 훈련장의 건설 현황·운영 방식·과제와 해외 사례.', topics: ['로봇', '해외 동향'], pages: 11,
    title: '중국 로봇 훈련장 현황', name: '중국 로봇 훈련장 현황',
    href: '/files/china-robot-training-grounds.docx', size: '1.1MB', pdf: '/files/china-robot-training-grounds.pdf', pdfSize: '1.5MB', hwpx: '/hwpx/china-robot-training-grounds.hwpx', hwpxSize: '1.3MB', date: '2026-10-12' },
  { slug: 'daegu-listed-2026q2', summary: 'DART 반기보고서 주요계정으로 집계한 대구 본사 상장회사 53곳의 2026년 2분기 매출액·영업이익과 업종별·기업별 실적, 회사가 공시한 변동 사유.', topics: ['상장기업', '실적'], pages: 10,
    title: '대구 소재 상장기업 2026년 2분기 실적', name: '대구 소재 상장기업 2026년 2분기 실적',
    href: '/files/daegu-listed-2026q2.docx', size: '0.4MB', pdf: '/files/daegu-listed-2026q2.pdf', pdfSize: '0.8MB', hwpx: '/hwpx/daegu-listed-2026q2.hwpx', hwpxSize: '0.4MB', date: '2026-10-12' },
  { slug: 'daegu-industry-structure', summary: '17개 시도 지역소득 자료로 계산한 대구의 산업구조 지표(입지계수·산업집중도·고부가 3부문 비중)와 경제성장의 관계.', topics: ['산업구조', '성장'], pages: 25,
    title: '지역 산업구조 특성이 경제성장에 미치는 영향 — 대구판(산업구조지수를 중심으로)', name: '지역 산업구조 특성이 경제성장에 미치는 영향 — 대구판',
    href: '/files/daegu-industry-structure.docx', size: '1.7MB', pdf: '/files/daegu-industry-structure.pdf', pdfSize: '2.2MB', hwpx: '/hwpx/daegu-industry-structure.hwpx', hwpxSize: '2.3MB', date: '2026-09-30' },
  { slug: 'supply-chain-map-guide', summary: '한국은행 「주요 제조업 생산 및 공급망 지도」(2026.7)를 대구 산업 관점에서 풀어 쓴 해설 원고.', topics: ['공급망', '제조업'], pages: 161,
    title: '주요 제조업 공급망 지도 해설', name: '주요 제조업 공급망 지도 해설',
    href: '/files/supply-chain-map-guide.docx', size: '11.4MB', pdf: '/files/supply-chain-map-guide.pdf', pdfSize: '15MB', hwpx: '/hwpx/supply-chain-map-guide.hwpx', hwpxSize: '9.9MB', date: '2026-09-30' },
];
export const reportBySlug = (slug: string) => REPORT_FILES.find(f => f.slug === slug);
