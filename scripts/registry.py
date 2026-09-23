#!/usr/bin/env python3
"""기업 사전 모집단 통합 — 팩토리온 ∪ 국민연금 (∪ 이후 단지 명단·벤처확인) → scripts/data/companies_registry.json

키: 사업자등록번호는 국민연금 파일이 앞 6자리만 주고 팩토리온에는 아예 없어 유일키가 못 된다.
    그래서 key = "k" + sha1(정규화 회사명 + "|" + 구·군)[:12]. 같은 회사가 같은 구·군에 두 출처로 나타나면 한 레코드에
    source 만 쌓인다(중복 생성 없음). 사업자번호(6자리·10자리)는 속성으로만 둔다.
정규화: 주식회사/(주)/㈜/(유)/공백/괄호 제거, 영문 소문자.

레코드
  key, name, district, emd, source[factoryon|nps|...], factoryon_id(있으면 — 기존 /companies/<id>/ 주소 유지용),
  sector_code, sector, sector_group, product, address(팩토리온 공장주소; 국민연금만 있으면 읍면동 주소),
  complex, workers_band(팩토리온), subscribers(국민연금 가입자수), corp_type, bizr6, zone_hint, as_of
팩토리온에서 온 회사만 공장 정보(단지명·공장주소·업종 상세)를 갖는다. 국민연금만 있는 회사는 업종·가입자수·읍면동까지.

사용: python3 scripts/registry.py            # 통합 파일 생성 + 통계
      python3 scripts/registry.py --stats    # 통계만
"""
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scripts" / "data"
FACTORYON = DATA / "dalseong_companies.csv"
NPS_FILES = sorted((DATA / "sources").glob("nps_20*.json"))
NPS = NPS_FILES[-1] if NPS_FILES else None   # 가장 최근 월 파일
OUT = DATA / "companies_registry.json"
STATS_ONLY = "--stats" in sys.argv

# 개인 성명으로 보이는 공장명 제외 규칙(src/lib/csv.ts looksLikePersonName 과 같은 취지, 보수적으로)
SURNAMES = set("김이박최정강조윤장임한오서신권황안송전홍유고문양손배백허남심노하곽성차주우구민류나진지엄채원천방공현함변염여추도소석선설마길연위표명기반라왕금옥육인맹제모탁국어은편용예봉사부")
LOAN = set("스카캠밀드프텍코컴넷폴랩센젠맥팩플크트북팜닷샵몰링잉엔앤니벤토룩엘벡온샘디홈들촌람")
SUFFIX = ["산업", "공업", "기업", "테크", "정밀", "섬유", "식품", "상사", "상회", "공장", "제작소", "기계", "화학", "전자", "금속", "물산", "건설", "시스템", "코리아", "개발", "스틸", "패션", "인쇄", "유통", "에너지", "가공", "제조", "공사", "공방", "기공", "직물", "부동산", "유니온"]


def looks_like_person(name: str) -> bool:
    n = name.strip()
    if any(s in n for s in SUFFIX) or n.endswith("사"):
        return False
    if re.fullmatch(r"[가-힣]{3}", n):
        return n[0] in SURNAMES and not (set(n[1:]) & LOAN)
    return False


def norm(s: str) -> str:
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사|유한책임회사|\(사\)|\(재\)|\(합\)|합자회사|\s", "", s or "")
    s = re.sub(r"\([^)]*\)", "", s)
    return s.lower()


def key_of(name: str, district: str) -> str:
    return "k" + hashlib.sha1(f"{norm(name)}|{district}".encode()).hexdigest()[:12]


def main() -> None:
    reg: dict[str, dict] = {}
    # 1) 팩토리온
    with FACTORYON.open(encoding="utf-8-sig", newline="") as fh:
        fac = list(csv.DictReader(fh))
    skipped_person = 0
    for r in fac:
        if looks_like_person(r["name"]):
            skipped_person += 1
            continue
        k = key_of(r["name"], r["district"])
        rec = reg.get(k)
        if rec is None:
            rec = reg[k] = {"key": k, "name": r["name"], "district": r["district"], "emd": r.get("eupmyeon", ""), "source": [],
                            "factoryon_id": r["id"], "sector_code": r["sector_code"], "sector": r["sector"], "sector_group": r["sector_group"],
                            "product": r["product"], "address": r["address"], "complex": r["complex"], "workers_band": r["workers_band"],
                            "as_of": r["as_of"]}
        else:   # 같은 회사가 다른 단지에도 → 공장 주소·단지를 이어 붙이고 id 는 첫 것을 유지
            if r["address"] and r["address"] not in rec["address"]:
                rec["address"] = rec["address"] + " / " + r["address"]
            if r["complex"] and r["complex"] not in rec["complex"]:
                rec["complex"] = rec["complex"] + " / " + r["complex"]
            rec.setdefault("factoryon_ids", [rec["factoryon_id"]]).append(r["id"])
        if "factoryon" not in rec["source"]:
            rec["source"].append("factoryon")
    n_fac = len(reg)
    # 2) 국민연금
    n_nps = n_new = 0
    if NPS is not None and NPS.exists():
        nps = json.loads(NPS.read_text(encoding="utf-8"))["rows"]
        for r in nps:
            n_nps += 1
            k = key_of(r["name"], r["district"])
            rec = reg.get(k)
            if rec is None:
                n_new += 1
                rec = reg[k] = {"key": k, "name": r["name"], "district": r["district"], "emd": r["emd"], "source": [],
                                "sector_code": r["sector_code"], "sector": r["sector"], "sector_group": "", "product": "",
                                "address": r["address"], "complex": "", "workers_band": "", "as_of": r["collected"][:7]}
            for f in ("bizr6", "corp_type", "subscribers", "zone_hint"):
                if r.get(f) not in (None, ""):
                    rec[f] = r[f]
            if not rec.get("sector") and r["sector"]:
                rec["sector"], rec["sector_code"] = r["sector"], r["sector_code"]
            if "nps" not in rec["source"]:
                rec["source"].append("nps")
    both = sum(1 for v in reg.values() if "factoryon" in v["source"] and "nps" in v["source"])
    only_nps = sum(1 for v in reg.values() if v["source"] == ["nps"])
    zones = Counter(v.get("zone_hint", "") for v in reg.values() if v.get("zone_hint"))
    print(f"[registry] 팩토리온 {len(fac):,}행 → {n_fac:,}개 (성명 제외 {skipped_person}) · 국민연금 {n_nps:,}건 중 신규 {n_new:,} · "
          f"양쪽 모두 {both:,} · 국민연금만 {only_nps:,} · 통합 {len(reg):,}개")
    print("[registry] 동 기준 단지 힌트:", dict(zones))
    if STATS_ONLY:
        return
    OUT.write_text(json.dumps({"as_of": max((v.get("as_of", "") for v in reg.values()), default=""), "count": len(reg),
                               "companies": sorted(reg.values(), key=lambda v: (v["district"], v["name"]))},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[registry] 저장: {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024/1024:.1f} MB)")


if __name__ == "__main__":
    main()
