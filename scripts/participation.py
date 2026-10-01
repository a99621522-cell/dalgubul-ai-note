#!/usr/bin/env python3
"""참여 사업별 기업 분류 — config/participation.yml 의 명단(모터 소부장 앵커·규제자유특구·글로벌혁신특구·첨복 입주·
규제샌드박스·연구소기업·스타기업 등) → data/participation/members.csv·summary.json + 기업 사전 태그(company_tags.csv, 태그 = 사업 key).

운영자 지시 2026-10-01: 특구를 단지·입지로 근사하던 방식(구역별) 대신 공개 명단에 이름이 실린 기업으로 나눈다.
기업 사전과는 회사 이름(법인 표기·'○○공장' 제거)으로 잇는다. 같은 이름의 공장 기록이 여럿이면 종사자가 가장 큰 기록 하나에만 태그한다(통계의 기업 수가 부풀지 않게).
동명 다른 회사가 섞일 수 있어 페이지에 적는다. 대표자·주소 번지는 저장하지 않는다(주소는 대구/역외와 구·군만).
사용: python3 scripts/participation.py   (fetch_public.yml 이 명단을 받은 뒤 실행)
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from sites import load_all_companies, TAGS  # noqa: E402

CFG = ROOT / "config" / "participation.yml"
RAW = ROOT / "data" / "participation" / "raw"
OUT = ROOT / "data" / "participation"
HIST = ROOT / "scripts" / "data" / "support_history.csv"
TAG_SOURCE = "참여 명단"   # company_tags.csv 의 출처 접두어(재실행 때 이 출처의 태그만 지우고 다시 쓴다)
_DIST = re.compile(r"대구(?:광역시)?\s*(\S+?[구군])(?:\s|$)")
_SIDO = re.compile(r"^\s*(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충청?북|충청?남|충북|충남|전라?북|전북|전라?남|전남|경상?북|경북|경상?남|경남|제주)")


def norm(s: str) -> str:
    s = re.sub(r"\(주\)|㈜|\(유\)|\(재\)|\(사\)|주식회사|유한회사|유한책임회사|합자회사|농업회사법인|사단법인|재단법인", "", s or "")
    s = re.sub(r"[\s\-_.,·ㆍ&/()\[\]'\"]", "", s).lower()
    return re.sub(r"(대구|구지|논공|성서|달성|현풍|유가)?(제?\d+)?(공장|사업장|지점|지사)$", "", s)


def index_companies() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """정규화 이름 → 공장 기록들, id → 기록."""
    by: dict[str, list[dict]] = {}
    ids: dict[str, dict] = {}
    for c in load_all_companies():
        ids[c["id"]] = c
        k = norm(c["name"])
        if len(k) >= 2:
            by.setdefault(k, []).append(c)
    return by, ids


def workers(c: dict) -> int:
    try:
        return int(re.sub(r"\D", "", str(c.get("workers") or "")) or 0)
    except ValueError:
        return 0


def region_of(addr: str) -> tuple[str, str]:
    if not addr:
        return "", ""
    m = _DIST.search(addr)
    if "대구" in addr[:6]:
        return "대구", (m.group(1) if m else "")
    m2 = _SIDO.match(addr)
    return ("역외", m2.group(1) if m2 else "")


def rows_portal(p: dict) -> list[dict]:
    f = RAW / f"{p['dataset']}.csv"
    if not f.exists():
        print(f"[part] {p['key']}: 원본 없음 {f.relative_to(ROOT)} — 건너뜀")
        return []
    out = []
    for r in csv.DictReader(open(f, encoding="utf-8")):
        if any(w not in (r.get(col) or "") for col, w in (p.get("where") or {}).items()):
            continue
        name = (r.get(p["name_col"]) or "").strip()
        if not name:
            continue
        org = any((r.get(col) or "").strip() in vals for col, vals in (p.get("org_when") or {}).items())
        reg, dist = region_of(r.get(p["region"], "")) if p.get("region") else ("", "")
        out.append({"name": name, "sub": (r.get(p.get("sub", ""), "") or "").strip(), "org": org, "region": reg, "district": dist,
                    "as_of": p.get("as_of") or r.get("_as_of", "")})
    return out


def rows_history(p: dict) -> list[dict]:
    if not HIST.exists():
        return []
    out = []
    for r in csv.DictReader(open(HIST, encoding="utf-8")):
        if p["match"] not in (r.get("source", "") + " " + r.get("source_url", "")):
            continue
        if p.get("program") and r.get("program", "").strip() != p["program"]:
            continue
        out.append({"name": r["name"].strip(), "sub": r.get("year", ""),
                    "org": False, "region": "대구", "district": r.get("district", ""), "as_of": r.get("as_of", ""), "id": r.get("id", "")})
    return out


def ym(s: str) -> str:
    """기준일 표기 맞춤: 20250531 → 2025-05, 2025-09 → 그대로."""
    m = re.fullmatch(r"(20\d{2})-?(\d{2})(?:-?\d{2})?", (s or "").strip())
    return f"{m.group(1)}-{m.group(2)}" if m else (s or "").strip()


def main() -> int:
    cfg = yaml.safe_load(open(CFG, encoding="utf-8"))
    by, ids = index_companies()
    members, summary, tags = [], [], {}
    for p in cfg["programs"]:
        src = p["from"]
        if src == "static":
            # 이름만, 또는 {name, district}: 같은 이름의 다른 회사를 피하려고 구·군을 적은 경우 그 구·군 공장만 잇는다
            rows = [{"name": n["name"] if isinstance(n, dict) else n, "sub": "", "org": False, "region": "", "district": "",
                     "only_district": n.get("district", "") if isinstance(n, dict) else "", "as_of": p.get("as_of", "")} for n in p["members"]]
        elif src == "portal":
            rows = rows_portal(p)
        elif src == "history":
            rows = rows_history(p)
        else:
            rows = []
        seen = set()
        for r in rows:
            k = norm(r["name"])
            if (k, r["sub"]) in seen:
                continue
            seen.add((k, r["sub"]))
            cs = [] if r["org"] else by.get(k, [])
            if r.get("id") and not cs and r["id"] in ids:   # 지원 이력에서 이미 이어진 id
                cs = [ids[r["id"]]]
            if r.get("only_district"):
                cs = [c for c in cs if c.get("district") == r["only_district"]]
            if p.get("daegu_only_by_name") and not cs:
                continue
            cs = sorted(cs, key=workers, reverse=True)
            region = r["region"] or ("대구" if cs else "")
            district = r["district"] or (cs[0].get("district", "") if cs else "")
            members.append({"program": p["key"], "name": r["name"], "kind": "기관" if r["org"] else "기업", "sub": r["sub"],
                            "region": region, "district": district, "id": cs[0]["id"] if cs else "",
                            "ids": ";".join(c["id"] for c in cs), "as_of": ym(r["as_of"])})
            # 태그는 대표 기록 하나(종사자가 가장 큰 공장)에만 — 지원 이력과 같은 규칙. 공장마다 붙이면 통계의 기업 수가 부푼다.
            # 이름만 같은 후보(전국 명단)와 다른 스크립트가 태그를 맡는 사업(tag: false)은 붙이지 않는다
            for c in ([] if p.get("candidates_only") or p.get("tag") is False else cs[:1]):
                tags[(c["id"], p["key"])] = {"id": c["id"], "tag": p["key"], "source": f"{TAG_SOURCE}: {p['name']}", "as_of": r["as_of"]}
        mine = [m for m in members if m["program"] == p["key"]]
        names = {norm(m["name"]) for m in mine}
        firms = [m for m in mine if m["kind"] == "기업"]
        linked = {norm(m["name"]) for m in mine if m["id"]}
        w = sum(max((workers(c) for c in by.get(k, [])), default=0) for k in linked)
        summary.append({"key": p["key"], "group": p["group"], "name": p["name"], "short": p.get("short", p["name"]), "desc": p.get("desc", ""),
                        "n": len(names), "n_firm": len({norm(m['name']) for m in firms}), "n_org": len(names) - len({norm(m['name']) for m in firms}),
                        "n_outside": len({norm(m['name']) for m in firms if m['region'] == '역외'}), "n_linked": len(linked), "workers": w,
                        "subs": Counter(m["sub"] for m in mine if m["sub"]).most_common(8) if p["from"] != "history" else [],
                        "as_of": max((m["as_of"] for m in mine), default=p.get("as_of", "")), "source": p.get("source", ""),
                        "source_url": p.get("source_url", ""), "note": p.get("note", ""), "link": p.get("link", ""),
                        "candidates_only": bool(p.get("candidates_only")), "n_national": len(rows) if p.get("daegu_only_by_name") else None})
        print(f"[part] {p['key']:8} {p['name']}: 명단 {len(names)} (기업 {summary[-1]['n_firm']}, 기관 {summary[-1]['n_org']}, 역외 {summary[-1]['n_outside']}) · 기업 사전 연결 {len(linked)}")

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "members.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["program", "name", "kind", "sub", "region", "district", "id", "ids", "as_of"])
        w.writeheader()
        w.writerows(members)
    (OUT / "summary.json").write_text(json.dumps({"groups": cfg["groups"], "programs": summary}, ensure_ascii=False, indent=1), encoding="utf-8")

    old = list(csv.DictReader(open(TAGS, encoding="utf-8"))) if TAGS.exists() else []
    kept = [t for t in old if not t.get("source", "").startswith(TAG_SOURCE)]
    have = {(t["id"], t["tag"]) for t in kept}
    new = [t for k, t in sorted(tags.items()) if k not in have]
    with open(TAGS, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "tag", "source", "as_of"])
        w.writeheader()
        w.writerows(kept + new)
    print(f"[part] 명단 {len(members)}행 → {(OUT / 'members.csv').relative_to(ROOT)}, 태그 {len(new)}건 추가 → {TAGS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
