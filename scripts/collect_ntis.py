#!/usr/bin/env python3
"""NTIS(국가과학기술지식정보서비스) 오픈API 과제 검색 → 대구 수행기관 과제만 지원 이력 투입 CSV(scripts/data/support/ntis.csv)로.
표준 라이브러리 + requests. 키는 환경변수 NTIS_KEY. 설정은 scripts/sources.yml 의 ntis: (주소·검색어·연도·필드 이름).
이 세션 환경은 ntis.go.kr 접속이 막혀 있어 .github/workflows/ntis.yml 이 러너에서 돌린다.

사용: python3 scripts/collect_ntis.py --probe            # 응답 원문·항목 태그 이름만 찍어 필드 이름을 확인(첫 연결 때)
      python3 scripts/collect_ntis.py [--years 2023,2024,2025] [--query 대구] [--max-pages 50]
개인정보: 연구책임자·참여연구원 성명 필드(MANAGER/RESEARCHER/PERSON 이 든 태그)는 읽지 않는다. 수행기관명·과제명·사업명·부처·연도·정부연구비만.
"""
import argparse, csv, os, re, sys, time, xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
import requests, yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "data" / "support" / "ntis.csv"
CFG = yaml.safe_load((ROOT / "scripts" / "sources.yml").read_text(encoding="utf-8")).get("ntis") or {}
UA = "daitda-note-bot/1.0 (+https://note.daitda.co.kr)"
PERSONAL = re.compile(r"MANAGER|RESEARCHER|PERSON|MGR|LEADER|EMAIL|TEL|PHONE", re.I)
DAEGU = re.compile(r"대구")

# 응답 항목 태그 이름 후보 (NTIS 공개 API 문서마다 이름이 달라 후보를 여러 개 두고 --probe 로 확인한다)
FIELDS = {
    "id": ["PJT_ID", "PROJECT_ID", "PROJECT_NO", "PJT_NO"],
    "title": ["PJT_NAME", "PROJECT_NAME", "KOREAN_TITLE", "PJT_KOREAN_NAME"],
    "program": ["PJT_BUSINESS_NAME", "BUSINESS_NAME", "PROGRAM_NAME", "BSNS_NAME", "PROJECT_BUSINESS_NAME"],
    "ministry": ["ORDER_AGENCY", "MINISTRY_NAME", "MINISTRY", "ORDER_AGENCY_NAME", "SPECIALIST_AGENCY"],
    "org": ["RESEARCH_AGENCY", "RESEARCH_AGENCY_NAME", "AGENCY_NAME", "PERFORM_AGENCY", "MAIN_AGENCY"],
    "year": ["PJT_YEAR", "PROJECT_YEAR", "YEAR", "BSNS_YEAR"],
    "gov_money": ["GOV_RESEARCH_MONEY", "GOVERNMENT_FUNDS", "GOV_FUNDS", "GOVERNMENT_RESEARCH_MONEY"],
    "total_money": ["TOTAL_RESEARCH_MONEY", "TOTAL_FUNDS", "TOTAL_MONEY"],
    "region": ["RESEARCH_AGENCY_REGION", "REGION", "AGENCY_REGION", "RESEARCH_REGION", "ADDRESS"],
}
FIELDS.update({k: [v] if isinstance(v, str) else v for k, v in (CFG.get("fields") or {}).items()})


def get(params: dict, timeout: int = 60) -> str:
    url = CFG.get("api") or "https://www.ntis.go.kr/rndopen/openApi/public_project"
    r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r.text


def hits(xml_text: str):
    """응답 XML 에서 항목(HIT/ITEM/item) 목록을 태그→글자 사전으로. 개인정보 태그는 버린다."""
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    items = root.findall(".//HIT") or root.findall(".//ITEM") or root.findall(".//item")
    total = None
    for tag in ("TOTALHITS", "TOTAL_COUNT", "totalCount", "TOTALCOUNT"):
        e = root.find(".//" + tag)
        if e is not None and (e.text or "").strip().isdigit():
            total = int(e.text.strip()); break
    out = []
    for it in items:
        d = {}
        for ch in it.iter():
            if ch is it or PERSONAL.search(ch.tag):
                continue
            t = (ch.text or "").strip()
            if t and ch.tag not in d:
                d[ch.tag] = t
        out.append(d)
    return total, out


