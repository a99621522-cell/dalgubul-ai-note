"""현행 법령 전체(법률·대통령령·총리령·부령)에서 '조례' 가 든 항·호를 뽑는다(러너 전용: 이 세션은 law.go.kr 차단).

목적: 상위법령이 '조례로 정한다'고 맡겼는데 대구시·구군에 그 조례(조문)가 없는 곳 찾기(scripts/ordin/unenacted.py 가 읽음).
입력: data/ordinance/laws/current.json.gz(fetch.py 의 현행 법령 목록)
출력: data/ordinance/deleg_all.json.gz — {법령일련번호: {id, name, kind, prom, units: [[조, 제목, 글자], ...]}}
      '조례' 가 없는 법령도 빈 units 로 남겨 다시 받지 않는다(법령일련번호가 바뀌면 다시).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch as F  # noqa: E402

OUT = F.ROOT / "data" / "ordinance" / "deleg_all.json.gz"
KINDS = re.compile(r"^(법률|대통령령|총리령|.+부령)$")


def units(root) -> list[list[str]]:
    out = []
    for u in root.iter("조문단위"):
        if F.tx(u, "조문여부") != "조문":
            continue
        no, br = F.tx(u, "조문번호"), F.tx(u, "조문가지번호")
        lab = f"제{no}조" + (f"의{int(br)}" if br and br not in ("0", "00") else "")
        title = F.tx(u, "조문제목")
        for p in u.iter():
            if p.tag in ("조문내용", "항내용", "호내용", "목내용") and "조례" in (p.text or ""):
                out.append([lab, title, re.sub(r"\s+", " ", p.text).strip()[:700]])
    return out


def one(v: dict):
    if F.left() < 180:
        return v["mst"], None
    root = F.xml(F.get("lawService.do", timeout=120, target="law", MST=v["mst"]))
    if root is None:
        return v["mst"], None
    return v["mst"], {"id": v.get("law_id", ""), "name": v["name"], "kind": v["kind"], "prom": v.get("prom", ""), "units": units(root)}


def main():
    cur = F.jload(F.ROOT / "data" / "ordinance" / "laws" / "current.json.gz", {}).get("items") or {}
    if not cur:
        cur = F.current_laws()
    have = F.jload(OUT, {})
    want = {v["mst"]: v for v in cur.values() if KINDS.match(v["kind"])}
    have = {k: x for k, x in have.items() if k in want}  # 개정되어 일련번호가 바뀐 판은 버린다
    todo = [v for m, v in want.items() if m not in have]
    print(f"현행 법령 {len(want)}건, 받아 둔 것 {len(have)}, 받을 것 {len(todo)}", flush=True)
    step = 400
    for i in range(0, len(todo), step):
        if F.left() < 180:
            break
        for mst, r in F.pmap(one, todo[i:i + step], "법령 전문"):
            if r is not None:
                have[mst] = r
        F.jdump(OUT, have, gz=True)  # 중간 저장(시간이 다 되어도 이어 받기)
    n = sum(1 for x in have.values() if x["units"])
    print(f"완료: {len(have)}/{len(want)}건, '조례' 든 법령 {n}건, 요청 {F.STATS['req']} 실패 {F.STATS['fail']}", flush=True)


if __name__ == "__main__":
    main()
