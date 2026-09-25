#!/usr/bin/env python3
"""지식산업센터 건물 목록 갱신 — 한국산업단지공단 '전국지식산업센터현황'(공공데이터포털 15117154 / 팩토리온 자료실) → scripts/data/kic_buildings.csv

사용: python3 scripts/import_kic.py <전국지식산업센터현황.csv 또는 .xlsx> [--as-of 2025-06]

파일 열(포털 설명): 시도, 시군구, 지식산업센터명, 입지구분, 회사명, 등록구분, 단지명, 관리기관, 산업단지구분, 현황, …,
공장대표주소(도로명), 공장대표주소(지번). 행은 센터 안 등록공장 단위라 센터명+도로명주소로 묶어 건물 하나로 만든다.
대구만 남기고, 기존 kic_buildings.csv 의 손으로 넣은 행(source 가 파일이 아닌 것)은 유지한다.
회사명은 저장하지 않는다(입주기업 판정은 주소로 한다).
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "data" / "kic_buildings.csv"
COLS = {
    "sido": ["시도", "시도명"],
    "sigungu": ["시군구", "시군구명"],
    "name": ["지식산업센터명", "지식산업센터", "센터명"],
    "road": ["공장대표주소(도로명)", "도로명주소", "공장대표주소_도로명", "주소(도로명)"],
    "jibun": ["공장대표주소(지번)", "지번주소"],
}
_ROAD = re.compile(r"대구광역시\s+(\S+[구군])\s+(.+(?:로|길)\s*\d+(?:-\d+)?)")  # greedy: '성서공단로35길 42' 전체


def pick(r: dict, k: str) -> str:
    for c in COLS[k]:
        if c in r and r[c] not in (None, ""):
            return str(r[c]).strip()
    return ""


def read_any(p: Path) -> list[dict]:
    if p.suffix.lower() in (".xlsx", ".xls"):
        import pandas as pd  # 엑셀일 때만 (repair_factoryon.py 와 같은 조건)
        return pd.read_excel(p, dtype=str).fillna("").to_dict("records")
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return list(csv.DictReader(raw.decode(enc).splitlines()))
        except UnicodeDecodeError:
            continue
    return list(csv.DictReader(raw.decode("cp949", errors="replace").splitlines()))


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    as_of = argv[argv.index("--as-of") + 1] if "--as-of" in argv else ""
    src = Path(argv[0])
    rows = read_any(src)
    found: dict[tuple[str, str], str] = {}
    for r in rows:
        if "대구" not in (pick(r, "sido") + pick(r, "road") + pick(r, "jibun")):
            continue
        m = _ROAD.search(pick(r, "road"))
        if not m:
            continue  # 건물번호 없는 주소는 거리 전체를 잡아 버리므로 쓰지 않는다
        district, road = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
        found[(district, road)] = pick(r, "name") or "지식산업센터(명칭 미확인)"
    if not found:
        print("대구 지식산업센터 행을 찾지 못함 (열 이름·주소 형식 확인)", file=sys.stderr)
        return 1
    keep = []
    if OUT.exists():
        for r in csv.DictReader(open(OUT, encoding="utf-8")):
            if (r["district"], r["road_address"]) not in found and not r["source"].startswith("전국지식산업센터현황"):
                keep.append(r)
    out_rows = keep + [{"name": n, "district": d, "road_address": rd, "source": f"전국지식산업센터현황({src.name})", "as_of": as_of}
                       for (d, rd), n in sorted(found.items())]
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "district", "road_address", "source", "as_of"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"대구 지식산업센터 {len(found)}동 → {OUT.relative_to(ROOT)} (기존 수기 행 {len(keep)} 유지)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
