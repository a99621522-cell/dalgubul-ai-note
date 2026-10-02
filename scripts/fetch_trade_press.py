#!/usr/bin/env python3
"""월간 수출입 보도자료 원문 받기 — 전국(산업통상부 「YYYY년 M월 수출입 동향」)과 대구·경북(대구본부세관 「YYYY년 M월 대구·경북지역 수출입 현황」).

본문 글자와 첨부(PDF·HWP·HWPX) 글자를 data/trade/raw/<기관>_<YYYYMM>*.txt 로 남긴다(원문 대조용, 사이트 표시 안 함).
비교표 값은 이 글자에서 세션이 옮겨 data/trade/<YYYYMM>.json 으로 만든다(값을 만들지 않는다, 원문 그대로).
운영자 지시 2026-10-02: 대구 월간 수출입이 나오면 전국과 비교표. 이 세션 환경은 두 사이트가 막혀 있어 워크플로(trade_press.yml)로 돈다.
사용: python3 scripts/fetch_trade_press.py --month 2026-08
"""
import argparse
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "data" / "trade" / "raw"
UA = {"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"}
S = requests.Session()
S.headers.update(UA)

CUSTOMS = "https://www.customs.go.kr"
CUSTOMS_LIST = CUSTOMS + "/daegu/na/ntt/selectNttList.do?mi=3867&bbsId=1525"
CUSTOMS_VIEW = CUSTOMS + "/daegu/na/ntt/selectNttInfo.do"
MOTIR = "https://www.motir.go.kr"
MOTIR_LIST = MOTIR + "/kor/article/ATCL3f49a5a8c"


def get(url, **kw):
    time.sleep(1)
    return S.get(url, timeout=60, **kw)


def text_of(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer"]):
        t.decompose()
    node = soup.select_one(".view_cont, .bbs_view, .board_view, .view-content, .view_con, #contents, .content") or soup
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", node.get_text("\n", strip=True)))


def file_text(name: str, data: bytes) -> str:
    from fetch_budget_docs import kind_of, to_text
    kind = kind_of(name, data)
    if not kind:
        return ""
    with tempfile.NamedTemporaryFile(suffix="." + kind, delete=False) as f:
        f.write(data)
        p = Path(f.name)
    return to_text(kind, p)


def save(name: str, text: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(text, encoding="utf-8")
    print(f"  저장 {p.relative_to(ROOT)} ({len(text):,}자)")


def fetch_attachments(html: str, base: str, prefix: str, referer: str) -> None:
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        label = a.get_text(" ", strip=True)
        if not re.search(r"(nttFileDownload|fileDown|FileDown|download|atchFile)", href, re.I) and not re.search(r"\.(pdf|hwpx?)\b", label, re.I):
            continue
        if not href or href.startswith(("#", "javascript")):
            continue
        url = urljoin(base, href)
        if url in seen or "바로보기" in label:
            continue
        seen.add(url)
        try:
            r = get(url, headers={"Referer": referer})
        except Exception as e:  # noqa: BLE001
            print(f"  첨부 실패 {label[:40]}: {e}")
            continue
        cd = r.headers.get("Content-Disposition", "")
        name = label or url
        m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
        if m:
            name = m.group(1)
            try:
                name = name.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        txt = file_text(name, r.content)
        print(f"  첨부 {label[:50]} → {len(r.content):,} bytes, 글자 {len(txt):,}")
        if txt.strip():
            save(f"{prefix}_att{len(seen)}.txt", f"# 첨부: {label}\n# 주소: {url}\n\n{txt}")


def customs(month: str) -> None:
    y, m = month.split("-")
    want = f"{int(y)}년 {int(m)}월 대구"
    r = get(CUSTOMS_LIST)
    print(f"[세관] 목록 HTTP {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    hit = None
    for a in soup.find_all("a"):
        t = a.get_text(" ", strip=True)
        if want in t.replace("·", "·") and "수출입" in t:
            hit = a
            break
    if not hit:
        print(f"[세관] '{want} … 수출입' 글 없음 — 아직 게시 전")
        return
    attrs = {k: v for k, v in hit.attrs.items()}
    print(f"[세관] 글: {hit.get_text(' ', strip=True)} | 속성 {attrs}")
    sn = ""
    for v in list(attrs.values()) + [str(hit.parent)]:
        mm = re.search(r"(\d{5,})", str(v))
        if mm:
            sn = mm.group(1)
            break
    if not sn:
        print("[세관] 글 번호(nttSn) 못 찾음")
        return
    data = {"bbsId": "1525", "nttSn": sn, "mi": "3867"}
    v = S.post(CUSTOMS_VIEW, data=data, timeout=60, headers={"Referer": CUSTOMS_LIST})
    if v.status_code != 200 or len(v.text) < 2000:
        v = get(f"{CUSTOMS_VIEW}?bbsId=1525&nttSn={sn}&mi=3867")
    print(f"[세관] 상세 HTTP {v.status_code}, {len(v.text):,}자 (nttSn {sn})")
    body = text_of(v.text)
    save(f"customs_{y}{m}.txt", f"# 대구본부세관 보도자료 nttSn={sn}\n# 주소: {CUSTOMS_VIEW}?bbsId=1525&nttSn={sn}&mi=3867\n\n{body}")
    fetch_attachments(v.text, v.url, f"customs_{y}{m}", v.url)


def motir(month: str) -> None:
    y, m = month.split("-")
    want = re.compile(rf"{int(y)}년\s*{int(m)}월\s*수출입\s*동향")
    url = None
    for page in range(1, 6):
        r = get(f"{MOTIR_LIST}?pageIndex={page}&searchCondition=1&searchKeyword=수출입")
        for a in BeautifulSoup(r.text, "html.parser").find_all("a", href=True):
            if want.search(a.get_text(" ", strip=True)) and "/view" in a["href"]:
                url = urljoin(r.url, a["href"])
                break
        if url:
            break
    if not url:
        print(f"[산업부] '{want.pattern}' 글 없음")
        return
    v = get(url)
    print(f"[산업부] 상세 {url} HTTP {v.status_code}")
    save(f"motir_{y}{m}.txt", f"# 산업통상부 보도자료\n# 주소: {url}\n\n{text_of(v.text)}")
    fetch_attachments(v.text, v.url, f"motir_{y}{m}", v.url)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True, help="YYYY-MM")
    ap.add_argument("--only", default="customs,motir")
    a = ap.parse_args()
    for k in a.only.split(","):
        try:
            {"customs": customs, "motir": motir}[k](a.month)
        except Exception as e:  # noqa: BLE001
            print(f"[{k}] 실패: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
