#!/usr/bin/env python3
"""참여 기업 명단(공공데이터포털 파일데이터) 원본 → data/participation/raw/<번호>.csv (UTF-8, 개인정보 열 제외).

지역(구역)이 아니라 실제 참여 명단으로 기업을 나누기 위한 원자료(운영자 지시 2026-10-01:
'모터 소부장 참여기업·규제샌드박스 참여기업 등으로 분류, 구역별로 하지 말 것'). 분류·기업 사전 매칭은 scripts/participation.py.
대표자·성명·전화·이메일·사업자번호 열은 저장하지 않는다.
사용: python3 scripts/participation_raw.py [data/raw]   (fetch_public.yml save 때 실행)
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_public_support import read_any, as_of_from  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "participation" / "raw"
IDS = {
    "15124790": "중소벤처기업진흥공단 규제자유특구 참여기업 현황",
    "15134916": "중소벤처기업진흥공단 글로벌 혁신 규제자유특구 참여기업 현황",
    "15145229": "한국산업기술진흥원 특례부여현황(산업융합 규제샌드박스)",
    "15121625": "한국산업기술기획평가원 소재부품장비 특화단지 지정현황",
    "15036286": "대구광역시 첨단의료복합단지 입주기업 현황",
    "15094642": "중소벤처기업진흥공단 규제자유특구 지역별 산업별 지정 현황",
}
PRIVATE = re.compile(r"대표|성명|전화|연락처|이메일|e-?mail|사업자\s*(등록)?\s*번호|법인\s*번호|휴대", re.I)


def main(argv: list[str]) -> int:
    raw = Path(argv[0]) if argv else ROOT / "data" / "raw"
    OUT.mkdir(parents=True, exist_ok=True)
    for pk, title in IDS.items():
        d = raw / pk
        if not d.is_dir():
            continue
        files = [f for f in sorted(d.iterdir()) if f.suffix.lower() in (".csv", ".xlsx", ".xls")]
        if not files:
            print(f"[part] {pk} 표 파일 없음")
            continue
        f = files[-1]
        try:
            rows, cols = read_any(f)
        except Exception as e:  # noqa: BLE001
            print(f"[part] {pk} 읽기 실패: {e}")
            continue
        keep = [c for c in cols if c and not PRIVATE.search(str(c))]
        out = OUT / f"{pk}.csv"
        with open(out, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["_dataset", "_title", "_as_of"] + keep)
            for r in rows:
                w.writerow([pk, title, as_of_from(f.stem)] + [str(r.get(c, "")).strip() for c in keep])
        print(f"[part] {pk} {title}: {len(rows)}행, 열 {keep} (뺀 열 {[c for c in cols if c not in keep]}) → {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
