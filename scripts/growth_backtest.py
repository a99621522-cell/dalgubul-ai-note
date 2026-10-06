#!/usr/bin/env python3
"""성장 계산기 되돌려 보기(운영자 평가 2026-10-06: 계산 방식이 맞는지 과거 자료로 시험해 오차를 공개).

계산기와 같은 식(업종별 연평균 실질 성장률을 그대로 이어 간다)을 2015→2019년 자료로 만들고, 2019년 부가가치에서 2024년을 맞혀
실제 2019→2024년과 견준다. ① 전체: 2015→2019 연평균 성장률을 그대로 이어 갔을 때의 2024년 GRDP 와 실제 ② 업종별: 2015→2019 추세로
맞힌 2024년 부가가치와 실제의 차이(실질, 억 원·%). 자료는 data/kosis/grdp-sido-industry-all.csv(실질 값). 결과 data/growth/backtest.json.
오차는 '그때 그 방식이 얼마나 빗나갔나'이지 앞으로의 정확도가 아니다(2020년 코로나가 사이에 있다).
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from growth_commentary import LEAVES, REGION, TOT  # noqa: E402

OUT = ROOT / "data" / "growth" / "backtest.json"


def main() -> int:
    V: dict[tuple, float] = {}
    for r in csv.DictReader(open(ROOT / "data/kosis/grdp-sido-industry-all.csv", encoding="utf-8")):
        try:
            V[(r["ITM_NM"], r["C1_NM"], r["C2_NM"], int(r["PRD_DE"]))] = float(r["DT"])
        except ValueError:
            pass
    a, m, b = 2015, 2019, 2024
    real = lambda k, y: V.get(("실질", REGION, k, y))
    tot_a, tot_m, tot_b = real(TOT, a), real(TOT, m), real(TOT, b)
    if not (tot_a and tot_m and tot_b):
        print("실질 GRDP 없음")
        return 1
    g_fit = (tot_m / tot_a) ** (1 / (m - a)) - 1          # 2015→2019 연평균
    g_act = (tot_b / tot_m) ** (1 / (b - m)) - 1          # 실제 2019→2024 연평균
    pred_tot = tot_m * (1 + g_fit) ** (b - m)
    rows = []
    pred_sum = 0.0
    for k, nm in LEAVES:
        va_a, va_m, va_b = real(k, a), real(k, m), real(k, b)
        if not (va_a and va_m and va_b and va_a > 0 and va_m > 0):
            continue
        g = (va_m / va_a) ** (1 / (m - a)) - 1
        pred = va_m * (1 + g) ** (b - m)
        pred_sum += pred
        rows.append({"name": nm, "g_fit": round(g * 100, 2), "g_actual": round(((va_b / va_m) ** (1 / (b - m)) - 1) * 100, 2),
                     "pred_2024_eok": round(pred / 100), "actual_2024_eok": round(va_b / 100), "error_pct": round((pred / va_b - 1) * 100, 1)})
    gva_m = sum(real(k, m) or 0 for k, _ in LEAVES)
    gva_b = sum(real(k, b) or 0 for k, _ in LEAVES)
    g_sector = (pred_sum / gva_m) ** (1 / (b - m)) - 1     # 업종별 추세를 더한 전체 연평균
    g_gva_act = (gva_b / gva_m) ** (1 / (b - m)) - 1
    out = {
        "generated": date.today().isoformat(), "fit": [a, m], "test": [m, b], "source": "국가데이터처 지역소득(KOSIS, 실질)",
        "total": {"fit_cagr_pct": round(g_fit * 100, 2), "actual_cagr_pct": round(g_act * 100, 2), "error_pp": round((g_fit - g_act) * 100, 2),
                  "pred_2024_trillion": round(pred_tot / 1e6, 2), "actual_2024_trillion": round(tot_b / 1e6, 2), "error_pct": round((pred_tot / tot_b - 1) * 100, 1)},
        "by_sector_sum": {"fit_cagr_pct": round(g_sector * 100, 2), "actual_cagr_pct": round(g_gva_act * 100, 2), "error_pp": round((g_sector - g_gva_act) * 100, 2)},
        "sectors": sorted(rows, key=lambda r: -abs(r["error_pct"])),
        "note": "2015→2019 연평균 성장률을 그대로 이어 간 2024년 값과 실제의 차이. 사이에 2020년(코로나)이 있어 오차가 크게 나온 업종이 많다. 앞으로의 정확도가 아니라 방식의 한계를 보여 주는 값.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"전체: 2015→19 추세 {out['total']['fit_cagr_pct']}% vs 실제 2019→24 {out['total']['actual_cagr_pct']}% (오차 {out['total']['error_pp']}%p, 2024 규모 {out['total']['error_pct']}%)")
    print(f"업종 합: {out['by_sector_sum']}")
    for r in out["sectors"][:5]:
        print(f"  {r['name']}: 추세 {r['g_fit']}% 실제 {r['g_actual']}% → 2024 오차 {r['error_pct']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
