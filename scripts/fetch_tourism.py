#!/usr/bin/env python3
"""한국관광공사 관광빅데이터(한국관광 데이터랩) 지자체 방문자 수 → data/tourism/visitors_monthly.csv (운영자 지시 2026-10-03: 관광 통계).

공공데이터포털 '한국관광공사_관광빅데이터 정보서비스' 오픈API(DataLabService):
  metcoRegnVisitrDDList  광역 지자체 일별 방문자 수(현지인·외지인·외국인)
  locgoRegnVisitrDDList  기초 지자체(시군구) 일별 방문자 수
이동통신 신호로 추정한 값이다(페이지에 '추정치'로 적는다). 대구(광역 코드 27, 시군구 코드 27xxx)만 남기고 달마다 일별 값을 더해
`month, level(광역|기초), code, name, tou_div(현지인|외지인|외국인), visitors, days` 로 저장한다. 값을 만들지 않는다(합계만).
키: 환경변수 DATA_GO_KR_KEY(공공데이터포털 일반 인증키, 이 API 활용신청 필요). 이 세션 환경은 apis.data.go.kr 차단이라 워크플로(tourism.yml)로.
사용: python3 scripts/fetch_tourism.py [--start 2024-01] [--probe] [--refresh 2]
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
from calendar import monthrange
from pathlib import Path
from urllib.parse import unquote

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "tourism"
CSV = OUT / "visitors_monthly.csv"
BASE = "https://apis.data.go.kr/B551011/DataLabService"
FIELDS = ["month", "level", "code", "name", "tou_div", "visitors", "days"]


def call(op: str, key: str, start: str, end: str, page: int, rows: int = 1000) -> tuple[list[dict], int, str]:
    params = {"serviceKey": key, "numOfRows": rows, "pageNo": page, "MobileOS": "ETC", "MobileApp": "daitda", "startYmd": start, "endYmd": end, "_type": "json"}
    try:
        r = requests.get(f"{BASE}/{op}", params=params, timeout=60)
    except Exception as e:  # noqa: BLE001
        return [], 0, f"요청 실패 {e}"
    try:
        j = r.json()
    except ValueError:
        return [], 0, f"HTTP {r.status_code} JSON 아님: {r.text[:300]}"
    body = (j.get("response") or {}).get("body") or {}
    head = (j.get("response") or {}).get("header") or {}
    if head.get("resultCode") not in (None, "0000", "00"):
        return [], 0, f"{head.get('resultCode')} {head.get('resultMsg')}"
    items = (body.get("items") or {}) if isinstance(body.get("items"), dict) else {}
    it = items.get("item") or []
    if isinstance(it, dict):
        it = [it]
    return it, int(body.get("totalCount") or 0), ""


def month_rows(op: str, key: str, ym: str) -> tuple[list[dict], str]:
    y, m = int(ym[:4]), int(ym[5:])
    start, end = f"{y}{m:02d}01", f"{y}{m:02d}{monthrange(y, m)[1]:02d}"
    out, page = [], 1
    while True:
        items, total, err = call(op, key, start, end, page)
        if err:
            return out, err
        out += items
        if not items or len(out) >= total or page > 200:
            break
        page += 1
        time.sleep(0.2)
    return out, ""


def aggregate(ym: str, level: str, items: list[dict]) -> list[dict]:
    acc: dict[tuple, dict] = {}
    for it in items:
        code = str(it.get("signguCode") or it.get("areaCode") or "")
        name = str(it.get("signguNm") or it.get("areaNm") or "")
        if not (code.startswith("27") or "대구" in name):
            continue
        k = (code, name, str(it.get("touDivNm") or it.get("touDivCd") or ""))
        a = acc.setdefault(k, {"month": ym, "level": level, "code": code, "name": name, "tou_div": k[2], "visitors": 0.0, "days": set()})
        try:
            a["visitors"] += float(it.get("touNum") or 0)
        except ValueError:
            pass
        a["days"].add(it.get("baseYmd"))
    return [{**a, "visitors": round(a["visitors"]), "days": len(a["days"])} for a in acc.values()]


def months(start: str) -> list[str]:
    today = dt.date.today()
    y, m = int(start[:4]), int(start[5:])
    out = []
    while (y, m) < (today.year, today.month):
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-01")
    ap.add_argument("--probe", action="store_true", help="첫 달 첫 쪽 응답만 찍기")
    ap.add_argument("--refresh", type=int, default=2, help="이미 받은 달 중 최근 N달은 다시 받기(고침 반영)")
    a = ap.parse_args()
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not key:
        print("[tourism] DATA_GO_KR_KEY 가 없어 끝냄")
        return 0
    key = unquote(key) if "%" in key else key   # 인코딩 키면 풀어서 requests 가 한 번만 인코딩하게
    ms = months(a.start)
    if a.probe:
        last = ms[-1]
        for op in ("metcoRegnVisitrDDList", "locgoRegnVisitrDDList"):
            items, total, err = call(op, key, f"{last.replace('-', '')}01", f"{last.replace('-', '')}03", 1, 20)
            print(f"[probe] {op} {last} 1~3일: total {total}, err {err!r}")
            for it in items[:8]:
                print("   ", json.dumps(it, ensure_ascii=False))
        return 0
    old = list(csv.DictReader(open(CSV, encoding="utf-8"))) if CSV.exists() else []
    have = sorted({r["month"] for r in old})
    redo = set(have[-a.refresh:]) if a.refresh else set()
    todo = [m for m in ms if m not in have or m in redo]
    print(f"[tourism] 달 {len(ms)}개 중 받을 달 {len(todo)}개: {todo[:3]}…{todo[-3:]}")
    new: list[dict] = []
    done = set()
    for ym in todo:
        rows_m = []
        for op, level in (("metcoRegnVisitrDDList", "광역"), ("locgoRegnVisitrDDList", "기초")):
            items, err = month_rows(op, key, ym)
            if err:
                print(f"[tourism] {ym} {op}: {err} — 이 달은 건너뜀")
                rows_m = []
                break
            agg = aggregate(ym, level, items)
            print(f"[tourism] {ym} {level}: 전국 {len(items)}행 → 대구 {len(agg)}행")
            rows_m += agg
        if rows_m:
            new += rows_m
            done.add(ym)
        elif ym == ms[-1] or ym == ms[-2]:
            print(f"[tourism] {ym}: 자료 없음(아직 공개 전일 수 있음)")
    rows = [r for r in old if r["month"] not in done] + new
    rows.sort(key=lambda r: (r["month"], r["level"] != "광역", r["code"], r["tou_div"]))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows({k: r[k] for k in FIELDS} for r in rows)
    meta = {"source": "한국관광공사 관광빅데이터(한국관광 데이터랩) 지자체 방문자 수", "api": BASE, "portal": "https://www.data.go.kr/data/15101972/openapi.do",
            "datalab": "https://datalab.visitkorea.or.kr", "note": "이동통신 데이터로 추정한 방문자 수의 일별 값을 달마다 더한 값(연인원)",
            "months": sorted({r['month'] for r in rows}), "fetched": dt.date.today().isoformat()}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[tourism] {len(rows)}행 → {CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
