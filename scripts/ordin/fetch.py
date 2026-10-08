"""대구 자치법규 정비 검토 — 수집(러너 전용: 이 세션 환경은 law.go.kr 차단).

단계(앞 단계 캐시를 다음 실행이 이어 쓴다, 시간 예산 BUDGET_MIN 안에서 멈추면 남은 것은 다음 실행):
 1. 목록: lawSearch target=ordin org=6270000(대구 전체 — 구·군·교육청 포함, 지자체기관명으로 거름) → data/ordinance/list.json
 2. 본문: lawService target=ordin MST — 바뀐 것만(일련번호 비교). 전화번호는 저장하지 않는다 → ordin/<org>.json.gz
 3. 인용 법령 이름 풀이: refs.py 로 인용을 뽑아 이름별로 lawSearch target=law(현행) → 없으면 lsHistory(연혁, HTML) · admrul · ordin
    → laws/index.json (status: current | renamed | not_current | admrul | admrul_missing | local | local_missing | unresolved)
 4. 현행 법령 조문 목록: lawService target=law MST → laws/arts/<법령ID>.json.gz (조 번호·제목·삭제·이동, 인용된 조만 글자 400자)
 5. 인용 조문 변경 이력: lawService target=lsJoHstInf ID JO → laws/johist.json.gz (법령 일련번호가 바뀌면 다시)
 6. 「정부조직법」 현행 본문 → laws/gov_org.txt (옛 기관명 신호용)
API 인자·태그는 2026-10-08 실측(docs/ordinance/api.md). 요청은 스레드 4개, 실패는 로그만.
"""
from __future__ import annotations

import gzip
import html
import json
import os
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refs import extract, norm_name  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "ordinance"
CFG = yaml.safe_load((ROOT / "config" / "ordinance.yml").read_text(encoding="utf-8"))
OC = os.environ.get("LAW_OC", "test").strip() or "test"
BASE = "https://www.law.go.kr/DRF"
UA = "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"
TODAY = date.today().isoformat()
T0 = time.time()
BUDGET = float(os.environ.get("BUDGET_MIN", "320")) * 60
WORKERS = int(os.environ.get("WORKERS", "4"))
_local = threading.local()
LOCK = threading.Lock()
STATS = {"req": 0, "fail": 0}


def left() -> float:
    return BUDGET - (time.time() - T0)


def sess() -> requests.Session:
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers["User-Agent"] = UA
    return _local.s


def get(path: str, timeout=60, **p) -> bytes | None:
    p.setdefault("OC", OC)
    p.setdefault("type", "XML")
    for attempt in range(3):
        try:
            r = sess().get(f"{BASE}/{path}", params=p, timeout=timeout)
            with LOCK:
                STATS["req"] += 1
            if r.status_code == 200 and r.content:
                time.sleep(0.25)
                return r.content
            print(f"  HTTP {r.status_code} {path} {p.get('target')} {p.get('query') or p.get('MST') or p.get('ID')}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  실패 {path} {p.get('target')}: {type(e).__name__} {str(e)[:80]}", flush=True)
        time.sleep(2 * (attempt + 1))
    with LOCK:
        STATS["fail"] += 1
    return None


def xml(b: bytes | None) -> ET.Element | None:
    if not b:
        return None
    try:
        return ET.fromstring(b)
    except ET.ParseError as e:
        print("  XML 오류", e, b[:160], flush=True)
        return None


def tx(el, tag) -> str:
    x = el.find(tag) if el is not None else None
    return (x.text or "").strip() if x is not None else ""


def jdump(path: Path, obj, gz=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":") if gz else (",", ": "), indent=None if gz else 1)
    if gz:
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(s)
    else:
        path.write_text(s + "\n", encoding="utf-8")


def jload(path: Path, default):
    if not path.exists():
        return default
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as f:
                return json.load(f)
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print("  캐시 읽기 실패", path, e)
        return default


