#!/usr/bin/env python3
"""지방재정365 통합자료실 「N 회계연도 세부사업별 세출 현황」(전국 자치단체, 해마다 1월 게시) → 대구 행만 data/vat/lofin_biz/<연도>.csv

공공데이터포털 15138684(행정안전부_지방재정365_연도별 세부사업별세출현황)가 가리키는 곳:
https://www.lofin365.go.kr/portal/LF8310000.do?ntcaClsDvCd=FSL446 — 로그인 없이 열림, robots.txt 전체 허용.
게시판은 화면 스크립트(tui-grid)라 Playwright 로 열어 그해 줄의 「첨부파일 다운로드」를 눌러 받는다(요청 사이 3초).
엑셀은 전국 자치단체 전부라 크다 — 저장소에는 대구(본청·구군) 행만 CSV 로 남기고 원본은 지운다.

사용: python3 scripts/fetch_lofin_bizexp.py [--years 2021,2022,2023,2024,2025] [--keep DIR]
세부사업별 예산현액·지출액(국비·시도비·시군구비) — 통계목·거래처는 없다(통계목은 주민참여 재정 포털 2021~2023 에만).
"""
import argparse, csv, io, json, re, sys, time, zipfile
from pathlib import Path

URL = "https://www.lofin365.go.kr/portal/LF8310000.do?ntcaClsDvCd=FSL446"
OUT = Path("data/vat/lofin_biz")


def download(years: list[str], tmp: Path) -> dict[str, Path]:
    from playwright.sync_api import sync_playwright
    got: dict[str, Path] = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(accept_downloads=True, locale="ko-KR")
        pg.goto(URL, wait_until="networkidle", timeout=120_000)
        pg.wait_for_selector("td[data-column-name=ntcaTitCn]", timeout=60_000)
        for y in years:
            row = pg.locator("tr", has=pg.locator("td[data-column-name=ntcaTitCn]", has_text=f"{y} 회계연도 세부사업별"))
            btn = row.locator("td[data-column-name=atflNum] button")
            if not btn.count():
                print(f"[lofin_biz] {y}: 게시판에 그해 줄이 없음", flush=True)
                continue
            try:
                with pg.expect_download(timeout=600_000) as dl:
                    btn.first.click()
                d = dl.value
                f = tmp / f"{y}_{d.suggested_filename}"
                d.save_as(f)
                print(f"[lofin_biz] {y}: {d.suggested_filename} {f.stat().st_size:,}B", flush=True)
                got[y] = f
            except Exception as e:  # 한 해가 실패해도 나머지는 받는다
                print(f"[lofin_biz] {y}: 받기 실패 {e}", flush=True)
            time.sleep(3)
        b.close()
    return got


def sheets(path: Path):
    """xlsx(또는 zip 안의 xlsx)의 시트마다 행(값 목록)을 낸다."""
    import openpyxl
    data = path.read_bytes()
    blobs = []
    if data[:2] == b"PK" and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            blobs = [z.read(n) for n in z.namelist() if n.lower().endswith(".xlsx")]
    else:
        blobs = [data]
    for blob in blobs:
        wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
        for ws in wb.worksheets:
            yield ws.title, ws.iter_rows(values_only=True)


def norm(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"\s+", " ", str(v)).strip()


def extract(y: str, path: Path) -> dict:
    """머리글 줄(‘자치단체’ 든 줄)을 찾고, 지역·자치단체 칸이 대구인 행만 남긴다."""
    out = OUT / f"{y}.csv"
    head, n_all, n_dg, cols, sub = None, 0, 0, {}, False
    with out.open("w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        for title, rows in sheets(path):
            head = None
            for i, r in enumerate(rows):
                vals = [norm(v) for v in r]
                if head is None:
                    if i < 4:
                        print(f"  [{title} {i}] {vals[:16]}", flush=True)
                    if any("자치단체" in v for v in vals) and sum(1 for v in vals if v) >= 4:
                        head = vals
                        cols = {k: j for j, k in enumerate(head) if k}
                        sub = True   # 다음 줄이 묶음 머리(예산현액 → 계·국비·시도비·…)인지 본다
                    continue
                if sub:
                    sub = False
                    if not any(v.startswith("대구") for v in vals) and any(vals[j] for j in range(len(vals)) if j < len(head) and not head[j]):
                        top = ""
                        for j in range(len(head)):   # 빈 위 칸은 왼쪽 묶음 이름을 이어 받아 '예산현액_국비' 식으로
                            top = head[j] or top
                            if j < len(vals) and vals[j]:
                                head[j] = f"{top}_{vals[j]}" if vals[j] != top else top
                        print(f"  머리글: {head}", flush=True)
                        w.writerow(["연도"] + head)
                        continue
                    w.writerow(["연도"] + head)
                if not any(vals):
                    continue
                n_all += 1
                key = [vals[j] for k, j in cols.items() if ("지역" in k or "자치단체" in k or "시도" in k) and j < len(vals)]
                if any(k.startswith("대구") for k in key):
                    w.writerow([y] + vals[: len(head)])
                    n_dg += 1
    print(f"[lofin_biz] {y}: 전국 {n_all:,}행 중 대구 {n_dg:,}행 → {out}", flush=True)
    if not n_dg:
        out.unlink(missing_ok=True)
    return {"rows": n_dg, "all": n_all, "head": head or []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2021,2022,2023,2024,2025")
    ap.add_argument("--keep", default="", help="받은 원본을 둘 폴더(비우면 임시 폴더, 끝나면 지움)")
    a = ap.parse_args()
    import tempfile
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(a.keep) if a.keep else Path(tempfile.mkdtemp())
    tmp.mkdir(parents=True, exist_ok=True)
    got = download([y.strip() for y in a.years.split(",") if y.strip()], tmp)
    idx_p = OUT / "index.json"
    idx = json.loads(idx_p.read_text(encoding="utf-8")) if idx_p.exists() else {}
    for y, f in got.items():
        try:
            info = extract(y, f)
        except Exception as e:
            print(f"[lofin_biz] {y}: 읽기 실패 {e}", flush=True)
            continue
        if info["rows"]:
            idx[y] = {"file": f.name.split("_", 1)[1], "fetched": time.strftime("%Y-%m-%d"), **info}
    idx_p.write_text(json.dumps(dict(sorted(idx.items())), ensure_ascii=False, indent=1), encoding="utf-8")
    if not got:
        sys.exit(1)


if __name__ == "__main__":
    main()
