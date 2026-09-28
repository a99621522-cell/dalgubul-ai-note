#!/usr/bin/env python3
"""한국은행 「우리나라 주요 제조업 생산 및 공급망 지도」(2026.7) PDF → 표 3종 CSV (scripts/data/).

  bok_dependency.csv  ① 업종별 '특정국 의존도가 높은 품목' — 업종·구분·국가·품목·HS코드·금액(백만달러)·비중(%)
                        (자동차부품 장은 HS 표가 아니라 희소금속 표라 품목=금속(기호), HS코드 빈칸, 금액=총수입, 국가=주요 수입국)
  bok_multipliers.csv ② 권역별 유발계수(부록) — 권역·부문·생산/수입/부가가치/취업(명/10억원). 자료: 한국은행 지역산업연관표(2020)
  bok_region.csv      ③ 권역별 현황 — 업종별 권역 생산 점유율(2024, 각 장), 전국 업종 현황(요약, 생산·부가가치·고용·수출·사업체수 2014/2019/2024)
                        ※ 부록의 권역별 '사업체 수·고용(2024)' 그래프는 막대에 숫자가 없어 글자로 뽑히지 않는다(값 없음). 그래프 판독은 하지 않는다.

필요: poppler-utils(pdftotext). 값은 보고서 그대로, 평가 없음. 원본: docs/sources/bok_supplychain_2026-07.pdf (한국은행 홈페이지 공개 자료).
사용: python3 scripts/parse_bok_map.py [--pdf 경로] [--match]   # --match: 의존도 품목을 기업 사전 생산품과 키워드 대조해 표 출력
"""
import argparse, csv, os, re, subprocess, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "docs" / "sources" / "bok_supplychain_2026-07.pdf"
OUT = ROOT / "scripts" / "data"
SOURCE = "한국은행 「우리나라 주요 제조업 생산 및 공급망 지도」(2026.7)"

# 장(章)별 쪽 범위 → 업종. 각 장의 넷째 쪽이 '국가별 수입비중(의존도) 및 高의존도 품목' 표.
CHAPTERS = [("반도체", 8, 11), ("디스플레이", 12, 15), ("무선통신기기", 16, 19), ("자동차", 20, 23), ("자동차부품", 24, 27),
            ("철강", 28, 31), ("조선", 32, 35), ("석유정제", 36, 39), ("석유화학", 40, 43), ("기계장비", 44, 47), ("전기장비", 48, 52)]
DEP_PAGES = {11: "반도체", 15: "디스플레이", 19: "무선통신기기", 23: "자동차", 31: "철강", 35: "조선", 39: "석유정제", 43: "석유화학",
             47: "기계장비", 51: "전기장비", 52: "전기장비(이차전지)"}
RARE_PAGE = 27   # 자동차부품: 희소금속 표
PRIORITY = ["자동차부품", "자동차", "기계장비", "전기장비", "전기장비(이차전지)", "반도체"]
REGION_PAGES = range(54, 59)
SECTORS = ["석탄 및 석유제품", "기초 화학물질", "철강 1차제품", "반도체", "전자표시장치", "통신, 방송 및 영상, 음향기기", "컴퓨터 및 주변기기",
           "전기장비", "일반목적용 기계", "특수목적용 기계", "자동차", "선박"]
COUNTRIES = set("""중국 일본 미국 네덜란드 대만 독일 싱가포르 말레이시아 베트남 이스라엘 영국 인도네시아 프랑스 이탈리아 스위스 인도 태국 캐나다 호주
멕시코 브라질 칠레 남아공 러시아 사우디 카타르 쿠웨이트 오만 필리핀 스페인 스웨덴 오스트리아 벨기에 체코 폴란드 헝가리 튀르키예 홍콩 핀란드 덴마크
노르웨이 아일랜드 룩셈부르크 뉴질랜드 페루 아르헨티나 카자흐스탄 이집트 모로코 우크라이나 라오스 캄보디아 방글라데시 파키스탄 스리랑카 미얀마 마카오
아랍에미리트 UAE 슬로바키아 슬로베니아 루마니아 불가리아 포르투갈 그리스 리투아니아 에스토니아 라트비아 나이지리아 콩고 민주콩고 잠비아 짐바브웨
모잠비크 마다가스카르 가봉 가나 알제리 리비아 이란 이라크 바레인 요르단 파나마 콜롬비아 에콰도르 볼리비아 우루과이 베네수엘라 몽골 우즈베키스탄 네팔
브루나이 파푸아뉴기니 대만2) 기타""".split())
HS = re.compile(r"^\d{4}\.\d{2}-\d{4}$")
NUM = re.compile(r"^[\d,]+$")
FOOT = re.compile(r"(?<=\S)\d\)(\d\))*$|^\d\)(\d\))*$")


