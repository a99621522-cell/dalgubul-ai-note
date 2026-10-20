#!/usr/bin/env python3
"""SDV 연구보고서용 대구·경북 자동차부품사 DART 원자료(일회성, 사이트와 분리 — 운영자 지시 2026-10-20).
「현대·기아차의 SDV가 지역 자동차 부품회사에 미치는 영향과 대책 — 대구·경북」에 쓸 원자료를 data/dart_sdv/ 에만 저장한다.
사이트 산출물(scripts/data/company_financials*.csv, data/dart/*.csv)은 읽지도 쓰지도 않는다.

a) 대상 확정: scripts/data/sdv_targets.csv 의 회사명 → corpCode.xml 이름 정확 일치(공백만 무시) → company.json(본사 주소·종목코드·업종코드).
   이름이 같은 회사가 여럿이면 상장 + 본사 대구·경북인 쪽, 그다음 상장, 그다음 대구·경북. → data/dart_sdv/targets_resolved.csv
   --discover: 상장회사(종목코드 있음) 전부의 기업개황을 보고 본사 경상북도 + 업종코드 30xxx(자동차 및 트레일러 제조업)인 곳을 '추가 발견'으로 더한다.
   기업개황은 data/dart_sdv/company_cache.json 에 남겨 다시 부르지 않는다(대표자 이름 등은 저장하지 않음).
b) 재무: 단일회사 전체 재무제표(fnlttSinglAcntAll) — 사업보고서(11011) 2023·2024·2025, 2026년 반기보고서(11012), 연결(CFS) 없으면 개별(OFS).
   → data/dart_sdv/financials.csv: 주요 계정(매출액·영업이익·당기순이익·자산·부채·자본총계·판매비와관리비·연구개발비 계열)만, 공시 계정명 그대로
   → data/dart_sdv/financials_all.csv: 받은 모든 계정 행(손익·재무상태·현금흐름·자본변동)
   반기보고서 손익 계정은 '2분기(4~6월)'와 '1~6월 누적' 두 줄, 재무상태 계정은 6월 말 값.
값은 공시 그대로(원). 해석·평가 없음. 키: DART_KEY. API 실패는 로그 후 건너뛴다.

사용: python3 scripts/collect_dart_sdv.py [--discover] [--no-fin]
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_dart_notes import API, CALLS, KEY, UA, clean, get, redact  # noqa: E402  (재시도·한도 초과 멈춤을 같이 쓴다)

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ROOT / "scripts" / "data" / "sdv_targets.csv"
OUT = ROOT / "data" / "dart_sdv"
CACHE = OUT / "company_cache.json"
CLS = {"Y": "유가증권", "K": "코스닥", "N": "코넥스", "E": "기타"}
YEARS = [2023, 2024, 2025]
HALF_YEAR = 2026
REG = ("대구", "경상북도", "경북")

# 표준 항목 ← account_id 먼저, 없으면 계정명
KEYS = [
    ("매출액", ("ifrs-full_Revenue",), ("매출액", "수익(매출액)", "영업수익", "매출")),
    ("영업이익", ("dart_OperatingIncomeLoss",), ("영업이익", "영업이익(손실)", "영업손익")),
    ("당기순이익", ("ifrs-full_ProfitLoss",), ("당기순이익", "당기순이익(손실)", "당기순손익", "분기순이익", "반기순이익", "반기순이익(손실)")),
    ("자산총계", ("ifrs-full_Assets",), ("자산총계",)),
    ("부채총계", ("ifrs-full_Liabilities",), ("부채총계",)),
    ("자본총계", ("ifrs-full_Equity",), ("자본총계",)),
    ("판매비와관리비", ("dart_TotalSellingGeneralAdministrativeExpenses", "ifrs-full_SellingGeneralAndAdministrativeExpense"), ("판매비와관리비", "판매비와 관리비", "판매비및관리비")),
]
RND = re.compile(r"연구개발|경상연구")

COLS_T = ["회사명", "지역(입력)", "corp_code", "DART 회사명", "stock_code", "시장", "본사주소", "induty_code", "매칭방법", "비고"]
COLS_F = ["회사명", "corp_code", "연도", "보고서", "기간", "연결/개별", "표준항목", "계정명", "account_id", "재무제표", "금액(원)", "rcept_no", "url"]
COLS_A = ["회사명", "corp_code", "연도", "보고서", "연결/개별", "재무제표", "account_id", "계정명", "account_detail",
          "당기명", "당기금액", "당기누적금액", "전기명", "전기금액", "전기누적금액", "통화", "ord", "rcept_no"]


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def corp_list() -> list[tuple[str, str, str]]:
    try:
        r = requests.get(f"{API}/corpCode.xml", params={"crtfc_key": KEY}, headers=UA, timeout=180)
        xml = zipfile.ZipFile(io.BytesIO(r.content)).read("CORPCODE.xml").decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        print(f"[sdv] corpCode 실패: {redact(e)[:120]}")
        return []
    out = []
    for m in re.finditer(r"<corp_code>(.*?)</corp_code>\s*<corp_name>(.*?)</corp_name>.*?<stock_code>(.*?)</stock_code>", xml, re.S):
        out.append((clean(m.group(1)), clean(m.group(2)), clean(m.group(3)).strip()))
    print(f"[sdv] 고유번호 목록 {len(out):,}곳 (종목코드 있는 곳 {sum(1 for x in out if x[2]):,})")
    return out


def company(code: str, cache: dict) -> dict:
    if code in cache:
        return cache[code]
    j = get("company.json", corp_code=code) or {}
    time.sleep(0.08)
    info = {k: (j.get(k) or "").strip() for k in ("corp_name", "stock_code", "corp_cls", "adres", "induty_code", "est_dt", "acc_mt")}
    if j:
        cache[code] = info
    return info


def in_region(adr: str) -> bool:
    a = adr.replace(" ", "")
    return a.startswith(REG) or a.startswith("(") and any(r in a[:30] for r in REG)


def resolve(targets: list[dict], corps: list[tuple[str, str, str]], cache: dict) -> list[dict]:
    by = {}
    for code, name, stock in corps:
        by.setdefault(norm(name), []).append((code, name, stock))
    rows = []
    for t in targets:
        nm = t["회사명"].strip()
        cands = by.get(norm(nm), [])
        rec = {"회사명": nm, "지역(입력)": t.get("지역", ""), "비고": t.get("메모", "")}
        if not cands:
            rec.update({"매칭방법": "일치 없음", "비고": (rec["비고"] + " · DART 고유번호 목록에 같은 이름 없음").strip(" ·")})
            rows.append(rec)
            continue
        infos = [(c, company(c[0], cache)) for c in cands]

        def score(x):
            (code, name, stock), info = x
            return ((1 if stock else 0) + (1 if in_region(info.get("adres", "")) else 0) * 2, 1 if stock else 0)
        infos.sort(key=score, reverse=True)
        (code, name, stock), info = infos[0]
        how = "이름 정확 일치" if len(cands) == 1 else f"이름 정확 일치 {len(cands)}곳 중 " + ("상장·본사 대구경북" if stock and in_region(info.get("adres", "")) else "상장" if stock else "본사 대구경북" if in_region(info.get("adres", "")) else "첫 후보")
        notes = [rec["비고"]] if rec["비고"] else []
        if not stock:
            notes.append("비상장(종목코드 없음)")
        if info.get("adres") and not in_region(info["adres"]):
            notes.append("본사 대구·경북 아님")
        if info.get("acc_mt") and info["acc_mt"] != "12":
            notes.append(f"결산월 {info['acc_mt']}월")
        rec.update({"corp_code": code, "DART 회사명": name, "stock_code": stock, "시장": CLS.get(info.get("corp_cls", ""), info.get("corp_cls", "")),
                    "본사주소": info.get("adres", ""), "induty_code": info.get("induty_code", ""), "매칭방법": how, "비고": " · ".join(notes)})
        rows.append(rec)
        print(f"[sdv] {nm} → {code} {name} {stock or '-'} {rec['시장']} {info.get('adres', '')[:30]} {info.get('induty_code', '')} ({how})")
    return rows


def discover(corps, cache, have: set) -> list[dict]:
    listed = [c for c in corps if c[2]]
    print(f"[sdv] 추가 발견: 상장회사 {len(listed):,}곳 기업개황 확인(캐시 {sum(1 for c in listed if c[0] in cache):,}곳)")
    out = []
    for i, (code, name, stock) in enumerate(listed, 1):
        info = company(code, cache)
        if i % 300 == 0:
            print(f"[sdv]   {i:,}/{len(listed):,} · API {CALLS[0]:,}건")
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
        adr = info.get("adres", "").replace(" ", "")
        if code in have or not (adr.startswith("경상북도") or adr.startswith("경북")):
            continue
        if not (info.get("induty_code", "").startswith("30") and info.get("corp_cls") in ("Y", "K", "N")):
            continue
        out.append({"회사명": name, "지역(입력)": "경북", "corp_code": code, "DART 회사명": name, "stock_code": stock,
                    "시장": CLS.get(info.get("corp_cls", ""), ""), "본사주소": info.get("adres", ""), "induty_code": info.get("induty_code", ""),
                    "매칭방법": "추가 발견(본사 경북 + 업종 30xxx)", "비고": f"결산월 {info['acc_mt']}월" if info.get("acc_mt") and info["acc_mt"] != "12" else ""})
        print(f"[sdv] 추가 발견 {name} {stock} {info.get('induty_code')} {info.get('adres', '')[:30]}")
    return out


def fin(row: dict) -> tuple[list[dict], list[dict]]:
    code, name = row["corp_code"], row["회사명"]
    picks, alls = [], []
    jobs = [(y, "11011", "사업보고서") for y in YEARS] + [(HALF_YEAR, "11012", "반기보고서")]
    for y, rc, rname in jobs:
        lst, fs = [], ""
        for fd in ("CFS", "OFS"):
            j = get("fnlttSinglAcntAll.json", corp_code=code, bsns_year=y, reprt_code=rc, fs_div=fd)
            time.sleep(0.12)
            lst = (j or {}).get("list", [])
            if lst:
                fs = "연결" if fd == "CFS" else "개별"
                break
        if not lst:
            print(f"[sdv]   {name} {y} {rname}: 없음")
            continue
        rno = lst[0].get("rcept_no", "")
        url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rno}" if rno else ""
        for x in lst:
            alls.append({"회사명": name, "corp_code": code, "연도": y, "보고서": rname, "연결/개별": fs, "재무제표": x.get("sj_nm", "") or x.get("sj_div", ""),
                         "account_id": x.get("account_id", ""), "계정명": (x.get("account_nm") or "").strip(), "account_detail": x.get("account_detail", ""),
                         "당기명": x.get("thstrm_nm", ""), "당기금액": x.get("thstrm_amount", ""), "당기누적금액": x.get("thstrm_add_amount", ""),
                         "전기명": x.get("frmtrm_nm", ""), "전기금액": x.get("frmtrm_amount", ""), "전기누적금액": x.get("frmtrm_add_amount", ""),
                         "통화": x.get("currency", ""), "ord": x.get("ord", ""), "rcept_no": x.get("rcept_no", "")})
        seen = set()
        for x in lst:
            sj = x.get("sj_div", "")
            if sj not in ("BS", "IS", "CIS"):
                continue
            aid, anm = x.get("account_id", ""), (x.get("account_nm") or "").strip()
            std = ""
            for k, ids, names in KEYS:
                if aid in ids or norm(anm) in {norm(n) for n in names}:
                    std = k
                    break
            if not std and RND.search(anm):
                std = "연구개발비(계정)"
            if not std or (std != "연구개발비(계정)" and std in seen):
                continue
            # IS 와 CIS 에 같은 계정이 두 번 나오면 먼저 나온 것 하나만
            seen.add(std)
            base = {"회사명": name, "corp_code": code, "연도": y, "보고서": rname, "연결/개별": fs, "표준항목": std, "계정명": anm,
                    "account_id": aid, "재무제표": x.get("sj_nm", "") or sj, "rcept_no": rno, "url": url}
            if sj == "BS":
                picks.append({**base, "기간": "기말" if rc == "11011" else "6월 말", "금액(원)": x.get("thstrm_amount", "")})
            elif rc == "11011":
                picks.append({**base, "기간": "연간", "금액(원)": x.get("thstrm_amount", "")})
            else:
                picks.append({**base, "기간": "2분기(4~6월)", "금액(원)": x.get("thstrm_amount", "")})
                if x.get("thstrm_add_amount"):
                    picks.append({**base, "기간": "1~6월 누적", "금액(원)": x.get("thstrm_add_amount", "")})
        print(f"[sdv]   {name} {y} {rname} {fs}: 계정 {len(lst)}행, 주요 {len(seen)}개")
    return picks, alls


def write(path: Path, cols: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:   # 엑셀에서 바로 열리게 BOM
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"[sdv] 저장 {path.relative_to(ROOT)} {len(rows):,}행")


def main(argv: list[str]) -> int:
    if not KEY:
        print("DART_KEY 없음")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    targets = list(csv.DictReader(open(TARGETS, encoding="utf-8-sig")))
    corps = corp_list()
    if not corps:
        return 0
    rows = resolve(targets, corps, cache)
    if "--discover" in argv:
        rows += discover(corps, cache, {r.get("corp_code") for r in rows if r.get("corp_code")})
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    write(OUT / "targets_resolved.csv", COLS_T, rows)
    if "--no-fin" not in argv:
        picks, alls = [], []
        for r in rows:
            if r.get("corp_code"):
                p, a = fin(r)
                picks += p
                alls += a
        write(OUT / "financials.csv", COLS_F, picks)
        write(OUT / "financials_all.csv", COLS_A, alls)
    print(f"[sdv] 끝 — API {CALLS[0]:,}건")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
