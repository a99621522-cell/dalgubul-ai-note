#!/usr/bin/env python3
"""대구시 세부사업(scripts/data/city_programs.csv, parse_city_budget.py 결과) ↔ 국비 사업 DB(programs_*.csv) 이름 매칭
→ scripts/data/match_daegu_national.csv. 표준 라이브러리만. 평가 없음 — 이름 유사도와 '확실/확인 필요' 판정만 적는다.

사용: python3 scripts/match_daegu.py  (인자 없음. 옛 버전은 PDF 를 받았지만 이제 파서가 따로 있다)
"""
import csv, difflib, re
from pathlib import Path
from programs import norm  # 정규화 규칙은 programs.py 한 곳에만 둔다

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scripts" / "data"
THRESHOLD, SURE = 0.72, 0.85
MINISTRY_HINT = {"산업부": "산업통상", "산업통상부": "산업통상", "중기부": "중소벤처", "중소벤처기업부": "중소벤처", "과기부": "과학기술", "과기정통부": "과학기술"}


def load_programs():
    out = []
    for f in sorted(DATA.glob("programs_*.csv")):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            if r.get("name"):
                out.append({**r, "src": f.stem.replace("programs_", ""), "n": norm(r["name"])})
    return out


def main():
    allp = load_programs()
    src = DATA / "city_programs.csv"
    if not src.exists():
        print("city_programs.csv 가 없다 — scripts/parse_city_budget.py 를 먼저"); return
    rows, seen = [], set()
    for c in csv.DictReader(open(src, encoding="utf-8")):
        if c.get("admin") == "Y" or c["name"] in seen:
            continue
        seen.add(c["name"])
        n = norm(c["name"])
        if len(n) < 5:
            continue
        hay = f"{c.get('basis','')} {c.get('content','')} {c.get('purpose','')}"
        hint = next((v for k, v in MINISTRY_HINT.items() if k in hay), "")
        best = (0.0, None)
        for r in allp:
            if not r["n"]:
                continue
            sc = difflib.SequenceMatcher(None, n, r["n"]).ratio()
            if len(n) >= 8 and (n in r["n"] or r["n"] in n):
                sc = max(sc, 0.9)
            if hint and hint in (r.get("ministry") or ""):
                sc += 0.03   # 사업설명서 본문이 그 부처를 언급하면 같은 부처 사업을 조금 우선
            if sc > best[0]:
                best = (sc, r)
        if best[0] >= THRESHOLD:
            r = best[1]
            rows.append({"대구시 실국": c["org"], "부서": c["dept"], "대구시 세부사업": c["name"], "대구시 2026(천원)": c["budget_2026"], "대구시 2025(천원)": c["budget_2025"],
                         "출처": r["src"], "부처": r.get("ministry", ""), "국비 사업": r["name"], "코드": r.get("code", ""), "국비 2026(백만원)": r.get("budget_2026", ""),
                         "유사도": round(min(best[0], 1.0), 2), "판정": "확실" if best[0] >= SURE else "확인 필요", "대구시 상태": c["status"]})
    out = DATA / "match_daegu_national.csv"
    # 옛 세출예산 명세서에서 이은 다른 실국(경제국 등) 행은 그 실국의 사업설명서가 들어올 때까지 남긴다
    new_orgs = {c["org"] for c in csv.DictReader(open(src, encoding="utf-8"))}
    if out.exists():
        kept = [r for r in csv.DictReader(open(out, encoding="utf-8")) if r.get("대구시 실국") and r["대구시 실국"] not in new_orgs and r["대구시 세부사업"] not in {x["대구시 세부사업"] for x in rows}]
        for r in kept:
            rows.append({k: r.get(k, "") for k in (rows[0].keys() if rows else r.keys())})
        if kept:
            print(f"옛 매칭 {len(kept)}건 유지(실국: {sorted({r['대구시 실국'] for r in kept})})")
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["대구시 세부사업"])
        w.writeheader(); w.writerows(rows)
    print(f"{len(rows)}건 매칭 (확실 {sum(1 for r in rows if r['판정'] == '확실')}) → {out}")


if __name__ == "__main__":
    main()
