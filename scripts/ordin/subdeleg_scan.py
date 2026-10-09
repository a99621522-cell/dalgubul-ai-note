#!/usr/bin/env python3
"""규칙(시행규칙)이 주민 권리 제한·부담을 정한 곳 전수 점검 — 모조례의 구체적 위임 대조(네트워크 없음).

근거: 대법원 2020추5169(조례가 법률에서 위임받은 사항을 규칙에 재위임할 때도 규칙에 정할 내용의 대강을
조례만 보아도 예측할 수 있어야 함), 「지방자치법」 제156조제1항(사용료·수수료·분담금 징수는 조례로),
법제처 의견13-0283·13-0347·26-0099(사용료 상한·하한·산정기준 등 대강은 조례에), 의견23-0199·23-0344(금연구역 범위는 조례로).

입력: data/ordinance/ordin/<org>.json.gz(현행 자치법규 전문)
출력: docs/ordinance/subdeleg_scan_<날짜>.md — 사람이 대조할 목록. 대조 결과는 config/ordinance_review.yml 의 subdeleg: 에 적는다.

    python3 scripts/ordin/subdeleg_scan.py [날짜]
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "ordinance"

FEE = r"(사용료|수수료|이용료|입장료|점용료|요금)"
FEE_AMT = re.compile(FEE + r".{0,40}(\d[\d,.]*\s*원|별표)")
BASIS = re.compile(FEE + r"[^.。]{0,80}(별표|상한|하한|한도|범위\s*(에서|안에서|내에서|내)|이내|초과하지|산정|단위|요율|\d[\d,.]*\s*원|퍼센트|분의)")
WEAK = re.compile(FEE + r"[^.。]{0,80}고려하여")
VAGUE = re.compile(r"합리적\s*범위")
DIST = re.compile(r"\d+\s*(미터|m|킬로미터|㎞)\s*(이내|이상|안)")
RESTRICT = re.compile(r"금연|가축|사육|제한|금지|할\s*수\s*없|아니\s*된다")
GEN = re.compile(r"시행에\s*(관하여\s*)?필요한\s*사항은.{0,10}규칙으로")


def one(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def load():
    rules, ords = [], {}
    for f in sorted((D / "ordin").glob("*.json.gz")):
        for x in json.load(gzip.open(f, "rt", encoding="utf-8"))["items"]:
            x["name"] = re.sub(r"\s+", " ", x["name"])
            if x["kind"] == "규칙":
                rules.append(x)
            else:
                ords[(x["org"], x["name"])] = x
    return rules, ords


def norm(n: str) -> str:
    return re.sub(r"[\s·ㆍ.,]", "", n)


def parent_of(r, ords):
    idx = {(o, norm(n)): x for (o, n), x in ords.items()}
    for cand in (re.sub(r"\s*시행\s*규칙$", "", r["name"]), re.sub(r"규칙$", "조례", r["name"])):
        x = idx.get((r["org"], norm(cand)))
        if x and x["name"] != r["name"]:
            return x
    return None


def dists(t: str) -> set:
    return {re.sub(r"\s", "", m.group(0)).replace("m", "미터") for m in re.finditer(r"\d+\s*(미터|m)(?![a-z²])", t)}


def scan():
    rules, ords = load()
    fee, dist = [], []
    for r in rules:
        P = parent_of(r, ords)
        for a in r["articles"]:
            t, ti = a["text"], a.get("title") or ""
            if re.search(r"서식|삭제", ti):
                continue
            # 1) 사용료·수수료 금액을 규칙에서 정함 — 모조례에 대강(상한·범위·산정기준)이 있는지
            if FEE_AMT.search(t) and not re.search(r"반환|감면|지원", ti) and not re.search(r"조례」?\s*별표|관련한\s*별표", t):
                if not P:
                    st, pa = "모조례 없음(법령 직접 위임 여부 확인)", []
                else:
                    pa = [x for x in P["articles"] if re.search(FEE, x["text"]) and not re.search(r"정의|목적", x.get("title") or "")
                          and not (re.search(r"감면|반환", x.get("title") or "") and not re.search(r"징수|사용료\s*등|이용료\s*등|\(사용료\)|\(이용료\)", x.get("title") or ""))]
                    ok = [x for x in pa if any(not VAGUE.search(m.group(0)) and not re.search(r"감면|반환", m.group(0)) for m in BASIS.finditer(x["text"]))]
                    weak = [x for x in pa if WEAK.search(x["text"])]
                    st = "대강 있음" if ok else ("고려 요소만" if weak else "대강 없음")
                fee.append((st, r, a, P, pa))
            # 2) 거리·범위 기준으로 권리를 제한하는 규칙 조문
            if DIST.search(t) and RESTRICT.search(r["name"] + t) and not re.search(r"행정기구|정원|하부조직", r["name"]):
                if not P:
                    st, pa = "모조례 없음(법령 직접 위임 여부 확인)", []
                else:
                    pd = set().union(*[dists(x["text"]) for x in P["articles"]]) if P["articles"] else set()
                    miss = sorted(dists(t) - pd)
                    pa = [x for x in P["articles"] if DIST.search(x["text"])]
                    st = f"조례에 없는 거리: {', '.join(miss)}" if miss else "조례에 같은 거리 있음"
                dist.append((st, r, a, P, pa))
    return fee, dist


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
    fee, dist = scan()
    L = [f"# 규칙이 정한 사용료·거리 기준 — 모조례 위임 대조 ({day}, 자동 목록 · 세션 대조 전)", "",
         "`scripts/ordin/subdeleg_scan.py` 가 만든 목록. '대강 없음'·'고려 요소만'·'조례에 거리 기준 없음'을 사람이 원문과 대조하고,",
         "후보로 올릴 것은 `config/ordinance_review.yml` 의 `subdeleg:` 에 적는다.", ""]
    for title, rows in (("사용료·수수료 금액을 정한 규칙 조문", fee), ("거리 기준으로 권리를 제한하는 규칙 조문", dist)):
        L += [f"## {title} ({len(rows)}건)", "", "| 판정 | 규칙 | 조문 | 모조례 관련 조문 |", "|---|---|---|---|"]
        for st, r, a, P, pa in sorted(rows, key=lambda x: (x[0], x[1]["org"], x[1]["name"])):
            pp = " / ".join(f"{x['no']} {one(x['text'])[:120]}" for x in pa[:2]).replace("|", "｜")
            L.append(f"| {st} | {r['name']} ({r['id']}) | {a['no']}({a.get('title') or ''}) | {pp} |")
        L.append("")
    out = ROOT / "docs" / "ordinance" / f"subdeleg_scan_{day}.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(out, len(fee), len(dist))


if __name__ == "__main__":
    main()
