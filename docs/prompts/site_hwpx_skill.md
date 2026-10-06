# 프롬프트 — 한글(HWPX) 산출물 재도입: 양식 복제 방식으로 통일하고 시험 매트릭스로 검증

작성 2026-10-06(운영자 지시 '한글 관련 클로드 스킬은 Drive 에 올렸다, 프롬프트는 네가 만들라'). **이 문서는 실행 지시가 아니라 다음 세션에 줄 프롬프트**다. 실행은 운영자가 "실행해"라고 할 때.

Drive 확인 결과(2026-10-06): 한글 스킬은 `hwpx-autofill-conversion.zip` 하나(원본 SKILL.md 2,276자 + 샘플 양식 2개). 샘플 양식은 저장소 `scripts/data/hwpx/report_basic.hwpx`·`report_summary.hwpx` 와 바이트까지 같고, 저장소의 `.claude/skills/hwpx-autofill-conversion/SKILL.md` 는 그 원본을 이 저장소 절차(hwpx_report.py·그림·금지 사항)로 넓힌 판이다. 그러므로 세션은 **저장소의 SKILL.md 를 따르고**, Drive 판은 원칙(양식 XML 을 분류해 그 문단을 원형으로 채운다, 결과는 반드시 .hwpx)의 출처로만 본다.

---

# 역할
당신은 한컴오피스 문서 자동화 엔지니어(OWPML/KS X 6101 HWPX 구조, header.xml 스타일 참조 체계, 표 셀 격자 `cellAddr`/`cellSpan`/`cellSz`, zip 패키징 규칙)이자 공공기관 문서 담당자다. 운영자는 현직 지방공무원이며 이 사이트(daitda.co.kr, Astro 정적 사이트, 서버·AI 호출 없음)의 표·기업 카드·검토 의견서를 **한글(HWP)에서 바로 열어 쓰는 파일**로 받고 싶다. 저장소 지침 `CLAUDE.md` 와 스킬 `.claude/skills/hwpx-autofill-conversion/SKILL.md` 를 먼저 읽는다.

# 배경(사실)
- 2026-09-27: 브라우저에서 HWPX 를 만드는 `src/scripts/hwpx.ts` + `scripts/hwpx_template.py`(→ `public/hwpx/template.json`: 양식의 header.xml·용지 문단·표 원형을 JSON 으로 내보내고 브라우저가 **section0.xml 을 새로 써서** zip 으로 묶음)로 기업 카드 HWP·표 HWP 를 냈다.
- 2026-10-01 운영자 확인: 그 HWPX 가 한글에서 깨져 **PDF(pdf.ts)로 바꾸고 hwpx.ts 는 쓰지 않는다.** 2026-10-06: Word(.docx, `company_docx.ts`)를 추가. 클립보드 「한글 표 복사」(table_tools.ts, text/html+TSV)는 유지.
- 반면 `scripts/hwpx_report.py`(정책제안 리포트 → 양식 `report_basic.hwpx` 를 **복제해 채우는** 방식, 그림 BinData·manifest 포함, `--check`)의 산출물 `public/hwpx/<id>.hwpx`·`<id>-요약.hwpx` 는 한글에서 열렸다(운영자 양식 제공 2026-09-27, 리포트 메뉴에 게시 중).
- 즉 **같은 양식·같은 스타일 id 인데 '문단을 새로 쓴 쪽'만 깨졌다.** 스킬의 원칙("새 문단을 만들지 말고 양식의 문단을 deepcopy 해 글자만 바꾼다", "네임스페이스 접두어 보존", "mimetype 은 STORED 첫 항목")이 깨진 원인을 가리킨다.
- 한글(한컴오피스)은 이 세션 환경과 GitHub 러너에 없다. 실물 열림 시험은 운영자가 국내 PC 에서 한다. 시험표는 `docs/design/hwpx-compat.md`(2026-10-06, 빈 표).

# 목표
1. hwpx.ts 가 깨진 **원인을 XML 수준에서 특정**하고(추정이 아니라 diff 로), 2. 모든 HWPX 산출물을 **양식 복제(template-clone) 방식 하나로 통일**하며, 3. 한글 없이도 돌릴 수 있는 **자동 구조 검사**와 운영자가 채우는 **실물 시험 매트릭스**를 갖춰, 4. 시험을 통과한 산출물만 사이트에 노출하는 **관문(gate)** 을 둔다. 통과 전까지 사이트의 HWPX 단추는 켜지 않는다(운영자 확인 2026-10-01 유지).

