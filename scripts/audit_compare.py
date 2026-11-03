#!/usr/bin/env python3
"""대구 비상장 외감·상장 제조업 재무 묶음 통계와 전국 비교 → data/dart/audit_compare.json
(운영자 지시 2026-11-03 '전국과 비교하는 것도 구현해야지' → '진행해'. 화면은 src/lib/dartAudit.ts 가 이 파일만 읽는다.)

입력: scripts/data/company_financials_audit.csv(대구 비상장 외감), data/dart/national_listed.csv(전국 상장, region 으로 대구 가름),
      data/dart/national_audit_sample.csv(전국 비상장 외감 표본), data/kosis/corp-mgmt-quantile.csv(한국은행 기업경영분석 분위수, 있으면),
      data/ecos/corp-mgmt-region-*.csv(지역별 기업경영분석, 있으면).
지표(회사마다): 매출액증가율·매출액영업이익률·영업현금흐름 대 매출·부채비율·이자보상비율(영업이익 ÷ 이자비용 × 100, 한국은행과 같은 %).
통계: 중앙값·1·3사분위(기업 분포)와 합계 비율(Σ분자 ÷ Σ분모). 전국 비상장 표본 중앙값은 부트스트랩 95% 범위.
기업 수 5곳 미만 칸은 값을 비운다. 회사 이름·순위는 내지 않는다. 판정 낱말 없음.
"""
from __future__ import annotations

import csv
import json
import random
import statistics
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DG = ROOT / "scripts" / "data" / "company_financials_audit.csv"
NL = ROOT / "data" / "dart" / "national_listed.csv"
NS = ROOT / "data" / "dart" / "national_audit_sample.csv"
NS_META = ROOT / "data" / "dart" / "national_audit_sample.json"
SUMMARY = ROOT / "data" / "dart" / "audit_summary.json"
BOK_Q = ROOT / "data" / "kosis" / "corp-mgmt-quantile.csv"
ECOS = ROOT / "data" / "ecos"
OUT = ROOT / "data" / "dart" / "audit_compare.json"
MIN_N = 5

IND = [  # (key, 이름, 단위)
    ("growth", "매출액 증가율", "%"),
    ("opm", "매출액 영업이익률", "%"),
    ("ocf", "영업현금흐름 대 매출액", "%"),
    ("debt", "부채비율", "%"),
    ("icr", "이자보상비율", "%"),
]
BOK_NAMES = {  # 한국은행 기업경영분석 항목 이름(앞 글자 일치) → 지표
    "growth": ["매출액증가율"],
    "opm": ["매출액영업이익률"],
    "debt": ["부채비율"],
    "icr": ["이자보상비율"],
    "ocf": ["매출액영업활동현금흐름비율", "영업활동현금흐름대매출액"],
}


def num(v) -> float | None:
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def ratios(r: dict) -> dict:
    s, sp, op, ocf = num(r.get("sales")), num(r.get("sales_prev")), num(r.get("op")), num(r.get("ocf"))
    liab, eq, ie = num(r.get("liab")), num(r.get("equity")), num(r.get("interest"))
    out = {}
    if s is not None and sp and sp > 0:
        out["growth"] = (s - sp) / sp * 100
    if s and s > 0 and op is not None:
        out["opm"] = op / s * 100
    if s and s > 0 and ocf is not None:
        out["ocf"] = ocf / s * 100
    if liab is not None and eq and eq > 0:
        out["debt"] = liab / eq * 100
    if ie and ie > 0 and op is not None:
        out["icr"] = op / ie * 100
    return out


def pooled(rows: list[dict], key: str) -> float | None:
    """합계 비율 — 한국은행 기업경영분석과 같은 꼴(Σ분자 ÷ Σ분모). 두 값이 모두 있는 회사만."""
    pairs = {
        "growth": ("sales", "sales_prev", lambda a, b: (a - b) / b * 100),
        "opm": ("op", "sales", lambda a, b: a / b * 100),
        "ocf": ("ocf", "sales", lambda a, b: a / b * 100),
        "debt": ("liab", "equity", lambda a, b: a / b * 100),
        "icr": ("op", "interest", lambda a, b: a / b * 100),
    }
    a_k, b_k, f = pairs[key]
    xs = [(num(r.get(a_k)), num(r.get(b_k))) for r in rows]
    xs = [(a, b) for a, b in xs if a is not None and b is not None]
    if key == "icr":
        xs = [(a, b) for a, b in xs if b > 0]
    if key == "debt":
        xs = [(a, b) for a, b in xs if b > 0]
    if len(xs) < MIN_N:
        return None
    A, B = sum(a for a, _ in xs), sum(b for _, b in xs)
    return round(f(A, B), 1) if B else None


