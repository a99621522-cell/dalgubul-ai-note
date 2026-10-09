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


def pdf_text(link: str) -> str:
    if not link or not shutil.which("pdftotext"):
        return ""
    url = link if link.startswith("http") else "https://www.law.go.kr" + link
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


def main():
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
    first = [True]
    PROBED: list = []

    def one(t):
        # 자치법규 본문(lawService target=ordin)에는 별표가 없어 별표서식 목록(lawSearch target=ordinbyl, 해당 자치법규명 검색)으로 받는다
        q = t["name"].replace("·", " ").replace("ㆍ", " ")
        root = F.xml(F.get("lawSearch.do", target="ordinbyl", query=q, search=2, display=100))
        if root is None:
            return {**t, "fail": 1}
        p = probe and first[0]
        first[0] = False
        rows = [{c.tag: (c.text or "").strip() for c in it} for it in root if len(it)]
        if rows and not PROBED:
            PROBED.append(1)
            print("  [probe] ordinbyl 행 수", len(rows), "필드:", {k: v[:60] for k, v in rows[0].items()}, flush=True)
        out = []
        for r in rows:
            nm = next((v for k, v in r.items() if "자치법규명" in k or "법규명" in k), "")
            if norm_name(nm) != norm_name(t["name"]) and t["mst"] not in r.values():
                continue
            pdf = next((v for k, v in r.items() if "PDF" in k and "링크" in k and v), "")
            body = pdf_text(pdf)
            out.append({"no": r.get("별표번호", ""), "br": r.get("별표가지번호", ""), "kind": r.get("별표종류") or r.get("별표구분", ""),
                        "title": next((v for k, v in r.items() if k in ("별표명", "별표서식명", "별표제목") and v), ""), "text": body[:MAXC], "src": "PDF" if body else "",
                        "link": pdf or r.get("별표서식파일링크", "")})
        return {**t, "annex": out, "rows": len(rows)}

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
