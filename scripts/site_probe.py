#!/usr/bin/env python3
"""소스 추가 전 확인용: robots.txt 와 첫 화면의 메뉴·게시판 링크를 찍는다(첫 화면 1회, 그 밖의 쪽은 열지 않는다).
이 세션 환경은 외부 사이트가 막혀 있어 GitHub Actions(site_probe.yml)로 돌리고 로그로 본다.
사용: python3 scripts/site_probe.py <url> [--render]
"""
import re, sys
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 daitda-note-bot/1.0 (+https://note.daitda.co.kr)"


def main():
    url = sys.argv[1]
    render = "--render" in sys.argv
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    r = requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=20)
    print(f"== robots.txt ({r.status_code}) ==")
    print(r.text[:3000] if r.ok else "(없음)")
    path = urlparse(url).path or "/"
    for line in r.text.splitlines():
        if re.match(r"(?i)disallow:\s*/\s*$", line.strip()):
            print(f"!! robots 가 전체 차단(Disallow: /). 첫 화면 외 수집 불가")
    html = ""
    if render:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(user_agent=UA)
            pg.goto(url, wait_until="networkidle", timeout=60000); html = pg.content(); b.close()
    else:
        rr = requests.get(url, headers={"User-Agent": UA}, timeout=30); print(f"== {url} ({rr.status_code}, {len(rr.text)} bytes) =="); html = rr.text
    soup = BeautifulSoup(html, "html.parser")
    print(f"== title: {soup.title.get_text(strip=True) if soup.title else ''}")
    seen = set()
    print("== 링크 (내부, 텍스트 - 주소) ==")
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"]); text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))[:40]
        if urlparse(href).netloc != urlparse(url).netloc or href in seen or not text: continue
        seen.add(href); print(f"{text} - {href}")
    print(f"== 링크 {len(seen)}개")
    if "--dump" in sys.argv:   # 표·선택 상자·스크립트 속 주소까지: 통계표 화면이 어떻게 그려지는지 볼 때
        for i, sel in enumerate(soup.find_all("select")[:12]):
            opts = [o.get_text(strip=True) for o in sel.find_all("option")]
            print(f"== select[{i}] name={sel.get('name') or sel.get('id')} ({len(opts)}개): {' | '.join(opts[:40])}")
        for i, tb in enumerate(soup.find_all("table")[:15]):
            cap = tb.find("caption"); rows = tb.find_all("tr")
            print(f"== table[{i}] caption={cap.get_text(strip=True) if cap else ''} rows={len(rows)}")
            for tr in rows[:4]:
                print("   " + " | ".join(re.sub(r"\s+", " ", c.get_text(" ", strip=True))[:30] for c in tr.find_all(["th", "td"])[:10]))
        urls = sorted(set(re.findall(r"""['"]([^'"]*?\.(?:do|json|xml|csv|xlsx?)(?:\?[^'"]*)?)['"]""", html)))
        print(f"== 스크립트·속성 속 주소 {len(urls)}개: " + " | ".join(urls[:60]))
        for i, sc in enumerate([x for x in soup.find_all("script") if x.string and re.search(r"ajax|fetch|XMLHttpRequest|\.do", x.string)][:6]):
            print(f"== script[{i}] 앞 600자: " + re.sub(r"\s+", " ", sc.string)[:600])


if __name__ == "__main__":
    main()
