#!/usr/bin/env python3
"""출처별 수집기(collect_venture / collect_innopolis / collect_dgmif / collect_nps)가 함께 쓰는 도우미. 표준 라이브러리 + requests.

- portal_file(pk)      공공데이터포털 '파일데이터' 페이지에서 그때의 첨부 링크를 찾아 내려받는다(키 불필요).
                       첨부 id 가 갱신마다 바뀌므로 매번 페이지에서 다시 읽는다
- decode_csv(bytes)    utf-8-sig → cp949 순으로 풀어 행 목록으로
- norm(name)           회사명 정규화 (dart_match.py 와 같은 규칙 — 병합의 기준)
- district_of(addr)    주소 문자열에서 구·군
- INNOPOLIS_DISTRICT   대구연구개발특구 지구 → 구·군 (주소가 없는 명단용)
- write_source(...)    scripts/data/sources/<출처>_YYYYMMDD.json 저장 (공통 스키마 + 출처 고유 항목), 최근 2개만 보관

공통 스키마: name, address, district, sector_code, sector, product, source, collected  (+ 출처 고유 항목)
저장하지 않는 것: 대표자·전화·이메일·팩스 (어느 출처에 있어도).
"""
import csv
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "scripts" / "data" / "sources"
UA = {"User-Agent": "Mozilla/5.0 (compatible; dalgubul-ai-note/0.1; +personal blog collector)"}

# 대구연구개발특구 지구 → 구·군. 주소가 없는 특구 명단에 쓴다. 지식서비스R&D지구는 수성알파시티 일대.
# 융합R&D지구는 위치가 갈려 비워 두고(이름 대조로 채움) 표시할 때는 '특구 융합R&D지구'로만 적는다.
INNOPOLIS_DISTRICT = {
    "테크노폴리스지구": "달성군",
    "성서첨단지구": "달서구",
    "의료R&D지구": "동구",
    "지식서비스R&D지구1": "수성구", "지식서비스R&D지구2": "수성구",
    "융합R&D지구1": "", "융합R&D지구2": "",
}
ZONE_LABEL = {  # 지구 → 카드에 쓸 단지 표시명
    "테크노폴리스지구": "테크노폴리스", "성서첨단지구": "성서 특구",
    "의료R&D지구": "첨복단지 일대(의료R&D지구)", "지식서비스R&D지구1": "알파시티 일대(지식서비스R&D지구)",
    "지식서비스R&D지구2": "알파시티 일대(지식서비스R&D지구)", "융합R&D지구1": "특구 융합R&D지구", "융합R&D지구2": "특구 융합R&D지구",
}


def portal_file(pk: str) -> tuple[bytes, str, str]:
    """(bytes, 파일명, 데이터셋 제목). 페이지 → 첨부 링크 → 다운로드."""
    page = f"https://www.data.go.kr/data/{pk}/fileData.do"
    r = requests.get(page, headers=UA, timeout=60)
    r.raise_for_status()
    m = re.search(r'https://www\.data\.go\.kr/cmm/cmm/fileDownload\.do\?atchFileId=[A-Z0-9_]+&fileDetailSn=\d+[^"\'<>\s]*', r.text)
    if not m:
        raise RuntimeError(f"데이터셋 {pk}: 첨부 링크를 찾지 못함")
    t = re.search(r"<title>([^<]*)</title>", r.text)
    title = (t.group(1).replace("| 공공데이터포털", "").strip() if t else pk)
    d = requests.get(m.group(0).replace("&amp;", "&"), headers={**UA, "Referer": page}, timeout=300)
    d.raise_for_status()
    fn = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', d.headers.get("Content-Disposition", ""))
    return d.content, (fn.group(1) if fn else ""), title


def decode_csv(b: bytes) -> list[list[str]]:
    if b.startswith(b"\xef\xbb\xbf"):
        txt = b.decode("utf-8-sig")
    else:
        try:
            txt = b.decode("cp949")
        except UnicodeDecodeError:
            txt = b.decode("utf-8", "replace")
    rows = list(csv.reader(io.StringIO(txt)))
    return [[c.strip() for c in r] for r in rows if any(c.strip() for c in r)]


def col(hdr: list[str], *names: str, required: bool = True) -> int | None:
    for n in names:
        for i, h in enumerate(hdr):
            if n in h:
                return i
    if required:
        raise KeyError(f"열 없음: {names} / 있는 열: {hdr}")
    return None


def norm(s: str) -> str:
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사|유한책임회사|\(사\)|\(재\)|\(합\)|합자회사|\s", "", s or "")
    s = re.sub(r"\([^)]*\)", "", s)
    return s.lower()


_GU = re.compile(r"(중구|동구|서구|남구|북구|수성구|달서구|달성군|군위군)")


def district_of(addr: str) -> str:
    m = _GU.search(addr or "")
    return m.group(1) if m else ""


def write_source(src: str, rows: list[dict], meta: dict) -> Path:
    SOURCES.mkdir(parents=True, exist_ok=True)
    today = date.today()
    out = SOURCES / f"{src}_{today.strftime('%Y%m%d')}.json"
    out.write_text(json.dumps({"meta": {**meta, "source": src, "collected": today.isoformat(), "count": len(rows)}, "rows": rows},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for p in sorted(SOURCES.glob(f"{src}_20*.json"))[:-2]:
        p.unlink()
    return out


def latest_source(src: str) -> dict | None:
    files = sorted(SOURCES.glob(f"{src}_20*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None
