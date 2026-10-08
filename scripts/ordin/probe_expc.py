"""법제처 법령해석례·자치법규 의견제시 실측 — 인자·태그를 로그로만 본다(저장소 변경 없음)."""
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe import get, show, items, tags  # noqa: E402  (probe.py 는 import 때 실측을 돌리지 않게 아래에서 막음)

root = show("해석례 검색(조례)", "lawSearch.do", target="expc", query="조례", display=3)
for it in items(root, "expc"):
    print("  item:", it)
show("해석례 전체 건수", "lawSearch.do", target="expc", display=1)
for extra in ({"inq": "대구광역시"}, {"query": "대구광역시"}, {"search": "2", "query": "대구광역시"}, {"query": "지방자치법 제28조"}):
    r = get("lawSearch.do", target="expc", display=5, **extra)
    if r is not None:
        try:
            rt = ET.fromstring(r.content)
            print(f"\n  expc {extra} total={rt.findtext('totalCnt')}")
            for it in items(rt, "expc")[:5]:
                print("   ", it)
        except ET.ParseError:
            print("  XML 오류", r.text[:200])
its = items(root, "expc")
if its:
    iid = its[0].get("법령해석례일련번호") or its[0].get("id")
    rt = show("해석례 본문", "lawService.do", target="expc", ID=iid)
    if rt is not None:
        for el in rt.iter():
            if el.text and el.text.strip() and len(el) == 0:
                print(f"   <{el.tag}> {re.sub(r'\\s+', ' ', el.text.strip())[:300]}")
# 자치법규 의견제시·해석 후보 target
for t in ("ordinExpc", "ordinOpin", "opinOrd", "elisOpin", "ordinInterp", "lsOpin", "expcOrd", "ordinIntp", "ordinCmt"):
    r = get("lawSearch.do", target=t, query="조례", display=2)
    if r is not None:
        print(f"\n  target={t} HTTP {r.status_code} {re.sub(r'\\s+', ' ', r.text[:250])}")
# 부처 해석(행정규칙 아님) — 중앙부처 1차 해석
for t in ("moelCgmExpc", "molitCgmExpc", "moisCgmExpc", "cgmExpc"):
    r = get("lawSearch.do", target=t, query="조례", display=2)
    if r is not None:
        print(f"\n  target={t} HTTP {r.status_code} {re.sub(r'\\s+', ' ', r.text[:250])}")
# 자치법규정보시스템(ELIS)
for u in ("https://www.elis.go.kr/robots.txt", "https://www.elis.go.kr/", "https://www.moleg.go.kr/robots.txt"):
    try:
        r = requests.get(u, timeout=30, headers={"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"})
        print(f"\n  {u} HTTP {r.status_code} {len(r.content)}B {re.sub(r'\\s+', ' ', r.text[:600])}")
        if u.endswith("elis.go.kr/"):
            for h in sorted(set(re.findall(r'href="([^"]+)"', r.text)))[:120]:
                if any(k in h for k in ("opin", "Opin", "expc", "intp", "case", "Case", "의견", "사례")):
                    print("    링크:", h)
    except Exception as e:  # noqa: BLE001
        print("  실패", u, type(e).__name__, str(e)[:100])
    time.sleep(1)
print("\n끝")
