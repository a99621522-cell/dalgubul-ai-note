"""법제처 회신 쟁점을 현행 법령과 대조하려고 법령 전문(조·항·호·목 글자)을 받는다(러너 전용: 이 세션은 law.go.kr 차단).

config/ordinance_lawtext.yml 의 법령마다 같은 이름으로 시작하는 시행령·시행규칙까지 현행판 전문을 받아
data/ordinance/lawtext/<법령ID>.json.gz({name, kind, prom, eff, units: [[조, 제목, 글자], ...]})와 index.json 으로 둔다.
법령일련번호(mst)가 같으면 다시 받지 않는다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch as F  # noqa: E402
from refs import norm_name  # noqa: E402

OUT = F.ROOT / "data" / "ordinance" / "lawtext"
CFG = yaml.safe_load((F.ROOT / "config" / "ordinance_lawtext.yml").read_text(encoding="utf-8"))["laws"]
SUFFIX = re.compile(r"^(시행령|시행규칙)?$")


def units(root) -> list[list[str]]:
    out = []
    for u in root.iter("조문단위"):
        if F.tx(u, "조문여부") != "조문":
            continue
        no, br = F.tx(u, "조문번호"), F.tx(u, "조문가지번호")
        lab = f"제{no}조" + (f"의{int(br)}" if br and br not in ("0", "00") else "")
        title = F.tx(u, "조문제목")
        for p in u.iter():
            if p.tag in ("조문내용", "항내용", "호내용", "목내용") and (p.text or "").strip():
                out.append([lab, title, re.sub(r"\s+", " ", p.text).strip()])
    return out


def main():
    cur = F.jload(F.ROOT / "data" / "ordinance" / "laws" / "current.json.gz", {}).get("items") or F.current_laws()
    idx = F.jload(OUT / "index.json", {})
    for base in CFG:
        nb = norm_name(base)
        hits = [v for k, v in cur.items() if k.startswith(nb) and SUFFIX.match(k[len(nb):])]
        if not hits:
            print("  현행 목록에 없음:", base, flush=True)
            continue
        for v in hits:
            key = v.get("law_id") or v["mst"]
            if idx.get(key, {}).get("mst") == v["mst"]:
                continue
            root = F.xml(F.get("lawService.do", timeout=120, target="law", MST=v["mst"]))
            if root is None:
                print("  받기 실패:", v["name"], flush=True)
                continue
            us = units(root)
            F.jdump(OUT / f"{key}.json.gz", {"name": v["name"], "kind": v["kind"], "prom": v.get("prom"), "eff": v.get("eff"), "units": us}, gz=True)
            idx[key] = {"name": v["name"], "mst": v["mst"], "prom": v.get("prom"), "eff": v.get("eff"), "n": len(us)}
            print(f"  {v['name']} ({v.get('eff')}) 조문 단위 {len(us)}", flush=True)
    F.jdump(OUT / "index.json", idx)
    print("끝 — 법령", len(idx), "요청", F.STATS["req"], "실패", F.STATS["fail"], flush=True)


if __name__ == "__main__":
    main()
