#!/usr/bin/env python3
"""소스 추가 전 확인용: robots.txt 와 첫 화면의 메뉴·게시판 링크를 찍는다(첫 화면 1회, 그 밖의 쪽은 열지 않는다).
이 세션 환경은 외부 사이트가 막혀 있어 GitHub Actions(site_probe.yml)로 돌리고 로그로 본다.
사용: python3 scripts/site_probe.py <url> [--render] [--dump] [--text] [--raw] [--xhr [--click 글자1,글자2@2] [--body N]]
--xhr: 브라우저로 열어 화면이 숫자를 받아 오는 내부 요청(XHR·fetch)의 주소·방식·보낸 값·응답 앞 600자를 찍는다.
  --click 은 연 뒤 그 글자가 든 요소를 차례로 누른다(지역·메뉴 고르기). 화면 하나 확인용이지 수집기가 아니다.
--text: 운영자가 준 기사·공지 한 쪽의 제목·날짜·본문 글자만 찍는다(robots.txt 가 그 경로를 막으면 본문은 찍지 않는다). 수집기가 아니라 한 번 읽기용.
"""
import time, re, sys
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"


def main():
    url = sys.argv[1]
    render = "--render" in sys.argv
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    r = None
    for _ in range(4):   # 간헐적 연결 시간 초과: 다시 시도
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=40); break
        except requests.RequestException as e:
            print(f"  robots.txt 다시 시도: {str(e)[:120]}"); time.sleep(10)
    if r is None:
        print("!! robots.txt 를 받지 못함"); return
    print(f"== robots.txt ({r.status_code}) ==")
    print(r.text[:3000] if r.ok else "(없음)")
    path = urlparse(url).path or "/"
    agent = ""   # User-agent: * 묶음만 본다(특정 봇만 막은 줄은 우리와 무관)
    for line in r.text.splitlines():
        m = re.match(r"(?i)user-agent:\s*(\S+)", line.strip())
        if m: agent = m.group(1); continue
        if agent == "*" and re.match(r"(?i)disallow:\s*/\s*$", line.strip()):
            print(f"!! robots 가 전체 차단(Disallow: /). 첫 화면 외 수집 불가")
    html = ""
    if "--xhr" in sys.argv:
        return xhr(url)
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
    if "--dump" in sys.argv:   # 검색 폼·입력 이름·쪽 넘김 함수(행 클릭형 게시판의 검색·쪽 인자를 알아낼 때)
        for i, f in enumerate(soup.find_all("form")[:6]):
            ins = [(x.get("name") or x.get("id") or "", x.get("type") or x.name) for x in f.find_all(["input", "select"]) if (x.get("name") or x.get("id"))]
            print(f"== form[{i}] method={f.get('method')} action={f.get('action')} inputs={ins[:20]}")
        fns = sorted(set(re.findall(r"(?:href|onclick)=[\"']javascript:([A-Za-z_]\w*)\(([^)]*)\)", html)))[:20]
        print(f"== javascript: 호출 {len(fns)}개: " + " | ".join(f"{a}({b[:30]})" for a, b in fns))
        for m in re.finditer(r"function\s+(fn_?[Pp]age\w*|goPage\w*|fn_?[Ss]earch\w*|page\w*)\s*\(([^)]*)\)\s*\{(.{0,300})", html, re.S):
            body3 = re.sub(r"\s+", " ", m.group(3))[:300]
            print(f"== function {m.group(1)}({m.group(2)}): {body3}")
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
        if len(re.sub(r"\s", "", text)) < 200:   # 큰 틀 안에 본문이 있어 '글 덩어리'를 못 고른 화면: body 전체 글자
            text = re.sub(r"[ \t]+", " ", (soup.body or soup).get_text("\n", strip=True))
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
            if len(rows) > 1:   # 첫 데이터 행의 HTML(링크·제목이 어떻게 들었는지)
                print("   html: " + re.sub(r"\s+", " ", str(rows[1]))[:1200])
        urls = sorted(set(re.findall(r"""['"]([^'"]*?\.(?:do|json|xml|csv|xlsx?)(?:\?[^'"]*)?)['"]""", html)))
        print(f"== 스크립트·속성 속 주소 {len(urls)}개: " + " | ".join(urls[:60]))
        for i, sc in enumerate([x for x in soup.find_all("script") if x.string and re.search(r"ajax|fetch|XMLHttpRequest|\.do", x.string)][:6]):
            print(f"== script[{i}] 앞 600자: " + re.sub(r"\s+", " ", sc.string)[:600])


