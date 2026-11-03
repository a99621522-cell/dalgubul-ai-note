#!/usr/bin/env python3
"""감사원 감사결과 공개문에서 부가가치세 지적을 찾아 발췌한다(운영자 2026-11-03 '감사원 감사 지적사항도 포함시켜').

감사원 누리집(bai.go.kr)은 Nuxt 화면이지만 API 가 열려 있다(2026-11-03 확인, 이 세션에서 직접 호출):
  목록  GET  https://www.bai.go.kr/api/bak/dar/AWUBAKDAR001E?searchType=0&searchText=&fromRegiDt=YYYYMMDD&toRegiDt=YYYYMMDD&size=100&page=N
        (Accept: application/json, text/plain, */* 가 없으면 406; searchYear 는 안 먹고 fromRegiDt/toRegiDt 로 해마다; 응답 _embedded.aWUBAKDAR001EDtoList[{srno,openDt,audSphDtlNm,titNm,audKndNm}])
  상세  GET  …/AWUBAKDAR001E/<srno>  → commonFileOpenDtoList[{fileId,fileSn,fileName}]
  파일  POST https://www.bai.go.kr/api/files/download  {"fileId","fileSn"} → 첨부(공개문 PDF; 2016년 이전은 배포용 HWP·CSD 라 글자를 못 읽는다)
  누리집 상세 화면: https://www.bai.go.kr/bai/result/branch/detail?srno=<srno>
감사 분야가 지방자치단체·지방재정·지방세인 보고서(제목에 지방공기업·공유재산이 든 것 포함)의 PDF 를 받아 pdftotext 로 쪽마다 글자를 뽑고
부가가치세·매입세액·경정청구·세금계산서가 나온 문단만 data/vat/audits/bai/<srno>.json 에 남긴다(원문 PDF 는 저장하지 않음, 보고서는 이미 이름을 가린 공개문).
값·문장 그대로, 평가 없음. 전화번호 꼴은 지운다.

사용: python3 scripts/fetch_bai_vat.py [--from 2015] [--to 2026] [--srno 3189,2895] [--all-fields] [--sleep 1.0] [--probe]
"""
from __future__ import annotations
import argparse, datetime as dt, json, re, subprocess, sys, tempfile, time
from pathlib import Path

API = "https://www.bai.go.kr/api"
UA = "Mozilla/5.0 (compatible; daitda-vat/1.0; +https://vat-daitda.pages.dev/vat/)"
OUT = Path("data/vat/audits/bai"); OUT.mkdir(parents=True, exist_ok=True)
IDX = OUT / "index.json"
FIELDS = {"지방자치단체", "지방재정", "지방세"}
TITLE_RE = re.compile(r"지방공|공유재산|지방재정|지자체|시·군|시군|구청|도시공사|시설관리|공단(?!계)")
KW = re.compile(r"부가가치세|매입세액|경정청구|세금계산서|과세사업|면세사업")
VAT_RE = re.compile(r"부가가치세|부가세|매입세액|매출세액")
COMPL_RE = re.compile(r"매입세액|경정청구|환급|신고|납부|공제|가산세|합계표|안분|납세|과세표준|불공제|과세사업|면세사업|세금계산서")
def is_core(text: str) -> bool:
    """부가세 신고·납부와 닿는 문단: 부가가치세(또는 매입·매출세액) 낱말과 신고·공제·환급 같은 낱말이 함께 있는 것. 계약 금액 '부가가치세 포함' 줄, 지방세 경정청구, 보조금 정산의 세금계산서 위조는 mention"""
    return bool(VAT_RE.search(text) and COMPL_RE.search(text) and not re.fullmatch(r".*부가가치세\s*(포함|제외|별도).*", text.replace("\n", " ")) or re.search(r"매입세액|부가가치세\s*(신고|환급|공제|납부|가산세|경정|예수)", text))
HEAD_RE = re.compile(r"^\s*(?:\d+\.\s|[가-힣]\.\s|\(\d+\)\s|【|\[).{4,80}(부적정|소홀|미흡|부당|관련|누락|미이행|미반납|미징수|미환급|과다|개선)\s*$")
PHONE = re.compile(r"0\d{1,2}-\d{3,4}-\d{4}")


