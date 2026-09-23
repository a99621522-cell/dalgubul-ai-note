#!/usr/bin/env python3
"""벤처확인기업 — 중소벤처기업부 「벤처기업명단」(공공데이터포털 파일데이터 15084581, 매월 갱신) → 대구만
→ scripts/data/sources/venture_YYYYMMDD.json

지시서는 '벤처기업확인기관 벤처확인기업 공시 API' 를 말했지만 포털에 그 이름의 API 는 없고, 이 파일이 요구 항목
(업종·주요제품·확인 유형·유효기간)을 전부 담고 있어 이것을 쓴다. 키 불필요 → VENTURE_KEY 도 필요 없다.

열(2026-04 파일): 연번, 업체명, 대표자명(익명), 벤처확인유형, 지역, 주소(구 단위), 업종분류(기보), 업종명(11차), 주생산품,
벤처유효시작일, 벤처유효종료일, 벤처확인기관, 신규_재확인
저장하지 않는 것: 대표자명(익명 처리돼 있어도 개인 항목이라 제외).

사용: python3 scripts/collect_venture.py [--dry-run]
"""
import sys
from datetime import date

from sources_common import col, decode_csv, district_of, portal_file, write_source

PK = "15084581"
DRY = "--dry-run" in sys.argv


def main() -> None:
    b, fn, title = portal_file(PK)
    print(f"[venture] {title} · {fn} · {len(b)/1024:.0f} KB")
    rows = decode_csv(b)
    hdr = rows[0]
    i = {
        "name": col(hdr, "업체명"), "type": col(hdr, "벤처확인유형"), "region": col(hdr, "지역"), "addr": col(hdr, "주소"),
        "sector_kb": col(hdr, "업종분류"), "sector": col(hdr, "업종명"), "product": col(hdr, "주생산품"),
        "from": col(hdr, "유효시작"), "to": col(hdr, "유효종료"), "agency": col(hdr, "확인기관"), "renew": col(hdr, "신규_재확인", "재확인", required=False),
    }
    out = []
    for r in rows[1:]:
        if len(r) <= max(v for v in i.values() if v is not None):
            continue
        if r[i["region"]] != "대구" and not r[i["addr"]].startswith("대구"):
            continue
        out.append({
            "name": r[i["name"]], "address": r[i["addr"]], "district": district_of(r[i["addr"]]),
            "sector_code": "", "sector": r[i["sector"]], "sector_kb": r[i["sector_kb"]], "product": r[i["product"]],
            "venture_type": r[i["type"]], "valid_from": r[i["from"]], "valid_to": r[i["to"]],
            "agency": r[i["agency"]], "renew": r[i["renew"]] if i["renew"] is not None else "",
            "source": "venture", "collected": date.today().isoformat(),
        })
    today = date.today().isoformat()
    active = sum(1 for x in out if x["valid_to"] >= today)
    by_type: dict[str, int] = {}
    for x in out:
        by_type[x["venture_type"]] = by_type.get(x["venture_type"], 0) + 1
    print(f"[venture] 대구 {len(out):,}곳 (유효기간 내 {active:,}) · 유형 {by_type}")
    if DRY:
        return
    p = write_source("venture", out, {"dataset": PK, "title": title, "file": fn,
                                       "note": "중소벤처기업부 벤처기업명단(월간). 주소는 구 단위. 대표자명은 저장하지 않음."})
    print(f"[venture] 저장: {p.name} ({p.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
