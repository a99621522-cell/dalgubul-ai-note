#!/usr/bin/env bash
# 매월 팩토리온 갱신 루틴 (국내 PC 에서). 사용: scripts/monthly.sh "<전국(개별,계획)입주업체현황.xlsx>" ["<산단공관할단지내_입주업체리스트.xlsx>"]
# 1 기업·단지 CSV 갱신 → 2 산단 외 기업·태그 → 3 월간 집계 → 4 그래프 → 5 산업연관표 빈 고리·유치 후보 (거래표·부문분류표가 scripts/data/io/ 에 있을 때)
set -euo pipefail
cd "$(dirname "$0")/.."
MAIN="${1:?전국 입주업체현황 xlsx 경로}"
KICOX="${2:-}"
python3 scripts/import_factoryon.py "$MAIN" ${KICOX:+"$KICOX"}
python3 scripts/import_extra.py
python3 scripts/build_stats.py
python3 scripts/render_charts.py
if ls scripts/data/io/*.xls* >/dev/null 2>&1; then
  python3 scripts/attract.py --factoryon "$MAIN"
else
  echo "scripts/data/io/ 에 산업연관표 엑셀이 없어 attract.py 는 건너뜀 (scripts/data/io/README.md)"
fi
echo "완료. git status 로 확인 뒤 커밋."
