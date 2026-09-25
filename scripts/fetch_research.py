#!/usr/bin/env python3
"""국내외 연구기관·기업지원기관·컨설팅사·산업협회의 최근 발간물 목록을 받아 data/research/ 에 둔다 (정책제안 리포트의 근거 창고).

사용:
  python3 scripts/fetch_research.py                 # config/research_sources.yml 전부
  python3 scripts/fetch_research.py --only keit,nia # 일부 key
  python3 scripts/fetch_research.py --dry-run       # 접속·RSS 발견만, 저장 안 함
  python3 scripts/fetch_research.py --query 로봇 휴머노이드   # 저장된 목록에서 키워드 검색(리포트 작성 때)

기관마다: rss 주소가 있으면 그것을, 없으면 홈·발간물 페이지에서 RSS 링크를 자동 발견(<link type="application/rss+xml">, /rss·/feed 후보),
그것도 없으면 발간물 목록 페이지의 링크 가운데 날짜가 붙은 것을 항목으로 본다. robots.txt 를 지키고 기관당 요청 5회 이내, 하루 1회.
제목·주소·날짜·요약 첫 300자만 저장한다(원문 본문은 저장하지 않음). 최근 MAX_DAYS 일 안의 항목만.
출력: data/research/<key>.json, data/research/summary.md(기관별 상태·건수·최신 항목 — 어느 기관을 참조할 수 있는지의 조사 결과).
이 세션 환경은 외부 사이트가 막혀 있어 워크플로(.github/workflows/research.yml)가 대신 돈다. 실패는 로그만.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrape_institution_boards import UA, robots_ok  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "research_sources.yml"
OUT = ROOT / "data" / "research"
TODAY = date.today()
MAX_DAYS = 70
MAX_ITEMS = 40
FUTURE = (date.today() + timedelta(days=3)).isoformat()   # 이보다 뒤 날짜는 발간일로 보지 않는다
RSS_CANDIDATES = ["/rss", "/feed", "/rss.xml", "/feed.xml", "/index.xml", "/rss/", "/feed/", "/atom.xml"]
DATE_RE = re.compile(r"(20\d{2})[.\-/년年]\s?(\d{1,2})[.\-/월月]\s?(\d{1,2})")
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_EN = re.compile(r"\b([A-Z][a-z]{2,8})\.?\s+(\d{1,2}),?\s+(20\d{2})\b|\b(\d{1,2})\s+([A-Z][a-z]{2,8})\.?,?\s+(20\d{2})\b")
JUNK = re.compile(r"바로가기|건너뛰기|건더뛰기|메뉴|배너|skip to|본문|로그인|회원가입|sitemap|cookie|다운로드|download|열지않기|더보기|상세보기", re.I)


def get(url: str, sess: requests.Session, timeout: int = 40) -> requests.Response | None:
    try:
        r = sess.get(url, headers={"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"}, timeout=timeout, allow_redirects=True)
        return r if r.status_code == 200 else None
    except Exception as e:  # noqa: BLE001
        print(f"    실패 {url[:80]}: {type(e).__name__} {str(e)[:60]}")
        return None


def parse_date(s: str) -> str:
    if not s:
        return ""
    m = DATE_RE.search(s)
    if m:
        y, mo, d = m.groups()
        try:
            return date(int(y), int(mo), int(d)).isoformat()
        except ValueError:
            return ""
    m = DATE_EN.search(s)
    if m:
        mon, d, y = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(5), m.group(4), m.group(6))
        mi = MONTHS.get(mon[:3].lower())
        if mi:
            try:
                return date(int(y), mi, int(d)).isoformat()
            except ValueError:
                return ""
    try:
        from email.utils import parsedate_to_datetime  # noqa: WPS433
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:  # noqa: BLE001
        pass
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else ""


def recent(d: str) -> bool:
    if not d:
        return True   # 날짜를 못 읽은 항목은 남긴다(최신순 정렬에서 뒤로)
    try:
        return (TODAY - date.fromisoformat(d)).days <= MAX_DAYS
    except ValueError:
        return True


def discover_rss(url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for link in soup.find_all("link", attrs={"type": re.compile(r"rss|atom", re.I)}):
        if link.get("href"):
            out.append(urljoin(url, link["href"]))
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if re.search(r"rss|feed|atom", h, re.I) and not re.search(r"\.(png|jpg|gif)$", h, re.I):
            out.append(urljoin(url, h))
    return list(dict.fromkeys(out))[:5]


def from_feed(feed_url: str, sess: requests.Session) -> list[dict]:
    r = get(feed_url, sess)
    if not r or not r.content:
        return []
    f = feedparser.parse(r.content)
    items = []
    for e in f.entries[:MAX_ITEMS * 2]:
        d = parse_date(e.get("published", "") or e.get("updated", "") or "")
        if not d and e.get("published_parsed"):
            d = time.strftime("%Y-%m-%d", e.published_parsed)
        summary = re.sub(r"<[^>]+>", " ", e.get("summary", "") or "")
        items.append({"title": (e.get("title") or "").strip(), "url": e.get("link", ""), "date": d, "summary": re.sub(r"\s+", " ", summary).strip()[:300]})
    return [i for i in items if i["title"] and recent(i["date"])][:MAX_ITEMS]


def from_list(page_url: str, html: str, item_pat: str | None, org_names: tuple = ()) -> list[dict]:
    """목록 페이지: 링크 글자 + 그 주변 텍스트에서 날짜를 찾는다."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer"]):
        t.decompose()
    pat = re.compile(item_pat) if item_pat else None
    items, seen = [], set()
    for a in soup.find_all("a", href=True):
        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        href = urljoin(page_url, a["href"])
        is_js = href.startswith("javascript") or a["href"].strip() in ("#", "")
        if JUNK.search(title) and re.search(r"fileView|fileDown|download|\.pdf", href, re.I) and not is_js:
            # 첨부 링크만 있고 제목은 글자로만 있는 목록(KDB 등): 같은 칸의 글에서 제목을 뽑는다
            title = block_title(a)
            if not title:
                continue
        if is_js:
            href = page_url + "#" + re.sub(r"\W+", "-", title)[:40]   # 목록이 스크립트로 열리는 사이트: 목록 페이지 주소로 연결
        if len(title) < 8 or href in seen or (not is_js and "#" in href.split("/")[-1]) or JUNK.search(title) or title in org_names:
            continue
        if pat and not pat.search(href + " " + title):
            continue
        node, ctx, d = a, "", ""
        for _ in range(3):
            par = node.parent
            if par is None:
                break
            tm = par.find("time")
            if tm is not None and (tm.get("datetime") or tm.get_text()):
                d = parse_date(tm.get("datetime") or tm.get_text())
            ctx = par.get_text(" ", strip=True)
            if d or DATE_RE.search(ctx) or DATE_EN.search(ctx):
                break
            node = par
        d = d or parse_date(ctx)
        if not d or d > FUTURE:   # 행사 예정일 같은 미래 날짜는 발간일이 아니다
            continue
        seen.add(href)
        prev = items[-1] if items else None
        if prev and is_js and prev["url"].split("#")[0] == href.split("#")[0] and prev["date"] == d and len(title) > 60 and not prev["summary"]:
            prev["summary"] = title[:300]   # 같은 칸의 긴 문장은 앞 항목의 요약(KITA 카드형 목록)
            continue
        items.append({"title": title[:160], "url": href, "date": d, "summary": ""})
    items.sort(key=lambda i: i["date"], reverse=True)
    return [i for i in items if recent(i["date"])][:MAX_ITEMS]


