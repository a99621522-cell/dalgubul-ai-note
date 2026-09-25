#!/usr/bin/env python3
"""한국은행 산업연관표(기본부문 생산자가격 거래표·부문분류표) 첨부를 받아 scripts/data/io/ 에 둔다.

사용: python3 scripts/fetch_io_tables.py            # config 의 seeds 전부
      python3 scripts/fetch_io_tables.py --dry-run  # 링크만 보고 받지 않음

seeds 는 config/io_sources.yml. 한국은행 보도자료·간행물 페이지와 KOSIS 파일 페이지의 첨부(xlsx·xls·zip)를
label 이 file_pattern 에 맞을 때만 받는다. zip 은 풀어서 xlsx 만 남긴다. 이 세션 환경은 한국은행·KOSIS 접속이
막혀 있어 워크플로(.github/workflows/io_tables.yml)가 대신 받는다. 파일 형식 확인·매핑은 scripts/attract.py.
"""
from __future__ import annotations

import io
import re
import sys
import time
import zipfile
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_budget_docs import click_download, download, kind_of, links_of, render, safe, text_of  # noqa: E402
from scrape_institution_boards import robots_ok  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "io_sources.yml"
OUT = ROOT / "scripts" / "data" / "io"


def main(argv: list[str]) -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    dry = "--dry-run" in argv
    file_re = re.compile(cfg["file_pattern"])
    excl_re = re.compile(cfg.get("exclude_pattern") or "$^")
    ext_re = re.compile(r"\.(xlsx?|zip)(\?|$)", re.I)
    sess = requests.Session()
    robots: dict = {}
    OUT.mkdir(parents=True, exist_ok=True)
    got = 0
    for seed in cfg["seeds"]:
        url = seed["url"]
        print(f"\n== {seed.get('name', url)}")
        if not robots_ok(url, robots):
            print("  robots 차단")
            continue
        html, final = render(url)
        if not html:
            print("  페이지 열기 실패")
            continue
        links = links_of(html, final)
        n = 0
        for label, href, onclick in links:
            text = f"{label} {href} {onclick}"
            is_file = bool(ext_re.search(href)) or bool(re.search(r"fileDown|FileDown|download|atchFile|fileSn|attach|fileView", href + onclick, re.I)) or bool(re.search(r"\.(xlsx?|zip)\s*(\[|$)", label, re.I))
            if not is_file or not file_re.search(text) or excl_re.search(label):
                continue
            n += 1
            print(f"  링크: {label[:70]} → {href[:90]}")
            if dry:
                continue
            gf = download(href, final, sess) if href.startswith("http") else click_download(final, label)
            if not gf:
                print("    받기 실패")
                continue
            name, data = gf
            kind = kind_of(name, data)
            items = [(name, data)] if kind == "xlsx" else []
            if kind == "zip":
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        for zi in z.infolist()[:50]:
                            try:
                                zn = zi.filename.encode("cp437").decode("cp949")
                            except Exception:  # noqa: BLE001
                                zn = zi.filename
                            if re.search(r"\.xlsx?$", zn, re.I):
                                items.append((Path(zn).name, z.read(zi)))
                except Exception as e:  # noqa: BLE001
                    print(f"    zip 실패: {str(e)[:60]}")
            if not items:
                print(f"    엑셀 아님({kind or '알 수 없음'}): {name[:60]}")
                continue
            for fn, fd in items:
                p = OUT / safe(fn, 120)
                p.write_bytes(fd)
                got += 1
                print(f"    저장 {p.name} ({len(fd):,} bytes)")
            time.sleep(1)
        if not n:
            sample = [(l[:30], h[-60:]) for l, h, _ in links if re.search(r"xls|zip|첨부|다운", f"{l} {h}", re.I)][:12]
            print(f"  맞는 첨부 없음. 표본: {sample}")
        time.sleep(1)
    print(f"\n완료: 엑셀 {got}개 → {OUT.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
