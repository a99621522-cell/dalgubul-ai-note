# data/dpi — 대구정책연구원 연구 보고서 수치

`university_industry.json` — 대구정책연구원 「지역과 대학의 상생발전을 위한 전략 수립」(연구 2026-09, 2026.1) 4장
산업별 표(보고서 126~138쪽)의 대구 2016~2023년 사업체·종사자(1인 이상, 전국사업체조사)·생산액·부가가치(10인 이상, 광업·제조업조사, 백만 원)와
보고서에 적힌 전국 값, 산업별 세세분류 업종 코드. 운영자가 Drive 에 올린 원문을 OCR 로 읽어 `data/refs/dpi-2026-university-region-mutual-development.json`
(key_figures·industry_codes)에 옮긴 값을 구조화한 것 — 값을 만들거나 고치지 않았다(ABB 의 2020~2022 생산액·부가가치는 보고서 '-' → null).

쓰는 곳: `src/components/IndustryBundles.astro` — `/stats/industry/#bundles` 와 `/policy/dpi-industry/`. 사이트에는 최근 연도(2023) 대구 값만 보인다(운영자 지시 2026-10-09 '2016년 이런 과거 자료는 필요 없어, 그냥 대구정책연구원 자료만 올려'); 전국 값·연도별 값은 이 파일에만.
통계청 공개 통계로 만든 표(`/stats/industry/#bundles`, `data/kosis/industry_bundles.json`)·성장 계산기·리포트 집계에는 섞지 않는다.
