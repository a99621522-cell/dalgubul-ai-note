# data/notices — 지원사업 공고 데이터 (글 아님)

`scripts/collect.py` 가 매일 기업마당 API·inbox 공고를 글로 만들지 않고 여기 `notices.csv` 에 사실만 덧붙인다:
수집일, 제목, 기관, 소관부처, 범위(대구 한정/전국), 마감, 원문 링크, 공약 분야 키, 예산 대조(사업코드·사업명·부처·2026 예산·유사도).
원문 요약·재작성 없음, Gemini 호출 없음. 정책제안 리포트(scripts/report_context.py)의 "타 기관 공고 동향" 근거로 쓴다.
