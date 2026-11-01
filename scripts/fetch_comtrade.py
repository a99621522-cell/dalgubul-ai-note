#!/usr/bin/env python3
"""UN Comtrade 공개 미리보기 API(키 없음)로 한국의 HS 6단위 수출입을 국가별로 받는다.

휴머노이드 부품 수입 대체 조사용(운영자 지시 2026-11-02). 사이트는 이 자료를 읽지 않는다.
- 품목 목록: config/humanoid_hs.yml (부품 묶음 → HS 6단위, 한계 설명)
- 결과: data/humanoid/trade/comtrade_kor.csv (연도·수출입·HS·상대국·금액 USD·순중량 kg·수량)
         data/humanoid/trade/summary.csv (연도·HS 별 수입 합계, 중국·일본·독일·미국 비중, 수출, 무역수지)
- 값은 한국이 Comtrade 에 보고한 값 그대로. HS 6단위는 휴머노이드 전용이 아니라 산업용 전체가 섞인 값이다.

이 세션 환경은 comtradeapi.un.org 접속이 막혀 워크플로(comtrade.yml)가 받는다.
"""
import csv
import json
import os
import sys
import time

import requests
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "humanoid_hs.yml")
OUT = os.path.join(ROOT, "data", "humanoid", "trade")
API = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
UA = {"User-Agent": "daitda.co.kr research (public data)"}
PARTNERS = {0: "세계", 156: "중국", 392: "일본", 276: "독일", 842: "미국", 344: "홍콩",
            490: "대만(기타 아시아)", 757: "스위스", 752: "스웨덴", 380: "이탈리아", 250: "프랑스",
            528: "네덜란드", 826: "영국", 704: "베트남", 764: "태국", 458: "말레이시아", 702: "싱가포르",
            608: "필리핀", 360: "인도네시아", 356: "인도", 40: "오스트리아", 203: "체코", 616: "폴란드"}


def get(params):
    for i in range(5):
        try:
            r = requests.get(API, params=params, headers=UA, timeout=60)
            if r.status_code == 429:
                time.sleep(10 * (i + 1))
                continue
            if r.status_code != 200:
                print(f"  ! HTTP {r.status_code} {params} {r.text[:200]}")
                time.sleep(3)
                continue
            return r.json().get("data") or []
        except Exception as e:  # 무인 실행: 로그만
            print(f"  ! {e}")
            time.sleep(5)
    return None


def main():
    cfg = yaml.safe_load(open(CFG, encoding="utf-8"))
    years = [str(y) for y in cfg["years"]]
    codes = [(g["group"], h) for g in cfg["groups"] for h in g["hs"]]
    os.makedirs(OUT, exist_ok=True)
    rows, misses = [], []
    for grp, hs in codes:
        hs = str(hs).replace(".", "")
        for y in years:
            for flow in ("M", "X"):
                p = {"reporterCode": 410, "period": y, "cmdCode": hs, "flowCode": flow,
                     "includeDesc": "true"}
                if flow == "X":
                    p["partnerCode"] = 0
                data = get(p)
                time.sleep(1.2)
                if data is None:
                    misses.append(f"{hs} {y} {flow}")
                    continue
                n = 0
                for d in data:
                    if d.get("partner2Code") not in (0, None) or d.get("motCode") not in (0, None) \
                            or d.get("customsCode") not in ("C00", None):
                        continue
                    pc = d.get("partnerCode")
                    rows.append({
                        "year": y, "flow": "수입" if flow == "M" else "수출", "group": grp, "hs": hs,
                        "hs_desc": (d.get("cmdDesc") or "")[:120], "partner_code": pc,
                        "partner": PARTNERS.get(pc) or d.get("partnerDesc") or str(pc),
                        "value_usd": d.get("primaryValue") or d.get("cifvalue") or d.get("fobvalue") or "",
                        "netwgt_kg": d.get("netWgt") or "", "qty": d.get("qty") or "",
                        "qty_unit": d.get("qtyUnitAbbr") or "",
                    })
                    n += 1
                print(f"{hs} {y} {flow}: {n}행")
    if not rows:
        print("받은 행 없음 — 저장하지 않음")
        return 1
    cols = list(rows[0].keys())
    with open(os.path.join(OUT, "comtrade_kor.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    # 요약: 연도·HS 별 수입 합계(세계 행), 상대국 비중
    summ = {}
    for r in rows:
        k = (r["year"], r["hs"])
        s = summ.setdefault(k, {"year": r["year"], "group": r["group"], "hs": r["hs"], "hs_desc": r["hs_desc"],
                                "imp": 0, "exp": 0, "cn": 0, "jp": 0, "de": 0, "us": 0, "tw": 0})
        v = float(r["value_usd"] or 0)
        if r["flow"] == "수출" and r["partner_code"] == 0:
            s["exp"] = v
        if r["flow"] == "수입":
            pc = r["partner_code"]
            if pc == 0:
                s["imp"] = v
            elif pc == 156:
                s["cn"] = v
            elif pc == 392:
                s["jp"] = v
            elif pc == 276:
                s["de"] = v
            elif pc == 842:
                s["us"] = v
            elif pc == 490:
                s["tw"] = v
    with open(os.path.join(OUT, "summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "group", "hs", "hs_desc", "import_usd", "export_usd", "balance_usd",
                    "china_pct", "japan_pct", "germany_pct", "usa_pct", "taiwan_pct"])
        for k in sorted(summ):
            s = summ[k]
            imp = s["imp"]
            pct = lambda v: f"{v / imp * 100:.1f}" if imp else ""
            w.writerow([s["year"], s["group"], s["hs"], s["hs_desc"], f"{imp:.0f}", f"{s['exp']:.0f}",
                        f"{s['exp'] - imp:.0f}", pct(s["cn"]), pct(s["jp"]), pct(s["de"]), pct(s["us"]),
                        pct(s["tw"])])
    json.dump({"source": "UN Comtrade public preview API (reporter 410 Korea, annual, HS)",
               "url": API, "fetched": time.strftime("%Y-%m-%d"), "rows": len(rows), "missing": misses},
              open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"저장 {len(rows)}행, 빠짐 {len(misses)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
