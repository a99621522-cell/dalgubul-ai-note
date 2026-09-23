#!/usr/bin/env python3
"""match.json 의 법인마다 OpenDART 단일회사 주요계정(fnlttSinglAcnt.json)으로 최근 5개 사업연도 재무를 모아
scripts/data/dart/financials.json 에 저장한다. (사업보고서 reprt_code=11011)

- 연결재무제표(CFS)가 있으면 CFS, 없으면 개별(OFS). 연도마다 어느 쪽인지 fs 로 기록
- 항목: 매출액(매출액·수익(매출액)·영업수익), 영업이익, 당기순이익, 자산총계, 부채총계, 자본총계. 원 단위 정수
- 한 번의 호출은 당기·전기·전전기 3개 연도를 함께 주므로, 최신 연도부터 두 칸씩 건너뛰며 호출해 5년을 채운다
  (예: 2025 보고서 → 2025·2024·2023, 2023 보고서 → 2023·2022·2021). 이미 있는 연도는 다시 받지 않는다
- status 013(조회 데이터 없음)이면 그 법인은 "공시 없음" 으로 기록하고 넘어간다. 다음 연도 보고서가 나오면
  (checked 가 90일 이상 지났으면) 다시 시도한다
- 하루 호출 상한(--budget, 기본 9,000)에 닿으면 저장하고 정상 종료. 요청 간 0.2초, 429·네트워크 오류 3회 재시도

사용: python3 scripts/dart_financials.py [--budget N] [--years 5]
환경: DART_KEY
"""
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
DART_DIR = ROOT / "scripts" / "data" / "dart"
MATCH = DART_DIR / "match.json"
FIN = DART_DIR / "financials.json"
API = "https://opendart.fss.or.kr/api"
UA = {"User-Agent": "dalgubul-ai-note/0.1 (+personal blog collector)"}

_ENV = ROOT / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())
DART_KEY = os.environ.get("DART_KEY", "").strip()


def arg(name: str, default):
    if name in sys.argv:
        i = sys.argv.index(name)
        return type(default)(sys.argv[i + 1]) if i + 1 < len(sys.argv) else default
    return default


BUDGET = arg("--budget", 9000)
YEARS = arg("--years", 5)
CALLS = 0
FAILURES: list[str] = []

# 계정명 → 우리 키. DART 표기가 회사마다 조금씩 다르다
ACCOUNTS = {
    "revenue": ("매출액", "수익(매출액)", "영업수익", "매출"),
    "op_income": ("영업이익", "영업이익(손실)", "영업손익"),
    "net_income": ("당기순이익", "당기순이익(손실)", "당기순손익", "당기순이익(손실)_지배"),
    "assets": ("자산총계",),
    "liabilities": ("부채총계",),
    "equity": ("자본총계",),
}


def redact(e: object) -> str:
    return re.sub(r"crtfc_key=[^&\s]+", "crtfc_key=***", str(e))


def get(path: str, **params):
    global CALLS
    params["crtfc_key"] = DART_KEY
    for attempt in range(3):
        try:
            CALLS += 1
            r = requests.get(f"{API}/{path}", params=params, headers=UA, timeout=60)
            if r.status_code == 429:
                raise requests.HTTPError("429 Too Many Requests")
            r.raise_for_status()
            time.sleep(0.2)
            j = r.json()
            if j.get("status") == "020":
                FAILURES.append("일 한도 초과(020)")
                return None
            return j
        except Exception as e:  # noqa: BLE001
            wait = 2 * (attempt + 1)
            print(f"[dart] {path} {attempt+1}차 실패: {redact(e)} → {wait}s 후 재시도")
            time.sleep(wait)
    FAILURES.append(f"{path}: 3회 실패")
    return None


def to_int(s: str) -> int | None:
    s = (s or "").strip().replace(",", "")
    if not s or s == "-":
        return None
    m = re.fullmatch(r"\(?(-?\d+)\)?", s)
    if not m:
        return None
    v = int(m.group(1))
    return -abs(v) if s.startswith("(") else v