def run(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True).stdout


def words_of(pdf: Path, page: int) -> list[tuple]:
    html = run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), str(pdf), "-"])
    out = []
    for m in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', html):
        t = m.group(5).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        out.append((float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)), t))
    return out


def group_lines(ws: list[tuple], tol: float = 2.6) -> list[tuple[float, list]]:
    lines: list[tuple[float, list]] = []
    for w in sorted(ws, key=lambda w: (w[1], w[0])):
        if lines and abs(lines[-1][0] - w[1]) < tol:
            lines[-1][1].append(w)
        else:
            lines.append((w[1], [w]))
    return [(y, sorted(l, key=lambda w: w[0])) for y, l in lines]


def clean_item(s: str) -> str:
    s = re.sub(r"(?<=[가-힣A-Za-z)])\d\)(\d\))*", "", s)      # 각주 번호 3), 3)4)
    s = re.sub(r"\s+\d\)(\d\))*(?=\s|$)", "", s)
    s = re.sub(r"\s*\(\s*", "(", s).replace(" )", ")")
    return re.sub(r"\s+", " ", s).strip()


# ── ① 의존도 표(HS 코드형) ────────────────────────────────────────────────
def dep_tables(ws: list[tuple], page: int, industry: str) -> list[dict]:
    """표 머리 '국가 품목 / (주요 제품) HS코드 금액 비중' 낱말의 x 위치로 열을 정하고, 품목·HS·금액·비중을 y 순서로 짝짓는다."""
    heads = []
    for x0, y0, x1, y1, t in ws:
        if t != "국가":
            continue
        pm = [w for w in ws if abs(w[1] - y0) < 3 and 0 < w[0] - x1 < 45 and w[4].startswith("품목")]
        sub = [w for w in ws if abs(w[1] - y0) < 3 and w[0] > x0 - 5]
        hs_h = [w for w in sub if w[4] == "HS코드"]
        am_h = [w for w in sub if w[4] == "금액"]
        sh_h = [w for w in sub if w[4].startswith("비중")]
        if pm and hs_h and am_h and sh_h:
            hs_h, am_h, sh_h = (min(v, key=lambda w: w[0] - x0) for v in (hs_h, am_h, sh_h))   # 같은 줄에 옆 표 머리가 있으면 가까운 것
            heads.append({"x": x0, "y": y0, "xp": pm[0][0], "xh": hs_h[0], "xa1": am_h[2], "xs1": sh_h[2], "xs0": sh_h[0]})
    labels = []                                            # '[특정국 의존도가 높은 …]' — 같은 줄에 옆 표 라벨이 있어도 ']' 까지만
    for y, l in group_lines(ws):
        for i, w in enumerate(l):
            if w[4].startswith("["):
                buf = []
                for v in l[i:]:
                    buf.append(v[4])
                    if "]" in v[4]:
                        break
                labels.append((w[0], y, " ".join(buf)))
    anchors = sorted(w[0] for w in ws if w[4] == "품목" and any(abs(v[1] - w[1]) < 3 and 0 < v[0] - w[2] < 40 and v[4] == "(주요" for v in ws))
    notes = [(w[0], w[1]) for w in ws if w[4] in ("주:", "자료:")]
    rows = []
    for h in heads:
        hx, hy = h["x"], h["y"]
        below = [y for x, y in [(g["x"], g["y"]) for g in heads] + notes + [(x, y) for x, y, t in labels] if y > hy + 5 and abs(x - hx) < 150]
        y_end = min(below) if below else 10_000
        right = [x for x in anchors if x > h["xp"] + 60]
        x_end = min(right) - 35 if right else 10_000
        tw = [w for w in ws if w[1] > hy + 8 and w[1] < y_end - 1 and w[0] >= hx - 15 and w[0] < x_end]
        hs = sorted([w for w in tw if HS.match(w[4])], key=lambda w: w[1])
        if not hs:
            continue
        tw = [w for w in tw if w[1] <= hs[-1][1] + 6]                      # 마지막 HS 줄 아래(각주·다음 표 안내)는 버린다
        nums = [w for w in tw if NUM.match(w[4]) and w[0] > h["xh"] + 30 and w[2] <= h["xs1"] + 8]   # 비중 열 오른쪽의 순번 등은 제외
        amt = sorted([w for w in nums if abs(w[2] - h["xa1"]) <= abs(w[2] - h["xs1"])], key=lambda w: w[1])
        shr = sorted([w for w in nums if abs(w[2] - h["xa1"]) > abs(w[2] - h["xs1"])], key=lambda w: w[1])
        ctry = sorted([w for w in tw if w[0] < hx + 14 and w[4] in COUNTRIES], key=lambda w: w[1])
        prod = [w for w in tw if hx + 14 <= w[0] < h["xh"] - 3 and not HS.match(w[4])]
        items: list[tuple[float, str]] = []
        for y, l in group_lines(prod):
            t = " ".join(w[4] for w in l)
            if re.fullmatch(r"[\d)\s]*|[∙·ㆍ\s]+", t):
                continue                                   # 각주 번호·점 글자만 있는 줄
            prev = items[-1][1] if items else ""
            if items and (t.startswith("(") and y - items[-1][0] < 9.5 or prev.endswith(",") or prev.count("(") > prev.count(")")):
                items[-1] = (items[-1][0], prev + " " + t); continue
            items.append((y, t))
        while len(items) > len(hs):                        # 두 줄 품목명: HS 줄과 가장 먼 줄을 앞 줄에 붙인다
            gaps = [min(abs(y - g[1]) for g in hs) for y, _ in items]
            i = max(range(len(items)), key=lambda k: gaps[k])
            if i == 0:
                break
            items[i - 1] = (items[i - 1][0], items[i - 1][1] + " " + items[i][1]); del items[i]
        if os.environ.get("BOK_DEBUG") == f"{page}:{hy:.0f}":
            for name, seq in (("items", [(y, t) for y, t in items]), ("hs", [(w[1], w[4]) for w in hs]), ("amt", [(w[1], w[4]) for w in amt]), ("shr", [(w[1], w[4]) for w in shr])):
                print(name, [(round(y), t) for y, t in seq], file=sys.stderr)
        if not (len(items) == len(hs) == len(amt) == len(shr)):
            print(f"::warning::p{page} {industry} 표(머리 y={hy:.0f}) 칸 수 불일치 — 품목 {len(items)} HS {len(hs)} 금액 {len(amt)} 비중 {len(shr)} (y 로 짝지어 빈 칸은 check 표시)", file=sys.stderr)
        prev = [g["y"] for g in heads if g["y"] < hy - 5 and abs(g["x"] - hx) < 120]
        lab = sorted([(y, t) for x, y, t in labels if y < hy and abs(x - hx) < 150 and y > (max(prev) if prev else -1)])
        section = re.sub(r"^\[|\]$", "", lab[-1][1]).strip() if lab else ""
        section = re.sub(r"\]?\s*\(백만달러.*$", "", section).strip()
        # HS 줄을 기준으로 y 가 가까운 품목(같은 줄 또는 바로 위)·금액·비중을 짝짓는다
        used: set[int] = set()
        for k, hw in enumerate(hs):
            cand = [(hw[1] - y, i) for i, (y, _) in enumerate(items) if i not in used and -1.5 <= hw[1] - y <= 14]   # 품목 줄은 HS 줄과 같거나 조금 위
            item = ""
            if cand:
                i = min(cand)[1]; used.add(i); item = items[i][1]
            a = [w[4] for w in amt if abs(w[1] - hw[1]) < 3]
            sh = [w[4] for w in shr if abs(w[1] - hw[1]) < 3]
            c = [w[4] for w in ctry if w[1] <= hw[1] + 3]
            rows.append({"industry": industry, "section": section, "country": c[-1] if c else "", "item": clean_item(item),
                         "hs_code": hw[4], "amount_musd": (a[0] if a else "").replace(",", ""), "share_pct": (sh[0] if sh else "").replace(",", ""),
                         "page": page, "check": "" if item and a and sh else "원문 확인"})
    return rows


