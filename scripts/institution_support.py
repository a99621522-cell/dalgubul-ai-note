#!/usr/bin/env python3
"""기업지원기관별 지원 기업 조사 — 공공데이터포털 과제·보조사업 파일(data/raw/<번호>/…)에서
config/support_institutions.yml 의 기관(대구TP·DIP·DMI·케이메디허브·창경센터·로봇산업진흥원·ETRI·생기원·경북대 …)이
주관·참여·수행·상위보조사업자로 든 사업을 찾아, 같은 사업의 기업을 '대구 기업 / 역외 기업 / 기관·대학' 으로 나눈다.

판정
- 기관·대학: 이름에 non_company_patterns(대학교·연구원·진흥원 …)가 들면 기업이 아니므로 뺀다
- 대구 기업: 기업 사전(팩토리온+산단 외+벤처 명단) 이름 일치, 또는 지역·주소 열에 '대구'
- 역외 기업: 그 밖의 모든 기업명 (주소 열이 없는 자료는 '대구 기업 사전에 없음' 이 기준이므로 '역외(사전 미수록 포함)' 로 표기)
- 평가·순위 없음. 공개 자료의 사실 나열. 사업자번호·대표자는 읽지 않는다

출력
- data/institutions/by_institution.csv  기관, 데이터셋, 연도, 사업명, 과제명, 기업명, 구분(대구/역외/기관), 근거
- data/institutions/summary.json         기관×연도 대구·역외 기업 수, 사업 수
- data/institutions/README.md            표 요약(사이트·리포트가 인용)

사용: python3 scripts/institution_support.py [data/raw] [--since 2018]
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sites import load_all_companies  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "institutions"
CFG = ROOT / "config" / "support_institutions.yml"
PORTAL = "https://www.data.go.kr/data/{id}/fileData.do"
DAEGU_RE = re.compile(r"대구광역시|(?<![가-힣])대구(?![가-힣])")


def norm(s: str) -> str:
    s = re.sub(r"\(주\)|㈜|\(유\)|주식회사|유한회사|유한책임회사|합자회사|농업회사법인|\(사\)|사단법인|재단법인|\(재\)", "", s or "")
    return re.sub(r"[\s\-_.,·ㆍ&/()\[\]'\"]", "", s).lower()


def read_any(p: Path) -> tuple[list[dict], list[str]]:
    if p.suffix.lower() in (".xlsx", ".xls"):
        import pandas as pd
        df = pd.read_excel(p, dtype=str).fillna("")
        return df.to_dict("records"), list(df.columns)
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("cp949", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    return rows, (list(rows[0].keys()) if rows else [])


def col(r: dict, names) -> str:
    """정확한 열 → 접두어 열(설명이 붙은 열 이름 대비)."""
    if isinstance(names, str):
        names = [names]
    for n in names:
        if n in r and r[n] not in (None, ""):
            return str(r[n]).strip()
    for n in names:
        for k, v in r.items():
            if k and k.replace(" ", "").startswith(n.replace(" ", "")) and v not in (None, ""):
                return str(v).strip()
    return ""


def split_names(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,;/|]| 외 ", s or "") if x.strip() and not re.fullmatch(r"\d+\s*(개|곳)?", x.strip())]


def main(argv: list[str]) -> int:
    raw_dir = Path(argv[0]) if argv and not argv[0].startswith("--") else RAW
    since = int(argv[argv.index("--since") + 1]) if "--since" in argv else 2018
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    insts = cfg["institutions"]
    alias_map = [(norm(a), i) for i in insts for a in i["aliases"]]
    non_co = re.compile("|".join(map(re.escape, cfg["non_company_patterns"])))
    known = {norm(c["name"]) for c in load_all_companies()}

    def inst_of(name: str):
        n = norm(name)
        return next((i for a, i in alias_map if a and a in n), None)

    def kind_of(name: str, region: str) -> tuple[str, str]:
        if inst_of(name) or non_co.search(name):
            return "기관·대학", "기관명 패턴"
        if norm(name) in known:
            return "대구 기업", "기업 사전 일치"
        if region and DAEGU_RE.search(region):
            return "대구 기업", "지역 열 '대구'"
        if region:
            return "역외 기업", f"지역 열 '{region[:12]}'"
        return "역외 기업(사전 미수록 포함)", "기업 사전에 없음·지역 열 없음"

    rows_out, missing = [], []
    for d in sorted(raw_dir.glob("*")):
        if not d.is_dir():
            continue
        ds = cfg["datasets"].get(d.name)
        if not ds:
            continue
        files = [f for f in d.iterdir() if f.suffix.lower() in (".csv", ".xlsx", ".xls")]
        for f in files:
            rows, cols = read_any(f)
            org_cols = [c for c in ds["orgs"] if c in cols or any(k.replace(" ", "").startswith(c) for k in cols)]
            if not org_cols:
                org_cols = [k for k in cols if re.search(r"기관|기업|사업자", k)]
                missing.append(f"[{d.name}] 설정한 열이 없어 이름 열 추정: {org_cols[:6]} (열 {cols[:15]})")
            n_hit = 0
            for r in rows:
                year = re.sub(r"\D", "", col(r, ds.get("year", "")))[:4] if ds.get("year") else ""
                if year and int(year) < since:
                    continue
                names_by_col = {c: split_names(col(r, c)) for c in org_cols}
                hit = {}
                for c, names in names_by_col.items():
                    for n in names:
                        i = inst_of(n)
                        if i:
                            hit[i["key"]] = (i, c)
                if not hit:
                    continue
                n_hit += 1
                region = col(r, ds["region"]) if ds.get("region") else ""
                program = col(r, ds.get("program", "")) if ds.get("program") else ""
                title = col(r, ds.get("title", "")) if ds.get("title") else ""
                partners = [(c, n) for c, names in names_by_col.items() for n in names if not inst_of(n)]
                region_col = ds.get("region_for") or org_cols[0]  # 지역 열은 그 열(보통 주관·수행기관)의 이름에만 적용
                for i, role_col in hit.values():
                    if not partners:  # 기관 혼자 수행한 과제
                        rows_out.append({"institution": i["name"], "key": i["key"], "role": role_col, "dataset": d.name, "dataset_name": ds["name"],
                                         "year": year, "program": program, "title": title, "company": "", "company_role": "", "kind": "기관 단독", "basis": "",
                                         "source_url": PORTAL.format(id=d.name)})
                    for c, n in partners:
                        kind, basis = kind_of(n, region if c == region_col else "")
                        rows_out.append({"institution": i["name"], "key": i["key"], "role": role_col, "dataset": d.name, "dataset_name": ds["name"],
                                         "year": year, "program": program, "title": title, "company": n, "company_role": c, "kind": kind, "basis": basis,
                                         "source_url": PORTAL.format(id=d.name)})
            print(f"[{d.name}] {f.name}: {len(rows):,}행 중 기관 관련 {n_hit:,}행 (이름 열 {org_cols})")
    for m in missing:
        print(m)
    if not rows_out:
        print("기관 관련 행 없음 — data/raw 에 과제 파일이 있는지, 열 이름이 설정과 맞는지 확인")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    # 같은 기관·연도·사업·과제·기업은 한 번만
    seen, uniq = set(), []
    for r in rows_out:
        k = (r["key"], r["year"], r["program"], r["title"], r["company"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    cols_out = ["institution", "key", "role", "dataset", "dataset_name", "year", "program", "title", "company", "company_role", "kind", "basis", "source_url"]
    with open(OUT / "by_institution.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols_out)
        w.writeheader()
        w.writerows(sorted(uniq, key=lambda r: (r["key"], r["year"], r["program"], r["title"], r["kind"], r["company"]), reverse=False))

    # 요약: 기관 × 연도 → 사업(과제) 수, 대구 기업 수, 역외 기업 수 (기업은 기관·연도 안에서 중복 제거)
    summ: dict = {}
    for i in insts:
        rs = [r for r in uniq if r["key"] == i["key"]]
        if not rs:
            continue
        by_year = defaultdict(lambda: {"projects": set(), "daegu": set(), "outside": set(), "programs": Counter()})
        for r in rs:
            y = by_year[r["year"] or "연도 미상"]
            y["projects"].add((r["program"], r["title"]))
            y["programs"][r["program"]] += 0
            if r["kind"] == "대구 기업":
                y["daegu"].add(norm(r["company"]))
                y["programs"][r["program"]] += 1
            elif r["kind"].startswith("역외"):
                y["outside"].add(norm(r["company"]))
        all_d = {norm(r["company"]) for r in rs if r["kind"] == "대구 기업"}
        all_o = {norm(r["company"]) for r in rs if r["kind"].startswith("역외")}
        summ[i["key"]] = {"name": i["name"], "note": i.get("note", ""), "datasets": sorted({r["dataset"] for r in rs}),
                          "total": {"projects": len({(r["program"], r["title"]) for r in rs}), "daegu_firms": len(all_d), "outside_firms": len(all_o)},
                          "by_year": {y: {"projects": len(v["projects"]), "daegu_firms": len(v["daegu"]), "outside_firms": len(v["outside"])}
                                      for y, v in sorted(by_year.items())},
                          "top_programs": [p for p, _ in Counter(r["program"] for r in rs if r["program"]).most_common(8)]}
    (OUT / "summary.json").write_text(json.dumps({"generated": __import__("datetime").date.today().isoformat(), "since": since,
                                                    "rule": "대구 기업 = 기업 사전(팩토리온·산단 외·벤처 명단) 이름 일치 또는 지역 열 '대구'. 역외 기업 = 그 외 기업명(지역 열 없는 자료는 사전 미수록 포함). 기관·대학은 제외. 평가 없음",
                                                    "institutions": summ}, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# 기업지원기관별 지원 기업 (공공데이터포털 과제·보조사업 자료, %d년 이후)" % since, "",
             "자동 생성: scripts/institution_support.py. 대구 기업 = 기업 사전 이름 일치 또는 지역 열 '대구'. 역외 기업 = 그 외(지역 열 없는 자료는 사전 미수록 포함). 기관·대학 제외. 사실 나열이며 평가·순위가 아님.", "",
             "| 기관 | 자료 | 사업(과제) 수 | 대구 기업 | 역외 기업 |", "|---|---|---:|---:|---:|"]
    for k, s in summ.items():
        lines.append(f"| {s['name']} | {', '.join(s['datasets'])} | {s['total']['projects']:,} | {s['total']['daegu_firms']:,} | {s['total']['outside_firms']:,} |")
    lines += ["", "## 기관별 연도 추이 (대구 / 역외 기업 수)", ""]
    for k, s in summ.items():
        yrs = " · ".join(f"{y}: {v['daegu_firms']}/{v['outside_firms']}" for y, v in s["by_year"].items())
        lines.append(f"- **{s['name']}** — {yrs}" + (f" ({s['note']})" if s["note"] else ""))
        if s["top_programs"]:
            lines.append(f"  - 사업: {', '.join(s['top_programs'][:6])}")
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"저장: {OUT.relative_to(ROOT)}/by_institution.csv ({len(uniq):,}행), summary.json, README.md")
    for k, s in summ.items():
        print(f"  {s['name']}: 과제 {s['total']['projects']:,} · 대구 기업 {s['total']['daegu_firms']:,} · 역외 기업 {s['total']['outside_firms']:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
