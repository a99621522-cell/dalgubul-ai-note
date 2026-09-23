#!/usr/bin/env python3
"""기업 사전(dalseong_companies.csv) ↔ OpenDART 법인 매칭 → scripts/data/dart/match.json

흐름
  1) corpCode.xml(zip) 내려받아 corp_code·corp_name·stock_code 목록으로. scripts/data/dart/corp_codes.json 에 캐시
     (하루 이내면 재사용, 저장소에는 넣지 않음 — .gitignore)
  2) 기업 DB 회사명 정규화(주식회사/(주)/㈜/공백/괄호 제거, 소문자) → 같은 이름의 DART 법인을 모두 후보로
  3) 후보마다 company.json 으로 본사 주소·사업자번호·법인번호·업종코드를 받는다. 회사당 1회, 결과는
     scripts/state/dart_corp.json 에 캐시(collect_dart.py 와 같은 파일 — 필드를 넓혀 함께 쓴다)
  4) 확정 규칙: 본사 주소가 '대구'로 시작하는 후보가 1개면 확정. 여럿이면 팩토리온 공장의 구·군과 같은 쪽,
     그래도 여럿이면 미확정. 후보는 있으나 대구 본사가 없으면 '본사 타지역'(미확정). 미확정은 unmatched.csv 에.
     기업 DB 안에서 같은 회사가 여러 id(여러 단지 공장)면 한 법인을 여러 id 에 붙인다(다대일 허용).
  5) 하루 호출 한도(10,000)를 넘지 않게 호출 수를 세고, 상한(--budget, 기본 9,000)에 닿으면 캐시를 저장하고
     정상 종료한다. 다음 실행은 캐시 덕에 이어서 진행된다. 요청 간 0.2초, 429·네트워크 오류는 3회 재시도.

저장하지 않는 것: 대표자(ceo_nm)·전화·팩스·홈페이지 등 — 기업 사전 원칙. 주소는 시·구까지만.

사용: python3 scripts/dart_match.py                 # 전체
      python3 scripts/dart_match.py --sample 100    # 후보가 있는 기업 100곳만 (결과 표 출력, match.json 은 쓰지 않음)
      python3 scripts/dart_match.py --budget 3000   # 이번 실행 API 호출 상한
      python3 scripts/dart_match.py --workers 4     # 기업개황 동시 조회 수(기본 4)
환경: DART_KEY (.env 또는 secrets)
"""
import csv
import io
import json
import os
import re
import sys
import time
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
import threading
from concurrent.futures import ThreadPoolExecutor

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "scripts" / "data" / "dalseong_companies.csv"
DART_DIR = ROOT / "scripts" / "data" / "dart"
CORP_CACHE = DART_DIR / "corp_codes.json"          # gitignore
MATCH = DART_DIR / "match.json"
UNMATCHED = DART_DIR / "unmatched.csv"
CORP_INFO = ROOT / "scripts" / "state" / "dart_corp.json"   # collect_dart.py 와 공유
API = "https://opendart.fss.or.kr/api"
UA = {"User-Agent": "dalgubul-ai-note/0.1 (+personal blog collector)"}

from env import get as _env_get, missing as _env_missing, require as _env_require  # 공용 .env 로더 (scripts/env.py)
DART_KEY = _env_get("DART_KEY")


def arg(name: str, default):
    if name in sys.argv:
        i = sys.argv.index(name)
        return type(default)(sys.argv[i + 1]) if i + 1 < len(sys.argv) else default
    return default


SAMPLE = arg("--sample", 0)
BUDGET = arg("--budget", 9000)
WORKERS = arg("--workers", 4)      # company.json 동시 조회 수. 일 한도만 있고 초당 제한은 문서에 없어 4로 보수적으로
CALLS = 0
LOCK = threading.Lock()
FAILURES: list[str] = []


def redact(e: object) -> str:
    return re.sub(r"crtfc_key=[^&\s]+", "crtfc_key=***", str(e))


# ------------------------------------------------------------------ API
def get(path: str, **params):
    """JSON 또는 bytes. 429·네트워크 오류 3회 재시도. 호출 수를 센다."""
    global CALLS
    params["crtfc_key"] = DART_KEY
    for attempt in range(3):
        try:
            with LOCK:
                CALLS += 1
            r = requests.get(f"{API}/{path}", params=params, headers=UA, timeout=60)
            if r.status_code == 429:
                raise requests.HTTPError("429 Too Many Requests")
            r.raise_for_status()
            time.sleep(0.2)
            if path.endswith(".xml"):
                return r.content
            j = r.json()
            st = j.get("status")
            if st == "020":   # 사용 한도 초과 — 재시도 무의미
                FAILURES.append("일 한도 초과(020)")
                return None
            return j
        except Exception as e:  # noqa: BLE001
            wait = 2 * (attempt + 1)
            print(f"[dart] {path} {attempt+1}차 실패: {redact(e)} → {wait}s 후 재시도")
            time.sleep(wait)
    FAILURES.append(f"{path}: 3회 실패")
    return None


