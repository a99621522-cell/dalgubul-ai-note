"""국세청 「부가가치세 신고안내 매뉴얼」(참고자료실, 예정·확정 신고철마다 새 판) 본문 받기 — 운영자 2026-11-03 '국세청 신고안내 매뉴얼 받아서 규칙과 비교해봐'.
nts.go.kr 은 작성 세션에서 연결이 끊겨 러너(fetch_nts_manual.yml)가 받는다. 목록 페이지에서 제목에 '부가가치세 신고안내 매뉴얼'이 든 가장 최근 글을 열어
첨부(PDF·HWP) 링크를 받고 pdftotext -layout 으로 글자를 뽑아 data/vat/manuals/<key>.txt.gz + index.json 에 둔다(원문 파일은 저장소에 두지 않음).
사용: python3 scripts/fetch_nts_manual.py [--list URL] [--url 직접 PDF 주소] [--key 2026-1F] [--title 제목]"""
import gzip, json, re, subprocess, sys, tempfile
from pathlib import Path
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
LIST = "https://www.nts.go.kr/nts/na/ntt/selectNttList.do?mi=2409&bbsId=30008"
OUT = Path("data/vat/manuals")

def arg(k, d=None):
    a = sys.argv[1:]
    return a[a.index(k) + 1] if k in a else d

def get(url, **kw):
    r = requests.get(url, headers={"User-Agent": UA, "Referer": "https://www.nts.go.kr/"}, timeout=90, **kw)
    print(f"GET {url[:110]} → {r.status_code} {r.headers.get('content-type','')[:40]} {len(r.content):,}B")
    r.raise_for_status()
    return r

def find_latest(list_url):
    s = BeautifulSoup(get(list_url).text, "html.parser")
    for a in s.select("a"):
        t = a.get_text(" ", strip=True)
        if "부가가치세 신고안내 매뉴얼" in t or ("부가가치세" in t and "매뉴얼" in t):
            href = a.get("href") or ""
            oc = a.get("onclick") or ""
            m = re.search(r"nttSn=(\d+)", href + oc) or re.search(r"['\"](\d{6,})['\"]", oc)
            if m:
                return t, f"https://www.nts.go.kr/nts/na/ntt/selectNttInfo.do?mi=2409&nttSn={m.group(1)}"
    return None, None

def find_attach(page_url):
    r = get(page_url); s = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in s.select("a"):
        t = a.get_text(" ", strip=True); href = a.get("href") or ""; oc = a.get("onclick") or ""
        if re.search(r"\.(pdf|hwpx?)\b", t, re.I) or "fileDown" in href + oc or "atchFile" in href + oc:
            out.append((t, href, oc))
    print("첨부 후보:", out[:8])
    for t, href, oc in out:
        if href.startswith("http"): return t, href
        if href.startswith("/"): return t, "https://www.nts.go.kr" + href
        m = re.search(r"fn_egov_downFile\('([^']+)'\s*,\s*'([^']+)'\)", oc)
        if m: return t, f"https://www.nts.go.kr/nts/cmm/fms/FileDown.do?atchFileId={m.group(1)}&fileSn={m.group(2)}"
    return None, None

def main():
    key = arg("--key", ""); title = arg("--title", ""); url = arg("--url"); list_url = arg("--list", LIST)
    if not url:
        t, page = find_latest(list_url)
        if not page: print("목록에서 매뉴얼 글을 못 찾음"); sys.exit(2)
        title = title or t; print("글:", t, page)
        at, url = find_attach(page)
        if not url: print("첨부 링크를 못 찾음"); sys.exit(3)
        print("첨부:", at, url)
    if not key:
        m = re.search(r"(\d{4})\s*년?\s*(?:제)?\s*([12])\s*기\s*(예정|확정)", title or "")
        key = f"{m.group(1)}-{m.group(2)}{'P' if m.group(3) == '예정' else 'F'}" if m else "latest"
    r = get(url)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "m.bin"; p.write_bytes(r.content)
        head = r.content[:8]
        if head.startswith(b"%PDF"):
            txt = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout
            pages = len(re.findall("\f", txt)) + 1
        else:
            print("PDF 가 아님(앞 바이트):", head); sys.exit(4)
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / f"nts_{key}.txt.gz", "wt", encoding="utf-8") as w: w.write(txt)
    idx = json.loads((OUT / "index.json").read_text(encoding="utf-8")) if (OUT / "index.json").exists() else {}
    idx[f"nts_{key}"] = {"title": title, "url": url, "pages": pages, "chars": len(txt), "fetched": __import__("datetime").date.today().isoformat(), "src": "국세청 참고자료실 「부가가치세 신고안내 매뉴얼」 — 본문 글자만(pdftotext -layout), 원문 파일은 저장소에 두지 않음"}
    (OUT / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장 nts_{key}: {pages}쪽 {len(txt):,}자"); print(txt[:1500])

if __name__ == "__main__":
    main()
