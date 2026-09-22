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
