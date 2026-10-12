#!/usr/bin/env python3
"""산업단지 관리기관 분기 자료 글자(data/complexes/raw/) → 표 CSV(운영자 지시 2026-10-12 '산단별 매출액').

① <key>_<YYYY>q<N>_1.txt — 산단공 양식 「단지별 입주현황」: 단지(하위 단지)마다 총괄표(입주·가동·가동율·고용·생산·수출, 전년 같은 분기와 당분기)와
   '4. 매출액'(생산·수출 연간계획·당분기 실적·누계 실적, 백만원) → data/complexes/production.csv
② <key>_<YYYY>q<N>_2.txt — 관리기관 「입주업체 경기동향 보고서」 첫 쪽 요약(가동률·총생산액·입주업체·근로자수)과 '전분기 대비 생산실적' 표(생산액·내수·수출, 백만원)
   → data/complexes/trend.csv (분기마다 당분기 값만)
값은 문서 그대로 옮기고 계산하지 않는다(억 원 환산은 페이지에서 ÷100). 관리기관의 해설·전망 문장은 옮기지 않는다.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "complexes" / "raw"
OUT_P = ROOT / "data" / "complexes" / "production.csv"
OUT_T = ROOT / "data" / "complexes" / "trend.csv"
# 문서의 단지 이름 → 기업 사전(팩토리온) 단지 이름
FO = {"대구성서산업단지 1차단지": "성서지방산업단지", "대구성서산업단지 2차단지": "성서지방산업단지",
      "대구성서산업단지 3차단지": "성서지방산업단지", "대구성서산업단지 4차단지": "성서지방산업단지",
      "대구성서산업단지 5차단지": "성서5차첨단산업단지", "대구인쇄출판밸리": "대구인쇄출판밸리"}
COLS_P = ["source", "quarter", "complex", "total", "fo_name", "firms", "operating", "operating_rate", "employment_prev", "employment",
          "prod_prev_bil", "prod_bil", "export_prev_bil", "export_bil", "prod_plan_mil", "prod_q_mil", "prod_cum_mil",
          "export_plan_mil", "export_q_mil", "export_cum_mil", "doc_url"]
COLS_T = ["source", "quarter", "operating_rate", "prod_mil", "domestic_mil", "export_mil", "firms", "workers", "doc_url"]
NUM = r"-?[\d,]+(?:\.\d+)?"


def n(s: str) -> str:
    return s.replace(",", "")


def meta(text: str) -> tuple[str, str]:
    m = re.search(r"^# 첨부: .*?(https?://\S+)", text, re.M)
    g = re.search(r"^# 글: (\S+)", text, re.M)
    return (g.group(1) if g else ""), (m.group(1) if m else "")


def parse_units(path: Path, source: str, quarter: str) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    post, _ = meta(text)
    lines = text.splitlines()
    heads = [(i, re.sub(r"\s+입주현황.*$", "", ln.strip())) for i, ln in enumerate(lines) if re.search(r"입주현황(\(|$)", ln.strip()) and not ln.startswith("#")]
    rows = []
    for k, (i, name) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        block = lines[i:end]
        summ = next((ln for j, ln in enumerate(block) if j > 0 and "실 적 대비" in block[j - 1]), "")
        t = re.findall(NUM, summ)
        sales = ""
        for j, ln in enumerate(block):
            if "(3)연간계획" in ln:
                sales = next((x for x in block[j + 1:j + 4] if x.strip()), "")
                break
        s = re.findall(NUM, sales)
        if len(t) < 12 or len(s) < 6:
            print(f"  {path.name} '{name}' 읽기 실패 (총괄 {len(t)}칸, 매출액 {len(s)}칸)")
            continue
        firms, operating, op_rate = t[-12], t[-11], t[-10]
        e_prev, e_now, _, p_prev, p_now, _, x_prev, x_now, _ = t[-9:]
        total = "1" if not re.search(r"\d차단지|출판", name) else ""
        rows.append({"source": source, "quarter": quarter, "complex": name, "total": total, "fo_name": FO.get(name, ""),
                     "firms": n(firms), "operating": n(operating), "operating_rate": op_rate, "employment_prev": n(e_prev), "employment": n(e_now),
                     "prod_prev_bil": n(p_prev), "prod_bil": n(p_now), "export_prev_bil": n(x_prev), "export_bil": n(x_now),
                     "prod_plan_mil": n(s[0]), "prod_q_mil": n(s[1]), "prod_cum_mil": n(s[2]),
                     "export_plan_mil": n(s[3]), "export_q_mil": n(s[4]), "export_cum_mil": n(s[5]), "doc_url": post})
    return rows


def parse_trend(path: Path, source: str, quarter: str) -> dict | None:
    text = path.read_text(encoding="utf-8")
    post, _ = meta(text)

    def second(pat: str) -> str:
        m = re.search(pat + r"\s+(" + NUM + r")\s*[%개명]?\s+(" + NUM + r")", text)
        return n(m.group(2)) if m else ""

    row = {"source": source, "quarter": quarter, "operating_rate": second(r"가\s*동\s*률"), "prod_mil": second(r"\n\s*생산액"),
           "domestic_mil": second(r"\n\s*내\s*수"), "export_mil": second(r"\n\s*수\s*출"),
           "firms": second(r"입주업체"), "workers": second(r"근로자수"), "doc_url": post}
    if not row["prod_mil"]:
        print(f"  {path.name} 생산실적 표 못 찾음")
        return None
    return row


def main() -> int:
    prod, trend = [], []
    for p in sorted(RAW.glob("*_*q*_*.txt")):
        m = re.match(r"(.+)_(\d{4})q(\d)_(\d)\.txt$", p.name)
        if not m:
            continue
        src, q, kind = m.group(1), f"{m.group(2)}-{m.group(3)}", m.group(4)
        if kind == "1":
            prod += parse_units(p, src, q)
        else:
            r = parse_trend(p, src, q)
            if r:
                trend.append(r)
    for out, cols, rows in ((OUT_P, COLS_P, prod), (OUT_T, COLS_T, trend)):
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"저장: {out.relative_to(ROOT)} {len(rows)}행")
    return 0


if __name__ == "__main__":
    sys.exit(main())
