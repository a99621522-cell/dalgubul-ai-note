#!/usr/bin/env bash
# 매월 팩토리온 갱신 루틴 (국내 PC 에서). 사용: scripts/monthly.sh "<전국(개별,계획)입주업체현황.xlsx>" ["<산단공관할단지내_입주업체리스트.xlsx>"]
# 1 기업·단지 CSV 갱신 → 2 산단 외 기업·태그 → 3 월간 집계 → 4 그래프
set -euo pipefail
cd "$(dirname "$0")/.."
MAIN="${1:?전국 입주업체현황 xlsx 경로}"
KICOX="${2:-}"
python3 scripts/import_factoryon.py "$MAIN" ${KICOX:+"$KICOX"}
python3 scripts/import_extra.py
python3 scripts/build_stats.py
python3 scripts/render_charts.py
echo "완료. git status 로 확인 뒤 커밋."
