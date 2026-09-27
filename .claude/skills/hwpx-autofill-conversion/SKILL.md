---
name: hwpx-autofill-conversion
description: 한글(HWPX) 양식을 채워 문서를 만든다. 정책제안 리포트는 scripts/hwpx_report.py 로 공공기관 보고서 기본 양식·한 쪽 요약 양식을 자동으로 채우고, 다른 양식은 같은 방식(양식 문단 복제)으로 채운다. 최종 결과는 반드시 .hwpx 파일.
---

# 언제 쓰나
- 정책제안 리포트를 발행하거나 고쳤을 때: `python3 scripts/hwpx_report.py src/content/posts/<파일>.md` → `public/hwpx/<id>.hwpx`(보고서 기본 양식) + `<id>-요약.hwpx`(한 쪽 요약). `--all` 은 발행된 리포트 전부. 결과를 커밋한다. 사이트의 정책 목록·글 머리에 'HWP' 내려받기가 붙는다.
- 운영자가 다른 hwpx 양식과 주제를 주면: 아래 절차로 양식의 문단을 원형 삼아 내용을 채운 새 hwpx 를 만든다.

# HWPX 구조 (zip)
- `mimetype`(application/hwp+zip, 압축 없이 첫 항목) · `META-INF/manifest.xml` · `Contents/content.hpf`(메타·목록) · `Contents/header.xml`(글꼴·문단 모양·글자 모양 charPr·표 테두리 정의) · `Contents/section0.xml`(본문: `<hp:p>` 문단 → `<hp:run charPrIDRef>` → `<hp:t>` 글자, 표는 `<hp:tbl>/<hp:tr>/<hp:tc>/<hp:subList>/<hp:p>`) · `Preview/PrvText.txt`.
- 서식은 header.xml 의 id 를 참조하므로 **새 문단을 만들지 말고 양식의 문단을 복제(deepcopy)해 글자만 바꾼다.** `hp:t` 의 첫 run 만 남기고 나머지 글 run 은 지운다. `hp:linesegarray` 는 두어도 한글이 다시 계산한다.
- 저장할 때 네임스페이스 접두어(hp·hs·hc·hh…)를 그대로 써야 한다(ElementTree 는 `register_namespace`). 문자열 치환보다 트리 조작이 안전하다.

# 채우는 절차 (scripts/hwpx_report.py 가 하는 일)
1. 양식의 최상위 문단을 훑어 역할을 정한다: 표지 제목·날짜·부서 표, 목차 표, 절 머리표(Ⅰ Ⅱ …), 본문 단계 문단(□ HY헤드라인M 15 / ○ 휴먼명조 14 / - 14 / ※ 11), 표(맑은 고딕 12, 머리 행 굵게).
2. 내용을 블록으로 나눈다: `##` → 절, `###` → □, 굵은 첫 문장이 있는 문단 → ○ 한 문단 안에 붉은 굵은 리드 run(header.xml 에 글자 모양을 하나 추가: 원형 charPr + `<hh:bold/>` + textColor #C00000) + 보통 run, 문단 → ○, 목록 → -, 인용 → ※, `<figure>` → 그림 문단(가운데) + 캡션 문단, `**표 N. 제목**` → 표 캡션, 마크다운 표 → 표. 대표 그림(public/figures/<id>/hero.png)은 요약 절 맨 앞에.
3. 표지·목차를 바꿔 넣고, 첫 절 머리표부터 끝까지 지운 뒤 절마다 머리표(로마 숫자·제목) + 단계 문단을 복제해 붙인다.
4. zip 으로 다시 싼다(mimetype 은 STORED 로 첫 항목). `python3 scripts/hwpx_report.py --check <파일>` 로 XML 이 열리는지 본다.

# 지킬 것
- 원문 문장을 그대로 옮긴다(요약·평가·의견 추가 없음). 정책제안서에는 예산액·사업코드를 넣지 않는다.
- 표지의 부서·담당·연락처 표와 부서 이름 상자는 지운다(운영자 지시 2026-09-27). 한 쪽 요약의 소속부서 칸은 날짜만. 어떤 칸에도 사람 이름·연락처를 넣지 않는다.
- 그림은 LG경영연구원 리포트처럼 본문에 넣는다(운영자 지시 2026-09-27): SVG 는 `rsvg-convert -w 1600` 으로 PNG 로, 400KB 넘는 PNG 는 JPEG(폭 1400)로 줄여 `BinData/imageN.<ext>` 에 넣고 `Contents/content.hpf` 의 `<opf:manifest>` 에 `<opf:item id="imageN" href="BinData/imageN.png" media-type="image/png" isEmbeded="1"/>` 를 더한다. 문단에는 `<hp:run><hp:pic …><hc:img binaryItemIDRef="imageN"/>…</hp:pic><hp:t/></hp:run>` (treatAsChar=1, 크기 HWPUNIT = 픽셀×75, 최대 너비 42000, 가운데 정렬 paraPr). 캡션은 그림 아래 가운데 정렬 11pt. rsvg-convert 가 없으면 캡션만 ※ 줄로 남긴다. `--check` 가 그림 참조와 BinData·manifest 를 대조한다.
- 양식 파일: `scripts/data/hwpx/report_basic.hwpx`(보고서 기본), `report_summary.hwpx`(한 쪽 요약). 양식이 바뀌면 파일만 갈아끼우고 문단 역할 인덱스(top[3]·[8]·[12]·[15]·[17]·[19]~[24]·[64])를 다시 확인한다.
