#!/usr/bin/env python3
"""식품의약품안전처 「의료기기 생산 및 수·출입 실적 통계 자료」(해마다 5월쯤, mfds.go.kr 통계자료 게시판 m_386)의
'7. 지역별 생산 및 수출입실적 현황' 표 → data/mfds/device_region.csv (운영자 지시 2026-10-05: 보건산업 지역 통계 연결).

한 해 자료에 두 해(전년·당해) 값이 실린다. 표는 7-1 의료기기 전체(체외진단 포함)·7-2 체외진단 의료기기 × (1) 생산 (2) 수출 (3) 수입,
17개 시도 + 합계, 칸은 해마다 업체 수(개소)·비중·운영인원(명)·비중·금액(생산 천원, 수출입 USD)·비중. 값은 받은 그대로 옮기고
같은 해 값이 두 자료에 있으면 늦게 나온 자료 값을 쓴다(잠정→확정). 원문 글자(7절만)는 data/mfds/raw/ 에 남겨 대조한다.
게시판 robots.txt 를 확인하고, 첨부는 자료마다 한 번만 받는다(요청 사이 1초). 이 세션 환경은 mfds.go.kr 이 막혀 워크플로(mfds_device.yml)가 돈다.
사용: python3 scripts/fetch_mfds_device.py            # 받고 파싱
      python3 scripts/fetch_mfds_device.py --parse-only  # data/mfds/raw/*.txt 만 다시 파싱
"""
import argparse, csv, json, re, subprocess, sys, tempfile, time
from pathlib import Path
from urllib import robotparser

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mfds"
RAW = OUT / "raw"
BASE = "https://www.mfds.go.kr"
LIST = BASE + "/brd/m_386/list.do?srchWord=%EC%9D%98%EB%A3%8C%EA%B8%B0%EA%B8%B0+%EC%83%9D%EC%82%B0&srchTp=0"
DOWN = BASE + "/brd/m_386/down.do?brd_id=stat0021&seq={seq}&data_tp=A&file_seq={fs}"
VIEW = BASE + "/brd/m_386/view.do?seq={seq}"
UA = "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"
# 게시판 목록에서 못 찾을 때 쓰는 글 번호(2026-10-05 목록 확인: 자료 연도 → seq)
KNOWN = {2025: 33118, 2024: 33116, 2023: 33114, 2022: 33112, 2021: 33109, 2020: 33106, 2019: 33103, 2018: 33100}
# 표의 지역 칸은 지방식약청 관할 순서이고 경기는 북부·남부로 나뉜다(원문 그대로 둔다)
REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기북부", "경기남부", "강원", "충북", "충남",
           "전북", "전남", "경북", "경남", "제주", "합계"]
KINDS = {"생산": "천원", "수출": "USD", "수입": "USD"}
FIELDS = ["year", "scope", "kind", "region", "firms", "firms_share", "staff", "staff_share", "amount", "amount_share", "unit",
          "pub", "source_url"]


def discover(sess):
    """게시판 목록에서 「YYYY년(도) 의료기기 생산 및 수·출입 실적 통계 자료」 글 번호를 찾는다."""
    found = dict(KNOWN)
    try:
        html = sess.get(LIST, timeout=40).text
        for m in re.finditer(r"(20\d\d)\s*년도?\s*의료기기\s*생산\s*및\s*수[·ㆍ\s]*출입\s*실적[^<]{0,40}?</a>.{0,3000}?seq=(\d+)", html, re.S):
            found[int(m.group(1))] = int(m.group(2))
        for m in re.finditer(r"seq=(\d+)[^>]*>[^<]*?(20\d\d)\s*년도?\s*의료기기\s*생산\s*및\s*수", html):
            found[int(m.group(2))] = int(m.group(1))
    except Exception as e:
        print("  ! 목록 못 읽음 — 알려진 글 번호만:", str(e)[:120])
    return found


