#!/usr/bin/env python3
"""회사 이름 목록 → DART 투자 관련 공시와 정기보고서의 설비 계획 문구(운영자 지시 2026-11-09 '전력반도체는 어떤 기업이 있고 투자 공시가 있는지').

1) DART 고유번호 목록(corpCode.xml)에서 이름이 같은 회사를 찾는다(법인 표기 뗀 이름 완전 일치, 없으면 포함 일치 앞 3곳).
2) 최근 --months 달 공시 중 제목이 신규시설투자·유형자산 양수/취득·사채(전환·신주인수권·교환) 발행 결정·유상증자 결정·
   증권신고서인 것: 원문에서 투자대상·금액·목적·기간(신규시설·유형자산)과 '시설자금 (원)' 금액, 원문에 나온 국내 시군구·해외 국가.
3) 가장 최근 정기보고서(사업·반기·분기, 없으면 감사보고서) 원문에서 '설비의 신설·매입 계획' 문단, 생산 사업장·공장 소재지 줄,
   건설중인자산 설명 문장, 시설투자·증설·신축 문장(최대 4개).
결과 data/dart/corp_invest.csv(공시마다 한 줄 + 회사마다 정기보고서 한 줄). 공시 사실·문구만 — 평가 없음, 사이트는 읽지 않는다.
사람 이름은 다루지 않는다(제출인 칸은 쓰지 않음). 키: DART_KEY.
사용: python3 scripts/dart_corp_invest.py --names DB하이텍,KEC,… [--months 24] [--tag 전력반도체]
"""
from __future__ import annotations

import csv
import io
import re
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_dart_future as F  # noqa: E402
from dart_capex_national import ABROAD, PLACE  # noqa: E402
from dart_capex_scan import detail_of  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "dart" / "corp_invest.csv"
COLS = ["tag", "query", "corp_code", "name", "stock_code", "corp_cls", "hq", "induty", "rcept_dt", "report_nm", "kind",
        "detail", "fclt_eok", "places", "abroad", "text", "rcept_no", "url"]
FAC = re.compile(r"[^.。|]{0,100}(?:설비의 신설|신규 ?투자|시설투자|증설|신축|신공장|생산라인|생산 라인|생산능력 확대|CAPA|팹|FAB|Fab)[^.。|]{0,120}")
ANY_PLACE = re.compile(r"(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충청|충북|충남|전라|전북|전남|경상|경북|경남|제주)[가-힣]*\s?[가-힣]{1,6}(?:시|군|구)\s?[가-힣0-9]{0,12}(?:로|길|동|읍|면|리)")


def clean(s: str) -> str:
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", s or "")
    return re.sub(r"\s+", "", s)


def kind_of(t: str) -> str:
    t = t.replace(" ", "")
    if "철회" in t:
        return ""
    for k, w in (("신규시설투자", "신규시설투자"), ("유형자산", "유형자산"), ("전환사채", "전환사채권발행결정"),
                 ("신주인수권부사채", "신주인수권부사채권발행결정"), ("교환사채", "교환사채권발행결정"),
                 ("유상증자", "유상증자결정"), ("증권신고서", "증권신고서")):
        if w in t:
            if k == "유형자산" and not ("양수" in t or "취득" in t):
                continue
            return k
    return ""


def periodic(t: str) -> int:
    for i, w in enumerate(("사업보고서", "반기보고서", "분기보고서", "감사보고서")):
        if w in t and "정정" not in t:
            return i + 1
    return 0


def corp_list() -> list[tuple[str, str, str]]:
    r = requests.get(f"{F.API}/corpCode.xml", params={"crtfc_key": F.KEY}, headers=F.UA, timeout=120)
    xml = zipfile.ZipFile(io.BytesIO(r.content)).read("CORPCODE.xml").decode("utf-8", "ignore")
    return [(m.group(1).strip(), m.group(2).strip(), m.group(3).strip())
            for m in re.finditer(r"<corp_code>(.*?)</corp_code>\s*<corp_name>(.*?)</corp_name>.*?<stock_code>(.*?)</stock_code>", xml, re.S)]


def periodic_lines(t: str) -> str:
    out = []
    m = re.search(r"설비의\s?신설\s?[ㆍ·및]?\s?매입\s?계획", t)
    if m:
        out.append("[설비 계획] " + t[m.end(): m.end() + 350].strip())
    i = t.find("생산설비")
    seg = t[i: i + 6000] if i >= 0 else ""
    pl = list(dict.fromkeys(p.strip() for p in ANY_PLACE.findall(seg)))[:6]
    if pl:
        out.append("[생산설비 소재지] " + " / ".join(pl))
    for s in re.findall(r"[^.。|]{0,40}건설중인\s?자산[^.。|]{0,160}(?:취득|계약|공사|신축|증설|설비)[^.。|]{0,120}", t)[:2]:
        out.append("[건설중인자산] " + s.strip())
    fac = [x.strip() for x in FAC.findall(t)]
    fac = [x for x in dict.fromkeys(fac) if len(x) > 25 and not re.search(r"위험|가정|불확실|일반적|산업의 특성|시장", x)][:4]
    out += ["[문장] " + x for x in fac]
    return " ‖ ".join(out)[:1800]


