#!/usr/bin/env python3
"""한국은행 경제통계시스템(ECOS) 오픈API → data/ecos/<key>.csv(대구 항목 행만) + <key>.json(표 이름·코드·주기·기간·출처). 표 목록은 config/ecos_tables.yml.

- 키: 환경변수 ECOS_KEY(인증키 하나로 모든 표). 없으면 아무것도 받지 않고 끝낸다(무인 실행이 죽지 않게).
- 표마다 StatisticSearch 를 부른다(항목 코드 없이 전체 → ITEM_NAME1~4 에 '대구'가 든 행만). 실패는 로그만 남기고 다음 표로.
- --discover: stat_code 가 빈 표는 통계표 목록(StatisticTableList)에서 search 낱말이 든 표를, stat_code 가 있는 표는
  항목 목록(StatisticItemList)에서 '대구'가 든 항목을 찍는다. 확인해서 yml 에 채운다.
- --only key,key  --dry-run(주소만 출력)  --summary(data/ecos/summary.md 만 다시 씀)
- 이 세션 환경은 ecos.bok.or.kr 접속이 막혀 있어 GitHub Actions(ecos.yml)가 대신 돈다. 평가 없음, 값은 그대로.
"""
import argparse, csv, json, os, sys, time
from datetime import date
from pathlib import Path
import requests, yaml

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "ecos_tables.yml"
OUT = ROOT / "data" / "ecos"
API = "https://ecos.bok.or.kr/api"
UA = "daitda-note-bot/1.0 (+https://daitda.co.kr)"
PAGE = 1000


def load():
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    d = cfg.get("defaults", {})
    return [{**d, **t} for t in cfg.get("tables", [])]


def period_range(cycle: str, years: int) -> tuple[str, str]:
    y = date.today().year
    return {"M": (f"{y - years}01", f"{y}12"), "Q": (f"{y - years}Q1", f"{y}Q4"), "S": (f"{y - years}S1", f"{y}S2"),
            "D": (f"{y - years}0101", f"{y}1231")}.get(cycle, (str(y - years), str(y)))


def call(path: str) -> dict:
    """접속 실패는 5·15·30초 뒤 다시 시도. 응답이 {"RESULT": {...}} 면 오류(INFO-200 은 '데이터 없음')."""
    last = None
    for wait in (0, 5, 15, 30):
        if wait:
            time.sleep(wait)
        try:
            r = requests.get(f"{API}/{path}", headers={"User-Agent": UA}, timeout=(20, 120))
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout) as e:
            last = e
    raise RuntimeError(f"접속 실패(4회): {type(last).__name__}")


def rows_of(data: dict, service: str) -> list:
    if service in data:
        return data[service].get("row") or []
    res = data.get("RESULT") or {}
    code = res.get("CODE", "")
    if code == "INFO-200":     # 해당하는 데이터가 없습니다
        return []
    raise RuntimeError(f"ECOS 오류 {code}: {res.get('MESSAGE', '')}")


def paged(key: str, service: str, tail: str, limit: int = 20) -> list:
    out, start = [], 1
    for _ in range(limit):
        data = call(f"{service}/{key}/json/kr/{start}/{start + PAGE - 1}/{tail}")
        rows = rows_of(data, service)
        out.extend(rows)
        total = int((data.get(service) or {}).get("list_total_count") or 0)
        if len(rows) < PAGE or len(out) >= total:
            break
        start += PAGE
        time.sleep(0.3)
    return out


