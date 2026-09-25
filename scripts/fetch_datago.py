#!/usr/bin/env python3
"""공공데이터포털(data.go.kr) 파일 데이터 내려받기 — 로그인·키 없이 공개된 '파일데이터' 첨부를 받는다.

사용:
  python3 scripts/fetch_datago.py --probe 15117154 15083277     # 페이지를 읽어 찾은 파일 목록·다운로드 응답을 출력만 (구조 확인)
  python3 scripts/fetch_datago.py --save  15117154 15083277     # data/raw/<id>/ 에 저장 (zip 이면 풀어서)
  python3 scripts/fetch_datago.py --save 15083277 --pick 2026    # 파일이 여럿이면 이름에 '2026' 이 든 것만
  python3 scripts/fetch_datago.py --search 대구테크노파크 한국로봇산업진흥원   # 포털 검색: 키워드별 파일데이터 번호·제목·제공기관 목록만 출력

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


SEARCH = "https://www.data.go.kr/tcs/dss/selectDataSetList.do"


def search(keyword: str, sess: requests.Session, pages: int = 2) -> list[tuple[str, str, str]]:
    """포털 검색(파일데이터만) → [(번호, 제목, 주변 문구)]. 페이지 구조가 바뀌면 링크만이라도 남긴다."""
    out, seen = [], set()
    for page in range(1, pages + 1):
        params = {"dType": "FILE", "keyword": keyword, "currentPage": page, "perPage": 40, "sort": "updtDt"}
        try:
            r = sess.get(SEARCH, params=params, headers=UA, timeout=60)
        except Exception as e:  # noqa: BLE001
            print(f"  검색 실패 '{keyword}' p{page}: {e}")
            break
        html = r.text
        hits = list(re.finditer(r'href="/data/(\d+)/fileData\.do[^"]*"[^>]*>([\s\S]{0,300}?)</a>', html))
        if page == 1:
            total = re.search(r"총\s*<[^>]*>?\s*([\d,]+)\s*<?[^>]*>?\s*건|검색결과\D{0,20}([\d,]+)", html)
            print(f"[검색 '{keyword}'] HTTP {r.status_code}, 링크 {len(hits)}개" + (f", 전체 {total.group(1) or total.group(2)}건" if total else ""))
        if not hits:
            break
        for m in hits:
            pk = m.group(1)
            if pk in seen:
                continue
            seen.add(pk)
            title = re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip()
            tail = re.sub(r"<[^>]+>|\s+", " ", html[m.end(): m.end() + 1500])
            org = re.search(r"(?:제공기관|기관)\s*[:：]?\s*(\S[^|]{0,40}?)(?:\s{2,}|수정일|등록일|조회|다운로드|\||$)", tail)
            out.append((pk, title, (org.group(1).strip() if org else tail[:80])))
        if len(hits) < 40:
            break
    return out


def get_page(pk: str, sess: requests.Session) -> str:
    """포털이 잠시 안 열릴 때(접속 시간 초과)를 대비해 3번까지 기다렸다 다시 시도한다."""
    import time
    for i in range(3):
        try:
            r = sess.get(PAGE.format(id=pk), headers=UA, timeout=60)
            print(f"[page {pk}] HTTP {r.status_code}, {len(r.text):,}자")
            return r.text
        except requests.exceptions.ConnectionError as e:
            if i == 2:
                raise
            print(f"[page {pk}] 접속 실패({str(e)[:60]}…) — {30 * (i + 1)}초 뒤 재시도")
            time.sleep(30 * (i + 1))
    return ""


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
    fn = re.search(r"function\s+fn_fileDataDown\s*\([^)]*\)\s*\{[\s\S]{0,2500}", html)
    scripts = re.findall(r"<script[^>]+src=[\"']([^\"']+)", html)
    forms = re.findall(r"<form[^>]*>", html)[:8]
    return {"title": title, "calls": calls, "uddis": uddis, "atch": atch, "names": names, "dates": dates[-10:],
            "fn": fn.group(0) if fn else "", "scripts": scripts, "forms": forms}


def html_text(r: requests.Response, n: int = 1200) -> str:
    """HTML 응답의 요지: 태그 제거 텍스트 + location/href/url 단서."""
    body = r.content[:200000].decode(r.encoding or "utf-8", errors="replace")
    hints = re.findall(r"(?:location\.href|location\.replace|window\.open|action)\s*[=(]\s*[\"']([^\"']+)", body)[:8]
    urls = re.findall(r"https?://[^\"'\s<>]+", body)[:8]
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", body)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return f"text: {text[:n]}\n    hints: {hints}\n    urls: {urls}"


def try_download(pk: str, call: list[str], sess: requests.Session, atch_page: list[str] | None = None) -> requests.Response | None:
    """fn_fileDataDown 인자 형태에 따라 엔드포인트를 차례로 시도한다. HTML 이 오면 그 내용을 찍어 다음 단서로 쓴다."""
    attempts = []
    uddi = next((a for a in call if a.startswith("uddi:")), None)
    atch = next((a for a in call if a.startswith("FILE_")), None) or (atch_page[0] if atch_page else None)
    nums = [a for a in call if re.fullmatch(r"\d{1,3}", a)]
    sn = nums[0] if nums else "1"
    if uddi:
        base = {"publicDataPk": pk, "publicDataDetailPk": uddi, "fileDetailSn": sn}
        attempts.append(("POST", DL_NEW, base))
        attempts.append(("POST", DL_NEW, {**base, "publicDataSn": nums[1] if len(nums) > 1 else "3", "fileNm": ""}))
        attempts.append(("GET", "https://www.data.go.kr/tcs/dss/selectFileDataDownload.do", base))
    if atch:
        for s_ in dict.fromkeys([sn, "1", "2", "3", "4"]):
            attempts.append(("GET", DL_OLD, {"atchFileId": atch, "fileDetailSn": s_}))
    for method, url, params in attempts:
        try:
            r = sess.request(method, url, params=params if method == "GET" else None, data=params if method == "POST" else None,
                             headers={**UA, "Referer": PAGE.format(id=pk)}, timeout=300, stream=True, allow_redirects=True)
            ct = r.headers.get("Content-Type", "")
            cd = r.headers.get("Content-Disposition", "")
            print(f"  {method} {url.split('/')[-1]} {params} → HTTP {r.status_code} · {ct[:40]} · {cd[:80]} · final {r.url[:100]}")
            if r.status_code == 200 and "text/html" not in ct:
                name = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
                fname = requests.utils.unquote(name.group(1)) if name else ""
                if not fname or re.search(r"\.(png|jpe?g|gif|pdf|hwp|hwpx|docx?|pptx?)$", fname, re.I):
                    print(f"    표 파일이 아님({fname[-40:]}) — 다음 파일 번호 시도")
                    r.close()
                    continue
                return r
            if "text/html" in ct:
                print("    " + html_text(r))
            r.close()
        except Exception as e:  # noqa: BLE001
            print(f"  {method} 실패: {e}")
    return None


def try_catalog(pk: str, sess: requests.Session) -> None:
    """/catalog/<pk>/fileData.json 같은 메타 끝점이 있으면 내용을 찍는다 (다운로드 주소 단서)."""
    for url in (f"https://www.data.go.kr/catalog/{pk}/fileData.json", f"https://www.data.go.kr/catalog/{pk}/fileData.do"):
        try:
            r = sess.get(url, headers={**UA, "Accept": "application/json, text/html"}, timeout=60)
            ct = r.headers.get("Content-Type", "")
            print(f"  catalog {url.split('/')[-1]} → HTTP {r.status_code} · {ct[:40]}")
            if "json" in ct:
                print("    " + r.text[:1500].replace("\n", " "))
            else:
                print("    " + html_text(r, 600))
        except Exception as e:  # noqa: BLE001
            print(f"  catalog 실패: {e}")


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
    ap.add_argument("--search", action="store_true", help="ids 를 검색어로 보고 파일데이터 목록만 출력")
    a = ap.parse_args(argv)
    sess = requests.Session()
    ok = 0
    if a.search:
        for kw in a.ids:
            for pk, title, org in search(kw, sess):
                print(f"  {pk} | {title[:90]} | {org[:60]}")
                ok += 1
        print(f"완료: 검색 결과 {ok}개")
        return 0
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
        print("   atch:", d["atch"][:5], "| scripts:", [x for x in d["scripts"] if "data" in x or "file" in x.lower()][:8])
        print("   forms:", d["forms"][:5])
        if d["fn"]:
            print("   fn_fileDataDown 원본:\n" + "\n".join("     " + ln for ln in d["fn"].splitlines()[:40]))
        try_catalog(pk, sess)
        calls = d["calls"] or [[u] for u in d["uddis"]] or [[x] for x in d["atch"]]
        if a.pick:
            calls = [c for c in calls if any(a.pick in x for x in c)] or calls
        if not (a.probe or a.save):
            continue
        for c in calls[: a.max]:
            try:
                r = try_download(pk, c, sess, d["atch"])
                if r is None:
                    continue
                files = save_response(r, pk, hint=next((x for x in c if "." in x), f"{pk}.bin"))
            except Exception as e:  # noqa: BLE001 — 한 파일이 끊겨도 다음 데이터셋으로
                print(f"  [{pk}] 받기 실패: {e}")
                continue
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
