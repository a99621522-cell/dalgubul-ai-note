#!/usr/bin/env python3
"""한국산업단지공단 「국가산업단지 산업동향정보」(분기) 대구 행 → data/complex_trend/ (운영자 지적 2026-10-18 '국가산단은 산업단지관리공단에 자료가 있잖아').

전국산업단지현황통계(fetch_complex_stats.py)는 2025년 3분기부터 생산·수출·고용 공표를 멈췄지만, 산단공이 관리하는 국가산업단지는
산업동향조사(분기)로 생산·수출·가동률·고용을 따로 공표한다. 공공데이터포털 파일데이터(키 없이 받음)를 받는다.
같은 내용의 오픈API(15152884, 산업동향조사 통계 조회 서비스)는 공공데이터포털 인증키가 필요해 쓰지 않는다.
  python3 scripts/fetch_national_trend.py --list   # 첨부 id 만
  python3 scripts/fetch_national_trend.py          # 받아 대구 행만 data/complex_trend/<key>_<판>.csv + index.json
전국 원본은 저장하지 않는다. 값은 원본 그대로(단위는 열 이름대로), 평가 없음. 내려받기 함수는 fetch_complex_stats.py 를 그대로 쓴다.
"""
from __future__ import annotations

import argparse, csv, io, json, re, sys, time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_complex_stats import get, ids_in, resolve, fetch_file, decode, OAS, PAGE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "complex_trend"
# 포털 검색(2026-10-18)으로 확인한 「국가산업단지 산업동향정보」 파일데이터 번호
SETS = {"15085891": "production", "15085892": "export", "15085890": "employment", "15085889": "operation",
        "15085894": "firms", "15085888": "operation_detail"}
LABEL = {"production": "생산실적", "export": "수출실적", "employment": "고용현황", "operation": "가동률",
         "firms": "입주업체 현황", "operation_detail": "단지별 가동률 세부내역"}
DEADLINE = time.time() + 45 * 60


def period_of(name: str, text: str) -> str:
    """파일 이름이나 본문의 기준 시점 — '2026년 2분기'·'2026.06'·'20260630' → '2026Q2'."""
    for s in (name, text[:3000]):
        m = re.search(r"(20\d{2}|\d{2})\s*[년.]\s*(\d)\s*/?\s*4?\s*분기", s)
        if m:
            y = int(m.group(1)); y = y + 2000 if y < 100 else y
            return f"{y}Q{m.group(2)}"
        m = re.search(r"(20\d{2})[.\-년\s]*(0[1-9]|1[0-2])(?:[.\-월\s]|\d{2})", s)
        if m:
            return f"{m.group(1)}Q{(int(m.group(2)) - 1) // 3 + 1}"
    return ""


def daegu_rows(text: str) -> tuple[list[str], list[list[str]], int]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return [], [], 0
    head = [h.strip() for h in rows[0]]
    keep = [[c.strip() for c in r] for r in rows[1:] if any(c.strip().startswith(("대구", "달성")) for c in r)]
    return head, keep, len(rows) - 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    sess = requests.Session()
    OUT.mkdir(parents=True, exist_ok=True)
    idx_path = OUT / "index.json"
    index = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"files": []}
    seen = {f["atch"] for f in index["files"]}
    for pk, key in SETS.items():
        atchs: list[str] = []
        live = get(sess, PAGE.format(pk=pk), timeout=60)
        if live is not None and live.status_code == 200:
            atchs += ids_in(live.text)[1]
        doc = get(sess, OAS.format(pk=pk), timeout=60)   # 판마다 남은 uddi → 그 판의 첨부 id(fetch_complex_stats.py 와 같은 길)
        if doc is not None and doc.status_code == 200:
            for uu in list(dict.fromkeys(re.findall(r"uddi:[0-9a-f-]{36}", doc.text))):
                if time.time() > DEADLINE:
                    print("   시간 한도 — 중단"); break
                at = resolve(sess, pk, uu)
                if at:
                    atchs.append(at)
                time.sleep(1)
        atchs = list(dict.fromkeys(atchs))
        print(f"[{pk} {LABEL[key]}] 첨부 id {len(atchs)}개")
        if a.list:
            continue
        for atch in atchs:
            if atch in seen or time.time() > DEADLINE:
                continue
            got = fetch_file(sess, pk, atch)
            if not got:
                continue
            name, raw = got
            text = decode(raw)
            head, rows, total = daegu_rows(text)
            p = period_of(name, text)
            print(f"   {atch} → {name} ({len(raw):,} bytes) 시점 {p or '?'} · 전체 {total}행 · 대구 {len(rows)}행")
            print(f"     열: {head}")
            for r in rows[:4]:
                print(f"     대구: {r}")
            if not rows:
                continue
            dest = OUT / f"{key}_{p or atch}.csv"
            with dest.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f); w.writerow(head); w.writerows(rows)
            index["files"].append({"key": key, "label": LABEL[key], "period": p, "file": dest.name, "orig": name, "atch": atch, "pk": pk, "rows": len(rows)})
            seen.add(atch)
            time.sleep(1.5)
    if not a.list:
        index["files"].sort(key=lambda f: (f["key"], f["period"]))
        index["note"] = "한국산업단지공단 국가산업단지 산업동향정보(공공데이터포털 파일데이터). 대구·달성 이름이 든 행만. 생산·수출·가동률은 제조업 가동업체 조사(포털 안내)."
        idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"저장: {len(index['files'])}개 파일")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
