#!/usr/bin/env python3
"""Google Drive 의 큰 PDF(스캔본 포함)를 받아 글자로 바꾼다. GitHub Actions(drive_ocr.yml)에서 돈다.

- Drive 커넥터(운영 세션)는 읽기 자체는 크기 제한이 없지만 이미지 스캔 PDF 는 글자가 없어 빈 쪽만 온다.
  그래서 러너가 파일을 받아 쪽마다 tesseract(kor+eng)로 글자를 뽑는다. 글자 층이 이미 있는 쪽은 pdftotext 값을 쓴다.
- 결과(ocr/<이름>.txt, index.json)는 워크플로 아티팩트로만 남긴다(7일). 원문·본문은 저장소에 커밋하지 않는다(data/refs 규칙).
- 입력: Drive 파일 id 또는 공유 링크(공백·쉼표 구분). 'folder:<id>' 면 공유 폴더 전체. 파일은 '링크가 있는 모든 사용자' 로 공유돼 있어야 한다.

사용: python3 scripts/drive_ocr.py --files "<id> <id>" [--dpi 200] [--lang kor+eng] [--out ocr]
필요: gdown, poppler-utils(pdftoppm·pdftotext), tesseract-ocr + tesseract-ocr-kor
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ID_RE = re.compile(r"[A-Za-z0-9_-]{20,}")


def drive_id(s: str) -> str:
    m = re.search(r"/d/([A-Za-z0-9_-]{20,})", s) or re.search(r"[?&]id=([A-Za-z0-9_-]{20,})", s)
    if m:
        return m.group(1)
    m = ID_RE.fullmatch(s.strip())
    return m.group(0) if m else ""


def download(item: str, dest: Path) -> list[Path]:
    """gdown 으로 받는다. 폴더면 folder:<id>. 받은 파일 목록을 돌려준다."""
    dest.mkdir(parents=True, exist_ok=True)
    before = set(dest.rglob("*"))
    if item.startswith("folder:"):
        fid = drive_id(item[7:])
        cmd = ["gdown", "--folder", "--remaining-ok", "-O", str(dest), f"https://drive.google.com/drive/folders/{fid}"]
    else:
        fid = drive_id(item)
        cmd = ["gdown", "--fuzzy", "-O", str(dest) + "/", f"https://drive.google.com/uc?id={fid}"]
    if not fid:
        print(f"::warning::Drive id 를 못 읽음: {item}")
        return []
    print("$", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(r.stdout[-2000:])
    if r.returncode != 0:
        msg = (r.stderr or "")[-1500:]
        if "Cannot retrieve" in msg or "permission" in msg.lower() or "access" in msg.lower():
            print(f"::error::[공유 필요] {fid} — Drive 에서 '링크가 있는 모든 사용자' 로 공유돼 있지 않다. gdown: {msg.strip()[-300:]}")
        else:
            print(f"::error::내려받기 실패 {fid}: {msg.strip()[-300:]}")
        return []
    return sorted(p for p in set(dest.rglob("*")) - before if p.is_file())


def pdf_pages(pdf: Path) -> int:
    r = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
    m = re.search(r"Pages:\s+(\d+)", r.stdout)
    return int(m.group(1)) if m else 0


def text_layer(pdf: Path, n: int) -> list[str]:
    """쪽마다 pdftotext 결과. 글자 층이 없으면 빈 문자열."""
    r = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True)
    pages = r.stdout.split("\f")
    pages = (pages + [""] * n)[:n]
    return [p if len(re.sub(r"\s", "", p)) >= 40 else "" for p in pages]


def ocr_page(png: Path, lang: str) -> str:
    r = subprocess.run(["tesseract", str(png), "-", "-l", lang, "--psm", "3"], capture_output=True, text=True)
    return r.stdout


def process_pdf(pdf: Path, out: Path, dpi: int, lang: str, workers: int) -> dict:
    t0 = time.time()
    n = pdf_pages(pdf)
    layer = text_layer(pdf, n) if n else []
    need = [i for i, t in enumerate(layer, 1) if not t]
    print(f"{pdf.name}: {n}쪽, 글자 층 있는 쪽 {n - len(need)}, OCR 할 쪽 {len(need)}", flush=True)
    work = out / "_pages" / pdf.stem
    work.mkdir(parents=True, exist_ok=True)
    texts = list(layer)
    if need:
        # 필요한 쪽만 회색 PNG 로 렌더 → 병렬 OCR
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", str(pdf), str(work / "p")], check=True)
        pngs = {int(m.group(1)): p for p in work.glob("p-*.png") if (m := re.search(r"-(\d+)\.png$", p.name))}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for i, t in zip(need, ex.map(lambda i: ocr_page(pngs[i], lang) if i in pngs else "", need)):
                texts[i - 1] = t
                if i % 20 == 0:
                    print(f"  … {i}/{n} ({time.time() - t0:.0f}s)", flush=True)
    shutil.rmtree(work, ignore_errors=True)
    body = "\n".join(f"=== 쪽 {i} ===\n{t.strip()}\n" for i, t in enumerate(texts, 1))
    name = re.sub(r"[^\w가-힣.()\- ]+", "_", pdf.stem)[:80] or "doc"
    (out / f"{name}.txt").write_text(body, encoding="utf-8")
    empty = sum(1 for t in texts if len(re.sub(r"\s", "", t)) < 20)
    return {"file": pdf.name, "txt": f"{name}.txt", "pages": n, "ocr_pages": len(need), "chars": len(body), "empty_pages": empty, "seconds": round(time.time() - t0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", required=True, help="Drive 파일 id·링크(공백/쉼표 구분) 또는 folder:<id>")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--lang", default="kor+eng")
    ap.add_argument("--out", default="ocr")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2)))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    dl = Path("_drive_dl")
    files: list[Path] = []
    for item in re.split(r"[\s,]+", a.files.strip()):
        if item:
            files += download(item, dl)
    index = []
    for f in files:
        if f.suffix.lower() == ".pdf":
            index.append(process_pdf(f, out, a.dpi, a.lang, a.workers))
        else:
            print(f"건너뜀(PDF 아님): {f.name}")
    shutil.rmtree(dl, ignore_errors=True)
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in index:
        print(f"{r['file']}: {r['pages']}쪽 · OCR {r['ocr_pages']}쪽 · {r['chars']:,}자 · 빈 쪽 {r['empty_pages']} · {r['seconds']}s → {r['txt']}")
    if not index:
        print("::error::처리한 PDF 가 없다"); sys.exit(1)


if __name__ == "__main__":
    main()
