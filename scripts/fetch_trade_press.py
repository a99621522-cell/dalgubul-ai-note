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
        if not re.search(r"(nttFileDownload|fileDown|FileDown|download|atchFile)", href + " " + (a.get("onclick") or ""), re.I) and not re.search(r"\.(pdf|hwpx?)\b", label, re.I):
            continue
        onclick = a.get("onclick") or ""
        if (not href or href.startswith(("#", "javascript"))) and onclick:
            mk = re.search(r"['\"]([A-Za-z0-9_\-]{8,})['\"]", onclick)
            href = f"/common/nttFileDownload.do?fileKey={mk.group(1)}" if mk else ""
            print(f"  첨부 onclick: {onclick[:120]} → {href}")
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
    # 상세는 목록의 글 제목을 누르면 스크립트가 폼을 POST 한다(직접 POST 는 '시스템안내' 오류) → 브라우저로 누른다
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(user_agent=UA["User-Agent"], accept_downloads=True)
        pg.on("dialog", lambda d: (print(f"  대화상자: {d.message[:80]} → 확인"), d.accept()))   # 내려받기 확인 창을 받아들인다
        pg.goto(CUSTOMS_LIST, wait_until="networkidle", timeout=60000)
        pg.get_by_text(hit.get_text(" ", strip=True)[:20], exact=False).first.click()
        pg.wait_for_load_state("networkidle", timeout=60000)
        html, cur = pg.content(), pg.url
        # 첨부: <a class="fdown" href="#none"> 를 누르면 스크립트가 /common/nttFileDownload.do?fileKey=… 로 보낸다.
        # 스크립트에서 fileKey 를 만드는 방식을 찾아 같은 브라우저 세션(쿠키 유지)으로 직접 받는다
        files = []
        for m_ in re.finditer(r".{0,400}fdown.{0,600}", html.replace("\n", " ")):
            if "nttFileDownload" in m_.group(0) or "function" in m_.group(0):
                print("  fdown 스크립트:", m_.group(0)[:900])
                break
        info = pg.evaluate("""() => [...document.querySelectorAll('a.fdown')].map(a => ({t: a.innerText.trim(),
            attrs: [...a.attributes].map(x => x.name + '=' + x.value), parent: a.parentElement.outerHTML.slice(0, 600)}))""")
        for it in info:
            print("  첨부:", it["t"][:60], it["attrs"], it["parent"][:400].replace("\n", " "))
        keys = re.findall(r"nttFileDownload\.do\?fileKey=['\"]?\s*\+?\s*['\"]?([A-Za-z0-9_\-]{8,})", html)
        cand = re.findall(r"(?:data-[a-z]+|fileKey|fileSn|value)=['\"]([A-Za-z0-9_\-]{16,})['\"]", " ".join(i["parent"] for i in info))
        for key in dict.fromkeys(keys + cand):
            url = f"{CUSTOMS}/common/nttFileDownload.do?fileKey={key}"
            try:
                r_ = pg.request.get(url, headers={"Referer": cur})
                body_ = r_.body()
                cd = r_.headers.get("content-disposition", "")
                print(f"  시도 {url} → {r_.status}, {len(body_):,} bytes, {cd[:80]}")
                if r_.ok and len(body_) > 5000 and not body_[:200].lstrip().startswith(b"<"):
                    mm = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
                    nm = mm.group(1) if mm else key
                    try:
                        nm = nm.encode("latin-1").decode("utf-8")
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        pass
                    files.append((nm, body_))
            except Exception as e:  # noqa: BLE001
                print(f"  시도 실패 {key}: {e}")
        if not files:   # 눌러서 오가는 요청을 지켜보고, 첨부(content-disposition) 응답을 그대로 담는다
            got = []

            def on_resp(r):
                try:
                    cd = r.headers.get("content-disposition", "")
                    if "attachment" in cd.lower() or "filename" in cd.lower():
                        got.append((cd, r.body()))
                except Exception as e:  # noqa: BLE001
                    print(f"  응답 읽기 실패: {str(e)[:80]}")
            pg.on("request", lambda q: print(f"  요청 {q.method} {q.url[:160]}") if "customs.go.kr" in q.url and not re.search(r"\.(css|js|png|gif|jpg|woff2?)(\?|$)", q.url) else None)
            pg.on("response", on_resp)
            pg.context.on("page", lambda np: (np.on("response", on_resp), print(f"  새 창 {np.url[:160]}")))
            fd = pg.locator("a.fdown")
            for i in range(fd.count()):
                if ".hwpx" not in fd.nth(i).inner_text() and i < fd.count() - 1:
                    continue
                try:
                    with pg.expect_download(timeout=30000) as dl:
                        fd.nth(i).click()
                    d = dl.value
                    files.append((d.suggested_filename, Path(d.path()).read_bytes()))
                except Exception as e:  # noqa: BLE001
                    print(f"  누르기 실패: {str(e)[:100]}")
                break
            for cd, body_ in got:
                mm = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
                nm = mm.group(1) if mm else "attach"
                try:
                    nm = nm.encode("latin-1").decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
                files.append((nm, body_))
        b.close()
    for k, (name, data) in enumerate(files, 1):
        txt = file_text(name, data)
        print(f"  첨부 {name} → {len(data):,} bytes, 글자 {len(txt):,}")
        if txt.strip():
            save(f"customs_{y}{m}_att{k}.txt", f"# 첨부: {name}\n\n{txt}")

    class V:  # requests 응답처럼 쓰기
        text, url = html, cur
    v = V()
    print(f"[세관] 상세 {cur}, {len(html):,}자 (nttSn {sn})")
    body = text_of(v.text)
    save(f"customs_{y}{m}.txt", f"# 대구본부세관 보도자료 nttSn={sn}\n# 목록: {CUSTOMS_LIST}\n\n{body}")


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
