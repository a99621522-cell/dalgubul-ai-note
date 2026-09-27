#!/usr/bin/env python3
"""통계청 KOSIS 공유서비스 → data/kosis/<key>.csv(대구 행만) + <key>.json(표 이름·단위·기간·출처). 표 목록은 config/kosis_tables.yml.

- 키: 환경변수 KOSIS_KEY(인증키 하나로 모든 표). 없으면 아무것도 받지 않고 끝낸다(무인 실행이 죽지 않게).
- 표마다 통계자료 조회 API 를 부른다. 실패는 로그만 남기고 다음 표로.
- --discover: tbl_id 가 빈 표의 search 낱말로 통계표 검색 API 를 불러 후보(표 이름·orgId·tblId)를 찍는다. 확인해서 yml 에 채운다.
- --only key,key  --dry-run(주소만 출력)  --summary(data/kosis/summary.md 만 다시 씀)
- 이 세션 환경은 kosis.kr 접속이 막혀 있어 GitHub Actions(kosis.yml)가 대신 돈다. 평가 없음, 값은 그대로.
"""
import argparse, csv, json, os, re, sys, time
from datetime import date
from pathlib import Path
import requests, yaml

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "kosis_tables.yml"
OUT = ROOT / "data" / "kosis"
API_DATA = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
API_SEARCH = "https://kosis.kr/openapi/statisticsSearch.do"
UA = "daitda-note-bot/1.0 (+https://note.daitda.co.kr)"


def load():
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    d = cfg.get("defaults", {})
    return [{**d, **t} for t in cfg.get("tables", [])]


def period_range(prd_se: str, years: int) -> tuple[str, str]:
    y = date.today().year
    if prd_se == "M":
        return f"{y - years}01", f"{y}12"
    if prd_se == "Q":
        return f"{y - years}01", f"{y}04"
    return str(y - years), str(y)


def fetch_table(t: dict, key: str, dry: bool) -> dict | None:
    start, end = period_range(t.get("prd_se", "Y"), int(t.get("years", 6)))
    params = {"method": "getList", "apiKey": key, "itmId": "ALL", "objL1": "ALL", "objL2": "ALL", "objL3": "ALL", "objL4": "ALL",
              "format": "json", "jsonVD": "Y", "prdSe": t.get("prd_se", "Y"), "startPrdDe": start, "endPrdDe": end,
              "orgId": str(t["org_id"]), "tblId": t["tbl_id"]}
    if dry:
        print(f"[dry] {t['key']}: {API_DATA}?" + "&".join(f"{k}={'***' if k == 'apiKey' else v}" for k, v in params.items()))
        return None
    r = requests.get(API_DATA, params=params, headers={"User-Agent": UA}, timeout=90)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("err"):
        raise RuntimeError(f"KOSIS 오류 {data.get('err')}: {data.get('errMsg')}")
    rows = data if isinstance(data, list) else []
    area_words = t.get("area") or ["대구"]
    col = t.get("area_col")
    keep = []
    for row in rows:
        names = [row.get(f"{c}_NM", "") for c in ("C1", "C2", "C3", "C4")]
        hay = row.get(f"{col}_NM", "") if col else " ".join(names)
        if any(w in hay for w in area_words):
            keep.append(row)
    if not keep and rows:   # 지역 열이 없는 표(전국 표)면 전부 남긴다
        keep = rows
    fields = ["PRD_DE", "ITM_NM", "C1_NM", "C2_NM", "C3_NM", "C4_NM", "DT", "UNIT_NM"]
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{t['key']}.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in keep:
            w.writerow({k: row.get(k, "") for k in fields})
    meta = {"key": t["key"], "name": t["name"], "tbl_nm": (rows[0].get("TBL_NM") if rows else ""), "org_id": str(t["org_id"]), "tbl_id": t["tbl_id"],
            "prd_se": t.get("prd_se", "Y"), "period": [start, end], "rows_total": len(rows), "rows_kept": len(keep),
            "latest": max((r.get("PRD_DE", "") for r in keep), default=""), "unit": (keep[0].get("UNIT_NM", "") if keep else ""),
            "areas": t.get("areas", []), "fetched": date.today().isoformat(),
            "source_url": f"https://kosis.kr/statHtml/statHtml.do?orgId={t['org_id']}&tblId={t['tbl_id']}", "note": t.get("note", "")}
    (OUT / f"{t['key']}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{t['key']}: {len(rows)}행 중 대구 {len(keep)}행, 최근 {meta['latest']}")
    return meta


def discover(t: dict, key: str) -> None:
    q = t.get("search") or t["name"]
    try:
        r = requests.get(API_SEARCH, params={"method": "getList", "apiKey": key, "searchNm": q, "format": "json", "jsonVD": "Y", "resultCount": 15},
                         headers={"User-Agent": UA}, timeout=60)
        items = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[discover] {t['key']}: 검색 실패 {e}")
        return
    if not isinstance(items, list):
        print(f"[discover] {t['key']}: {items}")
        return
    print(f"[discover] {t['key']} ← '{q}'")
    for it in items[:15]:
        print(f"   {it.get('ORG_ID')} {it.get('TBL_ID')} | {it.get('TBL_NM')} | {it.get('STAT_NM', '')} | {it.get('PRD_DE', '')}")


def write_summary(metas: list[dict]) -> None:
    files = sorted(OUT.glob("*.json"))
    lines = ["# KOSIS 수집 결과", "", f"갱신 {date.today().isoformat()} · 표 {len(files)}개 · 설정 config/kosis_tables.yml", "",
             "| key | 표 | 기간 | 최근 | 대구 행 | 단위 |", "|---|---|---|---|---:|---|"]
    for f in files:
        m = json.loads(f.read_text(encoding="utf-8"))
        lines.append(f"| {m['key']} | [{m.get('tbl_nm') or m['name']}]({m['source_url']}) | {m['prd_se']} {m['period'][0]}~{m['period'][1]} | {m['latest']} | {m['rows_kept']} | {m['unit']} |")
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
        write_summary([]); return 0
    key = os.environ.get("KOSIS_KEY", "")
    if not key and not a.dry_run:
        print("KOSIS_KEY 가 없어 받지 않음(GitHub Secrets 에 넣으면 동작)"); return 0
    metas = []
    for t in tables:
        if not t.get("tbl_id"):
            if a.discover:
                discover(t, key); time.sleep(0.5)
            else:
                print(f"{t['key']}: tbl_id 비어 있음 — --discover 로 후보 확인")
            continue
        try:
            m = fetch_table(t, key, a.dry_run)
            if m:
                metas.append(m)
        except Exception as e:  # noqa: BLE001
            print(f"{t['key']}: 실패 — {e}")
        time.sleep(0.5)
    write_summary(metas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
