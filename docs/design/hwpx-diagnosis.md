# 한글(HWPX) 산출물 진단 — 양식(T) · hwpx_report.py(A) · hwpx.ts v1(B) 대조 (2026-10-06)

`docs/prompts/site_hwpx_skill.md` 1절. 한글(한컴오피스)은 이 환경에 없으므로 아래는 **XML·zip 수준의 차이와 깨짐 원인 '가능성'** 이다. 확정은 `hwpx-compat.md` 의 실물 시험 뒤에 한다.

대조 파일
- **T** 양식 `scripts/data/hwpx/report_basic.hwpx`(운영자 제공 2026-09-27, 한글 11.0 WIN32 저장본 — 한글에서 열린다)
- **A** `public/hwpx/2026-10-06-policy-manufacturing-ax-sewing.hwpx`(`hwpx_report.py`, 양식을 열어 문단을 지우고 `para()`·`design_table()` 로 채움). 리포트 메뉴의 HWPX 판은 2026-09-30 '한글에서 제대로 열리지 않아' 내렸고, 같은 날 줄 배치(linesegarray)를 모두 빼는 수정이 들어갔다. 그 뒤 판이 열리는지는 **미확인**
- **B** `src/scripts/hwpx.ts` v1 산출물(template.json 의 header.xml + 문자열 템플릿으로 section0.xml 작성, 브라우저 zip STORED). 2026-10-01 운영자 확인 '한글에서 깨짐'

## 대조표

| # | 항목 | T(양식) | A(hwpx_report) | B(hwpx.ts v1) | 차이 | 깨짐 원인 가능성 |
|---|---|---|---|---|---|---|
| ① | zip 첫 항목 mimetype STORED | ○ | ○ | ○(직접 쓴 zip, 모든 항목 STORED, UTF-8 플래그) | B 는 압축 없음 — 한글은 STORED 도 연다(mimetype 이 그렇다) | 하 |
| ② | content.hpf manifest·spine | header·image1·section0·settings | 같음(+ 넣은 그림) | 같음(image1 은 쓰지 않아도 남김) | 없음 | 하 |
| ③ | settings.xml·version.xml | 있음(CaretPosition paraIDRef=80) | 양식 그대로 복사 | 양식 그대로 복사 | 캐럿이 가리키는 문단 id 가 산출물에 없음(A·B 공통) | 중 — 한글이 캐럿 위치를 못 찾으면 무시할 가능성이 크나 미확인 |
| ④ | 첫 문단 secPr·pagePr | ○ | ○(머리말·꼬리말 ctrl 만 뺌) | ○ | 없음 | 하 |
| ⑤ | 스타일 참조 무결성(paraPr·charPr·borderFill) | ○ | ○(검사기 PASS) | ○(검사기 PASS) | 없음 — 덧붙인 스타일은 itemCnt 다음 id | 하 |
| ⑥ | hp:p 속성 | id 다양(중복도 있음: 27개가 0) | id 거의 0 | id 모두 0 | 양식에도 id 중복이 있어 id 는 식별자가 아님 | 하 |
| ⑦ | hp:t 특수문자 | — | ET 가 이스케이프 | 직접 esc() | 없음 | 하 |
| ⑧ | **hp:linesegarray** | 모든 문단에 있음(vertpos 누적, vertsize=글자 크기) | **없음**(2026-09-30 부터 모두 뺌) | **없음** | T 만 있음. 2026-09-30 전 A 는 같은 값(vertpos 0)을 모든 문단에 넣어 '글자가 겹치고 그림 양옆이 검게 뭉침'(운영자 확인) → 한글이 이 값을 **믿는다**는 증거. 없을 때 새로 계산하는지는 미확인 | **상** — 시험 파일 `t01-simple-py-lineseg.hwpx`(어림값 넣음) 와 `t01-simple-py.hwpx`(없음) 로 가른다 |
| ⑨ | 표 격자(rowCnt·colCnt·cellAddr·cellSpan·cellSz) | ○ | ○ | ○(검사기 PASS) | 없음. hp:sz height 는 T 도 행 높이 합과 다른 표가 있음(허용) | 하 |
| ⑩ | **section 루트 네임스페이스 선언** | 14개(ha·hp·hp10·hs·hc·hh·hhs·hm·hpf·dc·opf·ooxmlchart·epub·config) | **hp·hs 2개**(ET.tostring 이 쓰인 것만 남김) | 2개 | 한글 파서가 선언을 요구하는지 미확인 | **중** — 2026-10-06 부터 A·B 모두 양식 선언 14개를 그대로 둔다(`hwpx_blocks.py` all_ns, `hwpx_report.py`) |
| ⑪ | XML 선언·인코딩 | UTF-8, BOM 없음 | 같음 | 같음 | 없음 | 하 |
| ⑫ | Preview/PrvText.txt·PrvImage.png | 둘 다 | PrvText 만 바꿈, PrvImage 양식 것 | PrvText 만, **PrvImage 없음** | container.xml 은 PrvText 만 가리킴 | 하 |
| ⑬ | 덧붙인 charPr 의 자식 | 양식 charPr 는 `strikeout shape="3D"` 까지 | fontRef·ratio·spacing·relSz·offset(+bold) | 같음 | 선택 자식이 없는 것은 스키마상 허용 | 하~중 |
| ⑭ | 표 원형 tbl 의 pos·outMargin | 양식 표마다 다름 | top[64] 복제 | 같은 원형을 JSON 으로 | 없음 | 하 |

## 결론(가능성 순)
1. **줄 배치(⑧)**: 한글이 값을 믿는 것은 확인됐고, 없을 때의 동작은 미확인. 시험 파일 두 변형으로 가른다. 값을 믿고 없으면 0 으로 보는 경우라면 '모든 문단이 한 자리에 겹침' = 운영자가 본 '깨짐' 과 같은 증상이다.
2. **네임스페이스(⑩)**: 비용 없이 양식과 같게 할 수 있어 2026-10-06 부터 두 경로 모두 14개를 선언한다.
3. **캐럿 위치(③)**: settings.xml 의 `CaretPosition paraIDRef` 가 없는 문단을 가리킨다. 다음 단계에서 산출물의 첫 문단 id 로 바꾸는 것을 검토(실물 시험에서 ①~⑩ 이 모두 ○인데 깨지면 이 항목).
4. B 만의 차이(STORED zip·PrvImage 없음)는 가능성 '하'로 둔다. 시험 파일은 같은 Block 을 py(압축 zip)·js(STORED zip) 두 경로로 내므로 둘의 결과가 갈리면 zip 쪽이 원인이다.

## 2026-10-06 조치
- 검사기 `scripts/hwpx_check.py`(①②④⑤⑨⑩⑪⑫ + 그림 manifest + lineseg 중복 경고 + 개인정보·금지 낱말)와 CI `hwpx_check.yml`.
- 두 경로를 양식 복제 하나로: `scripts/hwpx_blocks.py`(Python, ET deepcopy) ↔ `src/scripts/hwpx.ts` v2(브라우저, DOMParser cloneNode · XMLSerializer). 문자열 템플릿으로 hp:p·hp:tc 를 쓰지 않는다. 원형 조각은 `scripts/hwpx_template.py` 가 `public/hwpx/template.json` 으로 내보낸다.
- 시험 파일 15개 `public/hwpx/test/`(`scripts/hwpx_test.py`). 관문 `data/hwpx/compat.json`.