def block_title(a) -> str:
    """첨부 링크가 든 칸(tr·li·div)에서 제목으로 보이는 글자: 날짜·정크 링크 글자를 뺀 가장 긴 조각."""
    node = a
    for _ in range(3):
        node = node.parent
        if node is None:
            return ""
        txt = node.get_text("\n", strip=True)
        if DATE_RE.search(txt) or node.name in ("tr", "li", "article"):
            break
    pieces = [re.sub(r"\s+", " ", x).strip() for x in txt.split("\n")]
    pieces = [x for x in pieces if len(x) >= 8 and not JUNK.search(x) and not DATE_RE.fullmatch(x) and not re.fullmatch(r"[\d.\-/ ]+", x)]
    return max(pieces, key=len)[:160] if pieces else ""


def render_html(url: str) -> str:
    """JS 로 그리는 목록: 브라우저로 연다(워크플로에 playwright 가 있을 때만)."""
    try:
        from scrape_institution_boards import _goto, browser  # noqa: WPS433
        b = browser()
        if not b:
            return ""
        page = b.new_page(user_agent=UA, locale="ko-KR")
        try:
            return page.content() if _goto(page, url) else ""
        finally:
            page.close()
    except Exception as e:  # noqa: BLE001
        print(f"    브라우저 실패 {url[:60]}: {str(e)[:60]}")
        return ""