def main(argv: list[str]) -> int:
    names = [x.strip() for x in argv[argv.index("--names") + 1].split(",") if x.strip()] if "--names" in argv else []
    months = int(argv[argv.index("--months") + 1]) if "--months" in argv else 24
    tag = argv[argv.index("--tag") + 1] if "--tag" in argv else ""
    if not F.KEY or not names:
        print("DART_KEY 또는 --names 없음")
        return 0
    allc = corp_list()
    print(f"고유번호 목록 {len(allc)}곳, 대상 이름 {len(names)}개, 최근 {months}달")
    bgn = (date.today() - timedelta(days=months * 31)).strftime("%Y%m%d")
    end = date.today().strftime("%Y%m%d")
    rows = []
    for q in names:
        cq = clean(q)
        hit = [c for c in allc if clean(c[1]) == cq]
        if not hit:
            hit = [c for c in allc if cq in clean(c[1])][:3]
        if len(hit) > 1:   # 같은 이름이 여럿이면 종목코드 있는 곳 먼저, 그다음 최근 공시가 있는 곳
            hit.sort(key=lambda c: (not c[2].strip(),))
        if not hit:
            print(f"### {q}: 고유번호 목록에 없음")
            rows.append({"tag": tag, "query": q, "name": "", "kind": "목록에 없음"})
            continue
        for code, name, stock in hit[:3]:
            info = F.get_json("company.json", corp_code=code) or {}
            time.sleep(0.15)
            base = {"tag": tag, "query": q, "corp_code": code, "name": name, "stock_code": stock, "corp_cls": info.get("corp_cls", ""),
                    "hq": " ".join((info.get("adres") or "").split()[:3]), "induty": info.get("induty_code", "")}
            lst, page = [], 1
            while True:
                j = F.get_json("list.json", corp_code=code, bgn_de=bgn, end_de=end, page_no=page, page_count=100) or {}
                time.sleep(0.15)
                lst += j.get("list", [])
                if page >= int(j.get("total_page") or 1):
                    break
                page += 1
            print(f"### {q} → {name} ({code}, 종목 {stock or '-'}, {info.get('corp_cls')}) {base['hq']} 업종 {base['induty']} 공시 {len(lst)}건")
            if not lst:
                rows.append({**base, "kind": "공시 없음"})
                continue
            per = sorted([x for x in lst if periodic(x["report_nm"])], key=lambda x: x["rcept_dt"], reverse=True)
            hits = [(kind_of(x["report_nm"]), x) for x in lst]
            hits = [(k, x) for k, x in hits if k]
            for k, x in sorted(hits, key=lambda kx: kx[1]["rcept_dt"]):
                t = F.doc_text(x["rcept_no"])
                time.sleep(0.3)
                m = re.search(r"시설자금\s*\(원\)\s*([\d,]+)", t)
                fclt = int(m.group(1).replace(",", "")) if m else 0
                det = detail_of(t) if k in ("신규시설투자", "유형자산") else ""
                if k == "증권신고서":
                    i = t.find("자금의 사용목적")
                    seg = t[i: i + 5000] if i >= 0 else ""
                    fac = [s.strip() for s in FAC.findall(seg)][:3]
                    det = " | ".join(fac)[:400]
                row = {**base, "rcept_dt": x["rcept_dt"], "report_nm": " ".join(x["report_nm"].split()), "kind": k, "detail": det,
                       "fclt_eok": round(fclt / 1e8, 1) if fclt else "",
                       "places": " / ".join(dict.fromkeys(re.sub(r"\s", "", p) for p in PLACE.findall(t)))[:120],
                       "abroad": " / ".join(dict.fromkeys(ABROAD.findall(t)))[:60], "rcept_no": x["rcept_no"],
                       "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={x['rcept_no']}"}
                rows.append(row)
                print(f"  {x['rcept_dt']} {row['report_nm']} | {k} | {det[:200]} | 시설자금 {row['fclt_eok']}억 | {row['places'][:80]} | {row['abroad']}")
            if per:
                x = sorted(per, key=lambda x: (x["rcept_dt"][:6], -periodic(x["report_nm"])), reverse=True)[0]
                t = F.doc_text(x["rcept_no"])
                time.sleep(0.3)
                txt = periodic_lines(t)
                rows.append({**base, "rcept_dt": x["rcept_dt"], "report_nm": " ".join(x["report_nm"].split()), "kind": "정기보고서",
                             "text": txt, "rcept_no": x["rcept_no"], "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={x['rcept_no']}"})
                print(f"  [정기] {x['rcept_dt']} {x['report_nm'].strip()} :: {txt[:1200]}")
            if hit[0][2].strip():   # 상장 회사를 찾았으면 같은 이름 다른 회사는 보지 않음
                break
    OUT.parent.mkdir(parents=True, exist_ok=True)
    old = []
    if OUT.exists():
        old = [r for r in csv.DictReader(open(OUT, encoding="utf-8")) if r.get("query") not in names]
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in old + rows:
            w.writerow({c: r.get(c, "") for c in COLS})
    print(f"저장 {OUT.relative_to(ROOT)} {len(old) + len(rows)}줄(이번 {len(rows)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
