# data/hwpx — 한글(HWPX) 호환 승인 관문

- `compat.json` — `approved: true` 일 때만 사이트에 HWP 단추(표 도구 「HWP 표 내려받기」·「기업 카드 HWP」·「검토 의견서 HWP」)가 보인다. `src/layouts/Base.astro` 가 빌드 때 읽어 `<html data-hwpx="1">` 로 내보내고 `src/scripts/hwpx.ts` 의 `hwpxEnabled()` 가 본다.
- 채우는 사람: 운영자(한글 실물 시험, `docs/design/hwpx-compat.md`). 자동 구조 검사(`scripts/hwpx_check.py`, CI `hwpx_check.yml`)가 PASS 여도 실물 시험 전에는 `approved: false` 를 유지한다.
- `tested`: 시험 날짜(YYYY-MM-DD), `versions`: 시험한 한글 판(예: ["2020", "2022", "2024", "web"]), `paths.python`/`paths.browser`: 경로별 통과(true/false), `fails`: 실패 항목(파일·항목·현상). × 가 하나라도 있으면 그 경로의 단추는 켜지 않는다.