def fetch_table(t: dict, key: str, dry: bool) -> dict | None:
    cycle = t.get("cycle", "M")
    start, end = period_range(cycle, int(t.get("years", 6)))
    tail = f"{t['stat_code']}/{cycle}/{start}/{end}"
    if dry:
        print(f"[dry] {t['key']}: {API}/StatisticSearch/***/json/kr/1/{PAGE}/{tail}")
        return None
    rows = paged(key, "StatisticSearch", tail, int(t.get("max_pages", 20)))   # 큰 표(전 지역×여러 항목)는 max_pages 를 늘린다 — 기본 20쪽에서 잘리면 최근 달이 빠진다(2026-10-03 card-region)
    words = t.get("area") if t.get("area") is not None else ["대구"]
    keep = [r for r in rows if not words or any(w in " ".join(r.get(f"ITEM_NAME{i}", "") or "" for i in range(1, 5)) for w in words)]
    fields = ["TIME", "ITEM_NAME1", "ITEM_NAME2", "ITEM_NAME3", "ITEM_NAME4", "DATA_VALUE", "UNIT_NAME"]
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{t['key']}.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in keep:
            w.writerow({k: r.get(k, "") for k in fields})
    meta = {"key": t["key"], "name": t["name"], "stat_name": (rows[0].get("STAT_NAME") if rows else ""), "stat_code": t["stat_code"],
            "cycle": cycle, "period": [start, end], "rows_total": len(rows), "rows_kept": len(keep),
            "latest": max((r.get("TIME", "") for r in keep), default=""), "unit": (keep[0].get("UNIT_NAME", "") if keep else ""),
            "areas": t.get("areas", []), "fetched": date.today().isoformat(),
            "source_url": f"https://ecos.bok.or.kr/#/Short/{t['stat_code']}", "source_note": f"한국은행 ECOS 통계표 {t['stat_code']}",
            "note": t.get("note", "")}
    (OUT / f"{t['key']}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{t['key']}: {len(rows)}행 중 대구 {len(keep)}행, 최근 {meta['latest']}")
    return meta


_TABLES: list | None = None


def discover(t: dict, key: str) -> None:
    global _TABLES
    try:
        if t.get("stat_code"):
            items = paged(key, "StatisticItemList", t["stat_code"], limit=3)
            hit = [i for i in items if "대구" in (i.get("ITEM_NAME") or "")]
            print(f"[discover] {t['key']} {t['stat_code']}: 항목 {len(items)}개, '대구' 항목 {len(hit)}개")
            for i in hit[:10]:
                print(f"   {i.get('GRP_CODE')} {i.get('ITEM_CODE')} | {i.get('ITEM_NAME')} | {i.get('CYCLE')} {i.get('START_TIME')}~{i.get('END_TIME')} | {i.get('UNIT_NAME', '')}")
            return
        if _TABLES is None:
            _TABLES = paged(key, "StatisticTableList", "", limit=10)
            print(f"[discover] 통계표 목록 {len(_TABLES)}개")
        words = [w for w in str(t.get("search") or t["name"]).split() if w]
        cand = [x for x in _TABLES if all(w in (x.get("STAT_NAME") or "") for w in words) and (x.get("SRCH_YN") or "Y") == "Y"]
        print(f"[discover] {t['key']} ← '{' '.join(words)}' 후보 {len(cand)}개")
        for x in cand[:15]:
            print(f"   {x.get('STAT_CODE')} | {x.get('STAT_NAME')} | {x.get('CYCLE', '')} | {x.get('ORG_NAME', '')}")
    except Exception as e:  # noqa: BLE001
        print(f"[discover] {t['key']}: 실패 {e}")


def write_summary() -> None:
    files = sorted(OUT.glob("*.json"))
    lines = ["# 한국은행 ECOS 수집 결과", "", f"갱신 {date.today().isoformat()} · 표 {len(files)}개 · 설정 config/ecos_tables.yml", "",
             "| key | 표 | 코드 | 주기 | 최근 | 대구 행 | 단위 |", "|---|---|---|---|---|---:|---|"]
    for f in files:
        m = json.loads(f.read_text(encoding="utf-8"))
        lines.append(f"| {m['key']} | {m.get('stat_name') or m['name']} | {m['stat_code']} | {m['cycle']} | {m['latest']} | {m['rows_kept']} | {m['unit']} |")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    tables = load()
    if a.only:
        want = set(a.only.split(","))
        tables = [t for t in tables if t["key"] in want]
    if a.summary:
        write_summary(); return 0
    key = os.environ.get("ECOS_KEY", "").strip().strip('"\'')
    if not key and not a.dry_run:
        print("ECOS_KEY 가 없어 받지 않음(GitHub Secrets 에 넣으면 동작)"); return 0
    for t in tables:
        if a.discover:
            discover(t, key); time.sleep(0.3); continue
        if not t.get("stat_code"):
            print(f"{t['key']}: stat_code 비어 있음 — --discover 로 후보 확인"); continue
        try:
            fetch_table(t, key, a.dry_run)
        except Exception as e:  # noqa: BLE001
            print(f"{t['key']}: 실패 — {e}")
        time.sleep(0.5)
    if not a.discover and not a.dry_run:
        write_summary()
    return 0


if __name__ == "__main__":
    sys.exit(main())
