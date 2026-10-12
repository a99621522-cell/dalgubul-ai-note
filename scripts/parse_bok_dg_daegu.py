#!/usr/bin/env python3
"""한국은행 대구경북본부 「대구경북지역 주요 경제지표」(경제통계 PDF)에서 '(대 구)' 표만 뽑는다(운영자 지시 2026-10-12 '한국은행자료 대구만 추출해서 올려').

표마다 (대구·경북)·(대 구)·(경 북) 판이 있고 그중 대구 판만 → data/bok/daegu_<key>.csv(period, column, value) + data/bok/daegu_tables.json(표 이름·단위·열·기준).
period: 연간은 YYYY, 월은 YYYY-MM, 분기는 YYYY-Q1~Q4(산업별 대출금), (잠정 'p' 표시는 prelim 열). 값은 표 그대로('-' 는 빈칸). 행마다 합계 검산(가능한 표만)을 로그로.
BSI·소비자동향지수는 대구경북 판만 있어 scripts/parse_bok_dg_bsi.py 가 맡는다.
사용: python3 scripts/parse_bok_dg_daegu.py <PDF 또는 txt> --issue 2026-10
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bok"
# 표 제목 앞부분 → (key, 이름, 단위, 열, 시점 기준)
TABLES = [
    ("2.1 예금은행 수신(Ⅰ)", "deposits", "예금은행 수신", "억원", ["총수신", "예금 소계", "요구불예금", "저축성예금", "시장성 수신 소계", "CD", "금융채", "매출어음", "RP"], "말잔"),
    ("2.1 예금은행 수신(Ⅱ)", "deposits_demand", "예금은행 요구불예금", "억원", ["총예금", "요구불예금 소계", "가계당좌예금", "당좌예금", "보통예금", "별단예금", "공금예금", "기타"], "말잔"),
    ("2.1 예금은행 수신(Ⅲ)", "deposits_savings", "예금은행 저축성예금", "억원", ["저축성예금 소계", "정기예금", "정기적금", "저축예금", "기업자유예금", "수입부금", "주택부금", "기타"], "말잔"),
    ("2.2.1 자금별 대출금", "loans_fund", "예금은행 자금별 대출금", "억원", ["총대출금", "금융자금 소계", "할인어음", "당좌대출", "일반자금", "기타", "재정자금"], "말잔"),
    ("2.2.2 주체별 및 용도별 대출금", "loans_borrower", "예금은행 주체별·용도별 대출금", "억원", ["총대출금", "기업", "가계", "가계 중 주택담보대출", "공공 및 기타", "운전자금", "시설자금"], "말잔"),
    ("2.2.3 기업자금 대출금", "loans_corp", "예금은행 기업자금 대출금", "억원·%", ["총대출금", "기업자금 소계", "대기업", "중소기업", "중소기업 운전자금", "중소기업 시설자금", "중소기업 대출비중(%)"], "말잔"),
    ("2.2.4 산업별 대출금", "loans_industry", "예금은행 산업별 대출금", "억원", ["산업별 소계", "농림어업", "광업", "제조업", "전기·가스·증기·공기조절", "건설업", "도매 및 소매업", "운수 및 창고업", "숙박 및 음식점업", "금융 및 보험업", "부동산업", "가계 대출금", "대출금 총계"], "말잔"),
    ("3.1 비은행예금취급기관 수신", "nonbank_deposits", "비은행예금취급기관 수신", "억원", ["계", "종합금융회사", "자산운용회사", "신탁회사", "상호저축은행", "신용협동조합", "상호금융", "새마을금고", "우체국예금"], "말잔"),
    ("3.2.1 기관별 여신", "nonbank_loans", "비은행예금취급기관 기관별 여신", "억원", ["계", "종합금융회사", "신탁회사", "상호저축은행", "신용협동조합", "상호금융", "새마을금고", "기타"], "말잔"),
    ("3.2.2 차입주체별 여신", "nonbank_loans_borrower", "비은행예금취급기관 차입주체별 여신", "억원", ["기업", "대기업", "중소기업", "가계", "가계 중 주택담보대출"], "말잔"),
    ("4. 어음부도율", "bills_newcorp", "어음부도율·신설법인수", "억원·%·개", ["어음교환액", "어음부도액", "어음부도율(%)", "부도업체수", "부도 법인", "부도 개인", "신설법인수"], "기간중"),
]
# 검산: (key, 합 = 항목들)
CHECKS = {"deposits": ("총수신", ["예금 소계", "시장성 수신 소계"]), "loans_fund": ("총대출금", ["금융자금 소계", "재정자금"]),
          "loans_borrower": ("총대출금", ["기업", "가계", "공공 및 기타"]), "loans_corp": ("기업자금 소계", ["대기업", "중소기업"]),
          "loans_industry": ("대출금 총계", ["산업별 소계", "가계 대출금"]), "nonbank_loans_borrower": ("기업", ["대기업", "중소기업"])}


def text_of(p: Path) -> str:
    if p.suffix.lower() == ".pdf":
        return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout
    return p.read_text(encoding="utf-8")


def num(s: str):
    s = s.replace(",", "")
    return "" if s in ("-", "") else s


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    issue = argv[argv.index("--issue") + 1] if "--issue" in argv else ""
    L = text_of(Path(argv[0])).split("\n")
    meta, title = [], ""
    for i, ln in enumerate(L):
        s = ln.strip()
        if re.match(r"^\d(\.\d)*\.?\s?\S", s) and len(s) < 40:
            title = s
        if not re.match(r"^\(대\s*구\)", s):
            continue
        spec = next((t for t in TABLES if title.startswith(t[0])), None)
        if not spec:
            print(f"  표 정의 없음: {title}")
            continue
        _, key, name, unit, cols, basis = spec
        rows, year = [], ""
        for ln2 in L[i + 1:]:
            t = ln2.strip()
            if t.startswith("주 :") or t.startswith("자료") or re.match(r"^\((대|경)", t):
                break
            q = re.match(r"^(?:(\d{4})\.\s*)?([ⅠⅡⅢⅣ])(p?)\s+(.*)$", t)   # 분기 표(산업별 대출금)
            if q:
                vals = q.group(4).split()
                if len(vals) != len(cols):
                    continue
                year = q.group(1) or year
                period = f"{year}-Q{'ⅠⅡⅢⅣ'.index(q.group(2)) + 1}"
                for c, v in zip(cols, vals):
                    rows.append({"period": period, "column": c, "value": num(v), "prelim": "p" if q.group(3) else ""})
                continue
            m = re.match(r"^(\d{4})(?:\.\s*(\d{1,2})(p?))?\s+(.*)$", t) or re.match(r"^()(\d{1,2})(p?)\s+(.*)$", t)
            if not m:
                continue
            vals = m.group(4).split()
            if len(vals) != len(cols):
                continue
            if m.group(1):
                year = m.group(1)
            period = f"{year}-{int(m.group(2)):02d}" if m.group(2) else m.group(1)
            if not period or (not m.group(2) and not m.group(1)):
                continue
            for c, v in zip(cols, vals):
                rows.append({"period": period, "column": c, "value": num(v), "prelim": "p" if m.group(3) else ""})
        # 검산
        if key in CHECKS:
            tot, parts = CHECKS[key]
            by = {}
            for r in rows:
                by.setdefault(r["period"], {})[r["column"]] = r["value"]
            bad = [p for p, d in by.items() if all(d.get(x) not in (None, "") for x in [tot] + parts)
                   and abs(float(d[tot]) - sum(float(d[x]) for x in parts)) > 2]
            print(f"  {key}: 검산 {len(by)}개 시점, 어긋남 {bad[:5]}")
        with open(OUT / f"daegu_{key}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["period", "column", "value", "prelim"])
            w.writeheader()
            w.writerows(rows)
        periods = sorted({r["period"] for r in rows})
        meta.append({"key": key, "title": name, "source_title": title, "unit": unit, "basis": basis, "columns": cols,
                     "periods": len(periods), "first": periods[0] if periods else "", "last": periods[-1] if periods else ""})
        print(f"저장 daegu_{key}.csv {len(rows)}행 {periods[0] if periods else ''}~{periods[-1] if periods else ''}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "daegu_tables.json").write_text(json.dumps({"source": "한국은행 대구경북본부 「대구경북지역 주요 경제지표」(경제통계)", "issue": issue,
                                                      "region": "대구", "tables": meta}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
