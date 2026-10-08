"""대구 자치법규 정비 검토 — 신호 판정(수집 결과만 읽음, 네트워크 없음 → 세션·러너 어디서나).

입력: data/ordinance/{list.json, ordin/*.json.gz, laws/index.json, laws/arts/*.json.gz, laws/johist.json.gz, laws/gov_org.txt}
      config/ordinance_signals.yml · ordinance_terms.yml · ordinance.yml
출력: data/ordinance/candidates.json(후보), summary.json(건수·파싱 지표), lawrefs.json(법령 → 인용 자치법규 역색인),
      eval/sample.csv(신호별 표본 — 운영자가 맞음/아님 표시)
원칙: 판정이 아니라 '정비 검토 후보'. 원문 그대로 인용. 순위·평가 없음.
"""
from __future__ import annotations

import csv
import os
import gzip
import json
import random
import re
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refs import extract, norm_name  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
D = Path(os.environ.get("ORDIN_DATA") or ROOT / "data" / "ordinance")
CFG = yaml.safe_load((ROOT / "config" / "ordinance.yml").read_text(encoding="utf-8"))
SIG = yaml.safe_load((ROOT / "config" / "ordinance_signals.yml").read_text(encoding="utf-8"))["signals"]
TERMS = yaml.safe_load((ROOT / "config" / "ordinance_terms.yml").read_text(encoding="utf-8"))
CRULES = yaml.safe_load((ROOT / "config" / "ordinance_content_rules.yml").read_text(encoding="utf-8"))["rules"]
# YAML 1.1 은 키 `no` 를 불(False)로 읽는다 — 사례 번호 키를 되돌린다
for _r in CRULES.values():
    _r["prec"] = [{("no" if k is False else k): v for k, v in q.items()} for q in _r.get("prec") or []]
TODAY = date.today().strftime("%Y%m%d")


def jl(p: Path, default):
    if not p.exists():
        return default
    if p.suffix == ".gz":
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(p.read_text(encoding="utf-8"))


def ymd(s: str) -> str:
    return f"{s[:4]}-{s[4:6]}-{s[6:]}" if s and len(s) == 8 else (s or "")


def ordin_url(d):
    return f"https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq={d['mst']}"


def law_url(name, art=""):
    return f"https://www.law.go.kr/법령/{name.replace(' ', '')}" + (f"/제{art}조" if art and "의" not in art else (f"/제{art.replace('의', '조의')}" if art else ""))


REGION = re.compile(r"^(?:[가-힣]{1,5}?(?:특별자치시|특별자치도|특별시|광역시|도))?(?:[가-힣]{1,4}?(?:시|군|구))?")


def base_name(name: str) -> str:
    """자치법규 이름에서 지자체 이름을 뗀 비교용 이름: '대구광역시 달서구 지방보조금 관리 조례' → '지방보조금관리조례'.
    '…조례안'의 '안', 가운뎃점·공백 변이도 없앤다. 남는 이름이 4자 미만이면 빈 값(비교하지 않음)."""
    n = norm_name(name)
    n = re.sub(r"안$", "", n)
    b = REGION.sub("", n, count=1)
    return b if len(b) >= 4 else ""


# 법제처 의견제시 결론이 '조례로 정할 수 없다' 쪽인 표현
NEG = re.compile(r"(정할|규정할|둘|부과할|제한할|감면할|지급할|위임할|설치할|할)\s*수\s*없|위반|위배|저촉|어긋나|허용되지\s*않|위임이\s*없|위임\s*범위를\s*(벗어|넘)|바람직하지\s*않|적절하지\s*않|타당하지\s*않|근거가\s*없")
AMEND = re.compile(r"(일부\s*개정|폐지|일괄\s*개정|전부\s*개정)[^가-힣]*(조례|규칙)$|등\s*일부\s*개정")
GENERIC = re.compile(r"^(목적|정의|다른\s*법률과의\s*관계|적용\s*범위|시행일|벌칙|과태료|권한의\s*위임)")   # 해석·의견제시와 잇기엔 너무 일반적인 조문


STOP = {"등", "및", "의", "관한", "위한", "대한", "따른", "사항", "경우", "특례", "기준", "방법", "절차", "지방자치단체", "국가", "설치", "운영",
        "관리", "지원", "시행", "규정", "적용", "범위", "업무", "사무", "위원회"}


def title_hit(title: str, ctx: str) -> bool:
    """조문 제목 낱말(2자 이상, 흔한 말 제외) 가운데 하나라도 인용 구절·자치법규 조 제목에 있으면 True(표본 대조 2026-10-08: 2개 요구는 같은 조문을 놓침)."""
    words = [w for w in re.split(r"[\s,·ㆍ()]+", title or "") if len(w) >= 2 and w not in STOP]
    words = [re.sub(r"(의|에|을|를|과|와|은|는)$", "", w) if len(w) >= 3 else w for w in words]   # '정의'의 '의'는 조사가 아니다
    words = [w for w in words if len(w) >= 2 and w not in STOP]
    return any(w in ctx for w in words)


KEYSTOP = {"대구광역시", "조례", "규칙", "시행규칙", "및", "등", "관한", "에", "의", "위한", "설치", "운영", "구성", "지원", "운용", "기금", "특별회계", "관리"}


