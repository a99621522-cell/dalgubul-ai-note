#!/usr/bin/env python3
"""출처별 명단 → 기업 사전 통합 레지스트리 (scripts/data/companies_registry.json). registry.py 를 잇는 3단계 병합기.

모집단 = 팩토리온 ∪ 국민연금 ∪ 벤처확인 ∪ 대구연구개발특구(입주기업·연구소기업) ∪ 첨복단지
키     = "k" + sha1(정규화 회사명|구·군)[:12]  (사업자등록번호는 국민연금이 앞 6자리만 주고 다른 출처엔 없어 속성으로만)

매칭 우선순위 (기존 레코드에 새 출처를 붙일 때)
  (1) 사업자등록번호 일치 — 지금은 국민연금(6자리)끼리만 가능해 사실상 미사용, 자리만 둔다
  (2) 정규화 회사명 + 같은 구·군            → 같은 키
  (3) 정규화 회사명 + 국민연금 사업장명 일치 → 출처에 구·군이 없거나 (2)가 실패했을 때, 그 이름의 기존 레코드가 딱 하나면 거기에
  어느 것도 안 맞으면 신규. 같은 이름의 기존 레코드가 둘 이상이면 scripts/data/sources/ambiguous.csv 에 남기고 병합하지 않는다.

표시 규칙(권장안): 알파시티는 DIP 명단이 없어 '알파시티 일대'(특구 지식서비스R&D지구 + 국민연금 대흥동)로만 적는다.
첨단기술기업은 실데이터가 없어 다루지 않는다. 대표자·연락처는 어느 출처에서도 저장하지 않는다.

사용: python3 scripts/merge_sources.py                     # 통합 + 요약
      python3 scripts/merge_sources.py --sample 50 --source venture   # 그 출처 50곳의 매칭 표만 (파일 안 씀)
"""
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from sources_common import latest_source, norm

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scripts" / "data"
FACTORYON = DATA / "dalseong_companies.csv"
OUT = DATA / "companies_registry.json"
AMBIG = DATA / "sources" / "ambiguous.csv"


def arg(name: str, default):
    if name in sys.argv:
        i = sys.argv.index(name)
        return type(default)(sys.argv[i + 1]) if i + 1 < len(sys.argv) else default
    return default


SAMPLE = arg("--sample", 0)
SAMPLE_SRC = arg("--source", "")
KEEP_PLANTS = "--keep-plants" in sys.argv
PLANT = re.compile(r"태양광|발전소|발전\s*협동조합|호\s*발전|풍력|연료전지")   # 특구 입주 명단의 발전 SPV — 기업 사전 대상이 아니다

SURNAMES = set("김이박최정강조윤장임한오서신권황안송전홍유고문양손배백허남심노하곽성차주우구민류나진지엄채원천방공현함변염여추도소석선설마길연위표명기반라왕금옥육인맹제모탁국어은편용예봉사부")
LOAN = set("스카캠밀드프텍코컴넷폴랩센젠맥팩플크트북팜닷샵몰링잉엔앤니벤토룩엘벡온샘디홈들촌람")
SUFFIX = ["산업", "공업", "기업", "테크", "정밀", "섬유", "식품", "상사", "상회", "공장", "제작소", "기계", "화학", "전자", "금속", "물산", "건설", "시스템", "코리아", "개발", "스틸", "패션", "인쇄", "유통", "에너지", "가공", "제조", "공사", "공방", "기공", "직물", "부동산", "유니온"]


def looks_like_person(name: str) -> bool:
    n = name.strip()
    if any(s in n for s in SUFFIX) or n.endswith("사"):
        return False
    return bool(re.fullmatch(r"[가-힣]{3}", n)) and n[0] in SURNAMES and not (set(n[1:]) & LOAN)


_QUAL = re.compile(r"\(([^)]*)\)")


def qualifiers(name: str) -> set[str]:
    """괄호 안 한글 한정어 집합. '(주)'·'(구.…)'·영문 별칭은 한정어로 보지 않는다.
    '경북대학교(시간강사)' 처럼 국민연금 사업장명에 붙는 꼬리가 다른 회사에 붙는 걸 막는다."""
    out = set()
    for q in _QUAL.findall(name or ""):
        q = q.strip()
        if not q or q in ("주", "유", "사", "재", "합") or q.startswith(("구.", "舊", "구)")) or not re.search(r"[가-힣]", q):
            continue
        out.add(q)
    return out


