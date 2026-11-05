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



def bbox_lines(html: str) -> str:
    """pdftotext -bbox 낱말 좌표 → 세로로 겹치는 낱말을 한 줄로, 가로 순서대로(한글 PDF 가 쉼표·괄호를 따로 그려 -layout 이 줄을 가르는 것 보정). ALLBBOX:N"""
    import html as H
    out = []
    for pi, page in enumerate(re.findall(r"<page[^>]*>(.*?)</page>", html, flags=re.S), 1):
        ws = []
        for m in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', page):
            x0, y0, x1, y1 = map(float, m.groups()[:4])
            ws.append([x0, y0, x1, y1, H.unescape(m.group(5))])
        ws.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))
        lines = []
        for w in ws:
            best = None
            for L in lines:
                ov = min(L["y1"], w[3]) - max(L["y0"], w[1])
                if ov > 0.35 * min(L["y1"] - L["y0"], w[3] - w[1]) and (best is None or ov > best[0]):
                    best = (ov, L)
            if best:
                L = best[1]; L["w"].append(w)
                big = (w[3] - w[1]) > 0.6 * (L["y1"] - L["y0"])
                if big: L["y0"] = min(L["y0"], w[1]); L["y1"] = max(L["y1"], w[3])
            else:
                lines.append({"y0": w[1], "y1": w[3], "w": [w]})
        lines.sort(key=lambda L: L["y0"])
        for L in lines:
            L["w"].sort(key=lambda w: w[0])
            h = L["y1"] - L["y0"]; t = ""; prev = None
            for w in L["w"]:
                if prev is not None:
                    gap = w[0] - prev[2]
                    if gap > 0.22 * h and not re.match(r"^[,.)\]」』’”·‧:;]", w[4]) and not re.search(r"[(\[「『‘“]$", t):
                        t += " "
                t += w[4]; prev = w
            out.append(t)
        out.append(f"=={pi}==")
    return "\n".join(out)


def mu_lines(data: bytes, first=1, last=10**9) -> str:
    """PyMuPDF 글자 기준선(origin y)으로 줄을 묶고 글자 사이 간격으로 띄어쓰기를 되살림(ALLMU:N) — 한글 PDF 가 쉼표·괄호를 다른 글꼴로 그려 pdftotext 가 줄을 가르는 것 보정."""
    try:
        import pymupdf
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pymupdf"], check=False)
        import pymupdf
    doc = pymupdf.open(stream=data, filetype="pdf")
    out = []
    for pno in range(len(doc)):
        if not (first <= pno + 1 <= last): continue
        page = doc[pno]
        chars = []
        for b in page.get_text("rawdict")["blocks"]:
            for l in b.get("lines", []):
                for sp in l["spans"]:
                    for c in sp["chars"]:
                        x0, y0, x1, y1 = c["bbox"]
                        chars.append((c["origin"][1], c["origin"][0], x1, sp["size"], c["c"]))
        chars.sort(key=lambda c: (c[0], c[1]))
        rows = []
        for c in chars:
            if rows and abs(c[0] - rows[-1][0]) <= max(1.2, 0.25 * c[3]):
                rows[-1][1].append(c)
            else:
                rows.append([c[0], [c]])
        for y, cs in rows:
            cs.sort(key=lambda c: c[1])
            t = ""; prev = None
            for c in cs:
                if c[4] == " ":
                    if t and not t.endswith(" "): t += " "
                    prev = c; continue
                if prev is not None and prev[4] != " " and c[1] - prev[2] > 0.18 * c[3] and not t.endswith(" "):
                    t += " "
                t += c[4]; prev = c
            t = t.strip()
            if t: out.append(t)
        out.append(f"=={pno + 1}==")
    return "\n".join(out)

