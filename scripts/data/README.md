# data — 달성 산단·기업 기초 DB

## 파일
- `dalseong_companies.csv` 대구 전체 기업 11,174곳(2026-08, 파일명은 호환 유지). 열: id, name, complex(단지명 또는 '개별입지'), district(구·군), eupmyeon(읍면/동), sector_code, sector, sector_group, product, workers_band, workers, reg_type, first_registered, mfg_area_band(산단공 단지만), address(복수 공장은 ' / '), sites, source, as_of.
  `id`는 기업 페이지 주소(/companies/c0001/)라 바꾸지 말 것. `name`은 collect.py가 뉴스 키워드로 자동 사용.
- `dalseong_complexes.csv` 단지 22행(대구 산단·농공·특구 21 + 개별입지). firms·sites·workers·main_sectors는 기업 파일에서 계산됨. completed·area_km2는 손으로 채우는 칸.

## 매달 갱신 (팩토리온 → 고객지원 → 자료실 → 현황통계자료실, 매달 2일경)
1. "(YYYY.MM월말기준)_전국(개별,계획)입주업체현황" 내려받기 (필수)
2. "(YYYY.MM월말기준)_산단공관할단지내_입주업체리스트" 내려받기 (선택, 등록상태·면적 보강)
3. `python3 scripts/import_factoryon.py <1번파일> <2번파일>` → 두 CSV 갱신. 기존 기업 id 유지, 새 기업은 새 id, 사라진 기업은 옛 as_of로 남음

## 원칙
공개 자료만. 전화번호·대표자 등 연락처는 원본에 있어도 저장하지 않음. 종사자 수는 사이트에 구간으로만 표시.
