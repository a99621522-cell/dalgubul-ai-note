#!/usr/bin/env python3
"""지원 전후 고용 변화표 — 추세·비교·효과 보강 3단계(2026-10-06).

지원사업 이력(scripts/data/support_history.csv, 공개 명단)에 이름이 실린 기업과 그렇지 않은 기업의 국민연금 가입자 수를
지원 연도 전(전년 12월 자료)과 후(다음 해 1월 자료)로 나란히 놓는다. 비교군은 같은 산업 그룹·같은 규모 띠(지원 전 가입자 수)에서
지원 전해~다음 해에 지원 이력이 없는 기업.

이것은 관찰이지 효과 평가가 아니다(선정 자체가 성장 가능성이 큰 기업을 고른 결과일 수 있고, 가입자 수는 사업장 단위 합계다).
기업 이름은 싣지 않고 묶음별 집계만 낸다. 묶음 기업 수가 MIN_N 미만이면 값을 비운다.
출력: data/effects/summary.json (코호트 연도별 묶음 표). 페이지 /support/before-after/ 가 읽는다.
사용: python3 scripts/effect_table.py   (nps.yml·nps_backfill.yml 이 집계 뒤 실행하면 좋다)
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_stats as bs  # noqa: E402

OUT = ROOT / "data" / "effects"
MIN_N = 10
BANDS = [(1, 9, "1~9명"), (10, 49, "10~49명"), (50, 299, "50~299명"), (300, 10**9, "300명 이상")]


def band(n: int) -> str:
    for lo, hi, name in BANDS:
        if lo <= n <= hi:
            return name
    return "미상"


def nps_months() -> list[str]:
    return sorted(p.stem for p in bs.NPS_DIR.glob("??????.csv"))


def pick_months(year: int, months: list[str]) -> tuple[str | None, str | None]:
    """지원 연도 Y 의 전: Y-1 년 12월까지 중 가장 늦은 자료, 후: Y+1 년 1월부터 중 가장 이른 자료."""
    before = [m for m in months if m <= f"{year - 1}12"]
    after = [m for m in months if m >= f"{year + 1}01"]
    return (before[-1] if before else None), (after[0] if after else None)


def load_support() -> dict[str, list[dict]]:
    by_id: dict[str, list[dict]] = defaultdict(list)
    with open(bs.SUPPORT, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("id") and r.get("year", "").isdigit():
                by_id[r["id"]].append(r)
    return by_id


def summarize(pairs: list[tuple[int, int]]) -> dict | None:
    """pairs: [(전, 후)]. 기업 수가 MIN_N 미만이면 None."""
    n = len(pairs)
    if n < MIN_N:
        return {"n": n} if n else None
    b = sum(p[0] for p in pairs); a = sum(p[1] for p in pairs)
    rates = [(p[1] / p[0] - 1) * 100 for p in pairs if p[0] > 0]
    return {"n": n, "before_sum": b, "after_sum": a, "sum_change_pct": round((a / b - 1) * 100, 1) if b else None,
            "before_median": statistics.median(p[0] for p in pairs), "after_median": statistics.median(p[1] for p in pairs),
            "median_rate_pct": round(statistics.median(rates), 1) if rates else None,
            "up_share_pct": round(sum(1 for p in pairs if p[1] > p[0]) / n * 100, 1),
            "down_share_pct": round(sum(1 for p in pairs if p[1] < p[0]) / n * 100, 1)}


def main() -> int:
    companies = bs.load_companies()
    by_id = {c["id"]: c for c in companies}
    support = load_support()
    months = nps_months()
    years = sorted({int(r["year"]) for rs in support.values() for r in rs})
    cohorts = []
    cache: dict[str, dict[str, dict]] = {}

    def matched(m: str) -> dict[str, dict]:
        if m not in cache:
            rows = bs.load_nps(m)
            cache[m] = bs.match_nps(companies, rows) if rows else {}
        return cache[m]

    for y in years:
        mb, ma = pick_months(y, months)
        if not mb or not ma:
            continue
        emp_b, emp_a = matched(mb), matched(ma)
        # 기업별 (전, 후) — 두 달 모두 매칭되고 전 가입자 1명 이상
        pair: dict[str, tuple[int, int]] = {}
        for cid in emp_b.keys() & emp_a.keys():
            b, a = emp_b[cid].get("employment") or 0, emp_a[cid].get("employment") or 0
            if b >= 1:
                pair[cid] = (b, a)
        treated = {cid for cid, rs in support.items() if any(int(r["year"]) == y for r in rs) and cid in pair}
        untouched = {cid for cid in pair if cid not in support or not any(y - 1 <= int(r["year"]) <= y + 1 for r in support[cid])}
        # 묶음: 전체 / 산업 그룹 / 규모 띠 / 지원 유형 / 재원 — 지원군과 같은 산업·규모 비교군
        def group_key(cid: str, how: str) -> str:
            c = by_id.get(cid, {})
            return {"group": c.get("group", "미분류"), "band": band(pair[cid][0])}[how]
        def cmp_for(cids: set[str]) -> list[tuple[int, int]]:
            """지원군 cids 와 같은 (산업, 규모 띠) 조합의 비교군 쌍"""
            keys = {(group_key(c, "group"), group_key(c, "band")) for c in cids}
            return [pair[c] for c in untouched if (group_key(c, "group"), group_key(c, "band")) in keys]
        blocks = []
        def add(name: str, label: str, cids: set[str]) -> None:
            t = summarize([pair[c] for c in cids]); u = summarize(cmp_for(cids)) if cids else None
            if t:
                blocks.append({"kind": name, "label": label, "treated": t, "comparison": u})
        add("all", "전체", treated)
        for g in sorted({group_key(c, "group") for c in treated}):
            add("group", g, {c for c in treated if group_key(c, "group") == g})
        for _, _, bn in BANDS:
            add("band", bn, {c for c in treated if group_key(c, "band") == bn})
        kinds = defaultdict(set); layers = defaultdict(set)
        for cid in treated:
            for r in support[cid]:
                if int(r["year"]) == y:
                    kinds[r.get("type") or "기타"].add(cid); layers[r.get("layer") or "기타"].add(cid)
        for k in sorted(kinds):
            add("type", k, kinds[k])
        for k in sorted(layers):
            add("layer", k, layers[k])
        cohorts.append({"year": y, "before": f"{mb[:4]}-{mb[4:]}", "after": f"{ma[:4]}-{ma[4:]}", "treated_n": len(treated), "comparison_pool_n": len(untouched),
                        "support_rows_n": sum(1 for rs in support.values() for r in rs if int(r["year"]) == y), "blocks": blocks})
        print(f"[{y}] 전 {mb} 후 {ma}: 지원군 {len(treated)}곳(명단 {cohorts[-1]['support_rows_n']}건 중 양쪽 달 매칭) · 비교군 풀 {len(untouched)}곳 · 묶음 {len(blocks)}")
    OUT.mkdir(parents=True, exist_ok=True)
    doc = {"generated": __import__("datetime").date.today().isoformat(), "min_n": MIN_N, "nps_months": [f"{m[:4]}-{m[4:]}" for m in months],
           "method": "지원 연도 Y 의 전 = Y-1년 12월까지 가장 늦은 국민연금 자료, 후 = Y+1년 1월부터 가장 이른 자료. 두 달 모두 매칭되고 전 가입자 1명 이상인 기업만. "
                     "비교군 = 같은 산업 그룹·같은 규모 띠(전 가입자 수)에서 Y-1~Y+1 지원 이력이 없는 기업. 합계 증감률 = 후 합 ÷ 전 합 − 1, 중앙값 증감률 = 기업별 증감률의 중앙값. "
                     "관찰이지 효과 평가가 아니다(선정 편향, 사업장 단위 합계, 지원 시점·금액 미반영).",
           "cohorts": cohorts}
    (OUT / "summary.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {OUT.relative_to(ROOT)}/summary.json 코호트 {len(cohorts)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
