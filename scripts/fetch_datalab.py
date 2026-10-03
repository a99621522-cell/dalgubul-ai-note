#!/usr/bin/env python3
"""한국관광 데이터랩 「지역별 관광 현황」(로그인 없이 열리는 화면)의 대구 값 → data/tourism/datalab_*.csv (운영자 지시 2026-10-03:
'화면에서 볼 수 있으면 가져오라').

화면(https://datalab.visitkorea.or.kr/datalab/portal/loc/getAreaDataForm.do)이 차트를 그릴 때 부르는 내부 요청
/visualize/getTempleteData.do 를, 브라우저로 화면을 연 뒤 같은 화면 안에서 지역 코드만 대구(27, 구·군 27xxx)로 바꿔 부른다.
  LN_04_01_009         방문자 수(연인원) 추이 — 이동통신, 외부방문자(외지인) 기준, 명. 같은 사람이 여러 날 오면 날마다 센다
  LN_04_01_008_003     업종별 관광소비 추이 — 신용카드, 내국인(현지인+외지인), 천원 (_01 현지인, _02 외지인)
  LN_03_03_058         전국 대비 관광소비 추이 — 지역·전국 소비금액 백만원과 비중 % (_01 현지인, _02 외지인)
화면 안내: '빅데이터 방문자수 및 관광소비금액은 추세 분석으로 활용하고 총량으로 활용은 권장하지 않는다' — 페이지에 그대로 적는다.
2020-01 부터 있고 월간 조회는 한 번에 18개월까지라 12개월씩 나눠 부른다. 값은 받은 그대로(합계·나눗셈 없음).
로그인해야 열리는 메뉴(빅데이터 > 이동통신 지역별 방문자수, 신용카드 지역별 관광지출액)는 다루지 않는다(로그인 뒤 자료 수집 금지).
robots.txt 는 User-agent * 에 /search/ 만 막는다. 요청 사이 0.7초, 매월 한 번(datalab.yml).
사용: python3 scripts/fetch_datalab.py [--full] [--start 2020-01]   (기본: 있는 파일의 마지막 18개월만 다시 받아 덮어씀)
"""
import argparse
import csv
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "tourism"
PAGE = "https://datalab.visitkorea.or.kr/datalab/portal/loc/getAreaDataForm.do"
UA = "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"
SIDO = ("27", "대구광역시")
GUGUN = [("27110", "중구"), ("27140", "동구"), ("27170", "서구"), ("27200", "남구"), ("27230", "북구"),
         ("27260", "수성구"), ("27290", "달서구"), ("27710", "달성군"), ("27720", "군위군")]
GROUPS = {"": "내국인", "_01": "현지인", "_02": "외지인"}
FILES = {
    "visitors": ("datalab_visitors.csv", ["code", "region", "ym", "visitors", "prev_year", "yoy_pct"]),
    "spend": ("datalab_spend.csv", ["code", "region", "ym", "group", "industry", "amount_thousand_won"]),
    "share": ("datalab_spend_share.csv", ["ym", "group", "region_mil_won", "nation_mil_won", "share_pct"]),
}


def ym_add(ym, n):
    y, m = int(ym[:4]), int(ym[4:])
    t = y * 12 + (m - 1) + n
    return f"{t // 12}{t % 12 + 1:02d}"


