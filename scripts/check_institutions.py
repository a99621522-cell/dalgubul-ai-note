#!/usr/bin/env python3
"""대구 기업지원기관 목록(config/daegu_institutions.yml) → 표 / 홈페이지 조사.

  python3 scripts/check_institutions.py --list          # 네트워크 없이 목록 표만 → data/institutions/list.md
  python3 scripts/check_institutions.py [--only key,key] # 기관마다 첫 화면·robots.txt 를 받아 접속 결과와 '공고·공지' 링크 후보를
                                                         #   data/institutions/sites.md + sites.json 으로 (조사 결과, 평가 없음)

규칙: 공공기관 첫 화면과 robots.txt 만 받는다(기관당 요청 2번, 1초 간격). robots.txt 가 첫 화면을 막으면 링크를 찾지 않는다.
이 세션 환경은 외부 접속이 막혀 있어 .github/workflows/institution_sites.yml(수동, runner=korea 가능)로 돌린다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import yaml

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "daegu_institutions.yml"
OUT = ROOT / "data" / "institutions"
UA = "Mozilla/5.0 (compatible; daitda-note/1.0; +https://note.daitda.co.kr)"
GROUPS = {"data": "기초 자료", "city": "대구시 출연·출자·산하", "national": "국가 연구·전문기관(대구 소재)", "branch": "중앙부처·공공기관 대구경북 지역본부",
          "univ": "대학 산학협력·창업", "business": "경제단체·산단관리공단·협회", "gu": "구·군"}
LINK_PAT = re.compile(r"공고|공지|알림|사업안내|모집|선정|입찰|보도자료")


def load() -> list[dict]:
    return yaml.safe_load(CFG.read_text(encoding="utf-8"))["institutions"]


def write_list(insts: list[dict]) -> Path:
    lines = ["# 대구 기업지원기관 목록", "", f"기준 {date.today().isoformat()} · {len(insts)}곳 · 설정 config/daegu_institutions.yml · 공공·공익 기관만, 평가·순위 없음",
             "", "| # | 구분 | 기관 | 홈페이지 | 기업지원 기능 | 이미 쓰는 설정 | 비고 |", "|---:|---|---|---|---|---|---|"]
    n = 0
    for g, gname in GROUPS.items():
        for i in [x for x in insts if x.get("group") == g]:
            n += 1
            url = i.get("url") or ""
            link = f"[{urlparse(url).netloc}]({url})" if url else "(주소 확인 필요)"
            if i.get("verify") and url:
                link += " ⚠️확인 전"
            lines.append(f"| {n} | {gname} | {i['name']} | {link} | {', '.join(i.get('support') or [])} | {', '.join(i.get('linked') or [])} | {i.get('note') or ''} |")
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "list.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def robots_allows(home: str, sess) -> tuple[str, bool]:
    u = urlparse(home)
    rurl = f"{u.scheme}://{u.netloc}/robots.txt"
    try:
        r = sess.get(rurl, headers={"User-Agent": UA}, timeout=(15, 20))
    except Exception as e:  # noqa: BLE001
        return f"robots 실패({type(e).__name__})", True
    if r.status_code != 200:
        return f"robots {r.status_code}(없음)", True
    rp = RobotFileParser()
    rp.parse(r.text.splitlines())
    ok = rp.can_fetch("*", home) and rp.can_fetch(UA, home)
    return ("robots allow" if ok else "robots 차단"), ok


def check(inst: dict, sess) -> dict:
    rec = {"key": inst["key"], "name": inst["name"], "url": inst.get("url") or "", "status": "", "title": "", "robots": "", "links": [], "note": ""}
    if not rec["url"]:
        rec["status"] = "주소 없음"
        return rec
    rec["robots"], allowed = robots_allows(rec["url"], sess)
    time.sleep(1)
    try:
        r = sess.get(rec["url"], headers={"User-Agent": UA}, timeout=(15, 30), allow_redirects=True)
        rec["status"] = f"HTTP {r.status_code}"
        if r.url.rstrip("/") != rec["url"].rstrip("/"):
            rec["note"] = f"→ {r.url[:120]}"
        html = r.text
    except Exception as e:  # noqa: BLE001
        rec["status"] = f"실패 {type(e).__name__}"
        return rec
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    rec["title"] = re.sub(r"\s+", " ", m.group(1)).strip()[:80] if m else ""
    if not allowed:
        return rec
    seen = set()
    for href, text in re.findall(r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", html, re.S | re.I):
        label = re.sub(r"<[^>]+>|\s+", " ", text).strip()
        if not LINK_PAT.search(label) or len(label) > 40:
            continue
        full = urljoin(r.url, href.strip())
        if full in seen or urlparse(full).netloc != urlparse(r.url).netloc:
            continue
        seen.add(full)
        rec["links"].append({"text": label, "url": full})
        if len(rec["links"]) >= 8:
            break
    return rec


def write_sites(recs: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sites.json").write_text(json.dumps({"checked": date.today().isoformat(), "sites": recs}, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# 대구 기업지원기관 홈페이지 조사 결과", "", f"조사 {date.today().isoformat()} · {len(recs)}곳 · scripts/check_institutions.py (첫 화면·robots.txt 만 받음)",
             "", "| 기관 | 주소 | 접속 | robots | 제목 | 공고·공지 링크 후보 | 비고 |", "|---|---|---|---|---|---|---|"]
    for r in recs:
        links = "<br>".join(f"[{l['text']}]({l['url']})" for l in r["links"][:5])
        lines.append(f"| {r['name']} | {r['url']} | {r['status']} | {r['robots']} | {r['title']} | {links} | {r['note']} |")
    (OUT / "sites.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)
    insts = load()
    p = write_list(insts)
    print(f"목록 {len(insts)}곳 → {p.relative_to(ROOT)}")
    if a.list:
        return 0
    import requests
    sess = requests.Session()
    only = {k.strip() for k in a.only.split(",") if k.strip()}
    recs = []
    for inst in insts:
        if only and inst["key"] not in only:
            continue
        rec = check(inst, sess)
        recs.append(rec)
        print(f"[{rec['key']}] {rec['status']} · {rec['robots']} · {rec['title'][:40]} · 링크 {len(rec['links'])}개 {rec['note']}")
        time.sleep(1)
    write_sites(recs)
    print(f"저장: data/institutions/sites.md ({len(recs)}곳)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
