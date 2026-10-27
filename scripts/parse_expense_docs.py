#!/usr/bin/env python3
"""지자체 세출예산사업명세서(e호조 출력 PDF → pdftotext -layout 글자, 부서별 파일을 이어 붙인 것) → 세부사업 단위 CSV(운영자 지시 2026-10-27 '세출도 해봐').
쓰임: 지출 자동 귀속 매핑표 밑그림(세부사업명·부서 → 시설), 공통 지출(본청 부서의 공공운영비) 미리 찾기, 시설비(401)·보조금(307·308) 표시. 금액은 CSV 에만(내부) — 사이트 JSON 은 이름·편성목만(운영자 지시 2026-09-30 대구시 예산 미게시).
배치: 부서(0칸) → 정책(1칸) → 단위(2칸) → 세부사업(3칸) → 편성목 'NNN 이름'(4칸~) → 세목 'NN 이름' → (세세목) → N.산출. 대구시는 실국이 앞에 와 한 칸씩 밀린다.
사용: python3 scripts/parse_expense_docs.py <key> <year> <txt> [--name 이름] → data/vat/revenue/<key>_<year>_exp.csv
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "vat" / "revenue"
AMT = r"([\d,△\-]+)\s+([\d,△\-]+)\s+([\d,△\-]+)\s*$"
NAME_LINE = re.compile(r"^( *)(\S.*?)\s{2,}" + AMT)          # 부서·정책·단위·세부사업 줄(코드 없음, 금액 3개)
CODE_LINE = re.compile(r"^ *(\d{3}) (\S.*?)\s{2,}" + AMT)      # 편성목
SUB_LINE = re.compile(r"^ *(\d{2}) (\S.*?)\s{2,}" + AMT)       # 세목
HEADER = re.compile(r"^(부서|정책|단위|실국)\s*:|부서ㆍ정책ㆍ단위|\(단위|세 ?출 ?예 ?산 ?사 ?업 ?명 ?세 ?서|^\d{4}년도|^\s*전년도\s*$|^\s*예산액\s*$")
FAC_KW = [(r"골프장|파크골프|스키", "golf"), (r"수영|헬스|체육|구장|빙상|운동장|풋살|테니스|야구장|축구장|배드민턴|국민체육|생활체육|스포츠|경기장", "sports"),
          (r"휴양림|숙박|야영|캠핑|수련원|유스호스텔|오토캠핑", "lodging"), (r"박물관|미술관|과학관|도서관|전시관|기념관|동물원|식물원|역사관|문학관|생태원|수목원", "culture"),
          (r"공연장|문화회관|문화예술회관|회의실|예술회관|아트센터|문화센터", "venue"), (r"주차", "parking"), (r"상수도|하수도|정수|취수", "water"), (r"장례|화장장|봉안|추모|장사시설|공설묘", "funeral"),
          (r"버스|택시|여객", "transit"), (r"노인|장애인|복지관|재가|어린이집|보육|요양|경로|복지센터", "welfare"), (r"보건소|보건지소|진료", "medical"), (r"폐기물|쓰레기|소각|매립|재활용|분뇨", "waste_bag"),
          (r"시장|상가|임대", "lease_bldg"), (r"농기계|임대사업", "equip_rent")]
FACILITY_CODES = {"401", "402", "403", "405"}   # 시설비·민간자본사업보조·자치단체등자본이전·자산취득비
OPS_CODES = {"201"}                            # 일반운영비(01 사무관리비·02 공공운영비·03 행사운영비)
GRANT_CODES = {"307", "308"}                   # 민간이전·자치단체등이전(보조금·위탁사업비)


def to_k(s: str) -> int:
    try:
        return int(s.replace(",", "").replace("△", "-"))
    except ValueError:
        return 0


def parse(text: str, key: str, name: str, year: str) -> list[dict]:
    rows: list[dict] = []
    st = {"bureau": "", "dept": "", "policy": "", "unit": "", "detail": "", "detail_k": 0}
    cur: dict | None = None
    has_bureau = "실국:" in text or "실국ㆍ" in text
    base = 0   # 대구시 배치는 실국·부서가 모두 0칸(머리글 '실국: X  부서 : Y' 로 가른다), 정책 1·단위 2·세부사업 3칸은 같다
    bureaus = {m.group(1).strip() for m in re.finditer(r"실국\s*:\s*(\S+)", text)} if has_bureau else set()
    for ln in text.splitlines():
        if not ln.strip() or HEADER.search(ln):
            continue
        m = CODE_LINE.match(ln)
        if m and cur is not None:
            code, nm, amt = m.group(1), m.group(2).strip(), to_k(m.group(3))
            cur["codes"][code] = cur["codes"].get(code, 0) + amt
            cur["code_names"][code] = nm
            cur["_last"] = code
            continue
        if SUB_LINE.match(ln) and cur is not None:
            m2 = SUB_LINE.match(ln); assert m2
            if cur["_last"] == "201" and m2.group(1) == "02":
                cur["ops_public_k"] += to_k(m2.group(3))
            continue
        m = NAME_LINE.match(ln)
        if not m:
            continue
        indent, nm, amt = len(m.group(1)), m.group(2).strip(), to_k(m.group(3))
        if re.match(r"^\d+\.|^\(|^[가-힣]\.", nm) or "총 계" in nm or "총계" in nm:
            continue
        lvl = indent - base
        if has_bureau and indent == 0 and nm in bureaus:
            st["bureau"] = nm; continue
        if lvl == 0:
            st["dept"] = nm; st["policy"] = st["unit"] = st["detail"] = ""
        elif lvl == 1:
            st["policy"] = nm; st["unit"] = st["detail"] = ""
        elif lvl == 2:
            st["unit"] = nm; st["detail"] = ""
        elif lvl == 3:
            st["detail"] = nm
            cur = {"gov": name, "key": key, "year": year, "bureau": st["bureau"], "dept": st["dept"], "policy": st["policy"], "unit": st["unit"], "detail": nm, "amount_k": amt,
                   "codes": {}, "code_names": {}, "ops_public_k": 0, "_last": ""}
            rows.append(cur)
        else:
            continue
    out = []
    for r in rows:
        codes = r["codes"]
        fac = next((k for pat, k in FAC_KW if re.search(pat, r["detail"])), "")
        out.append({"gov": r["gov"], "key": r["key"], "year": r["year"], "bureau": r["bureau"], "dept": r["dept"], "policy": r["policy"], "unit": r["unit"], "detail": r["detail"],
                    "amount_k": r["amount_k"], "codes": " ".join(f"{c}:{codes[c]}" for c in sorted(codes)), "code_names": " ".join(f"{c}:{r['code_names'][c]}" for c in sorted(codes)),
                    "facility_k": sum(v for c, v in codes.items() if c in FACILITY_CODES), "ops_k": sum(v for c, v in codes.items() if c in OPS_CODES), "public_ops_k": r["ops_public_k"], "grant_k": sum(v for c, v in codes.items() if c in GRANT_CODES),
                    "fac_key": fac})
    return out


def write(rows: list[dict], key: str, year: str, meta: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ["gov", "key", "year", "bureau", "dept", "policy", "unit", "detail", "amount_k", "codes", "code_names", "facility_k", "ops_k", "public_ops_k", "grant_k", "fac_key"]
    with open(OUT / f"{key}_{year}_exp.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    idx_p = OUT / "index.json"
    idx = json.loads(idx_p.read_text(encoding="utf-8")) if idx_p.exists() else {}
    idx[f"{key}_{year}_exp"] = {**meta, "rows": len(rows), "depts": len({r["dept"] for r in rows}), "facility_rows": sum(1 for r in rows if r["facility_k"]), "fac_rows": sum(1 for r in rows if r["fac_key"])}
    idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 3:
        print(__doc__); sys.exit(1)
    key, year, txt = a[0], a[1], a[2]
    name = a[a.index("--name") + 1] if "--name" in a else key
    rows = parse(Path(txt).read_text(encoding="utf-8", errors="ignore"), key, name, year)
    write(rows, key, year, {"gov": name, "year": year, "source": a[a.index("--src") + 1] if "--src" in a else "", "fetched": a[a.index("--date") + 1] if "--date" in a else ""})
    print(f"{name} {year} 세출: 세부사업 {len(rows)}개 · 부서 {len({r['dept'] for r in rows})} · 시설비 있는 사업 {sum(1 for r in rows if r['facility_k'])} · 시설 낱말 {sum(1 for r in rows if r['fac_key'])} · 합계 {sum(r['amount_k'] for r in rows):,}천원")
