"""법제처 자치법규 의견제시 사례 수집 — 자치법규 정비 검토용(러너 전용, 이 세션 환경은 moleg.go.kr 연결이 자주 끊김).

출처: 법제처 누리집 > 법제업무정보 > 자치입법 의견제시 > 의견제시 사례 (moleg.go.kr/lawinfo/reglAnalysis/reglAnalysisList.mo,
공개 게시판, robots.txt Allow: /, 2026-10-08 전체 3,909건). 같은 사례가 자치법규정보시스템(ELIS) 실무자 커뮤니티에도 있으나
그쪽은 GPKI 로그인 뒤라 쓰지 않는다(원칙 7).
목록(쪽마다) → 새 caseSeq 만 상세. 요청 사이 1초, 하루 1회(주간 워크플로). 저장: 안건번호·안건명·요청기관·회신일자·질의요지(앞 500자)·
의견(앞 800자)·이유(앞 600자)·대상 자치법규 이름·인용 법령 조문(refs.py). 이유 전문은 저장하지 않고 링크로 본다. 사람 이름·연락처 없음.
"""
from __future__ import annotations

import html
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch as F  # noqa: E402
from fetch_expc import daegu_of  # noqa: E402
from refs import extract, norm_name  # noqa: E402

OUT = F.OUT / "opin"
BASE = "https://www.moleg.go.kr/lawinfo/reglAnalysis"
MID = "a10107020000"
S = requests.Session()
S.headers["User-Agent"] = F.UA


def get(url: str, **params) -> str:
    for attempt in range(4):
        try:
            r = S.get(url, params=params, timeout=60)
            time.sleep(1.0)
            if r.status_code == 200 and r.text:
                return r.text
            print(f"  HTTP {r.status_code} {url} {params.get('currentPage') or params.get('caseSeq')}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  실패 {url}: {type(e).__name__} {str(e)[:80]}", flush=True)
        time.sleep(3 * (attempt + 1))
    return ""


