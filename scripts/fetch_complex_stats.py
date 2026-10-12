#!/usr/bin/env python3
"""한국산업단지공단 「전국산업단지현황통계」(분기) 대구 단지 행 → data/complex_stats/ (운영자 지적 2026-10-12 '산단별 생산액이 안나와').

공공데이터포털 파일데이터(유형별: 국가·일반·도시첨단·농공 …)를 받는다. 포털 안내(2026-09-21 판): '25년 3분기부터 생산액·수출액·고용
항목 공표를 일시 중지'(직접 조사 → DB 기반 산출 전환) — 최신 판에는 면적·입주·가동업체만 있다. 그래서 생산액이 실린 옛 분기 판은
웨이백 머신(web.archive.org)에 남은 자료 페이지 스냅샷에서 첨부 id(atchFileId)를 뽑아 포털에서 내려받는다(nps_backfill.py 와 같은 방식).
  python3 scripts/fetch_complex_stats.py --list     # 데이터셋·스냅샷·첨부 id 만 출력
  python3 scripts/fetch_complex_stats.py            # 받아 대구 행만 data/complex_stats/<YYYYQn>_<유형>.csv + index.json
전국 원본은 저장하지 않는다. 값은 원본 그대로(단위는 열 이름에 적힌 대로), 평가 없음. 표준 라이브러리 + requests.
"""
from __future__ import annotations

import argparse, csv, io, json, re, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "complex_stats"
PAGE = "https://www.data.go.kr/data/{pk}/fileData.do"
CDX = "https://web.archive.org/cdx/search/cdx"
WB = "https://web.archive.org/web/{ts}id_/{url}"
DL = "https://www.data.go.kr/cmm/cmm/fileDownload.do"
DL_NEW = "https://www.data.go.kr/tcs/dss/selectFileDataDownload.do"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
# 포털 검색(2026-10-12)으로 확인한 번호. 나머지 유형은 --search 로 찾아 더한다
KNOWN = {"15085886": "일반", "15085878": "농공", "15085876": "노후"}
SEARCH_WORDS = ["전국산업단지현황통계"]


def get(sess: requests.Session, url: str, **kw) -> requests.Response | None:
    to = kw.pop("timeout", 90)
    for wait in (0, 15, 40, 90):   # 웨이백은 429 를 자주 돌려준다
        if wait:
            time.sleep(wait)
        try:
            r = sess.get(url, headers=UA, timeout=to, **kw)
        except Exception as e:  # noqa: BLE001
            print(f"   접속 실패 {url[:90]}: {str(e)[:80]}")
            continue
        if r.status_code in (429, 503):
            continue
        return r
    return None


def find_datasets(sess: requests.Session) -> dict[str, str]:
    sets = dict(KNOWN)
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from fetch_datago import search   # noqa: E402
        for w in SEARCH_WORDS:
            for pk, title, _ in search(w, sess, pages=2):
                t = re.sub(r"\s+", "", title)
                m = re.search(r"전국산업단지현황통계_?(\S+)", t)
                if "산업단지공단" in t and m:
                    sets.setdefault(pk, m.group(1))
    except Exception as e:  # noqa: BLE001
        print(f"검색 실패: {e}")
    return sets


def snapshots(sess: requests.Session, pk: str) -> list[str]:
    r = get(sess, CDX, params={"url": f"data.go.kr/data/{pk}/fileData.do", "output": "json", "from": "2022",
                               "filter": "statuscode:200", "collapse": "digest"}, timeout=60)
    if r is None or r.status_code != 200:
        return []
    try:
        return [row[1] for row in r.json()[1:]]
    except ValueError:
        return []


def ids_in(html: str) -> tuple[list[str], list[str]]:
    uddis = list(dict.fromkeys(re.findall(r"uddi:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", html)))
    atchs = list(dict.fromkeys(re.findall(r"FILE_\d{12,}", html)))
    return uddis, atchs


def resolve(sess: requests.Session, pk: str, uddi: str) -> str:
    try:
        r = sess.post(DL_NEW, data={"publicDataPk": pk, "publicDataDetailPk": uddi, "fileDetailSn": "1"},
                      headers={**UA, "Referer": PAGE.format(pk=pk)}, timeout=60)
        m = re.search(r'"atchFileId"\s*:\s*"(FILE_\d+)"', r.text)
        return m.group(1) if m else ""
    except Exception:  # noqa: BLE001
        return ""


