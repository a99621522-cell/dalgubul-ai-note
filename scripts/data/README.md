# data — 달성 산단·기업 기초 DB

## 파일
- `dalseong_companies.csv` 대구 전체 기업 11,174곳(2026-08, 파일명은 호환 유지). 열: id, name, complex(단지명 또는 '개별입지'), district(구·군), eupmyeon(읍면/동), sector_code, sector, sector_group, product, workers_band, workers, reg_type, first_registered, mfg_area_band(산단공 단지만), address(복수 공장은 ' / '), sites, source, as_of.
  `id`는 기업 페이지 주소(/companies/c0001/)라 바꾸지 말 것. `name`은 collect.py가 뉴스 키워드로 자동 사용.
- `dalseong_complexes.csv` 단지 22행(대구 산단·농공·특구 21 + 개별입지). firms·sites·workers·main_sectors는 기업 파일에서 계산됨. completed·area_km2는 손으로 채우는 칸.

## 매달 갱신 (팩토리온 → 고객지원 → 자료실 → 현황통계자료실, 매달 2일경)
1. "(YYYY.MM월말기준)_전국(개별,계획)입주업체현황" 내려받기 (필수)
2. "(YYYY.MM월말기준)_산단공관할단지내_입주업체리스트" 내려받기 (선택, 등록상태·면적 보강)
3. `python3 scripts/import_factoryon.py <1번파일> <2번파일>` → 두 CSV 갱신. 기존 기업 id 유지, 새 기업은 새 id, 사라진 기업은 옛 as_of로 남음
4. (러너로 하기, 2026-10-08) `.github/workflows/factoryon_import.yml` 이 매달 3일(또는 수동 실행) `scripts/fetch_factoryon.py` 로 자료실 최신 글 2개의 첨부를 받아(운영자 지시 2026-10-08 예외 — 다른 글은 열지 않음) 3번과 뒤 단계(국민연금 재대조·입지 유형·월간 통계·그래프·효과표)까지 돌리고 커밋·배포한다. 받기가 막히면 파일을 Google Drive 에 올리고(링크가 있는 모든 사용자 보기) 수동 실행(main=파일 id, kicox=선택, month=YYYY.MM). 전국 원본은 저장소에 들어가지 않는다

내려받은 파일이 엑셀에서 안 열리거나 정렬이 안 되면(확장자만 xls 이고 실제는 HTML 표·CSV 인 경우) `python3 scripts/repair_factoryon.py <파일>` 으로 실제 형식을 확인하고 옆에 `<파일명>_정리.xlsx` 를 만든 뒤 그 파일을 import 에 넘긴다. `--inspect` 는 진단만.

## 원칙
공개 자료만. 전화번호·대표자 등 연락처는 원본에 있어도 저장하지 않음. 종사자 수는 사이트에 구간으로만 표시.

## ca-extra.pem

대구테크노파크(www.ttp.org)가 TLS 중간 인증서를 보내지 않아 requests 가
`CERTIFICATE_VERIFY_FAILED` 로 죽는다. 브라우저는 누락분을 알아서 받아오지만 requests 는 못 한다.
그래서 발급기관의 중간 인증서(Sectigo Public Server Authentication CA DV R36, 2036-03-21 만료)를
여기 두고 certifi 번들과 합쳐 `verify=` 로 넘긴다.

```python
import certifi, tempfile
from pathlib import Path
bundle = Path(tempfile.gettempdir()) / "dalgubul-ca.pem"
bundle.write_text(Path(certifi.where()).read_text() + "\n" + Path("scripts/data/ca-extra.pem").read_text())
requests.get(url, verify=str(bundle))
```

ttp.org 가 서버 설정을 고치면 이 파일은 필요 없어진다.

## 한국은행 공급망 지도 표 (bok_*.csv)

`python3 scripts/parse_bok_map.py [--match]` 가 `docs/sources/bok_supplychain_2026-07.pdf`(한국은행 「우리나라 주요 제조업 생산 및 공급망 지도」 2026.7)에서 pdftotext 로 뽑는다. 값은 보고서 그대로, 평가 없음.

- `bok_dependency.csv` — 업종별 '특정국 의존도가 높은 품목'(2025년 수입, 백만달러·%). industry(장)·priority(자동차부품·기계장비·전기장비·반도체 = 우선)·section(표 이름)·country·item·hs_code·amount_musd·share_pct·check(빈 칸이 있으면 '원문 확인')·page. 자동차부품 장은 HS 표 대신 희소금속 표(한국지질자원연구원 자료)라 item=금속(기호), hs_code 빈칸, amount=총수입액, country=주요 수입국, note=용도. 자동차 장의 '특정국 의존도가 높은 자동차부품' 표는 industry=자동차. 기준: 의존도 40%(이차전지 20%) 이상·천만달러 초과 품목만 보고서에 실림
- `bok_multipliers.csv` — 부록 권역별 유발계수(생산·수입·부가가치·취업(명/10억원), 중분류 12개 부문). 자료: 한국은행 지역산업연관표(2020)
- `bok_region.csv` — 권역별 현황: 업종별 권역 생산 점유율(2024, 각 장), 전국 업종 현황(요약, 2014/2019/2024, 수출은 2025), 권역 제조업 생산 비중(요약). **부록의 권역별 '사업체 수·고용(2024)' 그래프는 막대에 숫자가 없어 글자로 뽑히지 않는다** — 값을 만들지 않고 비워 둔다
- `bok_dependency_daegu.csv`(`--match`) — 의존도 품목의 핵심 낱말(괄호 조건·'자동차용' 같은 수식어 제외)이 `dalseong_companies.csv` 생산품에 들어 있는지로 '대구 안에 생산 기업이 있는 품목/없는 품목'을 나눈 것. 낱말 일치일 뿐 그 기업이 그 품목을 만든다는 뜻이 아니므로 참고용(has_daegu_producer·daegu_companies·examples)
