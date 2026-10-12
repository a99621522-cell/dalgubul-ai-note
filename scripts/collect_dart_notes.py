#!/usr/bin/env python3
"""DART 실적 설명 문구 — 대구 본사 상장회사(유가증권·코스닥)의 분기·반기·사업보고서 본문과 기업설명회(IR) 자료에서
회사가 적은 실적 변동 이유·향후 전망 문장을 골라 남긴다(운영자 지시 2026-10-12 '실적이유와 가이던스는 없어? → 1 2 다해봐').

1) 정기보고서 본문 → data/dart/report_notes.csv
   scripts/data/company_financials_q.csv 의 회사별 최근 정기보고서 2건(접수번호)을 OpenDART 공시서류원본(document.xml)으로 받아
   'IV. 이사의 경영진단 및 분석의견'(분기보고서는 생략하는 회사가 많다 — 생략이면 mdna=생략)과
   'II. 사업의 내용' 중 사업의 개요·매출 및 수주상황·기타 참고사항의 문단(표 제외)에서
   ① 이유: 실적 낱말(매출·이익·수주…) + 증감 낱말 + 원인 표현(…으로 인해·…에 따라·영향) 이 함께 든 문장
   ② 전망: 시점 낱말(향후·하반기·내년·2027년…) + 전망 표현(전망·예상·계획·목표·예정…) 이 함께 든 문장
   을 회사 문구 그대로(문장당 180자 안, 보고서당 각 4문장 안) 남긴다. 예측정보 주의 문구·회계 기준 설명은 뺀다. 평가·해석 없음.
2) 기업설명회(IR) → data/dart/ir.csv
   공시검색에서 '기업설명회(IR)개최' 공시를 골라 원문의 개최 목적·주요 내용 구절과,
   첨부 IR 자료(PDF)가 dart.fss.or.kr 에서 받아지면(robots.txt 확인) pdftotext 로 글자를 뽑아 전망·목표·가이던스 낱말이 든 줄(8줄 안)을 남긴다.
   PDF 원문은 저장하지 않는다.
API·접속 실패는 로그 후 건너뛰고 못 받은 회사는 기존 행을 남긴다. 키: DART_KEY.

사용: python3 scripts/collect_dart_notes.py [--months 15] [--probe 회사명] [--no-ir] [--no-report]
  --probe: 그 회사만, 섹션 제목·뽑은 문장·IR 첨부 페이지 구조를 로그로(저장 안 함)
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import date, timedelta
from html import unescape
from pathlib import Path
from urllib import robotparser

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / "state" / "dart_corp.json"
QCSV = ROOT / "scripts" / "data" / "company_financials_q.csv"
OUT_R = ROOT / "data" / "dart" / "report_notes.csv"
OUT_I = ROOT / "data" / "dart" / "ir.csv"
API = "https://opendart.fss.or.kr/api"
WEB = "https://dart.fss.or.kr"
UA = {"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"}
KEY = os.environ.get("DART_KEY", "").strip()
LISTED = {"Y": "유가증권", "K": "코스닥"}
CALLS = [0]
COLS_R = ["corp_code", "name", "year", "quarter", "report_nm", "mdna", "kind", "section", "sentence", "rcept_no", "url", "as_of"]
COLS_I = ["rcept_dt", "corp_code", "name", "report_nm", "purpose", "content", "pdf", "guidance", "rcept_no", "url", "att_url", "as_of"]

PERF_W = r"(매출|영업이익|순이익|이익|손실|실적|수익성|수익|판매량|판매|수주|물량|출하|가동률|원가율|마진)"
CHG_W = r"(증가|감소|개선|악화|확대|축소|흑자|적자|상승|하락|호조|부진|성장|둔화|회복|증대|저하)"
CAUSE_W = r"(으로 인해|으로 인하여|로 인해|로 인하여|에 따라|에 따른|영향으로|영향을|의 영향|덕분|때문|기인|힘입어|반영되어|으로 매출|로 매출)"
TIME_W = r"(향후|하반기|상반기|내년|차기|익년|금년|올해|중장기|앞으로|202[6-9]년|20[3-9]\d년|다음 분기|4분기|하반기에)"
FWD_W = r"(전망|예상|예정|계획|목표|기대|추진할|추진하고|노력할|것으로 보|할 것|될 것|확대할|강화할|진출할)"
BOILER = r"(예측정보|책임을 지지|보장할 수 없|보장하지|투자자는|유의하시|K-IFRS|기준서|회계정책|주석|감사인|재작성|공시대상기간)"
GUIDE_W = re.compile(r"(가이던스|guidance|outlook|전망|목표|target|계획|예상|\b20[2-3]\dE\b|E\)|Plan\b)", re.I)


def redact(e: object) -> str:
    return re.sub(r"crtfc_key=[^&\s]+", "crtfc_key=***", str(e))


def get(path: str, **params) -> dict | None:
    params["crtfc_key"] = KEY
    CALLS[0] += 1
    for attempt in (1, 2):
        try:
            r = requests.get(f"{API}/{path}", params=params, headers=UA, timeout=30)
            r.raise_for_status()
            j = r.json()
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                print(f"[dart_notes] {path} 실패: {redact(e)[:160]}")
                return None
            time.sleep(3)
    st = j.get("status")
    if st == "013":
        return {"list": []}
    if st == "020":
        print("[dart_notes] 사용 한도 초과(020) — 여기서 멈춤")
        raise SystemExit(0)
    if st != "000":
        print(f"[dart_notes] {path} 오류 {st}: {j.get('message')}")
        return None
    return j


def doc_xml(rcept_no: str) -> str:
    """공시서류원본 zip 에서 본문 XML(접수번호.xml, 없으면 가장 큰 파일) 글자"""
    try:
        r = requests.get(f"{API}/document.xml", params={"crtfc_key": KEY, "rcept_no": rcept_no}, headers=UA, timeout=90)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
    except Exception as e:  # noqa: BLE001
        print(f"[dart_notes] 원문 {rcept_no} 실패: {redact(e)[:120]}")
        return ""
    names = z.namelist()
    main = next((n for n in names if n.startswith(rcept_no) and n.endswith(".xml") and "_" not in n), None)
    main = main or max(names, key=lambda n: z.getinfo(n).file_size)
    raw = z.read(main)
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", unescape(s)).strip()


def sections(xml: str) -> list[tuple[str, int, int]]:
    """(제목, 시작, 끝) — 끝은 다음 제목 위치"""
    ts = [(clean(m.group(1)), m.start()) for m in re.finditer(r"<TITLE[^>]*>(.*?)</TITLE>", xml, re.S)]
    return [(t, s, ts[i + 1][1] if i + 1 < len(ts) else len(xml)) for i, (t, s) in enumerate(ts)]


def top_block(secs: list, pat: str, xml: str) -> str:
    """로마 숫자 장(章) 제목이 pat 에 맞는 곳부터 다음 장 제목 앞까지"""
    roman = re.compile(r"^(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)\.\s")
    for i, (t, s, _) in enumerate(secs):
        if roman.match(t) and re.search(pat, t):
            e = next((s2 for (t2, s2, _) in secs[i + 1:] if roman.match(t2)), len(xml))
            return xml[s:e]
    return ""


def paragraphs(block: str) -> list[tuple[str, str]]:
    """(소제목, 문단) — 표 안 글자는 뺀다"""
    block = re.sub(r"<TABLE.*?</TABLE>", " ", block, flags=re.S | re.I)
    out, cur = [], ""
    for m in re.finditer(r"<TITLE[^>]*>(.*?)</TITLE>|<P[^>]*>(.*?)</P>", block, re.S):
        if m.group(1) is not None:
            cur = clean(m.group(1))
        else:
            t = clean(m.group(2))
            if len(t) >= 15:
                out.append((cur, t))
    return out


def sentences(p: str) -> list[str]:
    parts = re.split(r"(?<=[다음함됨임])\.\s+|\s(?=[①-⑩]|\(\d+\)\s|[가-하]\.\s|-\s)", p)
    return [s.strip(" -·") for s in parts if s and len(s.strip()) >= 12]


def classify(s: str) -> str:
    if re.search(BOILER, s):
        return ""
    if re.search(TIME_W, s) and re.search(FWD_W, s):
        return "전망"
    if re.search(PERF_W, s) and re.search(CHG_W, s) and re.search(CAUSE_W, s):
        return "이유"
    return ""


def cut(s: str, n: int = 180) -> str:
    return s if len(s) <= n else s[:n].rstrip() + "…"


def report_notes(code: str, meta: dict, rep: dict, probe: bool) -> list[dict]:
    xml = doc_xml(rep["rcept_no"])
    time.sleep(0.3)
    if not xml:
        return []
    secs = sections(xml)
    mdna_blk = top_block(secs, r"경영진단|분석의견", xml)
    mdna_par = paragraphs(mdna_blk) if mdna_blk else []
    body = " ".join(p for _, p in mdna_par)
    if not mdna_blk:
        mdna = "없음"
    elif re.search(r"기재(하지 않|를 생략|생략)|생략(합니다|하였습니다)|해당사항 없|작성하지 않", body[:400]) or len(body) < 150:
        mdna = "생략"
    else:
        mdna = "있음"
    biz_blk = top_block(secs, r"사업의 내용", xml)
    biz_par = [(t, p) for t, p in paragraphs(biz_blk) if re.search(r"사업의 개요|영업의 (개황|현황)|매출 및 수주|기타 참고|시장 ?여건|산업의 (특성|전망)", t)]
    if probe:
        print(f"== probe {meta['name']} {rep['year']}.{rep['quarter']}Q {rep['report_nm']} 장 제목: "
              f"{[t for t, _, _ in secs if re.match(r'^[IVX]+\.', t)]}")
        print(f"   경영진단: {mdna} 문단 {len(mdna_par)} · 사업의 내용 문단 {len(biz_par)} · 앞부분: {body[:300]}")
    rows, seen = [], set()
    count = {"이유": 0, "전망": 0}
    for sec_name, pars in (("경영진단", mdna_par if mdna == "있음" else []), ("사업의 내용", biz_par)):
        for sub, p in pars:
            if re.search(r"예측정보", sub):
                continue
            for s in sentences(p):
                k = classify(s)
                if not k or count[k] >= 4 or s[:60] in seen:
                    continue
                seen.add(s[:60])
                count[k] += 1
                rows.append({"corp_code": code, "name": meta.get("name", ""), "year": rep["year"], "quarter": rep["quarter"],
                             "report_nm": rep["report_nm"], "mdna": mdna, "kind": k, "section": f"{sec_name} · {sub}"[:60],
                             "sentence": cut(s), "rcept_no": rep["rcept_no"],
                             "url": f"{WEB}/dsaf001/main.do?rcpNo={rep['rcept_no']}", "as_of": date.today().isoformat()})
                if probe:
                    print(f"   [{k}] ({sec_name}·{sub}) {cut(s)}")
    if not rows:   # 문장이 없어도 경영진단 여부는 남긴다
        rows.append({"corp_code": code, "name": meta.get("name", ""), "year": rep["year"], "quarter": rep["quarter"],
                     "report_nm": rep["report_nm"], "mdna": mdna, "kind": "", "section": "", "sentence": "",
                     "rcept_no": rep["rcept_no"], "url": f"{WEB}/dsaf001/main.do?rcpNo={rep['rcept_no']}", "as_of": date.today().isoformat()})
    return rows


# ---------- IR ----------
ROBOTS: dict[str, robotparser.RobotFileParser | None] = {}


def allowed(url: str) -> bool:
    host = re.match(r"https?://[^/]+", url).group(0)
    if host not in ROBOTS:
        rp = robotparser.RobotFileParser()
        try:
            r = requests.get(host + "/robots.txt", headers=UA, timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            print(f"[dart_notes] {host}/robots.txt HTTP {r.status_code}")
            ROBOTS[host] = rp
        except Exception as e:  # noqa: BLE001
            print(f"[dart_notes] robots.txt 실패 {host}: {str(e)[:100]} — 이 호스트는 받지 않음")
            ROBOTS[host] = None
    rp = ROBOTS[host]
    return bool(rp) and rp.can_fetch(UA["User-Agent"], url)


def web(url: str) -> requests.Response | None:
    if not allowed(url):
        print(f"[dart_notes] robots.txt 가 막음: {url}")
        return None
    try:
        r = requests.get(url, headers=UA, timeout=60)
        time.sleep(1.0)
        r.raise_for_status()
        return r
    except Exception as e:  # noqa: BLE001
        print(f"[dart_notes] 받기 실패 {url}: {str(e)[:120]}")
        return None


def field(text: str, keys: list[str], n: int = 200) -> str:
    for k in keys:
        m = re.search(re.escape(k), text)
        if m:
            s = text[m.end(): m.end() + n + 40].strip(" :-·)")
            s = re.split(r"\s\d{1,2}\s*\.\s|\s※", s)[0].strip()
            return cut(s, n)
    return ""


def pdf_lines(pdf: bytes) -> list[str]:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.pdf"
        p.write_bytes(pdf)
        try:
            t = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, timeout=120).stdout.decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            print(f"[dart_notes] pdftotext 실패: {e}")
            return []
    out, seen = [], set()
    for ln in t.splitlines():
        s = re.sub(r"\s{2,}", "  ", ln).strip()
        if len(s) < 8 or not GUIDE_W.search(s) or not re.search(r"\d", s) or re.search(BOILER, s):
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(cut(s, 150))
        if len(out) >= 8:
            break
    return out


def ir_attachment(rcept_no: str, probe: bool) -> tuple[str, list[str], str]:
    """(pdf 여부, 전망 줄, 첨부 주소) — dart.fss.or.kr 공시 화면의 첨부 선택 → PDF 내려받기"""
    page = web(f"{WEB}/dsaf001/main.do?rcpNo={rcept_no}")
    if not page:
        return "", [], ""
    html = page.text
    opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', html)
    att = [(v, clean(t)) for v, t in opts if re.search(r"rcpNo=\d+|^\d{14}$", v) and t.strip()]
    if probe:
        print(f"   IR 화면 select 옵션: {opts[:12]}")
        for m in re.finditer(r".{0,80}(dcmNo|pdf/download|download).{0,120}", html):
            print("   …", m.group(0)[:220])
    cands = [(re.search(r"\d{14}", v).group(0), t) for v, t in att if re.search(r"\d{14}", v)]
    cands = [c for c in cands if c[0] != rcept_no] or [(rcept_no, "본문")]
    for arc, name in cands:
        sub = web(f"{WEB}/dsaf001/main.do?rcpNo={arc}") if arc != rcept_no else page
        if not sub:
            continue
        dcms = re.findall(r"dcmNo['\"]?\]?\s*[=:]\s*['\"]?(\d+)", sub.text) or re.findall(r"dcmNo=(\d+)", sub.text)
        if probe:
            print(f"   첨부 {name} {arc} dcmNo 후보 {dcms[:5]}")
        for dcm in dict.fromkeys(dcms):
            url = f"{WEB}/pdf/download/pdf.do?rcp_no={arc}&dcm_no={dcm}"
            r = web(url)
            if r is not None and r.content[:4] == b"%PDF":
                lines = pdf_lines(r.content)
                if probe:
                    print(f"   PDF {len(r.content)//1024}KB 전망 줄 {len(lines)}: {lines[:4]}")
                return "예", lines, url
            if probe and r is not None:
                print(f"   {url} → PDF 아님({r.headers.get('content-type')}) {r.text[:200]!r}")
    return "아니오", [], ""


def ir_rows(code: str, meta: dict, months: int, seen: set, probe: bool, budget: list[int]) -> list[dict]:
    bgn = (date.today() - timedelta(days=months * 31)).strftime("%Y%m%d")
    out, page = [], 1
    while True:
        j = get("list.json", corp_code=code, bgn_de=bgn, end_de=date.today().strftime("%Y%m%d"), page_no=page, page_count=100)
        time.sleep(0.12)
        if not j:
            break
        for r in j.get("list", []):
            nm = " ".join((r.get("report_nm") or "").split())
            if "기업설명회" not in nm.replace(" ", "") or "철회" in nm or r["rcept_no"] in seen:
                continue
            text = clean(doc_xml(r["rcept_no"]))
            time.sleep(0.2)
            purpose = field(text, ["개최목적", "개최 목적", "목적"], 120)
            content = field(text, ["주요내용", "주요 내용", "설명회 내용", "IR 내용", "내용"], 200)
            pdf, lines, att = ("", [], "")
            if budget[0] > 0:
                budget[0] -= 1
                pdf, lines, att = ir_attachment(r["rcept_no"], probe)
            if probe:
                print(f"== probe IR {r['rcept_dt']} {nm}\n   원문 앞: {text[:500]}\n   목적: {purpose}\n   내용: {content}")
            out.append({"rcept_dt": r.get("rcept_dt", ""), "corp_code": code, "name": meta.get("name") or r.get("corp_name", ""),
                        "report_nm": nm, "purpose": purpose, "content": content, "pdf": pdf, "guidance": " / ".join(lines),
                        "rcept_no": r["rcept_no"], "url": f"{WEB}/dsaf001/main.do?rcpNo={r['rcept_no']}", "att_url": att,
                        "as_of": date.today().isoformat()})
        if page >= int(j.get("total_page") or 1):
            break
        page += 1
    return out


def latest_reports(n: int = 2) -> dict[str, list[dict]]:
    """회사별 최근 정기보고서 n건 — 분기 실적 CSV 의 접수번호(4분기는 사업보고서)"""
    if not QCSV.exists():
        return {}
    names = {1: "분기보고서(1분기)", 2: "반기보고서", 3: "분기보고서(3분기)", 4: "사업보고서"}
    by: dict[str, dict[str, dict]] = {}
    for r in csv.DictReader(open(QCSV, encoding="utf-8")):
        if not r.get("rcept_no"):
            continue
        q = int(r["quarter"])
        by.setdefault(r["corp_code"], {})[r["rcept_no"]] = {"rcept_no": r["rcept_no"], "year": r["year"], "quarter": r["quarter"],
                                                             "report_nm": f"{r['year']} {names[q]}"}
    return {c: sorted(d.values(), key=lambda x: (int(x["year"]), int(x["quarter"])), reverse=True)[:n] for c, d in by.items()}


def write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str]) -> int:
    if not KEY:
        print("DART_KEY 없음")
        return 0
    months = int(argv[argv.index("--months") + 1]) if "--months" in argv else 15
    probe = argv[argv.index("--probe") + 1] if "--probe" in argv else ""
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    corps = {c: v for c, v in cache.items() if v.get("daegu") and v.get("corp_cls") in LISTED}
    if probe:
        corps = {c: v for c, v in corps.items() if probe in (v.get("name") or "")}
    if not corps:
        print("대상 회사 없음")
        return 0
    reps = latest_reports(2)
    rrows, irows = [], []
    old_i = list(csv.DictReader(open(OUT_I, encoding="utf-8"))) if OUT_I.exists() else []
    seen_i = {r["rcept_no"] for r in old_i if r.get("pdf")}      # 첨부까지 본 공시만 건너뛴다
    budget = [80 if not probe else 3]
    for i, (code, meta) in enumerate(sorted(corps.items()), 1):
        if "--no-report" not in argv:
            for rep in reps.get(code, []):
                rrows += report_notes(code, meta, rep, bool(probe))
        if "--no-ir" not in argv:
            irows += ir_rows(code, meta, months, seen_i, bool(probe), budget)
        if i % 10 == 0:
            print(f"[dart_notes] {i}/{len(corps)}곳 · 보고서 문장 {len(rrows)} · IR {len(irows)}")
    if probe:
        print(f"[dart_notes] probe 끝 — 보고서 행 {len(rrows)}, IR {len(irows)}, API {CALLS[0]}건(저장 안 함)")
        return 0
    if "--no-report" not in argv:
        done = {r["rcept_no"] for r in rrows}
        old_r = list(csv.DictReader(open(OUT_R, encoding="utf-8"))) if OUT_R.exists() else []
        keep_codes = {c for c in corps}
        valid = {x["rcept_no"] for v in reps.values() for x in v}
        kept = [r for r in old_r if r["rcept_no"] not in done and r["rcept_no"] in valid and r["corp_code"] in keep_codes]
        out_r = sorted(kept + rrows, key=lambda r: (r["name"], -int(r["year"]), -int(r["quarter"]), r["kind"]))
        write(OUT_R, COLS_R, out_r)
        print(f"저장: {OUT_R.relative_to(ROOT)} {len(out_r)}행 · 경영진단 있음 "
              f"{len({r['rcept_no'] for r in out_r if r['mdna'] == '있음'})}건 / 보고서 {len({r['rcept_no'] for r in out_r})}건")
    if "--no-ir" not in argv:
        cutoff = (date.today() - timedelta(days=months * 31)).strftime("%Y%m%d")
        new = {r["rcept_no"] for r in irows}
        out_i = [r for r in old_i if r["rcept_no"] not in new and r["rcept_dt"] >= cutoff] + irows
        out_i.sort(key=lambda r: (r["rcept_dt"], r["rcept_no"]), reverse=True)
        write(OUT_I, COLS_I, out_i)
        print(f"저장: {OUT_I.relative_to(ROOT)} {len(out_i)}건 · PDF 받음 {sum(1 for r in out_i if r['pdf'] == '예')} · API {CALLS[0]}건")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