def close_names(q: str, pool: list[str]) -> list[str]:
    """이름이 바뀐 자치법규 후보: 핵심 낱말(지자체 이름·'조례' 등 뺀 것)이 절반 이상 겹치는 현행 이름을, 겹친 낱말 수 → 글자 비율 순으로 2개.
    '의회' 자치법규는 인용 이름에 '의회'가 있을 때만(2026-10-08 대조: '포상 조례'가 '의회 포상 조례'로 잘못 이어짐)."""
    import difflib
    def keys(x):
        x = re.sub(r"^대구광역시\s*(중구|동구|서구|남구|북구|수성구|달서구|달성군|군위군)?", "", x)
        ws = [re.sub(r"(에|의|을|를)$", "", w) for w in re.split(r"[\s·ㆍ,]+", x) if w]
        return {w for w in ws if len(w) >= 2 and w not in KEYSTOP}
    kq = keys(q)
    if not kq:
        return []
    out = []
    for n in pool:
        if "의회" in n and "의회" not in q:
            continue
        nn = norm_name(n)
        hit = sum(1 for w in kq if w in nn)
        if hit * 2 >= len(kq) and hit:
            out.append((hit, difflib.SequenceMatcher(None, norm_name(q), nn).ratio(), n))
    out.sort(reverse=True)
    return [n for h, r, n in out[:2] if r >= 0.55]


def art_sort(a: str):
    return [int(x) for x in a.split("의")] if re.fullmatch(r"\d+(의\d+)?", a or "") else [9999]


