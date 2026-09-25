#!/usr/bin/env python3
"""월간 통계 집계 — 기업 DB(팩토리온) + 국민연금 사업장 파일(있으면) → data/stats/

사용:
  python3 scripts/build_stats.py                 # 최신 달(국민연금 파일이 있으면 그 최신 달, 없으면 팩토리온 기준월)
  python3 scripts/build_stats.py --month 202609  # 특정 달
  python3 scripts/build_stats.py --backfill      # data/nps/*.csv 전부 + 팩토리온 기준월을 오래된 달부터 차례로

입력
  scripts/data/dalseong_companies.csv   팩토리온 기업 DB (id, complex, district, sector_code, workers, as_of …)
  scripts/data/extra_companies.csv      산단 외 기업(알파시티·특구·창경센터·지식산업센터·창업기업, import_extra.py) + company_tags.csv
  scripts/data/support_history.csv      지원사업 수혜 이력(import_support.py) → 축별 support_3y(기업 수·건수·합산 금액)
  data/nps/YYYYMM.csv                   국민연금 사업장 가입현황 대구분 (선택). 열 이름은 NPS_COLS 의 후보 가운데 하나면 된다
  config/industry_groups.yml            산업 그룹 규칙 (scripts/industry.py 가 읽음)
  scripts/state/dart_corp.json          DART 대구 기업 캐시 (공시 기업 수 계산용, 매출은 자료 없음 → null)
  src/content/posts/*.md                진행 중 공모 공고 수 (deadline ≥ 집계 시점, draft 아님)

출력
  data/stats/monthly/YYYYMM.json        그 달 집계: 전체 / 산업 / 산단 / 구·군 × 지표, 산업×산단 교차표, 집계 대상 비율
  data/stats/monthly/YYYYMM_industry.csv 산업별 고용 표 (별도 산출물: 기업 수·집계 대상·고용·평균·규모 구간·증감)
  data/stats/industry_timeseries.csv    월 × 산업 고용·기업 수
  data/stats/monthly/YYYYMM.ids.csv     그 달 기업 id → [산업, 단지, 구군] (다음 달 신규·소멸 계산용)
  data/stats/timeseries.json            월별 시계열 (모든 달 보관, 최소 24개월)
  data/stats/companies.json             기업별: 산업 그룹, 고용 인원, 최근 12개월 고용 (국민연금 매칭 기업만 시계열)

원칙
  - 고용 인원의 근거(basis)는 달마다 기록한다: "nps" = 국민연금 가입자수 합계, "factoryon" = 공장등록 신고값(국민연금 파일이 없는 달)
  - 국민연금에 매칭되지 않은 기업은 고용 집계에서 빠지므로 모든 집계에 covered(집계 대상 기업 수)/firms(전체 기업 수)를 같이 둔다
  - 자료가 없는 지표는 0 이 아니라 null 로 둔다 (원문에 없는 수치를 만들지 않는다)
  - 평가·순위 표현 없음. 숫자만.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from industry import classify, config as industry_config  # noqa: E402
from sites import load_all_companies, site_types, tag_name  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "scripts" / "data" / "dalseong_companies.csv"
NPS_DIR = ROOT / "data" / "nps"
DART = ROOT / "scripts" / "state" / "dart_corp.json"
POSTS = ROOT / "src" / "content" / "posts"
OUT = ROOT / "data" / "stats"
MONTHLY = OUT / "monthly"
MIN_MONTHS = 24

SIZE_BANDS = [("1~9", 1, 9), ("10~49", 10, 49), ("50~299", 50, 299), ("300+", 300, 10**9)]

# 국민연금 파일 열 이름 후보 (공공데이터포털 '국민연금 가입 사업장 내역' 기준, 다른 출처면 여기만 고친다)
NPS_COLS = {
    "name": ["사업장명", "사업장명칭", "회사명"],
    "address": ["사업장도로명상세주소", "사업장지번상세주소", "사업장주소", "고객법정동주소", "주소"],
    "employment": ["가입자수", "국민연금가입자수", "가입자 수"],
    "gain": ["신규취득자수", "당월취득자수", "취득자수"],
    "loss": ["상실가입자수", "당월상실자수", "상실자수"],
    "status": ["사업장가입상태코드", "가입상태"],
    "reg_date": ["적용일자", "사업장등록일", "등록일"],
    "withdraw_date": ["탈퇴일자", "사업장탈퇴일"],
}

# ---------------------------------------------------------------- 입력
def load_companies() -> list[dict]:
    """팩토리온 기업 전부 + 산단 외 기업 목록(extra_companies.csv). 전수 원칙: 어느 기업도 빼지 않는다.
    개인 성명으로 보이는 공장명을 감추는 규칙은 목록·페이지 표시(src/lib/csv.ts)에만 둔다."""
    rows = load_all_companies()
    for r in rows:
        r["group"] = classify(r["sector_code"], r["sector"], r["product"])
        w = (r.get("workers") or "").strip()
        r["fo_workers"] = int(w) if w.isdigit() else None
        r["complex"] = r.get("complex") or "개별입지"
    return rows


def norm_name(s: str) -> str:
    s = re.sub(r"\(주\)|㈜|\(유\)|주식회사|유한회사|유한책임회사|합자회사|합명회사|농업회사법인|영농조합법인|\(사\)|사단법인|재단법인", "", s or "")
    s = re.sub(r"[\s\-_.,·ㆍ&/()\[\]'\"]", "", s)
    return s.lower()


_DIST = re.compile(r"대구광역시\s*(\S+?[구군])\b|대구\s*(\S+?[구군])\b")


def district_of(addr: str) -> str:
    m = _DIST.search(addr or "")
    return (m.group(1) or m.group(2)) if m else ""


def pick(row: dict, key: str) -> str:
    for c in NPS_COLS[key]:
        if c in row and row[c] is not None:
            return str(row[c]).strip()
    for c in NPS_COLS[key]:  # '사업장가입상태코드 1 등록 2 탈퇴'처럼 설명이 붙은 열 이름
        for k, v in row.items():
            if k and k.replace(" ", "").startswith(c) and v is not None:
                return str(v).strip()
    return ""


def to_int(s: str) -> int | None:
    s = re.sub(r"[,\s명]", "", s or "")
    return int(s) if s.lstrip("-").isdigit() else None


def load_nps(month: str) -> list[dict] | None:
    """data/nps/YYYYMM.csv → [{name, norm, district, employment, gain, loss, status, reg_date, withdraw_date}]"""
    p = NPS_DIR / f"{month}.csv"
    if not p.exists():
        return None
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("cp949", errors="replace")
    rows = list(csv.DictReader(text.splitlines()))
    out = []
    for r in rows:
        name = pick(r, "name")
        if not name:
            continue
        out.append({
            "name": name, "norm": norm_name(name), "district": district_of(pick(r, "address")),
            "employment": to_int(pick(r, "employment")), "gain": to_int(pick(r, "gain")), "loss": to_int(pick(r, "loss")),
            "status": pick(r, "status"), "reg_date": pick(r, "reg_date"), "withdraw_date": pick(r, "withdraw_date"),
        })
    return out


def match_nps(companies: list[dict], nps: list[dict]) -> dict[str, dict]:
    """기업 id → {employment, gain, loss, new, closed}. 정규화 회사명 + 구·군 (구·군이 없으면 이름만, 유일할 때)."""
    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_name: dict[str, list[dict]] = defaultdict(list)
    for r in nps:
        by_key[(r["norm"], r["district"])].append(r)
        by_name[r["norm"]].append(r)
    matched: dict[str, dict] = {}
    for c in companies:
        n = norm_name(c["name"])
        rows = by_key.get((n, c["district"])) or ([] if len(by_name.get(n, [])) != 1 else by_name[n])
        if not rows:
            continue
        emp = sum(r["employment"] or 0 for r in rows)
        matched[c["id"]] = {
            "employment": emp,
            "gain": sum(r["gain"] or 0 for r in rows) if any(r["gain"] is not None for r in rows) else None,
            "loss": sum(r["loss"] or 0 for r in rows) if any(r["loss"] is not None for r in rows) else None,
            "reg_dates": [r["reg_date"] for r in rows if r["reg_date"]],
            "withdraw_dates": [r["withdraw_date"] for r in rows if r["withdraw_date"]],
        }
    return matched


SUPPORT = ROOT / "scripts" / "data" / "support_history.csv"
UNIT_WON = {"원": 1, "천원": 1_000, "백만원": 1_000_000, "억원": 100_000_000}


def load_support(years: int = 3) -> dict[str, list[dict]]:
    """기업 id → 최근 n년 지원 이력. 금액은 단위를 원으로 통일해 합산할 수 있게 amount_won 을 붙인다(단위 모르면 None)."""
    out: dict[str, list[dict]] = {}
    if not SUPPORT.exists():
        return out
    y0 = date.today().year - years + 1
    for r in csv.DictReader(open(SUPPORT, encoding="utf-8")):
        if not r.get("id") or not (r.get("year") or "").isdigit() or int(r["year"]) < y0:
            continue
        won = None
        if r.get("amount"):
            try:
                won = float(r["amount"]) * UNIT_WON.get((r.get("amount_unit") or "원").replace(" ", ""), 0) or None
            except ValueError:
                won = None
        r["amount_won"] = won
        out.setdefault(r["id"], []).append(r)
    return out


_support_cache: dict[str, list[dict]] | None = None


def support_metrics(cs: list[dict]) -> dict:
    """지원사업 수혜(최근 3년): 기업 수·이력 건수·합산 금액(원, 단위가 있는 건만)·국비/시비 건수."""
    global _support_cache
    if _support_cache is None:
        _support_cache = load_support()
    recs = [r for c in cs for r in _support_cache.get(c["id"], [])]
    firms = {r["id"] for r in recs}
    known = [r["amount_won"] for r in recs if r["amount_won"]]
    layers = Counter((r.get("layer") or "미상") for r in recs)
    return {"firms": len(firms), "records": len(recs), "amount_won": int(sum(known)) if known else None, "amount_known_records": len(known),
            "by_layer": dict(layers)} if recs else {"firms": 0, "records": 0, "amount_won": None, "amount_known_records": 0, "by_layer": {}}


def load_dart_names() -> set[str]:
    if not DART.exists():
        return set()
    d = json.loads(DART.read_text(encoding="utf-8"))
    return {norm_name(v["name"]) for v in d.values() if v.get("daegu")}


def count_open_programs(as_of: date) -> int:
    n = 0
    for p in POSTS.glob("*.md"):
        head = p.read_text(encoding="utf-8").split("---", 2)
        if len(head) < 3:
            continue
        fm = head[1]
        if re.search(r"^draft:\s*true", fm, re.M):
            continue
        m = re.search(r"^deadline:\s*['\"]?(\d{4}-\d{2}-\d{2})", fm, re.M)
        if m and date.fromisoformat(m.group(1)) >= as_of:
            n += 1
    return n


# ---------------------------------------------------------------- 집계
def in_month(d: str, month: str) -> bool:
    return re.sub(r"\D", "", d or "")[:6] == month


def metrics(cs: list[dict], nps: dict[str, dict] | None, prev: dict[str, list] | None, month: str, dart: set[str],
            axis: int | None = None, value: str | None = None) -> dict:
    """한 집합의 지표. prev 는 전월 id → [산업, 단지, 구군]; axis/value 는 이 집합이 어느 축의 어느 값인지 (소멸 기업 계산용)."""
    firms = len(cs)
    if nps is not None:
        emp_rows = [(c, nps[c["id"]]["employment"]) for c in cs if c["id"] in nps]
    else:
        emp_rows = [(c, c["fo_workers"]) for c in cs if c["fo_workers"] is not None]
    covered = len(emp_rows)
    employment = sum(e for _, e in emp_rows)
    bands = {b: 0 for b, _, _ in SIZE_BANDS}
    for _, e in emp_rows:
        for b, lo, hi in SIZE_BANDS:
            if lo <= e <= hi:
                bands[b] += 1
                break
    gain = loss = None
    new_firms = closed_firms = None
    if nps is not None:
        gs = [nps[c["id"]]["gain"] for c in cs if c["id"] in nps and nps[c["id"]]["gain"] is not None]
        ls = [nps[c["id"]]["loss"] for c in cs if c["id"] in nps and nps[c["id"]]["loss"] is not None]
        gain, loss = (sum(gs) if gs else None), (sum(ls) if ls else None)
        new_firms = sum(1 for c in cs if c["id"] in nps and any(in_month(d, month) for d in nps[c["id"]]["reg_dates"]))
        closed_firms = sum(1 for c in cs if c["id"] in nps and any(in_month(d, month) for d in nps[c["id"]]["withdraw_dates"]))
    if prev is not None:  # 전월 id 목록이 있으면 그것이 우선 (팩토리온 등록·소멸 기준)
        ids = {c["id"] for c in cs}
        new_firms = len(ids - prev.keys())
        prev_here = {i for i, v in prev.items() if axis is None or v[axis] == value}
        closed_firms = len(prev_here - ids)
    return {
        "firms": firms,
        "employment": employment,
        "covered": covered,
        "avg_employment": round(employment / covered, 1) if covered else None,
        "size_bands": bands,
        "nps_gain": gain,
        "nps_loss": loss,
        "new_firms": new_firms,
        "closed_firms": closed_firms,
        "dart_firms": sum(1 for c in cs if norm_name(c["name"]) in dart) if dart else None,
        "dart_revenue": None,      # 개별 기업 재무는 company_financials.csv(collect_dart_fin.py); 축 합산은 하지 않는다
        "projects_12m": None,      # (구) 과제 선정 → support_3y 로 대체
        "support_3y": support_metrics(cs),  # 지원사업 수혜 최근 3년 (support_history.csv)
        "mom": None, "yoy": None,  # 아래 attach_deltas 가 채움
    }


def delta(cur: dict, prev: dict | None) -> dict | None:
    if not prev:
        return None
    out = {}
    for k in ("firms", "employment"):
        a, b = cur.get(k), prev.get(k)
        if a is None or b is None:
            out[k] = None
        else:
            out[k] = {"diff": a - b, "pct": round((a - b) / b * 100, 1) if b else None}
    return out


def shift_month(month: str, n: int) -> str:
    y, m = int(month[:4]), int(month[4:])
    m -= n
    while m <= 0:
        m += 12
        y -= 1
    return f"{y}{m:02d}"


def save_ids(month: str, companies: list[dict]) -> None:
    """그 달 기업 id → [산업, 단지, 구군]. 24개월 보관해도 작도록 값은 색인 번호로 적는다."""
    vals = [sorted({c["group"] for c in companies}), sorted({c["complex"] or "개별입지" for c in companies}), sorted({c["district"] or "기타" for c in companies})]
    idx = [{v: i for i, v in enumerate(vs)} for vs in vals]
    with open(MONTHLY / f"{month}.ids.csv", "w", encoding="utf-8", newline="") as f:
        f.write("# " + json.dumps(vals, ensure_ascii=False) + "\n")
        w = csv.writer(f)
        for c in companies:
            w.writerow([c["id"], idx[0][c["group"]], idx[1][c["complex"] or "개별입지"], idx[2][c["district"] or "기타"]])


def load_ids(month: str) -> dict[str, list] | None:
    p = MONTHLY / f"{month}.ids.csv"
    if not p.exists():
        return None
    lines = p.read_text(encoding="utf-8").splitlines()
    vals = json.loads(lines[0][2:])
    return {r[0]: [vals[0][int(r[1])], vals[1][int(r[2])], vals[2][int(r[3])]] for r in csv.reader(lines[1:]) if r}


def load_month(month: str) -> dict | None:
    p = MONTHLY / f"{month}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def attach_deltas(doc: dict, month: str) -> None:
    prev, prev_y = load_month(shift_month(month, 1)), load_month(shift_month(month, 12))
    for axis in ("total", "by_industry", "by_complex", "by_district", "by_site", "by_tag"):
        if axis == "total":
            doc["total"]["mom"] = delta(doc["total"], prev["total"] if prev else None)
            doc["total"]["yoy"] = delta(doc["total"], prev_y["total"] if prev_y else None)
            continue
        for k, m in doc[axis].items():
            m["mom"] = delta(m, (prev or {}).get(axis, {}).get(k))
            m["yoy"] = delta(m, (prev_y or {}).get(axis, {}).get(k))
    doc.setdefault("by_site", {}); doc.setdefault("by_tag", {})


def build_month(month: str, companies: list[dict], dart: set[str], as_of: date) -> dict:
    nps_rows = load_nps(month)
    nps = match_nps(companies, nps_rows) if nps_rows is not None else None
    prev = load_ids(shift_month(month, 1))

    group_names = [g["name"] for g in industry_config()["groups"]] + [industry_config()["unclassified"]]
    by_ind = {g: [c for c in companies if c["group"] == g] for g in group_names}
    by_ind = {g: cs for g, cs in by_ind.items() if cs}
    by_cx: dict[str, list] = defaultdict(list)
    by_di: dict[str, list] = defaultdict(list)
    by_site: dict[str, list] = defaultdict(list)
    by_tag: dict[str, list] = defaultdict(list)
    for c in companies:
        by_cx[c["complex"] or "개별입지"].append(c)
        by_di[c["district"] or "기타"].append(c)
        by_site[c["site_type"]].append(c)
        for t in c["tags"]:
            by_tag[tag_name(t)].append(c)
    site_order = [t["name"] for t in site_types()]

    doc = {
        "month": f"{month[:4]}-{month[4:]}",
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "basis": "nps" if nps is not None else "factoryon",
        "basis_label": "국민연금 가입자수" if nps is not None else "공장등록 신고값(팩토리온)",
        "sources": {
            "factoryon": {"as_of": companies[0]["as_of"] if companies else "", "companies": len(companies)},
            "nps": {"file": f"data/nps/{month}.csv", "rows": len(nps_rows), "matched": len(nps)} if nps_rows is not None else None,
            "dart": {"corps_daegu": len(dart), "note": "collect_dart.py 가 확인한 대구 본사 공시 기업만. 재무(매출)는 미연결"},
        },
        "total": metrics(companies, nps, prev, month, dart),
        "by_industry": {g: metrics(cs, nps, prev, month, dart, 0, g) for g, cs in by_ind.items()},
        "by_complex": {k: metrics(cs, nps, prev, month, dart, 1, k) for k, cs in sorted(by_cx.items(), key=lambda kv: -len(kv[1]))},
        "by_district": {k: metrics(cs, nps, prev, month, dart, 2, k) for k, cs in sorted(by_di.items(), key=lambda kv: -len(kv[1]))},
        "by_site": {k: metrics(by_site[k], nps, None, month, dart) for k in site_order if by_site.get(k)},
        "by_tag": {k: metrics(cs, nps, None, month, dart) for k, cs in sorted(by_tag.items(), key=lambda kv: -len(kv[1]))},
        "sources_extra": {"outside_companies": sum(1 for c in companies if c["id"].startswith("x")),
                          "note": "산단 외 기업 목록(scripts/data/extra_companies.csv). 없으면 0"},
        "cross": {},
        "cross_site": {},
        "open_programs": count_open_programs(as_of),
    }
    # 산업 × 산단 교차표 (기업 수, 고용, 집계 대상)
    for g, cs in by_ind.items():
        row: dict[str, dict] = defaultdict(lambda: {"firms": 0, "employment": 0, "covered": 0})
        for c in cs:
            cx = c["complex"] or "개별입지"
            e = nps[c["id"]]["employment"] if nps is not None and c["id"] in nps else (None if nps is not None else c["fo_workers"])
            row[cx]["firms"] += 1
            if e is not None:
                row[cx]["employment"] += e
                row[cx]["covered"] += 1
        doc["cross"][g] = dict(sorted(row.items(), key=lambda kv: -kv[1]["employment"]))
    # 산업 × 입지 유형 교차표 (산단 외 기업이 어느 산업인지)
    for g, cs in by_ind.items():
        row2: dict[str, dict] = defaultdict(lambda: {"firms": 0, "employment": 0, "covered": 0})
        for c in cs:
            e = nps[c["id"]]["employment"] if nps is not None and c["id"] in nps else (None if nps is not None else c["fo_workers"])
            row2[c["site_type"]]["firms"] += 1
            if e is not None:
                row2[c["site_type"]]["employment"] += e
                row2[c["site_type"]]["covered"] += 1
        doc["cross_site"][g] = {k: row2[k] for k in site_order if k in row2}
    attach_deltas(doc, month)

    MONTHLY.mkdir(parents=True, exist_ok=True)
    (MONTHLY / f"{month}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    save_ids(month, companies)
    write_industry_table(doc, month)
    return doc


def write_industry_table(doc: dict, month: str) -> Path:
    """산업별 고용 표를 별도 CSV 로 (data/stats/monthly/YYYYMM_industry.csv). 화면·월보·엑셀 공용."""
    out = MONTHLY / f"{month}_industry.csv"
    cols = ["산업", "기업 수", "집계 대상 기업 수", "고용 인원", "평균 고용", "1~9인", "10~49인", "50~299인", "300인 이상",
            "전월 대비 고용", "전월 대비 %", "전년 동월 대비 고용", "전년 동월 대비 %", "신규 등록 기업", "폐업·탈퇴 기업", "신규취득", "상실"]
    d = lambda m, k, f: (m.get(k) or {}).get("employment", {}) or {}  # noqa: E731
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        rows = list(doc["by_industry"].items()) + [("전체", doc["total"])]
        for name, m in rows:
            mom, yoy = d(m, "mom", 0), d(m, "yoy", 0)
            b = m["size_bands"]
            w.writerow([name, m["firms"], m["covered"], m["employment"], m["avg_employment"], b["1~9"], b["10~49"], b["50~299"], b["300+"],
                        mom.get("diff"), mom.get("pct"), yoy.get("diff"), yoy.get("pct"), m["new_firms"], m["closed_firms"], m["nps_gain"], m["nps_loss"]])
        w.writerow([])
        w.writerow([f"기준 {doc['month']} · 고용 인원 = {doc['basis_label']} · 집계 대상 = 고용 값이 있는 기업 · 빈칸 = 자료 없음"])
    return out


def write_industry_timeseries(ts: dict) -> Path:
    """월 × 산업 고용·기업 수 (data/stats/industry_timeseries.csv)."""
    out = OUT / "industry_timeseries.csv"
    names = list(ts["by_industry"].keys())
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["월", "고용 근거", "전체 고용", "전체 기업 수"] + [f"{n} 고용" for n in names] + [f"{n} 기업 수" for n in names])
        for i, m in enumerate(ts["months"]):
            w.writerow([m, ts["basis"][i], ts["total"]["employment"][i], ts["total"]["firms"][i]]
                       + [ts["by_industry"][n]["employment"][i] for n in names] + [ts["by_industry"][n]["firms"][i] for n in names])
    return out


def rebuild_timeseries(companies: list[dict]) -> dict:
    months = sorted(p.stem for p in MONTHLY.glob("??????.json"))
    docs = {m: load_month(m) for m in months}
    ts = {"months": [f"{m[:4]}-{m[4:]}" for m in months], "basis": [docs[m]["basis"] for m in months],
          "total": {"employment": [], "firms": [], "covered": []}, "by_industry": {}, "by_complex": {}, "by_district": {}, "by_site": {}}
    for m in months:
        d = docs[m]
        for k in ("employment", "firms", "covered"):
            ts["total"][k].append(d["total"][k])
        for axis in ("by_industry", "by_complex", "by_district", "by_site"):
            for name in d.get(axis, {}):
                ts[axis].setdefault(name, {"employment": [], "firms": [], "covered": []})
    for axis in ("by_industry", "by_complex", "by_district", "by_site"):
        for name, series in ts[axis].items():
            for m in months:
                v = docs[m].get(axis, {}).get(name)
                for k in ("employment", "firms", "covered"):
                    series[k].append(v[k] if v else None)
    ts["note"] = f"월 {len(months)}개 보관 (최소 {MIN_MONTHS}개월). basis: nps=국민연금 가입자수, factoryon=공장등록 신고값"
    (OUT / "timeseries.json").write_text(json.dumps(ts, ensure_ascii=False), encoding="utf-8")
    return ts


def rebuild_companies_json(companies: list[dict]) -> None:
    months = sorted(p.stem for p in MONTHLY.glob("??????.json"))[-12:]
    # 기업별 12개월 고용은 국민연금이 있는 달만. 매칭 결과는 각 달 문서에 싣지 않으므로 다시 계산한다
    series: dict[str, list] = defaultdict(list)
    any_nps = False
    for m in months:
        rows = load_nps(m)
        matched = match_nps(companies, rows) if rows is not None else {}
        any_nps = any_nps or rows is not None
        for c in companies:
            series[c["id"]].append(matched.get(c["id"], {}).get("employment"))
    out = {"months": [f"{m[:4]}-{m[4:]}" for m in months], "basis_note": "g 산업 그룹, t 입지 유형, k 태그, e 최신 달 고용 인원(국민연금 매칭 시 가입자수, 아니면 공장등록 신고값), s 최근 12개월 국민연금 가입자수(매칭 기업만)", "companies": {}}
    for c in companies:
        s = series[c["id"]]
        latest = next((v for v in reversed(s) if v is not None), None)
        entry = {"g": c["group"], "t": c["site_type"], "e": latest if latest is not None else c["fo_workers"], "b": "nps" if latest is not None else "factoryon"}
        if c["tags"]:
            entry["k"] = sorted(c["tags"])
        if any_nps and any(v is not None for v in s):
            entry["s"] = s
        out["companies"][c["id"]] = entry
    (OUT / "companies.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", help="YYYYMM")
    ap.add_argument("--backfill", action="store_true", help="data/nps/*.csv 전부를 오래된 달부터")
    a = ap.parse_args(argv)

    companies = load_companies()
    if not companies:
        print("기업 DB 없음", file=sys.stderr)
        return 1
    dart = load_dart_names()
    fo_month = companies[0]["as_of"].replace("-", "")[:6]
    nps_months = sorted(p.stem for p in NPS_DIR.glob("??????.csv")) if NPS_DIR.is_dir() else []

    # 국민연금 파일이 하나라도 있으면 그 달들만 집계한다(근거가 다른 달을 한 시계열에 섞지 않기 위해). 없으면 팩토리온 기준월 하나
    if a.backfill:
        months = nps_months or [fo_month]
    elif a.month:
        months = [a.month]
    else:
        months = [nps_months[-1] if nps_months else fo_month]

    for m in months:
        doc = build_month(m, companies, dart, as_of=date.today())
        t = doc["total"]
        src = doc["sources"]["nps"]
        print(f"[{doc['month']}] 기업 {t['firms']:,} · 고용 {t['employment']:,}명 ({doc['basis_label']}, 집계 대상 {t['covered']:,}/{t['firms']:,})"
              + (f" · 국민연금 {src['rows']:,}행 중 매칭 {src['matched']:,}곳" if src else " · 국민연금 파일 없음")
              + f" · 진행 중 공고 {doc['open_programs']}건")
        print(f"   {'산업':<10}{'기업 수':>8}{'집계 대상':>8}{'고용 인원':>10}{'평균':>7}{'전월 대비':>10}")
        for g, mtr in list(doc["by_industry"].items()) + [("전체", t)]:
            mom = (mtr.get("mom") or {}).get("employment")
            mom_s = f"{mom['diff']:+,}" if mom and mom.get("diff") is not None else "—"
            print(f"   {g:<10}{mtr['firms']:>8,}{mtr['covered']:>8,}{mtr['employment']:>10,}{(mtr['avg_employment'] or 0):>7.1f}{mom_s:>10}")
        print(f"   → data/stats/monthly/{m}_industry.csv")
        print("   입지 유형: " + " · ".join(f"{k} {v['firms']:,}곳/{v['employment']:,}명" for k, v in doc["by_site"].items()))
        if doc["by_tag"]:
            print("   태그: " + " · ".join(f"{k} {v['firms']:,}곳" for k, v in doc["by_tag"].items()))
    ts = rebuild_timeseries(companies)
    write_industry_timeseries(ts)
    rebuild_companies_json(companies)
    print(f"시계열 {len(ts['months'])}개월 → data/stats/timeseries.json, industry_timeseries.csv, companies.json")
    if len(ts["months"]) < MIN_MONTHS:
        print(f"(과거 국민연금 월별 파일을 data/nps/ 에 넣고 --backfill 하면 {MIN_MONTHS}개월까지 소급됩니다)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