# ------------------------------------------------------------------ 이름 정규화
def norm(s: str) -> str:
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사|유한책임회사|\(사\)|\(재\)|\(합\)|합자회사|\s", "", s or "")
    s = re.sub(r"\([^)]*\)", "", s)
    return s.lower()


# ------------------------------------------------------------------ corpCode
def load_corp_codes() -> list[dict]:
    if CORP_CACHE.exists() and time.time() - CORP_CACHE.stat().st_mtime < 86400:
        return json.loads(CORP_CACHE.read_text(encoding="utf-8"))
    raw = get("corpCode.xml")
    if not raw:
        if CORP_CACHE.exists():
            print("[dart] corpCode 내려받기 실패 — 오래된 캐시 사용")
            return json.loads(CORP_CACHE.read_text(encoding="utf-8"))
        return []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        root = ET.fromstring(z.read(z.namelist()[0]))
    corps = [{"corp_code": e.findtext("corp_code"), "corp_name": (e.findtext("corp_name") or "").strip(),
              "stock_code": (e.findtext("stock_code") or "").strip()} for e in root.iter("list")]
    DART_DIR.mkdir(parents=True, exist_ok=True)
    CORP_CACHE.write_text(json.dumps(corps, ensure_ascii=False), encoding="utf-8")
    print(f"[dart] corpCode {len(corps):,}개 내려받아 캐시")
    return corps


