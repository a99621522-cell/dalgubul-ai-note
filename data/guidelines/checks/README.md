# 지침별 검토표 (data/guidelines/checks)

기업지원기관이 낸 예산요구서·집행 서류·결산서(정산보고서)를 지침대로 작성·집행했는지 볼 때 쓰는 항목표. 항목마다 근거 조문과 원문 문구를 붙인다.
지침 본문은 `../<key>.txt.gz`(scripts/fetch_guidelines.py), 목록은 `../index.json`. 검토표는 세션이 본문을 읽고 초안을 쓰고 운영자가 검토한다(status: draft → reviewed).
원칙: 조문을 그대로 옮기고 해석·평가를 덧붙이지 않는다. 지침 개정(시행일)이 바뀌면 다시 대조한다. 사이트 `/programs/guidelines/` 가 이 표를 보여 주고 한글로 내려받게 한다.

형식(JSON):
- key: 지침 key(index.json 과 같음) · name · eff(대조한 본문의 시행일) · status(draft|reviewed) · added
- items[]: { id, stage(예산요구서|집행|결산서), item(검토 항목 한 줄), check(무엇을 어디서 확인하는지), basis(조문), quote(원문 문구, 짧게), doc(검토 대상 서류) }

## 자동 판정 규칙 (rules.json)
`/programs/guidelines/check/`(사업계획서 지침 검토기, `src/scripts/budget_check.ts`)가 쓴다. 대상은 예산을 집행하는 사업계획서(집행 서류·정산보고서도 가능). 사용자가 올린 PDF·HWPX·TXT 를 브라우저 안에서만 읽어(서버·AI 호출 없음) 공백을 뺀 글자에 항목별 정규식을 맞춘다.
- `doc_patterns`: 지침 key 마다 '이 지침이 적용되는 문서' 단서 낱말. 가장 많이 맞은 지침을 기본 선택(사용자가 바꿀 수 있음).
- `stage_patterns`: 예산요구서·집행·결산서 단서 낱말. `plan_patterns` 에 맞으면 사업계획서로 보고 세 단계를 모두 대조한다. `plan_sections`: 계획서 구성 점검 8가지(name·patterns(모두 있어야)·basis·fix).
- `items["<key>/<id>"]`: 검토표 항목마다 하나. `type` — `any`(하나라도 있으면 확인됨) · `all`(모두 있어야, 빠진 것은 보완 필요) · `absent`(있으면 검토 필요) · `flag`(있으면 조건 확인) · `if_then`(`cond` 가 있으면 `then` 모두 필요, 없으면 해당 없음) · `number`(`pattern` 의 % 값을 `min`/`max` 와 비교, 둘 다 없으면 값만 보여 줌) · `amount_then`(`amount` 의 최대 금액이 `min` 이상이면 `then` 필요) · `days`(`frm`·`to` 날짜 차이가 `max_days` 이하) · `manual`(문서로 판정 불가, 힌트만). `warn` 은 어느 type 에나 덧붙여 발견되면 검토 필요. `fix` 는 '고칠 방법' 문장(없으면 검토표의 check).
- 판정은 참고용이며 조문 대조와 최종 판단은 담당자가 한다. 어긋나는 사례가 나오면 규칙을 고친다(항목 수와 규칙 수가 같아야 한다 — `python3 -c` 로 대조).
