#!/usr/bin/env python3
"""대구 비상장 외감·상장 제조업 재무 묶음 통계와 전국 비교 → data/dart/audit_compare.json
(운영자 지시 2026-11-03 '대구 비상장 재무 현황표 조사해봐' → '전국과 비교하는 것도 구현해야지' → '진행해'
 → '같은 회사 여러 해 추이·규모별·국민연금 고용·이자보상비율 100% 미만 비중·한국은행 법인 전수와 빠진 층·내려받기'.
 화면은 src/lib/dartAudit.ts 가 이 파일만 읽는다.)

입력(회사 × 사업연도 한 줄, basis 당기/전기 비교):
  scripts/data/company_financials_audit.csv  대구 비상장 외감 제조업
  data/dart/national_listed.csv               전국 유가증권·코스닥 제조업(별도), region 으로 대구 가름
  data/dart/national_audit_sample.csv         전국 비상장 외감 제조업 표본
  data/kosis/corp-mgmt-quantile.csv           한국은행 기업경영분석 분위수(전국, 법인 전수)
  data/ecos/corp-mgmt-region-*.csv            한국은행 지역별 기업경영분석(대구, 법인 전수, 규모별)
  data/nps/YYYYMM.csv                         국민연금 가입 사업장(대구)
지표(회사마다): 매출액 증가율·영업이익률·영업현금흐름 대 매출·부채비율·이자보상비율(영업이익 ÷ 이자비용 × 100).
통계: 중앙값·1·3사분위와 합계 비율(Σ분자 ÷ Σ분모). 전국 표본 중앙값은 부트스트랩 95% 범위.
작은 칸은 값을 비운다(중앙값 5곳, 이자보상비율 100% 미만 비중·고용 20곳). 회사 이름·순위·판정 낱말 없음.
"""
from __future__ import annotations

import csv
import json
import random
import re
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
DG = ROOT / "scripts" / "data" / "company_financials_audit.csv"
NL = ROOT / "data" / "dart" / "national_listed.csv"
NS = ROOT / "data" / "dart" / "national_audit_sample.csv"
NS_META = ROOT / "data" / "dart" / "national_audit_sample.json"
SUMMARY = ROOT / "data" / "dart" / "audit_summary.json"
BOK_Q = ROOT / "data" / "kosis" / "corp-mgmt-quantile.csv"
ECOS = ROOT / "data" / "ecos"
NPS_DIR = ROOT / "data" / "nps"
OUT = ROOT / "data" / "dart" / "audit_compare.json"
MIN_N = 5
MIN_SHARE = 20     # 이자보상비율 100% 미만 비중·고용 칸의 최소 회사 수(작은 칸은 어느 회사인지 짐작될 수 있어 비움)

IND = [("growth", "매출액 증가율", "%"), ("opm", "매출액 영업이익률", "%"), ("ocf", "영업현금흐름 대 매출액", "%"),
       ("debt", "부채비율", "%"), ("icr", "이자보상비율", "%")]
BOK_NAMES = {"growth": ["매출액증가율"], "opm": ["매출액영업이익률"], "debt": ["부채비율"], "icr": ["이자보상비율"],
             "ocf": ["매출액영업활동현금흐름비율", "영업활동현금흐름대매출액"]}
BANDS = [("100억 원 미만", 0, 1e10), ("100억~500억 원", 1e10, 5e10), ("500억~1,500억 원", 5e10, 1.5e11), ("1,500억 원 이상", 1.5e11, 1e20)]


def num(v) -> float | None:
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def read(p: Path) -> list[dict]:
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