# ------------------------------------------------------------------ 기업개황 캐시
def load_info() -> dict:
    if CORP_INFO.exists():
        try:
            return json.loads(CORP_INFO.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_info(info: dict) -> None:
    CORP_INFO.parent.mkdir(parents=True, exist_ok=True)
    CORP_INFO.write_text(json.dumps(info, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")


def company_info(corp: dict, info: dict) -> dict | None:
    """캐시에 상세(bizr_no)가 있으면 그대로. 없으면 company.json. 예산 소진이면 None."""
    hit = info.get(corp["corp_code"])
    if hit and "bizr_no" in hit:
        return hit
    if CALLS >= BUDGET:
        return None
    j = get("company.json", corp_code=corp["corp_code"])
    if not j or j.get("status") not in ("000",):
        return None
    adres = (j.get("adres") or "").strip()
    rec = {
        "name": j.get("corp_name") or corp["corp_name"],
        "stock_code": (j.get("stock_code") or corp.get("stock_code") or "").strip(),
        "bizr_no": j.get("bizr_no", ""), "jurir_no": j.get("jurir_no", ""),
        "induty_code": j.get("induty_code", ""), "est_dt": j.get("est_dt", ""),
        "region": " ".join(adres.split()[:2]),          # 시·구까지만
        "daegu": adres.startswith("대구"),
        "checked": date.today().isoformat(),
    }
    with LOCK:
        info[corp["corp_code"]] = rec
    return rec


# ------------------------------------------------------------------ 매칭
def decide(company: dict, cands: list[tuple[dict, dict]]) -> tuple[str, dict | None, str]:
    """(status, chosen_info_with_code, reason). cands = [(corp, info)]"""
    daegu = [(c, i) for c, i in cands if i["daegu"]]
    if len(daegu) == 1:
        c, i = daegu[0]
        return "matched", {**i, "corp_code": c["corp_code"]}, "이름+대구 본사"
    if len(daegu) > 1:
        same = [(c, i) for c, i in daegu if company["district"] and company["district"] in i["region"]]
        if len(same) == 1:
            c, i = same[0]
            return "matched", {**i, "corp_code": c["corp_code"]}, f"이름+대구 본사+{company['district']}"
        return "ambiguous", None, f"대구 본사 동명 {len(daegu)}개"
    return "hq_elsewhere", None, "본사 타지역: " + "; ".join(f"{i['name']}({i['region']})" for _, i in cands[:3])


def main() -> None:
    _env_require("DART_KEY")
    corps = load_corp_codes()
    if not corps:
        print("[dart] corpCode 없음 — 종료")
        return
    by: dict[str, list[dict]] = {}
    for c in corps:
        by.setdefault(norm(c["corp_name"]), []).append(c)
    with COMPANIES.open(encoding="utf-8-sig", newline="") as fh:
        companies = list(csv.DictReader(fh))
    info = load_info()
    # --- 1) 필요한 법인(후보) 목록을 모아 기업개황을 병렬로 미리 채운다. 60초마다 캐시를 저장해 중단돼도 이어간다
    need: dict[str, dict] = {}
    seen_ids = 0
    for co in companies:
        cands_c = by.get(norm(co["name"]), [])
        if not cands_c:
            continue
        if SAMPLE and seen_ids >= SAMPLE:
            break
        seen_ids += 1
        for c in cands_c[:8]:
            if not (info.get(c["corp_code"]) and "bizr_no" in info[c["corp_code"]]):
                need[c["corp_code"]] = c
    print(f"[dart] 기업개황 조회 필요 {len(need):,}개 법인 (캐시 {len(info):,}개 보유) · 동시 {WORKERS}")
    last_save = [time.time()]
    def fetch(c: dict) -> None:
        if CALLS >= BUDGET:
            return
        company_info(c, info)
        if time.time() - last_save[0] > 60:
            with LOCK:
                if time.time() - last_save[0] > 60:
                    save_info(info); last_save[0] = time.time()
    if need:
        with ThreadPoolExecutor(max_workers=max(1, WORKERS)) as ex:
            list(ex.map(fetch, list(need.values())))
        save_info(info)
        print(f"[dart] 기업개황 조회 끝 · 호출 {CALLS:,} · 캐시 {len(info):,}개")
    # --- 2) 판정 (여기서부터는 캐시만 읽으므로 빠르다)
    prev = json.loads(MATCH.read_text(encoding="utf-8")) if MATCH.exists() else {"companies": {}}
    result: dict[str, dict] = dict(prev.get("companies", {})) if not SAMPLE else {}
    unmatched: list[dict] = []
    stats = {"no_candidate": 0, "matched": 0, "ambiguous": 0, "hq_elsewhere": 0, "pending": 0}
    sample_rows: list[dict] = []
    processed = 0
    for co in companies:
        cands_c = by.get(norm(co["name"]), [])
        if not cands_c:
            stats["no_candidate"] += 1
            result.pop(co["id"], None)
            continue
        if SAMPLE and processed >= SAMPLE:
            break
        processed += 1
        pairs = []
        pending = False
        for c in cands_c[:8]:                      # 동명 8개 넘으면 그 이상은 보지 않는다(희귀, 한도 보호)
            i = company_info(c, info)
            if i is None:
                pending = True
                break
            pairs.append((c, i))
        if pending:
            stats["pending"] += 1
            continue
        status, chosen, reason = decide(co, pairs)
        stats[status] += 1
        if status == "matched" and chosen:
            result[co["id"]] = {
                "corp_code": chosen["corp_code"], "corp_name": chosen["name"], "stock_code": chosen["stock_code"],
                "bizr_no": chosen["bizr_no"], "jurir_no": chosen["jurir_no"], "induty_code": chosen["induty_code"],
                "region": chosen["region"], "method": reason, "checked": date.today().isoformat(),
            }
        else:
            result[co["id"]] = {"status": status, "reason": reason, "checked": date.today().isoformat()}
            unmatched.append({"id": co["id"], "name": co["name"], "district": co["district"], "complex": co["complex"],
                              "status": status, "reason": reason,
                              "candidates": " | ".join(f"{i['name']}[{c['corp_code']}] {i['region']}" for c, i in pairs)})
        sample_rows.append({"id": co["id"], "name": co["name"], "district": co["district"], "status": status,
                            "corp_name": chosen["name"] if chosen else "", "region": chosen["region"] if chosen else "",
                            "stock": chosen["stock_code"] if chosen else "", "reason": reason})
        if len(sample_rows) % 200 == 0:
            save_info(info)
    save_info(info)

    if SAMPLE:
        print(f"\n=== 샘플 {len(sample_rows)}곳 (API 호출 {CALLS}건) ===")
        print(f"{'id':6} {'상태':12} {'기업 DB 회사명':22} {'구군':6} {'DART 법인명':22} {'본사':14} {'종목':6} 사유")
        for r in sample_rows:
            print(f"{r['id']:6} {r['status']:12} {r['name'][:20]:22} {r['district']:6} {r['corp_name'][:20]:22} {r['region'][:12]:14} {r['stock']:6} {r['reason'][:40]}")
    else:
        DART_DIR.mkdir(parents=True, exist_ok=True)
        MATCH.write_text(json.dumps({"as_of": date.today().isoformat(), "source": "OpenDART corpCode.xml + company.json",
                                     "companies": dict(sorted(result.items()))}, ensure_ascii=False, indent=0), encoding="utf-8")
        with UNMATCHED.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["id", "name", "district", "complex", "status", "reason", "candidates"])
            w.writeheader(); w.writerows(unmatched)
    matched_corps = len({v["corp_code"] for v in result.values() if "corp_code" in v})
    line = (f"[요약] 기업 {len(companies):,} · 후보 없음 {stats['no_candidate']:,} · 확정 {stats['matched']:,}(법인 {matched_corps:,}) · "
            f"동명 미확정 {stats['ambiguous']:,} · 본사 타지역 {stats['hq_elsewhere']:,} · 한도로 보류 {stats['pending']:,} · API 호출 {CALLS:,}")
    if FAILURES:
        line += " / 실패: " + " | ".join(dict.fromkeys(FAILURES))
    print(line)
    sp = os.environ.get("GITHUB_STEP_SUMMARY")
    if sp:
        with open(sp, "a", encoding="utf-8") as fh:
            fh.write("## DART 법인 매칭\n\n- " + line.replace("[요약] ", "") + "\n\n")


if __name__ == "__main__":
    main()
