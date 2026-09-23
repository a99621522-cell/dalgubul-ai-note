#!/usr/bin/env python3
"""OpenDART 공시 → 대구 기업의 '확장 신호' 공시만 골라 scripts/inbox/dart-YYYYMMDD.json 으로 떨군다.
그 뒤는 collect.py 가 inbox 를 읽어 Gemini 요약 → economy 초안(draft) → 사람 승인. (로드맵 4단계 11번의 첫 조각)

흐름
  1) list.json      최근 N일 공시 목록(주요사항보고 B, 거래소공시 I)을 페이지로 받는다
  2) 보고서명 필터   신규시설투자·유상증자·타법인주식취득·공급계약·영업양수·합병 등 키워드(sources.yml dart.keywords)
  3) 대구 판정      회사마다 company.json 으로 본사 주소를 받아 '대구광역시' 여부를 본다.
                    결과는 scripts/state/dart_corp.json 에 캐시(회사당 1회) — 호출 한도(일 1만 건) 안에서 끝난다
  4) 기업 사전 연결  회사명이 dalseong_companies.csv 와 정확히 맞으면 /companies/<id>/ 링크를 본문에 넣는다
  5) inbox JSON     collect.py 의 inbox 형식({title,url,source,category,body})으로 저장

원칙: 공시 '사실'과 원문 링크만 싣는다. 평가·전망·순위 없음(CLAUDE.md). 수치는 목록 API 에 없으므로 본문에
'원문 확인 필요'로 두고, 요약 단계도 원문에 없는 수치를 만들지 않도록 돼 있다.
외부 API 가 실패해도 죽지 않고 로그를 남기고 끝낸다(매일 무인 실행).

사용: python3 scripts/collect_dart.py            # inbox JSON 생성
      python3 scripts/collect_dart.py --dry-run  # 후보만 출력(캐시는 갱신, 파일은 안 씀)
환경: DART_KEY (OpenDART 인증키). 로컬은 .env, Actions 는 secrets.DART_KEY
"""
import csv
import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
import yaml

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "scripts" / "inbox"
STATE = ROOT / "scripts" / "state" / "dart_corp.json"
CONFIG = ROOT / "scripts" / "sources.yml"
COMPANIES = ROOT / "scripts" / "data" / "dalseong_companies.csv"
DRY_RUN = "--dry-run" in sys.argv
UA = {"User-Agent": "dalgubul-ai-note/0.1 (+personal blog collector)"}
API = "https://opendart.fss.or.kr/api"

# 로컬 실행 편의: .env (collect.py 와 같은 방식, 기존 환경변수 우선)
_ENV = ROOT / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

DART_KEY = os.environ.get("DART_KEY", "").strip()
CORP_CLS = {"Y": "유가증권", "K": "코스닥", "N": "코넥스", "E": "비상장"}
FAILURES: list[str] = []


def redact(e: object) -> str:
    return re.sub(r"crtfc_key=[^&\s]+", "crtfc_key=***", str(e))


def cfg() -> dict:
    d = yaml.safe_load(CONFIG.read_text(encoding="utf-8")).get("dart") or {}
    d.setdefault("days_back", 3)
    d.setdefault("types", ["B", "I"])
    d.setdefault("keywords", ["신규시설투자", "유상증자", "타법인주식", "단일판매", "공급계약", "영업양수", "합병", "자산양수", "유형자산", "투자판단", "공장"])
    d.setdefault("exclude", ["철회", "취소"])
    d.setdefault("region_words", ["대구광역시", "대구시"])
    d.setdefault("max_items", 20)
    d.setdefault("max_company_lookups", 300)
    return d


def get(path: str, **params) -> dict | None:
    params["crtfc_key"] = DART_KEY
    try:
        r = requests.get(f"{API}/{path}", params=params, headers=UA, timeout=30)
        r.raise_for_status()
        j = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[dart] {path} 실패: {redact(e)}")
        FAILURES.append(f"{path}: {redact(e)[:160]}")
        return None
    st = j.get("status")
    if st == "013":            # 조회 결과 없음 — 정상
        return {"list": []}
    if st != "000":
        print(f"[dart] {path} 오류 {st}: {j.get('message')}")
        FAILURES.append(f"{path} status {st}: {j.get('message')}")
        return None
    return j


def fetch_list(c: dict) -> list[dict]:
    end = date.today()
    bgn = end - timedelta(days=int(c["days_back"]))
    out: list[dict] = []
    for ty in c["types"]:
        page = 1
        while True:
            j = get("list.json", bgn_de=bgn.strftime("%Y%m%d"), end_de=end.strftime("%Y%m%d"),
                    pblntf_ty=ty, last_reprt_at="Y", page_no=page, page_count=100)
            if j is None:
                break
            out += j.get("list", [])
            total = int(j.get("total_page") or 1)
            if page >= total or page >= 40:   # 40쪽(4,000건)이면 하루치로 충분하고도 남는다
                break
            page += 1
            time.sleep(0.2)
    print(f"[dart] 최근 {c['days_back']}일 공시 {len(out)}건 (유형 {','.join(c['types'])})")
    return out


def wanted(report_nm: str, c: dict) -> bool:
    if any(x in report_nm for x in c["exclude"]):
        return False
    return any(k in report_nm for k in c["keywords"])


