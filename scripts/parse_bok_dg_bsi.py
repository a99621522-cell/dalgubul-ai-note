#!/usr/bin/env python3
"""한국은행 대구경북본부 「대구경북지역 주요 경제지표」(경제통계 PDF)의 '7. 기업경기실사지수(대구경북)' 표 → data/bok/dg_bsi.csv.

운영자 지시 2026-10-12 '대구경북 주요 경제지표로 BSI 채워 넣어'. 한국은행 ECOS 지역 BSI(data/ecos/bsi-region.csv)는 2025-09 에서 멈춰,
운영자가 올린 이 자료로 대구경북 BSI 를 잇는다. 표는 대구경북 합산 값이다(대구 단독 값 아님). 값은 표 그대로 옮긴다.
열: 제조업 — 업황·매출·설비투자·채산성·인력사정·자금사정 각 실적/전망, 비제조업 — 업황·매출·채산성·인력사정·자금사정 각 실적/전망.
전망은 그 달에 조사한 다음 달 전망. 마지막 달은 전망만 있는 행이 있다(실적은 빈칸).
사용: python3 scripts/parse_bok_dg_bsi.py <PDF 또는 pdftotext -layout 결과 txt> [--issue 2026-10]
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bok" / "dg_bsi.csv"
ITEMS = {"제조업": ["업황", "매출", "설비투자", "채산성", "인력사정", "자금사정"],
         "비제조업": ["업황", "매출", "채산성", "인력사정", "자금사정"]}


def text_of(p: Path) -> str:
    if p.suffix.lower() == ".pdf":
        return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout
    return p.read_text(encoding="utf-8")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    issue = argv[argv.index("--issue") + 1] if "--issue" in argv else ""
    t = text_of(Path(argv[0]))
    start = [m.start() for m in re.finditer(r"기업경기실사지수", t)]
    if len(start) < 2:
        print("표를 찾지 못함")
        return 1
    body = t[start[1]: t.index("소비자동향지수", start[1])]
    rows, sector, year = [], "", ""
    for ln in body.splitlines():
        s = ln.strip()
        if s.startswith("비제조업"):
            sector, year = "비제조업", ""
            continue
        if s.startswith("제조업"):
            sector, year = "제조업", ""
            continue
        m = re.match(r"^(?:(\d{4})\.)?\s*(\d{1,2})\s+([\d\s]+)$", s)
        if not sector or not m:
            continue
        year = m.group(1) or year
        nums = m.group(3).split()
        k = len(ITEMS[sector])
        month = f"{year}-{int(m.group(2)):02d}"
        if len(nums) == 2 * k:
            pairs = [(nums[2 * i], nums[2 * i + 1]) for i in range(k)]
        elif len(nums) == k:          # 마지막 달: 전망만
            pairs = [("", nums[i]) for i in range(k)]
        else:
            print(f"  건너뜀 {sector} {month}: 칸 {len(nums)}개")
            continue
        for item, (a, o) in zip(ITEMS[sector], pairs):
            rows.append({"month": month, "sector": sector, "item": item, "actual": a, "outlook": o, "issue": issue})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["month", "sector", "item", "actual", "outlook", "issue"])
        w.writeheader()
        w.writerows(rows)
    months = sorted({r["month"] for r in rows})
    print(f"저장: {OUT.relative_to(ROOT)} {len(rows)}행, {months[0]}~{months[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
