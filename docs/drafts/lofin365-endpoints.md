# 지방재정365(lofin365.go.kr) 대구 세출예산 — 내부 요청 조사 메모

조사일 2026-10-05. GitHub Actions `site_probe.yml` 12회(xhr·render/dump·file)로 확인. 이 세션 환경은 lofin365 직접 접속 불가.
초안 메모이며 수집 스크립트는 아직 없다.

## 0. 공통 사항 (확인됨)

- robots.txt: `User-agent: * / Allow: /`. 모든 화면과 아래 요청은 **로그인 없이** 열렸다(화면 머리에 '로그인을 해주세요'만 뜨고 데이터는 그대로 나옴).
- 화면 구조: `/portal/LFxxxxxxx.do`(껍데기) → POST `…/retvLstXxx.do`(HTML 조각, 폼·스크립트 포함) → POST `…/retvLstXxxAjax.do` 또는 `…Sch.do`(JSON 데이터).
- 데이터 요청은 **POST 전용**. 같은 주소를 GET 으로 부르면 405(오류 화면)가 돌아온다(`retvLstByacBfae.do` 로 확인).
- 화면 껍데기 주소의 쿼리 인자는 첫 조회에 그대로 넘어간다(`frstParamYn=Y`). 예: `LF5100000.do?srchCrstCn=성질별&frstParamYn=Y` 는 데이터셋 검색어가 채워진 채 열린다. `LF2210000.do?fyr=2026&…&tab=gov` 도 같은 방식.
- 금액 단위: JSON 은 **원**(예: 2026 전국 일반회계 `417556886093000`). 화면 표는 백만원, 그래프는 억원.
- 자치단체 코드(7자리 `lafCd`): 서울본청 `1100000`, 서울종로구 `1111000`, 부산 `2600000` 확인. 시도 코드 표(`codeId`/`lafTyCd`)에서 대구 = `27`. 같은 규칙으로 **대구광역시 본청 = `2700000`**(추정, 실제 행은 아직 화면에서 못 봄). 구·군은 `27xx000`(행정표준코드 기준: 중구 2711000, 동구 2714000, 서구 2717000, 남구 2720000, 북구 2723000, 수성구 2726000, 달서구 2729000, 달성군 2771000, 군위군 2772000 — lofin 응답으로는 미확인).
- 연도: 지방재정통계 예산 화면 2001~2026(기능별 화면 2008~2026), 통합공시 2012~2026.

## 1. 기능별(분야별) 세출예산 — 찾음

### 1-1. 지방재정통계 > 예산 > 예산현황 > 기능별 회계별 세출예산 (화면 `/portal/LF3110102.do`)

| 항목 | 값 |
|---|---|
| 데이터 URL | `POST https://www.lofin365.go.kr/lf/lnncGramStst/laf/bdgSvi/retvLstByacBfaeAjax.do` |
| Content-Type | `application/x-www-form-urlencoded` |
| 관찰된 본문 | `menuUrl=/lf/lnncGramStst/laf/bdgSvi/retvLstByacBfae.do&menuNm=기능별 회계별 세출예산&menuParaCn=STST&menuId=LF3110102&uprMenuId=LF3110100&crtrLvl=&subCode=&inqYmd=2026&inqCap=&inqSgg=` |
| 연도 | `inqYmd`(=회계연도, 응답에 `inqYr` 로 되돌아옴) |
| 지역 | `inqCap`(시도), `inqSgg`(자치단체). 빈 값 = 전국. **대구 값은 미검증** — 시도 선택 상자 목록(`POST /lf/lnncGramStst/laf/bdgSvi/sidoLF03002M2Ajax.do`, 본문 `fyr=2026`)이 `cdValChcNm`(예 `1100000`, `2600000`)을 주므로 `inqCap=2700000` 일 가능성이 크다. `inqSgg` 는 구·군 목록 요청(시도 고른 뒤 부르는 다른 `…Ajax.do`, 이름 미확인) 값. 본청만이면 `inqSgg=2700000`, 시+구군 합계(시도계)는 `inqSgg=` 빈 값일 가능성(미검증). |
| 응답 | `{"paramDto":{…},"result":{"byacBfaeIxRsltDto":[{"nextSnum":0,"bfSnum":0,"amt1":417556886093000,"amt2":0,…}, …]}}` — 행마다 `amt1…amtN` 열. 2026 전국 첫 행 `amt1` = 일반회계 합계(원). 열↔분야 대응은 미확인(화면 그래프 순서: 일반공공행정, 공공질서및안전, 교육, 문화및관광, 환경, 사회복지, 보건, 농림해양수산, 산업·중소기업및에너지, 교통및물류, 국토및지역개발, 과학기술, 예비비, 기타 × 일반회계/기타특별회계/공기업특별회계). |
| 로그인 | 필요 없음 |

