#!/usr/bin/env python3
"""대구 산업단지 전체 현황표(단지별 지정면적·입주업체·종업원·연 매출액·관리기관) → data/complexes/overview.csv + overview.json.

운영자 지시 2026-10-18 '다른 산단은 산단별 홈페이지 이런 곳을 찾아봐': 관리기관 누리집을 찾다가 KOTRA 「대구 투자환경」 누리집
(investkorea.org/dg-kr, 투자 프로젝트 > 전체 산업단지 현황)의 '산업단지 현황' 표에 대구 산업단지 24곳(국가 1·일반 16·도시첨단 3·농공 4)의
'YY년 매출액(억 원)이 단지마다 실린 것을 찾았다(2024년 12월 말 기준). 표는 담당 부서로 대구시 산단진흥과 등을 적는다.
표의 '계' 행과 단지 행의 합이 칸마다 맞을 때만 저장한다(행 구조가 바뀌어 잘못 읽으면 덮어쓰지 않는다). 값은 표 그대로, 평가 없음.
robots.txt 를 지킨다(2026-10-18 확인: /dg-kr/cntnts/ 는 막지 않음). 이 세션 환경은 외부 접속이 막혀 있어 complex_reports.yml 이 돌린다.
  python3 scripts/fetch_complex_overview.py
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.robotparser
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "complexes"
URL = "https://www.investkorea.org/dg-kr/cntnts/i-2972/web.do"
UA = "Mozilla/5.0 (compatible; daitda-note-bot/1.0; +https://daitda.co.kr)"
HEAD = ["group", "name", "built", "area_k_m2", "firms", "employees", "sales_eok", "agency", "industrial_k_m2"]
NUMS = ["area_k_m2", "firms", "employees", "sales_eok", "industrial_k_m2"]


def text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def num(s: str) -> str:
    s = s.replace(",", "").strip()
    return s if re.fullmatch(r"\d+(\.\d+)?", s) else ""


def expand(table) -> list[list]:
    """rowspan·colspan 을 펼친 격자(칸마다 원래 요소)."""
    grid: list[list] = []
    span: dict[int, tuple[object, int]] = {}
    for tr in table.find_all("tr"):
        row: list = []
        cells = iter(tr.find_all(["th", "td"], recursive=False))
        col = 0
        while True:
            if col in span:
                el, left = span[col]
                row.append(el)
                span[col] = (el, left - 1) if left > 1 else None
                if span[col] is None:
                    del span[col]
                col += 1
                continue
            c = next(cells, None)
            if c is None:
                break
            cs, rs = int(c.get("colspan", 1) or 1), int(c.get("rowspan", 1) or 1)
            for _ in range(cs):
                row.append(c)
                if rs > 1:
                    span[col] = (c, rs - 1)
                col += 1
        while col in span:
            el, left = span[col]
            row.append(el)
            span[col] = (el, left - 1) if left > 1 else None
            if span[col] is None:
                del span[col]
            col += 1
        grid.append(row)
    return grid


def parse(html: str) -> tuple[list[dict], dict, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    body = text(soup)
    m = re.search(r"\((20\d\d)\.\s*(\d{1,2})\s*월\s*말\s*기준", body)
    as_of = f"{m.group(1)}-{int(m.group(2)):02d}" if m else ""
    m = re.search(r"[’']\s*(\d\d)\s*년\s*매출액", body)
    sales_year = f"20{m.group(1)}" if m else ""
    table = next((t for t in soup.find_all("table") if "매출액" in text(t)), None)
    if table is None:
        return [], {}, as_of, sales_year
    # 표는 단지마다 두 줄이다(2026-10-18 확인): 윗줄 = 단지 유형·이름·조성년도·지정면적·입주업체·종업원·매출액·관리기관, 아랫줄 = 산업용지 면적.
    # 유형·이름·관리기관 칸은 여러 줄에 걸치므로(rowspan) 격자로 펼친 뒤 열 자리로 읽는다. 아랫줄은 이름 칸이 윗줄과 같은 요소다.
    grid = expand(table)
    keys = ["group", "name", "built", "area_k_m2", "firms", "employees", "sales_eok", "agency"]
    rows, total, prev_name, last = [], {}, None, None
    for g in grid:
        if len(g) < 8:
            continue
        el = {k: g[i] for i, k in enumerate(keys)}
        val = {k: (text(e) if e is not None else "") for k, e in el.items()}
        if not num(val["area_k_m2"]):                 # 머리 줄
            prev_name = None
            continue
        if prev_name is not None and el["name"] is prev_name:   # 아랫줄 = 산업용지
            if last is not None:
                last["industrial_k_m2"] = num(val["area_k_m2"])
            prev_name = None
            continue
        rec = {k: val[k] for k in keys}
        for k in NUMS[:-1]:
            rec[k] = num(rec[k])
        rec["group"] = re.sub(r"\s*\(\d+\)\s*$", "", rec["group"]).replace(" ", "")
        rec["name"] = rec["name"].replace(" ", "") if re.fullmatch(r"[가-힣](\s[가-힣])+", rec["name"]) else rec["name"]
        rec["industrial_k_m2"] = ""
        if rec["name"].startswith("계"):
            total = rec
        else:
            rows.append(rec)
        last, prev_name = rec, el["name"]
    return rows, total, as_of, sales_year


def main(argv: list[str]) -> int:
    if argv[:1] == ["--html"]:                        # 저장해 둔 화면으로 읽기(시험용)
        return save(*parse(Path(argv[1]).read_text(encoding="utf-8")))
    rp = urllib.robotparser.RobotFileParser("https://www.investkorea.org/robots.txt")
    try:
        rp.read()
        if not rp.can_fetch(UA, URL):
            print("robots.txt 가 막음 — 받지 않음"); return 0
    except Exception as e:  # noqa: BLE001
        print(f"robots.txt 읽기 실패 {e} — 받지 않음"); return 0
    try:
        r = requests.get(URL, headers={"User-Agent": UA}, timeout=40)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"받기 실패 {e}"); return 0
    return save(*parse(r.text))


def save(rows: list[dict], total: dict, as_of: str, sales_year: str) -> int:
    print(f"단지 {len(rows)}곳 · 기준 {as_of} · 매출 {sales_year}년")
    for x in rows:
        print("  ", x)
    bad = [k for k in NUMS if total.get(k) and sum(float(x[k] or 0) for x in rows) != float(total[k])]
    if not rows or not total or bad or not as_of:
        print(f"::warning::표를 제대로 읽지 못함(계 행 {bool(total)}, 합 안 맞는 칸 {bad}, 기준 {as_of!r}) — 저장하지 않음")
        return 0
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=HEAD, lineterminator="\n"); w.writeheader()
    for x in rows:
        w.writerow({k: x.get(k, "") for k in HEAD})
    dest = OUT / "overview.csv"
    if dest.exists() and dest.read_text(encoding="utf-8") == buf.getvalue():
        print("값이 그대로 — 다시 쓰지 않음"); return 0
    dest.write_text(buf.getvalue(), encoding="utf-8")
    meta = {"as_of": as_of, "sales_year": sales_year, "source": "KOTRA 대구 투자환경 누리집 「전체 산업단지 현황」", "url": URL,
            "fetched": date.today().isoformat(), "total": {k: total[k] for k in NUMS},
            "note": "단지 행 합 = 표의 계 행(칸마다 확인). 면적 천㎡, 매출액 억 원. 관리기관 칸은 표 그대로(괄호 안은 담당 부서)."}
    (OUT / "overview.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("저장: data/complexes/overview.csv, overview.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
