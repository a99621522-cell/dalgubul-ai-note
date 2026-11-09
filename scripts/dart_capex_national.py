#!/usr/bin/env python3
"""전국 DART 공시 회사의 신규시설투자·유형자산 양수 공시 — 공장 증설·신설 위치 조사용(운영자 지시 2026-11-09 '증설 조사해봐').

공시검색(list.json, 회사 지정 없이 3개월씩, 수시공시 I·주요사항보고 B)에서 제목이 신규시설투자·유형자산 양수/취득인 공시를 모으고,
기업개황 업종 코드가 --ind 접두어(기본 22·24·25·26·27·28·29·30 — 자동차·부품·전기장비·기계·로봇·소재)인 회사만 원문(document.xml)을 열어
투자 대상·금액·자기자본 대비·목적·기간 줄과 원문에 나온 국내 시군구·해외 국가 이름, '미정' 낱말을 data/dart/capex_national.csv 로.
공시 사실·제목·링크만 — 평가 없음, 사이트는 읽지 않는다. 기업개황은 data/dart_sdv/company_cache.json 을 먼저 쓰고 없으면 받아 덧붙인다.
키: DART_KEY. 사용: python3 scripts/dart_capex_national.py [--months 18] [--ind 28,29,30]
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_dart_future as F  # noqa: E402  get_json·doc_text 재사용
from dart_capex_scan import detail_of  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "dart" / "capex_national.csv"
CACHE = ROOT / "data" / "dart_sdv" / "company_cache.json"
COLS = ["rcept_dt", "corp_code", "name", "corp_cls", "induty", "hq", "report_nm", "kind", "detail", "places", "abroad",
        "undecided", "rcept_no", "url"]
SIDO = ("서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충청북도|충남|충청남도|전북|전라북도|전남|전라남도|"
        "경북|경상북도|경남|경상남도|제주")
PLACE = re.compile(rf"((?:{SIDO})(?:특별시|광역시|특별자치시|특별자치도|도)?\s?[가-힣]{{1,5}}(?:시|군|구))")
ABROAD = re.compile(r"(미국|멕시코|헝가리|폴란드|체코|슬로바키아|스페인|독일|베트남|인도네시아|인도|중국|태국|말레이시아|"
                    r"캐나다|튀르키예|터키|모로코|브라질|일본|우즈베키스탄|사우디|아랍에미리트|필리핀|루마니아|세르비아)")


def kind_of(t: str) -> str:
    t = t.replace(" ", "")
    if "신규시설투자" in t:
        return "신규시설투자"
    if "유형자산" in t and ("양수" in t or "취득" in t):
        return "유형자산 양수"
    return ""


def windows(months: int):
    end = date.today()
    start = end - timedelta(days=months * 31)
    a = start
    while a <= end:
        b = min(a + timedelta(days=89), end)
        yield a.strftime("%Y%m%d"), b.strftime("%Y%m%d")
        a = b + timedelta(days=1)


def main(argv: list[str]) -> int:
    months = int(argv[argv.index("--months") + 1]) if "--months" in argv else 18
    ind = tuple((argv[argv.index("--ind") + 1] if "--ind" in argv else "22,24,25,26,27,28,29,30").split(","))
    if not F.KEY:
        print("DART_KEY 없음")
        return 0
    cache = json.load(open(CACHE, encoding="utf-8")) if CACHE.exists() else {}
    hits = []
    for bgn, end in windows(months):
        for ty in ("I", "B"):
            page = 1
            while True:
                j = F.get_json("list.json", bgn_de=bgn, end_de=end, pblntf_ty=ty, page_no=page, page_count=100)
                time.sleep(0.12)
                if not j:
                    break
                for r in j.get("list", []):
                    k = kind_of(r.get("report_nm", ""))
                    if k and "철회" not in r["report_nm"] and r.get("corp_cls") in ("Y", "K", "N", "E"):
                        hits.append((k, r))
                if page >= int(j.get("total_page") or 1):
                    break
                page += 1
        print(f"  {bgn}~{end}: 누적 {len(hits)}건")
    print(f"제목 일치 {len(hits)}건, 회사 {len({r['corp_code'] for _, r in hits})}곳")
    rows, new = [], 0
    for k, r in hits:
        code = r["corp_code"]
        if code not in cache:
            inf = F.get_json("company.json", corp_code=code) or {}
            time.sleep(0.12)
            cache[code] = {x: inf.get(x, "") for x in ("corp_name", "stock_code", "corp_cls", "adres", "induty_code", "est_dt", "acc_mt")}
            new += 1
        c = cache[code]
        indc = c.get("induty_code") or ""
        row = {"rcept_dt": r["rcept_dt"], "corp_code": code, "name": r.get("corp_name", ""), "corp_cls": r.get("corp_cls", ""),
               "induty": indc, "hq": " ".join((c.get("adres") or "").split()[:2]), "report_nm": " ".join(r["report_nm"].split()),
               "kind": k, "detail": "", "places": "", "abroad": "", "undecided": "", "rcept_no": r["rcept_no"],
               "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}"}
        if indc.startswith(ind):
            t = F.doc_text(r["rcept_no"])
            time.sleep(0.3)
            row["detail"] = detail_of(t)
            row["places"] = " / ".join(dict.fromkeys(re.sub(r"\s", "", p) for p in PLACE.findall(t)))[:120]
            row["abroad"] = " / ".join(dict.fromkeys(ABROAD.findall(t)))[:60]
            row["undecided"] = "미정" if re.search(r"미정|미확정|검토 ?중|확정되지", t) else ""
        rows.append(row)
    if new:
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    rows.sort(key=lambda x: (x["induty"][:2], x["name"], x["rcept_dt"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    sel = [x for x in rows if x["induty"].startswith(ind)]
    print(f"저장 {OUT.relative_to(ROOT)} {len(rows)}건(대상 업종 {len(sel)}건, 기업개황 새로 {new}곳)",
          Counter(x["induty"][:2] for x in sel).most_common())
    for x in sel:
        print(f"{x['rcept_dt']} | {x['name']} | {x['induty']} | {x['hq']} | {x['kind']} | {x['detail'][:120]} | "
              f"{x['places'][:60]} | {x['abroad']} | {x['undecided']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
