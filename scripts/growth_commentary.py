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
# src/lib/grdp.ts 의 LEAVES·HIGH 와 같게 유지(산업구조지수 리포트 scripts/structure_index.py 와 같은 25개 부문)
LEAVES = [("농업 임업 및 어업", "농림어업"), ("광업", "광업"), ("음식료품 및 담배제조업", "음식료품·담배"), ("섬유 의복 및 가죽 제품 제조업", "섬유·의복·가죽"),
          ("목재종이인쇄 및 복제업", "목재·종이·인쇄"), ("석탄 및 석유 화학제품 제조업", "석탄·석유·화학"), ("비금속광물 및 금속제품 제조업", "비금속·금속"),
          ("전기 전자 및 정밀기기 제조업", "전기·전자·정밀기기"), ("기계 운송장비 및 기타 제품 제조업", "기계·운송장비·기타"), ("전기 가스 증기 및 공기 조절 공급업", "전기·가스"),
          ("수도 하수 및 폐기물 처리 원료 재생업", "수도·폐기물"), ("건설업", "건설업"), ("도매 및 소매업", "도소매"), ("운수 및 창고업", "운수·창고"), ("숙박 및 음식점업", "숙박·음식점"),
          ("정보통신업", "정보통신"), ("금융 및 보험업", "금융·보험"), ("부동산업", "부동산"), ("전문 과학 및 기술 서비스업", "전문·과학·기술"),
          ("사업시설 관리 사업 지원 및 임대 서비스업", "사업시설·지원"), ("공공 행정 국방 및 사회보장 행정", "공공행정"), ("교육 서비스업", "교육"),
          ("보건업 및 사회복지 서비스업", "보건·사회복지"), ("예술 스포츠 및 여가관련 서비스", "예술·스포츠·여가"), ("협회 및 단체 수리 및 기타 개인 서비스업", "협회·수리·개인")]
HIGH = ["전기 전자 및 정밀기기 제조업", "정보통신업", "금융 및 보험업"]
MFG = [k for k, _ in LEAVES[2:9]]


def f1(v: float) -> str:
    return f"{v:.1f}"


