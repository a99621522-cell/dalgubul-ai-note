#!/usr/bin/env python3
"""대구연구개발특구 — 연구개발특구진흥재단 공개 파일 두 개를 합쳐 scripts/data/sources/innopolis_YYYYMMDD.json 으로.

  1) 특구입주기업현황 (15083254, 열: 번호·지역·기관명·지구)  → is_tenant, zone(지구), district(지구→구·군)
  2) 연구소기업 운영현황 (15089826, 열: 구분·기업명·등록연도·현행특구) → is_research_company, registered_year
두 파일 모두 '대구' 행만. 둘 다 주소가 없다. 구·군은 지구로만 채우고(sources_common.INNOPOLIS_DISTRICT),
연구소기업은 이름으로 병합 단계에서 붙인다. 첨단기술기업은 포털에 합성데이터뿐이라 다루지 않는다(보류).
같은 이름이 두 파일에 다 있으면 한 행으로 합쳐 플래그를 둘 다 켠다.

사용: python3 scripts/collect_innopolis.py [--dry-run]
"""
import sys
from datetime import date

from sources_common import INNOPOLIS_DISTRICT, ZONE_LABEL, col, decode_csv, norm, portal_file, write_source

PK_TENANT, PK_RESEARCH = "15083254", "15089826"
DRY = "--dry-run" in sys.argv


def main() -> None:
    today = date.today().isoformat()
    rows: dict[str, dict] = {}   # norm(name) → row
    b, fn, title = portal_file(PK_TENANT)
    t = decode_csv(b); h = t[0]
    i_reg, i_name, i_zone = col(h, "지역"), col(h, "기관명", "기업명"), col(h, "지구")
    n_t = 0
    for r in t[1:]:
        if len(r) <= max(i_reg, i_name, i_zone) or "대구" not in r[i_reg]:
            continue
        n_t += 1
        k = norm(r[i_name])
        row = rows.setdefault(k, {"name": r[i_name], "address": "", "district": "", "sector_code": "", "sector": "", "product": "",
                                  "is_tenant": False, "zone": "", "zone_label": "", "is_research_company": False, "registered_year": "",
                                  "source": "innopolis", "collected": today})
        row["is_tenant"] = True
        row["zone"] = r[i_zone]
        row["zone_label"] = ZONE_LABEL.get(r[i_zone], r[i_zone])
        row["district"] = INNOPOLIS_DISTRICT.get(r[i_zone], "")
    print(f"[innopolis] {title}: 대구 입주기업 {n_t}곳")
    b2, fn2, title2 = portal_file(PK_RESEARCH)
    t2 = decode_csv(b2); h2 = t2[0]
    i_n, i_y, i_z = col(h2, "기업명"), col(h2, "등록연도", "등록년도"), col(h2, "현행특구", "특구")
    n_r = 0
    for r in t2[1:]:
        if len(r) <= max(i_n, i_y, i_z) or "대구" not in r[i_z]:
            continue
        n_r += 1
        k = norm(r[i_n])
        row = rows.setdefault(k, {"name": r[i_n], "address": "", "district": "", "sector_code": "", "sector": "", "product": "",
                                  "is_tenant": False, "zone": "", "zone_label": "", "is_research_company": False, "registered_year": "",
                                  "source": "innopolis", "collected": today})
        row["is_research_company"] = True
        row["registered_year"] = r[i_y]
    both = sum(1 for v in rows.values() if v["is_tenant"] and v["is_research_company"])
    print(f"[innopolis] {title2}: 대구 연구소기업 {n_r}곳 · 두 명단 겹침 {both}곳 · 합계 {len(rows)}곳")
    zones: dict[str, int] = {}
    for v in rows.values():
        if v["zone"]:
            zones[v["zone"]] = zones.get(v["zone"], 0) + 1
    print("[innopolis] 지구별:", zones)
    if DRY:
        return
    p = write_source("innopolis", list(rows.values()), {"datasets": {"tenant": PK_TENANT, "research_company": PK_RESEARCH},
                                                        "titles": [title, title2], "files": [fn, fn2],
                                                        "note": "주소 없음. district 는 지구로만 채움(융합R&D지구는 비움). 첨단기술기업은 실데이터 없음(보류)."})
    print(f"[innopolis] 저장: {p.name} ({p.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