def section7(text):
    """pdftotext -layout 글자에서 본문 7절(목차 다음, 마지막 '7. 지역별' ~ '8. 대륙별')만."""
    starts = [m.start() for m in re.finditer(r"7\.\s*지역별\s*생산\s*및\s*수\s*출입\s*실적\s*현황", text)]
    if not starts:
        return ""
    s = starts[-1]
    e = re.search(r"\n\s*8\.\s*대륙별", text[s:])
    return text[s: s + e.start()] if e else text[s: s + 40000]


def xlsx_text(data):
    """엑셀 첨부(옛 자료)는 '지역별' 이 든 시트를 표 글자처럼 한 행 한 줄로(칸 사이 두 칸 띄움). 숫자는 원래 값(비율은 소수 둘째 자리)."""
    import io, openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        lines = []
        for row in ws.iter_rows(values_only=True):
            cells = []
            for c in row:
                if c is None or str(c).strip() == "":
                    continue
                if isinstance(c, float):
                    c = f"{int(c):,}" if c == int(c) and abs(c) >= 1 else f"{c:,.2f}"
                elif isinstance(c, int):
                    c = f"{c:,}"
                cells.append(re.sub(r"\s+", " ", str(c)).strip())
            if cells:
                lines.append("  ".join(cells))
        body = "\n".join(lines)
        print(f"    시트 「{ws.title}」 {len(lines)}줄{' ← 지역 표' if '경기북부' in body else ''}")
        if "경기북부" in body:   # 지역 표만(목차·품목 표 제외)
            out.append(f"## 시트 {ws.title}\n{body}")
    return "\n".join(out)


def num(t):
    t = t.replace(",", "")
    return "" if t in ("-", "") else t


def parse(sec, pub, url):
    rows, scope, kind, years = [], None, None, None
    for line in sec.splitlines():
        l = line.strip()
        if not l:
            continue
        if l.startswith("## 시트"): kind = None; years = None; continue
        if re.match(r"7-1\.", l): scope = "전체"; continue
        if re.match(r"7-2\.", l): scope = "체외진단"; continue
        m = re.match(r"\(\d\)\s*지역별\s*(생산|수출|수입)\s*실적", l)
        if m: kind = m.group(1); years = None; continue
        h = re.search(r"(생산|수출|수입)액", l)
        if h and not kind:   # 엑셀 시트는 '(1) 지역별 …' 머리 대신 칸 이름으로
            kind = h.group(1)
        if re.search(r"20\d\d\s*년", l) and l.split()[0] not in REGIONS and not re.search(r"\d,\d{3}", l):   # '2024년 2025년' · 엑셀은 '지역 2018년 2019년
            years = [int(y) for y in re.findall(r"(20\d\d)\s*년", l)][:2]; continue
        name = l.split()[0]
        if kind and not scope:
            scope = "전체"   # 2017년도 자료처럼 7-1 머리가 없으면 전체
        if name not in REGIONS or not (scope and kind and years):
            continue
        toks = [t for t in l.split()[1:] if re.fullmatch(r"-|-?[\d,]+(\.\d+)?%?", t)]
        if len(toks) < 6 * len(years):
            print(f"  ? {pub} {scope} {kind} {name}: 칸 {len(toks)}개 — 건너뜀 | {l[:160]}")
            continue
        for i, y in enumerate(years):
            v = [num(t) for t in toks[i * 6: i * 6 + 6]]
            rows.append({"year": y, "scope": scope, "kind": kind, "region": name, "firms": v[0], "firms_share": v[1],
                         "staff": v[2], "staff_share": v[3], "amount": v[4], "amount_share": v[5], "unit": KINDS[kind],
                         "pub": pub, "source_url": url})
    return rows