def curl(url: str, post: dict | None = None, out: Path | None = None, timeout: int = 120) -> bytes:
    cmd = ["curl", "-sS", "-m", str(timeout), "-A", UA, "-H", "Accept: application/json, text/plain, */*", "-H", "Referer: https://www.bai.go.kr/bai/result/branch/list/"]
    if post is not None:
        cmd += ["-H", "Content-Type: application/json;charset=UTF-8", "-X", "POST", "--data", json.dumps(post, ensure_ascii=False)]
    if out:
        cmd += ["-o", str(out)]
    cmd.append(url)
    for i in range(4):
        r = subprocess.run(cmd, capture_output=True, timeout=timeout + 30)
        if r.returncode == 0 and (out and out.exists() and out.stat().st_size > 0 or (not out and r.stdout)):
            return r.stdout if not out else out.read_bytes()[:4]
        print(f"  [{i + 1}] curl {r.returncode} {url[-50:]} {r.stderr.decode('utf-8', 'ignore')[:100].strip()}", flush=True)
        time.sleep(4 * (i + 1))
    return b""


def list_year(y: int) -> list[dict]:
    rows: list[dict] = []
    for page in range(0, 20):
        raw = curl(f"{API}/bak/dar/AWUBAKDAR001E?searchType=0&searchText=&fromRegiDt={y}0101&toRegiDt={y}1231&searchYear=&audSphCd=&audSphDtlCd=&audKndCd=&size=100&index=0&page={page}")
        try:
            d = json.loads(raw.decode("utf-8", "ignore"))
        except Exception:
            print(f"  목록 {y} p{page} 못 읽음"); break
        L = d.get("_embedded", {}).get("aWUBAKDAR001EDtoList", [])
        rows += L
        pg = d.get("page") or {}
        if page + 1 >= int(pg.get("totalPages") or 1) or not L:
            break
        time.sleep(0.8)
    return rows


def detail(srno: int) -> dict:
    raw = curl(f"{API}/bak/dar/AWUBAKDAR001E/{srno}")
    try:
        return json.loads(raw.decode("utf-8", "ignore"))
    except Exception:
        return {}


def files_of(d: dict) -> list[dict]:
    seen = set(); out = []
    for f in (d.get("commonFileOpenDtoList") or []) + (d.get("commonFileDetailDtoList") or []):
        k = (f.get("fileId"), f.get("fileSn"))
        if k in seen or not f.get("fileId"):
            continue
        seen.add(k); out.append({"fileId": f["fileId"], "fileSn": f["fileSn"], "name": f.get("fileName") or "", "size": f.get("fileSize")})
    return out


def pdf_pages(pdf: Path) -> list[str]:
    txt = pdf.with_suffix(".txt")
    for args in (["-layout"], []):
        subprocess.run(["pdftotext", *args, str(pdf), str(txt)], capture_output=True, timeout=600)
        if txt.exists() and txt.stat().st_size > 2000:
            t = txt.read_text("utf-8", "ignore")
            if KW.search(t) or len(t) > 20000:
                return t.split("\f")
    return txt.read_text("utf-8", "ignore").split("\f") if txt.exists() else []


