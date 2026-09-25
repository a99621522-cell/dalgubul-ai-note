#!/usr/bin/env python3
"""공공데이터포털에서 받은 '지원받은 기업' 파일들(data/raw/<데이터셋번호>/…) → 지원 이력 투입 CSV(scripts/data/support/)와
산단 외 기업·태그 투입 CSV(scripts/data/extra/)로 변환한다. 이어서 import_support.py / import_extra.py 를 실행한다.

데이터셋별 열 매핑은 MAPPINGS 에 있다. 지역 열이 있으면 대구만, 없으면 기업 사전 이름과 맞는 행만 남긴다(전국 과제 수만 건에서 대구 기업만).
금액 열이 없는 자료는 금액을 비워 둔다(만들지 않는다). 사업자번호·대표자는 저장하지 않는다.
모르는 데이터셋 번호는 열 이름만 출력한다(매핑 추가용).

사용: python3 scripts/import_public_support.py [data/raw]
"""
from __future__ import annotations

import csv
import io
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sites import load_all_companies  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SUPPORT_IN = ROOT / "scripts" / "data" / "support"
EXTRA_IN = ROOT / "scripts" / "data" / "extra"
PORTAL = "https://www.data.go.kr/data/{id}/fileData.do"

# kind: support(지원 이력) | tag(기업 태그·산단 외 기업)
MAPPINGS: dict[str, dict] = {
    "15018033": {"kind": "support", "source": "KEIT 산업기술 R&D 과제현황(공공데이터포털)", "layer": "국비", "type": "R&D",
                 "name": ["주관기관"], "also_names": "참여기관", "year": "지원년도", "program": "내역사업명", "funder": "주관부처",
                 "region": None, "min_year": 2018},
    "15149536": {"kind": "support", "source": "KEIT 산업기술 R&D 과제 상세정보(공공데이터포털)", "layer": "국비", "type": "R&D",
                 "name": ["주관기관", "주관기관명", "수행기관"], "also_names": "참여기업", "year": ["지원년도", "사업년도", "기준연도"],
                 "program": ["내역사업명", "사업명"], "funder": "산업통상자원부", "amount": ["정부지원금", "정부출연금", "정부지원금(백만원)"],
                 "amount_unit_guess": True, "region": None, "min_year": 2018},
    "3044610": {"kind": "support", "source": "중소벤처기업부 중소기업기술개발과제정보(공공데이터포털)", "layer": "국비", "type": "R&D",
                "name": ["주관기관"], "year": "사업년도", "program": "사업명", "funder": "중소벤처기업부", "region": None, "min_year": 2018},
    "15106650": {"kind": "support", "source": "한국에너지기술평가원 지원과제정보(공공데이터포털)", "layer": "국비", "type": "R&D",
                 "name": ["수행기관명"], "year": "기준연도", "program": "세부사업", "funder": "산업통상자원부(에너지기술평가원)",
                 "region": ("수행기관 지역", "대구"), "min_year": 2018},
    "15100252": {"kind": "support", "source": "중소벤처기업진흥공단 스마트제조기업 일자리 패키지 참여기업(공공데이터포털)", "layer": "국비", "type": "선정",
                 "name": ["기업명"], "year": "참여년도", "program": "스마트제조기업 일자리 패키지", "funder": "중소벤처기업진흥공단",
                 "region": ("지역구분", "대구"), "min_year": 2018},
    "15025589": {"kind": "support", "source": "중소기업기술정보진흥원 기술개발 우수성과 50선(공공데이터포털)", "layer": "국비", "type": "선정",
                 "name": ["주관기관"], "year": "우수사례 선정년도", "program": "사업명", "funder": "중소기업기술정보진흥원",
                 "region": ("지역", "대구"), "min_year": 2018},
    "15106072": {"kind": "support", "source": "중소기업기술정보진흥원 지역혁신 선도기업 선정 현황(공공데이터포털)", "layer": "국비", "type": "선정",
                 "name": ["기업명", "주관기관", "업체명"], "year": ["선정년도", "선정연도", "년도", "연도"], "program": "지역혁신 선도기업",
                 "funder": "중소기업기술정보진흥원", "region": ("지역", "대구"), "min_year": 2018},
    "15067341": {"kind": "support", "source": "한국데이터산업진흥원 데이터 활용 사업화 지원 선정기업(공공데이터포털)", "layer": "국비", "type": "선정",
                 "name": ["기업명", "선정기업", "업체명"], "year": ["선정년도", "선정연도", "년도", "연도", "사업년도"], "program": "데이터 활용 사업화 지원",
                 "funder": "한국데이터산업진흥원", "region": ("지역", "대구"), "min_year": 2018},
    "15130932": {"kind": "support", "source": "대구광역시 스타기업·PRE-스타기업·3030기업 현황(공공데이터포털)", "layer": "시비", "type": "선정",
                 "name": ["기업명", "업체명", "회사명"], "year": ["선정년도", "선정연도", "지정년도", "기준년도"], "program": ["구분", "기업구분", "유형"],
                 "funder": "대구광역시", "region": None, "min_year": 0},
    "15084581": {"kind": "tag", "tag": "venture", "source": "중소벤처기업부 벤처기업명단(공공데이터포털)",
                 "name": ["기업명", "업체명", "회사명"], "address": ["주소", "간략주소", "소재지"], "region": ("지역", "대구"),
                 "sector": ["업종", "업종명", "산업분류"], "product": ["주요제품", "주생산품"], "founded": []},
    "3033893": {"kind": "tag", "tag": "innobiz", "source": "중소벤처기업부 혁신형중소기업 현황(공공데이터포털)",
                "name": ["기업명", "업체명", "회사명"], "address": ["주소", "소재지"], "region": ("지역", "대구"),
                "sector": ["업종", "업종명"], "product": ["주요제품", "주생산품"], "founded": []},
}


