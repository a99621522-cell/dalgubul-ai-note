#!/usr/bin/env python3
"""소상공인시장진흥공단 「상가(상권)정보」(공공데이터포털 파일데이터, 분기) 대구 점포 → 구·군·행정동·업종 집계 data/stores/
(운영자 지시 2026-10-26 '상가 정보랑 인구이동도 받아서 붙여' — 구·군 경제 현황 /stats/districts/).

포털 파일은 전국 zip(시도별 CSV) 하나이고 최신 분기만 보인다. 옛 분기 판은 fetch_complex_stats 와 같은 길(웨이백 스냅샷에 남은
판별 uddi → 포털 selectFileDataDownload → 첨부 id)로 받는다. 받은 첨부 id 는 index.json 에 남겨 다음 분기에 전 분기를 다시 받아
점포 번호(상가업소번호)를 맞춰 '새로 잡힌 점포·빠진 점포'를 센다(개업·폐업 신고가 아니라 이 명단에 들고 난 것).

저장하는 것은 집계뿐이다 — 상호명·주소·좌표 같은 점포 행은 저장소에 넣지 않는다.
  data/stores/gu_<YYYYQn>.csv    시군구 × 대분류 × 중분류 점포 수
  data/stores/dong_<YYYYQn>.csv  시군구 × 행정동 × 대분류 점포 수
  data/stores/flow.csv           (앞 분기, 이번 분기, 시군구, 대분류) 이번 분기 점포·새로 잡힘·빠짐
  data/stores/index.json         분기별 원 파일 이름·첨부 id·대구 점포 수·받은 날
  python3 scripts/fetch_sbiz_stores.py --list        # 식별자만
  python3 scripts/fetch_sbiz_stores.py [--history 8]  # 최근 판 + 옛 판 최대 8개 분기
표준 라이브러리 + requests.
"""
from __future__ import annotations

import argparse, csv, io, json, re, sys, tempfile, time, zipfile
from collections import Counter
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_complex_stats import PAGE, DL, UA, get, snapshots, ids_in, resolve, decode  # noqa: E402

OUT = ROOT / "data" / "stores"
PK = "15083033"   # 소상공인시장진흥공단_상가(상권)정보
DEADLINE = time.time() + 50 * 60


def quarter_of(name: str) -> str:
    m = re.search(r"(20\d{2})[._-]?(0[1-9]|1[0-2])(?:\d{2})?(?!\d)", name)
    if not m:
        return ""
    return f"{m.group(1)}Q{(int(m.group(2)) - 1) // 3 + 1}"


def download(sess: requests.Session, atch: str, dest: Path) -> str:
    """첨부 하나를 파일로 받아 원 파일 이름을 돌려준다(전국 zip 이라 메모리에 올리지 않는다)."""
    try:
        with sess.get(DL, params={"atchFileId": atch, "fileDetailSn": "1"}, headers={**UA, "Referer": PAGE.format(pk=PK)}, timeout=(30, 600), stream=True) as r:
            if r.status_code != 200 or "text/html" in r.headers.get("Content-Type", ""):
                print(f"   {atch}: HTTP {r.status_code} {r.headers.get('Content-Type', '')[:30]} — 파일 아님")
                return ""
            cd = requests.utils.unquote(r.headers.get("Content-Disposition", ""))
            m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            return m.group(1) if m else f"{atch}.zip"
    except Exception as e:  # noqa: BLE001
        print(f"   받기 실패 {atch}: {str(e)[:120]}")
        return ""


def col(head: list[str], *names: str) -> int:
    for n in names:
        for i, h in enumerate(head):
            if h.replace(" ", "") == n:
                return i
    for n in names:
        for i, h in enumerate(head):
            if n in h.replace(" ", ""):
                return i
    return -1


def daegu_stores(path: Path) -> tuple[str, list[dict]]:
    """zip(또는 CSV) 안의 대구 파일 → 점포 행(번호·시군구·행정동·대·중분류만). 돌려주는 이름은 대구 파일 이름."""
    texts: list[tuple[str, str]] = []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            pick = [n for n in names if "대구" in n] or [n for n in names if "대구" in n.encode("cp437", "ignore").decode("cp949", "ignore")]
            if not pick:
                print(f"   zip 안에 대구 파일 없음: {names[:20]}")
                return "", []
            for n in pick:
                texts.append((n, decode(z.read(n))))
    else:
        texts.append((path.name, decode(path.read_bytes())))
    out: list[dict] = []
    name = ""
    for n, text in texts:
        rows = csv.reader(io.StringIO(text))
        head = [h.strip().lstrip("﻿") for h in next(rows, [])]
        ii = {"id": col(head, "상가업소번호"), "sido": col(head, "시도명"), "gu": col(head, "시군구명"), "dong": col(head, "행정동명"),
              "l": col(head, "상권업종대분류명"), "m": col(head, "상권업종중분류명")}
        if min(ii.values()) < 0:
            print(f"   열 이름을 못 찾음({n}): {head[:30]}")
            continue
        name = n
        for r in rows:
            if len(r) <= max(ii.values()) or not r[ii["sido"]].startswith("대구"):
                continue
            out.append({k: r[i].strip() for k, i in ii.items()})
    return name, out


