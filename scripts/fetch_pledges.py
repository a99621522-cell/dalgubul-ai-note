#!/usr/bin/env python3
"""민선 9기 대구광역시장 공약 원문 받기 — (A) 대구시청·열린시장실 공약 페이지, (B) 중앙선관위 선거공약 오픈API.
결과는 data/pledges/ 에 텍스트·JSON 으로 남기고, 사람이(또는 다음 단계 스크립트가) config/pledge_areas.yml 의 공약 항목을 채운다.
공약 이행 평가·점수화는 하지 않는다. 원문 URL 과 받은 날짜를 함께 저장한다.

  A) 시청: scripts/sources.yml 의 pledges.seeds 주소를 읽고, 같은 호스트 안에서 링크 글자에 '공약' 이 든 페이지를 1단계 더 따라간다.
     각 페이지의 본문 텍스트(태그 제거)를 data/pledges/city/<번호>_<제목>.txt 로. 첨부(pdf·hwp·xlsx)는 data/pledges/city/files/ 에.
  B) 선관위: 공공데이터포털 '중앙선거관리위원회_선거공약 정보'(15040587) + '후보자 정보'(getPofelcddRegistSttusInfoInqire).
     sgId=20260603(제9회 지방선거), sgTypecode=3(시·도지사), 대구광역시 후보자 전원의 5대 공약 → data/pledges/nec/*.json, *.txt. 키 DATA_GO_KR_KEY.

이 세션 환경은 두 사이트 모두 막혀 있어 GitHub Actions(.github/workflows/pledges.yml)에서 실행한다. 실패는 로그만 남긴다.
사용: python3 scripts/fetch_pledges.py [--city] [--nec]   (둘 다 없으면 둘 다)
"""
from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "pledges"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept-Language": "ko-KR,ko;q=0.9"}
TODAY = date.today().isoformat()


def safe(s: str, n: int = 60) -> str:
    return re.sub(r"[^\w가-힣.-]+", "_", s).strip("_")[:n] or "page"


def page_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        t.decompose()
    title = (soup.title.get_text(" ", strip=True) if soup.title else "")[:120]
    main = soup.find("main") or soup.find(id=re.compile("content|contents|container", re.I)) or soup.body or soup
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(ln.strip() for ln in main.get_text("\n").splitlines() if ln.strip()))
    return title, text


