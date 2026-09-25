#!/usr/bin/env python3
"""예산서·사업설명자료 수집기 — config/budget_sources.yml 의 기관 페이지에서 예산·사업설명 첨부를 받아
data/raw/budget/<key>/ 에 저장하고, 본문 텍스트(pdftotext·HWPX)를 data/budget/<key>/<파일>.txt.gz 로 남긴다.
parse: true 인 기관의 올해 '사업설명자료' 본문은 scripts/parse_budget.py 로 읽어 scripts/data/programs_budget_<key>.csv 를 만든다(--parse-only 면 받지 않고 본문만 다시 파싱).

이 세션 환경은 정부 사이트 접속이 막혀 있어 GitHub Actions(.github/workflows/fetch_budget.yml)에서 브라우저(Playwright)로 돈다.
robots.txt 를 지키고, 기관당 요청은 max_files_per_org 이내. 실패는 로그만 남긴다. 평가·해석 없음.

사용: python3 scripts/fetch_budget_docs.py [--only motie,msit] [--no-parse]
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import re
import subprocess
import sys
import time
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrape_institution_boards import UA, browser, _goto, robots_ok, text_of  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "budget_sources.yml"
RAW = ROOT / "data" / "raw" / "budget"
OUT = ROOT / "data" / "budget"
PROGRAMS = ROOT / "scripts" / "data"
TODAY = date.today().isoformat()


def safe(s: str, n: int = 90) -> str:
    return re.sub(r"[^\w가-힣.\-()]+", "_", s).strip("_")[:n] or "file"


def render(url: str) -> tuple[str, str]:
    """브라우저로 열어 HTML 과 최종 주소. 브라우저가 없으면 requests."""
    b = browser()
    if b:
        page = b.new_page(user_agent=UA, locale="ko-KR")
        try:
            if _goto(page, url):
                return page.content(), page.url
        finally:
            page.close()
        return "", url
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=45)
        r.encoding = r.apparent_encoding or "utf-8"
        return (r.text if r.status_code == 200 else ""), r.url
    except Exception as e:  # noqa: BLE001
        print(f"    requests 실패 {url[:80]}: {str(e)[:60]}")
        return "", url


def links_of(html: str, base: str) -> list[tuple[str, str, str]]:
    """(글자, 절대주소, onclick) 목록."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        href = a["href"].strip()
        out.append((label, urljoin(base, href).split("#")[0] if not href.startswith("javascript") else href, a.get("onclick") or ""))
    return out


def download(url: str, referer: str, sess: requests.Session) -> tuple[str, bytes] | None:
    try:
        r = sess.get(url, headers={"User-Agent": UA, "Referer": referer}, timeout=180)
    except Exception as e:  # noqa: BLE001
        print(f"    내려받기 실패 {url[:80]}: {str(e)[:60]}")
        return None
    ct = r.headers.get("Content-Type", "")
    if r.status_code != 200 or "text/html" in ct or len(r.content) < 1000:
        return None
    cd = r.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
    name = requests.utils.unquote(m.group(1)) if m else Path(urlparse(url).path).name
    return name or "download.bin", r.content


def click_download(page_url: str, label: str) -> tuple[str, bytes] | None:
    """자바스크립트 첨부 링크: 글 페이지를 열고 그 글자를 눌러 내려받기를 기다린다."""
    b = browser()
    if not b:
        return None
    page = b.new_page(user_agent=UA, locale="ko-KR", accept_downloads=True)
    try:
        if not _goto(page, page_url):
            return None
        with page.expect_download(timeout=120000) as dl:
            page.get_by_text(label[:50], exact=False).first.click(timeout=8000)
        f = dl.value
        return (f.suggested_filename or label, Path(f.path()).read_bytes())
    except Exception as e:  # noqa: BLE001
        print(f"    클릭 내려받기 실패 {label[:40]}: {str(e)[:60]}")
        return None
    finally:
        page.close()


def kind_of(name: str, data: bytes) -> str:
    n = name.lower()
    if n.endswith(".pdf") or data[:4] == b"%PDF":
        return "pdf"
    if n.endswith(".hwpx") or (data[:2] == b"PK" and b"Contents/" in data[:6000]):
        return "hwpx"
    if n.endswith((".xlsx", ".xls")):
        return "xlsx"
    if n.endswith(".hwp") or data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "hwp"
    if n.endswith(".zip") or data[:2] == b"PK":
        return "zip"
    return ""


