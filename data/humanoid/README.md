# 휴머노이드 부품 수입 대체 조사 원자료

운영자 지시 2026-11-02(중국·한국 휴머노이드 부품 공급망 비교, 목적은 수입품 대체). 사이트는 이 폴더를 읽지 않는다.

- `trade/comtrade_kor.csv` — UN Comtrade 공개 미리보기 API(키 없음)의 한국 보고 연간 수출입, HS 6단위, 2022~2025. 수입은 상대국 전부, 수출은 세계 합계만. 금액 USD(수입 CIF), 순중량 kg.
- `trade/summary.csv` — 연도·HS 별 수입·수출·수지와 중국·일본·독일·미국·대만(기타 아시아) 수입 비중(이 자료의 나눗셈).
- `trade/index.json` — 받은 날·행 수·빠진 요청(8479.50 산업용 로봇은 미리보기 API 가 대부분 빈 응답).
- 품목 목록과 HS 대응은 `config/humanoid_hs.yml`. HS 6단위는 휴머노이드 전용이 아니라 산업용·가전·자동차용이 섞인 값이다.
- 다시 받기: `scripts/fetch_comtrade.py`(워크플로 `comtrade.yml`, 수동 또는 스크립트·설정 푸시 때). 이 세션 환경은 comtradeapi.un.org 차단.