def facts() -> dict:
    """페이지(src/components/GrowthStructure.astro)와 같은 계산"""
    rep = json.loads((ROOT / "data/kosis/structure_report.json").read_text(encoding="utf-8"))
    y0, y1 = rep["years"]
    d = rep["data"]
    V: dict[tuple, float] = {}
    regions = set()
    for r in csv.DictReader(open(ROOT / "data/kosis/grdp-sido-industry-all.csv", encoding="utf-8")):
        try:
            V[(r["ITM_NM"], r["C1_NM"], r["C2_NM"], int(r["PRD_DE"]))] = float(r["DT"])
            regions.add(r["C1_NM"])
        except ValueError:
            pass
    n = y1 - y0

    def cagr(reg, k):
        a, b = V.get(("실질", reg, k, y0)), V.get(("실질", reg, k, y1))
        return ((b / a) ** (1 / n) - 1) * 100 if a and b and a > 0 and b > 0 else None
    tot = sum(V.get(("명목", REGION, k, y1), 0) for k, _ in LEAVES)
    ntot = sum(V.get(("명목", "전국", k, y1), 0) for k, _ in LEAVES)
    sido = [r for r in regions if r != "전국"]
    rows = []
    for k, nm in LEAVES:
        va = V.get(("명목", REGION, k, y1), 0)
        if va <= 0:
            continue
        s, ns = va / tot * 100, V.get(("명목", "전국", k, y1), 0) / ntot * 100
        cs = sorted([c for c in (cagr(r, k) for r in sido) if c is not None], reverse=True)
        g = cagr(REGION, k) or 0.0
        rows.append({"key": k, "name": nm, "s": s, "lq": s / ns if ns else 0, "g": g, "gn": cagr("전국", k) if cagr("전국", k) is not None else g,
                     "t3": sum(cs[:3]) / min(3, len(cs)) if cs else g, "high": k in HIGH, "mfg": k in MFG, "spec": ns > 0 and s / ns >= 1})
    base = d["grdp_growth"]["대구"]
    io = json.loads((ROOT / "scripts/data/bok_io_daegu.json").read_text(encoding="utf-8"))
    va_in = next(r["within"] for r in io["final_demand"] if r["region"] == "대구" and r["type"] == "부가가치유발계수" and r["year"] == 2020)
    imp = float(re.search(r"수입\s*([\d.]+)%", next(f["text"] for f in io["facts"] if re.search(r"표 IV-7.*대구", f["text"]))).group(1))
    k_eff = (1 - imp / 100) * va_in
    gdp = V[("명목", REGION, TOT, y1)] / 100   # 억 원
    growth = lambda gs: base + sum(r["s"] / 100 * (gs[i] - r["g"]) for i, r in enumerate(rows))

    def nxt(gs):
        w = [r["s"] * (1 + gs[i] / 100) for i, r in enumerate(rows)]
        t = sum(w)
        return [x / t * 100 for x in w]

    def high_share(gs):
        return sum(x for x, r in zip(nxt(gs), rows) if r["high"])

    def years_to_nat(gs):
        sh = [r["s"] for r in rows]
        for y in range(1, 61):
            w = [x * (1 + gs[i] / 100) for i, x in enumerate(sh)]
            t = sum(w)
            sh = [x / t * 100 for x in w]
            if sum(x for x, r in zip(sh, rows) if r["high"]) >= d["daegu"]["high_share_nat"][str(y1)]:
                return y
        return None
    P = {"추세 그대로": lambda r: r["g"], "감소 업종 멈춤": lambda r: max(r["g"], 0), "전국보다 낮은 업종 → 전국 수준": lambda r: max(r["g"], r["gn"]),
         "고부가 3부문 → 상위 3개 시도 수준": lambda r: max(r["g"], r["t3"]) if r["high"] else r["g"],
         "제조업 → 상위 3개 시도 수준": lambda r: max(r["g"], r["t3"]) if r["mfg"] else r["g"], "모든 업종 → 상위 3개 시도 수준": lambda r: max(r["g"], r["t3"])}
    presets = []
    for nm, f in P.items():
        gs = [f(r) for r in rows]
        y = years_to_nat(gs)
        presets.append({"시나리오": nm, "성장률": f"{growth(gs):.2f}" if nm == "추세 그대로" else f1(growth(gs)), "다음 해 고부가 비중": f1(high_share(gs)),
                        "고부가 비중 전국 수준까지": f"{y}년" if y else "60년 넘음"})
    groups = {"모든 업종": lambda r: True, "고부가 3부문만": lambda r: r["high"], "제조업만": lambda r: r["mfg"], "특화 부문만": lambda r: r["spec"]}
    route = []
    for T in (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0):
        E = T - base
        cells = {}
        for gname, f in groups.items():
            rs = [r for r in rows if f(r)]
            sh = sum(r["s"] for r in rs)
            avg = sum(r["s"] * r["g"] for r in rs) / sh
            cells[gname] = {"필요 성장률": f1(avg + E / sh * 100), "추세보다": f1(E / sh * 100)}
        route.append({"목표": f1(T), "길": cells, "GRDP 한 해 증가(조 원)": f1(gdp * T / 100 / 10000), "추세보다 더(조 원)": f1(gdp * E / 100 / 10000),
                      "필요 최종수요(조 원)": f1(gdp * E / 100 / k_eff / 10000)})
    sh = lambda f: f1(sum(r["s"] for r in rows if f(r)))
    return {"기간": f"{y0}→{y1}년", "추세(연평균, %)": f"{base:.2f}", "전국(%)": f"{d['grdp_growth']['전국']:.2f}", "6개 광역시 평균(%)": f"{d['metro6_avg']['grdp']:.2f}",
            "17개 시도 GRDP 성장 상위 3곳 평균(%)": f1(sum(sorted([v for k, v in d["grdp_growth"].items() if k != "전국"], reverse=True)[:3]) / 3),
            "명목 GRDP(조 원)": f1(gdp / 10000), "고부가 3부문 비중(%)": f1(d["daegu"]["high_share"][str(y1)]), "전국 고부가 비중(%)": f1(d["daegu"]["high_share_nat"][str(y1)]),
            "산업집중도": d["hhi_2024"]["대구"], "17개 시도 산업집중도 평균": d["hhi_avg"], "패널 추정 산업집중도 계수": f"{d['panel']['GRDP']['Δln(산업집중도)']['coef']:.2f}",
            "묶음 비중(%)": {"고부가 3부문": sh(lambda r: r["high"]), "제조업": sh(lambda r: r["mfg"]), "특화 부문": sh(lambda r: r["spec"])},
            "부가가치유발계수(수입품 제외 후)": f"{k_eff:.3f}", "시나리오": presets, "목표별 길": route}


