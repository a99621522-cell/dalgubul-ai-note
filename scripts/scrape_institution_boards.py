#!/usr/bin/env python3
"""대구 기업지원기관 홈페이지 공고 게시판 → '선정 기업 명단' 공고 → 지원 이력 투입 CSV.

흐름: config/institution_boards.yml 의 기관마다 (1) robots.txt 확인 → (2) 게시판 목록(없으면 첫 화면에서 '공고·공지' 링크 탐색) →
(3) 제목이 title_pattern 에 맞는 글만 열어 본문·첨부(PDF·HWPX·XLSX·HWP)에서 기업명을 뽑는다 →
(4) scripts/data/support/inst_<key>.csv (import_support.py 형식) + data/institution_boards/<key>/ 에 원문 텍스트·색인.

기업명 추출 규칙: 표에서 머리글이 기업명·업체명·회사명·참여기업·선정기업·수행기관 등인 열의 값, 그리고 본문 줄에서 (주)·㈜·주식회사 가 붙은 상호.
기관·대학·병원(config/support_institutions.yml non_company_patterns)은 뺀다. 대표자·연락처는 읽지 않는다. 사업명은 공고 제목, 연도는 게시일.
평가·순위 없음. 이 세션 환경은 기관 사이트 접속이 막혀 있어 GitHub Actions(.github/workflows/institution_boards.yml)에서 브라우저로 돈다.

사용: python3 scripts/scrape_institution_boards.py [--only ttp,dmi] [--max 40]
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib import robotparser

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "institution_boards.yml"
OUT_RAW = ROOT / "data" / "institution_boards"
OUT_SUP = ROOT / "scripts" / "data" / "support"
UA = "Mozilla/5.0 (X11; Linux x86_64) daitda-note-bot/1.0 (+https://note.daitda.co.kr; 공개 공고 수집, 하루 1회)"
TODAY = date.today().isoformat()
NAME_COL = re.compile(r"기업\s*명|업체\s*명|회사\s*명|참여\s*기업|선정\s*기업|수혜\s*기업|지원\s*기업|수행\s*기관|주관\s*기관|신청\s*기관|기업\s*\(?기관\)?\s*명|기관\s*명")
CORP = re.compile(r"(?:\(주\)|㈜|주식회사|\(유\)|유한회사|유한책임회사|농업회사법인)\s*[가-힣A-Za-z0-9&·\-\.]{2,30}|[가-힣A-Za-z0-9&·\-\.]{2,30}\s*(?:\(주\)|㈜|주식회사|\(유\)|유한회사)")
DATE_RE = re.compile(r"(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})")
POST_HREF = re.compile(r"view|read|detail|nttId|boardRead|articleView|seq=|idx=|no=|bbsId|artcl|wr_id|contentsView|BoardView|getBoard", re.I)
BOARD_LINK = re.compile(r"사업\s*공고|공고|공지|알림|선정|결과|모집")

_inst_cfg = yaml.safe_load((ROOT / "config" / "support_institutions.yml").read_text(encoding="utf-8"))
NON_CO = re.compile("|".join(map(re.escape, _inst_cfg["non_company_patterns"])))
CORP_SUFFIX = re.compile(r"\(주\)|㈜|\(유\)|주식회사|유한회사|유한책임회사|합자회사|농업회사법인")

_BROWSER = None
_PW = None


def browser():
    global _BROWSER, _PW
    if _BROWSER is not None:
        return _BROWSER or None
    try:
        from playwright.sync_api import sync_playwright
        _PW = sync_playwright().start()
        _BROWSER = _PW.chromium.launch()
        print("[browser] Chromium 사용")
    except Exception as e:  # noqa: BLE001
        print(f"[browser] 없음({str(e)[:60]}) — requests 만 사용")
        _BROWSER = False
    return _BROWSER or None


def robots_ok(url: str, cache: dict) -> bool:
    host = urlparse(url).netloc
    if host not in cache:
        rp = robotparser.RobotFileParser()
        try:
            r = requests.get(f"https://{host}/robots.txt", headers={"User-Agent": UA}, timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:  # noqa: BLE001
            rp.parse([])
        cache[host] = rp
    return cache[host].can_fetch("*", url)


def get(url: str, sess: requests.Session, use_browser: bool = True) -> tuple[str, bytes, str]:
    """(html 또는 '', 바이너리, content-type). HTML 은 브라우저가 있으면 렌더링 결과."""
    try:
        r = sess.get(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}, timeout=45)
        ct = r.headers.get("Content-Type", "")
        if r.status_code == 200 and "text/html" not in ct:
            return "", r.content, ct
        html = r.text if r.status_code == 200 else ""
        if r.status_code == 200:
            r.encoding = r.apparent_encoding or "utf-8"
            html = r.text
    except Exception as e:  # noqa: BLE001
        print(f"    requests 실패 {url[:80]}: {str(e)[:60]}")
        html, ct = "", "text/html"
    if use_browser and browser():
        page = browser().new_page(user_agent=UA, locale="ko-KR")
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(800)
            html = page.content()
        except Exception as e:  # noqa: BLE001
            print(f"    [browser] 실패 {url[:80]}: {str(e)[:60]}")
        finally:
            page.close()
    return html, b"", ct


def text_of(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        t.decompose()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()))


def names_from_table_rows(rows: list[list[str]]) -> list[str]:
    out = []
    if not rows:
        return out
    header = [c.strip() for c in rows[0]]
    cols = [i for i, h in enumerate(header) if NAME_COL.search(h)]
    for r in rows[1:]:
        for i in cols:
            if i < len(r) and r[i].strip():
                out.append(r[i].strip())
    return out


def names_from_html(html: str) -> tuple[list[str], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    table_names = []
    for tb in soup.find_all("table"):
        rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])] for tr in tb.find_all("tr")]
        table_names += names_from_table_rows(rows)
    text = text_of(html)
    return table_names, [m.group(0).strip() for m in CORP.finditer(text)]


def names_from_pdf(data: bytes) -> tuple[list[str], list[str], str]:
    tn, txt = [], ""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for pg in pdf.pages[:60]:
                txt += (pg.extract_text() or "") + "\n"
                for tb in pg.extract_tables() or []:
                    tn += names_from_table_rows([[(c or "").replace("\n", " ") for c in row] for row in tb if row])
    except Exception as e:  # noqa: BLE001
        txt = f"(PDF 추출 실패 {str(e)[:60]})"
    return tn, [m.group(0).strip() for m in CORP.finditer(txt)], txt


def names_from_xlsx(data: bytes) -> tuple[list[str], list[str], str]:
    tn, txt = [], ""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        for ws in wb.worksheets[:5]:
            rows = [["" if v is None else str(v) for v in r] for r in ws.iter_rows(values_only=True, max_row=2000)]
            rows = [r for r in rows if any(x.strip() for x in r)]
            # 머리글 행 찾기: 이름 열이 있는 첫 행
            for i, r in enumerate(rows[:10]):
                if any(NAME_COL.search(c) for c in r):
                    tn += names_from_table_rows(rows[i:])
                    break
            txt += "\n".join(" | ".join(r) for r in rows[:300]) + "\n"
    except Exception as e:  # noqa: BLE001
        txt = f"(XLSX 추출 실패 {str(e)[:60]})"
    return tn, [m.group(0).strip() for m in CORP.finditer(txt)], txt


def names_from_hwpx(data: bytes) -> tuple[list[str], list[str], str]:
    txt, tn = "", []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for n in z.namelist():
                if n.startswith("Contents/section") and n.endswith(".xml"):
                    xml = z.read(n).decode("utf-8", errors="replace")
                    # 표: <hp:tbl> 안의 <hp:tr>/<hp:tc>
                    for tbl in re.findall(r"<hp:tbl[\s\S]*?</hp:tbl>", xml):
                        rows = []
                        for tr in re.findall(r"<hp:tr>[\s\S]*?</hp:tr>", tbl):
                            cells = [re.sub(r"<[^>]+>", "", tc).strip() for tc in re.findall(r"<hp:tc[\s\S]*?</hp:tc>", tr)]
                            rows.append(cells)
                        tn += names_from_table_rows(rows)
                    txt += re.sub(r"<[^>]+>", " ", xml) + "\n"
    except Exception as e:  # noqa: BLE001
        txt = f"(HWPX 추출 실패 {str(e)[:60]})"
    txt = re.sub(r"[ \t]+", " ", txt)
    return tn, [m.group(0).strip() for m in CORP.finditer(txt)], txt


def names_from_hwp(data: bytes, tmp: Path) -> tuple[list[str], list[str], str]:
    """pyhwp(hwp5txt) 가 있을 때만. 표 구조는 못 살리므로 상호 접미어 패턴만."""
    import subprocess
    tmp.write_bytes(data)
    try:
        txt = subprocess.run(["hwp5txt", str(tmp)], capture_output=True, text=True, timeout=120).stdout
    except Exception as e:  # noqa: BLE001
        txt = f"(HWP 추출 실패 {str(e)[:60]})"
    return [], [m.group(0).strip() for m in CORP.finditer(txt)], txt


def clean_names(names: list[str]) -> list[str]:
    out, seen = [], set()
    for n in names:
        n = re.sub(r"\s+", " ", n).strip(" ·-.,;:")
        if len(n) < 2 or len(n) > 40 or re.fullmatch(r"[\d\W]+", n):
            continue
        if NON_CO.search(n) and not CORP_SUFFIX.search(n):
            continue
        if re.search(r"대표|담당|연락처|전화|이메일|주소|번호|합계|계$|비고|순번|연번|구분|성명|이름", n):
            continue
        k = re.sub(r"\(주\)|㈜|주식회사|\s", "", n).lower()
        if k and k not in seen:
            seen.add(k)
            out.append(n)
    return out


def find_boards(home: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(home).netloc
    out = []
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        href = urljoin(home, a["href"]).split("#")[0]
        if urlparse(href).netloc == host and BOARD_LINK.search(label) and not re.search(r"채용|입찰|낙찰", label) and href not in out and not href.startswith("javascript"):
            out.append(href)
    return out[:6]


def list_posts(board_url: str, html: str, title_re: re.Pattern, excl_re: re.Pattern) -> tuple[list[tuple[str, str, str]], list[str]]:
    """(제목, 주소, 목록의 날짜) 와 다음 페이지 후보."""
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(board_url).netloc
    posts, pages = [], []
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        href = a["href"]
        onclick = a.get("onclick") or ""
        full = urljoin(board_url, href).split("#")[0]
        if re.fullmatch(r"\d{1,2}", label) and (re.search(r"page|Page|pageIndex|pageNo|cpage", href + onclick)):
            pages.append(full if not href.startswith("javascript") else "")
            continue
        if len(label) < 6 or not title_re.search(label) or excl_re.search(label):
            continue
        if href.startswith("javascript") or urlparse(full).netloc != host:
            continue
        if not POST_HREF.search(full) and not re.search(r"\d{3,}", full):
            continue
        tr = a.find_parent("tr") or a.find_parent("li") or a.parent
        d = DATE_RE.search(tr.get_text(" ", strip=True) if tr else "")
        posts.append((label[:120], full, f"{d.group(1)}-{int(d.group(2)):02d}-{int(d.group(3)):02d}" if d else ""))
    return posts, [p for p in pages if p][:6]


def main(argv: list[str]) -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    max_posts = int(argv[argv.index("--max") + 1]) if "--max" in argv else cfg.get("max_posts_per_institution", 40)
    title_re = re.compile(cfg["title_pattern"])
    excl_re = re.compile(cfg["exclude_title"])
    sess = requests.Session()
    robots: dict = {}
    OUT_SUP.mkdir(parents=True, exist_ok=True)
    grand = 0
    for inst in cfg["institutions"]:
        if only and inst["key"] not in only:
            continue
        key, name = inst["key"], inst["name"]
        raw = OUT_RAW / key
        raw.mkdir(parents=True, exist_ok=True)
        print(f"\n== {name} ({inst['home']})")
        if not robots_ok(inst["home"], robots):
            print("  robots.txt 가 첫 화면을 막음 — 건너뜀")
            continue
        boards = list(inst.get("boards") or [])
        if not boards:
            html, _, _ = get(inst["home"], sess)
            boards = find_boards(inst["home"], html)
            print(f"  첫 화면에서 찾은 게시판 {len(boards)}개: {boards}")
        seen_posts, found = set(), []
        for b in boards:
            if not robots_ok(b, robots):
                print(f"  robots 차단: {b}")
                continue
            queue, visited = [b], set()
            while queue and len(visited) < cfg.get("max_pages_per_board", 4):
                url = queue.pop(0)
                if url in visited:
                    continue
                visited.add(url)
                html, _, _ = get(url, sess)
                if not html:
                    continue
                posts, pages = list_posts(url, html, title_re, excl_re)
                print(f"  목록 {url[:90]} → 후보 글 {len(posts)}개, 다음 페이지 {len(pages)}개")
                for t, u, d in posts:
                    if u not in seen_posts:
                        seen_posts.add(u)
                        found.append((t, u, d))
                queue += [p for p in pages if p not in visited]
                time.sleep(1)
        rows, index = [], []
        for t, u, d in found[:max_posts]:
            if not robots_ok(u, robots):
                continue
            html, _, _ = get(u, sess)
            if not html:
                continue
            body = text_of(html)
            dm = DATE_RE.search(body)
            post_date = d or (f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}" if dm else "")
            year = post_date[:4]
            tn, ln = names_from_html(html)
            att_txt = ""
            soup = BeautifulSoup(html, "html.parser")
            atts = []
            for a in soup.find_all("a", href=True):
                href = urljoin(u, a["href"])
                label = a.get_text(" ", strip=True)
                if re.search(r"\.(pdf|hwpx?|xlsx?)(\?|$)", href, re.I) or re.search(r"\.(pdf|hwpx?|xlsx?)$", label, re.I) or re.search(r"fileDown|download|FileDown|atchFile", href, re.I):
                    atts.append((label or Path(urlparse(href).path).name, href))
            for label, href in atts[:6]:
                try:
                    r = sess.get(href, headers={"User-Agent": UA, "Referer": u}, timeout=90)
                    ct = r.headers.get("Content-Type", "")
                    cd = r.headers.get("Content-Disposition", "")
                    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
                    fname = requests.utils.unquote(m.group(1)) if m else label
                    data = r.content
                    if r.status_code != 200 or "text/html" in ct or len(data) < 200:
                        continue
                    ext = (re.search(r"\.(pdf|hwpx|hwp|xlsx|xls)$", fname.lower()) or [None, ""])[1] if fname else ""
                    if not ext:
                        ext = "pdf" if data[:4] == b"%PDF" else "hwpx" if data[:2] == b"PK" and b"Contents/" in data[:4000] else "xlsx" if data[:2] == b"PK" else "hwp" if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" else ""
                    if ext == "pdf":
                        a1, a2, at = names_from_pdf(data)
                    elif ext in ("xlsx", "xls"):
                        a1, a2, at = names_from_xlsx(data)
                    elif ext == "hwpx":
                        a1, a2, at = names_from_hwpx(data)
                    elif ext == "hwp":
                        a1, a2, at = names_from_hwp(data, raw / "_tmp.hwp")
                    else:
                        continue
                    tn += a1
                    ln += a2
                    att_txt += f"\n\n### 첨부 {fname} ({ext}, {len(data):,} bytes)\n{at[:20000]}"
                    print(f"    첨부 {fname[:50]} ({ext}) 표 이름 {len(a1)} · 상호 패턴 {len(a2)}")
                except Exception as e:  # noqa: BLE001
                    print(f"    첨부 실패 {href[:70]}: {str(e)[:60]}")
            names = clean_names(tn) or clean_names(ln)
            src_kind = "표" if clean_names(tn) else "상호 패턴"
            fn = raw / (re.sub(r"[^\w가-힣]+", "_", f"{post_date}_{t}")[:80] + ".txt")
            fn.write_text(f"# {t}\n# 출처: {u}\n# 게시일: {post_date} · 받은 날짜: {TODAY}\n# 기업명 {len(names)}개({src_kind}): {', '.join(names[:60])}\n\n{body[:30000]}{att_txt}", encoding="utf-8")
            index.append({"title": t, "url": u, "date": post_date, "names": len(names), "how": src_kind, "file": fn.name})
            print(f"  [{post_date or '날짜?'}] {t[:60]} → 기업명 {len(names)}개({src_kind})")
            for n in names:
                rows.append({"기업명": n, "주소": "", "선정연도": year, "구분": "기관", "지원기관": name, "사업명": t, "지원유형": "선정",
                             "금액": "", "단위": "", "출처": f"{name} 홈페이지 공고", "출처URL": u, "기준일": post_date or TODAY})
            time.sleep(1)
        (raw / "index.json").write_text(json.dumps({"fetched": TODAY, "boards": boards, "posts": index}, ensure_ascii=False, indent=1), encoding="utf-8")
        target = OUT_SUP / f"inst_{key}.csv"
        if rows:
            with open(target, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            print(f"  → {target.relative_to(ROOT)} {len(rows)}행 (글 {len(index)}개)")
        else:
            print(f"  → 기업명이 잡힌 글 없음 (후보 글 {len(found)}개)")
        grand += len(rows)
    if _PW:
        try:
            _BROWSER.close(); _PW.stop()
        except Exception:  # noqa: BLE001
            pass
    print(f"\n완료: 지원 이력 행 {grand}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
