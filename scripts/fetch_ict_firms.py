#!/usr/bin/env python3
"""수성알파시티 입주기업·대경ICT산업협회 회원사 명단 → data/ict_firms/ (운영자 지시 2026-10-21
'알파시티와 대경 ICT협회 기업을 조사해서 … 영남권의 판교가 가능한지 평가해보자').

1) 수성알파시티 기업현황(alphacity.or.kr/boardList?type=1, 35쪽) — 미국 러너에서 HTTP 403(해외 차단)이라
   인터넷 보관소(web.archive.org) 사본을 읽는다. CDX 목록에서 쪽마다 가장 최근 사본을 고르고, 없으면 '/web/2026id_/' 로 가장 가까운 사본.
   열: 기업명·산업분야·사업분야(대표자 열은 읽지 않는다 — import_alphacity.parse 재사용) → data/ict_firms/alphacity.csv
2) 대경ICT산업협회 회원사(dgict.org/member/?mpage=1~, robots.txt 허용) — 목록의 등급·회사명과
   상세 페이지의 홈페이지 주소만(대표자·전화는 읽지 않는다) → data/ict_firms/dgict_members.csv
3) 중소벤처기업부 스마트제조혁신추진단 스마트공장 공급기업(공공데이터포털 15042132, 2,865곳) — 기업명·주소의 시도·시군구만
   (담당자·연락처 열은 버린다, 원본 파일은 저장하지 않는다) → data/ict_firms/smart_factory_suppliers.csv
요청 사이 1초. 실패는 로그만 남기고 건너뛴다. 사용: python3 scripts/fetch_ict_firms.py [--no-alpha] [--no-dgict] [--no-detail] [--no-sf]
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


def smart_factory(sess: requests.Session) -> list[dict]:
    import io
    import zipfile
    from fetch_datago import discover, get_page, try_download
    pk = "15042132"
    try:
        d = discover(get_page(pk, sess))
    except Exception as e:  # noqa: BLE001
        print(f"[sf] 페이지 실패: {e}")
        return []
    calls = d["calls"] or [[u] for u in d["uddis"]] or [[x] for x in d["atch"]]
    for c in calls[:2]:
        try:
            r = try_download(pk, c, sess, d["atch"])
        except Exception as e:  # noqa: BLE001
            print(f"[sf] 받기 실패: {e}")
            continue
        if r is None:
            continue
        data = r.content
        if zipfile.is_zipfile(io.BytesIO(data)):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                data = z.read(next(n for n in z.namelist() if n.lower().endswith(".csv")))
        for enc in ("utf-8-sig", "cp949"):
            try:
                txt = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            continue
        rows = list(csv.DictReader(io.StringIO(txt)))
        if not rows:
            continue
        keys = list(rows[0].keys())
        kn = next((k for k in keys if "기업명" in k or "업체명" in k or "회사" in k), keys[1] if len(keys) > 1 else keys[0])
        ka = next((k for k in keys if "주소" in k or "소재" in k), "")
        print(f"[sf] 열 {keys} → 이름 '{kn}', 주소 '{ka}' (담당자·연락처 열은 버림)")
        out = []
        for x in rows:
            adr = (x.get(ka) or "").split()
            sido = adr[0] if adr else ""
            sgg = adr[1] if len(adr) > 1 else ""
            out.append({"회사명": (x.get(kn) or "").strip(), "시도": sido, "시군구": sgg})
        print(f"[sf] {len(out)}곳")
        return out
    return []


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
    if "--no-sf" not in argv:
        rows = smart_factory(sess)
        if rows:
            for x in rows:
                x["기준일"] = today
            write(OUT / "smart_factory_suppliers.csv", ["회사명", "시도", "시군구", "기준일"], rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
