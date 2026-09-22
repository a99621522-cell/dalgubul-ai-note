# inbox — 외부 크롤러 결과 넣는 곳

Claude Code 웹 크롤러 에이전트 등으로 수집한 결과를 이 폴더에 JSON 으로 두면
다음 `collect.py` 실행 때 읽어서 Gemini 요약 → 초안으로 만든다. 처리된 파일은 `done/` 으로 이동.

형식 (배열):
```json
[
  {"title": "공고 제목", "url": "https://...", "source": "대구테크노파크",
   "category": "grants", "body": "본문 텍스트(선택)", "deadline": "2026-10-15"}
]
```
category: economy | grants | policy

크롤러 에이전트에게 줄 지시 예:
"대구시 보도자료 게시판 최근 30건을 수집해서 title, url, source, category=economy, body 로
scripts/inbox/daegu-press.json 에 저장해줘. 공공기관 사이트만, 하루 1회, 개인정보 없는 글만."
