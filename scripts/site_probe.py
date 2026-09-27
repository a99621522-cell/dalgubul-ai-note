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


if __name__ == "__main__":
    main()
