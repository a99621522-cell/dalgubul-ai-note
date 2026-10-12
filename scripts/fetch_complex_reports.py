#!/usr/bin/env python3
"""대구 산업단지 관리기관 누리집의 분기 자료(생산·수출·고용) 첨부 PDF → 글자 파일(data/complexes/raw/<key>_<YYYY>q<N>_<n>.txt).

설정 config/complex_sources.yml(운영자 지시 2026-10-12). 게시판 목록에서 제목이 `title` 에 맞는 글을 찾고, 글 안 첨부 중 이름이 `files` 낱말을 담은
PDF 만 받아 pdftotext -layout 으로 글자를 뽑는다(원본 PDF 는 저장하지 않음). 입주업체 명단(엑셀) 첨부는 받지 않는다. robots.txt 를 지키고 요청 사이 1초.
이미 있는 글자 파일은 다시 받지 않는다. 이 세션 환경은 외부 접속이 막혀 있어 .github/workflows/complex_reports.yml 이 돌린다.
표 읽기는 scripts/parse_complex_reports.py.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "complexes" / "raw"
CFG = ROOT / "config" / "complex_sources.yml"
UA = "Mozilla/5.0 (compatible; daitda-note-bot/1.0; +https://daitda.co.kr)"


def allowed(url: str, cache: dict) -> bool:
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if base not in cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:  # noqa: BLE001
            rp.parse([])
        cache[base] = rp
    return cache[base].can_fetch(UA, url)


def get(url: str) -> requests.Response | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        time.sleep(1)
        return r
    except Exception as e:  # noqa: BLE001
        print(f"  실패 {url}: {str(e)[:120]}")
        return None


def quarter_of(title: str) -> str:
    m = re.search(r"(\d{4})\s*년\s*(\d)\s*/\s*4\s*분기|(\d{4})\s*년\s*(\d)\s*분기", title)
    if not m:
        return ""
    y, q = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    return f"{y}q{q}"


def pdf_text(data: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
        t.write(data)
        t.flush()
        return subprocess.run(["pdftotext", "-layout", t.name, "-"], capture_output=True, text=True).stdout


def run(src: dict, robots: dict) -> int:
    n = 0
    posts: dict[str, str] = {}
    for p in range(1, int(src.get("pages", 1)) + 1):
        url = src["list"] + (f"?page={p}" if p > 1 else "")
        if not allowed(url, robots):
            print(f"  robots 차단: {url}")
            return 0
        r = get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            t = a.get_text(" ", strip=True)
            if re.search(src["post"], href) and re.search(src["title"], t) and quarter_of(t):
                posts.setdefault(href, t)
    print(f"[{src['key']}] 글 {len(posts)}개")
    for href, title in posts.items():
        q = quarter_of(title)
        r = get(href)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for i, kw in enumerate(src["files"], 1):
            out = RAW / f"{src['key']}_{q}_{i}.txt"
            if out.exists():
                continue
            link = next((a for a in soup.find_all("a", href=True) if kw in a.get_text(" ", strip=True)
                         and re.search(r"\.pdf", a.get_text(" ", strip=True), re.I)), None)
            if not link:
                print(f"  {q} '{kw}' 첨부 없음")
                continue
            furl = urljoin(href, link["href"])
            f = get(furl)
            if not f or not f.content.startswith(b"%PDF"):
                print(f"  {q} '{kw}' PDF 아님")
                continue
            text = pdf_text(f.content)
            out.write_text(f"# {src['name']} — {title}\n# 글: {href}\n# 첨부: {link.get_text(' ', strip=True)} {furl}\n\n{text}", encoding="utf-8")
            print(f"  저장 {out.relative_to(ROOT)} ({len(text):,}자)")
            n += 1
    return n


def main(argv: list[str]) -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    RAW.mkdir(parents=True, exist_ok=True)
    robots: dict = {}
    total = 0
    for src in cfg["sources"]:
        if only and src["key"] not in only:
            continue
        try:
            total += run(src, robots)
        except Exception as e:  # noqa: BLE001
            print(f"[{src['key']}] 건너뜀: {e}")
    print(f"새 글자 파일 {total}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
