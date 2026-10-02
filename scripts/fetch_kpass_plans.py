#!/usr/bin/env python3
"""KIAT 과제관리시스템(k-pass.kr) 자료실의 '[대구] ○○년 지역산업진흥계획' 첨부를 받는다(운영자 지시 2026-10-01:
대구 지역산업육성계획을 찾아 사이트에서 내려받게). 시·도가 수립해 KIAT 자료실에 공개한 계획서(공개 자료)만.

1) 자료실 목록을 '대구'로 검색해 제목·등록일·글 번호(potmId)를 찍는다
2) 제목에 '지역산업진흥계획' 이 든 글의 첨부 팝업(/cmm/fileDownPopup.do → fn_egov_downFile(번호) → /cmm/FileDown.do)에서 PDF 를 받는다
   → public/files/regional-plan/daegu-regional-industry-plan-<연도>.pdf (원본 그대로, /policy/ 리포트 페이지에서 내려받기)
     + data/regional_plan/index.json(연도·제목·원 파일명·크기·쪽수·게시일·원문 링크)
   KIAT 자료실의 대구 진흥계획은 2017~2022년분(2022-01-05 게시가 마지막, 2026-10-02 확인). 같은 글의 성과보고서 첨부는 받지 않는다.
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
OUT = ROOT / "public" / "files" / "regional-plan"
INDEX = ROOT / "data" / "regional_plan" / "index.json"
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


def save(resp, potm: str, info: dict) -> dict | None:
    """진흥계획 PDF 만 연도 이름으로 저장한다(성과보고서 등 다른 첨부는 건너뜀)."""
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
    raw = unquote(m.group(1)) if m else ""
    try:   # 서버가 UTF-8 바이트를 그대로 보내 requests 가 latin-1 로 읽는다
        raw = raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    if not resp.content.startswith(b"%PDF") or "진흥계획" not in raw.replace(" ", ""):
        print(f"    건너뜀(진흥계획 PDF 아님): {raw or resp.url[-40:]}")
        return None
    y = re.search(r"(20\d{2})년", raw) or re.search(r"(20\d{2})", info["title"])
    if not y:
        return None
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"daegu-regional-industry-plan-{y.group(1)}.pdf"
    p.write_bytes(resp.content)
    pages = None
    try:
        import subprocess
        out = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True).stdout
        pages = int((re.search(r"Pages:\s+(\d+)", out) or [0, 0])[1]) or None
    except Exception:  # noqa: BLE001
        pass
    print(f"    저장 {p.relative_to(ROOT)} ({len(resp.content):,} bytes, {pages}쪽) ← {raw}")
    return {"year": y.group(1), "title": f"{y.group(1)}년 대구 지역산업진흥계획" + ("(안)" if "(안)" in raw else ""), "orig": raw,
            "file": "/files/regional-plan/" + p.name, "bytes": len(resp.content), "pages": pages,
            "posted": info["date"], "source_title": info["title"], "source_url": info["url"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", default="대구")
    ap.add_argument("--match", default="지역산업진흥계획")
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
    index = {x["year"]: x for x in (json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else [])}
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
            got = save(d, r["potmId"], {**r, "url": url}) if d.ok and ok_type and len(d.content) > 10000 else None
            if got:
                files.append(got)
                index[got["year"]] = got
            else:
                print(f"    파일 아님 {u[:80]} HTTP {d.status_code} {d.headers.get('Content-Type', '')}")
    if index:
        INDEX.parent.mkdir(parents=True, exist_ok=True)
        INDEX.write_text(json.dumps(sorted(index.values(), key=lambda x: x["year"], reverse=True), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[kpass] 진흥계획 {len(index)}건 → {INDEX.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