def pmap(fn, items, label):
    out, n = [], len(items)
    with ThreadPoolExecutor(WORKERS) as ex:
        for i, r in enumerate(ex.map(fn, items), 1):
            out.append(r)
            if i % 200 == 0 or i == n:
                print(f"  {label} {i}/{n} (요청 {STATS['req']}, 실패 {STATS['fail']}, 남은 {left()/60:.0f}분)", flush=True)
    return out


# ───────────────────────── 1. 목록
ORG_OF = {}
for o in CFG["orgs"]:
    for nm in o["names"]:
        ORG_OF[nm] = o["key"]


def fetch_list() -> list[dict]:
    items, page, total = [], 1, None
    while True:
        root = xml(get("lawSearch.do", target="ordin", org="6270000", display=100, page=page))
        if root is None:
            print("  목록 실패 page", page)
            break
        total = int(root.findtext("totalCnt") or 0)
        rows = list(root.iter("law"))
        for it in rows:
            d = {c.tag: (c.text or "").strip() for c in it}
            items.append(d)
        if not rows or page * 100 >= total:
            break
        page += 1
    out = []
    for d in items:
        key = ORG_OF.get(d.get("지자체기관명", ""))
        if not key:
            continue
        out.append({"org": key, "id": d.get("자치법규ID"), "mst": d.get("자치법규일련번호"), "name": d.get("자치법규명"),
                    "kind": d.get("자치법규종류"), "prom": d.get("공포일자"), "prom_no": d.get("공포번호"), "eff": d.get("시행일자"),
                    "rev": d.get("제개정구분명"), "field": d.get("자치법규분야명")})
    others = sorted({d.get("지자체기관명", "") for d in items} - set(ORG_OF))
    print(f"[1] 목록 totalCnt={total} 받은 {len(items)} · 대상 10곳 {len(out)} · 제외 기관 {others}", flush=True)
    return out


# ───────────────────────── 2. 본문
def jo_label(jo: str) -> str:
    """'000100' → '제1조', '000102' → '제1조의2'"""
    if not re.fullmatch(r"\d{6}", jo or ""):
        return jo or ""
    n, b = int(jo[:4]), int(jo[4:])
    return f"제{n}조" + (f"의{b}" if b else "")


def fetch_body(it: dict) -> dict | None:
    if left() < 600:
        return None
    root = xml(get("lawService.do", target="ordin", MST=it["mst"]))
    if root is None:
        return None
    info = root.find("자치법규기본정보")
    arts = []
    for jo in root.iter("조"):
        if tx(jo, "조문여부") not in ("Y", ""):
            continue
        arts.append({"jo": tx(jo, "조문번호"), "no": jo_label(tx(jo, "조문번호")), "title": tx(jo, "조제목"), "text": tx(jo, "조내용")})
    add = []
    b = root.find("부칙")
    if b is not None:
        ds, ns, cs = b.findall("부칙공포일자"), b.findall("부칙공포번호"), b.findall("부칙내용")
        for i, c in enumerate(cs):
            add.append({"date": (ds[i].text or "").strip() if i < len(ds) else "", "no": (ns[i].text or "").strip() if i < len(ns) else "",
                        "text": (c.text or "").strip()})
    annex = [tx(a, "별표제목") for a in root.iter("별표단위") if tx(a, "별표제목")]
    return {**it, "dept": tx(info, "담당부서명"), "articles": arts, "addenda": add, "annex": annex[:30],
            "reason": (root.findtext("제개정이유/제개정이유내용") or "").strip()[:3000]}


# ───────────────────────── 3. 이름 풀이
LOCAL_RE = re.compile(r"(조례(\s*시행규칙)?|^대구.*규칙)$")
ADM_RE = re.compile(r"(고시|훈령|예규|지침|요령|기준|규정|공고|강령)$")
RESOLVE_V = 2   # 풀이 규칙 판 — 바꾸면 모든 이름을 다시 푼다


