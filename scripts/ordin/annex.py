"""상위법령·자치법규 별표 본문 받기(러너 전용: 이 세션은 law.go.kr 차단).

config/ordinance_annex.yml 의 laws(시행령·시행규칙) 현행 별표와, ordin 정규식에 맞는 대구 자치법규의 별표를
국가법령정보센터 오픈API(lawService target=law / ordin)에서 받아 data/ordinance/annex/{laws,ordin}.json.gz 와 summary.md 로 남긴다.
별표 본문 글자가 비어 있고 PDF 링크가 있으면 PDF 를 받아 pdftotext 로 글자를 뽑는다(없으면 링크만).
조례 금액·요율이 별표 범위 안인지 대조는 사람이 한다(판정 아님).
"""
from __future__ import annotations

import gzip
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch as F  # noqa: E402
from refs import norm_name  # noqa: E402

ROOT = F.ROOT
OUT = ROOT / "data" / "ordinance" / "annex"
CFG = yaml.safe_load((ROOT / "config" / "ordinance_annex.yml").read_text(encoding="utf-8"))
MAXC = 40000
DIAG: list = []


def pdf_text(link: str) -> str:
    if not link or not shutil.which("pdftotext"):
        return ""
    url = link if link.startswith("http") else "https://www.law.go.kr" + link
    url = url.replace("http://", "https://", 1)
    try:
        r = F.sess().get(url, timeout=90)
        if r.status_code != 200 or not r.content[:5].startswith(b"%PDF"):
            return ""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.pdf"
            p.write_bytes(r.content)
            subprocess.run(["pdftotext", "-layout", str(p), str(p.with_suffix(".txt"))], check=False, timeout=120)
            t = p.with_suffix(".txt")
            return t.read_text(encoding="utf-8", errors="ignore") if t.exists() else ""
    except Exception as e:  # noqa: BLE001
        print("  PDF 실패", url[:80], type(e).__name__, flush=True)
        return ""


