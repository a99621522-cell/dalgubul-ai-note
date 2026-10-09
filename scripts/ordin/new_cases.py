#!/usr/bin/env python3
"""새로 수집된 법제처 의견제시·법령해석례 가운데 대구 조문과 대조할 것만 골라 목록으로 남긴다.

네트워크 없음. ordinance_expc.yml 이 매주 수집(fetch_expc.py·fetch_opin.py) 뒤 돌린다.
입력
  data/ordinance/opin/index.json.gz   — 자치법규 의견제시 사례
  data/ordinance/expc/index.json.gz   — 법령해석례
  data/ordinance/cases_reviewed.json  — 세션이 이미 대조한 사례 번호(의견·해석)
  data/ordinance/ordin/*.json.gz      — 대구 자치법규 전문(같은 이름 조례 찾기)
  data/ordinance/lawrefs.json.gz      — 대구 자치법규의 법령 인용(같은 법령 인용 수)
출력
  data/ordinance/new_cases.json            — 대조할 사례(번호·제목·결론·대구 같은 이름 조례·같은 법령 인용 수)
  docs/ordinance/new_cases_<날짜>.md        — 세션이 읽을 목록

고르는 기준(2026-10-09 opin_other·expc_other 대조와 같음)
  의견제시: 결론이 '위배·위반·할 수 없다·바람직하지 않다·신중' 취지
  법령해석: 질의·회답·제목에 '조례'가 있거나, 지방자치단체·단체장·지방의회 질의에 '없습니다·아닙니다·않습니다' 취지 회답
  대구 지자체가 질의한 것은 expc_daegu 가 따로 잇는다(목록에는 '대구 질의'로 표시만).

세션이 목록을 대조해 config/ordinance_review.yml opinion:/expc: 에 반영한 뒤
  python3 scripts/ordin/new_cases.py --mark   로 목록의 번호를 '대조함'에 넣는다.
처음 한 번은 --seed 로 지금까지 받은 사례 전부를 '대조함'으로 둔다(2026-10-09 세션이 전수 대조).
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "ordinance"
LEDGER = D / "cases_reviewed.json"
ORG_KO = {"daegu": "대구시", "jung": "중구", "dong": "동구", "seo": "서구", "nam": "남구", "buk": "북구",
          "suseong": "수성구", "dalseo": "달서구", "dalseong": "달성군", "gunwi": "군위군"}

NEG_OPIN = re.compile(r"위배|위반|할 수 없|정할 수 없|규정할 수 없|바람직하지 않|적절하지 않|신중|허용되지 않|저촉")
LOCAL = re.compile(r"지방자치단체|시장|군수|구청장|시ㆍ도지사|자치구|지방의회")
NEG_EXPC = re.compile(r"없습니다|없을 것입니다|아닙니다|않습니다|않을 것입니다|없다고 할 것|볼 수 없|허용되지")
# 조례 이름 앞의 지자체 이름(서울특별시 종로구 / 청주시 / 경상남도 의령군 …)
LOCAL_PREFIX = re.compile(r"^(?:\S+(?:특별시|광역시|특별자치시|특별자치도|도)\s*)?(?:\S+(?:시|군|구)\s*)?(?:의회\s*)?")
DAEGU_PREFIX = re.compile(r"^대구광역시\s*(?:중구|동구|서구|남구|북구|수성구|달서구|달성군|군위군)?\s*(?:의회\s*)?")
ORD_NAME = re.compile(r"「([^」]*(?:조례|규칙)[^」]*)」")
LAW_NAME = re.compile(r"「([^」]*(?:법|법률|시행령|시행규칙))」")


def jl(p: Path, d):
    if not p.exists():
        return d
    with (gzip.open(p, "rt", encoding="utf-8") if p.suffix == ".gz" else open(p, encoding="utf-8")) as f:
        return json.load(f)


def core(name: str, daegu: bool) -> str:
    n = (DAEGU_PREFIX if daegu else LOCAL_PREFIX).sub("", name.strip())
    n = re.sub(r"\s*(일부\s*)?개정\s*조례안?$|\s*조례안$", " 조례", n)
    return re.sub(r"[\s·ㆍ]+", "", n)


def daegu_index():
    by = defaultdict(list)
    for f in sorted((D / "ordin").glob("*.json.gz")):
        for x in jl(f, {}).get("items") or []:
            by[core(x["name"], True)].append((x["org"], str(x["id"]), x["name"]))
    return by


def law_cites():
    out = {}
    for _lid, r in jl(D / "lawrefs.json.gz", {}).items():
        base = re.sub(r"\s*(시행령|시행규칙)$", "", r["name"]).strip()
        s = out.setdefault(base, set())
        for x in r.get("refs") or []:
            s.add((x["org"], x["oid"]))
    return out


def pick():
    op = jl(D / "opin" / "index.json.gz", {})
    ex = jl(D / "expc" / "index.json.gz", {})
    seen = jl(LEDGER, {"opin": [], "expc": []})
    so, se = set(seen.get("opin") or []), set(seen.get("expc") or [])
    out = []
    for x in op.values():
        if x["no"] in so:
            continue
        if not NEG_OPIN.search(x.get("concl") or ""):
            continue
        out.append({"kind": "의견제시", "no": x["no"], "org": x.get("org", ""), "d": x.get("d", ""), "t": x.get("t", ""),
                    "concl": (x.get("concl") or "")[:300], "q": (x.get("q") or "")[:600]})
    for x in ex.values():
        no = "해석" + x["no"]
        if no in se:
            continue
        txt = x.get("q", "") + x.get("a", "") + x.get("t", "")
        if not ("조례" in txt or (LOCAL.search(x.get("t", "") + x.get("q", "")) and NEG_EXPC.search(x.get("a", "")))):
            continue
        out.append({"kind": "법령해석", "no": no, "org": x.get("qorg", ""), "d": x.get("d", ""), "t": x.get("t", ""),
                    "concl": (x.get("a") or "")[:300], "q": (x.get("q") or "")[:600]})
    return out, op, ex


def main():
    day = dt.date.today().isoformat()
    args = sys.argv[1:]
    if "--seed" in args:
        op = jl(D / "opin" / "index.json.gz", {})
        ex = jl(D / "expc" / "index.json.gz", {})
        LEDGER.write_text(json.dumps({"updated": day, "note": "2026-10-09 세션 전수 대조(opin_other·expc_other) 때 받은 사례 전부",
                                      "opin": sorted(x["no"] for x in op.values()),
                                      "expc": sorted("해석" + x["no"] for x in ex.values())}, ensure_ascii=False) + "\n", encoding="utf-8")
        print("seed", LEDGER)
        return
    if "--mark" in args:
        cur = jl(D / "new_cases.json", {}).get("items") or []
        led = jl(LEDGER, {"opin": [], "expc": []})
        for c in cur:
            k = "opin" if c["kind"] == "의견제시" else "expc"
            if c["no"] not in led[k]:
                led[k].append(c["no"])
        led["opin"].sort(); led["expc"].sort(); led["updated"] = day
        LEDGER.write_text(json.dumps(led, ensure_ascii=False) + "\n", encoding="utf-8")
        print("mark", len(cur))
        return

    items, _, _ = pick()
    dg = daegu_index()
    cites = law_cites()
    for c in items:
        c["daegu_q"] = "대구" in c["org"]
        same = []
        for nm in ORD_NAME.findall(c["t"] + " " + c["q"]):
            k = core(nm, False)
            for kk, v in dg.items():
                if len(k) >= 6 and (k == kk or (len(kk) >= 6 and (k in kk or kk in k))):
                    same += v
        c["same_name"] = sorted({(o, i, n) for o, i, n in same})[:12]
        laws = []
        for ln in dict.fromkeys(LAW_NAME.findall(c["t"] + " " + c["q"])):
            base = re.sub(r"\s*(시행령|시행규칙)$", "", ln).strip()
            if base in cites:
                laws.append([base, len(cites[base])])
        c["law_cites"] = laws[:5]
    items.sort(key=lambda c: (c["d"]), reverse=True)
    if (jl(D / "new_cases.json", {}).get("items") or None) != (items or None):  # 같으면 날짜만 바뀌는 커밋을 만들지 않는다
        (D / "new_cases.json").write_text(json.dumps({"built": day, "items": items}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    if not items:
        print("새로 대조할 사례 없음")
        return
    L = [f"# 새 법제처 회신 — 대구 조문 대조 대상 ({day}, 세션 대조 전)", "",
         f"지난 대조(`data/ordinance/cases_reviewed.json`) 뒤 새로 받은 의견제시·법령해석례 가운데 '조례로 정할 수 없다'·'바람직하지 않다' 취지이거나 조례·지방자치단체 권한에 관한 부정 회답 {len(items)}건.",
         "대조 방법은 `docs/ordinance/opin_other_check_2026-10-09.md`·`expc_other_check_2026-10-09.md` 와 같다: 회답 근거 법령을 현행 원문과 대조하고, 대구 조문 전체를 읽어 같은 쟁점만 `config/ordinance_review.yml` `opinion:`/`expc:` 에 적은 뒤 `python3 scripts/ordin/new_cases.py --mark`.", ""]
    for c in items:
        L.append(f"## {c['kind']} {c['no']} — {c['org']} ({c['d']}){' · 대구 질의(expc_daegu)' if c['daegu_q'] else ''}")
        L.append(f"- 제목: {c['t']}")
        L.append(f"- 결론: {c['concl']}")
        if c["same_name"]:
            L.append("- 대구 같은 이름 자치법규: " + ", ".join(f"{ORG_KO.get(o, o)} {n}({i})" for o, i, n in c["same_name"]))
        if c["law_cites"]:
            L.append("- 같은 법령을 인용한 대구 자치법규 수: " + ", ".join(f"「{b}」 {n}건" for b, n in c["law_cites"]))
        L.append("")
    p = ROOT / "docs" / "ordinance" / f"new_cases_{day}.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(p, len(items))


if __name__ == "__main__":
    main()