def key_of(name: str, district: str) -> str:
    return "k" + hashlib.sha1(f"{norm(name)}|{district}".encode()).hexdigest()[:12]


class Registry:
    def __init__(self) -> None:
        self.reg: dict[str, dict] = {}
        self.by_name: dict[str, set[str]] = {}       # norm(name) → {key}
        self.nps_names: dict[str, set[str]] = {}     # norm(name) → {key}  (국민연금 사업장명 색인, 우선순위 3)
        self.ambiguous: list[dict] = []
        self.stats: dict[str, Counter] = {}

    def _index(self, k: str, rec: dict) -> None:
        self.by_name.setdefault(norm(rec["name"]), set()).add(k)

    def new(self, name: str, district: str, src: str, **fields) -> dict:
        k = key_of(name, district)
        rec = self.reg.get(k)
        if rec is None:
            rec = self.reg[k] = {"key": k, "name": name, "district": district, "emd": "", "source": [], "sector_code": "", "sector": "",
                                 "sector_group": "", "product": "", "address": "", "complex": "", "workers_band": "", "zone_labels": [], "as_of": ""}
            self._index(k, rec)
        self._attach(rec, src, fields)
        return rec

    def _attach(self, rec: dict, src: str, fields: dict) -> None:
        if src not in rec["source"]:
            rec["source"].append(src)
        for f, v in fields.items():
            if v in (None, "", []):
                continue
            if f == "zone_labels":
                for z in v:
                    if z not in rec["zone_labels"]:
                        rec["zone_labels"].append(z)
            elif f in ("sector", "sector_code", "product", "address", "emd") and rec.get(f):
                continue                      # 팩토리온 값이 있으면 덮지 않는다
            else:
                rec[f] = v

    def attach(self, name: str, district: str, src: str, **fields) -> tuple[str, str]:
        """(방법, 붙은 레코드 이름 또는 '신규'/'미확정')."""
        n = norm(name)
        if district:                                            # (2) 이름 + 구·군
            k = key_of(name, district)
            if k in self.reg:
                self._attach(self.reg[k], src, fields)
                return "이름+구군", self.reg[k]["name"]
        cands = set(self.by_name.get(n, set()))                 # (3) 이름 일치 (국민연금 사업장명 포함)
        q_src = qualifiers(name)
        cands = {k for k in cands if not (qualifiers(self.reg[k]["name"]) - q_src)}   # 상대에만 있는 한정어가 있으면 다른 사업장
        if district:
            same = {k for k in cands if self.reg[k]["district"] == district}
            if same:
                cands = same
        if len(cands) == 1:
            k = next(iter(cands))
            self._attach(self.reg[k], src, fields)
            return ("이름+국민연금" if k in self.nps_names.get(n, set()) else "이름"), self.reg[k]["name"]
        if len(cands) > 1:
            self.ambiguous.append({"source": src, "name": name, "district": district,
                                   "candidates": " | ".join(f"{self.reg[k]['name']}({self.reg[k]['district']})" for k in sorted(cands))})
            return "미확정(동명)", ""
        if not district:                                        # 구·군도 이름 일치도 없으면 구·군 없는 신규
            district = ""
        self.new(name, district, src, **fields)
        return "신규", "신규"


def load_factoryon(R: Registry) -> tuple[int, int]:
    with FACTORYON.open(encoding="utf-8-sig", newline="") as fh:
        fac = list(csv.DictReader(fh))
    skipped = 0
    for r in fac:
        if looks_like_person(r["name"]):
            skipped += 1
            continue
        rec = R.new(r["name"], r["district"], "factoryon", emd=r.get("eupmyeon", ""), factoryon_id=r["id"], sector_code=r["sector_code"],
                    sector=r["sector"], sector_group=r["sector_group"], product=r["product"], address=r["address"], complex=r["complex"],
                    workers_band=r["workers_band"], as_of=r["as_of"])
        if rec.get("factoryon_id") != r["id"]:                  # 같은 회사의 다른 단지 공장
            rec.setdefault("factoryon_ids", [rec["factoryon_id"]])
            if r["id"] not in rec["factoryon_ids"]:
                rec["factoryon_ids"].append(r["id"])
            if r["address"] and r["address"] not in rec["address"]:
                rec["address"] += " / " + r["address"]
            if r["complex"] and r["complex"] not in rec["complex"]:
                rec["complex"] += " / " + r["complex"]
    return len(fac), skipped


