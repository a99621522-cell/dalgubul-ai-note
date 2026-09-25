#!/usr/bin/env python3
"""산단 외 기업 목록 투입 — scripts/data/extra/*.csv → scripts/data/extra_companies.csv + company_tags.csv

팩토리온(공장등록) 밖의 기업을 기업 DB에 넣는다: 수성알파시티 입주기업, 연구개발특구 연구소기업, 창조경제혁신센터 보육기업,
지식산업센터 입주기업, 창업기업 등. 입력 파일 형식은 scripts/data/extra/README.md.

규칙
- 이미 팩토리온에 있는 기업(정규화 회사명 + 구·군 일치)은 새로 만들지 않고 태그만 붙인다(company_tags.csv)
- 새 기업 id 는 x0001 부터 (팩토리온 id 'c…' 와 절대 겹치지 않는다). 한 번 준 id 는 바꾸지 않는다
- 대표자·연락처는 입력에 있어도 저장하지 않는다. 종사자 수는 있으면 그대로(없으면 빈칸 → 집계 대상에서 빠짐)
- 같은 기업이 여러 목록에 있으면 태그를 합친다

사용: python3 scripts/import_extra.py            # extra/ 전부 반영
      python3 scripts/import_extra.py --dry-run  # 무엇이 새로 들어가고 무엇이 태그만 붙는지
      python3 scripts/import_extra.py --replace-inputs        # 입력 파일에 든 출처의 기존 행(기업·태그)을 버리고 다시 넣는다(멱등)
      python3 scripts/import_extra.py --replace-source 국민연금  # 이 낱말로 시작하는 출처만
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from industry import classify  # noqa: E402
from sites import EXTRA, TAGS, config as site_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scripts" / "data"
INBOX = DATA / "extra"
COMPANIES = DATA / "dalseong_companies.csv"

COLS = ["id", "name", "complex", "district", "eupmyeon", "sector_code", "sector", "sector_group", "product", "workers_band", "workers",
        "reg_type", "first_registered", "mfg_area_band", "address", "sites", "source", "as_of", "founded", "tags"]
IN_COLS = {  # 입력 열 이름 후보 (첫 번째가 표준)
    "name": ["name", "회사명", "기업명", "업체명", "사업장명"],
    "address": ["address", "주소", "소재지", "사업장주소"],
    "sector_code": ["sector_code", "업종코드", "표준산업분류코드"],
    "sector": ["sector", "업종", "업종명"],
    "product": ["product", "생산품", "주요제품", "주요 제품", "사업내용"],
    "workers": ["workers", "종사자수", "종업원수", "고용인원", "상시근로자수"],
    "founded": ["founded", "설립일", "설립연도", "설립년도", "창업일"],
    "source": ["source", "출처"],
    "as_of": ["as_of", "기준일", "기준월"],
    "tags": ["tags", "태그"],
    "site_hint": ["site_type", "입지", "입지유형"],
}
_DIST = re.compile(r"대구(?:광역시)?\s*(\S+?[구군])")


def pick(row: dict, key: str) -> str:
    for c in IN_COLS[key]:
        if c in row and row[c] not in (None, ""):
            return str(row[c]).strip()
    return ""


def norm_name(s: str) -> str:
    s = re.sub(r"\(주\)|㈜|\(유\)|주식회사|유한회사|유한책임회사|합자회사|농업회사법인|\(사\)|사단법인|재단법인", "", s or "")
    return re.sub(r"[\s\-_.,·ㆍ&/()\[\]'\"]", "", s).lower()


def district_of(addr: str) -> str:
    m = _DIST.search(addr or "")
    return m.group(1) if m else ""


def workers_band(n: int) -> str:
    return "" if n <= 0 else "1~9명" if n < 10 else "10~49명" if n < 50 else "50~299명" if n < 300 else "300명 이상"


def read_inputs() -> list[dict]:
    rows = []
    for p in sorted(INBOX.glob("*.csv")):
        raw = p.read_bytes()
        for enc in ("utf-8-sig", "cp949"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("cp949", errors="replace")
        for r in csv.DictReader(text.splitlines()):
            name = pick(r, "name")
            if not name:
                continue
            rows.append({"name": name, "address": pick(r, "address"), "sector_code": pick(r, "sector_code"), "sector": pick(r, "sector"),
                         "product": pick(r, "product"), "workers": re.sub(r"\D", "", pick(r, "workers")), "founded": pick(r, "founded"),
                         "source": pick(r, "source") or p.stem, "as_of": pick(r, "as_of"), "tags": pick(r, "tags"), "_file": p.name})
    return rows


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    replace = argv[argv.index("--replace-source") + 1] if "--replace-source" in argv else None  # 이 출처로 시작하는 기존 행은 버리고 다시 넣는다
    inputs = read_inputs()
    if not inputs:
        print(f"입력 없음: {INBOX.relative_to(ROOT)}/*.csv (형식은 그 안의 README.md)")
        return 1
    # --replace-inputs: 입력 파일에 든 출처(source)와 같은 기존 행을 모두 버리고 다시 넣는다 (여러 출처를 한 번에, 멱등)
    sources = {r["source"] for r in inputs} if "--replace-inputs" in argv else set()

    def replaced(src: str) -> bool:
        return bool(replace and src.startswith(replace)) or src in sources

    fo = list(csv.DictReader(open(COMPANIES, encoding="utf-8")))
    by_key = {(norm_name(r["name"]), r["district"]): r["id"] for r in fo}
    extra = list(csv.DictReader(open(EXTRA, encoding="utf-8"))) if EXTRA.exists() else []
    if replace or sources:
        kept_ids = {r["id"]: r for r in extra if not replaced(r["source"])}
        # 같은 출처로 다시 들어올 기업은 예전 id 를 그대로 쓴다(URL 유지)
        old_ids = {(norm_name(r["name"]), r["district"]): r["id"] for r in extra if replaced(r["source"])}
        extra = list(kept_ids.values())
    else:
        old_ids = {}
    for r in extra:
        by_key.setdefault((norm_name(r["name"]), r["district"]), r["id"])
    next_id = 1 + max([int(r["id"][1:]) for r in extra if r["id"].startswith("x")] + [int(i[1:]) for i in old_ids.values()], default=0)
    tag_rows = list(csv.DictReader(open(TAGS, encoding="utf-8"))) if TAGS.exists() else []
    if replace or sources:  # 갈아끼우는 출처의 태그와, 사라진 기업의 태그는 버린다
        live = {r["id"] for r in fo} | {r["id"] for r in extra} | set(old_ids.values())
        tag_rows = [t for t in tag_rows if not replaced(t.get("source", "")) and t["id"] in live]
    have_tags = {(t["id"], t["tag"]) for t in tag_rows}
    outside = site_config()["outside_complex"]

    added, tagged, skipped = 0, 0, 0
    for r in inputs:
        dist = district_of(r["address"])
        key = (norm_name(r["name"]), dist)
        tags = [t.strip() for t in r["tags"].split(";") if t.strip()]
        cid = by_key.get(key)
        if cid is None and not dist:
            skipped += 1
            print(f"  건너뜀(대구 구·군을 주소에서 못 찾음): {r['name']} | {r['address'][:40]} [{r['_file']}]")
            continue
        if cid is None:
            cid = old_ids.get(key)
            if cid is None:
                cid = f"x{next_id:04d}"
                next_id += 1
            w = int(r["workers"]) if r["workers"] else 0
            group = classify(r["sector_code"], r["sector"], r["product"])
            extra.append({"id": cid, "name": r["name"], "complex": outside, "district": dist, "eupmyeon": "", "sector_code": r["sector_code"],
                          "sector": r["sector"], "sector_group": group, "product": r["product"], "workers_band": workers_band(w),
                          "workers": str(w) if w else "", "reg_type": "", "first_registered": "", "mfg_area_band": "", "address": r["address"],
                          "sites": "1", "source": r["source"], "as_of": r["as_of"], "founded": r["founded"], "tags": ";".join(tags)})
            by_key[key] = cid
            added += 1
        else:
            for t in tags:
                if (cid, t) not in have_tags:
                    tag_rows.append({"id": cid, "tag": t, "source": r["source"], "as_of": r["as_of"]})
                    have_tags.add((cid, t))
            if r["founded"]:
                for e in extra:
                    if e["id"] == cid and not e.get("founded"):
                        e["founded"] = r["founded"]
            tagged += 1

    print(f"입력 {len(inputs)}행 → 새 기업 {added}, 기존 기업에 태그 {tagged}, 건너뜀 {skipped}" + (" (dry-run, 저장 안 함)" if dry else ""))
    if dry:
        return 0
    with open(EXTRA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows({k: e.get(k, "") for k in COLS} for e in sorted(extra, key=lambda e: e["id"]))
    ids_now = {r["id"] for r in fo} | {r["id"] for r in extra}
    tag_rows = [t for t in tag_rows if t["id"] in ids_now]
    with open(TAGS, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "tag", "source", "as_of"])
        w.writeheader()
        w.writerows(sorted(tag_rows, key=lambda t: (t["id"], t["tag"])))
    print(f"저장: {EXTRA.relative_to(ROOT)} ({len(extra)}곳), {TAGS.relative_to(ROOT)} ({len(tag_rows)}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