def read_table(path: Path) -> list[dict]:
    """CSV/XLSX → dict 행 목록 (pandas 있으면 xlsx 도)."""
    import csv as _csv
    if path.suffix.lower() in (".xlsx", ".xls"):
        try:
            import pandas as pd  # noqa: WPS433
            return pd.read_excel(path, dtype=str).fillna("").to_dict("records")
        except Exception as e:  # noqa: BLE001
            print(f"    xlsx 읽기 실패 {path.name}: {str(e)[:60]}")
            return []
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp949", "utf-8"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return []
    return list(_csv.DictReader(txt.splitlines()))


def from_datago(pk: str, sess: requests.Session, days: int = 400) -> list[dict]:
    """공공데이터포털 파일데이터(기관 발간 목록) → 항목. 열 이름은 제목/일자/URL 비슷한 것을 고른다. 갱신이 늦어 최근 400일까지 본다."""
    try:
        import fetch_datago as fd  # noqa: WPS433
    except Exception as e:  # noqa: BLE001
        print(f"    fetch_datago 없음: {e}")
        return []
    try:
        html = fd.get_page(pk, sess)
    except Exception as e:  # noqa: BLE001
        print(f"    포털 페이지 실패 {pk}: {str(e)[:60]}")
        return []
    d = fd.discover(html)
    calls = d["calls"] or [[u] for u in d["uddis"]] or [[x] for x in d["atch"]]
    files: list[Path] = []
    for c in calls[:3]:
        r = fd.try_download(pk, c, sess, d["atch"])
        if r is not None:
            files = fd.save_response(r, pk, hint=next((x for x in c if "." in x), f"{pk}.csv"))
            break
    rows = []
    for f in files:
        if f.suffix.lower() in (".csv", ".xlsx", ".xls"):
            rows += read_table(f)
    if not rows:
        return []
    cols = list(rows[0].keys())
    pick = lambda pats: next((c for c in cols if re.search(pats, str(c))), None)  # noqa: E731
    tcol = pick(r"제목|보고서명|자료명|간행물명|명칭|title") or pick(r"명$")
    dcol = pick(r"발간일|발행일|등록일|게시일|작성일|일자|날짜|date|연월")
    ucol = pick(r"URL|url|주소|링크|원문")
    scol = pick(r"요약|내용|개요|summary")
    if not tcol:
        print(f"    열 이름을 못 골랐다: {cols[:12]}")
        return []
    ycol = pick(r"발간연도|발행연도|발간년도|발행년도|연도|년도|year")
    items = []
    for r in rows:
        title = str(r.get(tcol, "")).strip()
        dt = parse_date(str(r.get(dcol, ""))) if dcol else ""
        if not dt and dcol and re.fullmatch(r"\d{4}", str(r.get(dcol, "")).strip()):
            dt = f"{r[dcol].strip()}-01-01"
        if not dt:
            dt = date_from_title(title, str(r.get(ycol, "")) if ycol else "")
        if dt:
            try:
                if (TODAY - date.fromisoformat(dt)).days > days:
                    continue
            except ValueError:
                pass
        items.append({"title": title[:160], "url": str(r.get(ucol, "")).strip() if ucol else "", "date": dt,
                      "summary": re.sub(r"\s+", " ", str(r.get(scol, "")))[:300] if scol else ""})
    items = [i for i in items if i["title"]]
    items.sort(key=lambda i: i["date"], reverse=True)
    print(f"    포털 {pk}: {len(rows)}행 → 최근 {days}일 {len(items)}건 (열: 제목={tcol}, 일자={dcol}, 연도={ycol}, URL={ucol})")
    return items[:MAX_ITEMS]


