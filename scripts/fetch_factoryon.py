#!/usr/bin/env python3
"""팩토리온 현황통계자료실에서 월간 입주업체 파일 받기 (운영자 지시 2026-10-08 '니가 크롤링해').

팩토리온 robots.txt 는 /bbs/ 를 막고 있다. 이 스크립트는 크롤러가 아니라 운영자 지시로 매달 한 번, 공개 자료실의
파일 2개(전국(개별,계획)입주업체현황 · 산단공관할단지내_입주업체리스트)만 받는 내려받기 도구다(목록 1회 + 상세 2회 + 파일 2개).
그 밖의 글·첨부는 열지 않는다. 받은 파일은 저장소에 넣지 않는다(러너 임시 폴더).

사용:
  python3 scripts/fetch_factoryon.py --out /tmp/fo [--month 2026.09] [--probe]
  --probe : 상세 페이지의 링크·스크립트 호출·폼만 찍고 파일은 받지 않는다(구조 확인용)
출력: <out>/(YYYY.MM월말기준)_전국(개별,계획)입주업체현황.<ext>, <out>/(YYYY.MM월말기준)_산단공관할단지내_입주업체리스트.<ext>
      stdout 마지막 줄 'MONTH=YYYY.MM'
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup

BASE = "https://www.factoryon.go.kr"
LIST = BASE + "/bbs/frtblRecsroomBbsList.do"
DETAIL = BASE + "/bbs/frtblRecsroomBbsDetail.do"
UA = "Mozilla/5.0 daitda-note/1.0 (+https://daitda.co.kr; monthly manual download)"
WANT = {"main": "전국(개별,계획)입주업체현황", "kicox": "산단공관할단지내_입주업체리스트"}


def get(s: requests.Session, url: str, **kw) -> requests.Response:
    r = s.get(url, timeout=60, **kw); r.raise_for_status(); return r


def list_rows(s: requests.Session) -> list[dict]:
    html = get(s, LIST).text
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("table tr"):
        a = tr.find("a", href=re.compile(r"fnSelectView\((\d+)\)"))
        if not a:
            continue
        sn = re.search(r"fnSelectView\((\d+)\)", a["href"]).group(1)
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        date = next((t for t in tds if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t)), "")
        rows.append({"sn": sn, "title": a.get_text(strip=True), "date": date})
    # 폼의 숨은 값(상세 보기 POST 에 그대로 보낸다)
    form = soup.find("form", id="searchForm") or soup.find("form", action=re.compile("frtblRecsroomBbsList"))
    hidden = {i.get("name"): i.get("value", "") for i in (form.find_all("input") if form else []) if i.get("name")}
    return rows, hidden


def detail(s: requests.Session, sn: str, hidden: dict) -> BeautifulSoup:
    data = dict(hidden); data.update({"selectBbsSn": sn, "searchBbsMenu": "S", "pageIndex": data.get("pageIndex") or "1"})
    r = s.post(DETAIL, data=data, timeout=60, headers={"Referer": LIST}); r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def probe(soup: BeautifulSoup) -> None:
    print("== title:", soup.title.get_text(strip=True) if soup.title else "")
    for a in soup.find_all("a", href=True):
        t = a.get_text(" ", strip=True)
        if any(k in (a["href"] + t).lower() for k in ("down", "file", "xls", "attach", "atch", "첨부")):
            print("  a:", t[:80], "->", a["href"][:200], {k: v for k, v in a.attrs.items() if k not in ("href", "class")})
    for tag in soup.find_all(attrs={"onclick": True}):
        print("  onclick:", tag.get_text(" ", strip=True)[:60], "->", tag["onclick"][:200])
    for f in soup.find_all("form"):
        print("  form:", f.get("id"), f.get("method"), f.get("action"), [(i.get("name"), i.get("value", "")[:40]) for i in f.find_all("input") if i.get("name")][:12])
    for sc in soup.find_all("script"):
        txt = sc.get_text()
        for m in re.finditer(r"function\s+(fn\w*(?:Down|File|Atch)\w*)\s*\([^)]*\)\s*\{(.{0,500})", txt, re.S):
            print("  script fn:", m.group(1), "::", re.sub(r"\s+", " ", m.group(2))[:400])
        for m in re.finditer(r"[\"'](/[\w/]*(?:down|Down|file|File|atch|Atch)[\w/]*\.do)[\"']", txt):
            print("  script url:", m.group(1))


def find_downloads(soup: BeautifulSoup) -> list[tuple[str, str, dict]]:
    """[(표시 이름, 주소 또는 js 호출, 추가 정보)] — 첨부 파일로 보이는 것만"""
    out = []
    for a in soup.find_all("a", href=True):
        t = a.get_text(" ", strip=True); h = a["href"]
        if re.search(r"\.(xlsx?|zip|csv)\b", t, re.I) or re.search(r"(fileDown|FileDown|atchFile|downFile|fnDown)", h):
            out.append((t, h, dict(a.attrs)))
    for tag in soup.find_all(attrs={"onclick": True}):
        t = tag.get_text(" ", strip=True)
        if re.search(r"\.(xlsx?|zip|csv)\b", t, re.I) or re.search(r"(fileDown|FileDown|atchFile|downFile|fnDown)", tag["onclick"]):
            out.append((t, "javascript:" + tag["onclick"], dict(tag.attrs)))
    return out


def resolve_js(soup: BeautifulSoup, js: str) -> tuple[str, dict] | None:
    """javascript:fnXxx('a','b') 호출을 스크립트 속 함수 본문의 URL 로 바꾼다(GET 주소 + 인자 → 쿼리). 못 하면 None."""
    m = re.match(r"javascript:\s*(\w+)\((.*)\)\s*;?$", js, re.S)
    if not m:
        return None
    fn, args = m.group(1), [a.strip().strip("'\"") for a in re.split(r",(?![^(]*\))", m.group(2)) if a.strip()]
    for sc in soup.find_all("script"):
        txt = sc.get_text()
        fm = re.search(r"function\s+" + re.escape(fn) + r"\s*\(([^)]*)\)\s*\{(.*?)\n\s*\}", txt, re.S)
        if not fm:
            continue
        params = [p.strip() for p in fm.group(1).split(",") if p.strip()]
        body = fm.group(2)
        um = re.search(r"[\"'](/[^\"']+\.do)[\"']", body)
        if not um:
            continue
        url = urljoin(BASE, um.group(1))
        # 폼 필드 대입(예: $("#fileSn").val(fileSn)) 또는 쿼리 문자열 조립
        q = {}
        for pm in re.finditer(r"\$\([\"']#(\w+)[\"']\)\.val\((\w+)\)", body):
            field, var = pm.group(1), pm.group(2)
            if var in params:
                q[field] = args[params.index(var)]
        for pm in re.finditer(r"(\w+)=[\"']?\s*\+\s*(\w+)", body):
            field, var = pm.group(1), pm.group(2)
            if var in params:
                q[field] = args[params.index(var)]
        if not q and params:
            q = {p: a for p, a in zip(params, args)}
        return url, q
    return None


def download(s: requests.Session, url: str, q: dict, dest_base: Path, referer: str) -> Path:
    r = s.post(url, data=q, timeout=300, headers={"Referer": referer}, stream=True) if q else s.get(url, timeout=300, headers={"Referer": referer}, stream=True)
    if r.status_code != 200 or "text/html" in r.headers.get("Content-Type", "") and int(r.headers.get("Content-Length", "0") or 0) < 20000:
        # GET 으로 한 번 더
        r = s.get(url, params=q, timeout=300, headers={"Referer": referer}, stream=True)
    r.raise_for_status()
    cd = r.headers.get("Content-Disposition", "")
    fm = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
    name = unquote(fm.group(1)) if fm else ""
    ext = Path(name).suffix.lower() if name else ""
    if ext not in (".xls", ".xlsx", ".zip", ".csv"):
        ext = ".xlsx"
    dest = dest_base.with_suffix(ext)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            f.write(chunk)
    print(f"  받음 {dest.name} ({dest.stat().st_size:,} bytes, Content-Type {r.headers.get('Content-Type','')}, 원 이름 {name or '-'})")
    return dest


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--month", default="", help="YYYY.MM — 비우면 목록의 최신 글")
    ap.add_argument("--probe", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    s = requests.Session(); s.headers["User-Agent"] = UA
    rows, hidden = list_rows(s)
    print(f"목록 {len(rows)}건:", "; ".join(f"{r['sn']} {r['title']} {r['date']}" for r in rows[:12]))
    picked = {}
    for key, needle in WANT.items():
        cands = [r for r in rows if needle in r["title"].replace(" ", "") and (not a.month or a.month in r["title"])]
        if cands:
            picked[key] = max(cands, key=lambda r: int(r["sn"]))
    if "main" not in picked:
        print("전국 입주업체현황 글을 목록에서 찾지 못함", file=sys.stderr); return 2
    mm = re.search(r"\((\d{4})\.(\d{2})", picked["main"]["title"])
    month = f"{mm.group(1)}.{mm.group(2)}" if mm else a.month
    for key, row in picked.items():
        print(f"[{key}] sn {row['sn']} {row['title']} ({row['date']})")
        time.sleep(1.5)
        soup = detail(s, row["sn"], hidden)
        if a.probe:
            probe(soup); continue
        links = find_downloads(soup)
        print("  첨부 후보:", [(t[:60], h[:120]) for t, h, _ in links])
        got = None
        for t, h, attrs in links:
            if not re.search(r"\.(xlsx?|zip|csv)\b", t, re.I) and len(links) > 1:
                continue
            if h.startswith("javascript:"):
                res = resolve_js(soup, h)
                if not res:
                    print("  js 호출을 주소로 못 바꿈:", h[:120]); continue
                url, q = res
            else:
                url, q = urljoin(BASE, h), {}
            try:
                got = download(s, url, q, out / f"({month}월말기준)_{WANT[key]}", DETAIL)
                break
            except Exception as e:  # noqa: BLE001
                print("  내려받기 실패:", e)
        if not got:
            print(f"  [{key}] 파일을 받지 못함", file=sys.stderr)
            if key == "main":
                return 3
    print(f"MONTH={month}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