def fetch_file(sess: requests.Session, pk: str, atch: str) -> tuple[str, bytes] | None:
    try:
        r = sess.get(DL, params={"atchFileId": atch, "fileDetailSn": "1"}, headers={**UA, "Referer": PAGE.format(pk=pk)}, timeout=120)
    except Exception as e:  # noqa: BLE001
        print(f"   받기 실패 {atch}: {e}")
        return None
    if r.status_code != 200 or "text/html" in r.headers.get("Content-Type", ""):
        print(f"   {atch}: HTTP {r.status_code} {r.headers.get('Content-Type', '')[:30]} — 파일 아님")
        return None
    cd = requests.utils.unquote(r.headers.get("Content-Disposition", ""))
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
    return (m.group(1) if m else f"{atch}.csv"), r.content


def decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def quarter_of(name: str) -> str:
    """'(26년2분기)농공.csv' · '…_20250630' → '2026Q2'."""
    m = re.search(r"(\d{2,4})년\s*(\d)\s*분기", name)
    if m:
        y = int(m.group(1)); y = y + 2000 if y < 100 else y
        return f"{y}Q{m.group(2)}"
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", name)
    if m:
        return f"{m.group(1)}Q{(int(m.group(2)) - 1) // 3 + 1}"
    return ""


def daegu_rows(text: str) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return [], []
    head = [h.strip() for h in rows[0]]
    si = next((i for i, h in enumerate(head) if h in ("시도", "시·도", "지역")), 1)
    return head, [[c.strip() for c in r] for r in rows[1:] if len(r) > si and r[si].strip().startswith("대구")]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    sess = requests.Session()
    OUT.mkdir(parents=True, exist_ok=True)
    idx_path = OUT / "index.json"
    index = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"files": []}
    done = {(f["quarter"], f["type"]) for f in index["files"]}
    sets = find_datasets(sess)
    print("데이터셋:", sets)
    for pk, typ in sets.items():
        atchs: list[str] = []
        live = get(sess, PAGE.format(pk=pk), timeout=60)
        if live is not None and live.status_code == 200:
            u, at = ids_in(live.text)
            atchs += at
        snaps = snapshots(sess, pk)
        print(f"[{pk} {typ}] 웨이백 스냅샷 {len(snaps)}개: {snaps[:20]}")
        for ts in snaps:
            r = get(sess, WB.format(ts=ts, url=PAGE.format(pk=pk)))
            if r is None or r.status_code != 200:
                continue
            u, at = ids_in(r.text)
            if not at and u:
                at = [x for x in (resolve(sess, pk, uu) for uu in u[:2]) if x]
            print(f"   {ts}: uddi {u[:1]} atch {at[:3]}")
            atchs += at
            time.sleep(4)
        atchs = list(dict.fromkeys(atchs))
        print(f"[{pk} {typ}] 첨부 id {len(atchs)}개: {atchs}")
        if a.list:
            continue
        for atch in atchs:
            got = fetch_file(sess, pk, atch)
            if not got:
                continue
            name, raw = got
            q = quarter_of(name)
            head, rows = daegu_rows(decode(raw))
            print(f"   {atch} → {name} ({len(raw):,} bytes) 분기 {q or '?'} · 열 {len(head)} · 대구 {len(rows)}행")
            print(f"     열: {head}")
            if not q or not rows or (q, typ) in done:
                continue
            dest = OUT / f"{q}_{typ}.csv"
            with dest.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f); w.writerow(head); w.writerows(rows)
            index["files"].append({"quarter": q, "type": typ, "file": dest.name, "orig": name, "atch": atch, "pk": pk,
                                   "has_production": any("생산" in h for h in head), "rows": len(rows)})
            done.add((q, typ))
            time.sleep(1.5)
    if not a.list:
        index["files"].sort(key=lambda f: (f["quarter"], f["type"]))
        index["note"] = "한국산업단지공단 전국산업단지현황통계(공공데이터포털). 2025년 3분기부터 생산액·수출액·고용 공표 일시 중지(포털 안내)."
        idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"저장: {len(index['files'])}개 파일")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