def file_text(link: str) -> tuple[str, str]:
    """별표 파일(HWPX·HWP·PDF)을 받아 글자를 뽑는다 → (글자, 형식)."""
    if not link:
        return "", ""
    url = link if link.startswith("http") else "https://www.law.go.kr" + link
    url = url.replace("http://", "https://", 1)
    try:
        r = F.sess().get(url, timeout=90)
        b = r.content if r.status_code == 200 else b""
    except Exception as e:  # noqa: BLE001
        print("  파일 실패", url[:80], type(e).__name__, flush=True)
        return "", ""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "a"
        p.write_bytes(b)
        if b[:4] == b"PK\x03\x04":   # HWPX(zip)
            import zipfile
            try:
                z = zipfile.ZipFile(p)
                xs = sorted(n for n in z.namelist() if re.match(r"Contents/section\d+\.xml", n))
                t = " ".join(re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", "ignore")) for n in xs)
                return re.sub(r"\s+", " ", t), "HWPX"
            except Exception:  # noqa: BLE001
                return "", ""
        if b[:5] == b"%PDF-" and shutil.which("pdftotext"):
            subprocess.run(["pdftotext", "-layout", str(p), str(p) + ".txt"], check=False, timeout=120)
            q = Path(str(p) + ".txt")
            return (q.read_text(encoding="utf-8", errors="ignore"), "PDF") if q.exists() else ("", "")
        if b[:8] == bytes.fromhex("d0cf11e0a1b11ae1"):
            exe = shutil.which("hwp5txt")
            if not exe:
                if not DIAG:
                    DIAG.append(1)
                    print("  [diag] hwp5txt 없음", flush=True)
                return "", ""
            try:
                o = subprocess.run([exe, str(p)], capture_output=True, timeout=120)
                if not o.stdout.strip() and len(DIAG) < 3:
                    DIAG.append(1)
                    print("  [diag] hwp5txt 실패:", o.returncode, o.stderr.decode("utf-8", "ignore")[-400:], flush=True)
                return o.stdout.decode("utf-8", "ignore"), "HWP"
            except Exception as e:  # noqa: BLE001
                print("  [diag] hwp5txt 예외", type(e).__name__, flush=True)
                return "", ""
        if b[:16] == b"HWP Document Fil" and shutil.which("soffice"):   # 한글 97(3.0) — LibreOffice hwpfilter
            q = Path(td) / "a.hwp"
            q.write_bytes(b)
            try:
                subprocess.run(["soffice", f"-env:UserInstallation=file://{td}/lo", "--headless", "--convert-to", "txt:Text (encoded):UTF8", "--outdir", td, str(q)],
                               capture_output=True, timeout=180)
            except Exception as e:  # noqa: BLE001
                print("  [diag] soffice 예외", type(e).__name__, flush=True)
            t = Path(td) / "a.txt"
            if t.exists():
                return t.read_text(encoding="utf-8", errors="ignore"), "HWP97"
            if len(DIAG) < 5:
                DIAG.append(1)
                print("  [diag] soffice 변환 결과 없음", flush=True)
            return "", ""
        if len(DIAG) < 5:
            DIAG.append(1)
            print("  [diag] 알 수 없는 형식:", b[:16], len(b), flush=True)
    return "", ""


def annexes(root, probe=False) -> list[dict]:
    out = []
    for u in root.iter():
        if u.tag not in ("별표단위", "별표"):
            continue
        kids = list(u)
        if not kids or all(k.tag in ("별표단위",) for k in kids):
            continue
        d = {k.tag: re.sub(r"[ \t]+", " ", (k.text or "")).strip() for k in kids}
        if probe and not out:
            print("  [probe] 별표 태그:", {k: v[:60] for k, v in d.items()}, flush=True)
        body = next((v for k, v in d.items() if k.endswith("내용") and v), "")
        link = next((v for k, v in d.items() if "PDF" in k and v), "") or next((v for k, v in d.items() if "링크" in k and v), "")
        src = "본문"
        if not body and "PDF" in "".join(d):
            body, src = pdf_text(next((v for k, v in d.items() if "PDF" in k and v), "")), "PDF"
        out.append({"no": d.get("별표번호", ""), "br": d.get("별표가지번호", ""), "kind": d.get("별표구분", ""),
                    "title": d.get("별표제목", ""), "text": body[:MAXC], "src": src if body else "", "link": link})
    return out


def debug(name: str):
    for kw in ({}, {"knd": 1}, {"knd": 2}):
        for sv in (1, 2):
            root = F.xml(F.get("lawSearch.do", target="ordinbyl", query=name, search=sv, display=100, **kw))
            rows = [{c.tag: (c.text or "").strip() for c in it} for it in root if len(it)] if root is not None else []
            print(f"[debug] {name} search={sv} {kw} 행 {len(rows)} totalCnt {root.findtext('totalCnt') if root is not None else '-'}", flush=True)
            for r in rows[:12]:
                print("   ", r.get("별표종류"), r.get("별표번호"), r.get("별표명", "")[:40], r.get("관련자치법규일련번호"), re.sub(r"<[^>]+>", "", r.get("관련자치법규명", ""))[:40], flush=True)


def main():
    import os
    if os.environ.get("ANNEX_DEBUG"):
        debug(os.environ["ANNEX_DEBUG"])
        return
    probe = "--probe" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    cur = F.current_laws()
    laws = []
    for i, nm in enumerate(CFG.get("laws") or []):
        v = cur.get(norm_name(nm))
        if not v:
            print("  현행 법령 없음:", nm, flush=True)
            laws.append({"name": nm, "missing": 1})
            continue
        root = F.xml(F.get("lawService.do", timeout=120, target="law", MST=v["mst"]))
        ax = annexes(root, probe and i == 0) if root is not None else []
        laws.append({"name": v["name"], "prom": v.get("prom"), "eff": v.get("eff"), "annex": ax})
        print(f"  {v['name']} 별표 {len(ax)} (글자 있음 {sum(1 for a in ax if a['text'])})", flush=True)
    F.jdump(OUT / "laws.json.gz", laws, gz=True)

    rx = re.compile(CFG.get("ordin") or "$^")
    targets = []
    for f in sorted((ROOT / "data" / "ordinance" / "ordin").glob("*.json.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            it = json.load(fh)["items"]
        for d in (it if isinstance(it, list) else it.values()):
            if rx.search(d["name"]):
                targets.append({k: d[k] for k in ("org", "id", "mst", "name")})
    print(f"자치법규 대상 {len(targets)}", flush=True)
    old = {}
    for o in F.jload(OUT / "ordin.json.gz", []) or []:
        for a in o.get("annex") or []:
            if a.get("text") and a.get("id"):
                old[a["id"]] = a
    first = [True]
    PROBED: list = []
    PROBED2: list = []

    def one(t):
        root = F.xml(F.get("lawService.do", target="ordin", MST=t["mst"]))
        if root is None:
            return {**t, "fail": 1}
        out = []
        for u in root.iter("별표단위"):
            d = {k.tag: (k.text or "").strip() for k in u}
            if not PROBED:
                PROBED.append(1)
                print("  [probe] 자치법규 별표단위:", {k: v[:60] for k, v in d.items()}, flush=True)
            kind = d.get("별표구분") or d.get("별표종류") or ""
            title = d.get("별표제목") or d.get("별표명") or ""
            if title.startswith("[별지") or "서식]" in title[:16]:   # 별표구분은 별표도 '서식'으로 와서 제목으로 가른다
                continue
            bid = d.get("별표키") or f"{t['mst']}-{d.get('별표번호', '')}-{d.get('별표가지번호', '')}"
            if bid in old:
                out.append(old[bid])
                continue
            body = next((v for k, v in d.items() if k.endswith("내용") and v), "")
            src = "본문" if body else ""
            links = [v for k, v in d.items() if ("링크" in k or "파일명" in k) and v.startswith("http")]
            if not body and F.left() > 600:
                for ln in sorted(links, key=lambda x: 0 if "PDF" in x.upper() else 1):
                    body, src = file_text(ln)
                    if body:
                        break
            out.append({"id": bid, "no": d.get("별표번호", ""), "br": d.get("별표가지번호", ""), "kind": kind, "title": title,
                        "text": re.sub(r"[ \t]+", " ", body)[:MAXC], "src": src if body else "", "link": links[0] if links else ""})
        return {**t, "annex": out}

    ords = F.pmap(one, targets, "자치법규 별표")
    F.jdump(OUT / "ordin.json.gz", ords, gz=True)
    md = ["# 별표 본문 받기(자동, 판정 아님)", "", "출처: 국가법령정보센터 오픈API. 본문이 없으면 PDF(pdftotext)로 뽑았다.", "", "## 상위법령", ""]
    for L in laws:
        md.append(f"- {L['name']}: " + ("현행 법령 못 찾음" if L.get("missing") else
                  ", ".join(f"별표{a['no'].lstrip('0')}{('의' + a['br'].lstrip('0')) if a['br'].strip('0') else ''} {a['title'][:30]}({a['src'] or '글자 없음'})" for a in L["annex"][:40])))
    md += ["", "## 자치법규", "", "| 기관 | 자치법규 | 별표 수 | 글자 있음 |", "|---|---|---|---|"]
    for o in ords:
        ax = o.get("annex") or []
        md.append(f"| {o['org']} | {o['name']} | {len(ax)} | {sum(1 for a in ax if a['text'])} |")
    (OUT / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("끝", F.STATS, flush=True)


if __name__ == "__main__":
    main()
