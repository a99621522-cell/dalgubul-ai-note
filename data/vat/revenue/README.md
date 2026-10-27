# 지자체 세입예산사업명세서 (지자체 부가세 절감 점검기 맞춤형)

운영자 지시 2026-10-27 '대구시와 기초지자체별로 선택하면 맞춤형으로' → '세입 자료부터 받아서 해'.

- 지방재정365 재정 데이터셋의 세입은 관(款) 합계(지방세·경상적세외수입·임시적세외수입·보조금…)뿐이라 `data/lofin/revenue_settle.csv`(2002~2024, 대구 본청·구군)에만 두고,
  항·목·사업 단위는 지자체 누리집 재정공시의 **세입예산사업명세서**(e호조 출력 PDF, 공공누리)에서 받는다 — `config/revenue_docs.yml` → `scripts/fetch_revenue_docs.py`(러너 `.github/workflows/revenue_docs.yml`, 분기 첫 달 11일) → `raw/<key>_<year>.txt`(pdftotext -layout, PDF 원본은 두지 않음) → `scripts/parse_revenue_docs.py` → `<key>_<year>.csv` + `index.json`.
- CSV 열: gov·key·year·acct·jang·gwan·hang·mok_code·mok·bureau·dept·item·calc·amount_k(천원, 예산서 그대로)·vat_key(rules.yml revenue_items 키 — 목 코드·사업명 낱말로 짐작한 **참고 표시**, 기관 판단 아님)·fac_key(시설 종류 낱말). 세외수입(장 200)·보조금(장 500)만.
- `index.json[key].check`: 목 줄 예산액 ↔ 사업 합계가 다른 목(줄바꿈된 사업명·산출식 때문에 못 읽은 줄) — 투명하게 남긴다. 2026-10-27: 군위군·북구 세외수입 합계 일치, 달성군 −6,900천원(과태료), 대구시 211-02 −51,381천원.
- 2026-10-27 받은 곳: 대구광역시(jumin.daegu.go.kr 세입세출예산서, 세션·CSRF 토큰 뒤 POST fileDownload.do), 북구(budget_2026_1/5.pdf), 달성군(예산현황 글 첨부 eb014), 군위군(세입세출예산서 첨부). 중구·동구·서구·남구·수성구·달서구 누리집은 이 세션에서 연결 거부 → 러너 discover 로그를 보고 url 을 채운다.
- 읽는 곳: `src/lib/vatRevenue.ts` → `/vat-revenue.json` → `/vat/discover/`(지자체 선택: 세외수입 사업 금액 순 표·점검표 미리 표시·시설 관련 보조금 후보), `/vat/setup/`(세입예산서에서 시설 후보 불러오기).
- 사람 이름·전화 없음(예산서에 없다). 세출 사업설명서(지출 → 시설 매핑)는 다음 단계.
