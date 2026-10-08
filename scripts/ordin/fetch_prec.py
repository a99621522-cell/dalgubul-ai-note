"""조례 관련 대법원 판례 수집(러너 전용: 이 세션은 law.go.kr 차단). 국가법령정보센터 오픈API target=prec, 2026-10-08 실측.

대상(대법원만):
 1. 사건명 검색(search=1) '조례'·'조례안'·'조례무효'·'규칙' — 조례안 재의결 무효확인 등
 2. 본문 검색(search=2) '조례' 중 사건번호에 '추'(지방자치법 기관소송)가 든 것
 3. 법제처 의견제시·법령해석 원문이 인용한 대법원 판결(data/ordinance/opin·expc 에서 사건번호 추출)
본문(lawService target=prec ID)에서 판시사항·판결요지·참조조문·참조판례·주문·당사자(원고·피고 — 기관)·판례내용(앞 12,000자)을 저장한다.
주문으로 결과를 가른다: '효력이 없다'·'무효' → 무효, '기각' → 유효(청구 기각), 그 밖 → 기타.
→ data/ordinance/prec/index.json.gz, summary.json. 새 판례만 받는다.
"""
from __future__ import annotations

import gzip
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch as F  # noqa: E402

OUT = F.OUT / "prec"
CASE = re.compile(r"대법원\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*선고\s*(\d{2,4}[가-힣]{1,3}\d+)")


def clean(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


def search(q: str, sm: int, extra: dict | None = None, cap: int = 3000) -> list[dict]:
    out, page = [], 1
    while True:
        root = F.xml(F.get("lawSearch.do", target="prec", query=q, search=sm, display=100, page=page, **(extra or {})))
        if root is None:
            break
        rows = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("prec")]
        out += rows
        total = int(root.findtext("totalCnt") or 0)
        if not rows or page * 100 >= min(total, cap):
            break
        page += 1
    print(f"  검색 {q!r} search={sm} {extra or ''} → {len(out)}", flush=True)
    return out


def cited_cases() -> set[str]:
    nos = set()
    for sub, fn in (("opin", "index.json.gz"), ("expc", "index.json.gz")):
        p = F.OUT / sub / fn
        if not p.exists():
            continue
        with gzip.open(p, "rt", encoding="utf-8") as f:
            d = json.load(f)
        for v in d.values():
            t = " ".join(str(v.get(k, "")) for k in ("why", "op", "concl", "a", "q"))
            nos.update(m.group(1) for m in CASE.finditer(t))
    return nos


def result_of(order: str) -> str:
    if re.search(r"효력이\s*없|무효임을\s*확인|무효로\s*한다", order):
        return "무효"
    if re.search(r"기각", order):
        return "기각"
    return "기타"


def detail(pid: str) -> dict | None:
    root = F.xml(F.get("lawService.do", timeout=120, target="prec", ID=pid))
    if root is None:
        return None
    g = lambda t: clean(root.findtext(t) or "")  # noqa: E731
    body = g("판례내용")
    order = ""
    m = re.search(r"【\s*주\s*문\s*】(.*?)(【|$)", body, re.S)
    if m:
        order = m.group(1).strip()[:600]
    parties = {k: (re.search(rf"【\s*{k}\s*】\s*([^\n(【]+)", body) or [None, ""])[1].strip() for k in ("원 *고", "피 *고")}
    return {"id": pid, "no": g("사건번호"), "t": g("사건명"), "d": g("선고일자"), "court": g("법원명"), "kind": g("사건종류명"),
            "issue": g("판시사항")[:3000], "gist": g("판결요지")[:4000], "laws": g("참조조문")[:1500], "refs": g("참조판례")[:1500],
            "order": order, "result": result_of(order),
            "plaintiff": parties.get("원 *고", ""), "defendant": parties.get("피 *고", ""), "body": body[:12000]}


def main():
    idx = F.jload(OUT / "index.json.gz", {})
    cand: dict[str, dict] = {}
    for q in ("조례", "조례안", "조례무효", "규칙무효", "조례규칙"):
        for r in search(q, 1):
            cand[r["판례일련번호"]] = r
    for r in search("조례", 2):
        if "추" in r.get("사건번호", ""):
            cand[r["판례일련번호"]] = r
    nos = cited_cases()
    print(f"  법제처 문서 인용 대법원 판결 {len(nos)}", flush=True)
    have = {r.get("사건번호") for r in cand.values()} | {v.get("no") for v in idx.values()}
    for no in sorted(nos - have):
        if F.left() < 1200:
            break
        for r in search(no, 1, {"nb": no}, cap=100):
            if r.get("사건번호", "").replace(" ", "") == no:
                cand[r["판례일련번호"]] = r
    cand = {k: v for k, v in cand.items() if v.get("법원명") == "대법원"}
    todo = [k for k in cand if k not in idx]
    print(f"[prec] 후보 {len(cand)} · 새로 받을 것 {len(todo)} (보유 {len(idx)})", flush=True)
    for i, pid in enumerate(todo, 1):
        if F.left() < 600:
            print("  시간 예산 — 나머지는 다음 실행")
            break
        d = detail(pid)
        if d:
            d["cited"] = d["no"] in nos
            idx[pid] = d
        if i % 100 == 0:
            print(f"  본문 {i}/{len(todo)}", flush=True)
            F.jdump(OUT / "index.json.gz", idx, gz=True)
    F.jdump(OUT / "index.json.gz", idx, gz=True)
    res = {}
    for d in idx.values():
        res[d["result"]] = res.get(d["result"], 0) + 1
    chu = sum(1 for d in idx.values() if "추" in d["no"])
    F.jdump(OUT / "summary.json", {"fetched": F.TODAY, "held": len(idx), "chu": chu, "result": res, "cited_in_moleg": len(nos),
                                   "source": "국가법령정보센터 판례 오픈API(target=prec)"})
    print(f"[prec] 보유 {len(idx)} · 기관소송(추) {chu} · 결과 {res} · 요청 {F.STATS['req']} 실패 {F.STATS['fail']}", flush=True)


if __name__ == "__main__":
    main()