def to_text(kind: str, path: Path) -> str:
    try:
        if kind == "pdf":
            return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, timeout=600).stdout
        if kind == "hwpx":
            with zipfile.ZipFile(path) as z:
                parts = [re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", errors="replace")) for n in z.namelist() if n.startswith("Contents/section")]
            return re.sub(r"[ \t]+", " ", "\n".join(parts))
        if kind == "hwp":
            return subprocess.run(["hwp5txt", str(path)], capture_output=True, text=True, timeout=600).stdout
        if kind == "xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            return "\n".join(" | ".join("" if v is None else str(v) for v in r) for ws in wb.worksheets[:10] for r in ws.iter_rows(values_only=True, max_row=5000))
    except Exception as e:  # noqa: BLE001
        return f"(본문 추출 실패: {str(e)[:80]})"
    return ""


def years_in(text: str) -> list[int]:
    """글자에 든 연도. '2026년'·'2026' 은 그대로, '25년'·'‘25' 은 2025."""
    ys = [int(y) for y in re.findall(r"(?<!\d)(20[123]\d)(?!\d)", text)]
    ys += [2000 + int(y) for y in re.findall(r"(?<![\d.])[‘'’]?([123]\d)\s*년", text)]
    return ys


def too_old(text: str, min_year: int) -> bool:
    ys = years_in(text)
    return bool(ys) and max(ys) < min_year


def crawl_org(org: dict, cfg: dict, sess: requests.Session, robots: dict) -> list[dict]:
    key = org["key"]
    link_re = re.compile(cfg["link_pattern"])
    excl_re = re.compile(cfg["exclude_pattern"])
    ext_re = re.compile(rf"\.({cfg['file_ext']})(\?|$)", re.I)
    home_re = re.compile(org["home_pattern"]) if org.get("home_pattern") else None
    raw_dir, out_dir = RAW / key, OUT / key
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    got, seen_pages, files, seen_hrefs = [], set(), 0, set()
    min_year = int(cfg.get("min_year") or 0)
    queue = [(s, 0) for s in org["seeds"]]
    print(f"\n== {org['name']}")
    while queue and files < cfg["max_files_per_org"]:
        url, depth = queue.pop(0)
        if url in seen_pages or len(seen_pages) > 40:
            continue
        seen_pages.add(url)
        if not robots_ok(url, robots):
            print(f"  robots 차단: {url}")
            continue
        html, final = render(url)
        if not html:
            continue
        host = urlparse(final).netloc
        links = links_of(html, final)
        n_match = 0
        for label, href, onclick in links:
            text = f"{label} {href} {onclick}"
            is_file = bool(ext_re.search(href)) or bool(re.search(r"fileDown|FileDown|download|atchFile|fileSn|attach", href + onclick, re.I)) or bool(re.search(r"\.(pdf|hwpx?|xlsx?|zip)\s*$", label, re.I))
            if is_file and (link_re.search(text) or link_re.search(html_title := text_of(html)[:300]) or depth >= 1):
                if excl_re.search(label):
                    continue
                if min_year and too_old(label + " " + href, min_year):
                    continue
                if href.startswith("http") and href in seen_hrefs:
                    continue
                seen_hrefs.add(href)
                if not robots_ok(href if href.startswith("http") else final, robots):
                    continue
                got_file = download(href, final, sess) if href.startswith("http") else click_download(final, label)
                if not got_file:
                    continue
                name, data = got_file
                kind = kind_of(name, data)
                if not kind:
                    continue
                if min_year and too_old(name, min_year):   # 링크 글자에 연도가 없어 받은 뒤에야 옛 자료임을 아는 경우
                    print(f"  옛 자료 건너뜀: {name[:60]}")
                    continue
                name = safe(name)
                (raw_dir / name).write_bytes(data)
                files += 1
                n_match += 1
                items = [(name, data, kind)]
                if kind == "zip":
                    items = []
                    try:
                        with zipfile.ZipFile(io.BytesIO(data)) as z:
                            for zi in z.infolist()[:30]:
                                try:
                                    zname = zi.filename.encode("cp437").decode("cp949")
                                except Exception:  # noqa: BLE001
                                    zname = zi.filename
                                zd = z.read(zi)
                                zk = kind_of(zname, zd)
                                if zk and zk != "zip":
                                    zn = safe(Path(zname).name)
                                    (raw_dir / zn).write_bytes(zd)
                                    items.append((zn, zd, zk))
                    except Exception as e:  # noqa: BLE001
                        print(f"    zip 실패 {name}: {str(e)[:50]}")
                for fn, fd, fk in items:
                    txt = to_text(fk, raw_dir / fn)
                    if txt.strip():
                        with gzip.open(out_dir / (fn + ".txt.gz"), "wt", encoding="utf-8") as gz:
                            gz.write(f"# {fn}\n# 출처: {final}\n# 링크 글자: {label}\n# 받은 날짜: {TODAY}\n\n{txt}")
                    got.append({"file": fn, "kind": fk, "bytes": len(fd), "chars": len(txt), "label": label[:120], "page": final, "url": href if href.startswith("http") else "", "fetched": TODAY})
                    print(f"  받음 {fn[:70]} ({fk}, {len(fd):,} bytes, 본문 {len(txt):,}자) ← {label[:50]}")
                if files >= cfg["max_files_per_org"]:
                    break
                time.sleep(1)
            elif depth < 2 and href.startswith("http") and urlparse(href).netloc == host and href not in seen_pages:
                if link_re.search(label) and not excl_re.search(label):
                    queue.append((href, depth + 1))
                elif depth == 0 and home_re and home_re.search(label):
                    queue.append((href, depth + 1))
        print(f"  {url[:90]} → 링크 {len(links)}개, 파일 {n_match}개, 대기 {len(queue)}")
        if depth == 0 and not n_match and not queue:
            sample = [(l[:24], h[-50:]) for l, h, _ in links if len(l) >= 6][:15]
            print(f"    (단서 없음) 링크 표본: {sample}")
        time.sleep(1)
    (out_dir / "index.json").write_text(json.dumps({"org": org["name"], "fetched": TODAY, "files": got}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  → {org['name']}: 파일 {len(got)}개 (data/budget/{key}/)")
    return got


def parse_programs(org: dict, got: list[dict], cfg: dict) -> None:
    """올해(budget_year) '사업설명자료' 본문 → scripts/data/programs_budget_<key>.csv (여러 권이면 이어 붙이고 volume 열에 파일명).
    사업 DB 원본(programs_<key>.csv)은 건드리지 않는다. 본문은 data/budget/<key>/*.txt.gz 를 읽으므로 원본 PDF 없이도 다시 파싱할 수 있다."""
    import parse_budget  # noqa: WPS433
    key = org["key"]
    year = int(cfg.get("budget_year") or TODAY[:4])
    out_dir = OUT / key
    cands, seen_files = [], set()
    for g in got:
        if g["kind"] != "pdf" or g["chars"] < 20000 or g["file"] in seen_files:
            continue
        seen_files.add(g["file"])
        gz = out_dir / (g["file"] + ".txt.gz")
        if not gz.exists():
            continue
        head = gzip.open(gz, "rt", encoding="utf-8").read(3000)
        label = f"{g['file']} {g['label']}"
        is_desc = re.search(r"사\s*업\s*설\s*명\s*자\s*료", head) or re.search(r"사업\s*설명|공통요구자료", label)
        ys = years_in(label) or years_in(head[:600])
        if is_desc and ys and max(ys) == year:
            cands.append((g, gz))
    if not cands:
        print(f"  [{key}] {year}년 사업설명자료 본문 없음 — programs_budget CSV 생성 안 함")
        return
    rows, cols = [], None
    for g, gz in cands:
        tmp = out_dir / (g["file"] + ".csv")
        try:
            parse_budget.main(str(gz), org.get("ministry"), str(tmp))
        except Exception as e:  # noqa: BLE001
            print(f"  [{key}] 파싱 실패 {g['file'][:50]}: {str(e)[:80]}")
            continue
        for r in csv.DictReader(open(tmp, encoding="utf-8")):
            r["source"] = f"{org['name']} {year}년도 예산 및 기금운용계획 사업설명자료({g['file'][:60]})"
            r["volume"] = g["file"]
            r["source_url"] = g["page"]
            rows.append(r)
            cols = cols or list(r.keys())
        tmp.unlink(missing_ok=True)
    if not rows:
        return
    seen, uniq = set(), []
    for r in rows:
        k = (r.get("code", ""), parse_budget.clean(r.get("name", "")))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    out = PROGRAMS / f"programs_budget_{key}.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows({c: r.get(c, "") for c in cols} for r in uniq)
    print(f"  [{key}] 사업 {len(uniq)}건 → {out.relative_to(ROOT)} (권 {len(cands)})")


def main(argv: list[str]) -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    sess = requests.Session()
    robots: dict = {}
    total = 0
    for org in cfg["organizations"]:
        if only and org["key"] not in only:
            continue
        if "--parse-only" in argv:  # 받은 본문(data/budget/<key>)만 다시 파싱
            ix = OUT / org["key"] / "index.json"
            got = json.loads(ix.read_text(encoding="utf-8"))["files"] if ix.exists() else []
        else:
            got = crawl_org(org, cfg, sess, robots)
            total += len(got)
        if org.get("parse") and "--no-parse" not in argv and got:
            parse_programs(org, got, cfg)
    print(f"\n완료: 파일 {total}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