def fetch_city(seeds: list[str], sess: requests.Session, max_pages: int = 60, max_depth: int = 2) -> int:
    d = OUT / "city"
    (d / "files").mkdir(parents=True, exist_ok=True)
    seen, queue, saved = set(), [(u, 0) for u in seeds], 0
    index = []
    while queue and saved < max_pages:
        url, depth = queue.pop(0)
        url = url.split("#")[0]
        if url in seen:
            continue
        seen.add(url)
        try:
            r = sess.get(url, headers=UA, timeout=60)
        except Exception as e:  # noqa: BLE001
            print(f"  [city] 실패 {url}: {str(e)[:80]}")
            continue
        ct = r.headers.get("Content-Type", "")
        if r.status_code != 200:
            print(f"  [city] HTTP {r.status_code} {url}")
            continue
        if "text/html" not in ct:
            name = safe(Path(urlparse(url).path).name or "file", 80)
            (d / "files" / name).write_bytes(r.content)
            print(f"  [city] 첨부 저장 {name} ({len(r.content):,} bytes)")
            index.append({"url": url, "file": f"files/{name}", "fetched": TODAY})
            continue
        r.encoding = r.apparent_encoding or "utf-8"
        title, text = page_text(r.text)
        if len(text) < 200:
            print(f"  [city] 본문이 거의 없음({len(text)}자, JS 렌더링일 수 있음): {url}\n      {r.text[:300].replace(chr(10), ' ')}")
        if depth == 0 or "공약" in title + text[:5000]:
            fn = f"{saved + 1:02d}_{safe(title)}.txt"
            (d / fn).write_text(f"# {title}\n# 출처: {url}\n# 받은 날짜: {TODAY}\n\n{text}", encoding="utf-8")
            index.append({"url": url, "title": title, "file": fn, "chars": len(text), "fetched": TODAY})
            saved += 1
            print(f"  [city] 저장 {fn} ({len(text):,}자) ← {url}")
        else:
            print(f"  [city] '공약' 없음, 건너뜀: {title[:40]} ← {url}")
        if depth >= max_depth:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        host = urlparse(url).netloc
        links = []
        for a in soup.find_all("a", href=True):
            label = a.get_text(" ", strip=True)
            href = urljoin(url, a["href"]).split("#")[0]
            if urlparse(href).netloc != host or href in seen or href.startswith("javascript"):
                continue
            links.append((label, href))
            hit = re.search(r"공약|비전|추진과제|시정|당선", label) or re.search(r"공약|pledge|promise|policy", href, re.I) \
                or (re.search(r"\.(pdf|hwpx?|xlsx?)(\?|$)", href, re.I) and "공약" in label + str(a.parent)[:200]) \
                or ("nec.go.kr" in host and re.search(r"대구|지방선거|시.?도지사|당선", label))
            if hit:
                queue.append((href, depth + 1))
        if depth == 0:  # 첫 페이지의 링크는 전부 로그에 남겨 다음 실행의 seed 를 고를 수 있게
            print(f"  [city] {url} 링크 {len(links)}개: " + " | ".join(f"{l[:20]}→{h[-60:]}" for l, h in links[:80]))
    (d / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[city] 페이지 {saved}개 저장 → {d.relative_to(ROOT)}")
    return saved


def fetch_nec(key: str, sess: requests.Session, sg_id: str = "20260603", sg_type: str = "3", sd: str = "대구광역시") -> int:
    if not key:
        print("[nec] DATA_GO_KR_KEY 없음 — 건너뜀")
        return 0
    d = OUT / "nec"
    d.mkdir(parents=True, exist_ok=True)
    base = "http://apis.data.go.kr/9760000"
    cands = []
    try:
        r = sess.get(f"{base}/PofelcddInfoInqireService/getPofelcddRegistSttusInfoInqire",
                     params={"serviceKey": key, "sgId": sg_id, "sgTypecode": sg_type, "sdName": sd, "numOfRows": 100, "pageNo": 1, "resultType": "json"}, timeout=60)
        print(f"[nec] 후보자 조회 HTTP {r.status_code}: {r.text[:200].replace(chr(10), ' ')}")
        items = _items(r)
        cands = [it for it in items if sd.replace("광역시", "") in (it.get("sdName") or "")] or items
    except Exception as e:  # noqa: BLE001
        print(f"[nec] 후보자 조회 실패: {e}")
    if not cands:
        # 대구시 선거구 이름이 다를 수 있어 전체를 받아 걸러본다
        try:
            r = sess.get(f"{base}/PofelcddInfoInqireService/getPofelcddRegistSttusInfoInqire",
                         params={"serviceKey": key, "sgId": sg_id, "sgTypecode": sg_type, "numOfRows": 200, "pageNo": 1, "resultType": "json"}, timeout=60)
            cands = [it for it in _items(r) if "대구" in json.dumps(it, ensure_ascii=False)]
            print(f"[nec] 전체 시도지사 후보 중 대구: {len(cands)}")
        except Exception as e:  # noqa: BLE001
            print(f"[nec] 후보자 전체 조회 실패: {e}")
    n = 0
    for c in cands:
        cid, name, party = c.get("huboid") or c.get("cnddtId") or "", c.get("name", ""), c.get("jdName", "")
        try:
            r = sess.get(f"{base}/ElecPrmsInfoInqireService/getCnddtElecPrmsInfoInqire",
                         params={"serviceKey": key, "sgId": sg_id, "sgTypecode": sg_type, "cnddtId": cid, "numOfRows": 10, "pageNo": 1, "resultType": "json"}, timeout=60)
            items = _items(r)
        except Exception as e:  # noqa: BLE001
            print(f"[nec] 공약 조회 실패 {name}: {e}")
            continue
        if not items:
            print(f"[nec] 공약 없음: {name} ({party}) id={cid} · {r.text[:120].replace(chr(10), ' ')}")
            continue
        it = items[0]
        (d / f"{safe(name)}_{cid}.json").write_text(json.dumps({"candidate": c, "pledges": it, "fetched": TODAY, "source": "중앙선거관리위원회 선거공약 정보(공공데이터포털 15040587)"}, ensure_ascii=False, indent=1), encoding="utf-8")
        lines = [f"# {name} ({party}) — 제9회 전국동시지방선거 대구광역시장 후보 5대 공약", f"# 출처: 중앙선거관리위원회 선거공약 정보 오픈API (data.go.kr/data/15040587), 받은 날짜 {TODAY}", ""]
        for i in range(1, 11):
            t = it.get(f"prmsTitle{i}") or it.get(f"prmmTitle{i}")
            if not t:
                continue
            lines += [f"## {i}. {t}", f"분야: {it.get(f'prmsRealmName{i}', '')}", f"목표: {it.get(f'prmsObjName{i}', '')}", "", it.get(f"prmsCont{i}", "") or "", ""]
        (d / f"{safe(name)}_{cid}.txt").write_text("\n".join(lines), encoding="utf-8")
        n += 1
        print(f"[nec] 저장 {name} ({party}) 공약 {sum(1 for i in range(1, 11) if it.get(f'prmsTitle{i}'))}개")
    return n


def _items(r: requests.Response) -> list[dict]:
    txt = r.text.strip()
    if txt.startswith("{"):
        j = r.json()
        body = (j.get("response") or {}).get("body") or {}
        items = (body.get("items") or {}).get("item") or []
        return items if isinstance(items, list) else [items]
    try:
        root = ET.fromstring(txt)
    except ET.ParseError:
        return []
    return [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load((ROOT / "scripts" / "sources.yml").read_text(encoding="utf-8")) or {}
    seeds = (cfg.get("pledges") or {}).get("seeds") or []
    sess = requests.Session()
    do_city = "--city" in argv or "--nec" not in argv
    do_nec = "--nec" in argv or "--city" not in argv
    total = 0
    if do_city:
        total += fetch_city(seeds, sess)
    if do_nec:
        total += fetch_nec(os.environ.get("DATA_GO_KR_KEY", "").strip(), sess)
    print(f"완료: {total}건")
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