def law_search(q: str, target="law", display=30) -> list[dict]:
    q2 = q.replace("·", " ").replace("ㆍ", " ")
    root = xml(get("lawSearch.do", target=target, query=q2, display=display))
    if root is None:
        return []
    return [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("law" if target != "admrul" else "admrul")]


def current_laws() -> dict[str, dict]:
    """현행 법령 전체 목록(법률·대통령령·부령 등) → {정규화 이름: 항목}. 짧은 이름(「상법」)이 검색 30건 밖으로 밀리는 문제를 피한다."""
    out, page, total = {}, 1, 0
    while True:
        root = xml(get("lawSearch.do", target="law", display=100, page=page))
        if root is None:
            break
        total = int(root.findtext("totalCnt") or 0)
        rows = list(root.iter("law"))
        for it in rows:
            d = {c.tag: (c.text or "").strip() for c in it}
            if d.get("현행연혁코드", "현행") == "현행":
                out[norm_name(d.get("법령명한글", ""))] = {"law_id": d.get("법령ID"), "mst": d.get("법령일련번호"), "name": d.get("법령명한글"),
                                                          "kind": d.get("법령구분명"), "prom": d.get("공포일자"), "eff": d.get("시행일자"), "ministry": d.get("소관부처명")}
        if not rows or page * 100 >= total:
            break
        page += 1
    print(f"[3] 현행 법령 목록 {len(out)} (totalCnt {total})", flush=True)
    return out


def hist_rows(q: str) -> list[dict]:
    """lsHistory(연혁 목록, HTML 표: 순번·법령명·소관·제개정구분·법령구분·공포번호·공포일·시행일·현행연혁) — 폐지·옛 이름 법령도 나온다."""
    b = get("lawSearch.do", target="lsHistory", query=q.replace("·", " ").replace("ㆍ", " "), display=100, type="HTML")
    if not b:
        return []
    s = b.decode("utf-8", "replace")
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 3:
            continue
        cells = [html.unescape(re.sub(r"<[^>]+>|\s+", " ", t)).strip() for t in tds]
        href = re.search(r"href=\"([^\"]+)\"", tr)
        h = html.unescape(href.group(1)) if href else ""
        rows.append({"cells": cells, "mst": (re.search(r"MST=(\d+)", h) or [None, ""])[1]})
    return rows


def law_id_of(mst: str) -> tuple[str, str]:
    """옛 판 일련번호 → (법령ID, 그 판 이름). 이름이 바뀐 법령은 법령ID 가 그대로다."""
    root = xml(get("lawService.do", timeout=120, target="law", MST=mst))
    info = root.find("기본정보") if root is not None else None
    return (tx(info, "법령ID"), tx(info, "법령명_한글")) if info is not None else ("", "")


def resolve(name: str, daegu_names: set[str], cur: dict[str, dict], cur_by_id: dict[str, dict]) -> dict:
    nn = norm_name(name)
    if LOCAL_RE.search(name):
        if nn in daegu_names:
            return {"status": "local"}
        res = [d for d in law_search(name, "ordin") if norm_name(d.get("자치법규명", "")) == nn]
        if res:
            return {"status": "local_other", "org": res[0].get("지자체기관명", "")}
        return {"status": "local_missing"}
    if nn in cur:
        return {"status": "current", **cur[nn]}
    if ADM_RE.search(name):
        adm = law_search(name, "admrul")
        for d in adm:
            if norm_name(d.get("행정규칙명", "")) == nn:
                return {"status": "admrul", "name": d.get("행정규칙명"), "issuer": d.get("소관부처명"), "eff": d.get("시행일자")}
        if not cur:   # 목록을 못 받았을 때만 아래로
            return {"status": "admrul_missing", "cands": [d.get("행정규칙명") for d in adm[:5]]}
    hist = hist_rows(name)
    exact = [h for h in hist if len(h["cells"]) > 1 and norm_name(h["cells"][1]) == nn]
    res = law_search(name)
    cands = [cur[norm_name(d.get("법령명한글", ""))] for d in res if norm_name(d.get("법령명한글", "")) in cur][:6]
    if exact:
        lid, _ = law_id_of(exact[0]["mst"]) if exact[0]["mst"] else ("", "")
        now = cur_by_id.get(lid)
        out = {"hist": [h["cells"][1:] for h in exact[:10]], "hist_law_id": lid, "cands": cands}
        if now:
            return {"status": "renamed", "now": now, **out}
        return {"status": "not_current", **out}
    if ADM_RE.search(name):
        return {"status": "admrul_missing", "cands": [c["name"] for c in cands]}
    return {"status": "search_only" if cands else "unresolved", "cands": cands}


