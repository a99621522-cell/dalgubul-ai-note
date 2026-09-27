# 참고자료 창고 (data/refs)

운영자가 Google Drive 폴더 **「다잇다 참고자료」** 에 올린 보고서·통계·전략 문서를 운영 세션이 읽고 **요약만** 여기에 남긴다. 원문 파일(PDF·HWP)은 저장소에 넣지 않는다. 정책제안 리포트 작성 세션은 `python3 scripts/report_context.py --area <key>` 의 "[참고자료 창고]" 항목으로 이 요약을 받아 근거로 쓴다.

## 규칙
- 파일 하나 = `data/refs/<slug>.json` 하나. slug 는 `<기관약칭>-<YYYY-MM>-<주제-영문-또는-한글>`.
- 공개 자료만(정부·지자체·공공기관·연구기관·협회 발간물). 비공개·내부 자료, 개인정보가 든 파일은 요약하지 않고 `skipped` 로 기록한다.
- 요약은 작성자의 문장으로 쓴다(원문 문장 복사 금지, 인용은 15단어 이내). 수치는 원문 그대로, 쪽 번호를 단다.
- 평가·비판 없음. 자료의 논지와 수치, 대구 시사점(사실 접점)만.
- `public_url` 은 검색으로 확인한 공개 페이지(PRISM·기관 누리집)만. 없으면 비워 두고, 리포트에서는 그 자료의 수치를 출처 목록에 넣지 않는다(검사기가 URL 없는 출처를 막는다). 자료의 존재와 프레임은 본문에서 "기관·제목·발행월" 로 언급할 수 있다.
- Drive 커넥터는 파일당 10MB 까지 읽는다. 큰 파일은 `skipped` 에 사유를 적고 운영자에게 알린다(글자 PDF 원본이면 대개 10MB 아래).

## JSON 형식
```json
{
  "slug": "kihasa-2025-12-health-data-ai-strategy",
  "file": "(보고서)보건의료 데이터·인공지능 활용전략 및 실행계획 수립을 위한 기초 연구.pdf",
  "drive_id": "1Cd66…",
  "title": "보건의료 데이터·인공지능 활용전략 및 실행계획 수립을 위한 기초 연구",
  "publisher": "한국보건사회연구원 (보건복지부 용역보고서)",
  "published": "2025-12",
  "pages": 208,
  "doc_type": "연구보고서",
  "areas": ["healthcare"],
  "keywords": ["의료데이터", "보건의료 AI"],
  "toc": ["제1장 서론", "…"],
  "summary": "작성자 문장으로 20줄 안팎. 논지·구조·핵심 수치·대구 접점.",
  "key_figures": [{"text": "…", "page": 92}],
  "daegu_notes": ["대구 시사점 사실 접점 한 줄씩"],
  "public_url": "",
  "added": "2026-09-27",
  "read_status": "full|partial|skipped",
  "note": "OCR 여부, 못 읽은 쪽 등"
}
```
`areas` 값은 config/pledge_areas.yml 의 key(mobility / robot-physical-ai / semiconductor / manufacturing-ax / healthcare / ai-sw-startup / machinery / automotive / textile / root). 검사: `python3 scripts/refs.py --check`.