def load_cache() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_cache(cache: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")


def is_daegu(corp_code: str, corp_name: str, cache: dict, c: dict, budget: list[int]) -> bool | None:
    """캐시에 있으면 그 값. 없으면 company.json 으로 주소를 받아 판정하고 캐시. 한도를 넘기면 None(이번 실행은 보류)."""
    hit = cache.get(corp_code)
    if hit is not None:
        return bool(hit.get("daegu"))
    if budget[0] <= 0:
        return None
    budget[0] -= 1
    j = get("company.json", corp_code=corp_code)
    time.sleep(0.15)
    if j is None:
        return None
    adres = (j.get("adres") or "").strip()
    daegu = any(w in adres for w in c["region_words"])
    # 주소는 시·구 단위까지만 저장한다(회사 주소는 공개 정보지만 필요한 건 지역 판정뿐)
    cache[corp_code] = {"name": corp_name, "region": " ".join(adres.split()[:2]), "daegu": daegu, "checked": date.today().isoformat()}
    return daegu


def company_index() -> dict[str, str]:
    """기업 사전 회사명(정규화) → id. 법인 접미어·공백을 떼고 정확히 같은 것만 잇는다."""
    def norm(s: str) -> str:
        s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사|\(사\)|\s", "", s or "")
        return s.lower()
    idx: dict[str, str] = {}
    if not COMPANIES.exists():
        return idx
    with COMPANIES.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            k = norm(r.get("name", ""))
            if k and k not in idx:
                idx[k] = r.get("id", "")
    return idx


def build_items(rows: list[dict], c: dict) -> list[dict]:
    cache = load_cache()
    budget = [int(c["max_company_lookups"])]
    cidx = company_index()
    norm = lambda s: re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사|\(사\)|\s", "", s or "").lower()  # noqa: E731
    seen_rcept: set[str] = set()
    cand = [r for r in rows if wanted(r.get("report_nm", ""), c)]
    print(f"[dart] 키워드 통과 {len(cand)}건")
    items: list[dict] = []
    deferred = 0
    for r in cand:
        rc = r.get("rcept_no", "")
        if not rc or rc in seen_rcept:
            continue
        seen_rcept.add(rc)
        d = is_daegu(r.get("corp_code", ""), r.get("corp_name", ""), cache, c, budget)
        if d is None:
            deferred += 1
            continue
        if not d:
            continue
        name = r.get("corp_name", "").strip()
        rpt = r.get("report_nm", "").strip()
        dt = r.get("rcept_dt", "")
        dt_h = f"{dt[:4]}-{dt[4:6]}-{dt[6:]}" if len(dt) == 8 else dt
        cid = cidx.get(norm(name))
        region = cache.get(r.get("corp_code", ""), {}).get("region", "")
        body = "\n".join([
            f"회사: {name} ({CORP_CLS.get(r.get('corp_cls', ''), r.get('corp_cls', ''))}"
            + (f", 종목코드 {r['stock_code']}" if r.get("stock_code") else "") + ")",
            f"본사 소재지: {region}",
            f"공시: {rpt}",
            f"접수일: {dt_h}",
            f"제출인: {r.get('flr_nm', '')}",
            f"원문: https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rc}",
            *( [f"기업 사전: /companies/{cid}/"] if cid else [] ),   # 공장등록이 없는 상장사(건설 등)는 사전에 없다 — 그때는 줄 자체를 뺀다
            "※ 이 자료는 공시 목록(제목·일자)만 담고 있다. 금액·규모·일정 등 세부 수치는 공시 원문에서 확인해야 하며, "
            "요약에 원문에 없는 수치를 쓰지 말 것.",
        ])
        items.append({
            "title": f"{name} {rpt} ({dt_h})",
            "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rc}",
            "source": "금융감독원 전자공시(DART)",
            "category": "economy",
            "body": body,
            "deadline": None,
        })
        if len(items) >= int(c["max_items"]):
            break
    save_cache(cache)
    print(f"[dart] 대구 기업 공시 {len(items)}건 (주소 조회 보류 {deferred}건, 캐시 {len(cache)}개사)")
    return items


def summary(n_list: int, n_items: int, path: Path | None) -> None:
    line = f"[요약] DART 공시 {n_list}건 → 대구 확장신호 {n_items}건" + (f" → {path.name}" if path else "")
    if FAILURES:
        line += " / 실패: " + " | ".join(dict.fromkeys(FAILURES))
    print(line)
    sp = os.environ.get("GITHUB_STEP_SUMMARY")
    if sp:
        with open(sp, "a", encoding="utf-8") as fh:
            fh.write(f"## DART 수집\n\n- 공시 {n_list}건 → 대구 확장신호 {n_items}건" + (f" → `{path.name}`" if path else "") + "\n")
            if FAILURES:
                fh.write("- 실패: " + " | ".join(dict.fromkeys(FAILURES)) + "\n")
            fh.write("\n")
    if n_list == 0 and FAILURES:
        print("::error title=DART 수집 실패::공시 목록을 받지 못함 — 키·네트워크 확인")


def main() -> None:
    if not DART_KEY:
        print("[dart] DART_KEY 없음 — 건너뜀")
        return
    c = cfg()
    rows = fetch_list(c)
    items = build_items(rows, c) if rows else []
    path = None
    if items and not DRY_RUN:
        INBOX.mkdir(exist_ok=True)
        path = INBOX / f"dart-{date.today().strftime('%Y%m%d')}.json"
        path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    for it in items:
        print("  ·", "[dry-run]" if DRY_RUN else "저장:", it["title"])
    summary(len(rows), len(items), path)


if __name__ == "__main__":
    main()