def date_from_title(title: str, year_cell: str = "") -> str:
    """일자 열이 없는 발간 목록: 제목의 '2026-6월호'·'(2026-3호)'·'2026년 8월'·연도 열에서 날짜를 추정한다(월을 모르면 1월 1일)."""
    m = re.search(r"(20\d{2})\s*[-.년]\s*(1[0-2]|0?[1-9])\s*월", title) or re.search(r"(20\d{2})\s*[-.]\s*(1[0-2]|0?[1-9])(?:\s*호|\s*월|\)|\]|\s|$)", title)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-01"
    m = re.search(r"\b(20\d{2})\b", title) or re.search(r"(20\d{2})", year_cell)
    return f"{m.group(1)}-01-01" if m else ""


def fetch_org(org: dict, sess: requests.Session, robots: dict) -> dict:
    key, name = org["key"], org["name"]
    print(f"\n== {name} ({key})")
    res = {"key": key, "name": name, "group": org.get("group", ""), "home": org.get("home", ""), "fetched": TODAY.isoformat(), "status": "", "method": "", "items": [], "note": ""}
    reqs, failed = 0, 0
    if org.get("datago"):
        res["items"] = from_datago(str(org["datago"]), sess)
        if res["items"]:
            res["method"] = f"공공데이터포털 {org['datago']}"
    feeds = [] if res["items"] else [u for u in [org.get("rss")] if u] + list(org.get("rss_candidates") or [])
    host_root = f"{urlparse(org.get('home') or org.get('list')).scheme}://{urlparse(org.get('home') or org.get('list')).netloc}"
    feeds += [host_root + c for c in RSS_CANDIDATES[:4]]
    for feed in feeds:
        if reqs >= 7:
            break
        if not robots_ok(feed, robots):
            continue
        items = from_feed(feed, sess)
        reqs += 1
        if items:
            res["items"], res["method"] = items, f"rss({feed[len(host_root):][:40] or '/'})"
            break
    if not res["items"] and not org.get("datago_only"):
        for page in (org.get("lists") or []) + [org.get("list"), org.get("home")]:
            if not page or reqs >= 12 or res["items"]:
                continue
            if not robots_ok(page, robots):
                res["note"] = "robots.txt 차단"
                print("  robots 차단:", page)
                continue
            r = get(page, sess)
            reqs += 1
            if not r:
                failed += 1
                continue
            html = r.text
            if org.get("render") and not from_list(page, html, org.get("item_pattern"), (org["name"], org["name"].split("(")[0].strip())):
                rendered = render_html(page)
                if rendered:
                    html = rendered
            if "sample_links" not in res:   # 진단용: 목록을 못 읽으면 어떤 링크가 있는지 남긴다
                soup = BeautifulSoup(html, "html.parser")
                res["sample_links"] = [(re.sub(r"\s+", " ", a.get_text(" ", strip=True))[:60], urljoin(page, a["href"])[:120])
                                       for a in soup.find_all("a", href=True) if len(a.get_text(strip=True)) >= 10][:40]
                res["page_chars"] = len(html)
                text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
                res["sample_dates"] = [text[max(0, m.start() - 90):m.end() + 20] for m in list(DATE_RE.finditer(text))[:6]]   # 날짜 주변 글(제목이 링크가 아닌 목록 진단)
            for feed in discover_rss(page, html)[:2]:
                if reqs >= 5:
                    break
                items = from_feed(feed, sess)
                reqs += 1
                if items:
                    res["items"], res["method"] = items, f"rss(발견 {feed[:60]})"
                    break
            if res["items"]:
                break
            if page != org.get("home") or not org.get("list"):
                items = from_list(page, html, org.get("item_pattern"), (org["name"], org["name"].split("(")[0].strip()))
                if items:
                    res["items"], res["method"] = items, "목록 페이지"
                    break
    res["status"] = "OK" if res["items"] else ("차단" if res["note"] else ("접속 실패" if failed else "항목 없음"))
    if res["items"]:
        res.pop("sample_links", None); res.pop("page_chars", None); res.pop("sample_dates", None)
    print(f"  → {res['status']} · {res['method']} · {len(res['items'])}건" + (f" · 최신 {res['items'][0]['date']} {res['items'][0]['title'][:40]}" if res["items"] else ""))
    return res