def save_quarter(q: str, rows: list[dict]) -> None:
    gu = Counter((r["gu"], r["l"], r["m"]) for r in rows)
    dong = Counter((r["gu"], r["dong"], r["l"]) for r in rows)
    with open(OUT / f"gu_{q}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["sigungu", "large", "middle", "stores"])
        for k in sorted(gu):
            w.writerow([*k, gu[k]])
    with open(OUT / f"dong_{q}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["sigungu", "dong", "large", "stores"])
        for k in sorted(dong):
            w.writerow([*k, dong[k]])


def flows(ids: dict[str, dict[str, tuple[str, str]]]) -> list[list]:
    """분기별 {점포 번호: (시군구, 대분류)} → 이어진 두 분기마다 새로 잡힘·빠짐."""
    qs = sorted(ids)
    out = []
    for a, b in zip(qs, qs[1:]):
        A, B = ids[a], ids[b]
        cur, new, gone = Counter(B.values()), Counter(v for k, v in B.items() if k not in A), Counter(v for k, v in A.items() if k not in B)
        for k in sorted(set(cur) | set(gone)):
            out.append([a, b, k[0], k[1], cur.get(k, 0), new.get(k, 0), gone.get(k, 0)])
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--history", type=int, default=8, help="옛 분기 판을 몇 개까지 찾을지")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    idx_path = OUT / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"quarters": {}}
    sess = requests.Session()

    # 1) 첨부 id 모으기: 지금 페이지 + 웨이백 스냅샷 + 이미 아는 것
    atchs: list[str] = []
    r = get(sess, PAGE.format(pk=PK), timeout=60)
    if r is not None and r.status_code == 200:
        uddis, found = ids_in(r.text)
        print(f"지금 페이지: uddi {len(uddis)} · 첨부 {len(found)}")
        atchs += found + [x for x in (resolve(sess, PK, u) for u in uddis) if x]
    else:
        print("포털 페이지를 못 엶")
    if a.history:
        seen_uddi: set[str] = set()
        for ts in snapshots(sess, PK)[: a.history * 3]:
            if time.time() > DEADLINE - 30 * 60:
                break
            w = get(sess, f"https://web.archive.org/web/{ts}id_/{PAGE.format(pk=PK)}", timeout=60)
            if w is None or w.status_code != 200:
                continue
            uddis, found = ids_in(w.text)
            atchs += found
            for u in uddis:
                if u not in seen_uddi:
                    seen_uddi.add(u)
                    x = resolve(sess, PK, u)
                    if x:
                        atchs.append(x)
            print(f"  스냅샷 {ts}: uddi {len(uddis)} · 첨부 {len(found)}")
            time.sleep(6)   # 웨이백 429
    atchs = list(dict.fromkeys(atchs + [v["atch"] for v in idx["quarters"].values() if v.get("atch")]))
    print(f"첨부 id {len(atchs)}개: {atchs}")
    if a.list:
        return 0

    # 2) 받아서 분기별 집계. 같은 분기는 한 번만.
    ids: dict[str, dict[str, tuple[str, str]]] = {}
    with tempfile.TemporaryDirectory() as td:
        for atch in atchs:
            if time.time() > DEADLINE:
                print("시간 한도 — 여기까지 저장")
                break
            known = next((q for q, v in idx["quarters"].items() if v.get("atch") == atch), "")
            if known and known in ids:
                continue
            p = Path(td) / f"{atch}.bin"
            fname = download(sess, atch, p)
            if not fname:
                continue
            dname, rows = daegu_stores(p)
            p.unlink(missing_ok=True)
            q = quarter_of(dname) or quarter_of(fname)
            print(f"  {atch}: {fname} / {dname} → {q or '분기 모름'} 대구 {len(rows):,}곳")
            if not q or not rows or q in ids:
                continue
            ids[q] = {r["id"]: (r["gu"], r["l"]) for r in rows if r["id"]}
            save_quarter(q, rows)
            idx["quarters"][q] = {"file": fname, "daegu_file": dname, "atch": atch, "stores": len(rows), "fetched": date.today().isoformat()}
    if not ids:
        print("받은 분기 없음")
        return 0

    # 3) 이어진 분기 쌍의 들고 남. 이번에 받은 분기끼리만 계산하고, 예전에 계산한 쌍은 그대로 둔다.
    fl_path = OUT / "flow.csv"
    old = list(csv.reader(fl_path.open(encoding="utf-8")))[1:] if fl_path.exists() else []
    new = flows(ids)
    pairs = {(x[0], x[1]) for x in new}
    rows = [x for x in old if (x[0], x[1]) not in pairs] + new
    with open(fl_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["from", "to", "sigungu", "large", "stores", "new", "gone"])
        w.writerows(sorted(rows, key=lambda x: (x[1], x[2], x[3])))
    idx["source"] = "소상공인시장진흥공단 「상가(상권)정보」(공공데이터포털 15083033)"
    idx["url"] = PAGE.format(pk=PK)
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"저장: 분기 {sorted(ids)} · 들고 남 쌍 {sorted(pairs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