같은 화면군(모두 `…/laf/bdgSvi/` 아래, 화면 `LF3110101~105`):
- 예산총계와 순계 `retvLstPrsmTotlSch.do` — 본문 `…&crtrLvl=&yearSelect=2026&gu_chk=A`(A=전국; 화면에 '전국/시도계/자치단체' 선택이 있어 B·C 가 시도계·자치단체로 보이나 미검증). 응답 `result.retvBdgScalOutl[].amt1…`.
- 기능별 재원별 세출예산(LF3110103), 기능별 단체별 세출예산(LF3110104), 재원별 세입예산(LF3110105) — 같은 방식으로 보이나 요청 이름 미확인.

### 1-2. 재정데이터개방 > 재정 데이터셋 (Sheet, 로그인 없음)

데이터셋 목록 화면 `/portal/LF5100000.do` (146건). 검색 결과 '세출예산'으로 6건:

| 데이터셋 | 내용 | 보유연도 | 분류 |
|---|---|---|---|
| 세출예산 | 연간 세출예산 규모(일반회계·공기업특별·기타특별·기금) | 2012~2026 | 예산규모 |
| 기능별 재원별 세출예산 | 기능별 재원별(총계) | 2008~2026 | 예산현황 |
| 구조별 기능별 세출예산 (`pdtaId=RL5CZ30XLWDXZAKXS5LP134169`) | 구조별(정책사업·행정운영경비·재무활동) × 기능별(분야·부문), 총계·순계 | 2008~2026 | 예산현황 |
| 기능별 회계별 세출예산 | (설명 잘림) | – | 예산현황 |
| (2건 더, 화면 글자 제한으로 못 봄) | | | |

- Sheet 화면: `/portal/LF5110000.do?pdtaId=<ID>&rdIncrYn=Y` → 조각 `POST /lf/pfinDtaOpen/dtst/dtstSvi/retvDtstDtsSheet.do`(본문 `menuId=LF5110000&uprMenuId=LF5100000&menuParaCn=CJG&pdtaId=<ID>&rdIncrYn=Y&…`). **표 데이터는 이 HTML 조각 안에 서버가 넣어 보낸다**(별도 XHR 없음).
- Sheet 화면에는 '회계연도·지역명·자치단체명' 검색 칸과 XML·JSON·XLSX·CSV·RDF 내려받기 단추가 있다(로그인 요구 문구 없음). 내려받기 요청 주소·인자 이름은 아직 못 봤다.
- 「구조별 기능별 세출예산」 열: 회계연도, 지역명, 자치단체코드, 자치단체명, 분야코드, 회계구분명, 분야명, 부문코드, 부문명, 정책사업예산총계, 행정운영경비총계, 재무활동총계, 정책사업예산순계, 재무활동순계, 행정운영경비순계. 단위 원. 첫 행 예: `2026 서울 1100000 서울본청 010 일반회계 일반공공행정 011 입법및선거관리 37,139,935,000 …`. 총 11,480행(전 단체·전 연도가 아니라 기본 조회 범위로 보임).
- OpenAPI 단추(`/portal/LF5120000.do`)는 인증키가 필요하다(키 발급은 회원가입·로그인 → 이번 범위에서 쓰지 않음).

## 2. 성질별 세출예산 — 아직 못 찾음

- 지방재정통계 > 예산의 메뉴(예산현황 5개, 주요경비 예산편성 4개: 공무원 관련경비·지방의회 관련경비·상근인력 관련경비·교육관련지원)에는 '성질별'이 없다.
- 재정 데이터셋 검색 '세출예산' 6건 중 성질별 없음. 검색 '성질별'의 첫 결과는 「성질별 단체별 세입결산」(`pdtaId=88R4QJFQDPDV7D8X8VAE916854`, 결산>결산현황, 2002~2024, 열: 회계연도·지역명·자치단체코드·자치단체명·세목코드·세목명·세입금액, 2,579행, 원). 세입이라 이번 목적과 다르지만 '성질별 단체별 세**출**결산'이 같은 묶음에 있을 가능성이 크다(미확인).
- 남은 후보: (1) 재정 데이터셋 '성질별' 검색 결과 전체 목록(2건째 이후), (2) 통합공시 단체별 현황(예산기준) `/portal/LF2310000.do` — 단체 한 곳의 공시 항목에 성질별 세출이 있을 수 있음, (3) 지방재정통계 > 결산(`/portal/LF3130101.do`) 하위 메뉴, (4) 지방재정자료 검색 `/portal/LF4100001.do`.
- 대분류 8개(인건비·물건비·경상이전·자본지출·융자 및 출자·보전재원·내부거래·예비비 및 기타)는 지방재정연감·통합공시의 성질별 분류와 같은 체계.

## 3. 통합공시 세출예산(회계별) — 찾음, 성질·기능 구분은 없음