def write_summary(results: list[dict]) -> None:
    L = [f"# 참조 기관 조사 — 최근 발간물 목록 (scripts/fetch_research.py, {TODAY})", "",
         "정책제안 리포트가 근거로 쓰는 기관과 접속 결과. OK = 최근 70일 안 항목을 받음. '항목 없음' 은 페이지는 열렸으나 RSS 도 날짜 붙은 목록도 못 찾은 경우(대개 JS 목록). '차단' 은 robots.txt 가 크롤러를 막아 존중. 실패는 접속 시간 초과·오류.", "",
         "| 구분 | 기관 | 상태 | 방법 | 건수 | 최신 항목 |", "|---|---|---|---|---|---|"]
    for r in sorted(results, key=lambda x: (x["group"], x["name"])):
        latest = f"{r['items'][0]['date']} [{r['items'][0]['title'][:40]}]({r['items'][0]['url']})" if r["items"] else "—"
        L.append(f"| {r['group']} | [{r['name']}]({r['home']}) | {r['status']} | {r['method'] or r['note']} | {len(r['items'])} | {latest} |")
    L += ["", "리포트 작성 때 `python3 scripts/fetch_research.py --query <키워드>` 로 이 목록을 검색한다. 본문 인용은 제목·날짜·링크만, 요약은 첫 300자 참고."]
    (OUT / "summary.md").write_text("\n".join(L), encoding="utf-8")


def query(words: list[str]) -> int:
    pat = re.compile("|".join(re.escape(w) for w in words), re.I)
    hits = []
    for f in sorted(OUT.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for it in d.get("items", []):
            if pat.search(it["title"] + " " + it.get("summary", "")):
                hits.append((it["date"], d["name"], it))
    hits.sort(key=lambda h: (h[0] or "", h[1]), reverse=True)
    print(f"'{' '.join(words)}' 일치 {len(hits)}건 (data/research, 최근 {MAX_DAYS}일)")
    for d, name, it in hits[:40]:
        print(f"  {d or '날짜 없음'}  [{name}] {it['title'][:70]}  {it['url']}")
    return 0


def main(argv: list[str]) -> int:
    if "--query" in argv:
        return query(argv[argv.index("--query") + 1:])
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    dry = "--dry-run" in argv
    sess = requests.Session()
    robots: dict = {}
    results = []
    for org in cfg["sources"]:
        if only and org["key"] not in only:
            continue
        results.append(fetch_org(org, sess, robots))
        time.sleep(1)
    if dry:
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for r in results:
        (OUT / f"{r['key']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    all_results = []
    for f in sorted(OUT.glob("*.json")):   # 이번에 안 돈 기관의 이전 결과도 표에 남긴다
        all_results.append(json.loads(f.read_text(encoding="utf-8")))
    write_summary(all_results)
    ok = sum(1 for r in results if r["status"] == "OK")
    print(f"\n완료: {len(results)}개 기관 중 OK {ok}, 항목 {sum(len(r['items']) for r in results)}건 → data/research/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
