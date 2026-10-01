#!/usr/bin/env python3
"""전국 등록공장 현황(공공데이터포털 15105482, 한국산업단지공단·팩토리온) → 경상북도 공장만 data/supply/gb_factories.csv.

대구·경북 품목 지도(scripts/supply_map.py, /supply-map/)에만 쓴다. 경북 기업은 기업 사전·기업 페이지에 넣지 않는다
(운영자 지시 2026-10-01: 1안 — 사이트 범위는 대구 그대로, 경북은 공급망 지도용).
원자료 열: 순번, 회사명, 단지명, 생산품, 공장주소(업종 코드·종업원 수 없음, 연 1회 갱신). 사업자번호 등은 원자료에 없다.
개인 성명으로 보이는 공장명은 이름을 비운다(src/lib/csv.ts looksLikePersonName 과 같은 규칙) — 집계에는 남긴다.
산업 그룹은 업종 코드가 없어 생산품 낱말로만 짐작한다(config/industry_groups.yml 키워드). 참고용.
사용: python3 scripts/import_gb_factories.py data/raw/15105482   (폴더·zip·csv 모두 받음, fetch_public.yml 이 실행)
"""
import csv
import io
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import industry  # noqa: E402

OUT = ROOT / "data" / "supply" / "gb_factories.csv"
SIDO = ("경상북도", "경북 ")

BIZ_SUFFIXES = ['산업', '공업', '기업', '테크', '정밀', '섬유', '식품', '상사', '상회', '공장', '제작소', '기계', '화학', '전자', '금속', '물산', '건설', '시스템', '코리아', '개발', '스틸', '패션', '인쇄', '유통', '에너지', '가공', '제조', '공사', '공방', '기공', '직물', '부동산', '유니온']
SURNAMES = set('강고공곽구국권금기길김나남노도라류마맹명모문민박반방배백변봉부사서석선설성소손송신심안양어엄여연염예오옥왕용우원위유육윤은이인임장전정제조주지진차채천최추탁편표하한함허현홍황')
SURNAMES2 = ['남궁', '황보', '제갈', '선우', '독고', '사공', '서문', '동방']
LOAN = set('넷니닷드들디람랩룩링맥몰밀벡벤북샘샵센스앤엔엘온잉젠촌카캠컴코크텍토트팜팩폴프플홈')


def looks_like_person(raw: str) -> bool:
    n = (raw or "").strip()
    if any(s in n for s in BIZ_SUFFIXES) or n.endswith("사"):
        return False
    if re.fullmatch(r"[가-힣]{3}", n):
        return n[0] in SURNAMES and not any(c in LOAN for c in n[1:])
    if re.fullmatch(r"[가-힣]{4}", n):
        return any(n.startswith(s) for s in SURNAMES2) and not any(c in LOAN for c in n[2:])
    return False


def read_rows(src: Path) -> tuple[list[dict], str]:
    """폴더·zip·csv 에서 '등록공장현황' CSV 를 찾아 행과 기준일(파일명 YYYYMMDD → YYYY-MM)을 돌려준다."""
    blobs: list[tuple[str, bytes]] = []
    files = [src] if src.is_file() else sorted(src.rglob("*"))
    for f in files:
        if f.suffix.lower() == ".zip":
            with zipfile.ZipFile(f) as z:
                blobs += [(n, z.read(n)) for n in z.namelist() if n.lower().endswith(".csv") and "사전" not in n]
        elif f.suffix.lower() == ".csv" and "사전" not in f.name:
            blobs.append((f.name, f.read_bytes()))
    rows, as_of = [], ""
    for name, b in blobs:
        for enc in ("utf-8-sig", "cp949", "euc-kr"):
            try:
                text = b.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            continue
        rd = list(csv.DictReader(io.StringIO(text)))
        if rd and "공장주소" in rd[0] and "생산품" in rd[0]:
            rows += rd
            m = re.search(r"(20\d{2})(\d{2})\d{2}", name)
            as_of = as_of or (f"{m.group(1)}-{m.group(2)}" if m else "")
            print(f"[gb] {name}: {len(rd):,}행")
    return rows, as_of


def sigungu(addr: str) -> str:
    m = re.match(r"\s*(?:경상북도|경북)\s+(\S+?[시군])(?:\s|$)", addr or "")
    return m.group(1) if m else ""


def main(argv: list[str]) -> int:
    src = Path(argv[1]) if len(argv) > 1 else ROOT / "data" / "raw" / "15105482"
    if not src.exists():
        print(f"[gb] 입력 없음: {src} — 건너뜀")
        return 0
    rows, as_of = read_rows(src)
    if not rows:
        print("[gb] 등록공장현황 CSV 를 찾지 못함 — 건너뜀")
        return 0
    out = []
    for r in rows:
        addr = (r.get("공장주소") or "").strip()
        if not addr.startswith(SIDO):
            continue
        name = (r.get("회사명") or "").strip()
        prod = re.sub(r"\s+", " ", (r.get("생산품") or "").strip())
        out.append({"name": "" if looks_like_person(name) else name, "sigungu": sigungu(addr), "complex": (r.get("단지명") or "").strip(),
                    "product": prod, "group": industry.classify("", "", prod), "as_of": as_of})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "sigungu", "complex", "product", "group", "as_of"])
        w.writeheader()
        w.writerows(out)
    blank = sum(1 for r in out if not r["name"])
    print(f"[gb] 전국 {len(rows):,}행 중 경북 {len(out):,}곳(이름 비움 {blank}곳) → {OUT.relative_to(ROOT)} (기준 {as_of})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