# 1. 진단 — 왜 깨졌나
- 비교 쌍: (A) 한글에서 열린 파일 `public/hwpx/2026-10-06-policy-manufacturing-ax-sewing.hwpx`(hwpx_report.py) / (B) hwpx.ts 가 만든 파일(세션에서 Playwright 로 기업 페이지 「기업 카드 HWP」 경로를 임시 복원해 받거나, template.json 과 hwpx.ts 의 `buildHwpx()` 를 Node 로 호출해 생성). 둘을 풀어 `Contents/header.xml`·`section0.xml`·`content.hpf`·`META-INF/manifest.xml`·`mimetype`·`Preview/` 를 항목별로 대조한다.
- 점검 항목(표로 보고): ① zip 첫 항목이 `mimetype` 이고 STORED 인가 ② `content.hpf` 의 manifest·spine 이 실제 파일과 맞는가(section0·header·settings·Preview) ③ `settings.xml`·`version.xml` 유무 ④ section0 의 첫 문단에 용지·구역 설정(`hp:secPr`, `hp:pagePr`, `hp:colPr`)이 양식과 같은 위치·속성으로 있는가 ⑤ 모든 `paraPrIDRef`·`charPrIDRef`·`styleIDRef`·`borderFillIDRef`·`tabPrIDRef`·`numberingIDRef` 가 header.xml 에 존재하는가(참조 무결성) ⑥ `hp:p` 의 `id`·`paraPrIDRef`·`styleIDRef`·`pageBreak`·`columnBreak`·`merged` 속성 집합이 양식 문단과 같은가 ⑦ `hp:run` 안 `hp:t` 의 특수문자·줄바꿈(`hp:lineBreak`·`hp:tab`) 처리 ⑧ `hp:linesegarray` 를 아예 뺐는지, 뺐다면 한글이 받아들이는지(양식 문단은 갖고 있다 — 복제하면 자동 해결) ⑨ 표: `hp:tbl` 의 `rowCnt`·`colCnt` 와 실제 `hp:tr`·`hp:tc` 수, 각 `hp:tc` 의 `cellAddr`(colAddr·rowAddr)·`cellSpan`·`cellSz`·`cellMargin`·`borderFillIDRef`, `hp:subList` 안 문단의 paraPr, 병합 셀 격자 합계 = colCnt ⑩ 네임스페이스 선언(hp·hs·hc·hh·hml·ha·hp10 …)이 루트에 모두 있고 접두어가 양식과 같은가 ⑪ XML 선언·인코딩(UTF-8, BOM 없음) ⑫ `Preview/PrvText.txt` 유무(없어도 열리는지는 시험 항목).
- 결과를 `docs/design/hwpx-diagnosis.md` 에 '항목 · (A) · (B) · 차이 · 깨짐 원인 가능성(상·중·하)' 표로. 추정은 '가능성'으로만 적고, 확정은 실물 시험(4절) 뒤에.

# 2. 구조 검사기 `scripts/hwpx_check.py`(한글 없이 돌리는 자동 검사)
- 입력 .hwpx 하나 또는 폴더. 1절 ①~⑫ 를 규칙으로 구현해 PASS/FAIL 과 위치(파일·문단 id·셀 주소)를 출력. 종료 코드로 CI 에서 쓸 수 있게. 기존 `hwpx_report.py --check`(XML 열림·그림 참조·BinData·manifest 대조)를 이 검사기로 옮기고 `--check` 는 호출만 남긴다.
- 참조 무결성은 header.xml 을 파싱해 id 집합을 만들고 section 전체 속성을 훑는다. 표 격자 검사는 각 행의 `cellSpan` 을 펼쳐 colCnt 와 맞춘다. 표준 라이브러리만(zipfile·xml.etree).
- 워크플로 `.github/workflows/hwpx_check.yml`: `public/hwpx/**`·`scripts/hwpx_*.py`·`src/scripts/hwpx.ts` 가 바뀐 푸시마다 `public/hwpx/` 전체와 2절 시험 파일을 검사. FAIL 이면 실패.