class Panel:
    """회사 × 사업연도. 옛 형식(basis 없음, 한 회사 한 줄)도 받는다 — sales_prev 로 전기 매출을 채운다."""

    def __init__(self, rows: list[dict]):
        self.by: dict[str, dict[str, dict]] = {}
        for r in rows:
            if not r.get("fy"):
                continue
            d = self.by.setdefault(r["corp_code"], {})
            if r["fy"] in d and d[r["fy"]].get("basis") == "당기" and r.get("basis") != "당기":
                continue
            d[r["fy"]] = r
            if not r.get("basis") and r.get("sales_prev") and str(int(r["fy"]) - 1) not in d:
                d[str(int(r["fy"]) - 1)] = {**r, "fy": str(int(r["fy"]) - 1), "basis": "전기 비교", "sales": r["sales_prev"], "op": r.get("op_prev", ""),
                                            "net": "", "assets": "", "liab": "", "equity": "", "interest": "", "ocf": ""}

    def year(self) -> str:
        """당기 행이 가장 많은 최근 사업연도(그 수의 절반 이상인 해 가운데 가장 늦은 해)."""
        cnt: dict[str, int] = {}
        for d in self.by.values():
            for fy, r in d.items():
                if r.get("basis", "당기") in ("당기", ""):
                    cnt[fy] = cnt.get(fy, 0) + 1
        if not cnt:
            return ""
        top = max(cnt.values())
        return max(y for y, c in cnt.items() if c >= top * 0.5)

    def at(self, fy: str, pred=lambda r: True) -> list[tuple[str, dict]]:
        return [(c, d[fy]) for c, d in self.by.items() if fy in d and pred(d[fy])]

    def ratios(self, corp: str, fy: str) -> dict:
        d = self.by[corp]
        r = d[fy]
        p = d.get(str(int(fy) - 1), {})
        s, op, ocf = num(r.get("sales")), num(r.get("op")), num(r.get("ocf"))
        sp = num(p.get("sales")) if p else num(r.get("sales_prev"))
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