def norm_name(s: str) -> str:
    s = re.sub(r"\(주\)|㈜|\(유\)|주식회사|유한회사|유한책임회사|합자회사|농업회사법인|\(사\)|사단법인|재단법인|\(재\)", "", s or "")
    return re.sub(r"[\s\-_.,·ㆍ&/()\[\]'\"]", "", s).lower()


def read_any(p: Path) -> tuple[list[dict], list[str]]:
    if p.suffix.lower() in (".xlsx", ".xls"):
        import pandas as pd
        df = pd.read_excel(p, dtype=str).fillna("")
        return df.to_dict("records"), list(df.columns)
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("cp949", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    return rows, (list(rows[0].keys()) if rows else [])


def pick(r: dict, cols) -> str:
    if isinstance(cols, str):
        cols = [cols]
    for c in cols:
        if c in r and r[c] not in (None, ""):
            return str(r[c]).strip()
    for c in cols:  # 접두어
        for k, v in r.items():
            if k and k.replace(" ", "").startswith(c.replace(" ", "")) and v not in (None, ""):
                return str(v).strip()
    return ""


def split_names(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,;/|]| 외 ", s or "") if x.strip() and not re.fullmatch(r"\d+\s*(개|곳)?", x.strip())]


def main(argv: list[str]) -> int:
    raw_dir = Path(argv[0]) if argv else RAW
    companies = load_all_companies()
    known = {norm_name(c["name"]) for c in companies}
    SUPPORT_IN.mkdir(parents=True, exist_ok=True)
    EXTRA_IN.mkdir(parents=True, exist_ok=True)
    summary = Counter()
    for d in sorted(raw_dir.glob("*")):
        if not d.is_dir():
            continue
        pk = d.name
        files = [f for f in d.iterdir() if f.suffix.lower() in (".csv", ".xlsx", ".xls")]
        if not files:
            print(f"[{pk}] 표 파일 없음 ({[f.name for f in d.iterdir()]})")
            continue
        m = MAPPINGS.get(pk)
        for f in files:
            rows, cols = read_any(f)
            if not m:
                print(f"[{pk}] 매핑 없음 — 열: {cols[:20]} ({len(rows):,}행) · {f.name}")
                continue
            out = []
            for r in rows:
                if m.get("region"):
                    col, word = m["region"]
                    if word not in pick(r, col):
                        continue
                names = [pick(r, m["name"])]
                if m.get("also_names"):
                    names += split_names(pick(r, m["also_names"]))
                names = [n for n in names if n]
                if not m.get("region"):  # 지역 열이 없으면 기업 사전에 있는 이름만
                    names = [n for n in names if norm_name(n) in known]
                if not names:
                    continue
                if m["kind"] == "support":
                    year = re.sub(r"\D", "", pick(r, m["year"]))[:4]
                    if year and int(year) < m.get("min_year", 0):
                        continue
                    program = pick(r, m["program"]) if not isinstance(m["program"], str) or m["program"] in r or any(k.startswith(m["program"]) for k in r) else m["program"]
                    if not program:
                        program = m["program"] if isinstance(m["program"], str) else ""
                    funder = pick(r, m["funder"]) if isinstance(m["funder"], str) and (m["funder"] in r) else m["funder"]
                    amount = re.sub(r"[^\d.]", "", pick(r, m["amount"])) if m.get("amount") else ""
                    unit = "백만원" if (amount and m.get("amount_unit_guess")) else ("원" if amount else "")
                    for n in names:
                        out.append({"기업명": n, "주소": "", "선정연도": year, "구분": m["layer"], "지원기관": funder, "사업명": program, "지원유형": m["type"],
                                    "금액": amount, "단위": unit, "출처": m["source"], "출처URL": PORTAL.format(id=pk), "기준일": re.sub(r".*?(\d{8}|\d{4}[-_.]\d{2}).*", r"\1", f.stem)})
                else:  # tag → import_extra 형식
                    out.append({"회사명": names[0], "주소": pick(r, m["address"]), "업종": pick(r, m["sector"]), "사업내용": pick(r, m["product"]),
                                "종사자수": "", "설립연도": pick(r, m["founded"]) if m.get("founded") else "", "태그": m["tag"],
                                "출처": m["source"], "기준월": re.sub(r".*?(\d{8}|\d{4}[-_.]\d{2}).*", r"\1", f.stem)})
            if not out:
                print(f"[{pk}] 대구·기업 사전 일치 행 없음 ({len(rows):,}행, 열 {cols[:12]})")
                continue
            target = (SUPPORT_IN if m["kind"] == "support" else EXTRA_IN) / f"portal_{pk}.csv"
            with open(target, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
                w.writeheader()
                w.writerows(out)
            summary[pk] += len(out)
            print(f"[{pk}] {m['kind']} {len(out):,}행 → {target.relative_to(ROOT)} (원본 {len(rows):,}행)")
    print("합계:", dict(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