| 항목 | 값 |
|---|---|
| 화면 | `/portal/LF2210000.do?fyr=2026&byatcClsTy=LCTBBDG01&pfaIndcCd=A129&rgnzDvCd=02&tab=gov` |
| 데이터 URL | `POST https://www.lofin365.go.kr/lf/lnncGramStst/lnncIpaByatcBdgCrtr/bfaeSvi/retvLstBfaeGov.do` |
| Content-Type | JSON |
| 본문 | `{"menuId":"LCTBMM000","rgnzDvCd":"02","fyr":"2026","byatcClsTy":"LCTBBDG01","pfaIndcCd":"A129","tab":"gov","waLafCd":""}` |
| 응답 | `{"bfaeIxInqRsltDto":[{"fyr":"2026","lafNm":"서울본청","aneTottAmt":"55249341502000","genAcntAmt":…,"pbcoSpcAcntAmt":…,"etcSpcAcntAmt":…,"fndAmt":…,"lafCd":"1100000"}, …]}` — 전국 단체 전부(약 52KB), 원 |
| 기준 | 당초예산 총계, 통합회계(일반+공기업특별+기타특별+기금) |
| 연도 | 2012~2026 (`retvLstByatcYr.do`) |
| 탭 | `retvLstBfaeCntry.do`(전국), `…Bysd.do`(시도별), `…Gov.do`(자치단체), `…SmkdCmty.do`(동종), `…SmrCmty.do`(유사) |
| 지표 코드 | `pfaIndcCd` A128 세입예산, A129 세출예산, RD01 지역통합재정통계 (분류 `LCTBBDG01` 예산규모). 다른 분류: LCTBBDG11 재정여건(예산), LCTBBDG21 재정운용계획, LCTBBDG31 재정운용성과 |
| 로그인 | 필요 없음 |

시도 '대구'의 `lafTyCd=27` (`retvLstByatcGovTy.do`, 본문 `{"comClsCd":"LF010"}`). `waLafCd` 에 `27` 을 넣으면 대구 본청+구군만 오는 것으로 보이나 미검증.

## 4. 최소 예시 (Python requests, 미검증 부분 표시)

```python
import requests
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"
BASE = "https://www.lofin365.go.kr"
S.get(BASE + "/portal/LF3110102.do", timeout=30)   # 세션 쿠키

# (A) 기능별 회계별 세출예산 — 확인된 요청. inqCap/inqSgg 대구 값은 미검증
r = S.post(BASE + "/lf/lnncGramStst/laf/bdgSvi/retvLstByacBfaeAjax.do", data={
    "menuUrl": "/lf/lnncGramStst/laf/bdgSvi/retvLstByacBfae.do",
    "menuNm": "기능별 회계별 세출예산", "menuParaCn": "STST",
    "menuId": "LF3110102", "uprMenuId": "LF3110100",
    "crtrLvl": "", "subCode": "", "inqYmd": "2026",
    "inqCap": "2700000",   # 미검증: 시도 선택 값(cdValChcNm)
    "inqSgg": "2700000",   # 미검증: 대구 본청. 시+구군 합계는 "" 로 시험
}, timeout=60)
rows = r.json()["result"]["byacBfaeIxRsltDto"]   # amt1..amtN, 단위 원

# (B) 통합공시 세출예산(회계별, 전국 단체 전부) — 확인된 요청
r = S.post(BASE + "/lf/lnncGramStst/lnncIpaByatcBdgCrtr/bfaeSvi/retvLstBfaeGov.do", json={
    "menuId": "LCTBMM000", "rgnzDvCd": "02", "fyr": "2026",
    "byatcClsTy": "LCTBBDG01", "pfaIndcCd": "A129", "tab": "gov", "waLafCd": ""})
daegu = [x for x in r.json()["bfaeIxInqRsltDto"] if x["lafCd"].startswith("27")]

# (C) 성질별 세출예산 — 해당 요청을 아직 찾지 못함(2절 참조)
```

## 5. 다음에 확인할 것

site_probe 는 응답 앞 600자·화면 글자 앞 2,000자만 찍어서(메뉴 글자가 약 1,700자를 먹음) 행 구조와 대구 코드 확인이 막혔다.
1. `inqCap`/`inqSgg` 대구 값과 구·군 목록 요청 이름: 기능별 화면에서 선택 상자를 실제로 고르는 클릭(옵션 선택은 지금의 `--click` 으로 안 됨) 또는 HTML 조각 스크립트 전체 읽기가 필요.
2. 성질별 세출: 데이터셋 '성질별' 검색 결과 전체 목록, 통합공시 단체별 현황(LF2310000), 결산 메뉴.
3. Sheet 의 CSV/JSON 내려받기 요청 주소·인자(자치단체명·회계연도 검색 인자 이름 포함).
4. 2023~2024 결산 기준: 통합공시 결산기준(`/portal/LF2220000.do`, `/portal/LF2320000.do`)과 결산 데이터셋.

위 항목은 site_probe 에 '응답 전문 저장(아티팩트)'이나 '선택 상자 고르기(select_option)' 옵션을 더하면 1~3회로 끝날 것으로 보인다(스크립트 수정·커밋은 운영자 승인 필요).