def show_text(label, text, words):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if words and words[0].startswith("ALL"):   # ALLRAW:N 은 -layout 없이. click 칸 'ALL' 또는 'ALL:3000' — 공개 문서 전체 글자(앞 N줄)를 찍는다(2026-11-04 국민성장펀드 가이드북)
        n = int(words[0].split(":")[1]) if ":" in words[0] else 3000
        print(f"== {label}: {len(lines)}줄 — 앞 {n}줄 전부")
        for l in lines[:n]: print("  ", l)
        return
    print(f"== {label}: {len(lines)}줄 — 앞 40줄")
    for l in lines[:40]: print("  ", l[:200])
    for w in words:
        hits = [i for i, l in enumerate(lines) if w in l]
        print(f"== '{w}' 든 줄 {len(hits)}개 (앞 25개, 앞뒤 2줄)")
        for i in hits[:25]:
            print("  --", " | ".join(x[:120] for x in lines[max(0, i - 2): i + 3]))


def csv_columns(txt):
    """CSV 열마다 값 종류가 30개 이하이면 분포를 찍는다(기업상태·지역 같은 분류 열 확인용)."""
    import csv as _csv, collections
    try:
        rows = list(_csv.reader(io.StringIO(txt)))
    except Exception:
        return
    if len(rows) < 2: return
    head = rows[0]
    for ci, name in enumerate(head):
        vals = collections.Counter(r[ci].strip() for r in rows[1:] if ci < len(r))
        if 1 < len(vals) <= 30:
            print(f"== 열 「{name}」 값 {len(vals)}종:", ", ".join(f"{k or '(빈칸)'} {v:,}" for k, v in vals.most_common()))


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
            elif d[:4] == b"%PDF" and words and words[0].startswith("ALLMU"):
                show_text("PDF 글자(PyMuPDF 기준선)", mu_lines(d), ["ALL:" + (words[0].split(":")[1] if ":" in words[0] else "6000")])
            elif d[:4] == b"%PDF" and words and words[0].startswith("ALLBBOX"):
                with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
                    t.write(d); t.flush()
                    out = subprocess.run(["pdftotext", "-bbox", t.name, "-"], capture_output=True, text=True).stdout
                show_text("PDF 글자(좌표로 줄 묶음)", bbox_lines(out), ["ALL:" + (words[0].split(":")[1] if ":" in words[0] else "6000")])
            elif d[:4] == b"%PDF":
                with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
                    t.write(d); t.flush()
                    out = subprocess.run(["pdftotext"] + ([] if words and words[0].startswith("ALLRAW") else ["-layout"]) + [t.name, "-"], capture_output=True, text=True).stdout  # ALLRAW: 읽는 순서 그대로(-layout 없음)
                show_text("PDF 글자", out, words)
            elif d[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                if low.endswith(".xls"):
                    try:
                        import xlrd
                        wb = xlrd.open_workbook(file_contents=d)
                        for sh in wb.sheets():
                            rows = [[str(sh.cell_value(r, c)).strip() for c in range(sh.ncols)] for r in range(min(sh.nrows, 400))]
                            print(f"== 시트 「{sh.name}」 {sh.nrows}행 — 앞 8행")
                            for r in rows[:8]: print("  ", " | ".join(r))
                            hit = [r for r in rows if any(w in " ".join(r) for w in words)]
                            if hit:
                                print(f"   {'·'.join(words)} 든 행 {len(hit)}개:")
                                for r in hit[:12]: print("     ", " | ".join(r))
                    except ImportError:
                        print("== 옛 xls — 글자만 찾지 않음(xlrd 없음)")
                    except Exception as e:
                        print("== 옛 xls 읽기 실패:", e)
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
                txt = None
                for enc in ("utf-8-sig", "cp949", "euc-kr"):   # 포털 CSV 는 cp949 가 많다(2026-10-06: utf-8 로만 읽어 글자가 깨졌음)
                    try: txt = d.decode(enc); break
                    except UnicodeDecodeError: pass
                txt = txt if txt is not None else d.decode("utf-8", "ignore")
                show_text("글자", txt, words)
                if low.endswith((".csv", ".txt")) or b"," in d[:200]:
                    csv_columns(txt)
        except Exception as e:
            print("  ! 읽기 실패:", str(e)[:300])


if __name__ == "__main__":
    main()