# ── ① 희소금속 표(자동차부품 장) ────────────────────────────────────────────
def rare_rows(pdf: Path, page: int) -> list[dict]:
    txt = run(["pdftotext", "-raw", "-f", str(page), "-l", str(page), str(pdf), "-"])
    txt = txt.replace("\n", " ")
    txt = re.sub(r"\s+", " ", txt)
    rows = []
    pat = re.compile(r"([가-힣〮]{1,6})(?:\d\))?\s+([\"“”]|[가-힣]+(?:\d\))?(?:\s[가-힣]+)?)\s+([A-Z][a-z]{0,2})\s+(.+?)\s+([\d,]+)\s+((?:[가-힣]+\(\d+\)[,\s]*){1,4})")
    sec = "희토류·백금족"
    for m in pat.finditer(txt):
        name, grp, sym, use, amt, imps = m.groups()
        name = re.sub(r"\d\)$|〮", "", name)
        if name in ("이름", "총수입") or len(use) > 60:
            continue
        if sym in ("Li",):
            sec = "기타 희소금속"
        for c, s in re.findall(r"([가-힣]+)\((\d+)\)", imps):
            rows.append({"industry": "자동차부품", "section": f"희소금속({sec})", "country": c, "item": f"{name}({sym})", "hs_code": "",
                         "amount_musd": amt.replace(",", ""), "share_pct": s, "page": page, "note": re.sub(r"\s*,\s*", ",", use)[:60]})
    return rows