def pick(d: dict, key: str) -> str:
    for name in FIELDS[key]:
        for k, v in d.items():
            if k.upper() == name.upper():
                return v
    return ""


def company_names() -> set[str]:
    names = set()
    for f in ("dalseong_companies.csv", "extra_companies.csv"):
        p = ROOT / "scripts" / "data" / f
        if p.exists():
            for r in csv.DictReader(p.open(encoding="utf-8")):
                n = norm(r.get("name") or r.get("회사명") or "")
                if n:
                    names.add(n)
    return names


def norm(s: str) -> str:
    s = re.sub(r"\(주\)|\(유\)|주식회사|유한회사|㈜|\s+", "", s or "")
    return s.lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--years", default=CFG.get("years") or "")
    ap.add_argument("--query", default=CFG.get("query") or "대구")
    ap.add_argument("--max-pages", type=int, default=int(CFG.get("max_pages") or 50))
    a = ap.parse_args()
    key = os.environ.get("NTIS_KEY", "")
    if not key:
        print("::error::NTIS_KEY 가 없다"); return 1
    per = int(CFG.get("display_cnt") or 100)
    base = {"apprvKey": key, "collection": CFG.get("collection") or "project", "displayCnt": per, "startPosition": 1, "query": a.query}
    base.update(CFG.get("params") or {})
    if a.probe:
        base["displayCnt"] = 3
        txt = get(base)
        print(f"== 응답 {len(txt):,}자, 앞 6,000자 (키는 가려서 출력) ==")
        print(txt[:6000].replace(key, "***"))
        try:
            total, rows = hits(txt)
            print(f"== 총 건수 {total}, 항목 {len(rows)}개, 태그: {sorted(rows[0].keys()) if rows else '(없음)'}")
        except ET.ParseError as e:
            print(f"== XML 아님: {e}")
        return 0
    years = [y.strip() for y in str(a.years).split(",") if y.strip()] or [""]
    names = company_names()
    rows_out, seen, kept_region, kept_name = [], set(), 0, 0
    today = date.today().isoformat()
    for y in years:
        pos, page = 1, 0
        while page < a.max_pages:
            params = dict(base, startPosition=pos)
            if y:
                params["addQuery"] = (CFG.get("year_query") or "PJT_YEAR:{year}").format(year=y)
            try:
                txt = get(params)
                total, rows = hits(txt)
            except Exception as e:  # 매일 무인 실행: 죽이지 않고 건너뛴다
                print(f"::warning::{y} {pos}: {str(e)[:200]}"); break
            if not rows:
                break
            for d in rows:
                pid, org = pick(d, "id") or pick(d, "title"), pick(d, "org")
                if not org or pid in seen:
                    continue
                region = pick(d, "region")
                if region and DAEGU.search(region):
                    kept_region += 1
                elif norm(org) in names:
                    kept_name += 1
                else:
                    continue
                seen.add(pid)
                yr = re.sub(r"\D", "", pick(d, "year"))[:4] or y
                money = re.sub(r"[^\d]", "", pick(d, "gov_money") or pick(d, "total_money"))
                rows_out.append({"name": org, "program": (pick(d, "program") + (" — " + pick(d, "title") if pick(d, "title") else "")).strip(" —"),
                                 "year": yr, "funder": pick(d, "ministry"), "layer": "국비", "type": "R&D", "amount": money,
                                 "amount_unit": CFG.get("amount_unit") or "천원", "address": region,
                                 "source": "NTIS 국가R&D 과제(오픈API)", "source_url": f"https://www.ntis.go.kr/project/pjtInfo.do?pjtId={pid}" if pick(d, "id") else "https://www.ntis.go.kr", "as_of": today})
            print(f"{y or '전체'} {pos}/{total}: 대구 지역 {kept_region} · 기업 사전 이름 일치 {kept_name} (누적)", flush=True)
            if total is not None and pos + per > total:
                break
            pos += per; page += 1
            time.sleep(0.5)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["name", "program", "year", "funder", "layer", "type", "amount", "amount_unit", "address", "source", "source_url", "as_of"])
        w.writeheader(); w.writerows(rows_out)
    print(f"→ {OUT} {len(rows_out)}건 (지역 {kept_region}, 이름 일치 {kept_name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
