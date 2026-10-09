"""자치법규 내용 점검 '참고' 후보의 상위법령 위임 근거 찾기(러너 전용: 이 세션은 law.go.kr 차단).

config/ordinance_delegation.yml 의 주제마다 법령(법률·시행령·시행규칙·규정) 현행 전문을 받아
 - '조례' 가 든 항·호(위임 조문 후보)
 - 주제 낱말(kw)이 든 항·호(법령이 직접 정한 의무·금지 — 조례가 그대로 옮긴 것인지 대조용)
를 data/ordinance/delegation/<주제>.json 과 summary.md 로 남긴다. 위임 여부 판정은 사람이 조문을 읽고 한다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch as F  # noqa: E402
from refs import norm_name  # noqa: E402

ROOT = F.ROOT
OUT = ROOT / "data" / "ordinance" / "delegation"
CFG = yaml.safe_load((ROOT / "config" / "ordinance_delegation.yml").read_text(encoding="utf-8"))["topics"]
SUFFIX = re.compile(r"^(시행령|시행규칙)?$")


def units(root) -> list[tuple[str, str, str]]:
    """(조 표시, 조 제목, 항·호 글자) 목록."""
    out = []
    for u in root.iter("조문단위"):
        if F.tx(u, "조문여부") != "조문":
            continue
        no = F.tx(u, "조문번호")
        br = F.tx(u, "조문가지번호")
        lab = f"제{no}조" + (f"의{int(br)}" if br and br not in ("0", "00") else "")
        title = F.tx(u, "조문제목")
        for p in u.iter():
            if p.tag in ("조문내용", "항내용", "호내용", "목내용") and (p.text or "").strip():
                out.append((lab, title, re.sub(r"\s+", " ", p.text).strip()))
    return out


def main():
    cur = F.current_laws()
    OUT.mkdir(parents=True, exist_ok=True)
    cache: dict[str, dict] = {}
    md = ["# 상위법령 위임 근거 조사(자동 추출, 판정 아님)", "",
          "조례 내용 점검 '참고' 후보에 대해 관련 법령 현행 전문에서 '조례' 가 든 항·호와 주제 낱말이 든 항·호를 뽑았다. 출처: 국가법령정보센터 오픈API.", ""]
    for key, t in CFG.items():
        res = {"what": t["what"], "ordin": t.get("ordin", []), "laws": []}
        kw = re.compile(t.get("kw") or "$^")
        for base in t["laws"]:
            nb = norm_name(base)
            hits = sorted([v for k, v in cur.items() if k.startswith(nb) and SUFFIX.match(k[len(nb):])], key=lambda v: len(v["name"]))
            if not hits:
                print(f"  [{key}] 현행 법령 없음: {base}", flush=True)
                res["laws"].append({"name": base, "missing": 1})
                continue
            for v in hits:
                if v["mst"] not in cache:
                    root = F.xml(F.get("lawService.do", timeout=120, target="law", MST=v["mst"]))
                    cache[v["mst"]] = {"u": units(root) if root is not None else None}
                us = cache[v["mst"]]["u"]
                if us is None:
                    res["laws"].append({"name": v["name"], "fail": 1})
                    continue
                deleg = [{"a": a, "t": ti, "x": x[:500]} for a, ti, x in us if "조례" in x]
                kws = [{"a": a, "t": ti, "x": x[:500]} for a, ti, x in us if kw.search(x) and "조례" not in x][:int(t.get("max") or 40)]
                want = set(t.get("arts") or [])  # 조문 통째로(각 호까지) 볼 조 — 위임이 의무인지·요건이 무엇인지 확인용
                full = [{"a": a, "t": ti, "x": x[:700]} for a, ti, x in us if a in want]
                res["laws"].append({"name": v["name"], "kind": v.get("kind"), "prom": v.get("prom"), "eff": v.get("eff"),
                                    "deleg": deleg, "kw": kws, **({"arts": full} if full else {})})
                print(f"  [{key}] {v['name']} 조례 언급 {len(deleg)} · 낱말 {len(kws)}", flush=True)
        F.jdump(OUT / f"{key}.json", res)
        md += [f"## {key} — {t['what']}", ""]
        for L in res["laws"]:
            if L.get("missing") or L.get("fail"):
                md.append(f"- {L['name']}: {'현행 법령 못 찾음' if L.get('missing') else '받기 실패'}")
                continue
            md.append(f"- **{L['name']}** (공포 {L.get('prom')}) — 조례 언급 {len(L['deleg'])}곳")
            for d in L["deleg"]:
                md.append(f"  - {d['a']}({d['t']}) {d['x'][:220]}")
        md.append("")
    (OUT / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"끝 — 요청 {F.STATS['req']} 실패 {F.STATS['fail']}", flush=True)


if __name__ == "__main__":
    main()
