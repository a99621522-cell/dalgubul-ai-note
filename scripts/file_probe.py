#!/usr/bin/env python3
"""첨부 파일 한 개를 받아 형식·시트·표 머리·찾는 낱말이 든 줄을 찍는다(site_probe.yml 입력 file=true). 저장소 변경 없음.
새 통계 첨부(예: 식약처 의료기기 생산실적)가 지역별 표를 담는지 확인할 때. 수집기가 아니라 한 번 확인용.
사용: python3 scripts/file_probe.py <url> [찾을 낱말,…(기본: 대구,지역,시도)]
"""
import io, re, subprocess, sys, tempfile, zipfile
from pathlib import Path
from urllib.parse import unquote
import requests

UA = "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"


def name_of(r, url):
    cd = r.headers.get("content-disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd) or re.search(r'filename="?([^";]+)', cd)
    if not m:
        return url.rsplit("/", 1)[-1]
    n = unquote(m.group(1))
    try:
        n = n.encode("latin-1").decode("utf-8")
    except Exception:
        try: n = n.encode("latin-1").decode("euc-kr")
        except Exception: pass
    return n


def show_text(label, text, words):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    print(f"== {label}: {len(lines)}줄 — 앞 40줄")
    for l in lines[:40]: print("  ", l[:200])
    for w in words:
        hits = [i for i, l in enumerate(lines) if w in l]
        print(f"== '{w}' 든 줄 {len(hits)}개 (앞 25개, 앞뒤 2줄)")
        for i in hits[:25]:
            print("  --", " | ".join(x[:120] for x in lines[max(0, i - 2): i + 3]))


def xlsx(data, words):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    for ws in wb.worksheets:
        rows = [[("" if c is None else str(c)).strip() for c in row] for row in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(r)]
        print(f"== 시트 「{ws.title}」 {len(rows)}행 — 앞 8행")
        for r in rows[:8]: print("  ", " | ".join(r)[:300])
        for w in words:
            hit = [r for r in rows if any(w in c for c in r)]
            if hit:
                print(f"   '{w}' 든 행 {len(hit)}개:")
                for r in hit[:12]: print("    ", " | ".join(r)[:300])


def main():
    url = sys.argv[1]
    words = (sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else "대구,지역,시도").split(",")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
    data = r.content
    name = name_of(r, url)
    print(f"== {r.status_code} {r.headers.get('content-type')} {len(data):,} bytes 파일명 {name!r} 첫 바이트 {data[:8]!r}")
    files = [(name, data)]
    if data[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(data))
        names = z.namelist()
        print(f"== zip {len(names)}개:", names[:40])
        if not any(n.startswith("xl/") or n.startswith("Contents/") or n == "mimetype" for n in names):
            files = [(n, z.read(n)) for n in names if not n.endswith("/")]
    for fn, d in files:
        low = fn.lower()
        print(f"\n######## {fn} ({len(d):,} bytes)")
        try:
            if d[:2] == b"PK" and (low.endswith((".xlsx", ".xlsm")) or b"xl/" in d[:2000]):
                xlsx(d, words)
            elif d[:4] == b"%PDF":
                with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
                    t.write(d); t.flush()
                    out = subprocess.run(["pdftotext", "-layout", t.name, "-"], capture_output=True, text=True).stdout
                show_text("PDF 글자", out, words)
            elif d[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                if low.endswith(".xls"):
                    print("== 옛 xls — 글자만 찾지 않음(xlrd 없음)")
                else:
                    sys.path.insert(0, str(Path(__file__).parent))
                    import hwp_text
                    with tempfile.NamedTemporaryFile(suffix=".hwp") as t:
                        t.write(d); t.flush()
                        show_text("HWP 글자", hwp_text.extract(t.name), words)
            elif d[:2] == b"PK":
                z = zipfile.ZipFile(io.BytesIO(d))
                xml = " ".join(z.read(n).decode("utf-8", "ignore") for n in sorted(z.namelist()) if re.match(r"Contents/section\d+\.xml", n))
                txt = re.sub(r"<hp:p\b", "\n<hp:p", xml)
                show_text("HWPX 글자", re.sub(r"<[^>]+>", " ", txt), words)
            else:
                show_text("글자", d.decode("utf-8", "ignore"), words)
        except Exception as e:
            print("  ! 읽기 실패:", str(e)[:300])


if __name__ == "__main__":
    main()