# ── ② 유발계수 ────────────────────────────────────────────────────────────
def multipliers(pdf: Path) -> list[dict]:
    rows = []
    for p in REGION_PAGES:
        txt = run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), str(pdf), "-"])
        m = re.search(r"<(\S+?)>\s*주요 산업 현황", txt)
        if not m or "유발계수" not in txt:
            continue
        region = m.group(1)
        for ind, key in (("생산", "production"), ("수입", "import"), ("부가가치", "value_added"), ("취업(명/10억원)", "employment_per_bil_won")):
            mm = re.search(r"^\s*" + re.escape(ind) + r"\s+((?:\d+\.\d+\s+){11}\d+\.\d+)", txt, re.M)
            if not mm:
                print(f"::warning::p{p} {region} 유발계수 {ind} 행 없음", file=sys.stderr); continue
            vals = mm.group(1).split()
            for s, v in zip(SECTORS, vals):
                rows.append({"region": region, "sector": s, "indicator": ind, "value": v, "page": p})
    return rows


# ── ③ 권역·전국 현황 ──────────────────────────────────────────────────────
def region_rows(pdf: Path) -> list[dict]:
    rows = []
    seen = set()
    for ind, a, b in CHAPTERS:
        for p in range(a, b + 1):
            txt = run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), str(pdf), "-"])
            for m in re.finditer(r"<(수도권|충청권|호남권|대경권|동남권)( 등\d\))?>\s*생산\s*([\d.]+)%", txt):
                if (ind, m.group(1)) in seen:
                    continue
                seen.add((ind, m.group(1)))
                rows.append({"type": "권역 생산 점유율", "industry": ind, "region": m.group(1) + (" 등" if m.group(2) else ""), "item": "생산 점유율",
                             "year": "2024", "value": m.group(3), "unit": "%", "page": p, "note": "각 장 '권역별 생산 점유율 및 주요 공장 현황'" + (" (등: 대경권·제주·강원 등 합산)" if m.group(2) else "")})
    txt = run(["pdftotext", "-raw", "-f", "7", "-l", "7", str(pdf), "-"])
    cur = None
    for line in txt.split("\n"):
        m = re.match(r"^(\S+) 2014 2019 2024$", line)
        if m:
            cur = m.group(1); continue
        if cur and re.match(r"^(생산|부가가치|고용|수출|사업체수)$", line.strip()):
            key = line.strip(); continue
        if cur and re.match(r"^[\$\d]", line):
            vals = re.findall(r"\$?([\d,.]+)(조원|만명|억|개)?", line)
            if len(vals) == 3 and "key" in dir():
                unit = {"조원": "조원", "만명": "만명", "억": "억달러", "개": "개"}.get(vals[0][1], "")
                for y, (v, _) in zip(("2014", "2019", "2024"), vals):
                    rows.append({"type": "전국 업종 현황", "industry": cur, "region": "전국", "item": key, "year": y, "value": v.replace(",", ""), "unit": unit, "page": 7, "note": "요약 '주요 제조업 현황'(수출은 2025)" if key == "수출" else "요약 '주요 제조업 현황'"})
        elif cur and line.startswith("["):
            shares = re.findall(r"\[([\d.]+)%\]", line)
            if len(shares) == 3:
                for y, v in zip(("2014", "2019", "2024"), shares):
                    rows.append({"type": "전국 업종 현황", "industry": cur, "region": "전국", "item": key + " 비중(제조업 대비)", "year": y, "value": v, "unit": "%", "page": 7, "note": "요약 '주요 제조업 현황'"})
    txt6 = run(["pdftotext", "-raw", "-f", "6", "-l", "6", str(pdf), "-"])
    for m in re.finditer(r"<(수도권|충청권|호남권|대경권|동남권)>[^\d]*([\d.]+)%", txt6):
        rows.append({"type": "권역 제조업 생산 비중", "industry": "제조업 전체", "region": m.group(1), "item": "생산 비중(전국 대비)", "year": "2024", "value": m.group(2), "unit": "%", "page": 6, "note": "요약 '제조업의 권역간 분포'"})
    return rows