def load(kind):
    name, fields = FILES[kind]
    p = OUT / name
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(kind, rows, keys):
    name, fields = FILES[kind]
    seen = {}
    for r in rows:
        seen[tuple(r[k] for k in keys)] = r
    out = sorted(seen.values(), key=lambda r: tuple(r[k] for k in keys))
    with (OUT / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)
    print(f"  {name}: {len(out)}행")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="2020-01(또는 --start)부터 모두 다시 받기")
    ap.add_argument("--start", default="2020-01")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    defaults = {}

    def on_req(req):
        if "getTempleteData" in req.url and req.post_data and "BASE_YM2=" in req.post_data:
            m = re.search(r"BASE_YM2=(\d{6})", req.post_data)
            if m: defaults.setdefault("end", m.group(1))

    old = {k: load(k) for k in FILES}
    new = {k: [] for k in FILES}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(user_agent=UA)
        pg.on("request", on_req)
        pg.goto(PAGE, wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(3000)
        if "Login" in pg.url:
            print("!! 로그인 화면으로 넘어감 — 받지 않는다"); b.close(); return 0
        end = defaults.get("end")
        if not end:
            print("!! 화면 기본 조회 끝 달을 못 찾음 — 건너뜀"); b.close(); return 0
        start = a.start.replace("-", "")
        if not a.full and old["visitors"]:
            start = max(start, ym_add(end, -17))
        print(f"== 조회 {start} ~ {end} (화면 기본 끝 달)")

        def call(code, name, qid, tab, y1, y2):
            body = {"SGG_CD": code, "SGG_NM": name, "BASE_YM1": y1, "BASE_YM2": y2, "tabDiv": tab, "srchAreaDate": "1",
                    "dispYn": "Y", "touDivCd": "2", "srchTypeText": "", "sggIntgYnFlag": "N", "sggIntgYnFlag2": "N",
                    "yearOverGlobal": "N", "qid": qid, "BASE_YR": "2018", "P_BASE_YM1": ym_add(y1, -12),
                    "P_BASE_YM2": ym_add(y2, -12), "P_GAP": "12"}
            try:
                txt = pg.evaluate("""b => fetch('/visualize/getTempleteData.do', {method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest'},
                    body: new URLSearchParams(b).toString()}).then(r => r.text())""", body)
                time.sleep(0.7)
                return json.loads(txt).get("list") or [] if txt.strip() else []
            except Exception as e:
                print(f"  ! {name} {qid} {y1}-{y2}: {str(e)[:160]}")
                return []

        y1 = start
        while y1 <= end:
            y2 = min(ym_add(y1, 11), end)
            print(f"-- {y1} ~ {y2}")
            for code, nm in [SIDO] + GUGUN:
                full = nm if code == SIDO[0] else f"{SIDO[1]} {nm}"
                for r in call(code, full, "LN_04_01_009", "2", y1, y2):
                    if r.get("BASE_YM") and y1 <= r["BASE_YM"] <= y2:
                        new["visitors"].append({"code": code, "region": nm, "ym": r["BASE_YM"], "visitors": r.get("TOU_NUM"),
                                                "prev_year": r.get("PREV_TOU_NUM"), "yoy_pct": r.get("TOU_NUM_PER")})
                for suf, grp in GROUPS.items():
                    if code != SIDO[0] and suf:
                        continue   # 구·군은 내국인 합계만(요청 수 줄임)
                    for r in call(code, full, "LN_04_01_008_003" + suf, "4", y1, y2):
                        if r.get("BASE_YM") and y1 <= r["BASE_YM"] <= y2:
                            new["spend"].append({"code": code, "region": nm, "ym": r["BASE_YM"], "group": grp,
                                                 "industry": (r.get("DPTR_REGN_NM") or "").strip(), "amount_thousand_won": r.get("TOU_NUM")})
                    if code == SIDO[0]:
                        for r in call(code, full, "LN_03_03_058" + suf, "4", y1, y2):
                            if r.get("BASE_DATE") and y1 <= r["BASE_DATE"] <= y2:
                                new["share"].append({"ym": r["BASE_DATE"], "group": grp, "region_mil_won": r.get("CARD_AMT"),
                                                     "nation_mil_won": r.get("TOTL_CARD_AMT"), "share_pct": r.get("CARD_PER")})
            y1 = ym_add(y2, 1)
        b.close()

    if not any(new.values()):
        print("!! 받은 값 없음 — 파일을 바꾸지 않는다"); return 0

    def num(v):
        if v is None or v == "":
            return ""
        f = float(v)
        return str(int(f)) if f == int(f) else str(f)

    for k in new:
        for r in new[k]:
            for f in r:
                if f not in ("code", "region", "ym", "group", "industry"):
                    r[f] = num(r[f])
    v = save("visitors", old["visitors"] + new["visitors"], ["code", "ym"])
    save("spend", old["spend"] + new["spend"], ["code", "ym", "group", "industry"])
    save("share", old["share"] + new["share"], ["ym", "group"])
    meta = {
        "source": "한국관광공사 한국관광 데이터랩 「지역별 관광 현황」",
        "page": PAGE,
        "fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "latest_ym": max(r["ym"] for r in v) if v else "",
        "notes": [
            "방문자 수: 이동통신 데이터, 외부방문자(외지인) 기준 연인원(같은 사람이 여러 날 방문하면 날마다 집계), 명",
            "관광소비: 신용카드 데이터, 업종별 관광소비액, 천원 / 전국 대비: 백만원",
            "빅데이터 방문자수 및 관광소비금액은 추세 분석으로 활용하고 총량으로 활용은 권장하지 않음(데이터랩 안내)",
        ],
    }
    (OUT / "datalab_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"== 끝: 최근 달 {meta['latest_ym']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