def q(vals: list[float], p: float) -> float:
    vals = sorted(vals)
    k = (len(vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def pooled(P: Panel, items: list[tuple[str, dict]], key: str) -> float | None:
    a_sum = b_sum = 0.0
    n = 0
    for c, r in items:
        if key == "growth":
            prev = P.by[c].get(str(int(r["fy"]) - 1), {})
            a, b = num(r.get("sales")), (num(prev.get("sales")) if prev else None)
            if a is None or not b:
                continue
            a_sum += a - b
            b_sum += b
        else:
            a_k, b_k = {"opm": ("op", "sales"), "ocf": ("ocf", "sales"), "debt": ("liab", "equity"), "icr": ("op", "interest")}[key]
            a, b = num(r.get(a_k)), num(r.get(b_k))
            if a is None or b is None or (key in ("debt", "icr") and b <= 0):
                continue
            a_sum += a
            b_sum += b
        n += 1
    return round(a_sum / b_sum * 100, 1) if n >= MIN_N and b_sum else None


def icr_low(P: Panel, items: list[tuple[str, dict]], fy: str) -> dict:
    """이자보상비율 100% 미만(영업이익 < 이자비용) 회사 비중 — 이자비용이 있는 회사만 분모. 3년 연속은 세 해 모두 자료가 있는 회사만."""
    one = [(c, r) for c, r in items if (num(r.get("interest")) or 0) > 0 and num(r.get("op")) is not None]
    k1 = sum(1 for _, r in one if num(r["op"]) < num(r["interest"]))
    out = {"n": len(one), "k": k1, "share": round(k1 / len(one) * 100, 1) if len(one) >= MIN_SHARE else None}
    ys = [str(int(fy) - i) for i in range(3)]
    three = []
    for c, _ in items:
        rs = [P.by[c].get(y) for y in ys]
        if all(x and (num(x.get("interest")) or 0) > 0 and num(x.get("op")) is not None for x in rs):
            three.append(all(num(x["op"]) < num(x["interest"]) for x in rs))
    out["n3"] = len(three)
    out["share3"] = round(sum(three) / len(three) * 100, 1) if len(three) >= MIN_SHARE else None
    if out["share"] is None:
        out["k"] = None    # 작은 칸은 건수도 비움
    return out


def stats(P: Panel, items: list[tuple[str, dict]], fy: str, boot: bool = False) -> dict:
    out = {"n": len(items)}
    rs = [P.ratios(c, fy) for c, _ in items]
    for key, _, _ in IND:
        vals = [x[key] for x in rs if key in x]
        cell = {"n": len(vals)}
        if len(vals) >= MIN_N:
            cell.update({"med": round(statistics.median(vals), 1), "q1": round(q(vals, .25), 1), "q3": round(q(vals, .75), 1)})
            if boot:
                rnd = random.Random(20261103)
                meds = sorted(statistics.median(rnd.choices(vals, k=len(vals))) for _ in range(1000))
                cell["ci"] = [round(meds[25], 1), round(meds[974], 1)]
        cell["pooled"] = pooled(P, items, key)
        out[key] = cell
    out["icr_low"] = icr_low(P, items, fy)
    return out


def ksic2(r: dict) -> str:
    k = (r.get("ksic") or "")[:2]
    return "C" + k if k.isdigit() else ""


def band(r: dict) -> str:
    s = num(r.get("sales"))
    if s is None:
        return ""
    return next((nm for nm, lo, hi in BANDS if lo <= s < hi), "")


# ── 한국은행 ──
def bok_quantile(fy: str) -> tuple[dict, dict, str]:
    rows = read(BOK_Q)
    if not rows:
        return {}, {}, ""
    yrs = sorted({r["PRD_DE"] for r in rows})
    year = fy if fy in yrs else yrs[-1]
    total: dict = {}
    by: dict = {}
    for r in rows:
        if r["PRD_DE"] != year or (r.get("C2_NM") or "").strip() != "종합":
            continue
        key = next((k for k, ns in BOK_NAMES.items() if any((r.get("C3_NM") or "").replace(" ", "").startswith(n) for n in ns)), None)
        v = num(r.get("DT"))
        if not key or v is None:
            continue
        sel = (r.get("C4_NM") or "").replace(" ", "")
        slot = "med" if "중위" in sel else "q1" if "1분위" in sel else "q3" if "3분위" in sel else "mean" if "평균" in sel else ""
        if not slot:
            continue
        code = (r.get("C1_NM") or "").split(" ")[0]
        tgt = total if code == "C" else by.setdefault(code, {}) if re.fullmatch(r"C\d\d", code) else None
        if tgt is not None:
            tgt.setdefault(key, {})[slot] = v
    return total, by, year


def bok_region(fy: str) -> dict:
    """ECOS 지역별 기업경영분석 — 대구 법인 전수의 규모별(종합·대기업·중기업·소기업) 제조업 비율과 매출액."""
    want = {"매출액증가율": "growth", "매출액영업이익률": "opm", "부채비율": "debt", "이자보상비율": "icr"}
    rows = []
    for k in ("growth", "profit", "stability", "income"):
        rows += read(ECOS / f"corp-mgmt-region-{k}.csv")
    yrs = sorted({r["TIME"] for r in rows if (r.get("ITEM_NAME1") or "").startswith("C 제조업")})
    if not yrs:
        return {}
    year = fy if fy in yrs else yrs[-1]
    out = {"year": year, "table": "한국은행 지역별 기업경영분석(ECOS 503Y002·005·006·007, 대구)", "by_scale": {}, "by_ksic": {}, "sales": {}}
    for r in rows:
        if r["TIME"] != year:
            continue
        code = (r.get("ITEM_NAME1") or "").split(" ")[0]
        scale = (r.get("ITEM_NAME2") or "").strip()
        nm = (r.get("ITEM_NAME4") or "").replace(" ", "")
        v = num(r.get("DATA_VALUE"))
        if v is None:
            continue
        if re.fullmatch(r"매출액(\(수익\))?", nm) and code == "C":
            out["sales"][scale] = {"value": v, "unit": r.get("UNIT_NAME", "")}
        key = want.get(nm)
        if not key:
            continue
        if code == "C":
            out["by_scale"].setdefault(scale, {})[key] = v
        elif re.fullmatch(r"C\d\d", code) and scale == "종합":
            out["by_ksic"].setdefault(code, {})[key] = v
    return out


def won(v: float, unit: str) -> float:
    u = (unit or "").replace(" ", "")
    return v * {"원": 1, "천원": 1e3, "백만원": 1e6, "십억원": 1e9, "억원": 1e8}.get(u, 1e6)


# ── 국민연금 고용 ──
def nps_months() -> tuple[str, str]:
    ms = sorted(p.stem for p in NPS_DIR.glob("[0-9]" * 6 + ".csv"))
    if not ms:
        return "", ""
    last = ms[-1]
    target = f"{int(last[:4]) - 1}{last[4:]}"
    older = [x for x in ms if "202506" <= x <= target]   # 2025-06 판부터 추출 범위가 달라 그 전 달과 견주지 않는다(data/nps/README)
    return last, (older[-1] if older else "")


def employment(items: list[tuple[str, dict]]) -> tuple[dict, dict]:
    """회사 → (최근 달 가입자, 비교 달 가입자). 이름(법인 표기·공장 표시 뗌) + 구·군으로 국민연금 사업장을 잇고 같은 이름·구·군 사업장은 더한다."""
    try:
        import build_stats as B
    except Exception as e:  # noqa: BLE001
        print(f"[compare] 국민연금 연결 건너뜀: {e}")
        return {}, {}
    last, prev = nps_months()
    meta = {"last": last, "prev": prev}
    if not last:
        return {}, meta

    def load(m: str) -> dict:
        idx: dict = {}
        for r in B.load_nps(m) or []:
            if (r.get("status") or "").strip() in ("2", "탈퇴"):
                continue
            idx.setdefault((r["norm"], r["district"]), []).append(r)
        return idx

    cur, old = load(last), (load(prev) if prev else {})
    out = {}
    for c, r in items:
        keys = [B.norm_name(r.get("name", ""))]
        base = B.site_base_name(r.get("name", ""))
        if base:
            keys.append(B.norm_name(base))
        dist = r.get("district", "")
        hit = next((cur[(k, dist)] for k in keys if (k, dist) in cur), None)
        if not hit:
            continue
        h0 = next((old[(k, dist)] for k in keys if (k, dist) in old), None)
        out[c] = (sum(x["employment"] or 0 for x in hit), sum(x["employment"] or 0 for x in h0) if h0 else None)
    meta["matched"] = len(out)
    return out, meta


def emp_stats(emp: dict, items: list[tuple[str, dict]]) -> dict:
    xs = [emp[c] for c, _ in items if c in emp]
    both = [(a, b) for a, b in xs if b]
    res = {"n": len(xs), "n_both": len(both)}
    if len(xs) >= MIN_SHARE:
        res.update({"med": statistics.median(a for a, _ in xs), "sum": sum(a for a, _ in xs)})
    if len(both) >= MIN_SHARE:
        s1, s0 = sum(a for a, _ in both), sum(b for _, b in both)
        res.update({"chg": round((s1 - s0) / s0 * 100, 1) if s0 else None,
                    "up": round(sum(1 for a, b in both if a > b) / len(both) * 100, 1),
                    "down": round(sum(1 for a, b in both if a < b) / len(both) * 100, 1)})
    return res


def main() -> int:
    DGp, NLp, NSp = Panel(read(DG)), Panel(read(NL)), Panel(read(NS))
    if not (DGp.by or NLp.by or NSp.by):
        print("[compare] 입력 없음 — 건너뜀")
        return 0
    y_dg, y_nl, y_ns = DGp.year(), NLp.year(), NSp.year()
    is_dg = lambda r: (r.get("region") or "").startswith("대구")
    scopes = {   # 이름 → (패널, 사업연도, 행 거르기, 부트스트랩)
        "daegu_listed": (NLp, y_nl, is_dg, False), "national_listed": (NLp, y_nl, lambda r: True, False),
        "daegu_unlisted": (DGp, y_dg, lambda r: True, False), "national_unlisted": (NSp, y_ns, lambda r: True, True),
    }

    def run(extra=lambda r: True) -> dict:
        return {k: stats(P, P.at(fy, lambda r, f=f: f(r) and extra(r)), fy, b) if fy else {"n": 0} for k, (P, fy, f, b) in scopes.items()}

    bq_total, bq_ksic, bq_year = bok_quantile(y_dg or y_nl)
    reg = bok_region(y_dg or y_nl)
    res = {
        "updated": date.today().isoformat(), "min_n": MIN_N, "min_share": MIN_SHARE,
        "indicators": [{"key": k, "name": n, "unit": u} for k, n, u in IND],
        "bands": [b[0] for b in BANDS],
        "years": {"daegu_unlisted": y_dg, "listed": y_nl, "national_unlisted": y_ns},
        "total": run(),
        "by_group": [], "by_ksic": [], "by_band": [], "by_district": [], "trend": {},
        "bok": {"year": bq_year, "table": "한국은행 기업경영분석 분위수(KOSIS DT_501Y086)", "by": bq_total} if bq_total else {},
        "bok_year_ksic": bq_year, "bok_region": reg,
        "sample": json.loads(NS_META.read_text(encoding="utf-8")) if NS_META.exists() else {},
        "summary": json.loads(SUMMARY.read_text(encoding="utf-8")) if SUMMARY.exists() else {},
    }
    allrows = [r for P in (DGp, NLp, NSp) for d in P.by.values() for r in d.values()]
    for g in sorted({r.get("group", "") for r in allrows if r.get("group")}):
        res["by_group"].append({"group": g, **run(lambda r, g=g: r.get("group") == g)})
    for code in sorted({ksic2(r) for r in allrows if ksic2(r)}):
        res["by_ksic"].append({"code": code, **run(lambda r, code=code: ksic2(r) == code),
                               "bok": bq_ksic.get(code, {}), "bok_region": (reg.get("by_ksic") or {}).get(code, {})})
    for nm, _, _ in BANDS:
        res["by_band"].append({"band": nm, **run(lambda r, nm=nm: band(r) == nm)})
    if y_dg:
        for d in sorted({r.get("district", "") for _, r in DGp.at(y_dg) if r.get("district")}):
            res["by_district"].append({"district": d, "daegu_unlisted": stats(DGp, DGp.at(y_dg, lambda r, d=d: r.get("district") == d), y_dg)})
    # 3개 사업연도 추이 — 그해 있는 회사 전체와, 세 해 모두 있는 같은 회사 묶음
    for k, (P, fy, f, b) in scopes.items():
        if not fy:
            continue
        ys = [str(int(fy) - i) for i in (2, 1, 0)]
        same = {c for c, d in P.by.items() if all(y in d and f(d[y]) for y in ys)}
        res["trend"][k] = {"years": ys, "all": {y: stats(P, P.at(y, f), y) for y in ys},
                           "same": {y: stats(P, [(c, r) for c, r in P.at(y, f) if c in same], y) for y in ys}, "same_n": len(same)}
    # 국민연금 고용(대구 비상장 외감)
    if y_dg:
        items = DGp.at(y_dg)
        emp, meta = employment(items)
        res["employment"] = {"months": meta, "total": emp_stats(emp, items),
                             "by_band": [{"band": nm, **emp_stats(emp, [(c, r) for c, r in items if band(r) == nm])} for nm, _, _ in BANDS],
                             "by_ksic": [{"code": code, **emp_stats(emp, [(c, r) for c, r in items if ksic2(r) == code])}
                                         for code in sorted({ksic2(r) for _, r in items if ksic2(r)})]}
    # 빠진 층 — 대구 법인 전수(한국은행) 매출 가운데 이 사이트가 읽은 외감·상장 회사 매출 몫
    if (reg.get("sales") or {}).get("종합"):
        yr = reg["year"]
        tot = won(reg["sales"]["종합"]["value"], reg["sales"]["종합"]["unit"])
        dg_sum = sum(num(r.get("sales")) or 0 for _, r in DGp.at(yr))
        dl_sum = sum(num(r.get("sales")) or 0 for _, r in NLp.at(yr, is_dg))
        res["coverage"] = {"year": yr, "bok_sales_won": tot, "unlisted_sales_won": dg_sum, "listed_sales_won": dl_sum,
                           "unlisted_n": len(DGp.at(yr)), "listed_n": len(NLp.at(yr, is_dg)),
                           "unlisted_share": round(dg_sum / tot * 100, 1) if tot else None,
                           "listed_share": round(dl_sum / tot * 100, 1) if tot else None}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    t = res["total"]
    print(f"[compare] 대구 상장 {t['daegu_listed']['n']} · 전국 상장 {t['national_listed']['n']} · 대구 비상장 {t['daegu_unlisted']['n']} · "
          f"전국 비상장 표본 {t['national_unlisted']['n']} → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