def main():
    lst = jl(D / "list.json", None)
    if not lst:
        print("list.json 없음 — 수집 먼저")
        return
    laws = jl(D / "laws" / "index.json", {"items": {}})["items"]
    jh = jl(D / "laws" / "johist.json.gz", {})
    oldt = jl(D / "laws" / "old_titles.json.gz", {})   # 자치법규 공포 당시 판의 조문 제목(fetch 5b)
    gov = (D / "laws" / "gov_org.txt").read_text(encoding="utf-8") if (D / "laws" / "gov_org.txt").exists() else ""
    arts_cache: dict[str, dict] = {}

    def arts_of(lid):
        if lid not in arts_cache:
            arts_cache[lid] = jl(D / "laws" / "arts" / f"{lid}.json.gz", None)
        return arts_cache[lid]

    org_name = {o["key"]: o["name"] for o in CFG["orgs"]}
    # 법제처 법령해석례: (법령 이름, 조) → 해석례 목록. 자치법규 관련(local) 또는 대구 질의(dg)만 잇는다
    expc = jl(D / "expc" / "index.json.gz", {})
    ex_by: dict[tuple, list] = {}
    for iid, e in expc.items():
        if not (e.get("local") or e.get("dg")):
            continue
        # 쟁점 조문 = 안건명의 인용(질의요지·회답 속 부수 인용은 잇지 않음, 표본 대조 2026-10-08)
        for r0 in extract([{"no": "", "text": e.get("t", "")}]):
            if r0["art"]:
                k0 = (norm_name(r0["law"]), r0["art"])
                if iid not in ex_by.get(k0, []):
                    ex_by.setdefault(k0, []).append(iid)
    # 법령별 최근 전부개정일(조문 번호가 바뀌었을 수 있는 경계) — 경계 앞뒤가 다른 해석례·자치법규는 잇지 않는다
    # 법제처 자치법규 의견제시 사례(법제처 누리집 공개 게시판): ① 같은 이름 자치법규(지자체 이름 뗀 이름) ② 쟁점 조문(제목·질의요지의 법령 조문)
    opin = jl(D / "opin" / "index.json.gz", {})
    op_by_name: dict[str, list] = {}
    op_by_art: dict[tuple, list] = {}
    for sq, e in opin.items():
        for nm in e.get("targets", []):
            b = base_name(nm)
            if b and sq not in op_by_name.get(b, []):
                op_by_name.setdefault(b, []).append(sq)
        for nn2, _raw, art in e.get("refs", []):
            if art:
                op_by_art.setdefault((nn2, art), []).append(sq)
    def op_card(sq):
        e = opin[sq]
        return {"id": sq, "t": e["t"], "no": e.get("no", ""), "d": ymd(e.get("d", "")), "qorg": e.get("org", ""),
                "a": (e.get("op", "") if len(e.get("op", "")) > 40 else (e.get("op", "") + " " + e.get("why", "")).strip())[:220],
                "url": f"https://www.moleg.go.kr/lawinfo/reglAnalysis/reglAnalysisInfo.mo?mid=a10107020000&caseSeq={sq}", "dg": e.get("dg", ""), "kind": "opin"}
    op_ord: dict[str, set] = {}   # 대구 요청 의견제시 → 이은 같은 지자체 자치법규
    ex_ord: dict[str, set] = {}   # 대구 질의 해석례 → 이은 같은 지자체 자치법규(전부개정 경계 반영)
    full_rev: dict[str, str] = {}
    for k, h in jh.items():
        lid = k.split("|")[0]
        for x in h.get("rows", []):
            if re.search(r"전부개정|전문개정", (x.get("why") or "") + (x.get("rev") or "")) and (x.get("d") or "") > full_rev.get(lid, ""):
                full_rev[lid] = x["d"]
    def ex_card(iid):
        e = expc[iid]
        return {"id": iid, "t": e["t"], "no": e.get("no", ""), "d": ymd(e.get("d", "")), "qorg": e.get("qorg", ""), "a": e.get("a", "")[:220],
                "url": f"https://www.law.go.kr/LSW/expcInfoP.do?expcSeq={iid}", "dg": e.get("dg", "")}
    cands, n_ref, n_ref_ok, n_unres = [], 0, 0, 0
    lawrefs: dict[str, dict] = {}
    ordin_count = {}
    seq = 0

    def add(d, art, sig, **kw):
        nonlocal seq
        seq += 1
        cands.append({"id": f"{d['org']}-{d['id']}-{seq}", "org": d["org"], "oid": d["id"], "oname": d["name"], "kind": d.get("kind", ""),
                      "prom": d.get("prom", ""), "dept": d.get("dept", ""), "url": ordin_url(d), "no": art.get("no", "") if art else "",
                      "atitle": art.get("title", "") if art else "", "text": (art.get("text", "") if art else "")[:1500],
                      "sig": sig, "conf": SIG[sig]["conf"], **kw})

    # 정부조직법 본문에서 부칙(경과 규정의 옛 이름)과 새 이름(겹침: '기후에너지환경부' 안의 '환경부')을 빼고 옛 이름을 찾는다
    mpos = re.search(r"\n부\s*칙\s*<", gov)
    gov_body = gov[: mpos.start()] if mpos else gov
    for m in TERMS.get("ministries", []):
        gov_body = gov_body.replace(m.get("now") or "\0", "")
    ministries = [m for m in TERMS.get("ministries", []) if gov and m["old"] not in gov_body]
    if not gov:
        print("  정부조직법 본문 없음 — 옛 기관명 신호 건너뜀")
    for o in CFG["orgs"]:
        items = jl(D / "ordin" / f"{o['key']}.json.gz", {"items": []})["items"]
        ordin_count[o["key"]] = len(items)
        for d in items:
            if AMEND.search(d.get("name", "")):
                continue   # 다른 자치법규를 고치거나 없애는 일괄 개정·폐지 조례 — 폐지 대상 이름을 인용하는 것이 정상
            arts = d.get("articles") or []
            prom = d.get("prom") or ""
            refs = extract(arts)
            seen = set()
            art_by_no = {a["no"]: a for a in arts}
            b = base_name(d["name"])
            if b and b in op_by_name:
                ids = sorted(op_by_name[b], key=lambda i: opin[i].get("d") or "", reverse=True)
                mine = [i for i in ids if opin[i].get("dg") == d["org"]]
                for i in mine:
                    op_ord.setdefault(i, set()).add(d["id"])
                sig = "opin_daegu" if mine else "opin_same"
                use = mine or ids
                # 법제처가 '조례로 정할 수 없다'·'위임 범위를 벗어난다' 취지로 회신한 사례 → 상위법령 위반 소지(같은 규정이 있는지 확인)
                neg = [i for i in use if NEG.search(opin[i].get("concl", "") or opin[i].get("op", ""))]
                if neg:
                    sig = "opin_conflict"
                    use = neg + [i for i in use if i not in neg]
                add(d, None, sig, ev={"base": b, "n": len(use), "ordin_prom": ymd(prom), "after": any((opin[i].get("d") or "") > prom for i in use),
                                      "concl": (opin[use[0]].get("concl") or opin[use[0]].get("op") or "")[:300], "mine": bool(mine),
                                      "expc": [op_card(i) for i in use[:4]], "targets": sorted({t for i in use[:4] for t in opin[i].get("targets", [])})[:6]})
            for r in refs:
                n_ref += 1
                nn = norm_name(r["law"])
                L = laws.get(nn)
                a = art_by_no.get(r["no"])
                if not L:
                    n_unres += 1
                    continue
                st = L.get("status")
                if st in ("current", "renamed", "admrul", "local", "local_other"):
                    n_ref_ok += 1
                # 역색인
                if st == "current":
                    lr = lawrefs.setdefault(L["law_id"], {"name": L["name"], "eff": L.get("eff", ""), "refs": {}})
                    k = f"{d['org']}|{d['id']}"
                    e = lr["refs"].setdefault(k, {"org": d["org"], "oid": d["id"], "oname": d["name"], "arts": []})
                    if r["art"] and r["art"] not in e["arts"]:
                        e["arts"].append(r["art"])
                key = (r["no"], nn, r["art"])
                if key in seen:
                    continue
                seen.add(key)
                ev = {"law": r["law"], "art": r["art"], "ctx": r["ctx"]}
                if st == "renamed":
                    c = L["now"]
                    if (nn, "renamed", r["no"]) not in seen:
                        seen.add((nn, "renamed", r["no"]))
                        add(d, a, "law_renamed", ev={**ev, "now": c["name"], "now_url": law_url(c["name"]), "hist": L.get("hist", [])[:6]},
                            fix={"old": f"「{r['law']}」", "new": f"「{c['name']}」"})
                elif st == "not_current":
                    if (nn, "nc", r["no"]) not in seen:
                        seen.add((nn, "nc", r["no"]))
                        add(d, a, "law_not_current", ev={**ev, "hist": L.get("hist", [])[:8], "cands": [c["name"] for c in L.get("cands", [])][:4]})
                elif st in ("search_only", "unresolved"):
                    if (nn, "un", r["no"]) not in seen:
                        seen.add((nn, "un", r["no"]))
                        add(d, a, "name_unmatched", ev={**ev, "cands": [c["name"] for c in L.get("cands", [])][:4]})
                elif st == "local_missing":
                    if (nn, "lm", r["no"]) not in seen:
                        seen.add((nn, "lm", r["no"]))
                        add(d, a, "local_ref_missing", ev=ev)
                elif st == "admrul_missing":
                    if (nn, "am", r["no"]) not in seen:
                        seen.add((nn, "am", r["no"]))
                        add(d, a, "admrul_missing", ev={**ev, "cands": L.get("cands", [])[:4]})
                gen = False
                if st == "current" and r["art"]:
                    A0 = arts_of(L["law_id"])
                    gen = bool(A0 and GENERIC.match((A0["arts"].get(r["art"]) or {}).get("t", "")))
                if not gen and st == "current" and r["art"] and (nn, r["art"]) in op_by_art and (nn, "op", r["no"], r["art"]) not in seen:
                    seen.add((nn, "op", r["no"], r["art"]))
                    fr = full_rev.get(L["law_id"], "")
                    ids = [i for i in op_by_art[(nn, r["art"])] if not fr or ((opin[i].get("d") or "") >= fr) == (prom >= fr)]
                    if ids:
                        ids.sort(key=lambda i: opin[i].get("d") or "", reverse=True)
                        add(d, a, "opin_article", ev={**ev, "now": L["name"], "now_url": law_url(L["name"], r["art"]), "ordin_prom": ymd(prom),
                                                       "after": any((opin[i].get("d") or "") > prom for i in ids), "n": len(ids), "expc": [op_card(i) for i in ids[:4]]})
                if not gen and st == "current" and r["art"] and (nn, r["art"]) in ex_by and (nn, "ex", r["no"], r["art"]) not in seen:
                    seen.add((nn, "ex", r["no"], r["art"]))
                    fr = full_rev.get(L["law_id"], "")
                    ids = [i for i in ex_by[(nn, r["art"])] if not fr or ((expc[i].get("d") or "") >= fr) == (prom >= fr)]
                    ids.sort(key=lambda i: expc[i].get("d") or "", reverse=True)
                    mine = [i for i in ids if expc[i].get("dg") == d["org"]]
                    for i in mine:
                        ex_ord.setdefault(i, set()).add(d["id"])
                    if mine:
                        last = max(expc[i].get("d") or "" for i in mine)
                        add(d, a, "expc_daegu", ev={**ev, "now": L["name"], "now_url": law_url(L["name"], r["art"]), "ordin_prom": ymd(prom),
                                                     "after": last > prom, "expc": [ex_card(i) for i in mine[:4]]})
                    elif ids:
                        add(d, a, "expc_related", ev={**ev, "now": L["name"], "now_url": law_url(L["name"], r["art"]), "ordin_prom": ymd(prom),
                                                       "after": any((expc[i].get("d") or "") > prom for i in ids), "n": len(ids), "expc": [ex_card(i) for i in ids[:4]]})
                if st == "current" and r["art"]:
                    A = arts_of(L["law_id"])
                    if not A:
                        continue
                    la = A["arts"].get(r["art"])
                    ev2 = {**ev, "now": L["name"], "now_url": law_url(L["name"], r["art"]), "law_eff": ymd(A.get("eff", ""))}
                    if la is None:
                        add(d, a, "article_missing", ev=ev2)
                        continue
                    ev2["atitle"] = la.get("t", "")
                    ev2["atext"] = la.get("x", "")
                    if la.get("del"):
                        add(d, a, "article_deleted", ev=ev2)
                        continue
                    h = jh.get(f"{L['law_id']}|{r['art']}")
                    if not h or not prom:
                        continue
                    # 자치법규 최종 공포 뒤에 '공포'되고 오늘까지 '시행'된 조문 변경 — 공포 뒤·시행 전에 미리 고친 자치법규는 걸리지 않는다
                    later = [x for x in h.get("rows", []) if prom < (x.get("prom") or x.get("d") or "") and (x.get("d") or "") <= TODAY and x.get("why") != "제정"]
                    if not later:
                        continue
                    ren = [x for x in later if re.search(r"전부개정|전문개정|이동", (x.get("why") or "") + (x.get("rev") or ""))]
                    if ren:
                        # 공포 당시 판의 같은 번호 조문 제목과 지금 제목을 비교한다(표본 대조 2026-10-08: 제목 낱말 짐작은 정확도 60% 안팎)
                        before = [x for x in h.get("rows", []) if (x.get("prom") or x.get("d") or "") <= prom and x.get("mst")]
                        b0 = max(before, key=lambda x: (x.get("prom") or x["d"], x["d"])) if before else None
                        ot = oldt.get(f"{L['law_id']}|{r['art']}|{b0['mst']}") if b0 else None
                        tn = lambda x: norm_name(re.sub(r"<[^>]*>|\[[^\]]*\]", "", x or ""))   # '<개정 2003.1.20>' 같은 표기는 빼고 비교
                        if ot and ot.get("t") and tn(ot["t"]) != tn(la.get("t", "")):
                            ev2["old_title"], ev2["old_text"], ev2["old_d"] = ot["t"], ot.get("x", ""), ymd(b0["d"])
                        else:
                            if ot and ot.get("t"):
                                ev2["old_title"] = ot["t"]   # 제목이 같음 — 번호는 그대로
                            ren = []
                    ev2["changes"] = [{"d": ymd(x["d"]), "why": x.get("why", ""), "rev": x.get("rev", "")} for x in later][-6:]
                    ev2["ordin_prom"] = ymd(prom)
                    add(d, a, "article_renumber" if ren else "article_changed", ev=ev2)
            # 본문 낱말 신호(부칙 제외)
            for a in arts:
                t = re.sub(r"「[^」]*」", "「」", a.get("text") or "")   # 인용 법령 이름 안의 낱말은 이름 신호가 맡는다
                for m in ministries:
                    body = t
                    if m.get("now"):
                        body = body.replace(m["now"], "")   # '기후에너지환경부' 안의 '환경부' 같은 겹침 제외
                    if m["old"] in body:
                        i = t.find(m["old"])
                        add(d, a, "ministry_outdated", ev={"old": m["old"], "now": m.get("now", ""), "ctx": t[max(0, i - 40): i + 60]},
                            fix={"old": m["old"], "new": m.get("now", "")} if m.get("now") and m["now"] in gov else None)
                for tm in TERMS.get("terms", []):
                    pat = r"(?<![가-힣])" + re.escape(tm["old"]) + (r"(?!단|재단|센터)" if tm["old"] == "문화재" else "") + (r"(?!환|질)" if tm["old"] == "간질" else "")
                    mm = re.search(pat, t)
                    if mm:
                        add(d, a, "term_outdated", ev={"old": tm["old"], "new": tm["new"], "basis": tm["basis"], "ctx": t[max(0, mm.start() - 40): mm.end() + 60]})
                if o["key"] == "gunwi":
                    mm = re.search(r"경상북도(?!\s*(또는|및|산|·|ㆍ))|경북(?!대|지원|지부|지역본부)|(?<![가-힣ㆍ·])도지사", t)
                    if mm:
                        add(d, a, "gunwi_gb", ev={"ctx": t[max(0, mm.start() - 40): mm.end() + 60], "word": mm.group(0)})
                raw = a.get("text") or ""
                if "과태료" in (a.get("title") or "") and not re.search(r"삭\s*제", raw[:40]) and not re.search(r"「[^」]+」|(?<![가-힣])(법|영|시행령|시행규칙|규칙|조례)\s*제\s*\d+\s*조", raw):
                    add(d, a, "penalty_basis", ev={"ctx": t[:200]})
                # 조례 내용 점검(config/ordinance_content_rules.yml) — 항(①②…·줄) 단위로 규칙의 낱말이 모두 맞으면 후보
                if not re.search(r"삭\s*제", raw[:40]):
                    paras = [p for p in re.split(r"(?=[①-⑳])|\n", raw) if p.strip()]
                    for rk, R in CRULES.items():
                        if R.get("scope") and not re.search(R["scope"], d["name"]):
                            continue
                        if R.get("not_scope") and re.search(R["not_scope"], d["name"]):
                            continue
                        if R.get("title") and not re.search(R["title"], a.get("title") or ""):
                            continue
                        if R.get("not_title") and re.search(R["not_title"], a.get("title") or ""):
                            continue
                        hitp = next((p for p in paras if all(re.search(x, p) for x in R["all"]) and not any(re.search(x, p) for x in R.get("none", []))), None)
                        if hitp and R.get("special") == "rights":
                            # 그 항이 법률(또는 법·영 약칭) 조문을 인용하면 위임이 있는 것으로 보고 넘긴다.
                            if re.search(r"「[^」]+」|(?<![가-힣])(법|영|시행령|시행규칙)\s*(제\s*\d+\s*조|에\s*따라|에서\s*정하는)", hitp):
                                continue
                            # 자치법규 전체가 법률 위임으로 제정됐다고 밝히면(제1조 '위임된 사항') 위임 범위를 벗어났는지만 남는다 → 참고로
                            first = (arts[0].get("text") or "") if arts else ""
                            # 제1조가 법률을 근거로 밝히거나(「…법」) 공공시설 이용 규칙(행위 제한·금지)이면 '위임 범위 확인' 참고로
                            facility = re.search(r"시설|센터|공원|회관|박물관|도서관|체육|캠핑|휴양|마을|광장|주차장", d["name"]) and re.search(r"행위|금지|제한|준수|이용", a.get("title") or "")
                            any_law = any(re.search(r"「[^」]+(법|법률|령|규칙)」", x.get("text") or "") and not re.search(r"「대구광역시", x.get("text") or "") for x in arts)
                            fee = re.search(r"요금|사용료|견인료|보관료|수수료|관람료", hitp)
                            if re.search(r"위임된\s*사항|위임에\s*따라|위임한\s*사항|「[^」]+(법|법률|령)」", first) or facility or any_law or fee:
                                add(d, a, "content_rule_ref", ev={"rule": rk, "rname": R["name"] + "(자치법규는 위임 근거를 밝힘)", "level": "참고", "ctx": hitp.strip()[:400],
                                                                  "basis": R.get("basis", ""), "prec": R.get("prec", []), "rwhy": R["why"], "rhow": "공공시설 이용 규칙이면 시설 관리 범위인지, 근거 법률이 있으면 그 법률이 이 의무·제한까지 맡겼는지 확인한다."})
                                continue
                        if hitp and R.get("strong"):
                            # 강한 신호(의무·법정 위원회)가 아니면 숨김 신호로
                            strong = any(re.search(x, hitp) for x in R["strong"]) or bool(R.get("strong_scope") and re.search(R["strong_scope"], d["name"] + " " + (a.get("title") or "")))
                            if not strong:
                                add(d, a, "content_rule_ref", ev={"rule": rk, "rname": R["name"], "level": "참고", "ctx": hitp.strip()[:400],
                                                                  "basis": R.get("basis", ""), "prec": R.get("prec", []), "rwhy": R["why"], "rhow": R["how"]})
                                continue
                        if hitp:
                            add(d, a, "content_rule", ev={"rule": rk, "rname": R["name"], "level": R["level"], "ctx": hitp.strip()[:400],
                                                          "basis": R.get("basis", ""), "prec": R.get("prec", []), "rwhy": R["why"], "rhow": R["how"]})
                # 상위법령 위반 소지 ① 조례로 형벌(징역·벌금)을 정함 — 지방자치법 제28조제1항 단서: 벌칙은 법률의 위임이 있어야 한다
                if not re.search(r"삭\s*제", raw[:40]):
                    mp = re.search(r"\d+\s*년\s*이하의\s*징역|[\d,]+\s*(?:억|천만|백만|만)?\s*원\s*이하의\s*벌금|(?:징역|벌금)에\s*처한다", raw)
                    if mp:
                        add(d, a, "penal_clause", ev={"ctx": raw[max(0, mp.start() - 80): mp.end() + 40], "word": mp.group(0),
                                                      "law_cited": bool(re.search(r"「[^」]+」", raw))})
                # ③ 주민등록번호 처리 — 「개인정보 보호법」 제24조의2: 법률·대통령령 등에 구체적 근거가 있을 때만 처리할 수 있다
                if "주민등록번호" in raw and not re.search(r"주민등록번호[^.。]{0,30}(제외|빼고|생략|뒷자리|앞자리|생년월일로)", raw):
                    mr = re.search(r"주민등록번호", raw)
                    add(d, a, "rrn_collect", ev={"ctx": raw[max(0, mr.start() - 80): mr.end() + 60], "law_cited": bool(re.search(r"「[^」]+」", raw))})
                # ② 조례 과태료 상한 — 지방자치법 제34조제1항: 조례 위반 과태료는 1천만원 이하. 법률 인용이 없는 조문만
                if "과태료" in raw and not re.search(r"「[^」]+」|(?<![가-힣])(법|영)\s*제\s*\d+\s*조", raw):
                    for mf in re.finditer(r"([\d,]+)\s*(억|천만|백만|만)?\s*원\s*이하의\s*과태료", raw):
                        won = int(mf.group(1).replace(",", "") or 0) * {"억": 10**8, "천만": 10**7, "백만": 10**6, "만": 10**4, None: 1}[mf.group(2)]
                        if won > 10**7:
                            add(d, a, "fine_over_cap", ev={"ctx": raw[max(0, mf.start() - 80): mf.end() + 20], "won": won})
                            break
            for src in [*(a.get("text") or "" for a in arts), *(x.get("text") or "" for x in d.get("addenda") or [])]:
                for mm in re.finditer(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*까지\s*(?:그\s*)?(효력을\s*가진다|유효하다|효력이\s*있다)", src):
                    end = f"{int(mm.group(1)):04d}{int(mm.group(2)):02d}{int(mm.group(3)):02d}"
                    # 유효기간이 지난 뒤에 공포된 개정(부칙)이 있으면 연장·정리했을 수 있어 넣지 않는다(옛 개정 부칙의 유효기간 오탐 방지)
                    later_amend = any((x.get("date") or "") > end for x in d.get("addenda") or []) or (d.get("prom") or "") > end
                    if end < TODAY and not later_amend:
                        add(d, None, "sunset", ev={"end": ymd(end), "ctx": src[max(0, mm.start() - 60): mm.end() + 10]})
                        break
    # 역색인 정리
    for lr in lawrefs.values():
        lr["refs"] = sorted(lr["refs"].values(), key=lambda e: (e["org"], e["oname"]))
        for e in lr["refs"]:
            e["arts"].sort(key=art_sort)
    # ── 정비 사유·정비 방향(규칙 문장). 판정이 아니라 검토할 내용을 적는다 ──
    names_by_org: dict[str, list] = {}
    for x in lst["items"]:
        names_by_org.setdefault(x["org"], []).append(x["name"])
    import difflib
    def cite(ev):
        art = ev.get("art") or ""
        return f"「{ev.get('law','')}」" + (f" 제{art.replace('의', '조의')}" + ("" if "의" in art else "조") if art else "")
    def moved_to(law_id, old_title):
        """공포 당시 조문 제목과 같은 제목의 현행 조문(번호가 옮겨 간 곳 후보)"""
        A = arts_of(law_id) or {}
        tn = lambda x: norm_name(re.sub(r"<[^>]*>|\[[^\]]*\]", "", x or ""))
        arts_ = (A.get("arts") or {}).items()
        hit = [k for k, v in arts_ if old_title and tn(v.get("t")) == tn(old_title)]
        if hit or not old_title:
            return hit, "같은 제목"
        # 같은 제목이 없으면 비슷한 제목(글자 비율 0.6 이상, 가장 가까운 것) — '동물보호센터의 설치·지정 등' → '동물보호센터의 설치 등'
        best = sorted(((difflib.SequenceMatcher(None, tn(old_title), tn(v.get("t"))).ratio(), k) for k, v in arts_ if v.get("t")), reverse=True)[:1]
        return ([best[0][1]], "비슷한 제목") if best and best[0][0] >= 0.6 else ([], "")
    law_id_by_name = {k: v.get("law_id") or (v.get("now") or {}).get("law_id") for k, v in laws.items()}
    for c in cands:
        ev, sg = c.get("ev") or {}, c["sig"]
        why = how = ""
        if sg == "law_renamed":
            why = f"{cite(ev)}의 법령 이름이 「{ev['now']}」로 바뀌었다(국가법령정보센터 연혁, 같은 법령ID)."
            how = f"인용 이름을 「{ev['now']}」로 고친다. 이름을 바꾸며 조문 번호가 달라졌을 수 있으니 인용한 조 번호도 함께 확인한다."
        elif sg == "law_not_current":
            last = ev.get("hist", [[]])[0] if ev.get("hist") else []
            why = f"{cite(ev)}이 현행 법령 목록에 없고 연혁에만 있다" + (f"(마지막 판 시행 {last[6]})" if len(last) > 6 and last[6] else "") + " — 폐지되었거나 다른 법령으로 통합된 것으로 보인다."
            alt = ev.get("cands") or []
            how = ("근거를 후속 법령으로 바꾼다" + (f"(검색에 나온 현행 법령: {', '.join('「'+x+'」' for x in alt[:3])} — 같은 내용인지 연혁에서 확인)" if alt else "") +
                   ". 그 법령이 이 자치법규의 제정 근거(제1조 목적)이고 대체 근거가 없으면 해당 규정 삭제나 자치법규 폐지를 검토한다.")
        elif sg == "article_missing":
            why = f"{cite(ev)}이 현행 「{ev.get('now', ev.get('law'))}」에 없다(조 번호 오기이거나 조문이 옮겨 갔다)."
            how = "원래 가리키려던 조문을 현행 법령에서 찾아 조 번호를 고친다. '제○조의1' 같은 표기는 '제○조'로 바로잡는다."
        elif sg == "article_deleted":
            why = f"{cite(ev)}이 현행 법령에서 삭제되었다({ev.get('atext', '')[:40]})."
            how = "삭제 사유와 내용이 옮겨 간 조문을 법령 연혁·신구조문에서 찾아 인용을 바꾸고, 옮겨 간 곳이 없으면 그 인용에 기댄 규정을 삭제하거나 고친다."
        elif sg == "article_renumber":
            lid = law_id_by_name.get(norm_name(ev.get("law", "")))
            mv, how_found = moved_to(lid, ev.get("old_title")) if lid else ([], "")
            A_ = arts_of(lid) if lid else None
            mvt = [(A_ or {}).get("arts", {}).get(m, {}).get("t", "") for m in mv]
            why = (f"근거 법령이 전부개정(또는 조문 이동)되어 {cite(ev)}의 내용이 바뀌었다 — 자치법규 공포 당시 이 조는 '{ev.get('old_title')}'였고 "
                   f"지금 제{ev['art']}조는 '{ev.get('atitle')}'이다.")
            how = (f"'{ev.get('old_title')}' 조문은 지금 " + ", ".join(f"제{m.replace('의', '조의')}{'' if '의' in m else '조'}({t})" for m, t in zip(mv[:2], mvt[:2])) +
                   f"로 보이니({how_found}) 인용 번호를 고친다(신구조문으로 확인)."
                   if mv else f"'{ev.get('old_title')}' 내용이 지금 몇 조에 있는지 신구조문에서 찾아 인용 번호를 고친다.")
            if mv:
                ev["moved_to"] = mv[:2]
        elif sg == "local_ref_missing":
            # 같은 지자체 자치법규를 먼저 찾고(인용 이름에 '대구광역시'만 있어도 구·군 조례를 가리키는 일이 많다), 없을 때만 대구시 것
            q0 = ev.get("law", "")
            own = names_by_org.get(c["org"], [])
            close = close_names(q0, own) if c["org"] != "daegu" and not re.match(r"^대구광역시\s+(?!중구|동구|서구|남구|북구|수성구|달서구|달성군|군위군)\S", q0) else []
            close = close or close_names(q0, names_by_org.get("daegu", []) if c["org"] != "daegu" else own)
            why = f"인용한 자치법규 「{ev.get('law')}」이 대구시·9개 구군 현행 자치법규 목록에 그 이름으로 없다(이름이 바뀌었거나 폐지)."
            how = (f"현행 이름으로 고친다 — 이름이 비슷한 현행 자치법규: {', '.join('「'+x+'」' for x in close)}." if close else "인용한 자치법규의 연혁을 확인해 현행 이름으로 고치거나, 폐지되었으면 인용을 삭제한다.")
            if close:
                ev["close"] = close
        elif sg == "ministry_outdated":
            why = f"'{ev['old']}'은 현행 「정부조직법」에 없는 옛 중앙행정기관 이름이다."
            how = f"'{ev['now']}'(현행 「정부조직법」)으로 고친다. 연혁을 서술하는 문장이면 그대로 둔다."
        elif sg == "sunset":
            why = f"유효기간 {ev['end']}이 지났는데 규정이 현행 자치법규에 남아 있다."
            how = "효력이 끝난 규정(또는 자치법규)을 삭제하거나, 계속 필요하면 유효기간을 연장하는 개정을 검토한다."
        elif sg == "term_outdated":
            why = f"'{ev['old']}'은 「{ev['basis']}」에서 '{ev['new']}'(으)로 바뀐 용어다."
            how = f"문맥을 보고 '{ev['new']}'(으)로 고친다."
        elif sg == "penal_clause":
            why = f"조례 조문이 형벌({ev['word']})을 정하고 있다 — 「지방자치법」 제28조제1항 단서는 벌칙을 정할 때 법률의 위임을 요구하고, 같은 법 제34조는 조례 위반에 과태료만 정할 수 있게 한다."
            how = "법률의 위임 조문을 확인한다. 위임이 없으면 형벌 규정을 삭제하거나 과태료(1천만원 이하)로 바꾸는 것을 검토한다. 법률의 벌칙을 안내만 하는 문장이면 그대로 둔다."
        elif sg in ("content_rule", "content_rule_ref"):
            pr = ev.get("prec") or []
            refs_ = "; ".join(f"{x.get('no') or ('법령해석 ' + x.get('expc', ''))}({x.get('org', '')}): {x.get('concl', '')}" for x in pr[:2])
            why = f"[{ev['level']}] {ev['rwhy']} 근거: {ev['basis']}." + (f" 법제처 사례 — {refs_}." if refs_ else "")
            if ev["level"] == "규제 개선 권고":
                c["cat_override"] = "규제 개선"
            how = ev["rhow"]
        elif sg == "rrn_collect":
            why = "조문이 주민등록번호를 다룬다 — 「개인정보 보호법」 제24조의2는 법률·대통령령·국회규칙 등이 구체적으로 요구·허용한 경우 등에만 주민등록번호 처리를 허용하고, 조례만으로는 근거가 되지 않는다."
            how = "주민등록번호를 요구하는 법령 근거가 있는지 확인하고, 없으면 생년월일 등으로 바꾸거나 삭제한다(서식 포함)."
        elif sg == "fine_over_cap":
            why = f"조례 과태료 {ev['won']//10**4:,}만원이 「지방자치법」 제34조제1항의 상한(1천만원)을 넘고, 조문에 다른 법률 근거 인용이 없다."
            how = "개별 법률이 더 높은 과태료를 조례에 위임했는지 확인하고, 없으면 1천만원 이하로 고친다."
        elif sg in ("expc_daegu", "expc_related"):
            x = (ev.get("expc") or [{}])[0]
            why = f"이 조문이 인용한 {cite(ev)}에 대해 법제처 법령해석({x.get('no','')}, {x.get('d','')})이 있다" + (" — 자치법규 최종 공포 뒤의 회답이다." if ev.get("after") else ".")
            how = "회답 취지가 조문에 반영되어 있는지 확인하고, 다르면 회답에 맞게 고친다."
        elif sg in ("opin_daegu", "opin_same", "opin_article", "opin_conflict"):
            x = (ev.get("expc") or [{}])[0]
            who = "이 자치법규" if sg == "opin_daegu" else ("같은 이름 조례(" + x.get("qorg", "") + ")" if sg in ("opin_same", "opin_conflict") else "같은 쟁점 조문")
            why = f"{who}에 대해 법제처 자치법규 의견제시({x.get('no','')}, {x.get('d','')})가 있다" + (f": '{ev.get('concl','')[:120]}'" if ev.get("concl") else "") + "."
            how = ("같은 규정이 이 자치법규에도 있는지 찾아, 있으면 법제처 의견 취지에 맞게 고치거나 삭제한다." if sg == "opin_conflict"
                   else "의견 취지가 이 자치법규 조문에 반영되어 있는지 확인한다.")
        elif sg in ("name_unmatched", "admrul_missing"):
            why = f"인용한 {cite(ev)}이 현행·연혁 목록에 그 이름으로 없다(띄어쓰기·약칭·오기 또는 폐지)."
            how = "정확한 현행 이름으로 고친다" + (f"(비슷한 현행: {', '.join('「'+str(x)+'」' for x in (ev.get('cands') or [])[:2])})" if ev.get("cands") else "") + "."
        elif sg == "article_changed":
            ch = (ev.get("changes") or [{}])[-1]
            why = f"{cite(ev)}이 자치법규 최종 공포 뒤 바뀌었다({ch.get('d','')} {ch.get('why','')})."
            how = "신구조문을 보고 위임 범위·기준·용어가 바뀌었으면 조례를 맞춘다."
        elif sg == "gunwi_gb":
            why, how = "군위군 편입(2023-07-01) 전 경상북도 표기가 남아 있다.", "대구광역시·시장 등으로 고칠 대상인지 문맥을 확인한다."
        elif sg == "penalty_basis":
            why, how = "과태료 조문에 법률 근거 인용이 없다.", "부과 근거 법률(「지방자치법」 제34조 또는 개별 법률)을 조문에 밝힌다."
        c["why"], c["how"] = why, how
        # 정비 성격(분류): 상위법령 개정·폐지 / 상위법령 위반 소지 / 법제처 의견 / 자구 정비
        c["cat"] = c.pop("cat_override", None) or ("위반 소지" if sg in ("penal_clause", "fine_over_cap", "opin_conflict", "penalty_basis", "rrn_collect", "content_rule")
                    else "법제처 의견" if sg.startswith(("expc", "opin"))
                    else "상위법령 개정·폐지" if sg in ("law_renamed", "law_not_current", "article_deleted", "article_renumber", "article_changed", "article_missing")
                    else "자구·기한 정비")

    # 대구 지자체가 질의한 해석례(자치법규 관련 여부와 무관) + 같은 지자체에서 같은 조문을 인용한 자치법규 수
    dq = []
    for iid, e in expc.items():
        if not e.get("dg"):
            continue
        hits = sorted(ex_ord.get(iid, set()))
        dq.append({**ex_card(iid), "q": e.get("q", "")[:300], "local": e.get("local", False), "refs": [f"「{raw}」" + (f" 제{art}조" if art and "의" not in art else (f" 제{art.replace('의', '조의')}" if art else "")) for _n, raw, art in e.get("refs", [])][:6], "ordins": hits[:30]})
    for sq, e in opin.items():
        if not e.get("dg"):
            continue
        dq.append({**op_card(sq), "q": e.get("q", "")[:300], "local": True, "targets": e.get("targets", []),
                   "refs": [f"「{raw}」" + (f" 제{art}조" if art and "의" not in art else (f" 제{art.replace('의', '조의')}" if art else "")) for _n, raw, art in e.get("refs", [])][:6],
                   "ordins": sorted(op_ord.get(sq, set()))[:30]})
    dq.sort(key=lambda x: x["d"], reverse=True)
    (D / "expc_daegu.json").write_text(json.dumps({"built": ymd(TODAY), "items": dq}, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    # 요약
    orgs = [o["key"] for o in CFG["orgs"]]
    by = {s: {k: 0 for k in orgs} for s in SIG}
    for c in cands:
        by[c["sig"]][c["org"]] += 1
    st = {}
    for L in laws.values():
        st[L.get("status")] = st.get(L.get("status"), 0) + 1
    summary = {"fetched": lst.get("fetched", ""), "built": ymd(TODAY), "orgs": [{"key": k, "name": org_name[k], "count": ordin_count.get(k, 0), "listed": lst["counts"].get(k, 0)} for k in orgs],
               "refs": n_ref, "refs_resolved": n_ref_ok, "refs_unknown": n_unres, "law_status": st, "laws_cited": len(laws),
               "by_signal": by, "total": len(cands), "expc_held": len(expc), "expc_linked": sum(1 for v in ex_by.values() for _ in v), "expc_daegu": len(dq), "opin_held": len(opin)}
    (D / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with gzip.open(D / "candidates.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"built": ymd(TODAY), "items": cands}, f, ensure_ascii=False, separators=(",", ":"))
    with gzip.open(D / "lawrefs.json.gz", "wt", encoding="utf-8") as f:
        json.dump(lawrefs, f, ensure_ascii=False, separators=(",", ":"))
    # 표본(신호별 30건, 고정 씨앗)
    rnd = random.Random(20261008)
    (D / "eval").mkdir(exist_ok=True)
    with open(D / "eval" / "sample.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["후보ID", "신호", "지자체", "자치법규", "조문", "근거(요약)", "세션 판단", "운영자 판단(맞음/아님/모름)", "메모"])
        for s in SIG:
            pool = [c for c in cands if c["sig"] == s]
            for c in rnd.sample(pool, min(30, len(pool))):
                ev = c.get("ev", {})
                w.writerow([c["id"], SIG[s]["name"], org_name[c["org"]], c["oname"], c["no"], json.dumps(ev, ensure_ascii=False)[:400], "", "", ""])
    print(f"후보 {len(cands)} · 인용 {n_ref}(법령 풀이 {n_ref_ok}, 미조회 {n_unres}) · 법령 상태 {st}")
    for s in SIG:
        print(f"  {s:18s} {sum(by[s].values()):6d}  " + " ".join(f"{org_name[k]}{by[s][k]}" for k in orgs))


if __name__ == "__main__":
    main()