def render(fx: dict) -> str:
    L = [f"자료: 국가데이터처 지역소득(KOSIS), 산업구조지수 리포트와 같은 정의 · 기간 {fx['기간']}",
         f"- 대구 실질 GRDP 연평균 성장률(추세) {fx['추세(연평균, %)']}%. 같은 기간 전국 {fx['전국(%)']}%, 6개 광역시 평균 {fx['6개 광역시 평균(%)']}%, 17개 시도 가운데 성장이 높았던 세 곳 평균 {fx['17개 시도 GRDP 성장 상위 3곳 평균(%)']}%. 명목 GRDP {fx['명목 GRDP(조 원)']}조 원.",
         f"- 산업구조: 고부가 3부문(전기·전자·정밀기기, 정보통신, 금융보험) 비중 {fx['고부가 3부문 비중(%)']}%(전국 {fx['전국 고부가 비중(%)']}%), 산업집중도 {fx['산업집중도']}(17개 시도 평균 {fx['17개 시도 산업집중도 평균']}). 리포트 패널 추정에서 산업집중도 1% 상승은 성장률 +{fx['패널 추정 산업집중도 계수']}%p 와 함께 움직였다(연관).",
         "- 묶음 비중(부가가치): " + ", ".join(f"{k} {v}%" for k, v in fx["묶음 비중(%)"].items()),
         "- 시나리오(단추, 추세에서 새로 시작 → 한 해 성장률, 다음 해 고부가 비중, 같은 성장률이 이어질 때 고부가 비중이 전국 수준에 닿는 데 걸리는 해):"]
    L += [f"  {x['시나리오']}: 성장률 {x['성장률']}%, 다음 해 고부가 비중 {x['다음 해 고부가 비중']}%, 전국 수준까지 {x['고부가 비중 전국 수준까지']}" for x in fx["시나리오"]]
    L.append("- 목표에 닿는 길(추세와 목표의 차이를 한 묶음만 더 성장해 메울 때 그 묶음의 필요 성장률(추세보다 더할 몫), 금액):")
    for x in fx["목표별 길"]:
        L.append(f"  목표 {x['목표']}%: " + ", ".join(f"{g} {c['필요 성장률']}%(+{c['추세보다']}%p)" for g, c in x["길"].items())
                 + f". GRDP 한 해 {x['GRDP 한 해 증가(조 원)']}조 원 증가(추세보다 {x['추세보다 더(조 원)']}조 원 더), 새 지출로 만든다면 필요한 대구 최종수요 {x['필요 최종수요(조 원)']}조 원.")
    L.append(f"- 금액 환산 계수: 대구 부가가치유발계수(수입품 제외 후) {fx['부가가치유발계수(수입품 제외 후)']}")
    return "\n".join(L)


PROMPT = """너는 대구 산업 통계를 정리하는 공무원용 자료 사이트의 해설 작성자다. 아래 [계산 결과]는 '성장 계산기' 페이지가 보여 주는 값이며, 정의는 같은 사이트의 산업구조지수 리포트와 같다.
읽는 사람은 대구시·구청 공무원이다. '어느 업종 묶음이 몇 % 성장해야 목표가 되는지'와 '그때 산업구조(고부가 비중·집중도)가 어떻게 되는지'를 바로 알게 써라.
JSON 하나로만 답하라. 다른 문장 금지.
형식: {"headline": "...", "sections": [{"title": "한눈에", "points": [...]}, {"title": "목표별로 보면", "points": [...]}, {"title": "산업구조로 보면", "points": [...]}, {"title": "금액으로", "points": [...]}, {"title": "읽을 때 주의", "points": [...]}]}
쓰는 법:
- headline: 45자 이내. 가장 중요한 결론 하나.
- points: 섹션마다 3~4개, 각 90자 이내, 개조식 명사형 종결('…가 필요함', '…임'). '조건 → 결과' 또는 비교로 쓴다(숫자 나열 금지).
- '한눈에': 추세와 전국·6개 광역시 비교, '모든 업종 → 상위 3개 시도 수준' 시나리오의 성장률.
- '목표별로 보면': 목표 3.0%·5.0%에서 묶음별 필요 성장률 비교(비중이 작은 묶음일수록 높음).
- '산업구조로 보면': 고부가 비중(지금·전국)과 시나리오별 전국 수준까지 걸리는 해, 산업집중도와 리포트 패널 추정은 '연관'이라고 쓴다.
- '금액으로': 목표별 GRDP 증가액, 추세보다 더, 필요한 최종수요.
- 숫자는 [계산 결과]에 적힌 값을 그대로만 쓴다(새로 더하거나 나누어 만든 숫자 금지). 단위는 %, %p, 조 원, 년. 'pp', '(%)' 표기 금지.
- '상위 3개 시도'는 17개 시도 가운데 그 업종 성장률이 높았던 세 곳의 평균인 비교 기준이며 순위·평가가 아님을 한 번 밝힌다.
- 정책·기관 평가·비판·칭찬, 전망, 달성 가능성 판단('어렵다', '가능하다', '현실적'), 권고('해야 한다', '바람직')를 쓰지 않는다. 특정 기업을 쓰지 않는다.
- '읽을 때 주의': 업종 사이 파급을 넣지 않은 계산, 그 해 가격 근사, 비중이 작은 업종과 기반이 작은 시도의 값이 크게 흔들림, 가정에 따른 계산이지 전망이 아님.
"""

def allowed_numbers(s: str) -> set[str]:
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
    fx_text = render(fx)
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
    ok = allowed_numbers(fx_text)
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