def excerpts(pages: list[str], cap: int = 15) -> list[dict]:
    hits: list[dict] = []; seen: set[str] = set()
    for pi, page in enumerate(pages, 1):
        lines = page.split("\n")
        for li, line in enumerate(lines):
            if not KW.search(line):
                continue
            a, b = max(0, li - 6), min(len(lines), li + 7)
            chunk = re.sub(r"[ \t]+", " ", "\n".join(l.strip() for l in lines[a:b] if l.strip()))
            chunk = PHONE.sub("(전화)", chunk)[:700]
            key = re.sub(r"\W", "", line)[:60]   # 같은 줄이 두 문단에 걸리면 한 번만
            if key in seen:
                continue
            seen.add(key)
            rel = "core" if is_core(chunk) else "mention"
            head = ""
            for j in range(li, max(-1, li - 80), -1):
                if HEAD_RE.match(lines[j]):
                    head = lines[j].strip()[:100]; break
            hits.append({"page": pi, "kw": KW.search(line).group(0), "rel": rel, "head": head, "text": chunk})
            if len(hits) >= cap:
                return hits
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="y0", type=int, default=2015)
    ap.add_argument("--to", dest="y1", type=int, default=dt.date.today().year)
    ap.add_argument("--srno", default="")
    ap.add_argument("--all-fields", action="store_true")
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--rescore", action="store_true", help="받아 둔 발췌 JSON 의 rel(core/mention)·중복만 다시 매김(내려받기 없음)")
    a = ap.parse_args()
    if a.rescore:
        idx: dict = json.loads(IDX.read_text("utf-8")) if IDX.exists() else {}
        for p in sorted(OUT.glob("*.json")):
            if p.name == "index.json":
                continue
            d = json.loads(p.read_text("utf-8")); seen: set[str] = set(); hs = []; prev = ""
            for h in d.get("hits", []):
                h["rel"] = "core" if is_core(h["text"]) else "mention"
                k = re.sub(r"\W", "", h["text"])[:60]
                mid = re.sub(r"\W", "", h["text"])[100:160]
                if k in seen or (mid and mid in prev):   # 앞 문단과 겹치는 창은 하나만
                    continue
                seen.add(k); hs.append(h); prev = re.sub(r"\W", "", h["text"])
            d["hits"] = hs; p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            if str(d.get("srno")) in idx:
                idx[str(d["srno"])]["hits"] = len(hs); idx[str(d["srno"])]["core"] = sum(1 for h in hs if h["rel"] == "core")
        IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8"); print("rescored", len(idx)); return
    idx: dict = json.loads(IDX.read_text("utf-8")) if IDX.exists() else {}
    targets: list[dict] = []
    if a.srno:
        targets = [{"srno": int(s), "openDt": "", "audSphDtlNm": "", "titNm": "", "audKndNm": ""} for s in a.srno.split(",")]
    else:
        for y in range(a.y0, a.y1 + 1):
            rows = list_year(y)
            sel = [r for r in rows if a.all_fields or (r.get("audSphDtlNm") in FIELDS) or TITLE_RE.search(r.get("titNm") or "")]
            print(f"[bai] {y}: 공개문 {len(rows)}건 가운데 지방 분야 {len(sel)}건", flush=True)
            targets += sel
            time.sleep(0.8)
    if a.probe:
        for r in targets[:50]:
            print(" ", r["srno"], r["openDt"], r.get("audSphDtlNm"), "|", r["titNm"][:60], "|", r.get("audKndNm"))
        return
    tmp = Path(tempfile.mkdtemp(prefix="bai_"))
    done = 0
    for r in targets:
        s = str(r["srno"])
        if s in idx and idx[s].get("status") in ("done", "hwp", "nofile") and not a.redo:
            continue
        d = detail(r["srno"])
        if not d:
            idx[s] = {"status": "fail", "title": r.get("titNm", ""), "openDt": r.get("openDt", "")}; continue
        meta = {"srno": r["srno"], "title": d.get("titNm") or r.get("titNm", ""), "openDt": d.get("openDt") or r.get("openDt", ""), "field": d.get("audSphDtlNm") or r.get("audSphDtlNm") or "", "kind": d.get("audKndNm") or r.get("audKndNm") or "", "url": f"https://www.bai.go.kr/bai/result/branch/detail?srno={r['srno']}"}
        fl = files_of(d)
        pdfs = [f for f in fl if f["name"].lower().endswith(".pdf")]
        if not fl:
            idx[s] = {**meta, "status": "nofile", "hits": 0}; print(f"  {s} 첨부 없음 — {meta['title'][:40]}"); continue
        if not pdfs:
            idx[s] = {**meta, "status": "hwp", "hits": 0, "files": [f["name"] for f in fl]}; print(f"  {s} PDF 없음({fl[0]['name'][-12:]}) — {meta['title'][:40]}"); continue
        hits_all: list[dict] = []; names = []
        for f in pdfs:
            p = tmp / f"{s}_{f['fileSn']}.pdf"
            curl(f"{API}/files/download", post={"fileId": f["fileId"], "fileSn": f["fileSn"]}, out=p, timeout=300)
            if not p.exists() or p.stat().st_size < 1000:
                print(f"  {s} 내려받기 실패 {f['name'][:40]}"); continue
            names.append(f["name"])
            try:
                pages = pdf_pages(p)
            except Exception as e:
                print(f"  {s} pdftotext 실패 {e}"); pages = []
            hs = excerpts(pages)
            for h in hs:
                h["file"] = f["name"]
            hits_all += hs
            p.unlink(missing_ok=True); p.with_suffix(".txt").unlink(missing_ok=True)
            time.sleep(a.sleep)
        idx[s] = {**meta, "status": "done", "hits": len(hits_all), "core": sum(1 for h in hits_all if h.get("rel") == "core"), "files": names}
        if hits_all:
            (OUT / f"{s}.json").write_text(json.dumps({**meta, "files": names, "fetched": dt.date.today().isoformat(), "hits": hits_all}, ensure_ascii=False, indent=1), encoding="utf-8")
        done += 1
        print(f"  {s} {meta['openDt']} {meta['title'][:40]} — 부가가치세 문단 {len(hits_all)}", flush=True)
        IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    n_hit = sum(1 for v in idx.values() if v.get("hits"))
    print(f"[bai] 처리 {done}건 · 색인 {len(idx)}건 · 부가가치세 문단이 있는 보고서 {n_hit}건 → {OUT}", flush=True)


if __name__ == "__main__":
    main()