def write(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    print(f"{path.relative_to(ROOT)}: {len(rows)}행")


# ── 대구 기업 사전 대조 ─────────────────────────────────────────────────────
GENERIC = set("기타 부품 부분품 제품 장치 장비 등 및 과 와 기기 소재 원료 부속품 기계류 화합물 어셈블리 모듈 시스템 유닛 신품 완제품 반가공 미가공".split())
MODIFIER = re.compile(r"^(자동차|차량|승용차|산업|가정|전기차|반도체|디스플레이|선박|건물|가구|통신|전동|수지식|일반|특수)용$|^(기타차량의|승용차|차량용|자동차용)$")


def keywords(item: str) -> list[str]:
    """품목명에서 대조에 쓸 핵심 낱말: 괄호 안 조건은 버리고, '자동차용'·'기타' 같은 수식어를 뺀 나머지.
    '자동차용 나선용 스프링' → ['스프링'], '롤러베어링(니들)' → ['롤러베어링'], '장착구·부착구' → ['장착구', '부착구']."""
    base = re.sub(r"\(.*?\)", " ", item)
    toks = []
    for part in re.split(r"[\s,/&]+", base):
        for t in re.split(r"[·∙ㆍ]", part):
            t = re.sub(r"[^가-힣A-Za-z0-9]", "", t)
            if len(t) >= 1 and t not in GENERIC and not MODIFIER.match(t):
                toks.append(t)
    return toks or [re.sub(r"\s+", "", base)]


def hit(kws: list[str], prod: str, prod_tokens: set[str]) -> bool:
    joined = "".join(kws)
    if len(joined) >= 3 and joined in prod:
        return True
    for k in kws:
        if len(k) >= 3 and k in prod:
            return True
        if len(k) <= 2 and k in prod_tokens:
            return True
    return False


def match_daegu(dep: list[dict]) -> list[dict]:
    comp = list(csv.DictReader(open(ROOT / "scripts" / "data" / "dalseong_companies.csv", encoding="utf-8")))
    prods = []
    for c in comp:
        raw = c.get("product") or ""
        toks = {re.sub(r"[^가-힣A-Za-z0-9]", "", t) for t in re.split(r"[\s,、/·∙ㆍ()\[\]]+", raw)}
        prods.append((c["name"], re.sub(r"\s+", "", raw), toks, c.get("sector_group", ""), c.get("district", "")))
    out = []
    seen = set()
    for r in dep:
        key = (r["industry"], r["item"])
        if key in seen:
            continue
        seen.add(key)
        kws = keywords(r["item"])
        hits = [(name, grp, dist) for name, prod, toks, grp, dist in prods if prod and hit(kws, prod, toks)]
        out.append({**r, "keywords": " ".join(kws), "daegu_companies": len(hits), "has_daegu_producer": "있음" if hits else "없음",
                    "examples": "; ".join(f"{n}({g},{d})" for n, g, d in hits[:3])})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(PDF))
    ap.add_argument("--match", action="store_true")
    a = ap.parse_args()
    pdf = Path(a.pdf)
    if not pdf.exists():
        print(f"PDF 없음: {pdf}"); return 1
    dep = []
    for p, ind in sorted(DEP_PAGES.items()):
        dep.extend(dep_tables(words_of(pdf, p), p, ind))
    dep.extend(rare_rows(pdf, RARE_PAGE))
    for r in dep:
        r["priority"] = "우선" if r["industry"] in PRIORITY else ""
        r["source"] = SOURCE
    dep.sort(key=lambda r: (PRIORITY.index(r["industry"]) if r["industry"] in PRIORITY else 99, r["page"], r["section"], -float((r["share_pct"] or "0").replace(",", ""))))
    write(OUT / "bok_dependency.csv", dep, ["industry", "priority", "section", "country", "item", "hs_code", "amount_musd", "share_pct", "note", "check", "page", "source"])
    mult = multipliers(pdf)
    for r in mult:
        r["source"] = SOURCE + " 부록, 한국은행 지역산업연관표(2020)"
    write(OUT / "bok_multipliers.csv", mult, ["region", "sector", "indicator", "value", "page", "source"])
    reg = region_rows(pdf)
    for r in reg:
        r["source"] = SOURCE
    write(OUT / "bok_region.csv", reg, ["type", "industry", "region", "item", "year", "value", "unit", "note", "page", "source"])
    if a.match:
        m = match_daegu(dep)
        write(OUT / "bok_dependency_daegu.csv", m, ["industry", "priority", "section", "country", "item", "hs_code", "amount_musd", "share_pct", "keywords", "has_daegu_producer", "daegu_companies", "examples", "page"])
        print("\n## 특정국 의존도가 높은 품목 × 대구 기업 사전(생산품 키워드 일치, 참고용)\n")
        for ind in PRIORITY + sorted({r["industry"] for r in m} - set(PRIORITY)):
            rs = [r for r in m if r["industry"] == ind]
            if not rs:
                continue
            yes = [r for r in rs if r["has_daegu_producer"] == "있음"]
            print(f"### {ind} — 품목 {len(rs)}개, 대구 안에 생산 기업이 있는 품목 {len(yes)}개 / 없는 품목 {len(rs) - len(yes)}개\n")
            print("| 구분 | 국가 | 품목 | HS코드 | 금액(백만$) | 비중(%) | 대구 생산 기업 | 예(기업명(산업그룹,구군)) |\n|---|---|---|---|---:|---:|---|---|")
            for r in sorted(rs, key=lambda r: (r["has_daegu_producer"] != "있음", -float((r["share_pct"] or "0").replace(",", "")))):
                print(f"| {r['section']} | {r['country']} | {r['item']} | {r['hs_code']} | {r['amount_musd']} | {r['share_pct']} | {r['has_daegu_producer']}({r['daegu_companies']}) | {r['examples']} |")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
