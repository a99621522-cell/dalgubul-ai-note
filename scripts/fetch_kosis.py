#!/usr/bin/env python3
"""통계청 KOSIS 공유서비스 → data/kosis/<key>.csv(대구 행만) + <key>.json(표 이름·단위·기간·출처). 표 목록은 config/kosis_tables.yml.

- 키: 환경변수 KOSIS_KEY(인증키 하나로 모든 표). 없으면 아무것도 받지 않고 끝낸다(무인 실행이 죽지 않게).
- 표마다 통계자료 조회 API 를 부른다. 실패는 로그만 남기고 다음 표로.
- --discover: tbl_id 가 빈 표의 search 낱말로 통계표 검색 API 를 불러 후보(표 이름·orgId·tblId)를 찍는다. 확인해서 yml 에 채운다.
- --list '낱말 낱말': 검색 API 가 못 찾을 때 주제별 통계목록 트리(statisticsList)를 내려가며 이름에 낱말이 든 표를 찍는다(워크플로 입력 list).
  표 번호를 찾는 다른 방법: KOSIS 사이트에서 표를 연 뒤 주소의 tblId=… 를 읽는다(예: statHtml.do?orgId=101&tblId=DT_1K52D01).
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
API_LIST = "https://kosis.kr/openapi/statisticsList.do"      # 통계목록(주제별 트리) — 검색 API 가 못 찾는 표 번호를 트리에서 찾는다
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
    if prd_se == "H":
        return f"{y - years}01", f"{y}02"
    return str(y - years), str(y)


class NetworkDead(RuntimeError):
    """러너 IP 에서 kosis.kr 연결 자체가 안 되는 상태(2026-09-28 관찰: 러너 IP 에 따라 첫 연결부터 시간 초과, 같은 IP 로 재시도해도 소용없음)."""


def _call(params: dict) -> list | dict:
    """접속 실패(시간 초과·연결 끊김)는 5초 뒤 한 번 더. 그래도 안 되면 NetworkDead — 같은 러너에서 다른 표를 더 시도하지 않는다.
    워크플로가 러너(IP)를 바꿔 다시 시도한다(kosis.yml 의 attempt 매트릭스)."""
    last = None
    for wait in (0, 5):
        if wait:
            time.sleep(wait)
        try:
            r = requests.get(API_DATA, params=params, headers={"User-Agent": UA}, timeout=(10, 120))
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout) as e:
            last = e
    raise NetworkDead(f"kosis.kr 접속 실패: {type(last).__name__}")


def _err(data) -> str:
    return f"KOSIS 오류 {data.get('err')}: {data.get('errMsg')}" if isinstance(data, dict) and data.get("err") else ""


def _get_rows(base: dict, start: str, end: str) -> list:
    """분류 단계 수(objL1..objL8)는 표마다 달라 API 가 '잘못된 요청 변수'(21)를 돌려주므로 1단계부터 늘려 가며 맞춘다.
    한 번에 받을 수 있는 양을 넘기면(오류 메시지에 '초과') 기간을 1년씩 나눠 받는다."""
    last = ""
    for n in range(1, 9):
        params = {**base, "startPrdDe": start, "endPrdDe": end, **{f"objL{i}": "ALL" for i in range(1, n + 1)}}
        data = _call(params)
        e = _err(data)
        if not e:
            return data if isinstance(data, list) else []
        last = e
        if "초과" in e or "40000" in e.replace(",", ""):   # 오류 31: 40,000셀 초과 → 연도별, 그래도 넘치면 1단계 분류(시도) 코드별로 나눠 받는다
            rows = _split_fetch(params, start, end)
            if rows:
                return rows
        elif not any(x in e for x in ("21", "변수", "30", "존재하지")):   # 분류 단계가 모자라면 21 또는 30(데이터 없음)이 온다
            break
        time.sleep(0.3)
    raise RuntimeError(last or "응답 없음")


def _obj1_codes(params: dict) -> list[str]:
    """표 메타(ITM)에서 1단계 분류(OBJ_ID_SN=1)의 코드 목록. 40,000셀 초과 표를 코드별로 나눠 받을 때 쓴다."""
    try:
        r = requests.get("https://kosis.kr/openapi/statisticsData.do", params={"method": "getMeta", "apiKey": params["apiKey"], "format": "json", "jsonVD": "Y",
                         "orgId": params["orgId"], "tblId": params["tblId"], "type": "ITM"}, headers={"User-Agent": UA}, timeout=(20, 60))
        items = r.json()
        return [it["ITM_ID"] for it in items if str(it.get("OBJ_ID_SN")) == "1" and it.get("OBJ_ID") != "ITEM"] if isinstance(items, list) else []
    except Exception:  # noqa: BLE001
        return []


def _split_fetch(params: dict, start: str, end: str) -> list:
    rows = []
    years = range(int(start[:4]), int(end[:4]) + 1)
    per = lambda y: (f"{y}01", f"{y}{end[4:]}") if len(start) > 4 else (str(y), str(y))
    for y in years:                                         # 1) 연도별
        ps, pe = per(y)
        d = _call({**params, "startPrdDe": ps, "endPrdDe": pe})
        e = _err(d)
        if not e and isinstance(d, list):
            rows.extend(d); time.sleep(0.3); continue
        if "초과" not in e and "40000" not in e.replace(",", ""):
            time.sleep(0.3); continue
        for code in _obj1_codes(params):                    # 2) 연도 × 1단계 분류 코드별
            d = _call({**params, "startPrdDe": ps, "endPrdDe": pe, "objL1": code})
            if not _err(d) and isinstance(d, list):
                rows.extend(d)
            time.sleep(0.3)
    return rows


def meta_codes(t: dict, obj_sn: int) -> dict[str, str]:
    """data/kosis/<key>.meta.json(--meta 로 저장)에서 분류 obj_sn 단계의 이름→코드."""
    p = OUT / f"{t['key']}.meta.json"
    if not p.exists():
        return {}
    out: dict[str, str] = {}
    for it in json.loads(p.read_text(encoding="utf-8")):
        if str(it.get("OBJ_ID_SN")) == str(obj_sn) and (it["ITM_NM"] not in out or len(it["ITM_ID"]) < len(out[it["ITM_NM"]])):
            out[it["ITM_NM"]] = it["ITM_ID"]     # 같은 이름이 여러 단계에 있으면 짧은 코드(상위 단계)
    return out


def apply_keep(t: dict, rows: list) -> list:
    """yml 의 keep: {C2_level: [1, 2], C3: ["계"]} — 분류 코드 길이(대분류 1·중분류 2·소분류 3…)와 값으로 행을 거른다. 74만 행짜리 표를 저장소에 맞게 줄일 때."""
    k = t.get("keep") or {}
    if not k:
        return rows
    out = rows
    for col in ("C1", "C2", "C3", "C4"):
        lv = k.get(f"{col}_level")
        if lv:
            codes = meta_codes(t, int(col[1]))
            if codes:
                out = [r for r in out if len(codes.get(r.get(f"{col}_NM", ""), "")) in lv or r.get(f"{col}_NM", "") in (k.get(f"{col}_also") or [])]
        vals = k.get(col)
        if vals:
            out = [r for r in out if r.get(f"{col}_NM", "") in vals]
    return out


def fetch_table(t: dict, key: str, dry: bool) -> dict | None:
    start, end = period_range(t.get("prd_se", "Y"), int(t.get("years", 6)))
    base = {"method": "getList", "apiKey": key, "itmId": "ALL", "format": "json", "jsonVD": "Y", "prdSe": t.get("prd_se", "Y"),
            "orgId": str(t["org_id"]), "tblId": t["tbl_id"]}
    if dry:
        print(f"[dry] {t['key']}: {API_DATA}?" + "&".join(f"{k}={'***' if k == 'apiKey' else v}" for k, v in {**base, "objL1": "ALL", "startPrdDe": start, "endPrdDe": end}.items()))
        return None
    rows = _get_rows(base, start, end)
    area_words = t["area"] if "area" in t and t["area"] is not None else ["대구"]   # area: [] 이면 전 지역 행을 남긴다
    col = t.get("area_col")
    keep = []
    for row in rows:
        names = [row.get(f"{c}_NM", "") for c in ("C1", "C2", "C3", "C4")]
        hay = row.get(f"{col}_NM", "") if col else " ".join(names)
        if not area_words or any(w in hay for w in area_words):
            keep.append(row)
    if not keep and rows:   # 지역 열이 없는 표(전국 표)면 전부 남긴다
        keep = rows
    keep = apply_keep(t, keep)
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
        msg = items.get("errMsg", "") if isinstance(items, dict) else ""
        hint = " — KOSIS 공유서비스(kosis.kr → 공유서비스 → 인증키 발급)의 키인지, 마이페이지 활용신청이 승인됐는지, 시크릿에 공백이 없는지 확인" if "인증" in msg else ""
        print(f"[discover] {t['key']}: {items}{hint}")
        return
    print(f"[discover] {t['key']} ← '{q}'")
    for it in items[:15]:
        print(f"   {it.get('ORG_ID')} {it.get('TBL_ID')} | {it.get('TBL_NM')} | {it.get('STAT_NM', '')} | {it.get('PRD_DE', '')}")


def probe(t: dict, key: str) -> None:
    """표 하나의 메타(수록기간·항목·분류)와 최소 요청 응답을 그대로 찍는다 — 오류 21(잘못된 요청 변수)이 어느 인자 때문인지 볼 때."""
    meta = "https://kosis.kr/openapi/statisticsData.do"
    for typ in ("TBL", "PRD", "ITM", "OBJ", "CMMT"):
        try:
            r = requests.get(meta, params={"method": "getMeta", "apiKey": key, "format": "json", "jsonVD": "Y", "orgId": str(t["org_id"]), "tblId": t["tbl_id"], "type": typ},
                             headers={"User-Agent": UA}, timeout=(20, 60))
            print(f"[meta {typ}] {r.text[:1200]}")
        except Exception as e:  # noqa: BLE001
            print(f"[meta {typ}] 실패 {e}")
    start, end = period_range(t.get("prd_se", "Y"), 1)
    base = {"method": "getList", "apiKey": key, "itmId": "ALL", "format": "json", "jsonVD": "Y", "prdSe": t.get("prd_se", "Y"), "orgId": str(t["org_id"]), "tblId": t["tbl_id"]}
    for n in (1, 2, 3, 4):
        for extra in ({"newEstPrdCnt": "1"}, {"startPrdDe": start, "endPrdDe": end}):
            params = {**base, **extra, **{f"objL{i}": "ALL" for i in range(1, n + 1)}}
            try:
                r = requests.get(API_DATA, params=params, headers={"User-Agent": UA}, timeout=(20, 120))
                body = r.text
                print(f"[try objL1..{n} {extra}] {len(body)}자: {body[:300]}")
            except Exception as e:  # noqa: BLE001
                print(f"[try objL1..{n} {extra}] 실패 {e}")
            time.sleep(0.3)


def save_meta(t: dict, key: str) -> None:
    """표의 항목·분류 메타(getMeta ITM)를 data/kosis/<key>.meta.json 에 저장 — 분류 코드(대·중·소분류 단계)가 필요한 표(전국사업체조사 산업 등)에."""
    r = requests.get("https://kosis.kr/openapi/statisticsData.do", params={"method": "getMeta", "apiKey": key, "format": "json", "jsonVD": "Y", "orgId": str(t["org_id"]), "tblId": t["tbl_id"], "type": "ITM"},
                     headers={"User-Agent": UA}, timeout=(20, 120))
    items = r.json()
    if not isinstance(items, list):
        print(f"[meta] {t['key']}: {items}"); return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{t['key']}.meta.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    print(f"[meta] {t['key']}: 항목·분류 {len(items)}개 → data/kosis/{t['key']}.meta.json")


def walk_list(key: str, words: list[str], parent: str = "", depth: int = 0, max_depth: int = 6, path: str = "") -> None:
    """KOSIS 주제별 통계목록 트리를 내려가며 이름에 낱말이 든 목록·표를 찍는다(--list '전국사업체조사 시도'). 검색 API 는 일부 표를 못 찾는다.
    낱말은 상위 목록 이름과 표 이름을 합친 글자에서 찾는다(조사 이름은 목록에, '시도'는 표 이름에 있는 식). 여러 검색은 ';' 로 나눈다."""
    try:
        r = requests.get(API_LIST, params={"method": "getList", "apiKey": key, "vwCd": "MT_ZTITLE", "parentListId": parent, "format": "json", "jsonVD": "Y"},
                         headers={"User-Agent": UA}, timeout=(20, 60))
        items = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[list] {parent}: 실패 {e}"); return
    if not isinstance(items, list):
        print(f"[list] {parent}: {items}"); return
    for it in items:
        name = it.get("LIST_NM") or it.get("TBL_NM") or ""
        tbl = it.get("TBL_ID")
        if tbl:
            if all(w in path + " " + name for w in words):
                print(f"   {it.get('ORG_ID')} {tbl} | {path.strip(' >')} > {name} | {it.get('PRD_DE', '')}~")
            continue
        lid = it.get("LIST_ID")
        # 목록 이름(상위 포함)에 첫 낱말이 들어 있으면 그 아래를 끝까지, 아니면 얕게만 내려간다
        if any(w in path + " " + name for w in words[:1]) or depth < 2:
            if depth >= max_depth:
                continue
            walk_list(key, words, lid, depth + 1, max_depth, path + " > " + name)
            time.sleep(0.2)


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
    ap.add_argument("--list", default="", help="통계목록 트리에서 낱말이 든 표를 찾는다(예: '전국사업체조사 시도')")
    ap.add_argument("--probe", default="", help="표 key 하나의 메타·최소 요청 응답을 찍는다(오류 21 원인 확인)")
    ap.add_argument("--meta", default="", help="표 key 의 항목·분류 메타를 data/kosis/<key>.meta.json 으로 저장(분류 코드가 필요할 때)")
    a = ap.parse_args()
    tables = load()
    if a.only:
        want = set(a.only.split(","))
        tables = [t for t in tables if t["key"] in want]
    if a.summary:
        write_summary([]); return 0
    key = os.environ.get("KOSIS_KEY", "").strip().strip('"\'')   # 시크릿에 공백·따옴표가 딸려 와도 그대로 쓰지 않게
    if not key and not a.dry_run:
        print("KOSIS_KEY 가 없어 받지 않음(GitHub Secrets 에 넣으면 동작)"); return 0
    if a.list:
        for phrase in a.list.split(";"):
            if phrase.strip():
                print(f"[list] '{phrase.strip()}'")
                walk_list(key, phrase.split())
        return 0
    if a.meta:
        for t in load():
            if t["key"] in a.meta.split(","):
                save_meta(t, key)
        return 0
    if a.probe:
        for t in load():
            if t["key"] == a.probe:
                probe(t, key)
        return 0
    metas = []
    for t in tables:
        if not t.get("tbl_id"):
            discover(t, key); time.sleep(0.5)   # tbl_id 가 비면 받기 실행에서도 후보를 찍어 준다
            continue
        try:
            m = fetch_table(t, key, a.dry_run)
            if m:
                metas.append(m)
        except NetworkDead as e:
            print(f"{t['key']}: {e} — 이 러너에서는 더 시도하지 않음(남은 표는 다음 시도에서)")
            write_summary(metas)
            return 75
        except Exception as e:  # noqa: BLE001
            print(f"{t['key']}: 실패 — {e}")
        time.sleep(0.5)
    write_summary(metas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
