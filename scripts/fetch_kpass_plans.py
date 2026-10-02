#!/usr/bin/env python3
"""KIAT 과제관리시스템(k-pass.kr) 자료실의 '[대구] ○○년 지역산업진흥계획' 첨부를 받는다(운영자 지시 2026-10-01:
대구 지역산업육성계획을 찾아 사이트에서 내려받게). 시·도가 수립해 KIAT 자료실에 공개한 계획서(공개 자료)만.

1) 자료실 목록을 '대구'로 검색해 제목·등록일·글 번호(potmId)를 찍는다
2) 제목에 '지역산업진흥계획'·'지역산업육성' 이 든 글의 상세 화면·첨부 팝업에서 내려받기 주소를 찾아 받는다
   → docs/sources/kpass/<글번호>_<파일명> (원본 그대로) + index.json(제목·등록일·원문 링크·파일·크기)
robots.txt 존중(전체 허용 확인), 요청 사이 1초. 이 세션 환경은 k-pass.kr 이 막혀 있어 워크플로(regional_plan.yml)로 돌린다.
사용: python3 scripts/fetch_kpass_plans.py [--keyword 대구] [--match 지역산업진흥계획,지역산업육성] [--max 10]
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "sources" / "kpass"
BASE = "https://www.k-pass.kr"
LIST = BASE + "/site/achive/achiveList.do"
VIEW = BASE + "/site/notice/noticeView.do"
UA = {"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"}
S = requests.Session()
S.headers.update(UA)


def get(url, **kw):
    time.sleep(1)
    r = S.get(url, timeout=60, **kw)
    return r


def list_rows(keyword: str, pages: int = 5) -> list[dict]:
    rows, seen = [], set()
    for page in range(1, pages + 1):
        params = {"menuID": 2, "boardTypeID": "H03", "pageIndex": page, "searchCondition": 0, "searchKeyword": keyword}
        try:
            r = get(LIST, params=params)
        except Exception as e:  # noqa: BLE001
            print(f"[kpass] 목록 실패 p{page}: {e}")
            break
        soup = BeautifulSoup(r.text, "html.parser")
        trs = soup.select("table tbody tr") or soup.find_all("tr")
        n = 0
        for tr in trs:
            html = str(tr)
            ids = re.findall(r"(?:potmId=|fileDownPopup\(\s*'|fn_\w+\(\s*')(\d{3,})", html)
            text = re.sub(r"\s+", " ", tr.get_text(" ", strip=True))
            if not ids or not text:
                continue
            date = (re.search(r"20\d{2}-\d{2}-\d{2}", text) or [""])[0]
            a = tr.find("a")
            title = re.sub(r"\s+", " ", a.get_text(" ", strip=True)) if a and a.get_text(strip=True) else text
            if ids[0] in seen:
                continue
            seen.add(ids[0])
            rows.append({"potmId": ids[0], "title": title, "date": date, "row": text[:160], "onclick": (a.get("onclick") or a.get("href") or "") if a else ""})
            n += 1
        print(f"[kpass] 목록 '{keyword}' p{page}: HTTP {r.status_code}, 행 {n}")
        if n == 0:
            break
    return rows


def scripts_with(soup: BeautifulSoup, base: str, name: str) -> list[str]:
    """페이지·외부 js 에서 함수 정의(name) 주변을 찾아 돌려준다(내려받기 방식 확인용)."""
    out = []
    for s in soup.find_all("script"):
        src = s.get("src")
        body = s.string or ""
        if src:
            try:
                body = get(urljoin(base, src)).text
            except Exception:  # noqa: BLE001
                continue
        i = body.find(name)
        while i >= 0 and len(out) < 4:
            out.append((src or "inline") + ": " + body[max(0, i - 50): i + 900].replace("\n", " "))
            i = body.find(name, i + 1)
    return out


def find_downloads(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a in soup.find_all(["a", "button"]):
        h = (a.get("href") or "") + " " + (a.get("onclick") or "")
        if re.search(r"down|Down|atchFile|fileSn|FileDown", h):
            m = re.search(r"(/[\w/.\-]*[Dd]own[\w/.\-]*\.do[^'\"\s)]*)", h)
            if m:
                urls.append(urljoin(base, m.group(1).replace("&amp;", "&")))
            elif a.get("href", "").startswith(("http", "/")):
                urls.append(urljoin(base, a["href"]))
    for m in re.finditer(r"['\"](/[\w/.\-]*[Dd]own[\w/.\-]*\.do\?[^'\"]+)['\"]", html):
        urls.append(urljoin(base, m.group(1).replace("&amp;", "&")))
    return list(dict.fromkeys(urls))


def save(resp, potm: str) -> dict | None:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
    if not m:   # 이름 머리가 없으면 PDF 일 때만 번호로 저장
        if not resp.content.startswith(b"%PDF"):
            return None
        raw = re.sub(r".*atchFileId=(\d+).*", r"file\1.pdf", resp.url)
    else:
        raw = m.group(1)
    for enc in ("utf-8", "euc-kr"):
        try:
            name = unquote(raw.encode("latin-1").decode(enc)) if "%" not in raw else unquote(raw)
            break
        except Exception:  # noqa: BLE001
            name = unquote(raw)
    name = re.sub(r"[\\/:*?\"<>|]", "_", name).strip()
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{potm}_{name}"
    p.write_bytes(resp.content)
    print(f"    저장 {p.relative_to(ROOT)} ({len(resp.content):,} bytes, {resp.headers.get('Content-Type', '')})")
    return {"file": p.name, "bytes": len(resp.content)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", default="대구")
    ap.add_argument("--match", default="지역산업진흥계획,지역산업육성,진흥계획")
    ap.add_argument("--max", type=int, default=10)
    a = ap.parse_args()
    try:
        rb = get(BASE + "/robots.txt").text
        print("[kpass] robots.txt:", rb.replace("\n", " | ")[:200])
        if re.search(r"(?im)^\s*disallow:\s*/\s*$", rb):
            print("[kpass] robots 가 전체 차단 — 중단")
            return 0
    except Exception as e:  # noqa: BLE001
        print(f"[kpass] 접속 실패: {e}")
        return 0
    rows = list_rows(a.keyword)
    for r in rows:
        print(f"  {r['potmId']} | {r['date']} | {r['title']} | {r['onclick'][:80]}")
    pats = [p for p in a.match.split(",") if p]
    want = [r for r in rows if any(p in r["title"].replace(" ", "") for p in pats)][: a.max]
    print(f"[kpass] 받을 글 {len(want)}개")
    index_p = OUT / "index.json"
    index = json.loads(index_p.read_text(encoding="utf-8")) if index_p.exists() else {}
    shown_js = False
    for r in want:
        url = f"{VIEW}?boardTypeID=H03&menuID=2&potmId={r['potmId']}"
        try:
            v = get(url)
        except Exception as e:  # noqa: BLE001
            print(f"  [{r['potmId']}] 상세 실패: {e}")
            continue
        soup = BeautifulSoup(v.text, "html.parser")
        body = re.sub(r"\s+", " ", (soup.select_one(".view, .board_view, .bbs_view, #contents") or soup).get_text(" ", strip=True))
        print(f"  [{r['potmId']}] 상세 HTTP {v.status_code}: {body[:300]}")
        cands = []
        # 첨부 이름 주변 HTML(내려받기 함수·인자 확인용)
        for m in re.finditer(r".{0,300}\.(?:pdf|hwp|hwpx|zip)\b.{0,200}", v.text, re.I):
            if "FileDown" in m.group(0) or "onclick" in m.group(0) or "href" in m.group(0):
                print("    첨부 HTML:", m.group(0).replace("\n", " ")[:500])
                break
        if not shown_js:
            for js in scripts_with(soup, v.url, "FileDown")[:3]:
                print("    js:", js[:900])
            shown_js = True
        # 목록의 fileDownPopup(potmId, posbId) → /cmm/fileDownPopup.do (common.js)
        pop = f"{BASE}/cmm/fileDownPopup.do?potmId={r['potmId']}&posbId=2"
        try:
            pv = get(pop)
            print(f"    팝업 HTTP {pv.status_code} {len(pv.text)}자")
            # 첨부: <a onclick="fn_egov_downFile('N')">파일명</a> → /cmm/FileDown.do?posbId=2&potmId=..&atchFileId=N&type=BOARD
            for m in re.finditer(r"fn_egov_downFile\('(\d+)'\)\"[^>]*>(?:<i[^>]*></i>)?\s*([^<]+)</a>", pv.text):
                n, fname = m.group(1), m.group(2).strip()
                if re.search(r"\.(pdf|hwp|hwpx|zip|docx?)$", fname, re.I):
                    cands.append(f"{BASE}/cmm/FileDown.do?posbId=2&potmId={r['potmId']}&atchFileId={n}&type=BOARD")
        except Exception as e:  # noqa: BLE001
            print(f"    팝업 실패: {e}")
        cands = list(dict.fromkeys(cands))
        print(f"    내려받기 후보 {len(cands)}: {cands[:5]}")
        files = []
        for u in cands[:6]:
            try:
                d = get(u)
            except Exception as e:  # noqa: BLE001
                print(f"    받기 실패 {u[:80]}: {e}")
                continue
            ok_type = not re.search(r"image/|text/html", d.headers.get("Content-Type", ""))
            got = save(d, r["potmId"]) if d.ok and ok_type and len(d.content) > 10000 else None
            if got:
                files.append(got)
            else:
                print(f"    파일 아님 {u[:80]} HTTP {d.status_code} {d.headers.get('Content-Type', '')}")
        if files:
            index[r["potmId"]] = {"title": r["title"], "date": r["date"], "url": url, "files": files}
    if index:
        OUT.mkdir(parents=True, exist_ok=True)
        index_p.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[kpass] index {len(index)}건 → {index_p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
