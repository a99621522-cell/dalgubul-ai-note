# 지침별 검토표 (data/guidelines/checks)

기업지원기관이 낸 예산요구서·집행 서류·결산서(정산보고서)를 지침대로 작성·집행했는지 볼 때 쓰는 항목표. 항목마다 근거 조문과 원문 문구를 붙인다.
지침 본문은 `../<key>.txt.gz`(scripts/fetch_guidelines.py), 목록은 `../index.json`. 검토표는 세션이 본문을 읽고 초안을 쓰고 운영자가 검토한다(status: draft → reviewed).
원칙: 조문을 그대로 옮기고 해석·평가를 덧붙이지 않는다. 지침 개정(시행일)이 바뀌면 다시 대조한다. 사이트 `/programs/guidelines/` 가 이 표를 보여 주고 한글로 내려받게 한다.

형식(JSON):
- key: 지침 key(index.json 과 같음) · name · eff(대조한 본문의 시행일) · status(draft|reviewed) · added
- items[]: { id, stage(예산요구서|집행|결산서), item(검토 항목 한 줄), check(무엇을 어디서 확인하는지), basis(조문), quote(원문 문구, 짧게), doc(검토 대상 서류) }