def parse(rows: list[dict], bsns_year: int) -> dict[str, dict]:
    """응답 행들 → {연도: {fs, revenue, ...}}. 연도마다 CFS 우선."""
    out: dict[str, dict] = {}
    by_fs: dict[str, list[dict]] = {"CFS": [], "OFS": []}
    for r in rows:
        by_fs.setdefault(r.get("fs_div", "OFS"), []).append(r)
    for fs in ("CFS", "OFS"):
        if not by_fs.get(fs):
            continue
        cols = {str(bsns_year): "thstrm_amount", str(bsns_year - 1): "frmtrm_amount", str(bsns_year - 2): "bfefrmtrm_amount"}
        for year, col in cols.items():
            if year in out:                       # 이미 CFS 로 채운 연도는 OFS 로 덮지 않는다
                continue
            rec: dict = {"fs": fs, "report": str(bsns_year)}
            got = False
            for key, names in ACCOUNTS.items():
                for r in by_fs[fs]:
                    nm = (r.get("account_nm") or "").replace(" ", "")
                    if nm in names:
                        v = to_int(r.get(col, ""))
                        if v is not None:
                            rec[key] = v
                            got = True
                        break
            if got:
                out[year] = rec
    return out


def main() -> None:
    if not DART_KEY:
        print("[dart] DART_KEY 없음 — 종료")
        return
    if not MATCH.exists():
        print("[dart] match.json 없음 — dart_match.py 먼저")
        return
    match = json.loads(MATCH.read_text(encoding="utf-8"))
    corps: dict[str, str] = {}
    for v in match.get("companies", {}).values():
        if "corp_code" in v:
            corps[v["corp_code"]] = v.get("corp_name", "")
    fin: dict = json.loads(FIN.read_text(encoding="utf-8")) if FIN.exists() else {}
    this_year = date.today().year
    targets = [str(y) for y in range(this_year - 1, this_year - 1 - YEARS, -1)]   # 예: 2025..2021
    today = date.today()
    stats = {"corps": len(corps), "fetched": 0, "already": 0, "none": 0, "pending": 0, "with_data": 0}
    for i, (code, name) in enumerate(sorted(corps.items())):
        rec = fin.get(code) or {"corp_name": name, "years": {}, "status": "", "checked": ""}
        rec["corp_name"] = rec.get("corp_name") or name
        missing = [y for y in targets if y not in rec["years"]]
        stale = rec.get("checked") and (today - date.fromisoformat(rec["checked"])).days >= 90
        if not missing or (rec.get("status") == "none" and not stale):
            stats["already"] += 1
            fin[code] = rec
            continue
        if CALLS >= BUDGET:
            stats["pending"] += 1
            continue
        # 최신 연도부터 두 칸씩: 한 호출이 3개 연도를 준다
        year_calls = [y for k, y in enumerate(targets) if k % 2 == 0] + ([targets[-1]] if len(targets) % 2 == 0 else [])
        any_data = False
        for y in year_calls:
            if all(t in rec["years"] for t in targets):
                break
            if CALLS >= BUDGET:
                break
            j = get("fnlttSinglAcnt.json", corp_code=code, bsns_year=y, reprt_code="11011")
            if j is None:
                continue
            if j.get("status") == "013":
                continue
            if j.get("status") != "000":
                FAILURES.append(f"{code} {y}: {j.get('status')} {j.get('message')}")
                continue
            parsed = parse(j.get("list", []), int(y))
            for yr, val in parsed.items():
                if yr in targets and yr not in rec["years"]:
                    rec["years"][yr] = val
            any_data = any_data or bool(parsed)
        rec["checked"] = today.isoformat()
        rec["status"] = "ok" if rec["years"] else "none"
        stats["fetched"] += 1
        if rec["status"] == "none":
            stats["none"] += 1
        fin[code] = rec
        if stats["fetched"] % 100 == 0:
            FIN.write_text(json.dumps(fin, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
            print(f"[dart] {stats['fetched']}개 법인 처리, 호출 {CALLS}")
    stats["with_data"] = sum(1 for v in fin.values() if v.get("years"))
    DART_DIR.mkdir(parents=True, exist_ok=True)
    FIN.write_text(json.dumps(fin, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    line = (f"[요약] 매칭 법인 {stats['corps']:,} · 이번에 조회 {stats['fetched']:,} · 이미 완료 {stats['already']:,} · "
            f"공시 없음(이번) {stats['none']:,} · 한도로 보류 {stats['pending']:,} · 재무 있음 누계 {stats['with_data']:,} · API 호출 {CALLS:,}")
    if FAILURES:
        line += " / 실패: " + " | ".join(list(dict.fromkeys(FAILURES))[:5])
    print(line)
    sp = os.environ.get("GITHUB_STEP_SUMMARY")
    if sp:
        with open(sp, "a", encoding="utf-8") as fh:
            fh.write("## DART 재무 수집\n\n- " + line.replace("[요약] ", "") + "\n\n")


if __name__ == "__main__":
    main()
