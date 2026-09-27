#!/usr/bin/env python3
"""소스 추가 전 확인용: robots.txt 와 첫 화면의 메뉴·게시판 링크를 찍는다(첫 화면 1회, 그 밖의 쪽은 열지 않는다).
이 세션 환경은 외부 사이트가 막혀 있어 GitHub Actions(site_probe.yml)로 돌리고 로그로 본다.
사용: python3 scripts/site_probe.py <url> [--render] [--dump] [--text] [--raw]
--text: 운영자가 준 기사·공지 한 쪽의 제목·날짜·본문 글자만 찍는다(robots.txt 가 그 경로를 막으면 본문은 찍지 않는다). 수집기가 아니라 한 번 읽기용.
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
        if "--raw" in sys.argv:   # XML·JSON 응답(오픈API)처럼 파싱하지 않고 앞부분을 그대로 볼 때
            print(f"== raw (Content-Type {rr.headers.get('Content-Type', '')}) ==\n" + rr.text[:3000])
    soup = BeautifulSoup(html, "html.parser")
    print(f"== title: {soup.title.get_text(strip=True) if soup.title else ''}")
    seen = set()
    print("== 링크 (내부, 텍스트 - 주소) ==")
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"]); text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))[:40]
        if urlparse(href).netloc != urlparse(url).netloc or href in seen or not text: continue
        seen.add(href); print(f"{text} - {href}")
    print(f"== 링크 {len(seen)}개")
    if "--text" in sys.argv:   # 기사·공지 한 쪽 읽기: 메타 → 본문(가장 글이 많은 덩어리)
        blocked = any(re.match(r"(?i)disallow:\s*(\S+)", l.strip()) and path.startswith(re.match(r"(?i)disallow:\s*(\S+)", l.strip()).group(1).rstrip("*")) for l in r.text.splitlines() if r.ok and re.match(r"(?i)disallow:\s*\S", l.strip()))
        for k in ("og:title", "og:description", "article:published_time", "article:modified_time", "og:site_name", "author"):
            m = soup.find("meta", attrs={"property": k}) or soup.find("meta", attrs={"name": k})
            if m and m.get("content"):
                print(f"== meta {k}: {m['content'][:300]}")
        if blocked:
            print("!! robots.txt 가 이 경로를 막아 본문은 찍지 않는다"); return
        for t in soup.find_all(["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]):
            t.decompose()
        cands = soup.find_all(["article", "div", "section"])
        best = max(cands, key=lambda e: len(re.sub(r"\s", "", e.get_text(" ", strip=True))) if len(e.find_all(["div", "section", "article"])) < 40 else 0, default=soup)
        text = re.sub(r"[ \t]+", " ", best.get_text("\n", strip=True))
        text = re.sub(r"\n{2,}", "\n", text)
        print(f"== 본문({len(text):,}자, 앞 8,000자) ==\n" + text[:8000])
        return
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