# ───────────────────────── 4·5. 조문
def art_key(no: str, branch: str) -> str:
    return f"{int(no)}" + (f"의{int(branch)}" if branch and branch not in ("0", "00") else "")


def fetch_arts(args) -> tuple[str, dict | None]:
    law_id, mst, cited = args
    if left() < 900:
        return law_id, None
    root = xml(get("lawService.do", timeout=120, target="law", MST=mst))
    if root is None:
        return law_id, None
    arts = {}
    for u in root.iter("조문단위"):
        if tx(u, "조문여부") != "조문":
            continue
        k = art_key(tx(u, "조문번호") or "0", tx(u, "조문가지번호"))
        body = tx(u, "조문내용")
        full = body + " " + " ".join((p.text or "").strip() for p in u.iter() if p.tag in ("항내용", "호내용", "목내용"))
        d = {"t": tx(u, "조문제목")}
        if re.match(r"^제\s*\d+\s*조(의\s*\d+)?\s*(\([^)]*\))?\s*삭제", body):
            d["del"] = 1
        if tx(u, "조문이동이전"):
            d["mv_from"] = tx(u, "조문이동이전")
        if tx(u, "조문이동이후"):
            d["mv_to"] = tx(u, "조문이동이후")
        if k in cited:
            d["x"] = re.sub(r"\s+", " ", full).strip()[:600]
        arts[k] = d
    info = root.find("기본정보")
    return law_id, {"mst": mst, "name": tx(info, "법령명_한글"), "eff": tx(info, "시행일자"), "prom": tx(info, "공포일자"),
                    "rev": tx(info, "제개정구분"), "arts": arts}


def fetch_johist(args) -> tuple[str, dict | None]:
    key, law_id, jo, mst = args
    if left() < 600:
        return key, None
    root = xml(get("lawService.do", target="lsJoHstInf", ID=law_id, JO=jo))
    if root is None:
        return key, None
    rows = []
    for it in root.iter("law"):
        rows.append({"d": it.findtext("조문정보/조문변경일") or "", "why": it.findtext("조문정보/변경사유") or "",
                     "rev": it.findtext("법령정보/제개정구분명") or "", "prom": it.findtext("법령정보/공포일자") or "",
                     "mst": it.findtext("법령정보/법령일련번호") or ""})
    return key, {"mst": mst, "rows": rows}


