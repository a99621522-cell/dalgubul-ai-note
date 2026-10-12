#!/usr/bin/env python3
"""한국산업단지공단 「전국산업단지 현황통계」(분기, 엑셀) → 대구 산업단지 행만 data/complexes/kicox_stats.csv.

운영자 지시 2026-10-12: 운영자가 올린 「2026년 2분기 전국산업단지 현황통계」의 분양률·입주업체·가동업체를 현황판 산업단지별 표에 붙인다.
'전국산업단지현황' 시트(상위·하위 단지 모두)에서 시도가 대구인 행을 그대로 옮긴다(값을 만들지 않음, '-' 는 0이 아니라 빈칸).
`fo_name` 은 기업 사전(팩토리온) 단지 이름과의 대응 — FO_MAP 에 적은 것만, 여러 산단공 단지가 한 팩토리온 단지면 같은 이름을 둔다.
이 통계에는 단지별 생산·수출·고용 칸이 없다(2026년 2분기 판 확인).
사용: python3 scripts/import_kicox_stats.py <엑셀> [--quarter 2026-2]
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "complexes" / "kicox_stats.csv"
COLS = ["quarter", "type", "district", "name", "sub", "status", "designated_k_m2", "managed_k_m2", "industrial_k_m2", "sale_target_k_m2",
        "sold_k_m2", "unsold_k_m2", "sale_rate", "firms_contracted", "firms_operating", "fo_name"]
# 산단공 단지 이름(공백·괄호 표기 뗀 것) → 기업 사전 단지 이름
FO_MAP = {
    "대구국가": "대구국가산업단지",
    "성서1차": "성서지방산업단지", "성서2차": "성서지방산업단지", "성서3차": "성서지방산업단지", "성서4차": "성서지방산업단지",
    "성서5차첨단": "성서5차첨단산업단지",
    "대구출판": "대구인쇄출판밸리",
    "대구이시아폴리스": "대구이시아폴리스일반산업단지",
    "검단": "북구검단일반산업단지",
    "대구염색": "대구염색일반산업단지",
    "달성1차": "달성일반산업단지",
    "달성2차①": "달성2차일반산업단지",
    "달성2차(외국인)②": "달성외국인투자지역",
    "대구테크노폴리스": "대구테크노폴리스일반산업단지",
    "대구제3": "대구제3일반산업단지",
    "금호워터폴리스": "대구금호워터폴리스일반산업단지",
    "서대구": "서대구일반산업단지",
    "구지": "대구구지농공단지", "옥포": "대구옥포농공단지", "군위": "군위농공단지", "효령": "군위효령농공단지",
}


def key(name: str) -> str:
    n = re.sub(r"\[[^\]]*\]", "", name.replace("\xa0", " ")).strip()      # [재생사업지구] 표기 떼기
    n = re.sub(r"\s*\((구:[^)]*)\)", "", n)
    n = re.sub(r"\s*\(\s*①\s*\+\s*②\s*\)|\s*\(\s*①\s*\)", "", n)
    return n.replace(" ", "")


def num(v):
    if v is None or (isinstance(v, str) and v.strip() in ("-", "")):
        return ""
    return v


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    q = argv[argv.index("--quarter") + 1] if "--quarter" in argv else ""
    wb = openpyxl.load_workbook(argv[0], read_only=True, data_only=True)
    if not q:
        title = next(wb["요약"].iter_rows(values_only=True))
        m = re.search(r"(\d{4})년\s*(\d)분기", " ".join(str(c) for c in title if c))
        q = f"{m.group(1)}-{m.group(2)}" if m else ""
    rows = []
    for r in wb["전국산업단지현황"].iter_rows(min_row=6, values_only=True):
        if not r or r[1] != "대구":
            continue
        raw = str(r[3])
        k = key(raw)
        rows.append({"quarter": q, "type": r[0], "district": r[2], "name": k, "sub": "1" if raw.startswith("\xa0") or raw.startswith(" ") else "",
                     "status": r[4], "designated_k_m2": num(r[5]), "managed_k_m2": num(r[6]), "industrial_k_m2": num(r[7]),
                     "sale_target_k_m2": num(r[8]), "sold_k_m2": num(r[9]), "unsold_k_m2": num(r[10]), "sale_rate": num(r[11]),
                     "firms_contracted": num(r[12]), "firms_operating": num(r[13]), "fo_name": FO_MAP.get(k, "")})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"저장: {OUT.relative_to(ROOT)} {len(rows)}행 ({q}), 기업 사전 단지와 이은 행 {sum(1 for x in rows if x['fo_name'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
