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
                add(d, None, sig, ev={"base": b, "n": len(use), "ordin_prom": ymd(prom), "after": any((opin[i].get("d") or "") > prom for i in use),
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
                    later = [x for x in h.get("rows", []) if prom < (x.get("d") or "") <= TODAY and x.get("why") != "제정"]   # 시행 예정 개정은 뺀다
                    if not later:
                        continue
                    ren = [x for x in later if re.search(r"전부개정|전문개정|이동", (x.get("why") or "") + (x.get("rev") or ""))]
                    if ren:
                        # 공포 당시 판의 같은 번호 조문 제목과 지금 제목을 비교한다(표본 대조 2026-10-08: 제목 낱말 짐작은 정확도 60% 안팎)
                        before = [x for x in h.get("rows", []) if (x.get("d") or "") <= prom and x.get("mst")]
                        b0 = max(before, key=lambda x: x["d"]) if before else None
                        ot = oldt.get(f"{L['law_id']}|{r['art']}|{b0['mst']}") if b0 else None
                        if ot and ot.get("t") and norm_name(ot["t"]) != norm_name(la.get("t", "")):
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
            for src in [*(a.get("text") or "" for a in arts), *(x.get("text") or "" for x in d.get("addenda") or [])]:
                for mm in re.finditer(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*까지\s*(?:그\s*)?(효력을\s*가진다|유효하다|효력이\s*있다)", src):
                    end = f"{int(mm.group(1)):04d}{int(mm.group(2)):02d}{int(mm.group(3)):02d}"
                    if end < TODAY:
                        add(d, None, "sunset", ev={"end": ymd(end), "ctx": src[max(0, mm.start() - 60): mm.end() + 10]})
                        break
    # 역색인 정리
    for lr in lawrefs.values():
        lr["refs"] = sorted(lr["refs"].values(), key=lambda e: (e["org"], e["oname"]))
        for e in lr["refs"]:
            e["arts"].sort(key=art_sort)
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
