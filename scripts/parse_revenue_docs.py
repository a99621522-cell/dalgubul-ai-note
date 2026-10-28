#!/usr/bin/env python3
"""지자체 세입예산사업명세서(e호조 출력 PDF → pdftotext -layout 글자) → 사업 단위 CSV + 부가세 판정 참고(운영자 지시 2026-10-27 '세입 자료부터 받아서 해').

두 배치를 읽는다 — ① 구·군: 장/관/항/목 → [회계] → <부서> → ○사업(또는 'N.사업') ② 대구시: 실국 → 부서 → 장/관/항/목 → ○사업.
세외수입(장 200)과 보조금(장 500)만 남기고, 목 코드·사업명 낱말로 rules.yml revenue_items 의 key(과세·면세·확인·공급 아님)를 짐작한다 — 참고 표시이지 기관 판단이 아니다.
값은 예산서 그대로(천원). 사람 이름·전화 없음(예산서에는 없다).
사용: python3 scripts/parse_revenue_docs.py <key> <year> <txt> [--acct 일반회계]  → data/vat/revenue/<key>_<year>.csv
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "vat" / "revenue"
CODE = re.compile(r"^\s*(\d{3})(?:-(\d{2}))?\s+(\S.*?)\s{2,}([\d,△\-]+)\s+([\d,△\-]+)(?:\s+([\d,△\-]+))?\s*$")
ACCT = re.compile(r"^\s*\[\s*(.+?)\s*\]")
DEPT = re.compile(r"^\s*<\s*(.+?)\s*>")
ITEM = re.compile(r"^\s*(?:○|◦|\d{1,2}\.)\s*(.*?)\s*$")
SUB = re.compile(r"^\s*[―－\-]\s*")
# 남구 서식(2026-10-27): ◎사업(합계가 같은 줄) 아래 ○세부 — ◎ 가 하나라도 있으면 ◎ 를 사업, ○ 를 세부로 읽는다
ITEM_DIA = re.compile(r"^\s*(?:◎|\d{1,2}\.)\s*(.*?)\s*$")
SUB_DIA = re.compile(r"^\s*[―－\-○◦]\s*")
NUM = re.compile(r"^[\d,]+$")
NAMEAMT = re.compile(r"^\s{0,2}(\S[^\d]*?)\s{2,}([\d,]+)\s+([\d,]+)\s+([\d,△\-]+)\s*$")   # 대구시 배치의 실국·부서 줄(코드 없음)
HEADER_SKIP = re.compile(r"^(장|관|항|실국|부서)\s*:|장ㆍ관ㆍ항ㆍ목|실국ㆍ부서|\(단위|세 ?입 ?예 ?산 ?사 ?업 ?명 ?세 ?서|^\d{4}년도|총\s+계")


def to_k(s: str) -> int:
    s = s.replace(",", "").replace("△", "-")
    try:
        return int(s)
    except ValueError:
        return 0


def tail_amount(line: str) -> int | None:
    toks = line.split()
    if toks and NUM.match(toks[-1]) and (len(toks) < 2 or "원" in toks[-2] or NUM.match(toks[-2]) is None or "원" in line):
        return to_k(toks[-1])
    if toks and NUM.match(toks[-1]) and len(toks) >= 2 and "원" in toks[-2]:
        return to_k(toks[-1])
    return None


# ── 부가세 판정 참고(목 코드 + 사업명 낱말 → rules.yml revenue_items key). 평가 아님. 시설 종류 낱말이 먼저, 그다음 목 코드 기본값 ──
FAC_KW = [
    (r"골프장|파크골프|스키", "golf"),
    (r"수영|헬스|체육|구장|빙상|운동장|풋살|테니스|야구장|축구장|골프연습|배드민턴|국민체육|생활체육|스포츠|체력|볼링|경기장", "sports"),
    (r"휴양림|숙박|야영|캠핑|수련원|유스호스텔|펜션|오토캠핑|치유의숲 ?숙박", "lodging"),
    (r"강습|강좌|수강|교육|체험|프로그램|회비|아카데미|교실|캠프|치유", "program"),
    (r"박물관|미술관|과학관|도서관|전시관|기념관|동물원|식물원|역사관|문학관|자료관|유적|생태원|수목원|테마파크", "culture"),
    (r"공연장|문화회관|문화예술회관|대관|회의실|강당|예술회관|아트센터|야외공연|행사장", "venue"),
    (r"주차", "parking"), (r"상수도|하수도|수돗물|급수", "water"), (r"장례|화장장|화장시설|봉안|추모|장사시설|묘지", "funeral"),
    (r"버스|택시|여객|교통카드", "transit"), (r"계류|선착|마리나|요트", "marina"),
    (r"농기계|기계임대|장비|자전거|임대사업|대여", "equip_rent"),
    (r"노인|장애인|복지관|재가|어린이집|보육|요양|경로|복지센터|돌봄", "welfare")]
MOK_KW = {
    "211": [(r"주택|관사|임대주택", "housing"), (r"사용허가|사용료|점용", "use_permit"), (r"", "lease_bldg")],
    "212": [(r"사용허가|점용|점유", "use_permit"), (r"", "use_permit")],
    "213": [(r"봉투|폐기물|쓰레기|분뇨|반입|소각|매립|재활용", "waste_bag"), (r"보건|진료|예방접종|검사|의료|진단", "medical"), (r"", "admin_fee")],
    "214": [(r"구내식당|직원식당", "canteen"), (r"매점|카페|식당|기념품|판매장|음식|커피|휴게소", "food"), (r"자판기|자동판매", "vending"),
            (r"광고|전광판|승강장", "ad_space"), (r"간행물|도서|지도|책자", "books"),
            (r"농산물|임산물|축산물|묘목|종자|산림|과수|벼|쌀|채소|꽃|예찰|시범포|가축|한우|젖소|버섯", "farm"),
            (r"미생물|퇴비|가공|제품|판매|생산", "goods"), (r"", "goods")],
    "221": [(r"토지|부지|택지|용지|임야|대지", "land_sale"), (r"고철|폐품|불용|불용품|차량|중고|폐자재", "scrap"), (r"건물|건축물|구축물|주택", "bldg_sale"), (r"", "bldg_sale")]}


def guess_key(hang: str, mok_code: str, mok: str, item: str) -> str:
    h = hang[:3]
    if h.startswith("5"):
        return "subsidy_grant"
    if not h.startswith("2") or h in ("215", "216", "222", "223", "224") or h.startswith("23"):
        return "non_supply"
    text = f"{mok} {item}"
    if h == "240":   # 지난연도 수입 — 사업명에 종류가 있으면 그걸로
        for pat, key in FAC_KW:
            if re.search(pat, item):
                return key
        if re.search(r"임대|대부", item):
            return "lease_bldg"
        return "non_supply"
    if h == "211":   # 재산임대수입은 시설 종류와 무관하게 임대(과세)·사용허가(확인)·주택(면세)
        if re.search(r"주택|관사|임대주택", item):
            return "housing"
        return "use_permit" if re.search(r"사용허가|사용료|점용", item) else "lease_bldg"
    if h == "212":
        if mok_code == "212-08" or re.search(r"주차", item):
            return "parking"
        for pat, key in FAC_KW:
            if re.search(pat, item):
                return key
        if mok_code in ("212-01", "212-02", "212-05") or re.search(r"점용|점유|사용허가", item):
            return "use_permit"
        if mok_code == "212-06":
            return "lease_bldg"
        if h == "211" and re.search(r"임대료|대부료|임대수입", item) and not re.search(r"사용허가|사용료", item):
            return "lease_bldg"
    if h == "213" and mok_code == "213-03":
        return "scrap"
    if h == "213" and re.search(r"체험|강습|수강|교육|회비", item):
        return "program"
    if h == "214":
        for pat, key in FAC_KW:
            if re.search(pat, item) and key in ("transit", "welfare", "program", "sports", "lodging", "culture", "venue", "parking", "equip_rent"):
                return key
    for pat, key in MOK_KW.get(h, [(r"", "non_supply")]):
        if pat == "" or re.search(pat, text):
            return key
    return "non_supply"


def parse(text: str, key: str, name: str, year: str, acct_default: str = "일반회계") -> list[dict]:
    ITEM, SUB = (ITEM_DIA, SUB_DIA) if re.search(r"^\s*◎", text, re.M) else (globals()["ITEM"], globals()["SUB"])
    lines = text.splitlines()
    rows: list[dict] = []
    layoutB = "실국ㆍ부서" in text or "실국:" in text
    st = {"jang": "", "gwan": "", "hang": "", "mok": "", "mok_code": "", "acct": acct_default, "dept": "", "bureau": ""}
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        i += 1
        if not ln.strip() or HEADER_SKIP.search(ln):
            continue
        m = CODE.match(ln)
        if m:
            code, mk, nm = m.group(1), m.group(2), m.group(3).strip()
            if mk:
                st["mok_code"], st["mok"] = f"{code}-{mk}", nm
            else:
                n = int(code)
                if n % 100 == 0:
                    st["jang"], st["gwan"], st["hang"], st["mok"], st["mok_code"] = f"{code} {nm}", "", "", "", ""
                elif n % 10 == 0:
                    st["gwan"], st["hang"], st["mok"], st["mok_code"] = f"{code} {nm}", "", "", ""
                else:
                    st["hang"], st["mok"], st["mok_code"] = f"{code} {nm}", "", ""
            continue
        m = ACCT.match(ln)
        if m:
            st["acct"] = m.group(1)
            continue
        m = DEPT.match(ln)
        if m:
            st["dept"] = m.group(1)
            continue
        if layoutB:
            m = NAMEAMT.match(ln)
            if m and not ln.startswith("   "):
                if ln.startswith(" "):
                    st["dept"] = m.group(1).strip()
                else:
                    st["bureau"] = m.group(1).strip()
                continue
        m = ITEM.match(ln)
        if m and not SUB.match(ln):
            body = m.group(1)
            # 이름과 산출·금액 나누기: 두 칸 이상 공백으로
            parts = re.split(r"\s{2,}", body)
            item = parts[0].strip()
            amt = tail_amount(body) if len(parts) > 1 else None
            calc = " ".join(parts[1:-1]).strip() if len(parts) > 2 else (parts[1].strip() if len(parts) == 2 and amt is None else "")
            if amt is None:
                # 줄바꿈된 사업명: 다음 줄이 금액으로 시작
                j = i
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    nx = lines[j].strip()
                    if re.match(r"^[\d,]+원|^[\d,]+\s*\S*\*|^[\d,]+$", nx) and not CODE.match(lines[j]) and not ITEM.match(lines[j]):
                        a2 = tail_amount(nx)
                        if a2 is not None:
                            amt = a2
                            calc = nx.rsplit(None, 1)[0] if len(nx.split()) > 1 else ""
                            i = j + 1
                if amt is None:
                    # 세부(―) 줄 합
                    tot = 0
                    j = i
                    while j < len(lines) and (SUB.match(lines[j]) or not lines[j].strip() or (lines[j].startswith(" ") and re.match(r"^\s+[\d,]+원", lines[j]))):
                        a3 = tail_amount(lines[j].strip())
                        if a3 is not None and lines[j].strip():
                            tot += a3
                        j += 1
                    if tot:
                        amt = tot
                        i = j
            if not st["hang"] or not st["jang"]:
                continue
            jang = st["jang"][:3]
            if jang not in ("200", "500"):
                continue
            k = guess_key(st["hang"], st["mok_code"], st["mok"], item)
            fac = next((key for pat, key in FAC_KW if re.search(pat, item)), "")   # 사업명의 시설 종류 낱말(보조금 행은 면세 시설 관련 보조금 후보를 고르는 데)
            rows.append({"gov": name, "key": key, "year": year, "acct": st["acct"], "jang": st["jang"], "gwan": st["gwan"], "hang": st["hang"],
                         "mok_code": st["mok_code"], "mok": st["mok"], "bureau": st["bureau"], "dept": st["dept"], "item": item, "calc": calc[:80],
                         "amount_k": amt or 0, "vat_key": k, "fac_key": fac})
    return rows


def check(text: str, rows: list[dict]) -> list[dict]:
    """목 줄의 예산액 ↔ 그 목에 붙은 사업 합계(회계 구분 없이) — 다르면 줄바꿈·산출식 때문에 못 읽은 사업이 있다는 뜻. index.json 에 남겨 투명하게"""
    tot: dict[str, int] = {}
    seen: set[str] = set()
    for ln in text.splitlines():
        m = CODE.match(ln)
        if m and m.group(2):
            code = f"{m.group(1)}-{m.group(2)}"
            if code.startswith(("2", "5")) and code not in seen:
                seen.add(code)
                tot[code] = tot.get(code, 0) + to_k(m.group(4))
            elif code.startswith(("2", "5")):
                tot[code] = tot.get(code, 0) + to_k(m.group(4))   # 같은 목이 부서마다 다시 나오면(대구시 배치) 더한다
    got: dict[str, int] = {}
    for r in rows:
        got[r["mok_code"]] = got.get(r["mok_code"], 0) + r["amount_k"]
    out = []
    for code, t in tot.items():
        g = got.get(code, 0)
        if t != g:
            out.append({"mok": code, "mok_total_k": t, "items_k": g, "diff_k": t - g})
    return out


def write(rows: list[dict], key: str, year: str, meta: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ["gov", "key", "year", "acct", "jang", "gwan", "hang", "mok_code", "mok", "bureau", "dept", "item", "calc", "amount_k", "vat_key", "fac_key"]
    with open(OUT / f"{key}_{year}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    idx_p = OUT / "index.json"
    idx = json.loads(idx_p.read_text(encoding="utf-8")) if idx_p.exists() else {}
    idx[f"{key}_{year}"] = {**meta, "rows": len(rows), "sum_k": sum(r["amount_k"] for r in rows if r["jang"].startswith("200")),
                            "grant_k": sum(r["amount_k"] for r in rows if r["jang"].startswith("500")), "check": meta.pop("_check", [])}
    idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 3:
        print(__doc__)
        sys.exit(1)
    key, year, txt = a[0], a[1], a[2]
    name = a[a.index("--name") + 1] if "--name" in a else key
    acct = a[a.index("--acct") + 1] if "--acct" in a else "일반회계"
    rows = parse(Path(txt).read_text(encoding="utf-8", errors="ignore"), key, name, year, acct)
    text = Path(txt).read_text(encoding="utf-8", errors="ignore")
    chk = check(text, rows)
    write(rows, key, year, {"gov": name, "year": year, "source": a[a.index("--src") + 1] if "--src" in a else "", "fetched": a[a.index("--date") + 1] if "--date" in a else "", "_check": chk})
    if chk:
        print(f"  목 합계와 다른 곳 {len(chk)}: " + ", ".join(f"{c['mok']} {c['diff_k']:+,}" for c in chk[:12]))
    from collections import Counter
    c = Counter(r["vat_key"] for r in rows)
    print(f"{name} {year}: {len(rows)}행 · 세외수입 {sum(r['amount_k'] for r in rows if r['jang'].startswith('200')):,}천원 · 보조금 {sum(r['amount_k'] for r in rows if r['jang'].startswith('500')):,}천원 · 0원 행 {sum(1 for r in rows if not r['amount_k'])} · {dict(c.most_common(12))}")
