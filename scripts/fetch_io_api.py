#!/usr/bin/env python3
"""산업연관표를 API 로 받아 scripts/data/io/ 에 놓는다 (한국은행 ECOS Open API 또는 공공데이터포털 API).

사용:
  ECOS_KEY=... python3 scripts/fetch_io_api.py --list                 # ECOS 통계표 목록에서 '산업연관' 표를 찾아 코드·이름 출력(ecos_tables.json 저장)
  ECOS_KEY=... python3 scripts/fetch_io_api.py --stat 0301010 --year 2023   # 그 표의 항목·값을 전부 받아 행렬 xlsx 로 (rows=항목1, cols=항목2)
  ECOS_KEY=... python3 scripts/fetch_io_api.py                        # config/io_sources.yml 의 api.ecos 설정대로(코드가 비어 있으면 목록에서 이름으로 고름)
  DATA_GO_KR_KEY=... python3 scripts/fetch_io_api.py --datago-url "<요청주소>"   # 공공데이터포털 API 전부 받아 datago_<이름>.csv 로, 열 이름을 출력

ECOS 주소 형식: https://ecos.bok.or.kr/api/<서비스>/<인증키>/json/kr/<시작건>/<끝건>/<통계표코드>/<주기>/<시작>/<끝>/<항목1>/<항목2>/...
인증키는 https://ecos.bok.or.kr/api/ 회원가입 → 인증키 신청. 이 세션 환경은 ECOS·포털 접속이 막혀 있어 워크플로(io_tables.yml)가 Secrets 의 키로 대신 돈다.
산업연관표 부문분류표(KSIC 연계)는 API 에 없다 — ECOS 화면에서 xlsx 를 받아 같은 폴더에 넣는다.
실패는 로그만 남기고 종료 코드 0.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "data" / "io"
CFG = ROOT / "config" / "io_sources.yml"
ECOS = "https://ecos.bok.or.kr/api"
PAGE = 10000            # ECOS 한 번 요청 건수 (상한 안쪽)
UA = "daitda-note/1.0 (public data, once a day)"


def ecos(service: str, key: str, *segs: str, start: int = 1, end: int = PAGE) -> list[dict]:
    url = f"{ECOS}/{service}/{key}/json/kr/{start}/{end}/" + "/".join(s for s in segs)
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
        j = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"  요청 실패 {service} {segs[:2]}: {str(e)[:80]}")
        return []
    if "RESULT" in j:
        print(f"  ECOS 응답: {j['RESULT'].get('CODE')} {j['RESULT'].get('MESSAGE', '')[:80]}")
        return []
    body = j.get(service) or {}
    rows = body.get("row") or []
    total = int(body.get("list_total_count") or len(rows))
    if total > end and rows:
        rows += ecos(service, key, *segs, start=end + 1, end=end + PAGE)
    return rows


def list_tables(key: str) -> list[dict]:
    rows = ecos("StatisticTableList", key, "", end=PAGE)
    io = [r for r in rows if re.search(r"산업연관|투입산출|거래표", r.get("STAT_NAME", ""))]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ecos_tables.json").write_text(json.dumps(io, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"통계표 {len(rows)}개 중 산업연관표 관련 {len(io)}개 → {OUT.relative_to(ROOT)}/ecos_tables.json")
    for r in io:
        print(f"  {r.get('STAT_CODE')}  {r.get('STAT_NAME')}  주기 {r.get('CYCLE')}  검색가능 {r.get('SRCH_YN')}  상위 {r.get('P_STAT_CODE')}")
    return io


def fetch_matrix(key: str, stat: str, year: str, name_hint: str = "") -> Path | None:
    items = ecos("StatisticItemList", key, stat)
    grp = {}
    for it in items:
        grp.setdefault(it.get("GRP_CODE"), []).append(it)
    print(f"  항목 그룹: " + ", ".join(f"{g}({len(v)})" for g, v in grp.items()))
    rows = ecos("StatisticSearch", key, stat, "A", year, year)
    if not rows:
        print(f"  {stat} {year}: 자료 없음")
        return None
    rcodes, ccodes, rname, cname, val = [], [], {}, {}, {}
    for r in rows:
        a, b = r.get("ITEM_CODE1", ""), r.get("ITEM_CODE2", "")
        if a not in rname:
            rname[a] = r.get("ITEM_NAME1", ""); rcodes.append(a)
        if b not in cname:
            cname[b] = r.get("ITEM_NAME2", ""); ccodes.append(b)
        try:
            val[(a, b)] = float(r.get("DATA_VALUE") or 0)
        except ValueError:
            pass
    print(f"  {stat} {year}: 값 {len(rows):,}건 · 행 {len(rcodes)} · 열 {len(ccodes)} (예: {rcodes[:3]} / {ccodes[:3]})")
    # 행렬 xlsx: attract.py 가 읽는 형식(1행 제목, 3행 열 코드, 4행 열 이름, 이후 행코드·행이름·값)
    import pandas as pd  # noqa: WPS433
    table = [[f"ECOS {stat} {name_hint} {year} (한국은행 Open API, 받은 날짜 {time.strftime('%Y-%m-%d')})"] + [""] * (len(ccodes) + 1),
             [""] * (len(ccodes) + 2), ["", "부문명"] + ccodes, ["", ""] + [cname[c] for c in ccodes]]
    for a in rcodes:
        table.append([a, rname[a]] + [val.get((a, b), 0.0) for b in ccodes])
    OUT.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w가-힣]+", "_", name_hint)[:40]
    p = OUT / f"ecos_{stat}_{year}_{safe}.xlsx"
    pd.DataFrame(table).to_excel(p, header=False, index=False)
    with (OUT / f"ecos_{stat}_{year}_long.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["item1", "name1", "item2", "name2", "value"])
        for (a, b), v in val.items():
            w.writerow([a, rname[a], b, cname[b], v])
    print(f"  → {p.name}")
    return p


def fetch_datago(url: str, key: str) -> None:
    """공공데이터포털 API: pageNo/numOfRows 로 전부 받아 CSV. 응답 구조가 제각각이라 열 이름을 출력해 다음 단계에서 맞춘다."""
    rows, page = [], 1
    while True:
        sep = "&" if "?" in url else "?"
        u = f"{url}{sep}serviceKey={key}&pageNo={page}&numOfRows=1000&type=json&resultType=json&returnType=json"
        try:
            r = requests.get(u, headers={"User-Agent": UA}, timeout=120)
            j = r.json()
        except Exception as e:  # noqa: BLE001
            print(f"  요청 실패(p{page}): {str(e)[:100]} / 본문: {r.text[:200] if 'r' in dir() else ''}")
            break
        items = None
        for path in (("response", "body", "items", "item"), ("response", "body", "items"), ("data",), ("items",), ("body", "items"), ("list",)):
            cur = j
            for k in path:
                cur = cur.get(k) if isinstance(cur, dict) else None
            if isinstance(cur, list):
                items = cur; break
        if not items:
            print(f"  p{page}: 항목 못 찾음. 응답 앞부분: {json.dumps(j, ensure_ascii=False)[:300]}")
            break
        rows += items
        if len(items) < 1000 or page > 500:
            break
        page += 1
        time.sleep(0.3)
    if not rows:
        return
    name = re.sub(r"[^\w]+", "_", url.split("/")[-1].split("?")[0])[:40] or "api"
    cols = list(dict.fromkeys(k for r in rows for k in r.keys()))
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"datago_{name}.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(f"  {len(rows):,}행 → {p.name} · 열: {cols[:20]}")


def main(argv: list[str]) -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8")) if CFG.exists() else {}
    api = cfg.get("api") or {}
    if "--datago-url" in argv or api.get("datago_url"):
        key = os.environ.get("DATA_GO_KR_KEY", "")
        url = argv[argv.index("--datago-url") + 1] if "--datago-url" in argv else api["datago_url"]
        if not key:
            print("DATA_GO_KR_KEY 없음")
        else:
            print(f"== 공공데이터포털 {url[:80]}")
            fetch_datago(url, key)
    key = os.environ.get("ECOS_KEY", "")
    if not key:
        print("ECOS_KEY 없음 — ECOS 는 건너뜀 (https://ecos.bok.or.kr/api/ 에서 인증키 신청 → Secrets ECOS_KEY)")
        return 0
    if "--list" in argv:
        list_tables(key)
        return 0
    stat = argv[argv.index("--stat") + 1] if "--stat" in argv else (api.get("ecos_stat") or "")
    year = argv[argv.index("--year") + 1] if "--year" in argv else str(api.get("ecos_year") or "2023")
    tables = list_tables(key)
    if not stat:
        pat = api.get("ecos_name_pattern") or r"생산자가격.*(기본부문|기본)|기본부문.*생산자가격"
        cand = [t for t in tables if re.search(pat, t.get("STAT_NAME", "")) and t.get("SRCH_YN") == "Y"]
        if not cand:
            print(f"  이름이 '{pat}' 에 맞는 검색 가능 통계표가 없다. 위 목록에서 코드를 골라 config/io_sources.yml api.ecos_stat 에 적을 것")
            return 0
        for t in cand:
            fetch_matrix(key, t["STAT_CODE"], year, t.get("STAT_NAME", ""))
    else:
        name = next((t.get("STAT_NAME", "") for t in tables if t.get("STAT_CODE") == stat), "")
        fetch_matrix(key, stat, year, name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
