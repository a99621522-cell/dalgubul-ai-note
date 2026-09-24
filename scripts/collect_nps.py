#!/usr/bin/env python3
"""국민연금 가입 사업장 내역(공공데이터포털) → data/nps/YYYYMM.csv (대구만, 표준 열)

두 가지 입력 방식
  A) 오픈API  python3 scripts/collect_nps.py                      # sources.yml 의 nps.api 와 DATA_GO_KR_KEY 사용
              python3 scripts/collect_nps.py --url <odcloud 주소>  # 이번 달 UDDI 주소를 직접 지정
  B) 파일     python3 scripts/collect_nps.py --file <내려받은 전국 CSV>   # 포털에서 받은 파일(cp949/utf-8)을 대구만 걸러 저장

공공데이터포털 데이터셋: "국민연금공단_국민연금 가입 사업장 내역" (월별 파일 + 오픈API, 데이터셋 15083277).
오픈API 는 파일마다 uddi 가 달라 sources.yml 의 nps.api 에 이번 달 주소를 적거나 --url 로 넘긴다.
키: 환경변수 DATA_GO_KR_KEY (공공데이터포털 일반 인증키, 해당 API 활용신청 필요).

원칙
- 저장하는 열은 매칭·집계에 필요한 것만(사업장명·주소·업종코드·가입자수·취득·상실·상태·적용일·탈퇴일·기준월). 고지금액 등은 저장하지 않는다
- 사업자등록번호는 포털이 앞 6자리만 주며 그대로 둔다(매칭 보조). 개인 성명으로 보이는 사업장명은 표시 단계(csv.ts)에서 가린다
- 이 세션(claude.ai 클라우드)은 포털 접속이 막혀 있어 GitHub Actions(.github/workflows/nps.yml) 나 로컬에서 실행한다
- 외부 API 실패는 로그를 남기고 종료 코드 1 (무인 실행에서 빈 파일을 커밋하지 않기 위해)
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "nps"
SOURCES = ROOT / "scripts" / "sources.yml"
UA = {"User-Agent": "daitda-note/1.0 (+https://note.daitda.co.kr)"}

# 표준 열(build_stats.py NPS_COLS 가 읽는 이름) ← 포털 열 이름 후보
COLS = {
    "자료생성년월": ["자료생성년월", "기준년월", "기준월"],
    "사업장명": ["사업장명", "사업장명칭"],
    "사업자등록번호": ["사업자등록번호"],
    "사업장가입상태코드": ["사업장가입상태코드", "가입상태"],
    "사업장도로명상세주소": ["사업장도로명상세주소", "도로명주소"],
    "사업장지번상세주소": ["사업장지번상세주소", "지번주소"],
    "법정동주소광역시도코드": ["법정동주소광역시도코드", "광역시도코드"],
    "사업장업종코드": ["사업장업종코드", "업종코드"],
    "사업장업종코드명": ["사업장업종코드명", "업종코드명", "업종명"],
    "적용일자": ["적용일자"],
    "재등록일자": ["재등록일자"],
    "탈퇴일자": ["탈퇴일자"],
    "가입자수": ["가입자수"],
    "신규취득자수": ["신규취득자수", "당월취득자수"],
    "상실가입자수": ["상실가입자수", "당월상실자수"],
}
DAEGU_SIDO_CODE = "27"


def cfg() -> dict:
    return (yaml.safe_load(SOURCES.read_text(encoding="utf-8")) or {}).get("nps", {}) or {}


def pick(row: dict, key: str) -> str:
    for c in COLS[key]:
        if c in row and row[c] is not None:
            return str(row[c]).strip()
    return ""


def is_daegu(row: dict, region_words: list[str]) -> bool:
    if pick(row, "법정동주소광역시도코드") == DAEGU_SIDO_CODE:
        return True
    addr = pick(row, "사업장도로명상세주소") + " " + pick(row, "사업장지번상세주소")
    return any(w in addr for w in region_words)


def month_of(rows: list[dict], override: str | None) -> str:
    if override:
        return re.sub(r"\D", "", override)[:6]
    for r in rows:
        m = re.sub(r"\D", "", pick(r, "자료생성년월"))
        if len(m) >= 6:
            return m[:6]
    return time.strftime("%Y%m")


def normalize(rows: list[dict]) -> list[dict]:
    return [{k: pick(r, k) for k in COLS} for r in rows]


# ---------------------------------------------------------------- A) 오픈API
def fetch_api(url: str, key: str, per_page: int, cond: dict | None, max_pages: int) -> list[dict]:
    out: list[dict] = []
    page = 1
    while page <= max_pages:
        params = {"serviceKey": key, "page": page, "perPage": per_page, "returnType": "JSON"}
        if cond:
            params[f"cond[{cond['column']}::{cond.get('op', 'EQ')}]"] = cond["value"]
        try:
            r = requests.get(url, params=params, headers=UA, timeout=60)
            r.raise_for_status()
            j = r.json()
        except Exception as e:  # 무인 실행: 죽이지 않고 로그
            print(f"[nps] API 실패 page={page}: {e}", file=sys.stderr)
            break
        data = j.get("data") or []
        out.extend(data)
        total = j.get("totalCount") or j.get("matchCount")
        print(f"[nps] page {page}: {len(data)}행 (누적 {len(out):,}{f' / 전체 {total:,}' if isinstance(total, int) else ''})")
        if len(data) < per_page:
            break
        page += 1
        time.sleep(0.2)
    return out


# ---------------------------------------------------------------- B) 파일
def read_file(path: Path) -> list[dict]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("cp949", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="odcloud API 주소 (sources.yml nps.api 대신)")
    ap.add_argument("--file", help="포털에서 내려받은 전국 CSV")
    ap.add_argument("--month", help="YYYYMM (자료생성년월이 없을 때)")
    ap.add_argument("--out", help="저장 경로 (기본 data/nps/YYYYMM.csv)")
    a = ap.parse_args(argv)
    c = cfg()
    region_words = c.get("region_words") or ["대구광역시", "대구 "]

    if a.file:
        rows = read_file(Path(a.file))
        print(f"[nps] 파일 {a.file}: {len(rows):,}행")
    else:
        url = a.url or c.get("api", "")
        key = os.environ.get("DATA_GO_KR_KEY", "").strip()
        if not url or not key:
            print("[nps] nps.api(sources.yml) 또는 --url, 그리고 DATA_GO_KR_KEY 가 필요합니다", file=sys.stderr)
            return 1
        cond = c.get("filter") or {"column": "법정동주소광역시도코드", "op": "EQ", "value": DAEGU_SIDO_CODE}
        rows = fetch_api(url, key, int(c.get("per_page", 1000)), cond, int(c.get("max_pages", 500)))
        if not rows:
            print("[nps] 받은 행이 없습니다. uddi 주소·키·활용신청을 확인하세요", file=sys.stderr)
            return 1

    daegu = [r for r in rows if is_daegu(r, region_words)]
    if not daegu:
        print("[nps] 대구 사업장이 0행입니다. 열 이름(법정동주소광역시도코드/주소)을 확인하세요", file=sys.stderr)
        return 1
    month = month_of(daegu, a.month)
    out = Path(a.out) if a.out else OUT_DIR / f"{month}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    norm = normalize(daegu)
    # 같은 사업장이 두 번 들어오면(API 중복 페이지 등) 하나만
    seen, uniq = set(), []
    for r in norm:
        k = (r["사업장명"], r["사업자등록번호"], r["사업장도로명상세주소"] or r["사업장지번상세주소"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(COLS))
        w.writeheader()
        w.writerows(uniq)
    emp = sum(int(r["가입자수"]) for r in uniq if r["가입자수"].isdigit())
    shown = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"[nps] 저장 {shown}: 대구 사업장 {len(uniq):,}곳 · 가입자 {emp:,}명 · 기준월 {month[:4]}-{month[4:]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