def q(vals: list[float], p: float) -> float:
    vals = sorted(vals)
    k = (len(vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def stats(rows: list[dict], boot: bool = False) -> dict:
    out = {"n": len(rows)}
    rs = [ratios(r) for r in rows]
    for key, _, _ in IND:
        vals = [x[key] for x in rs if key in x]
        cell = {"n": len(vals)}
        if len(vals) >= MIN_N:
            cell.update({"med": round(statistics.median(vals), 1), "q1": round(q(vals, .25), 1), "q3": round(q(vals, .75), 1)})
            if boot:
                rnd = random.Random(20261103)
                meds = sorted(statistics.median(rnd.choices(vals, k=len(vals))) for _ in range(1000))
                cell["ci"] = [round(meds[25], 1), round(meds[974], 1)]
        cell["pooled"] = pooled(rows, key)
        out[key] = cell
    return out


def read(p: Path) -> list[dict]:
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


def main_year(rows: list[dict]) -> tuple[str, list[dict]]:
    """가장 많은 회사가 있는 최근 사업연도 하나만(해가 섞이지 않게)."""
    cnt: dict[str, int] = {}
    for r in rows:
        cnt[r.get("fy", "")] = cnt.get(r.get("fy", ""), 0) + 1
    if not cnt:
        return "", []
    top = max(cnt.values())
    fy = max(y for y, c in cnt.items() if c >= top * 0.5 and y)
    return fy, [r for r in rows if r.get("fy") == fy]


def bok_baseline(fy: str) -> dict:
    """한국은행 기업경영분석 분위수(KOSIS DT_501Y086) — 제조업 전체·기업 규모 전체의 중위수·1·3분위·평균값. 표의 이름을 그대로 옮긴다."""
    rows = read(BOK_Q)
    if not rows:
        return {}
    yrs = sorted({r["PRD_DE"] for r in rows})
    year = fy if fy in yrs else yrs[-1]
    out = {"year": year, "table": "한국은행 기업경영분석 분위수(KOSIS DT_501Y086)", "by": {}}

    def is_mfg_total(nm: str) -> bool:
        nm = (nm or "").strip()
        return nm.startswith("C ") or nm in ("C", "제조업", "C 제조업")

    def is_all_scale(nm: str) -> bool:
        return (nm or "").strip() in ("종합", "전체", "합계")

    for key, names in BOK_NAMES.items():
        cell = {}
        for r in rows:
            if r["PRD_DE"] != year or not is_mfg_total(r.get("C1_NM", "")) or not is_all_scale(r.get("C2_NM", "")):
                continue
            if not any((r.get("C3_NM") or "").replace(" ", "").startswith(n) for n in names):
                continue
            sel = (r.get("C4_NM") or "").replace(" ", "")
            v = num(r.get("DT"))
            if v is None:
                continue
            if "중위" in sel or "2분위" in sel:
                cell["med"] = v
            elif "1분위" in sel:
                cell["q1"] = v
            elif "3분위" in sel:
                cell["q3"] = v
            elif "평균" in sel:
                cell["mean"] = v
            cell["name"] = r.get("C3_NM")
        if cell:
            out["by"][key] = cell
    return out


def bok_by_ksic(year: str) -> dict:
    """중분류(C10~C34)별 한국은행 중위수 — {"C25": {"name": …, "growth": {"med":…,"q1":…,"q3":…}, …}} (기업 규모 '종합')."""
    rows = read(BOK_Q)
    out: dict = {}
    for r in rows:
        if r["PRD_DE"] != year or (r.get("C2_NM") or "").strip() != "종합":
            continue
        code = (r.get("C1_NM") or "").split(" ")[0]
        if not (len(code) == 3 and code.startswith("C")):
            continue
        key = next((k for k, ns in BOK_NAMES.items() if any((r.get("C3_NM") or "").replace(" ", "").startswith(n) for n in ns)), None)
        v = num(r.get("DT"))
        if not key or v is None:
            continue
        sel = (r.get("C4_NM") or "").replace(" ", "")
        slot = "med" if "중위" in sel else "q1" if "1분위" in sel else "q3" if "3분위" in sel else "mean" if "평균" in sel else ""
        if slot:
            d = out.setdefault(code, {"name": r.get("C1_NM")})
            d.setdefault(key, {})[slot] = v
    return out


def ecos_region() -> dict:
    """ECOS 지역별 기업경영분석(503Y005~7) 대구 행 — 받아 둔 경우 항목 이름·시점·값만 옮긴다."""
    out = {}
    for k in ("growth", "profit", "stability"):
        p = ECOS / f"corp-mgmt-region-{k}.csv"
        if p.exists():
            out[k] = read(p)[:400]
    return out


def main() -> int:
    dg_all = read(DG)
    nl_all = read(NL)
    ns_all = read(NS)
    if not (dg_all or nl_all or ns_all):
        print("[compare] 입력 없음 — 건너뜀")
        return 0
    fy_dg, dg = main_year(dg_all)
    fy_nl, nl = main_year(nl_all)
    fy_ns, ns = main_year(ns_all)
    dl = [r for r in nl if (r.get("region") or "").startswith("대구")]
    groups = sorted({r.get("group", "") for r in dg + nl + ns if r.get("group")})
    res = {
        "updated": date.today().isoformat(), "min_n": MIN_N,
        "indicators": [{"key": k, "name": n, "unit": u} for k, n, u in IND],
        "years": {"daegu_unlisted": fy_dg, "listed": fy_nl, "national_unlisted": fy_ns},
        "total": {
            "daegu_listed": stats(dl), "national_listed": stats(nl),
            "daegu_unlisted": stats(dg), "national_unlisted": stats(ns, boot=True),
        },
        "by_group": [], "by_ksic": [], "by_district": [],
        "bok": bok_baseline(fy_dg or fy_nl), "ecos_region": ecos_region(),
        "sample": json.loads(NS_META.read_text(encoding="utf-8")) if NS_META.exists() else {},
        "summary": json.loads(SUMMARY.read_text(encoding="utf-8")) if SUMMARY.exists() else {},
    }
    for g in groups:
        res["by_group"].append({"group": g,
                                "daegu_listed": stats([r for r in dl if r.get("group") == g]),
                                "national_listed": stats([r for r in nl if r.get("group") == g]),
                                "daegu_unlisted": stats([r for r in dg if r.get("group") == g]),
                                "national_unlisted": stats([r for r in ns if r.get("group") == g], boot=True)})
    bok_year = res["bok"].get("year", "")
    bk = bok_by_ksic(bok_year) if bok_year else {}
    res["bok_year_ksic"] = bok_year
    for code in sorted({"C" + (r.get("ksic") or "")[:2] for r in dg + nl + ns if (r.get("ksic") or "")[:2].isdigit()}):
        sel = lambda rows: [r for r in rows if "C" + (r.get("ksic") or "")[:2] == code]
        res["by_ksic"].append({"code": code, "name": (bk.get(code) or {}).get("name", code),
                               "daegu_listed": stats(sel(dl)), "national_listed": stats(sel(nl)),
                               "daegu_unlisted": stats(sel(dg)), "national_unlisted": stats(sel(ns), boot=True),
                               "bok": {k: v for k, v in (bk.get(code) or {}).items() if k != "name"}})
    for d in sorted({r.get("district", "") for r in dg if r.get("district")}):
        res["by_district"].append({"district": d, "daegu_unlisted": stats([r for r in dg if r.get("district") == d])})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    t = res["total"]
    print(f"[compare] 대구 상장 {t['daegu_listed']['n']} · 전국 상장 {t['national_listed']['n']} · 대구 비상장 {t['daegu_unlisted']['n']} · 전국 비상장 표본 {t['national_unlisted']['n']} → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
