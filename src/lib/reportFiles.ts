/** 리포트 자료(운영자가 올린 보고서 PDF·Word). 파일은 public/files/ 에 두고 여기 한 줄씩 더한다.
 *  한글(HWPX)판은 `scripts/docx_to_hwpx.py`(Word → 공무원 양식 복제, hwpx_check PASS)로 `public/hwpx/` 에 만든다(운영자 지시 2026-10-06 '옮긴 리포트도 한글로').
 *  /policy/ 목록과 첫 화면 리포트 회전 카드(ReportCarousel)가 같이 읽는다(운영자 지시 2026-10-06: 봉제 AI 브리프를 내리고 이 자료 2건을 첫 화면 카드로). */
export type ReportFile = { title: string; name: string; href: string; size: string; pdf?: string; pdfSize?: string; hwpx?: string; hwpxSize?: string; date: string };
export const REPORT_FILES: ReportFile[] = [
  { title: '지역 산업구조 특성이 경제성장에 미치는 영향 — 대구판(산업구조지수를 중심으로)', name: '지역 산업구조 특성이 경제성장에 미치는 영향 — 대구판',
    href: '/files/daegu-industry-structure.docx', size: '1.7MB', pdf: '/files/daegu-industry-structure.pdf', pdfSize: '2.2MB', hwpx: '/hwpx/daegu-industry-structure.hwpx', hwpxSize: '2.3MB', date: '2026-09-30' },
  { title: '주요 제조업 공급망 지도 해설', name: '주요 제조업 공급망 지도 해설',
    href: '/files/supply-chain-map-guide.docx', size: '11.4MB', pdf: '/files/supply-chain-map-guide.pdf', pdfSize: '15MB', hwpx: '/hwpx/supply-chain-map-guide.hwpx', hwpxSize: '9.9MB', date: '2026-09-30' },
];
