"""법제처 법령해석례(질의·회답) 수집 — 자치법규 정비 검토용(러너 전용).

lawSearch target=expc 전체 목록(2026-10-08 8,881건) → 본문(lawService target=expc ID: 질의요지·회답·이유)을 한 번만 받아 캐시
→ data/ordinance/expc/index.json.gz. 해석례는 바뀌지 않으므로 새 일련번호만 받는다.
저장: 안건명·안건번호·해석일자·질의기관명·질의요지(앞 500자)·회답(앞 800자)·인용 법령 조문(refs.py)·자치법규 관련 여부·대구 질의 여부.
이유 전문은 저장하지 않는다(링크로 본다). 사람 이름·연락처 없음.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch as F  # noqa: E402  (get·xml·pmap·jdump·jload 재사용)
from refs import extract, norm_name  # noqa: E402

OUT = F.OUT / "expc"
LOCAL = re.compile(r"조례|자치법규|규칙으로\s*정|지방자치단체의\s*규칙")
DAEGU_ORG = re.compile(r"^대구광역시(?!교육청)\s*(중구|동구|서구|남구|북구|수성구|달서구|달성군|군위군)?")
ORG_KEY = {None: "daegu", "중구": "jung", "동구": "dong", "서구": "seo", "남구": "nam", "북구": "buk", "수성구": "suseong",
           "달서구": "dalseo", "달성군": "dalseong", "군위군": "gunwi"}


def daegu_of(qorg: str, title: str) -> str:
    """질의기관명 또는 안건명 머리('대구광역시 수성구 - …')로 대구 지자체 key. 군위군은 편입 전 '경상북도 군위군'·'군위군' 머리도."""
    for s in (qorg or "", (title or "").split(" - ")[0].strip()):
        m = DAEGU_ORG.match(s)
        if m:
            return ORG_KEY.get(m.group(1), "daegu")
        if re.match(r"^(경상북도\s*)?군위군", s):
            return "gunwi"
        if re.match(r"^달성군", s):
            return "dalseong"
    return ""


def fetch_list() -> list[dict]:
    out, page = [], 1
    while True:
        root = F.xml(F.get("lawSearch.do", target="expc", display=100, page=page))
        if root is None:
            print("  목록 실패 page", page)
            break
        total = int(root.findtext("totalCnt") or 0)
        rows = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("expc")]
        out += rows
        if not rows or page * 100 >= total:
            break
        page += 1
    print(f"[expc] 목록 {len(out)}건 (totalCnt {total})", flush=True)
    return out


def body(it: dict):
    iid = it.get("법령해석례일련번호")
    if F.left() < 600:
        return iid, None
    root = F.xml(F.get("lawService.do", target="expc", ID=iid))
    if root is None:
        return iid, None
    g = lambda t: re.sub(r"\s+", " ", (root.findtext(t) or "")).strip()
    title, q, a = g("안건명"), g("질의요지"), g("회답")
    qorg = g("질의기관명") or it.get("질의기관명", "")
    refs = extract([{"no": "", "text": f"{title}\n{q}\n{a}"}])
    pairs = sorted({(norm_name(r["law"]), r["law"], r["art"]) for r in refs})
    return iid, {"t": title, "no": g("안건번호"), "d": g("해석일자") or it.get("회신일자", "").replace(".", ""), "qorg": qorg,
                 "q": q[:500], "a": a[:800], "refs": [[n, raw, art] for n, raw, art in pairs],
                 "local": bool(LOCAL.search(f"{title} {q} {a}")), "dg": daegu_of(qorg, title)}


def main():
    idx = F.jload(OUT / "index.json.gz", {})
    lst = fetch_list()
    todo = [it for it in lst if it.get("법령해석례일련번호") and it["법령해석례일련번호"] not in idx]
    print(f"[expc] 본문 받을 것 {len(todo)} (보유 {len(idx)})", flush=True)
    for i in range(0, len(todo), 1000):
        if F.left() < 900:
            break
        for iid, d in F.pmap(body, todo[i:i + 1000], "해석례"):
            if d:
                idx[iid] = d
        F.jdump(OUT / "index.json.gz", idx, gz=True)
    n_local = sum(1 for d in idx.values() if d.get("local"))
    dg = {}
    for d in idx.values():
        if d.get("dg"):
            dg[d["dg"]] = dg.get(d["dg"], 0) + 1
    F.jdump(OUT / "summary.json", {"fetched": F.TODAY, "listed": len(lst), "held": len(idx), "local": n_local, "daegu": dg})
    print(f"[expc] 보유 {len(idx)} · 자치법규 관련 {n_local} · 대구 질의 {dg} · 요청 {F.STATS['req']} 실패 {F.STATS['fail']}", flush=True)


if __name__ == "__main__":
    main()