def fetch():
    import requests
    sess = requests.Session(); sess.headers["User-Agent"] = UA
    rp = robotparser.RobotFileParser()
    try:
        rp.parse(sess.get(BASE + "/robots.txt", timeout=30).text.splitlines())
        if not rp.can_fetch(UA, DOWN.format(seq=1, fs=1)):
            print("!! robots.txt 가 첨부 경로를 막음 — 받지 않는다"); return
    except Exception as e:
        print("  ! robots.txt 못 읽음:", str(e)[:120])
    RAW.mkdir(parents=True, exist_ok=True)
    meta_p = RAW / "index.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    for year, seq in sorted(discover(sess).items()):
        if str(year) in meta and (RAW / f"device_{year}.txt").exists():
            continue
        for fs in (1, 2, 3):
            url = DOWN.format(seq=seq, fs=fs)
            try:
                r = sess.get(url, timeout=120); time.sleep(1)
            except Exception as e:
                print(f"  ! {year} file_seq={fs}: {str(e)[:120]}"); continue
            if r.status_code != 200 or r.content[:4] not in (b"%PDF", b"PK\x03\x04"):
                print(f"  - {year} file_seq={fs}: {r.status_code} {r.content[:8]!r} (PDF·엑셀 아님)"); continue
            if r.content[:4] == b"%PDF":
                with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
                    t.write(r.content); t.flush()
                    text = subprocess.run(["pdftotext", "-layout", t.name, "-"], capture_output=True, text=True).stdout
                sec = section7(text)
            else:
                try:
                    text = xlsx_text(r.content)
                except Exception as e:
                    print(f"  - {year} file_seq={fs}: 엑셀 아님·못 읽음 {str(e)[:100]}"); continue
                sec = section7(text) or text
            if not sec:
                print(f"  - {year} file_seq={fs}: 7절(지역별) 없음"); continue
            (RAW / f"device_{year}.txt").write_text(sec, encoding="utf-8")
            meta[str(year)] = {"seq": seq, "file_seq": fs, "url": url, "view": VIEW.format(seq=seq), "bytes": len(r.content)}
            print(f"  + {year}년도 자료 seq={seq} file_seq={fs}: 7절 {len(sec):,}자")
            break
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build():
    meta_p = RAW / "index.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    best = {}
    for p in sorted(RAW.glob("device_*.txt")):
        pub = int(re.search(r"(\d{4})", p.stem).group(1))
        m = meta.get(str(pub), {})
        rows = parse(p.read_text(encoding="utf-8"), f"{pub}년도", m.get("view", ""))
        print(f"  {p.name}: {len(rows)}행")
        for r in rows:
            k = (r["year"], r["scope"], r["kind"], r["region"])
            if k not in best or int(best[k]["pub"][:4]) < pub:
                best[k] = r
    if not best:
        print("!! 파싱한 행 없음 — 파일을 바꾸지 않는다"); return
    order = {n: i for i, n in enumerate(REGIONS)}
    out = sorted(best.values(), key=lambda r: (r["year"], r["scope"] != "전체", list(KINDS).index(r["kind"]), order[r["region"]]))
    with (OUT / "device_region.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(out)
    print(f"== device_region.csv {len(out)}행, 연도 {sorted({r['year'] for r in out})}")
    # 검산: 시도 합 = 합계 (업체 수·금액)
    for (y, s, k) in sorted({(r["year"], r["scope"], r["kind"]) for r in out}):
        rs = [r for r in out if (r["year"], r["scope"], r["kind"]) == (y, s, k)]
        tot = next((r for r in rs if r["region"] == "합계"), None)
        if tot and tot["amount"]:
            sm = sum(float(r["amount"] or 0) for r in rs if r["region"] != "합계")
            if abs(sm - float(tot["amount"])) > max(5, float(tot["amount"]) * 0.0005):
                print(f"  ? {y} {s} {k}: 시도 합 {sm:,.0f} ≠ 합계 {float(tot['amount']):,.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parse-only", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not a.parse_only:
        fetch()
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
