#!/usr/bin/env python3
"""지자체 세입예산사업명세서 PDF 받기 → pdftotext -layout → scripts/parse_revenue_docs.py → data/vat/revenue/<key>_<year>.csv (운영자 지시 2026-10-27).
설정 config/revenue_docs.yml. kind: pdf / daegu_jumin / discover(첨부 후보만 로그). robots.txt 는 공시 페이지(지자체 누리집)라 확인 뒤 받는다(기본 허용).
러너(.github/workflows/revenue_docs.yml)에서 돌리며, 이 세션처럼 requests 가 프록시에서 막히면 curl 로 대신한다(--curl).
사용: python3 scripts/fetch_revenue_docs.py [--only key,key] [--curl] [--parse-only]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "config" / "revenue_docs.yml").read_text(encoding="utf-8"))
RAW = ROOT / "data" / "vat" / "revenue" / "raw"
UA = "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"
USE_CURL = "--curl" in sys.argv
S = requests.Session()
S.headers["User-Agent"] = UA


def get(url: str, out: Path | None = None, post: dict | None = None, referer: str = "", jar: Path | None = None) -> bytes:
    for i in range(4):
        try:
            if USE_CURL:
                cmd = ["curl", "-sS", "-m", "240", "-L", "-A", UA]
                if jar:
                    cmd += ["-c", str(jar), "-b", str(jar)]
                if referer:
                    cmd += ["-e", referer]
                if post:
                    cmd += ["-X", "POST"]
                    for k, v in post.items():
                        cmd += ["--data-urlencode", f"{k}={v}"]
                cmd.append(url)
                r = subprocess.run(cmd, capture_output=True, timeout=300)
                if r.returncode == 0 and r.stdout:
                    if out:
                        out.write_bytes(r.stdout)
                    return r.stdout
            else:
                h = {"Referer": referer} if referer else {}
                r2 = S.post(url, data=post, headers=h, timeout=240) if post else S.get(url, headers=h, timeout=240)
                if r2.ok and r2.content:
                    if out:
                        out.write_bytes(r2.content)
                    return r2.content
        except Exception as e:  # noqa: BLE001
            print(f"  [{i + 1}] {url[:80]} 실패: {str(e)[:100]}")
        time.sleep(2 + i * 3)
    return b""


def to_text(pdf: Path, txt: Path) -> bool:
    r = subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], capture_output=True)
    return r.returncode == 0 and txt.exists() and txt.stat().st_size > 1000


def fetch_pdf(g: dict, year: str) -> Path | None:
    RAW.mkdir(parents=True, exist_ok=True)
    pdf = RAW / f"{g['key']}_{year}.pdf"
    if g["kind"] == "pdf":
        data = get(g["url"], pdf)
    elif g["kind"] == "daegu_jumin":
        jar = RAW / f"{g['key']}.jar"
        page = get(g["page"], jar=jar).decode("utf-8", "ignore")
        m = re.search(r'name="CSRFToken" value="([^"]+)"', page)
        if not m:
            print(f"[revenue] {g['name']}: CSRF 토큰 못 찾음")
            return None
        data = get(g["page"].rsplit("/", 1)[0] + "/fileDownload.do", pdf, post={"CSRFToken": m.group(1), "fileName": g["file"], "startGubun": "budetBill"}, referer=g["page"], jar=jar)
        jar.unlink(missing_ok=True)
    else:
        return None
    if not data or not data.startswith(b"%PDF"):
        print(f"[revenue] {g['name']}: PDF 아님({len(data)}B)")
        pdf.unlink(missing_ok=True)
        return None
    return pdf


def fetch_expense(g: dict, year: str) -> Path | None:
    """세출예산사업명세서 부서별 파일을 받아 글자로 이어 붙인다(파일 사이 '#### 파일명'). 금액은 CSV(내부)에만 — 사이트에는 사업명·부서·편성목만"""
    urls = g.get("expense_urls") or []; files = g.get("expense_files") or []
    if not urls and not files:
        return None
    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / f"{g['key']}_{year}_exp.txt"; parts: list[str] = []
    jar = RAW / f"{g['key']}_exp.jar"; tok = ""
    if files:
        page = get(g["page"], jar=jar).decode("utf-8", "ignore"); m = re.search(r'name="CSRFToken" value="([^"]+)"', page); tok = m.group(1) if m else ""
    for i, item in enumerate(urls or files):
        pdf = RAW / f"_exp_{g['key']}_{i}.pdf"; txt = RAW / f"_exp_{g['key']}_{i}.txt"
        data = get(item, pdf) if urls else get(g["page"].rsplit("/", 1)[0] + "/fileDownload.do", pdf, post={"CSRFToken": tok, "fileName": item, "startGubun": "budetBill"}, referer=g["page"], jar=jar)
        if not data or not data.startswith(b"%PDF") or not to_text(pdf, txt):
            print(f"[revenue] {g['name']} 세출 {i + 1}/{len(urls or files)} 실패: {str(item)[-40:]}")
            pdf.unlink(missing_ok=True); txt.unlink(missing_ok=True); time.sleep(1.5); continue
        parts.append(f"#### {item}\n" + txt.read_text(encoding="utf-8", errors="ignore")); pdf.unlink(missing_ok=True); txt.unlink(missing_ok=True); time.sleep(1.5)
    jar.unlink(missing_ok=True)
    if not parts:
        return None
    out.write_text("\n".join(parts), encoding="utf-8"); print(f"[revenue] {g['name']} 세출 {len(parts)}개 파일 → {out.name}")
    return out


def discover(g: dict) -> None:
    html = get(g["page"]).decode("utf-8", "ignore")
    if not html:
        print(f"[revenue] {g['name']}: 페이지 못 받음 {g['page']}")
        return
    links = re.findall(r'href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S)
    print(f"[revenue] {g['name']} discover {g['page']} ({len(html)}B)")
    for href, txt in links:
        t = re.sub(r"<[^>]+>", "", txt).strip()
        if re.search(r"세입|예산서|명세|\.pdf|\.hwp|\.xls", t + href, re.I):
            print(f"   {t[:40]} | {href[:160]}")


def main() -> int:
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    year = str(CFG["year"])
    for g in CFG["govs"]:
        if only and g["key"] not in only:
            continue
        if g["kind"] == "discover":
            if "--parse-only" not in sys.argv:
                discover(g)
            continue
        txt = RAW / f"{g['key']}_{year}.txt"
        if "--parse-only" not in sys.argv:
            pdf = fetch_pdf(g, year)
            if not pdf:
                continue
            if not to_text(pdf, txt):
                print(f"[revenue] {g['name']}: pdftotext 실패")
                continue
            pdf.unlink(missing_ok=True)   # 원본 PDF 는 저장소에 두지 않고 글자만
        if not txt.exists():
            continue
        subprocess.run([sys.executable, str(ROOT / "scripts" / "parse_revenue_docs.py"), g["key"], year, str(txt), "--name", g["name"], "--src", g["page"], "--date", time.strftime("%Y-%m-%d"), "--acct", g.get("acct", "일반회계")])
        time.sleep(1.5)
        etxt = RAW / f"{g['key']}_{year}_exp.txt"
        if "--parse-only" not in sys.argv and "--no-expense" not in sys.argv:
            fetch_expense(g, year)
        if etxt.exists():
            subprocess.run([sys.executable, str(ROOT / "scripts" / "parse_expense_docs.py"), g["key"], year, str(etxt), "--name", g["name"], "--src", g["page"], "--date", time.strftime("%Y-%m-%d")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