def jo_code(art: str) -> str:
    m = re.fullmatch(r"(\d+)(?:의(\d+))?", art)
    return f"{int(m.group(1)):04d}{int(m.group(2) or 0):02d}" if m else ""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"시작 {TODAY} OC={'키' if OC != 'test' else 'test'} 예산 {BUDGET/60:.0f}분 스레드 {WORKERS}", flush=True)
    # 1
    lst = fetch_list()
    if not lst:
        print("목록을 못 받아 멈춤")
        return
    counts = {o["key"]: sum(1 for x in lst if x["org"] == o["key"]) for o in CFG["orgs"]}
    jdump(OUT / "list.json", {"fetched": TODAY, "counts": counts, "items": lst})
    # 2
    by_org = {}
    todo = []
    for o in CFG["orgs"]:
        old = {d["id"]: d for d in jload(OUT / "ordin" / f"{o['key']}.json.gz", {"items": []})["items"]}
        keep = []
        for it in (x for x in lst if x["org"] == o["key"]):
            prev = old.get(it["id"])
            if prev and prev.get("mst") == it["mst"] and prev.get("articles") is not None:
                keep.append({**prev, **it})
            else:
                todo.append(it)
        by_org[o["key"]] = keep
    print(f"[2] 본문 새로 받을 것 {len(todo)} (그대로 {sum(len(v) for v in by_org.values())})", flush=True)
    for d in pmap(fetch_body, todo, "본문"):
        if d:
            by_org[d["org"]].append(d)
    for k, v in by_org.items():
        v.sort(key=lambda d: d["name"])
        jdump(OUT / "ordin" / f"{k}.json.gz", {"fetched": TODAY, "items": v}, gz=True)
    got = sum(len(v) for v in by_org.values())
    print(f"[2] 본문 보유 {got}/{len(lst)}", flush=True)
    # 3
    daegu_names = {norm_name(x["name"]) for x in lst}
    cited: dict[str, set] = {}
    raw_names: dict[str, str] = {}
    for v in by_org.values():
        for d in v:
            for r in extract(d.get("articles") or []):
                nn = norm_name(r["law"])
                raw_names.setdefault(nn, r["law"])
                cited.setdefault(nn, set())
                if r["art"]:
                    cited[nn].add(r["art"])
    idx = jload(OUT / "laws" / "index.json", {"items": {}})
    items = idx["items"]
    # 현행으로 풀린 이름은 일주일에 한 번 다시(이름이 바뀌었을 수 있음), 나머지는 매번
    need = [nn for nn in cited if nn not in items or items[nn].get("checked") != TODAY or items[nn].get("v") != RESOLVE_V]
    curlist = current_laws()
    cur_by_id = {v["law_id"]: v for v in curlist.values()}
    if curlist:
        jdump(OUT / "laws" / "current.json.gz", {"fetched": TODAY, "items": curlist}, gz=True)
    print(f"[3] 인용 법령 이름 {len(cited)} · 이번에 풀이 {len(need)}", flush=True)
    def _res(nn):
        if left() < 1200:
            return nn, None
        return nn, resolve(raw_names[nn], daegu_names, curlist, cur_by_id)
    for nn, r in pmap(_res, need, "이름"):
        if r:
            items[nn] = {"raw": raw_names[nn], "checked": TODAY, "v": RESOLVE_V, **r}
    items = {k: v for k, v in items.items() if k in cited}   # 인용이 사라진 이름(파서 고침 포함)은 뺀다
    for nn in items:
        if nn in cited:
            items[nn]["arts_cited"] = sorted(cited[nn], key=lambda a: [int(x) for x in a.split("의")])
    st = {}
    for nn, d in items.items():
        st[d.get("status")] = st.get(d.get("status"), 0) + 1
    print(f"[3] 상태 {st}", flush=True)
    jdump(OUT / "laws" / "index.json", {"fetched": TODAY, "items": items})
    # 4
    cur = {}
    for nn, d in items.items():
        if d.get("status") == "renamed" and d.get("now", {}).get("law_id"):   # 바뀐 이름의 현행 법령도 조문 대조
            n2 = d["now"]
            cur.setdefault(n2["law_id"], {"mst": n2["mst"], "cited": set()})["cited"] |= set(d.get("arts_cited") or [])
        if d.get("status") == "current" and d.get("law_id"):
            cur.setdefault(d["law_id"], {"mst": d["mst"], "cited": set()})["cited"] |= set(d.get("arts_cited") or [])
    jobs = []
    for lid, c in cur.items():
        old = jload(OUT / "laws" / "arts" / f"{lid}.json.gz", None)
        if old and old.get("mst") == c["mst"] and all("x" in old["arts"].get(a, {"x": 1}) for a in c["cited"]):
            continue
        jobs.append((lid, c["mst"], c["cited"]))
    print(f"[4] 현행 법령 {len(cur)} · 조문 새로 받을 것 {len(jobs)}", flush=True)
    for lid, d in pmap(fetch_arts, jobs, "조문"):
        if d:
            jdump(OUT / "laws" / "arts" / f"{lid}.json.gz", d, gz=True)
    # 5
    jh = jload(OUT / "laws" / "johist.json.gz", {})
    jj = []
    for lid, c in cur.items():
        for a in c["cited"]:
            key = f"{lid}|{a}"
            if key in jh and jh[key].get("mst") == c["mst"]:
                continue
            code = jo_code(a)
            if code:
                jj.append((key, lid, code, c["mst"]))
    print(f"[5] 조문 변경 이력 받을 것 {len(jj)} (보유 {len(jh)})", flush=True)
    for i in range(0, len(jj), 2000):
        if left() < 900:
            print("  시간 예산 — 나머지는 다음 실행")
            break
        for key, d in pmap(fetch_johist, jj[i:i + 2000], "이력"):
            if d:
                jh[key] = d
        jdump(OUT / "laws" / "johist.json.gz", jh, gz=True)
    # 5b. 전부개정·이동 뒤 미개정 후보: 자치법규 공포 당시 판의 조문 제목(조문별 변경 이력이 준 판 일련번호 → eflaw 조문 하나)
    oldt = jload(OUT / "laws" / "old_titles.json.gz", {})
    want = set()
    for v in by_org.values():
        for d in v:
            prom = d.get("prom") or ""
            for r0 in extract(d.get("articles") or []):
                L0 = items.get(norm_name(r0["law"]))
                if not L0 or L0.get("status") not in ("current",) or not r0["art"]:
                    continue
                h = jh.get(f"{L0['law_id']}|{r0['art']}")
                if not h:
                    continue
                rows = h.get("rows", [])
                if not any(prom < (x.get("d") or "") <= TODAY.replace("-", "") and re.search(r"전부개정|전문개정|이동", (x.get("why") or "") + (x.get("rev") or "")) for x in rows):
                    continue
                before = [x for x in rows if (x.get("d") or "") <= prom and x.get("mst")]
                if before:
                    b = max(before, key=lambda x: x["d"])
                    k = f"{L0['law_id']}|{r0['art']}|{b['mst']}"
                    if k not in oldt:
                        want.add((k, b["mst"], jo_code(r0["art"]), b["d"]))
    print(f"[5b] 공포 당시 조문 제목 받을 것 {len(want)} (보유 {len(oldt)})", flush=True)
    def _old(args):
        k, mst, jo, d = args
        if left() < 600:
            return k, None
        root = xml(get("lawService.do", target="eflaw", MST=mst, JO=jo, efYd=d))
        if root is None:
            return k, None
        u = next((x for x in root.iter("조문단위") if tx(x, "조문여부") == "조문"), None)
        if u is None:
            return k, {"t": "", "x": "", "none": 1}
        return k, {"t": tx(u, "조문제목"), "x": re.sub(r"\s+", " ", tx(u, "조문내용"))[:200]}
    for k, d in pmap(_old, sorted(want), "당시 제목"):
        if d is not None:
            oldt[k] = d
    jdump(OUT / "laws" / "old_titles.json.gz", oldt, gz=True)
    # 6
    r = law_search("정부조직법")
    g = next((d for d in r if d.get("법령명한글") == "정부조직법"), None)
    if g:
        root = xml(get("lawService.do", target="law", MST=g["법령일련번호"]))
        if root is not None:
            txt = "\n".join((e.text or "").strip() for e in root.iter() if e.tag in ("조문내용", "항내용", "호내용", "목내용") and (e.text or "").strip())
            (OUT / "laws" / "gov_org.txt").write_text(f"# 정부조직법 MST {g['법령일련번호']} 시행 {g.get('시행일자')} 받은 날 {TODAY}\n" + txt, encoding="utf-8")
    print(f"끝 — 요청 {STATS['req']} 실패 {STATS['fail']} 걸린 {(time.time()-T0)/60:.0f}분", flush=True)


if __name__ == "__main__":
    main()