def clean(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


def list_page(page: int, size: int) -> tuple[list[dict], int]:
    t = get(f"{BASE}/reglAnalysisList.mo", mid=MID, currentPage=page, pageCnt=size)
    m = re.search(r"전체\s*([\d,]+)\s*건", re.sub(r"<[^>]+>", " ", t))
    total = int(m.group(1).replace(",", "")) if m else 0
    rows = []
    body = t[t.find("<tbody"): t.find("</tbody>")]
    for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        seq = re.search(r"caseSeq=(\d+)", tr)
        if not seq or len(tds) < 5:
            continue
        rows.append({"seq": seq.group(1), "no": clean(tds[1]), "t": clean(tds[2]), "org": clean(tds[3]), "date": clean(tds[4])})
    return rows, total


def ymd(s: str) -> str:
    m = re.match(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", s or "")
    return f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}" if m else ""


def detail(row: dict) -> dict | None:
    t = get(f"{BASE}/reglAnalysisInfo.mo", mid=MID, caseSeq=row["seq"])
    if not t:
        return None
    m = re.search(r'<div class="tstyle_view[^"]*">\s*<div class="title">(.*?)</div>', t, re.S)
    title = clean(m.group(1)) if m else row["t"]
    head = {clean(k): clean(v) for k, v in re.findall(r"<li[^>]*><strong>(.*?)</strong><span>(.*?)</span></li>", t, re.S)}
    blocks = {}
    for b in re.findall(r'<div class="tb_contents">(.*?)</div>', t, re.S):
        m = re.match(r"\s*<strong>\s*\d+\.\s*(.*?)</strong>(.*)", b, re.S)
        if m:
            blocks[clean(m.group(1))] = clean(m.group(2))
    q, op, why = blocks.get("질의요지", ""), blocks.get("의견", "") or blocks.get("회답", ""), blocks.get("이유", "")
    rel = ""
    k = why.find("【의견제시")
    if k >= 0:
        rel, why = why[k:], why[:k].strip()
    # 대상 자치법규: '○ 자치법규' 아래 겹낫표 이름(없으면 제목의 겹낫표 이름 중 조례·규칙)
    targets = []
    seg = rel.split("○ 관련법령")[0] if rel else ""
    for nm in re.findall(r"「([^」]{2,80}(?:조례|규칙)(?:안)?)」", seg or title):
        nm = re.sub(r"\s+", " ", nm.strip())
        if nm not in targets:
            targets.append(nm)
    def pairs_of(text):
        rs = extract([{"no": "", "text": text}])
        return sorted({(norm_name(r["law"]), r["law"], r["art"]) for r in rs if not re.search(r"(조례|규칙)(안)?$", r["law"]) or "시행규칙" in r["law"]})
    main = pairs_of(f"{title}\n{q}")                       # 쟁점 조문(제목·질의요지) — 자치법규와 잇는 데 쓴다
    allp = pairs_of(f"{op}\n{why}\n{rel.split('○ 관련법령')[-1] if '○ 관련법령' in rel else ''}")
    org = head.get("요청기관", row.get("org", ""))
    # 결론: 이유의 마지막 '따라서·그렇다면·결론적으로' 문장(없으면 이유 끝 400자) — 의견 칸이 '아래 이유를 참고'뿐인 사례가 많다
    concl = ""
    for m in re.finditer(r"(따라서|그렇다면|결론적으로|그러므로)[^\n]{10,}", why):
        concl = m.group(0)
    concl = (concl or why[-400:]).strip()[:600]
    return {"no": head.get("안건번호", row["no"]), "t": title, "concl": concl, "org": org, "d": ymd(head.get("회신일자", row["date"])),
            "q": q[:500], "op": op[:800], "why": why[:600], "targets": targets[:6], "refs": [[n, raw, art] for n, raw, art in main],
            "refs_all": [[n, raw, art] for n, raw, art in allp if (n, raw, art) not in main][:20],
            "dg": daegu_of(org, "")}


def main():
    idx = F.jload(OUT / "index.json.gz", {})
    rows, total = list_page(1, 100)
    size = 100 if len(rows) > 10 else 10
    if size == 10:
        print("  pageCnt=100 이 안 먹어 10건씩 받음", flush=True)
    pages = max(1, -(-total // size))
    allrows = list(rows)
    for p in range(2, pages + 1):
        if F.left() < 900:
            break
        r, _ = list_page(p, size)
        allrows += r
        if r and all(x["seq"] in idx for x in r) and len(idx) >= total - len(allrows):
            break   # 최신순 목록 — 이미 가진 사례만 나오면 그 뒤는 받은 것
    print(f"[opin] 목록 {len(allrows)}행 (전체 {total}건, {size}건씩 {pages}쪽)", flush=True)
    todo = [r for r in allrows if r["seq"] not in idx]
    print(f"[opin] 상세 받을 것 {len(todo)} (보유 {len(idx)})", flush=True)
    for i, r in enumerate(todo, 1):
        if F.left() < 600:
            print("  시간 예산 — 나머지는 다음 실행")
            break
        d = detail(r)
        if d:
            idx[r["seq"]] = d
        if i % 200 == 0:
            print(f"  상세 {i}/{len(todo)}", flush=True)
            F.jdump(OUT / "index.json.gz", idx, gz=True)
    F.jdump(OUT / "index.json.gz", idx, gz=True)
    dg = {}
    for d in idx.values():
        if d.get("dg"):
            dg[d["dg"]] = dg.get(d["dg"], 0) + 1
    F.jdump(OUT / "summary.json", {"fetched": F.TODAY, "listed": total, "held": len(idx), "daegu": dg,
                                   "source": "법제처 자치입법 의견제시 사례 https://www.moleg.go.kr/menu.es?mid=a10107020000"})
    print(f"[opin] 보유 {len(idx)} · 대구 요청 {dg}", flush=True)


if __name__ == "__main__":
    main()
