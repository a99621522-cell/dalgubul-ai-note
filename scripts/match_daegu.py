#!/usr/bin/env python3
"""대구시 세출예산 사업명세서(PDF) 세부사업 ↔ 국비 사업 DB(programs_*.csv) 이름 매칭 → scripts/data/match_daegu_national.csv
사용: python3 scripts/match_daegu.py <대구시 세출명세 PDF 1개 이상>
"""
import difflib, re, subprocess, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent; DATA = ROOT / "scripts" / "data"
def norm(s): return re.sub(r"\(R&D\)|\(정보화\)|\(국가직접지원\)|\(국가직접지|원\)|\(자율\)|\(1단계전환\)|\(2단계전환\)|\s|[·ㆍ‧,()/]", "", s)
def load_programs():
    fr = []
    for f in sorted(DATA.glob("programs_*.csv")):
        d = pd.read_csv(f, dtype=str).fillna(""); d["src"] = f.stem.replace("programs_", ""); fr.append(d)
    allp = pd.concat(fr, ignore_index=True); allp["n"] = allp.name.map(norm); return allp
def daegu_items(pdf):
    t = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
    org = re.search(r"본예산\s+\S+\s+(\S+)", t); org = org.group(1) if org else Path(pdf).stem
    lines = t.split("\n"); dept = ""; items = []
    for i, l in enumerate(lines):
        dm = re.search(r"부서\s*:\s*(\S+)", l)
        if dm: dept = dm.group(1)
        m = re.match(r"^\s*([가-힣A-Za-z][^\n]*?)\s+([\d,]+)\s+([\d,]+)\s+(△?[\d,]+)\s*$", l)
        if not m: continue
        name = m.group(1).strip()
        if i > 0 and re.match(r"^\s*[가-힣A-Za-z(][^\d]*$", lines[i-1]) and len(lines[i-1].strip()) > 3 and not re.search(r"단위|정책|실국|부서|코드|명칭", lines[i-1]):
            name = lines[i-1].strip() + " " + name
        if re.search(r"^\d|일반운영비|여비|업무추진비|민간이전|자치단체|자본이전|출연금|시설비|인건비|예수금|기본경비|경상적|사무관리|국내여비|민간경상|공기관", name): continue
        items.append((org, dept, name, m.group(2), m.group(3)))
    return list(dict.fromkeys(items))
def main(pdfs):
    allp = load_programs(); rows = []
    for pdf in pdfs:
        for org, dept, cn, b26, b25 in daegu_items(pdf):
            n = norm(cn)
            if len(n) < 5: continue
            best = (0, None)
            for r in allp.itertuples():
                if not r.n: continue
                sc = difflib.SequenceMatcher(None, n, r.n).ratio()
                if len(n) >= 8 and (n in r.n or r.n in n): sc = max(sc, 0.9)
                if sc > best[0]: best = (sc, r)
            if best[0] >= 0.72:
                r = best[1]; rows.append((org, dept, cn, b26, b25, r.src, r.ministry, r.name, r.code, r.budget_2026, round(best[0], 2), "확실" if best[0] >= 0.85 else "확인 필요"))
    m = pd.DataFrame(rows, columns=["대구시 실국", "부서", "대구시 세부사업", "대구시 2026(천원)", "대구시 2025(천원)", "출처", "부처", "국비 사업", "코드", "국비 2026(백만원)", "유사도", "판정"]).drop_duplicates(["대구시 세부사업"])
    m.to_csv(DATA / "match_daegu_national.csv", index=False, encoding="utf-8"); print(len(m), "건 매칭 (확실", (m["판정"] == "확실").sum(), ")")
if __name__ == "__main__": main(sys.argv[1:])
