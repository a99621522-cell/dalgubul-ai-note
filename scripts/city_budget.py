#!/usr/bin/env python3
"""대구시 세출(공공데이터포털 15133534 「대구광역시_주민참여예산 (신)이호조 대구시청 세출 데이터」) → 지출 경로별 규모
(운영자 지시 2026-10-05: 대구시 예산이 GRDP 성장에 얼마나 기여하는지 계산하기 위한 1단계 — 예산을 GRDP 지출 측 항목에 잇기).

입력: data/raw/15133534/*.csv(신 이호조) + data/raw/15133532/*.csv(구 이호조, 이전 연도) — fetch_public.yml save 로 받음. 열: 회계연도, 회계구분명, 세입구문명, 부서명, 정책사업명, 세부사업명,
      사업구분명, 예산현액, 국비, 시도비, 지출액, 분야명. 예산현액·국비·시도비는 천 원, 지출액은 원(같은 행에서 비율로 확인해 판정).
처리: 같은 사업이 '자체/보조' 로 두 번 실린 행(금액 모두 같음)은 하나로. 세부사업마다 '지출 경로'를 사업명 낱말로 짐작한다(근사):
  가계 이전(→ 민간소비) · 건설(→ 건설투자) · 기업·산업 지원(→ 설비·지식재산 투자 유도) · 정부 간 전출(구·군·교육청 등, 대구 GRDP 직접 항목 아님) ·
  운영·서비스(→ 정부소비, 나머지 전부)
출력: data/budget/daegu_expenditure.csv(세부사업별), data/budget/daegu_expenditure_summary.json(경로·분야별 합계).
사이트에는 싣지 않는다(운영자 지시 2026-09-30: 대구시 예산 삭제) — 계산·초안 문서용. 평가 없음, 값은 원자료 그대로(단위 맞춤만).
사용: python3 scripts/city_budget.py [폴더 …]
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "budget"
PATHS = [  # (경로, GRDP 지출 측 항목, 낱말)
    ("정부 간 전출", "대구 GRDP 직접 항목 아님(받는 기관이 다시 씀)", r"전출|교부금|조정교부|재정보전|교육비특별회계|교육청|구\s*·?\s*군\s*(보조|지원)|예비비|채무상환|원금상환|이자|상환"),
    ("가계 이전", "민간소비(가계가 받아 씀)", r"수당|급여|연금|생계|바우처|장려금|양육|출산|기초연금|의료급여|주거급여|보험료\s*지원|이용권|돌봄수당|생활지원|청년\s*(월세|수당)"),
    ("건설", "건설투자", r"건설|조성|정비|도로|확장|개설|신축|건립|설치|공사|하천|교량|리모델링|재생|개량|포장|터널|철도|도시철도|부지|매입|보상|단지\s*조성"),
    ("기업·산업 지원", "설비·지식재산 투자 유도(기업이 받아 투자)", r"기업|산업|R&D|연구개발|기술개발|창업|투자유치|특구|클러스터|스마트공장|육성|진흥|실증|사업화|벤처|소부장|로봇|모빌리티|반도체|의료기기|첨단"),
]
DEFAULT = ("운영·서비스", "정부소비(시가 직접 쓰는 행정·서비스)")


def read_csv(p: Path) -> list[dict]:
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return list(csv.DictReader(io.StringIO(raw.decode(enc))))
        except UnicodeDecodeError:
            continue
    return []


def num(s) -> float:
    try:
        return float(str(s).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def path_of(r: dict) -> tuple[str, str]:
    text = f"{r.get('정책사업명', '')} {r.get('세부사업명', '')}"
    for name, item, pat in PATHS:
        if re.search(pat, text):
            return name, item
    return DEFAULT


def main(argv: list[str]) -> int:
    srcs = [Path(a) for a in argv] or [ROOT / "data" / "raw" / "15133534", ROOT / "data" / "raw" / "15133532"]
    files = [f for s in srcs if s.exists() for f in (sorted(s.glob("*.csv")) if s.is_dir() else [s])]
    src = ", ".join(map(str, srcs))
    rows = [r for f in files for r in read_csv(f)]
    if not rows:
        print(f"[city_budget] 입력 없음: {src}")
        return 0
    seen, uniq = set(), []
    for r in rows:
        k = tuple(r.get(c, "").strip() for c in ("회계연도", "회계구분명", "부서명", "정책사업명", "세부사업명", "예산현액", "국비", "시도비", "지출액"))
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    # 지출액 단위 판정: 예산현액(천 원)×1000 과 견줘 대부분 1 이하이면 원
    ratios = sorted(num(r["지출액"]) / (num(r["예산현액"]) * 1000) for r in uniq if num(r.get("예산현액")) > 0 and num(r.get("지출액")) > 0)
    med = ratios[len(ratios) // 2] if ratios else 1
    spend_div = 1000 if med < 5 else 1       # 원 → 천 원
    print(f"[city_budget] 행 {len(rows)} → 중복 뺀 {len(uniq)} · 지출액/예산현액 중앙값 {med:.3f}(지출액 단위 {'원' if spend_div == 1000 else '천 원'})")
    out = []
    for r in uniq:
        name, item = path_of(r)
        out.append({"year": r.get("회계연도", ""), "account": r.get("회계구분명", ""), "field": r.get("분야명", ""), "dept": r.get("부서명", ""),
                    "policy": r.get("정책사업명", ""), "program": r.get("세부사업명", ""), "kind": r.get("사업구분명", ""),
                    "budget_thousand": round(num(r.get("예산현액"))), "national_thousand": round(num(r.get("국비"))), "city_thousand": round(num(r.get("시도비"))),
                    "spent_thousand": round(num(r.get("지출액")) / spend_div), "path": name, "grdp_item": item})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "daegu_expenditure.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    agg = defaultdict(lambda: {"n": 0, "budget_thousand": 0, "national_thousand": 0, "city_thousand": 0, "spent_thousand": 0})
    for o in out:
        for key in (("path", o["path"]), ("field", o["field"]), ("year", o["year"])):
            a = agg[key]
            a["n"] += 1
            for c in ("budget_thousand", "national_thousand", "city_thousand", "spent_thousand"):
                a[c] += o[c]
    summ = {"source": "공공데이터포털 15133534 대구광역시_주민참여예산 (신)이호조 대구시청 세출 데이터", "url": "https://www.data.go.kr/data/15133534/fileData.do",
            "rows": len(out), "years": sorted({o["year"] for o in out}),
            "by_path": {k[1]: v | {"grdp_item": next(o["grdp_item"] for o in out if o["path"] == k[1])} for k, v in agg.items() if k[0] == "path"},
            "by_field": {k[1]: v for k, v in agg.items() if k[0] == "field"}, "by_year": {k[1]: v for k, v in agg.items() if k[0] == "year"},
            "note": "지출 경로는 사업명 낱말로 짐작한 근사 분류다. 예산현액·국비·시도비·지출액 단위는 천 원."}
    (OUT / "daegu_expenditure_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in sorted(summ["by_path"].items(), key=lambda x: -x[1]["budget_thousand"]):
        print(f"  {k:10s} {v['n']:5d}개 예산현액 {v['budget_thousand']/1e5:,.0f}억 원 (국비 {v['national_thousand']/1e5:,.0f} · 시비 {v['city_thousand']/1e5:,.0f}) 지출 {v['spent_thousand']/1e5:,.0f}억 → {v['grdp_item']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
