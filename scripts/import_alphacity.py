#!/usr/bin/env python3
"""수성알파시티 홈페이지 '기업현황'(alphacity.or.kr/boardList?type=1) → 산단 외 기업 투입 CSV(scripts/data/extra/alphacity.csv)

입력은 둘 중 하나.
  1) 브라우저로 저장한 페이지 파일(.mht/.mhtml/.html)을 scripts/data/alphacity/ 에 넣고   python3 scripts/import_alphacity.py
     (32쪽이면 32개 파일. 파일 이름은 아무거나. 같은 기업이 여러 파일에 있으면 한 번만)
  2) 사이트에서 직접 받기(네트워크 되는 곳: GitHub Actions·국내 PC)                       python3 scripts/import_alphacity.py --fetch
     robots.txt 를 확인하고 쪽마다 1초 쉰다. 이 세션 환경은 외부 접속이 막혀 있어 1) 또는 워크플로(alphacity.yml)로.

목록의 열은 번호·로고·기업명·산업분야·대표자·사업분야. 대표자는 개인정보라 읽지 않고 버린다(기업 사전 원칙).
주소는 목록에 없으므로 '대구광역시 수성구 (수성알파시티 입주)' 로 두어 구·군(수성구)과 입지 유형(수성알파시티)만 판정되게 한다.
그다음 `python3 scripts/import_extra.py --replace-source 수성알파시티` 로 기업 DB 에 반영한다(이 스크립트가 --import 옵션으로 대신 실행).
"""
from __future__ import annotations

import csv
import email
import re
import sys
import time
from datetime import date
from email import policy
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "scripts" / "data" / "alphacity"
OUT = ROOT / "scripts" / "data" / "extra" / "alphacity.csv"
BASE = "https://alphacity.or.kr/"
LIST = BASE + "boardList?type=1&stx_cd=0&stx=&page={page}"
SOURCE = "수성알파시티 홈페이지 기업현황(alphacity.or.kr)"
ADDRESS = "대구광역시 수성구 (수성알파시티 입주, 상세 주소는 목록에 없음)"
UA = {"User-Agent": "Mozilla/5.0 (compatible; daitda-note/1.0; +https://note.daitda.co.kr)"}
COLS = ["회사명", "주소", "업종", "사업내용", "종사자수", "설립연도", "태그", "출처", "기준월"]


def html_of(path: Path) -> str:
    raw = path.read_bytes()
    if path.suffix.lower() in (".mht", ".mhtml") or raw[:5] in (b"From:", b"MIME-"):
        msg = email.message_from_bytes(raw, policy=policy.default)
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        return ""
    for enc in ("utf-8", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def parse(html: str) -> tuple[list[dict], int, int]:
    """표 행 → 기업 dict, (전체 건수, 마지막 쪽)."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    table = soup.find("table")
    if table is None:
        return rows, 0, 0
    heads = [th.get_text(" ", strip=True) for th in table.find_all("th")]
    idx = {h: i for i, h in enumerate(heads)}
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < len(heads) or not heads:
            continue
        cell = lambda h: re.sub(r"\s+", " ", tds[idx[h]].get_text(" ", strip=True)) if h in idx else ""  # noqa: E731
        name = cell("기업명")
        if not name:
            continue
        rows.append({"회사명": name, "업종": cell("산업분야"), "사업내용": cell("사업분야")})   # 대표자 열은 읽지 않는다
    text = soup.get_text(" ", strip=True)
    m = re.search(r"전체\s*([\d,]+)\s*건", text)
    total = int(m.group(1).replace(",", "")) if m else 0
    m = re.search(r"현재페이지\s*\d+\s*/\s*(\d+)", text)
    last = int(m.group(1)) if m else 0
    return rows, total, last


def robots_ok(sess: requests.Session) -> bool:
    try:
        r = sess.get(urljoin(BASE, "/robots.txt"), headers=UA, timeout=20)
    except Exception as e:  # noqa: BLE001
        print(f"robots.txt 확인 실패({e}); 계속")
        return True
    if r.status_code != 200:
        return True
    block, dis = False, []
    for line in r.text.splitlines():
        k, _, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            block = v == "*"
        elif k == "disallow" and block and v:
            dis.append(v)
    return not any("/boardList".startswith(d) or d == "/" for d in dis)


def fetch_all() -> tuple[list[dict], int]:
    sess = requests.Session()
    if not robots_ok(sess):
        print("robots.txt 가 /boardList 수집을 막고 있어 받지 않는다")
        return [], 0
    rows, total, last, page = [], 0, 1, 1
    while page <= last and page <= 100:
        try:
            r = sess.get(LIST.format(page=page), headers=UA, timeout=60)
        except Exception as e:  # noqa: BLE001
            print(f"  {page}쪽 실패: {str(e)[:80]}")
            break
        got, t, l = parse(r.text)
        total, last = total or t, last if page > 1 else (l or 1)
        print(f"  {page}/{last}쪽 HTTP {r.status_code} {len(got)}곳")
        if not got:
            break
        rows += got
        page += 1
        time.sleep(1)
    return rows, total


def main(argv: list[str]) -> int:
    if "--fetch" in argv:
        rows, total = fetch_all()
        note = "사이트에서 직접"
    else:
        files = sorted(p for p in INBOX.glob("*") if p.suffix.lower() in (".mht", ".mhtml", ".html", ".htm"))
        if not files:
            print(f"입력 없음: {INBOX.relative_to(ROOT)}/ 에 저장한 페이지(.mht/.html)를 넣거나 --fetch")
            return 1
        rows, total = [], 0
        for f in files:
            got, t, _ = parse(html_of(f))
            total = total or t
            print(f"  {f.name}: {len(got)}곳")
            rows += got
        note = f"저장한 페이지 {len(files)}개"
    seen, uniq = set(), []
    for r in rows:
        k = re.sub(r"\s", "", r["회사명"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    if not uniq:
        print("기업을 하나도 못 읽었다")
        return 1
    month = date.today().strftime("%Y-%m")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in uniq:
            w.writerow({"회사명": r["회사명"], "주소": ADDRESS, "업종": r["업종"], "사업내용": r["사업내용"], "종사자수": "", "설립연도": "",
                        "태그": "", "출처": SOURCE, "기준월": month})
    print(f"{note} → {OUT.relative_to(ROOT)}: {len(uniq)}곳" + (f" (사이트 전체 {total}건)" if total else ""))
    if total and len(uniq) < total:
        print(f"  ※ 전체 {total}건 중 {len(uniq)}건만 읽었다. 나머지 쪽도 저장해 넣거나 --fetch 로 받을 것 (전수 원칙)")
    if "--import" in argv:
        import subprocess
        return subprocess.call([sys.executable, str(ROOT / "scripts" / "import_extra.py"), "--replace-source", "수성알파시티"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