# 3. 양식 복제 방식으로 통일
- 원칙: **양식 문단·표·셀 XML 을 원형(prototype)으로 두고 DOM 을 복제해 글자만 바꾼다.** 문자열 템플릿으로 `<hp:p>` 를 새로 쓰지 않는다. 브라우저(hwpx.ts)도 같다 — `DOMParser` 로 양식 XML 을 읽어 `cloneNode(true)` 하고 `hp:t` 글자만 바꾼 뒤 `XMLSerializer` 로 쓴다(접두어 보존). `template.json` 은 'header.xml + 용지 문단' 에서 **'양식의 역할별 원형 문단(kicker·title·rule·body·h2·h3·caption·note·src, 표 tbl/tr/tc 원형, 그림 run 원형)의 XML 조각'** 으로 바꾼다. `scripts/hwpx_template.py` 가 양식에서 역할별 원형을 뽑아 내보내고, 역할 ↔ 양식 문단 인덱스는 `config/hwpx_forms.yml` 에 둔다(스킬의 `top[3]·[8]·…` 인덱스를 파일로 옮김).
- 역할 자동 탐지: 양식 문단의 글자 패턴(□·○·-·※ 첫 글자, 로마 숫자 머리표, 표지 제목 위치, 표의 머리 행 굵게)으로 역할을 짐작해 yml 초안을 만들고(`hwpx_template.py --detect <양식>`), 운영자가 확인한다. 운영자가 다른 공문·보고서 양식(.hwpx)을 `scripts/data/hwpx/` 에 넣으면 같은 절차로 양식을 추가한다(스킬 원문 "첨부 양식에 맞춰 작성").
- 산출물 3종을 같은 Block 입력(hwpx.ts·pdf.ts·company_docx.ts 가 공유하는 `Block`)으로: ① 기업 카드(한 장: 개요·지원 이력·재무·협업 후보·출처) ② 표 하나(표 도구 「HWP 표 내려받기」 — 제목 문단 + 표 + 자료 출처 문단, 열 폭은 화면 비율, 숫자 오른쪽, 병합 보존) ③ 사업계획서 검토 의견서(`budget_check.ts`). 단추는 PDF·Word 옆에 두되 **4절 관문 통과 전에는 렌더하지 않는다.**
- 표 셀 격자: `cellAddr`·`cellSpan`·`cellSz` 를 열 폭 합(본문 폭 48188 HWPUNIT, 양식 `report_basic` 기준)에 맞춰 계산하고, 병합은 `cellSpan` 으로만(겹치는 셀을 만들지 않는다). 긴 표는 머리 행 반복(`hp:tr` 의 header 속성, 양식에 있으면 그 속성 이름을 따른다). 20행 넘는 표는 쪽 넘김을 한글에 맡긴다(`pageBreak` 삽입 금지).
- 글꼴: 양식이 가진 글꼴(HY헤드라인M·휴먼명조·맑은 고딕)만 참조한다. header.xml 에 없는 글꼴 id 를 만들지 않는다. 기업 1만여 곳의 파일을 미리 만들지 않는다(Cloudflare Pages 파일 수 제한) — 브라우저 생성 유지.

# 4. 시험 매트릭스와 관문
- `scripts/hwpx_test.py` 가 시험 파일을 `public/hwpx/test/` 에 만든다(이름 `t01-simple.hwpx` …): 표 4종(단순 5×6 / 머리 두 줄 colspan·rowspan / 본문 병합 / 긴 표 60행) × 생성 경로 2개(hwpx_report.py 양식 복제 Python / hwpx.ts 브라우저 — Node 에서 같은 모듈을 불러 생성, 또는 Playwright 로 단추를 눌러 받음) + 그림 1장(PNG BinData) + 기업 카드 샘플 1 + 검토 의견서 샘플 1 = 11개. 값은 실제 사이트 표(`/stats/business/`·`/listed/`·`/stats/<월>`·`/companies/`)에서 가져오되 개인정보 열 없음을 검사기로 확인.
- 자동 검사(2절) 전부 PASS 가 **1차 관문**. 그 다음 운영자가 국내 PC 에서 `docs/design/hwpx-compat.md` A·B·C 표를 채운다(한글 2018/2020/2022/2024·한컴오피스 Web × 열림·테두리·글꼴·병합·줄바꿈·그림 6항목). 채우는 방법을 표 위에 3줄로(파일 열기 → 항목마다 ○/× → 깨진 화면은 캡처해 `docs/design/hwpx-compat/` 에 넣기, 사람 이름·연락처가 보이는 캡처 금지).
- **2차 관문**: 시험표에서 ×가 하나라도 있으면 그 생성 경로의 단추는 켜지 않는다(스킬·프롬프트 원칙: "실패 항목이 있으면 도입하지 않는다"). 결과는 `data/hwpx/compat.json`(`{approved: false, tested: "YYYY-MM-DD", versions: [...], fails: [...]}`)에 운영자가 적고, 페이지는 `approved: true` 일 때만 HWP 단추를 렌더한다(빌드 때 읽음, 원칙 5 와 같은 승인 구조).
- 1차 관문을 통과해도 실물에서 깨지면 1절 표에 '가능성'을 '확정'으로 고치고 원인 항목을 검사기 규칙에 추가한다(재발 방지).

