#!/usr/bin/env python3
"""수성알파시티 입주기업·대경ICT산업협회 회원사 명단 → data/ict_firms/ (운영자 지시 2026-10-21
'알파시티와 대경 ICT협회 기업을 조사해서 … 영남권의 판교가 가능한지 평가해보자').

1) 수성알파시티 기업현황(alphacity.or.kr/boardList?type=1, 35쪽) — 미국 러너에서 HTTP 403(해외 차단)이라
   인터넷 보관소(web.archive.org) 사본을 읽는다. CDX 목록에서 쪽마다 가장 최근 사본을 고르고, 없으면 '/web/2026id_/' 로 가장 가까운 사본.
   열: 기업명·산업분야·사업분야(대표자 열은 읽지 않는다 — import_alphacity.parse 재사용) → data/ict_firms/alphacity.csv
2) 대경ICT산업협회 회원사(dgict.org/member/?mpage=1~, robots.txt 허용) — 목록의 등급·회사명과
   상세 페이지의 홈페이지 주소만(대표자·전화는 읽지 않는다) → data/ict_firms/dgict_members.csv
요청 사이 1초. 실패는 로그만 남기고 건너뛴다. 사용: python3 scripts/fetch_ict_firms.py [--no-alpha] [--no-dgict] [--no-detail]
"""
from __future__ import annotations

import csv
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from import_alphacity import parse as alpha_parse  # noqa: E402

OUT = ROOT / "data" / "ict_firms"
UA = {"User-Agent": "Mozilla/5.0 (compatible; daitda-note/1.0; +https://daitda.co.kr)"}
LIST = "https://alphacity.or.kr/boardList?type=1&stx_cd=0&stx=&page={page}"
WB = "https://web.archive.org"


def get(sess: requests.Session, url: str, tries: int = 3) -> requests.Response | None:
    for i in range(tries):
        try:
            r = sess.get(url, headers=UA, timeout=60)
            if r.status_code == 429:
                time.sleep(10 * (i + 1))
                continue
            return r
        except Exception as e:  # noqa: BLE001
            print(f"  실패 {url[:90]}: {str(e)[:80]}")
            time.sleep(3)
    return None


def write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def alphacity(sess: requests.Session) -> list[dict]:
    """쪽 번호 → 보관소 사본(시각) 고르기: CDX 로 boardList?type=1 사본 전부를 보고 쪽마다 가장 최근 것"""
    best: dict[int, str] = {}
    r = get(sess, f"{WB}/cdx/search/cdx?url=alphacity.or.kr/boardList*&output=json&filter=statuscode:200&fl=timestamp,original&limit=5000")
    try:
        rows = r.json()[1:] if r is not None and r.status_code == 200 and r.text.strip() else []
    except ValueError:
        rows = []
    for ts, orig in rows:
        if "type=1" not in orig:
            continue
        m = re.search(r"[?&]page=(\d+)", orig)
        pg = int(m.group(1)) if m else 1
        if "stx=" in orig and re.search(r"stx=[^&]", orig):   # 검색어가 든 사본은 뺀다
            continue
        if ts > best.get(pg, ("", ""))[0]:
            best[pg] = (ts, orig)
    print(f"[alpha] CDX 사본이 있는 쪽 {len(best)}개: {sorted(best)[:40]}")
    out, last, page = [], 35, 1
    while page <= max(last, max(best) if best else 0) and page <= 60:
        if page in best:
            ts, orig = best[page]
            url = f"{WB}/web/{ts}id_/{orig}"
        else:
            ts, url = "2026", f"{WB}/web/2026id_/{LIST.format(page=page)}"
        r = get(sess, url)
        got, total, l = alpha_parse(r.text) if r is not None and r.status_code == 200 else ([], 0, 0)
        if page == 1 and l:
            last = l
        snap = re.search(r"/web/(\d{8})", r.url).group(1) if r is not None and re.search(r"/web/(\d{8})", r.url) else ts[:8]
        print(f"  {page}/{last}쪽 HTTP {r.status_code if r is not None else '-'} {len(got)}곳 · 사본 {snap}")
        for g in got:
            out.append({"회사명": g["회사명"], "산업분야": g["업종"], "사업분야": g["사업내용"], "쪽": page, "사본": snap})
        page += 1
        time.sleep(1.5)
    seen, uniq = set(), []
    for x in out:
        k = re.sub(r"\(주\)|㈜|주식회사|\s", "", x["회사명"])
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    print(f"[alpha] {len(out)}행 → 중복 뺀 {len(uniq)}곳")
    return uniq


def dgict(sess: requests.Session, detail: bool) -> list[dict]:
    out, page, last = [], 1, 1
    while page <= last and page <= 40:
        r = get(sess, f"https://dgict.org/member/?mpage={page}")
        if r is None or r.status_code != 200:
            print(f"  {page}쪽 실패")
            break
        soup = BeautifulSoup(r.text, "html.parser")
        if page == 1:
            nums = [int(m.group(1)) for a in soup.find_all("a", href=True) for m in [re.search(r"mpage=(\d+)", a["href"])] if m]
            last = max(nums + [1])
        n0 = len(out)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = re.match(r"https://dgict\.org/member/([^/?#]+)/?$", href)
            if not m:
                continue
            txt = a.get_text(" ", strip=True)
            grade = next((g for g in ("협회장", "수석부회장", "명예회장", "운영이사", "부회장사", "이사사", "사무총장", "부사무총장", "감사", "정회원", "특별회원", "준회원") if txt.startswith(g)), "")
            name = txt[len(grade):].strip() if grade else (txt or unquote(m.group(1)))
            if not name:
                name = unquote(m.group(1))
            out.append({"회사명": name, "등급": grade, "상세": href})
        print(f"  {page}/{last}쪽 {len(out) - n0}곳")
        page += 1
        time.sleep(1)
    seen, uniq = set(), []
    for x in out:
        if x["상세"] not in seen:
            seen.add(x["상세"])
            uniq.append(x)
    if detail:
        for i, x in enumerate(uniq, 1):
            r = get(sess, x["상세"])
            hp = ""
            if r is not None and r.status_code == 200:
                t = BeautifulSoup(r.text, "html.parser").find("table")
                for tr in (t.find_all("tr") if t else []):
                    th, td = tr.find("th"), tr.find("td")
                    if th and td and "홈페이지" in th.get_text():
                        hp = td.get_text(" ", strip=True)
                    if th and td and "등급" in th.get_text() and not x["등급"]:
                        x["등급"] = td.get_text(" ", strip=True)
            x["홈페이지"] = hp
            if i % 25 == 0:
                print(f"  상세 {i}/{len(uniq)}")
            time.sleep(1)
    print(f"[dgict] {len(uniq)}곳")
    return uniq


def main(argv: list[str]) -> int:
    sess = requests.Session()
    today = date.today().isoformat()
    if "--no-alpha" not in argv:
        rows = alphacity(sess)
        if rows:
            for x in rows:
                x["기준일"] = today
            write(OUT / "alphacity.csv", ["회사명", "산업분야", "사업분야", "쪽", "사본", "기준일"], rows)
    if "--no-dgict" not in argv:
        rows = dgict(sess, "--no-detail" not in argv)
        if rows:
            for x in rows:
                x["기준일"] = today
            write(OUT / "dgict_members.csv", ["회사명", "등급", "홈페이지", "상세", "기준일"], rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
