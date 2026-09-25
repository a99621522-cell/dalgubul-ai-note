#!/usr/bin/env python3
"""국민연금 대구 사업장 가운데 기업 DB(팩토리온)에 없는 곳을 산단 외 기업 목록으로 — data/nps/YYYYMM.csv → scripts/data/extra/nps_YYYYMM.csv

이어서 python3 scripts/import_extra.py 를 실행하면 extra_companies.csv(id x…)에 들어간다.
범위(공무원용 산업 사이트에 맞게): 산업 그룹이 '기타 서비스'·미분류가 아닌 사업장 + 연구개발·엔지니어링·소프트웨어·정보서비스 사업장.
음식점·소매·임대 등은 넣지 않는다.
같은 기업 판정: 정규화 사업장명 + 구·군이 팩토리온과 같거나, 도로명주소(구군+도로명+건물번호)가 팩토리온 공장 주소와 같으면 제외(이미 있는 기업).
국민연금 파일은 가입자 3인 이상 법인·10인 이상 개인사업장만 담고 있다(포털 설명). 사업자등록번호는 저장하지 않는다.

사용: python3 scripts/nps_to_extra.py [data/nps/YYYYMM.csv]   # 생략하면 최신 파일
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from industry import classify, config as industry_config  # noqa: E402
from sites import load_all_companies  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NPS_DIR = ROOT / "data" / "nps"
OUT_DIR = ROOT / "scripts" / "data" / "extra"
def keep_service(sector: str) -> bool:
    """연구개발·소프트웨어·엔지니어링 등(keep_service)은 산업 그룹이 '기타 서비스'로 나와도 넣는다. 단 도매·소매 등 서비스 낱말이 함께 있으면 제외."""
    c = industry_config()
    t = (sector or "").replace(" ", "")
    return any(k.replace(" ", "") in t for k in c.get("keep_service", [])) and not any(k.replace(" ", "") in t for k in c.get("service_patterns", []))
_ROAD = re.compile(r"(\S+[구군])\s+(.+?(?:로|길)\s*\d+(?:-\d+)?)")


def norm_name(s: str) -> str:
    s = re.sub(r"\(주\)|㈜|\(유\)|주식회사|유한회사|유한책임회사|합자회사|농업회사법인|\(사\)|사단법인|재단법인", "", s or "")
    return re.sub(r"[\s\-_.,·ㆍ&/()\[\]'\"]", "", s).lower()


def road_key(addr: str) -> str:
    m = _ROAD.search(addr or "")
    return (m.group(1) + m.group(2)).replace(" ", "") if m else ""


def col(row: dict, prefix: str) -> str:
    for k, v in row.items():
        if k and k.replace(" ", "").startswith(prefix):
            return (v or "").strip()
    return ""


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else max(NPS_DIR.glob("??????.csv"), default=None)
    if not path or not path.exists():
        print("data/nps/YYYYMM.csv 없음")
        return 1
    month = path.stem
    companies = load_all_companies()
    keys = {(norm_name(c["name"]), c["district"]) for c in companies}
    # 주소 → 그 주소에 등록된 팩토리온 기업 이름들. 한 건물에 여러 기업이 있으므로(지식산업센터·알파시티) 주소만으로 같은 기업이라 보지 않고,
    # 이름이 서로 포함 관계일 때만(예: '명장' ⊂ '(주)명장정밀') 같은 기업으로 본다
    roads: dict[str, set[str]] = {}
    for c in companies:
        for a in (c.get("address") or "").split(" / "):
            k = road_key(a)
            if k:
                roads.setdefault(k, set()).add(norm_name(c["name"]))
    out, why = [], Counter()
    for r in csv.DictReader(open(path, encoding="utf-8")):
        name = col(r, "사업장명")
        road = col(r, "사업장도로명상세주소")
        jibun = col(r, "사업장지번상세주소")
        addr = road or jibun
        m = re.search(r"대구(?:광역시)?\s*(\S+?[구군])", addr)
        dist = m.group(1) if m else ""
        if not name or not dist:
            why["주소·구군 없음"] += 1
            continue
        if col(r, "사업장가입상태코드").startswith("2"):
            why["탈퇴 사업장"] += 1
            continue
        if (norm_name(name), dist) in keys:
            why["팩토리온에 있음(이름)"] += 1
            continue
        n = norm_name(name)
        if len(n) >= 2 and any(n in x or x in n for x in roads.get(road_key(road), ())):
            why["팩토리온에 있음(주소+이름 포함)"] += 1
            continue
        sector = col(r, "사업장업종코드명")
        group = classify("", sector, "")
        if group in ("기타 서비스", "미분류") and not keep_service(sector):
            why["범위 밖 업종"] += 1
            continue
        out.append({"회사명": name, "주소": addr, "업종": sector, "종사자수": col(r, "가입자수"), "설립연도": col(r, "적용일자")[:4],
                    "출처": f"국민연금 가입 사업장 내역 {month[:4]}-{month[4:]}", "기준월": f"{month[:4]}-{month[4:]}", "태그": ""})
        why[f"추가 · {group}"] += 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"nps_{month}.csv"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["회사명", "주소", "업종", "종사자수", "설립연도", "출처", "기준월", "태그"])
        w.writeheader()
        w.writerows(out)
    print(f"국민연금 {month} → 산단 외 기업 후보 {len(out):,}곳 → {out_path.relative_to(ROOT)}")
    for k, v in why.most_common():
        print(f"  {k}: {v:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
