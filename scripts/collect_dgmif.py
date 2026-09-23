#!/usr/bin/env python3
"""첨복단지 — 「대구경북첨단의료산업진흥재단 입주기업 현황」(공공데이터포털 파일데이터 15020969)
→ scripts/data/sources/dgmif_YYYYMMDD.json

재단 홈페이지(dgmif.re.kr)는 접속이 되지 않아 이 파일이 유일한 출처다. 필지 단위 명단이라 기업뿐 아니라
연구기관·공공기관도 섞여 있다 → 업종으로 corp_type 을 '기관'/'기업'으로 나눠 둔다(둘 다 '첨복단지 입주'로 표시).
열: 번호, 필지번호, 주소, 면적(제곱미터), 기업 및 기관명, 업종, 대표전화번호
저장하지 않는 것: 대표전화번호.

사용: python3 scripts/collect_dgmif.py [--dry-run]
"""
import re
import sys
from datetime import date

from sources_common import col, decode_csv, district_of, portal_file, write_source

PK = "15020969"
DRY = "--dry-run" in sys.argv
ORG = re.compile(r"연구기관|연구원|연구소|공공|재단|센터|대학|병원|진흥원|공단|공사|협회|학교|기술원|지원단")


def main() -> None:
    b, fn, title = portal_file(PK)
    print(f"[dgmif] {title} · {fn} · {len(b)/1024:.0f} KB")
    rows = decode_csv(b); h = rows[0]
    i_lot, i_addr, i_area, i_name, i_sector = col(h, "필지"), col(h, "주소"), col(h, "면적"), col(h, "기업 및 기관명", "기관명", "기업명"), col(h, "업종")
    out = []
    for r in rows[1:]:
        if len(r) <= max(i_lot, i_addr, i_area, i_name, i_sector) or not r[i_name]:
            continue
        name, sector = r[i_name], r[i_sector]
        is_org = bool(ORG.search(sector)) or bool(ORG.search(name))
        out.append({
            "name": name, "address": r[i_addr], "district": district_of(r[i_addr]) or "동구",
            "sector_code": "", "sector": sector, "product": "",
            "corp_type": "기관" if is_org else "기업", "lot": r[i_lot], "area_m2": r[i_area],
            "zone_label": "첨복단지", "source": "dgmif", "collected": date.today().isoformat(),
        })
    n_org = sum(1 for x in out if x["corp_type"] == "기관")
    print(f"[dgmif] 입주 {len(out)}곳 (기업 {len(out)-n_org} · 기관 {n_org})")
    if DRY:
        return
    p = write_source("dgmif", out, {"dataset": PK, "title": title, "file": fn,
                                     "note": "필지 단위 명단. 기관(연구·공공)은 corp_type=기관. 대표전화번호는 저장하지 않음."})
    print(f"[dgmif] 저장: {p.name} ({p.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
