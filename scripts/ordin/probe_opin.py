"""자치법규 의견제시 사례가 공개된 곳 찾기(로그만): ① 국가법령정보센터 오픈API 활용가이드의 target 전체 목록
② law.go.kr·법제처(moleg.go.kr) 화면에서 '의견제시' 낱말이 든 링크 ③ 후보 target 응답 앞부분."""
import re
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"}


def get(u, **kw):
    try:
        r = requests.get(u, headers=UA, timeout=40, **kw)
        time.sleep(1)
        return r
    except Exception as e:  # noqa: BLE001
        print("  실패", u, type(e).__name__, str(e)[:80])
        return None


def links(html, base, words=("의견", "자치법규", "해석", "사례")):
    out = set()
    for m in re.finditer(r'<a[^>]*?(?:href|onclick)="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        t = re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip()
        if any(w in t for w in words):
            out.add((t[:40], m.group(1)[:160]))
    for t, h in sorted(out):
        print(f"   [{t}] {h}")


# ① API 목록
for u in ("https://open.law.go.kr/LSO/openApi/guideList.do", "https://open.law.go.kr/LSO/openApi/guideList.do?htmlName=lawSearch"):
    r = get(u)
    if r is not None:
        print(f"\n== {u} {r.status_code} {len(r.content)}B")
        ts = sorted(set(re.findall(r"target=([A-Za-z]+)", r.text)))
        print("  target:", ts)
        for m in re.finditer(r"([가-힣A-Za-z ·]{2,30}(?:의견|해석|질의|회신)[가-힣A-Za-z ·]{0,30})", r.text):
            print("   ", m.group(1).strip())
        names = re.findall(r'htmlName=([A-Za-z0-9_]+)', r.text)
        print("  htmlName:", sorted(set(names))[:200])
# ② 화면
for u in ("https://www.law.go.kr/LSW/main.html", "https://www.law.go.kr/LSW/ordinMain.do", "https://www.law.go.kr/LSW/expcMain.do",
          "https://www.moleg.go.kr/", "https://www.moleg.go.kr/robots.txt", "https://www.law.go.kr/robots.txt"):
    r = get(u)
    if r is not None:
        print(f"\n== {u} {r.status_code} {len(r.content)}B")
        if u.endswith("robots.txt"):
            print(r.text[:800])
        else:
            links(r.text, u)
            for m in set(re.findall(r"[가-힣 ]{0,15}의견제시[가-힣 ]{0,15}", r.text)):
                print("   글:", m)
# ③ 후보 target
for t in ("ordinOpinion", "opinion", "ordinOpn", "lsOpn", "ordnInterp", "elisOpn", "ordinCase", "moleg", "molegOpn", "ordinCmtt"):
    r = get("https://www.law.go.kr/DRF/lawSearch.do", params={"OC": "test", "target": t, "type": "XML", "query": "조례", "display": 2})
    if r is not None:
        print(f"  target={t} {r.status_code} {re.sub(r'\s+', ' ', r.text[:200])}")
print("끝")
