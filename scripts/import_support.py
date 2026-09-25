#!/usr/bin/env python3
"""지원사업 수혜 이력 투입 — scripts/data/support/*.csv → scripts/data/support_history.csv

대구시·중앙부처·기관의 지원사업에서 최근 몇 년간 지원받은 기업의 사업명·기관·연도·금액을 기업 사전에 잇는다.
입력 파일 형식과 넣을 수 있는 공개 자료는 scripts/data/support/README.md.

규칙
- 공개 자료만(선정 공고·보도자료 명단, NTIS 과제, 지방보조금 공개 목록, DART 공시). 원문 URL 과 기준일을 반드시 남긴다
- 금액은 원문 값 그대로(단위를 amount_unit 에: 원/천원/백만원). 환산·추정하지 않는다. 없으면 빈칸
- 기업 매칭: 정규화 회사명 + 구·군(주소가 있을 때), 없으면 이름이 유일할 때만. 못 맞춘 행도 이름으로 남긴다(id 빈칸)
- 평가·순위 없음. 같은 기업·연도·사업명은 한 번만

사용: python3 scripts/import_support.py [--dry-run]
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sites import load_all_companies  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scripts" / "data"
INBOX = DATA / "support"
OUT = DATA / "support_history.csv"

COLS = ["id", "name", "district", "year", "layer", "funder", "program", "type", "amount", "amount_unit", "source", "source_url", "as_of"]
IN_COLS = {
    "name": ["name", "기업명", "회사명", "업체명", "수행기관", "수혜기업", "사업자명", "보조사업자"],
    "address": ["address", "주소", "소재지", "지역"],
    "year": ["year", "연도", "선정연도", "지원연도", "사업연도", "기준연도"],
    "layer": ["layer", "구분", "재원"],                     # 국비 / 시비 / 기관
    "funder": ["funder", "지원기관", "부처", "소관부처", "주관기관", "기관"],
    "program": ["program", "사업명", "지원사업명", "과제명", "보조사업명"],
    "type": ["type", "지원유형", "유형"],                    # R&D / 보조금 / 융자 / 바우처 / 선정
    "amount": ["amount", "금액", "지원금액", "연구비", "정부출연금", "보조금액", "교부액"],
    "amount_unit": ["amount_unit", "단위", "금액단위"],
    "source": ["source", "출처"],
    "source_url": ["source_url", "출처URL", "url", "링크"],
    "as_of": ["as_of", "기준일", "기준월"],
}
_DIST = re.compile(r"대구(?:광역시)?\s*(\S+?[구군])")


def pick(r: dict, k: str) -> str:
    for c in IN_COLS[k]:
        if c in r and r[c] not in (None, ""):
            return str(r[c]).strip()
    return ""


def norm_name(s: str) -> str:
    s = re.sub(r"\(주\)|㈜|\(유\)|주식회사|유한회사|유한책임회사|합자회사|농업회사법인|\(사\)|사단법인|재단법인", "", s or "")
    return re.sub(r"[\s\-_.,·ㆍ&/()\[\]'\"]", "", s).lower()


def read(p: Path) -> list[dict]:
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return list(csv.DictReader(raw.decode(enc).splitlines()))
        except UnicodeDecodeError:
            continue
    return list(csv.DictReader(raw.decode("cp949", errors="replace").splitlines()))


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    files = sorted(INBOX.glob("*.csv"))
    if not files:
        print(f"입력 없음: {INBOX.relative_to(ROOT)}/*.csv (형식은 README.md)")
        return 1
    companies = load_all_companies()
    by_key = {(norm_name(c["name"]), c["district"]): c["id"] for c in companies}
    by_name: dict[str, list[str]] = {}
    for c in companies:
        by_name.setdefault(norm_name(c["name"]), []).append(c["id"])
    existing = list(csv.DictReader(open(OUT, encoding="utf-8"))) if OUT.exists() else []
    seen = {(r["name"], r["year"], r["program"]) for r in existing}

    added, matched, dup = 0, 0, 0
    per_file = Counter()
    for f in files:
        for r in read(f):
            name = pick(r, "name")
            program = pick(r, "program")
            if not name or not program:
                continue
            year = re.sub(r"\D", "", pick(r, "year"))[:4]
            key = (name, year, program)
            if key in seen:
                dup += 1
                continue
            seen.add(key)
            dist = ""
            m = _DIST.search(pick(r, "address"))
            if m:
                dist = m.group(1)
            n = norm_name(name)
            cid = by_key.get((n, dist)) if dist else None
            if cid is None and len(by_name.get(n, [])) == 1:
                cid = by_name[n][0]
            if cid:
                matched += 1
            amount = re.sub(r"[^\d.]", "", pick(r, "amount"))
            existing.append({"id": cid or "", "name": name, "district": dist, "year": year, "layer": pick(r, "layer"), "funder": pick(r, "funder"),
                             "program": program, "type": pick(r, "type"), "amount": amount, "amount_unit": pick(r, "amount_unit") or ("원" if amount else ""),
                             "source": pick(r, "source") or f.stem, "source_url": pick(r, "source_url"), "as_of": pick(r, "as_of")})
            added += 1
            per_file[f.name] += 1
    print(f"입력 {len(files)}파일 → 새 이력 {added}건(기업 사전 매칭 {matched}), 중복 {dup}" + (" (dry-run, 저장 안 함)" if dry else ""))
    for k, v in per_file.items():
        print(f"  {k}: {v}건")
    unmatched = Counter(r["name"] for r in existing if not r["id"])
    if unmatched:
        print(f"  매칭 안 된 기업 {len(unmatched)}곳 (이름으로만 표시됨): " + ", ".join(list(unmatched)[:8]) + (" …" if len(unmatched) > 8 else ""))
    if dry:
        return 0
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(sorted(existing, key=lambda r: (r["year"], r["name"], r["program"]), reverse=True))
    print(f"저장: {OUT.relative_to(ROOT)} ({len(existing)}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