def main() -> None:
    R = Registry()
    n_fac, skipped = load_factoryon(R)
    n_fac_keys = len(R.reg)
    # 국민연금 — 구·군이 있으므로 (2)로 바로 붙거나 신규. 사업장명 색인을 만들어 (3)에 쓴다
    nps = latest_source("nps")
    n_nps = new_nps = 0
    if nps:
        for r in nps["rows"]:
            n_nps += 1
            before = len(R.reg)
            zl = ["알파시티 일대"] if r.get("zone_hint") == "알파시티" else ([r["zone_hint"] + " 일대"] if r.get("zone_hint") else [])
            rec = R.new(r["name"], r["district"], "nps", emd=r["emd"], sector_code=r["sector_code"], sector=r["sector"], address=r["address"],
                        bizr6=r.get("bizr6", ""), corp_type=r.get("corp_type", ""), subscribers=r.get("subscribers"),
                        nps_new_month=r.get("new_month"), nps_lost_month=r.get("lost_month"), zone_labels=zl, as_of=nps["meta"]["data_ym"])
            R.nps_names.setdefault(norm(r["name"]), set()).add(rec["key"])
            new_nps += len(R.reg) - before
    # 주소가 없거나 구 단위뿐인 출처들 — attach() 의 우선순위 규칙을 탄다
    per_source: dict[str, Counter] = {}
    samples: dict[str, list] = {}
    for src, fields_of in (
        ("venture", lambda r: dict(sector=r["sector"], product=r["product"], venture_type=r["venture_type"], venture_valid_to=r["valid_to"],
                                   venture_agency=r["agency"], address=r["address"])),
        ("innopolis", lambda r: dict(zone_labels=[r["zone_label"]] if r["is_tenant"] else [], innopolis_zone=r["zone"],
                                     research_company=(r["registered_year"] or "Y") if r["is_research_company"] else "")),
        ("dgmif", lambda r: dict(zone_labels=["첨복단지"], sector=r["sector"], address=r["address"], corp_type=r["corp_type"], dgmif_lot=r["lot"])),
    ):
        data = latest_source(src)
        if not data:
            print(f"[merge] {src}: 원본 파일 없음 — 건너뜀")
            continue
        c = per_source[src] = Counter()
        rows = data["rows"]
        for r in rows:
            if looks_like_person(r["name"]):
                c["성명 제외"] += 1
                continue
            if src == "innopolis" and not KEEP_PLANTS and PLANT.search(r["name"]):
                c["발전소 제외"] += 1
                continue
            method, target = R.attach(r["name"], r.get("district", ""), src, **fields_of(r))
            c[method] += 1
            if SAMPLE and SAMPLE_SRC == src and len(samples.setdefault(src, [])) < SAMPLE:
                samples[src].append((r["name"], r.get("district", ""), method, target))
    # 요약
    both = sum(1 for v in R.reg.values() if "factoryon" in v["source"] and "nps" in v["source"])
    print(f"[merge] 팩토리온 {n_fac:,}행 → {n_fac_keys:,}개(성명 제외 {skipped}) · 국민연금 {n_nps:,}건(신규 {new_nps:,}, 팩토리온과 겹침 {both:,})")
    for src, c in per_source.items():
        print(f"[merge] {src:9}: " + " · ".join(f"{k} {v}" for k, v in c.most_common()))
    print(f"[merge] 통합 {len(R.reg):,}개 · 미확정(동명) {len(R.ambiguous)}건")
    if SAMPLE:
        for src, rows in samples.items():
            print(f"\n=== {src} 샘플 {len(rows)}곳 ===\n{'회사명':26} {'구군':6} {'방법':10} 붙은 레코드")
            for name, d, m, t in rows:
                print(f"{name[:24]:26} {d:6} {m:10} {t[:24]}")
        return
    OUT.write_text(json.dumps({"as_of": max((v.get("as_of", "") or "" for v in R.reg.values()), default=""), "count": len(R.reg),
                               "sources": sorted(per_source.keys() | {"factoryon", "nps"}),
                               "companies": sorted(R.reg.values(), key=lambda v: (v["district"], v["name"]))},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    AMBIG.parent.mkdir(parents=True, exist_ok=True)
    with AMBIG.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["source", "name", "district", "candidates"])
        w.writeheader(); w.writerows(R.ambiguous)
    print(f"[merge] 저장: {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024/1024:.1f} MB), {AMBIG.relative_to(ROOT)} ({len(R.ambiguous)}행)")


if __name__ == "__main__":
    main()
