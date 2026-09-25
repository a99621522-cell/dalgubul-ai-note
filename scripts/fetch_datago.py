#!/usr/bin/env python3
"""공공데이터포털(data.go.kr) 파일 데이터 내려받기 — 로그인·키 없이 공개된 '파일데이터' 첨부를 받는다.

사용:
  python3 scripts/fetch_datago.py --probe 15117154 15083277     # 페이지를 읽어 찾은 파일 목록·다운로드 응답을 출력만 (구조 확인)
  python3 scripts/fetch_datago.py --save  15117154 15083277     # data/raw/<id>/ 에 저장 (zip 이면 풀어서)
  python3 scripts/fetch_datago.py --save 15083277 --pick 2026    # 파일이 여럿이면 이름에 '2026' 이 든 것만

대상 예: 15117154 한국산업단지공단_전국지식산업센터현황 / 15083277 국민연금공단_국민연금 가입 사업장 내역(월별 파일 여러 개)
이 세션 환경은 data.go.kr 접속이 막혀 있어 GitHub Actions(.github/workflows/fetch_public.yml)에서 실행한다.
포털 페이지 구조가 바뀌면 --probe 출력으로 확인한다. 실패는 로그만 남긴다.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
PAGE = "https://www.data.go.kr/data/{id}/fileData.do"
DL_NEW = "https://www.data.go.kr/tcs/dss/selectFileDataDownload.do"
DL_OLD = "https://www.data.go.kr/cmm/cmm/fileDownload.do"


def get_page(pk: str, sess: requests.Session) -> str:
    r = sess.get(PAGE.format(id=pk), headers=UA, timeout=60)
    print(f"[page {pk}] HTTP {r.status_code}, {len(r.text):,}자")
    return r.text


def discover(html: str) -> dict:
    """페이지에서 다운로드 단서를 모두 뽑는다: fn_fileDataDown(...) 인자, uddi, atchFileId, 파일명, 기준일자."""
    calls = []
    for m in re.finditer(r"fn_fileDataDown\(([^)]*)\)", html):
        calls.append([a.strip().strip("'\"") for a in m.group(1).split(",")])
    uddis = sorted(set(re.findall(r"uddi:[0-9a-fA-F-]{20,}", html)))
    atch = sorted(set(re.findall(r"FILE_[0-9]{10,}", html)))
    names = sorted(set(re.findall(r"[^\"'<>\s]{3,120}\.(?:csv|zip|xlsx|xls|json)", html)))
    dates = sorted(set(re.findall(r"20\d{2}-\d{2}-\d{2}", html)))
    title = (re.search(r"<title>(.*?)</title>", html, re.S) or [None, ""])[1].strip()
    return {"title": title, "calls": calls, "uddis": uddis, "atch": atch, "names": names, "dates": dates[-10:]}


def try_download(pk: str, call: list[str], sess: requests.Session) -> requests.Response | None:
    """fn_fileDataDown 인자 형태에 따라 두 엔드포인트를 차례로 시도한다."""
    attempts = []
    uddi = next((a for a in call if a.startswith("uddi:")), None)
    atch = next((a for a in call if a.startswith("FILE_")), None)
    sn = next((a for a in call if re.fullmatch(r"\d{1,3}", a)), "1")
    if uddi:
        attempts.append(("POST", DL_NEW, {"publicDataPk": pk, "publicDataDetailPk": uddi, "fileDetailSn": sn}))
        attempts.append(("GET", DL_NEW, {"publicDataPk": pk, "publicDataDetailPk": uddi, "fileDetailSn": sn}))
    if atch:
        attempts.append(("GET", DL_OLD, {"atchFileId": atch, "fileDetailSn": sn}))
    for method, url, params in attempts:
        try:
            r = sess.request(method, url, params=params if method == "GET" else None, data=params if method == "POST" else None,
                             headers={**UA, "Referer": PAGE.format(id=pk)}, timeout=300, stream=True)
            ct = r.headers.get("Content-Type", "")
            cd = r.headers.get("Content-Disposition", "")
            print(f"  {method} {url.split('/')[-1]} {params} → HTTP {r.status_code} · {ct[:40]} · {cd[:80]}")
            if r.status_code == 200 and "text/html" not in ct:
                return r
            r.close()
        except Exception as e:  # noqa: BLE001
            print(f"  {method} 실패: {e}")
    return None


def save_response(r: requests.Response, pk: str, hint: str) -> list[Path]:
    RAW.joinpath(pk).mkdir(parents=True, exist_ok=True)
    cd = r.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
    name = requests.utils.unquote(m.group(1)) if m else (hint or "download.bin")
    data = r.content
    out = RAW / pk / name
    out.write_bytes(data)
    print(f"  저장 {out.relative_to(ROOT)} ({len(data):,} bytes)")
    files = [out]
    if zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for zi in z.infolist():
                try:
                    zname = zi.filename.encode("cp437").decode("cp949")
                except Exception:  # noqa: BLE001
                    zname = zi.filename
                p = RAW / pk / Path(zname).name
                p.write_bytes(z.read(zi))
                files.append(p)
                print(f"    zip 안: {zname} ({zi.file_size:,} bytes)")
    return files


def head_of(p: Path, n: int = 3) -> None:
    raw = p.read_bytes()[:4000]
    for enc in ("utf-8-sig", "cp949", "utf-8"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        txt = raw.decode("latin-1", errors="replace")
    for line in txt.splitlines()[:n]:
        print("    | " + line[:300])


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--pick", help="파일이 여럿일 때 이름·인자에 이 문자열이 든 것만")
    ap.add_argument("--max", type=int, default=3, help="데이터셋당 최대 파일 수")
    a = ap.parse_args(argv)
    sess = requests.Session()
    ok = 0
    for pk in a.ids:
        try:
            html = get_page(pk, sess)
        except Exception as e:  # noqa: BLE001
            print(f"[page {pk}] 실패: {e}")
            continue
        d = discover(html)
        print(f"[{pk}] {d['title'][:80]}")
        print(f"  fn_fileDataDown 호출 {len(d['calls'])}개, uddi {len(d['uddis'])}개, atchFileId {len(d['atch'])}개, 파일명 {len(d['names'])}개, 날짜 {d['dates']}")
        for c in d["calls"][:12]:
            print("   call:", c)
        for n in d["names"][:12]:
            print("   name:", n)
        calls = d["calls"] or [[u] for u in d["uddis"]] or [[x] for x in d["atch"]]
        if a.pick:
            calls = [c for c in calls if any(a.pick in x for x in c)] or calls
        if not (a.probe or a.save):
            continue
        for c in calls[: a.max]:
            r = try_download(pk, c, sess)
            if r is None:
                continue
            files = save_response(r, pk, hint=next((x for x in c if "." in x), f"{pk}.bin"))
            for f in files:
                if f.suffix.lower() in (".csv", ".txt", ".json"):
                    print(f"  머리 {f.name}:")
                    head_of(f)
            ok += 1
            if not a.save:  # probe 는 첫 파일만
                break
    print(f"완료: 파일 {ok}개")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
