#!/usr/bin/env python3
"""성장 계산기(/growth/) 해설 — 계산값을 Gemini 에게 주고 공무원용 개조식 해설을 쓰게 한다(운영자 지시 2026-10-05).

1) 계산(사실 묶음): 페이지와 같은 식으로 data/kosis/grdp-sido-industry-all.csv·scripts/data/bok_io_daegu.json 에서
   지난 10년 추세, 5단계 경로(목표 2.0~5.0%), 분야별 필요 성장률, 제조업 경로(목표 1.0~5.0%), 금액을 만든다.
2) Gemini: 사실 묶음만 근거로 JSON(headline + sections[title, points]) 해설. 평가·전망·권고 금지, 새 숫자 계산 금지.
3) 숫자 검사: 해설에 나온 숫자가 모두 사실 묶음에 있는지 본다(20 이하 정수·연도는 허용). 어긋나면 한 번 다시, 그래도 어긋나면 저장하지 않는다.
4) data/growth/commentary.json — approved: false 로 저장(원칙 5: 자동 생성 글은 승인 뒤 노출). 페이지는 approved 일 때만 보인다.
   운영자 확인 뒤 `python3 scripts/growth_commentary.py --approve`. 사실 묶음이 바뀌면(해시) 다시 쓰고 승인도 다시 받는다.
사용: python3 scripts/growth_commentary.py [--facts-only] [--force] [--approve]
키: GEMINI_KEY (모델 GEMINI_MODEL, 기본 collect.py 와 같음)
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "growth" / "commentary.json"
GEMINI_KEY = os.environ.get("GEMINI_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
REGION, TOT = "대구광역시", "지역내총생산(시장가격)"

# src/lib/grdp.ts 의 GRDP_COMP·MFG_SUB·PATH_FIELDS 와 같게 유지
GRDP_COMP = [("농업 임업 및 어업", "농림어업"), ("광업", "광업"), ("제조업", "제조업"), ("전기 가스 증기 및 공기 조절 공급업", "전기·가스·증기"),
             ("수도 하수 및 폐기물 처리 원료 재생업", "수도·하수·폐기물"), ("건설업", "건설업"), ("도매 및 소매업", "도매·소매"), ("운수 및 창고업", "운수·창고"),
             ("숙박 및 음식점업", "숙박·음식점"), ("정보통신업", "정보통신"), ("금융 및 보험업", "금융·보험"), ("부동산업", "부동산"),
             ("전문 과학 및 기술 서비스업", "전문·과학·기술"), ("사업시설 관리 사업 지원 및 임대 서비스업", "사업시설관리·지원·임대"),
             ("공공 행정 국방 및 사회보장 행정", "공공행정·국방"), ("교육 서비스업", "교육"), ("보건업 및 사회복지 서비스업", "보건·사회복지"),
             ("예술 스포츠 및 여가관련 서비스", "예술·스포츠·여가"), ("협회 및 단체 수리 및 기타 개인 서비스업", "협회·수리·개인서비스"), ("순생산물세", "순생산물세")]
MFG_SUB = [("음식료품 및 담배제조업", "음식료품·담배"), ("섬유 의복 및 가죽 제품 제조업", "섬유·의복·가죽"), ("목재종이인쇄 및 복제업", "목재·종이·인쇄"),
           ("석탄 및 석유 화학제품 제조업", "석유·화학"), ("비금속광물 및 금속제품 제조업", "비금속광물·금속"), ("전기 전자 및 정밀기기 제조업", "전기·전자·정밀기기"),
           ("기계 운송장비 및 기타 제품 제조업", "기계·운송장비·기타")]
FIELDS = {"base": ["섬유 의복 및 가죽 제품 제조업", "비금속광물 및 금속제품 제조업", "목재종이인쇄 및 복제업", "음식료품 및 담배제조업"],
          "core": ["기계 운송장비 및 기타 제품 제조업", "전기 전자 및 정밀기기 제조업", "석탄 및 석유 화학제품 제조업"],
          "ext": ["보건업 및 사회복지 서비스업", "교육 서비스업", "숙박 및 음식점업", "예술 스포츠 및 여가관련 서비스"],
          "know": ["전문 과학 및 기술 서비스업", "사업시설 관리 사업 지원 및 임대 서비스업", "정보통신업", "금융 및 보험업"]}
FIELD_NM = {"mfg": "제조업", "ext": "역외 수요 서비스(보건·교육·관광)", "know": "지식·생산자 서비스(전문·사업지원·정보통신·금융)", "life": "생활·기반 산업(도소매·부동산·건설·운수·공공 등)"}


def f1(v: float) -> str:
    return f"{v:.1f}"


def won(v: float) -> str:
    return f"{round(v):,}"


def facts() -> dict:
    V: dict[tuple, float] = {}
    regions = set()
    for r in csv.DictReader(open(ROOT / "data/kosis/grdp-sido-industry-all.csv", encoding="utf-8")):
        try:
            V[(r["ITM_NM"], r["C1_NM"], r["C2_NM"], int(r["PRD_DE"]))] = float(r["DT"])
            regions.add(r["C1_NM"])
        except ValueError:
            pass
    years = sorted({k[3] for k in V})
    y1 = years[-1]
    y0 = max(years[0], y1 - 10)
    n = y1 - y0

    def cagr(reg, k):
        a, b = V.get(("실질", reg, k, y0)), V.get(("실질", reg, k, y1))
        return ((b / a) ** (1 / n) - 1) * 100 if a and b and a > 0 and b > 0 else None
    nom = V[("명목", REGION, TOT, y1)]
    base = sum(sum(V.get(("실질기여도", REGION, k, y), 0) for y in range(y0 + 1, y1 + 1)) / n for k, _ in GRDP_COMP)
    sido = [r for r in regions if r != "전국"]
    names = dict(GRDP_COMP + MFG_SUB)
    keys = [k for k, _ in MFG_SUB] + [k for k, _ in GRDP_COMP if k not in ("제조업", "순생산물세")]
    rows = []
    for k in keys:
        cs = sorted([c for c in (cagr(r, k) for r in sido) if c is not None], reverse=True)
        g = cagr(REGION, k) or 0.0
        va = V.get(("명목", REGION, k, y1), 0)
        if va <= 0:
            continue
        mfg = any(k == m for m, _ in MFG_SUB)
        field = "mfg" if mfg else next((f for f, ks in FIELDS.items() if k in ks), "life")
        rows.append({"key": k, "name": names[k], "mfg": mfg, "field": field, "share": va / nom * 100, "va": va / 100, "g": g,
                     "gn": cagr("전국", k) if cagr("전국", k) is not None else g, "t3": sum(cs[:3]) / min(3, len(cs)) if cs else g})
    io = json.loads((ROOT / "scripts/data/bok_io_daegu.json").read_text(encoding="utf-8"))
    va_in = next(r["within"] for r in io["final_demand"] if r["region"] == "대구" and r["type"] == "부가가치유발계수" and r["year"] == 2020)
    imp = float(re.search(r"수입\s*([\d.]+)%", next(f["text"] for f in io["facts"] if re.search(r"표 IV-7.*대구", f["text"]))).group(1))
    k_eff = (1 - imp / 100) * va_in
    gdp_eok = nom / 100

    steps = [lambda r, c: max(c, 0) if r["mfg"] else c, lambda r, c: max(c, r["gn"]) if r["mfg"] else c,
             lambda r, c: max(c, r["gn"]) if not r["mfg"] else c, lambda r, c: max(c, r["t3"]) if r["mfg"] else c,
             lambda r, c: max(c, r["t3"]) if not r["mfg"] else c]
    stage_nm = ["제조업 감소 멈춤", "제조업 전국 수준", "서비스·기타 산업 전국 수준", "제조업 상위 3개 시도 수준", "서비스·기타 산업 상위 3개 시도 수준"]
    contrib = lambda cur: sum(r["share"] * (cur[i] - r["g"]) / 100 for i, r in enumerate(rows))

    def solve(T):
        cur, cum = [r["g"] for r in rows], base
        if cum >= T:
            return cur, 0, 1.0, 0.0
        for k, f in enumerate(steps):
            nxt = [f(r, cur[i]) for i, r in enumerate(rows)]
            add = contrib(nxt) - contrib(cur)
            if cum + add >= T:
                fr = (T - cum) / add if add > 0 else 1.0
                return [cur[i] + fr * (nxt[i] - cur[i]) for i in range(len(rows))], k + 1, fr, 0.0
            cum += add
            cur = nxt
        rest = T - cum
        return [c + rest for c in cur], -1, 1.0, rest

    def fg(fin, f):
        xs = [(r, fin[i]) for i, r in enumerate(rows) if r["field"] == f]
        sh = sum(r["share"] for r, _ in xs)
        return sum(r["share"] * x for r, x in xs) / sh if sh else 0
    stages, cur, cum = [], [r["g"] for r in rows], base
    for k, f in enumerate(steps):
        nxt = [f(r, cur[i]) for i, r in enumerate(rows)]
        add = contrib(nxt) - contrib(cur)
        cum += add
        stages.append({"stage": k + 1, "name": stage_nm[k], "add": f1(add), "cum": f1(cum)})
        cur = nxt
    g0 = [r["g"] for r in rows]
    trend_fields = {FIELD_NM[f]: f1(fg(g0, f)) for f in FIELD_NM}
    scen = []
    for T in (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0):
        fin, at, fr, rest = solve(T)
        scen.append({"target": f1(T), "stage": at, "stage_share_pct": round(fr * 100), "rest": f1(rest),
                     "fields": {FIELD_NM[f]: f1(fg(fin, f)) for f in FIELD_NM},
                     "grdp_increase_jo": f1(gdp_eok * T / 100 / 10000), "more_than_trend_jo": f1(gdp_eok * (T - base) / 100 / 10000),
                     "final_demand_needed_jo": f1(gdp_eok * (T - base) / 100 / k_eff / 10000) if T > base else "0.0"})
    # 제조업 경로
    M = [r for r in rows if r["mfg"]]
    msh = sum(r["share"] for r in M)
    mg = lambda cur: sum(r["share"] * cur[i] for i, r in enumerate(M)) / msh
    msteps = [lambda r, c: max(c, 0), lambda r, c: max(c, r["gn"]), lambda r, c: max(c, r["t3"])]

    def msolve(T):
        cur = [r["g"] for r in M]
        if mg(cur) >= T:
            return cur, 0, 0.0
        for k, f in enumerate(msteps):
            nxt = [f(r, cur[i]) for i, r in enumerate(M)]
            if mg(nxt) >= T:
                fr = (T - mg(cur)) / (mg(nxt) - mg(cur)) if mg(nxt) > mg(cur) else 1
                return [cur[i] + fr * (nxt[i] - cur[i]) for i in range(len(M))], k + 1, 0.0
            cur = nxt
        rest = T - mg(cur)
        return [c + rest for c in cur], -1, rest
    mscen = []
    for T in (1.0, 2.0, 3.0, 4.0, 5.0):
        fin, at, rest = msolve(T)
        more = sum(r["va"] * (fin[i] - r["g"]) / 100 for i, r in enumerate(M))
        mscen.append({"mfg_target": f1(T), "stage": at, "rest": f1(rest),
                      "sectors": {r["name"]: f1(fin[i]) for i, r in enumerate(M)},
                      "va_increase_eok": won(sum(r["va"] * fin[i] / 100 for i, r in enumerate(M))), "more_than_trend_eok": won(more),
                      "final_demand_eok": won(more / k_eff), "grdp_contrib_pp": f1(msh * T / 100)})
    return {
        "기준": {"자료": "국가데이터처 「시도별 경제활동별 지역내총생산」(KOSIS), 한국은행 「2020년 지역산업연관표」", "기간": f"{y0}→{y1}년",
               "명목 GRDP(조 원)": f1(gdp_eok / 10000), "지난 10년 추세(%)": f1(base),
               "전국 GRDP 10년 연평균(%)": f1(cagr("전국", TOT) or 0),
               "17개 시도 GRDP 10년 성장 상위 세 곳 평균(%)": f1(sum(sorted([c for c in (cagr(r, TOT) for r in sido) if c], reverse=True)[:3]) / 3),
               "부가가치유발계수(수입품 제외 후)": f"{k_eff:.3f}", "제조업 GRDP 비중(%)": f1(msh),
               "제조업 업종 가중 10년 성장(%)": f1(mg([r["g"] for r in M])), "분야별 10년 추세 성장(%)": trend_fields},
        "단계(누적 GRDP 성장률)": stages,
        "목표별 시나리오": scen,
        "업종(비중·10년 성장·전국·상위3)": [{"업종": r["name"], "비중": f1(r["share"]), "10년": f1(r["g"]), "전국": f1(r["gn"]), "상위3": f1(r["t3"]),
                                     "부가가치 억 원": won(r["va"])} for r in rows],
        "제조업 목표별": mscen,
    }


PROMPT = """너는 대구 산업 통계를 정리하는 공무원용 자료 사이트의 해설 작성자다. 아래 [계산 결과]는 '성장 계산기' 페이지가 보여 주는 값이다.
이 값만 근거로 페이지 맨 위에 둘 해설을 JSON 하나로만 써라. 다른 문장 금지.
형식: {"headline": "40자 이내 결론 한 줄", "sections": [{"title": "전체 경로", "points": ["...", ...]}, {"title": "목표별로 보면", "points": [...]}, {"title": "제조업", "points": [...]}, {"title": "금액", "points": [...]}, {"title": "읽을 때 주의", "points": [...]}]}
규칙:
- 각 points 는 3~5개, 각 80자 이내, 개조식 명사형 종결(예: '…에 닿음', '…가 필요함'). 결론을 먼저.
- 숫자는 [계산 결과]에 있는 값을 그대로만 쓴다. 더하기·빼기·나누기로 새 숫자를 만들지 않는다. 단위(%, %p, 조 원, 억 원)를 붙인다.
- '상위 3개 시도'는 17개 시도 가운데 그 업종 10년 성장률이 높았던 세 곳의 평균이며 비교 기준이지 순위·평가가 아니라고 쓴다.
- 정책·기관·지자체에 대한 평가·비판·칭찬, 전망, 달성 가능성 판단('어렵다', '가능하다', '충분하다'), 권고('해야 한다')를 쓰지 않는다. 계산상 필요한 값은 '필요'로 쓴다.
- 특정 기업을 언급하지 않는다. 모르는 것은 쓰지 않는다.
- '읽을 때 주의'에는 업종 사이 파급을 넣지 않은 계산이라는 점, 2024년 가격 근사라는 점, 비중이 작은 업종·기반이 작은 시도의 값이 흔들린다는 점을 넣는다.
"""


def allowed_numbers(fx: dict) -> set[str]:
    s = json.dumps(fx, ensure_ascii=False)
    out = set()
    for m in re.findall(r"-?\d[\d,]*(?:\.\d+)?", s):
        v = m.replace(",", "").lstrip("-")
        out.add(v)
        if "." in v:
            out.add(v.rstrip("0").rstrip("."))
    return out


def check(text: str, ok: set[str]) -> list[str]:
    bad = []
    for m in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        v = m.replace(",", "")
        if v in ok or v.rstrip("0").rstrip(".") in ok:
            continue
        if "." not in v and (int(v) <= 20 or 2000 <= int(v) <= 2100):
            continue
        bad.append(m)
    return bad


def gemini(prompt: str) -> dict | None:
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2500, "responseMimeType": "application/json"}}
    for attempt in range(3):
        try:
            r = requests.post(GEMINI_URL, json=body, headers={"x-goog-api-key": GEMINI_KEY}, timeout=90)
            r.raise_for_status()
            out = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(re.sub(r"^```(json)?|```$", "", out.strip(), flags=re.M).strip())
        except Exception as e:  # noqa: BLE001
            print(f"[growth] Gemini {attempt + 1}차 실패: {str(e)[:200]}")
            time.sleep(3 * (attempt + 1))
    return None


def main(argv: list[str]) -> int:
    if "--approve" in argv:
        if not OUT.exists():
            print("해설 파일 없음")
            return 1
        d = json.loads(OUT.read_text(encoding="utf-8"))
        d["approved"] = True
        d["approved_on"] = date.today().isoformat()
        OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("승인함 — 페이지에 보입니다")
        return 0
    fx = facts()
    fx_text = json.dumps(fx, ensure_ascii=False, indent=1)
    h = hashlib.sha256(fx_text.encode()).hexdigest()[:16]
    if "--facts-only" in argv:
        print(fx_text)
        return 0
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if old.get("facts_hash") == h and "--force" not in argv:
        print("계산값이 같아 다시 쓰지 않음")
        return 0
    if not GEMINI_KEY:
        print("GEMINI_KEY 없음")
        return 0
    ok = allowed_numbers(fx)
    res, bad = None, []
    for attempt in range(2):
        extra = "" if not bad else f"\n\n앞선 답에 [계산 결과]에 없는 숫자가 있었다: {', '.join(bad[:10])}. 그 숫자를 빼고 다시 써라."
        res = gemini(f"{PROMPT}{extra}\n\n[계산 결과]\n{fx_text}")
        if not res:
            return 0
        text = res.get("headline", "") + " " + " ".join(p for s in res.get("sections", []) for p in s.get("points", []))
        bad = check(text, ok)
        if not bad:
            break
        print(f"[growth] 사실 묶음에 없는 숫자: {bad[:10]}")
    if bad:
        print("[growth] 숫자 검사를 통과하지 못해 저장하지 않음")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"headline": str(res.get("headline", ""))[:80], "sections": [
        {"title": str(s.get("title", ""))[:30], "points": [str(p)[:140] for p in s.get("points", [])][:6]} for s in res.get("sections", [])][:6],
        "model": GEMINI_MODEL, "generated": date.today().isoformat(), "facts_hash": h, "approved": False}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[growth] 해설 저장(승인 전): {OUT.relative_to(ROOT)}")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