def xhr(url):
    from playwright.sync_api import sync_playwright
    clicks = []
    nbody = 600   # 응답 본문을 찍는 길이(--body N 으로 늘림: action.do 식으로 본문을 JSON 으로 주는 화면)
    if "--body" in sys.argv:
        nbody = int(sys.argv[sys.argv.index("--body") + 1])
    if "--click" in sys.argv:
        i = sys.argv.index("--click")
        clicks = [c.strip() for c in (sys.argv[i + 1] if i + 1 < len(sys.argv) else "").split(",") if c.strip()]
    seen = set()

    def on_resp(resp):
        req = resp.request
        if req.resource_type not in ("xhr", "fetch"): return
        key = (req.method, req.url, req.post_data or "")
        if key in seen: return
        seen.add(key)
        ct = resp.headers.get("content-type", "")
        try: body = resp.text()
        except Exception: body = ""
        print(f"\n## {req.method} {resp.status} {req.url}\n   type={ct[:60]} len={len(body)}")
        if req.post_data: print(f"   post={req.post_data[:600]}")
        print("   body=" + re.sub(r"\s+", " ", body[:nbody]))

    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(user_agent=UA, viewport={"width": 1400, "height": 1000})
        pg.on("response", on_resp)
        print(f"== XHR: {url}")
        for t in range(3):
            try:
                pg.goto(url, wait_until="networkidle", timeout=90000); break
            except Exception as e:
                print(f"  다시 시도: {str(e)[:120]}"); pg.wait_for_timeout(10000)
        pg.wait_for_timeout(3000)
        print(f"== title: {pg.title()}  최종 주소: {pg.url}")
        for c in clicks:
            print(f"\n==== 누름: {c}")
            try:
                nth = 0   # '글자@2' 면 두 번째 일치, 없으면 보이는 첫 요소(숨은 전체 메뉴에 같은 글자가 있을 때)
                m = re.match(r"^(.*)@(\d+)$", c)
                if m: c, nth = m.group(1), int(m.group(2)) - 1
                loc = pg.get_by_text(c, exact=True) if pg.get_by_text(c, exact=True).count() else pg.get_by_text(c, exact=False)
                vis = [k for k in range(loc.count()) if loc.nth(k).is_visible()]
                el = loc.nth(nth) if m else (loc.nth(vis[0]) if vis else loc.first)
                print(f"   일치 {loc.count()}개(보이는 것 {len(vis)}개) → {nth + 1 if m else (vis[0] + 1 if vis else 1)}번째")
                try: el.click(timeout=5000)
                except Exception: el.evaluate("e => e.click()")   # 접힌 메뉴 속 항목
                pg.wait_for_load_state("networkidle", timeout=30000); pg.wait_for_timeout(3000)
                print(f"   주소: {pg.url}")
            except Exception as e:
                print(f"   못 누름: {str(e)[:200]}")
        soup = BeautifulSoup(pg.content(), "html.parser")
        if "--text" in sys.argv:   # 화면에 보이는 글자와 그림(글이 그림인 안내 쪽)·프레임 주소
            sp = BeautifulSoup(pg.content(), "html.parser")   # 접힌(숨긴) 글자까지
            for t in sp.find_all(["script", "style", "noscript"]): t.decompose()
            vis = (sp.body or sp).get_text("\n", strip=True)
            vis = re.sub(r"\n{2,}", "\n", re.sub(r"[ \t]+", " ", vis))
            print(f"\n== 화면 글자({len(vis):,}자, 앞 12,000자) ==\n" + vis[:12000])
            imgs = [(urljoin(pg.url, i.get("src", "")), i.get("alt", "")) for i in soup.find_all("img") if i.get("src")]
            print(f"== 그림 {len(imgs)}개: " + " | ".join(f"{u} [{a[:60]}]" for u, a in imgs[:60]))
            for f in pg.frames[1:]:
                try: print(f"== 프레임 {f.url}\n" + re.sub(r"\s+", " ", f.inner_text("body"))[:3000])
                except Exception: pass
        if "--pages" in sys.argv:   # 목록 화면: pageIndex=2..N 을 차례로 열어 화면 글자만 찍는다(쪽 사이 2초)
            n = int(sys.argv[sys.argv.index("--pages") + 1])
            for k in range(2, n + 1):
                u = re.sub(r"([?&])pageIndex=\d+", "", pg.url).rstrip("?&")
                u = u + ("&" if "?" in u else "?") + f"pageIndex={k}"
                for t in range(3):
                    try:
                        pg.goto(u, wait_until="networkidle", timeout=90000); break
                    except Exception as e:
                        print(f"  {k}쪽 다시 시도: {str(e)[:120]}"); pg.wait_for_timeout(10000)
                sp = BeautifulSoup(pg.content(), "html.parser")   # 접힌(숨긴) 답까지: HTML 글자
                for t in sp.find_all(["script", "style", "noscript"]): t.decompose()
                vis = (sp.body or sp).get_text("\n", strip=True)
                vis = re.sub(r"\n{2,}", "\n", re.sub(r"[ \t]+", " ", vis))
                print(f"\n==== {k}쪽 {u} ({len(vis):,}자)\n" + vis[:20000])
                pg.wait_for_timeout(2000)
        links = sorted({urljoin(pg.url, a["href"]) for a in soup.find_all("a", href=True) if not a["href"].startswith("javascript")})
        print(f"\n== 화면 링크 {len(links)}개: " + " | ".join(links[:120]))
        txt = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        print(f"== 화면 글자 앞 2,000자: {txt[:2000]}")
        b.close()
    print(f"\n== 요청 {len(seen)}개")


if __name__ == "__main__":
    main()
