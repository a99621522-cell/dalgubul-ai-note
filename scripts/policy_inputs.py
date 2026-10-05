#!/usr/bin/env python3
"""정책 대안 프롬프트 조사 항목의 공공데이터포털 파일 → data/policy_inputs/<번호>.csv (운영자 지시 2026-10-05).

fetch_public.yml(save)이 받은 data/raw/<번호>/ 파일에서 '대구'가 든 행과 전국·합계 행(비교용)만 머리와 함께 남긴다.
'대구' 행이 하나도 없고 파일이 작으면(행 3,000 이하) 통째로 둔다(지역 열이 없는 집계표). 값은 그대로, 계산·평가 없음.
개인정보 열(대표자·성명·연락처·전화·이메일)은 버린다.

  15050054 한국교육개발원 외국인 유학생 현황(대학) · 15050055 (전문대학)
  15137813 한국보건산업진흥원 외국인 환자 유치실적 정보 · 15125603 연도별 지역별 외국인환자 유치의료기관 현황

사용: python3 scripts/policy_inputs.py data/raw
"""
from __future__ import annotations

import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "policy_inputs"
IDS = {
    "15050054": "한국교육개발원 외국인 유학생 현황(대학)",
    "15050055": "한국교육개발원 외국인 유학생 현황(전문대학)",
    "15137813": "한국보건산업진흥원 외국인 환자 유치실적 정보",
    "15125603": "한국보건산업진흥원 연도별 지역별 외국인환자 유치의료기관 현황",
}
DROP = ("대표자", "성명", "연락처", "전화", "이메일", "e-mail", "담당자", "팩스")
TOTAL = ("전국", "합계", "총계", "전체")


def read_rows(f: Path) -> list[list[str]]:
    if f.suffix.lower() in (".xlsx", ".xls"):
        try:
            import pandas as pd
            out = []
            for _, df in pd.read_excel(f, sheet_name=None, header=None, dtype=str).items():
                out += [["" if str(v) == "nan" else str(v).strip() for v in row] for row in df.values.tolist()]
            return out
        except Exception as e:  # noqa: BLE001
            print(f"  {f.name}: 엑셀 읽기 실패 {e}")
            return []
    raw = f.read_bytes()
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return [r for r in csv.reader(io.StringIO(raw.decode(enc)))]
        except UnicodeDecodeError:
            continue
    return []


def main(argv: list[str]) -> int:
    base = Path(argv[0]) if argv else ROOT / "data" / "raw"
    OUT.mkdir(parents=True, exist_ok=True)
    index = json.loads((OUT / "index.json").read_text(encoding="utf-8")) if (OUT / "index.json").exists() else {}
    for pk, title in IDS.items():
        d = base / pk
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if f.suffix.lower() not in (".csv", ".xlsx", ".xls"):
                continue
            rows = [r for r in read_rows(f) if any(c.strip() for c in r)]
            if not rows:
                continue
            head = rows[0]
            keep_cols = [i for i, h in enumerate(head) if not any(x in h for x in DROP)]
            dg = [r for r in rows[1:] if any("대구" in c for c in r) or any(c.strip() in TOTAL for c in r[:3])]
            small = len(rows) <= 201   # 시도별 표처럼 작은 표는 전국 비교를 위해 통째로
            body = rows[1:] if small else (dg if any(any("대구" in c for c in r) for r in dg) else (rows[1:] if len(rows) <= 3001 else []))
            out = OUT / f"{pk}.csv"
            with open(out, "w", encoding="utf-8", newline="") as fo:
                w = csv.writer(fo)
                w.writerow([head[i] for i in keep_cols])
                for r in body:
                    w.writerow([r[i] if i < len(r) else "" for i in keep_cols])
            index[pk] = {"title": title, "file": f.name, "rows_all": len(rows) - 1, "rows_kept": len(body),
                         "mode": "전체" if body is not dg else "대구·합계 행", "fetched": date.today().isoformat(),
                         "source_url": f"https://www.data.go.kr/data/{pk}/fileData.do"}
            print(f"[policy_inputs] {pk} {f.name}: {len(rows) - 1}행 → {len(body)}행 ({index[pk]['mode']})")
            print("   머리: " + " | ".join(head[i] for i in keep_cols)[:400])
            for r in body[:8]:
                print("   " + " | ".join(r[i] if i < len(r) else "" for i in keep_cols)[:400])
            break   # 번호마다 첫 표 파일 하나
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
