"""국가법령정보센터 오픈API(law.go.kr/DRF) 실측 — 자치법규 정비 검토용 API 의 실제 인자·태그를 로그로 본다.
저장소를 바꾸지 않는다. 결과는 docs/ordinance/api.md 에 사람이(세션이) 옮긴다."""
from __future__ import annotations

import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests

OC = os.environ.get("LAW_OC", "test").strip() or "test"
BASE = "https://www.law.go.kr/DRF"
UA = "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"


def get(path, **p):
    p.setdefault("OC", OC)
    p.setdefault("type", "XML")
    try:
        r = requests.get(f"{BASE}/{path}", params=p, headers={"User-Agent": UA}, timeout=60)
        time.sleep(0.7)
        return r
    except Exception as e:  # noqa: BLE001
        print("  실패", type(e).__name__, str(e)[:100])
        return None


def tags(xml: bytes, n=60):
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        print("  XML 오류", e, xml[:300])
        return None
    seen = {}
    def walk(el, path):
        p = path + "/" + el.tag
        seen[p] = seen.get(p, 0) + 1
        for c in el:
            walk(c, p)
    walk(root, "")
    for p, c in list(seen.items())[:n]:
        print(f"    {c:5d} {p}")
    return root


def show(title, path, **p):
    print(f"\n===== {title}  {path} {p}")
    r = get(path, **p)
    if r is None:
        return None
    print(f"  HTTP {r.status_code} {len(r.content)}B ctype={r.headers.get('content-type')}")
    print("  앞:", re.sub(r"\s+", " ", r.text[:700]))
    return tags(r.content)


def items(root, item="law"):
    return [{c.tag: (c.text or "").strip() for c in it} for it in root.iter(item)] if root is not None else []


def main():
    ORGS = ["대구광역시", "대구광역시 중구", "대구광역시 동구", "대구광역시 서구", "대구광역시 남구", "대구광역시 북구",
            "대구광역시 수성구", "대구광역시 달서구", "대구광역시 달성군", "대구광역시 군위군", "경상북도 군위군"]
    GUESS = {"6270000": "대구", "3220000": "중구?", "3230000": "동구?", "3240000": "서구?", "3250000": "남구?", "3260000": "북구?",
             "3270000": "수성구?", "3280000": "달서구?", "3290000": "달성군?", "5150000": "군위?", "5270000": "군위?", "3300000": "군위?"}

    root = show("자치법규 검색(대구 지방보조금)", "lawSearch.do", target="ordin", query="대구광역시 지방보조금", display=3)
    its = items(root)
    for it in its[:3]:
        print("  item:", it)
    for code, nm in GUESS.items():
        r = get("lawSearch.do", target="ordin", org=code, display=3)
        if r is None:
            continue
        try:
            rt = ET.fromstring(r.content)
            its2 = items(rt)
            print(f"  org={code}({nm}) totalCnt={rt.findtext('totalCnt')} 첫:", [(i.get('지자체기관명'), i.get('자치법규명')) for i in its2[:2]])
        except ET.ParseError:
            print("  org", code, "XML 오류", r.text[:200])
    for nm in ORGS:
        r = get("lawSearch.do", target="ordin", query=nm, display=3)
        if r is None:
            continue
        try:
            rt = ET.fromstring(r.content)
            print(f"  query={nm} totalCnt={rt.findtext('totalCnt')}", [(i.get('지자체기관명'), i.get('자치법규명')) for i in items(rt)[:3]])
        except ET.ParseError:
            print("  XML 오류")
    # 종류 인자
    for knd in ("30001", "30002", "조례", "규칙"):
        r = get("lawSearch.do", target="ordin", org="6270000", knd=knd, display=2)
        if r is not None:
            try:
                rt = ET.fromstring(r.content)
                print(f"  knd={knd} totalCnt={rt.findtext('totalCnt')}", [(i.get('자치법규종류'), i.get('자치법규명')) for i in items(rt)[:2]])
            except ET.ParseError:
                print("  knd XML 오류")

    if its:
        mst = its[0].get("자치법규일련번호")
        oid = its[0].get("자치법규ID")
        root = show("자치법규 본문", "lawService.do", target="ordin", MST=mst)
        if root is not None:
            print("  글자 앞 2500:", re.sub(r"\s+", " ", " | ".join(t for t in root.itertext() if t.strip()))[:2500])
        show("자치법규 본문(ID)", "lawService.do", target="ordin", ID=oid)

    # 법령 검색: 현행·연혁·이름 바뀐 법·폐지 법
    for q in ("벤처기업육성에 관한 특별법", "벤처기업육성에 관한 특별조치법", "문화재보호법", "공공기관의 개인정보보호에 관한 법률", "지방자치법"):
        for extra in ({}, {"nw": "1"}, {"nw": "2"}, {"nw": "3"}):
            r = get("lawSearch.do", target="law", query=q, display=5, **extra)
            if r is None:
                continue
            try:
                rt = ET.fromstring(r.content)
            except ET.ParseError:
                print("  XML 오류", q)
                continue
            print(f"\n  법령 검색 {q} {extra} total={rt.findtext('totalCnt')}")
            for i in items(rt)[:5]:
                print("   ", {k: i.get(k) for k in ("법령명한글", "법령ID", "법령일련번호", "현행연혁코드", "제개정구분명", "공포일자", "시행일자", "법령구분명")})
    root = show("법령 검색 첫 항목 전체 태그", "lawSearch.do", target="law", query="지방자치법", display=1)
    for i in items(root):
        print("  ", i)
    root = show("법령 본문 지방자치법", "lawService.do", target="law", ID="001706")
    if root is not None:
        n = 0
        for jo in root.iter("조문단위"):
            print("   조문단위:", {c.tag: (c.text or "")[:60] for c in jo if len(c) == 0})
            n += 1
            if n > 4:
                break
    # 연혁·변경이력·연계·위임·해석례
    show("법령 연혁 lsHistory", "lawSearch.do", target="lsHistory", query="지방자치법", display=3)
    show("변경이력 lsHstInf", "lawSearch.do", target="lsHstInf", regDt="20260901", display=3)
    show("조문별 변경이력 lsJoHstInf", "lawService.do", target="lsJoHstInf", ID="001706", JO="002800")
    show("위임법령 lsDelegated", "lawService.do", target="lsDelegated", ID="001706")
    show("연계 lnkOrd(자치법규 기준)", "lawSearch.do", target="lnkOrd", query="대구광역시 지방보조금", display=3)
    show("연계 lnkLs(법령 기준)", "lawSearch.do", target="lnkLs", query="지방자치단체 보조금 관리에 관한 법률", display=3)
    show("연계 lnkLsOrdJo", "lawSearch.do", target="lnkLsOrdJo", knd="", query="지방자치단체 보조금 관리에 관한 법률", display=3)
    show("신구법 oldAndNew", "lawSearch.do", target="oldAndNew", query="지방자치법", display=3)
    show("법령해석례 expc", "lawSearch.do", target="expc", query="조례 위임", display=3)
    show("판례 prec", "lawSearch.do", target="prec", query="조례 무효", display=3)
    print("\n끝")


if __name__ == "__main__":
    main()