# 5. 한글 표 복사(클립보드)와의 역할 분담
- 클립보드 HTML(2026-10-06, table_tools.ts)은 '한 표를 지금 쓰는 문서에 붙이기', HWPX 는 '붙임 파일로 보내기'(기업 카드·검토 의견서·표 파일). 둘의 서식 규약을 같은 표(맑은 고딕 10pt, 머리 음영 #EEF3FA, 테두리 0.12mm(=0.5pt 근사), 숫자 오른쪽·천 단위, 아래 '자료: … · URL · 받은 날' 문단)로 맞춘다 — HWPX 는 양식의 표 원형 테두리를 쓰므로 양식 쪽을 기준으로 적는다.
- 시험표 A(클립보드) 도 같은 세션에 운영자가 채운다. 둘 다 통과한 뒤 표 도구 메뉴에 「HWP 표 내려받기」를 더한다.

# 6. 수용 기준
① `hwpx_check.py` 가 `public/hwpx/` 전체와 시험 파일 11개에 PASS ② 1절 진단표에 (A)·(B) 차이가 항목별로 적혀 있고 가능성 '상' 항목은 검사기 규칙이 됨 ③ 세 산출물이 같은 Block 입력에서 나오며 PDF·Word·HWPX 의 글자·표 값이 같다(자동 대조: Block 의 셀 값 ↔ section0 의 `hp:t` 순서) ④ 개인정보 열 0건, 평가·순위 문장 0건(검사기에 금지 낱말 검사 추가: 순위·TOP·우수·추천) ⑤ `data/hwpx/compat.json` 의 `approved` 가 false 인 동안 사이트에 HWP 단추가 없다(Playwright 로 확인) ⑥ CI `hwpx_check.yml` 녹색 ⑦ `docs/design/hwpx-compat.md` 에 운영자 시험 절차와 결과 칸, `CLAUDE.md` 에 한 줄.

# 순서
1절 진단 → 2절 검사기(+기존 --check 이관) → 3절 template.json 재설계·hwpx.ts 복제 방식 전환·`hwpx_forms.yml` → 4절 시험 파일·관문·compat.json → 5절 표 도구 연결(단추는 숨김) → 문서·CI → 커밋·PR. 실물 시험은 운영자 몫이므로 세션은 '시험 준비 완료' 상태로 끝낸다.

# 하지 않을 것
- 통과 전 HWPX 단추 노출, 문자열 템플릿으로 `hp:p`·`hp:tc` 생성, header.xml 에 없는 스타일·글꼴 id 참조, 표지·칸에 사람 이름·연락처, 대구시 예산액, 평가·순위·추천 문장, 기업 파일 사전 생성, 서버·AI 호출, 운영자 양식 파일의 로고·직인 이미지 재사용(양식에 있으면 지운다), 한글 설치 파일·상용 변환 서비스 추가.

# 출력 형식
마크다운. 1절 진단표(항목·A·B·차이·가능성) → 2절 검사 규칙 표(규칙·검사 방법·실패 메시지) → 3절 원형 문단 목록(역할·양식 문단 인덱스·charPr/paraPr id)과 Block→HWPX 매핑 표 → 4절 시험 파일 목록과 관문 상태 → 6절 수용 기준 체크 → 변경 파일 목록. 전문 용어는 처음 나올 때 한 줄 풀이(OWPML, HWPUNIT, cellSpan 등). 근거는 측정값(파일 수·PASS 수·diff 항목 수)으로.
