#!/usr/bin/env python3
"""산업연관표 상품 기본부문(380) ↔ 한국표준산업분류(KSIC 10차 세세분류) 자동 연계표 만들기.

한국은행이 공개하는 파일(ECOS 2020 상품부문분류표·산업부문분류표)에는 KSIC 대응 열이 없다. 그래서 이 스크립트가
  (1) KSIC 대분류(2자리) → 허용되는 상품 중분류 목록(아래 DIV_MAP, 손으로 정한 표)
  (2) 그 안에서 KSIC 세세분류 이름과 상품 기본부문 이름의 글자 겹침(2글자 조각 Jaccard + 낱말 포함)
로 세세분류마다 가장 비슷한 기본부문을 고른다. 비슷한 정도가 낮으면 같은 중분류의 '기타' 부문(없으면 첫 부문)에 붙이고 '폴백' 으로 표시한다.
결과: scripts/data/io/io_ksic_map_auto.xlsx (attract.py 의 부문분류표 형식: 기본부문 코드 · 상품명 · 한국표준산업분류 열)
      + io_ksic_map_auto.csv (검토용: KSIC 코드·이름 → 부문, 점수, 방식)
KSIC 세세분류 코드·이름은 기업 사전(scripts/sites.py load_all_companies)에 나온 것만 쓴다(대구 기업이 쓰는 코드 전부).
**추정 연계표다.** 공식 연계표(ISTANS 산업분류 연계표 등)를 구하면 같은 폴더에 넣고 이 파일을 지우면 attract.py 가 그것을 쓴다.
사용: python3 scripts/build_io_ksic_map.py [--min-score 0.25]
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sites import load_all_companies  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
IO = ROOT / "scripts" / "data" / "io"
CLS = IO / "ecos_2020_상품부문분류표_기본380_소165_중83_대33.xlsx"
OUT_X = IO / "io_ksic_map_auto.xlsx"
OUT_C = IO / "io_ksic_map_auto.csv"

# KSIC 10차 대분류(2자리) → 상품 중분류(2자리) 후보. 제조업은 산업연관표 부문 순서가 KSIC 와 거의 같아 1:1~1:5 로 좁힌다.
DIV_MAP = {
    "01": ["01", "02", "05"], "02": ["03"], "03": ["04"], "05": ["06"], "06": ["07"], "07": ["07"], "08": ["07"],
    "10": ["08"], "11": ["09"], "12": ["10"], "13": ["11", "19"], "14": ["11"], "15": ["12"], "16": ["13"], "17": ["14"], "18": ["15"],
    "19": ["16"], "20": ["17", "18", "19", "21", "22"], "21": ["20"], "22": ["23", "24"], "23": ["25", "26"], "24": ["27", "28", "29"],
    "25": ["30"], "26": ["31", "32", "33", "34", "35"], "27": ["36"], "28": ["37"], "29": ["38", "39"], "30": ["40"], "31": ["41", "42"],
    "32": ["43"], "33": ["43", "44"], "34": ["44"], "35": ["45", "46"], "36": ["47"], "37": ["48"], "38": ["49"], "39": ["49"],
    "41": ["50", "51"], "42": ["50", "51"], "45": ["52", "82"], "46": ["52"], "47": ["52"], "49": ["53"], "50": ["54"], "51": ["55"],
    "52": ["56"], "53": ["57"], "55": ["58"], "56": ["58"], "58": ["63", "62"], "59": ["64"], "60": ["60"], "61": ["59"], "62": ["62"],
    "63": ["61", "62"], "64": ["65"], "65": ["66"], "66": ["67"], "68": ["68", "69"], "70": ["70"], "71": ["71"], "72": ["72"], "73": ["72"],
    "74": ["72"], "75": ["73", "74"], "76": ["73"], "84": ["75"], "85": ["76"], "86": ["77"], "87": ["78"], "90": ["79"], "91": ["80"],
    "94": ["81"], "95": ["82"], "96": ["82"],
}
# KSIC 10차 코드 접두어 → 상품 기본부문. 긴 접두어부터 맞춘다. 5대 클러스터(자동차부품·일반기계·전기장비·섬유·의료기기)와
# 이름만으로 잘못 붙기 쉬운 부문(주물·방적·염색·금속가공·1차금속·전자부품)을 손으로 정했다. 여기 없는 코드는 이름 겹침으로.
RULES = {
    # 자동차(30) · 운송장비(31)
    "3011": "4031", "3012": "4011", "30201": "4021", "30202": "4022", "303": "4032",
    "31111": "4101", "31112": "4102", "31113": "4103", "3112": "4102", "312": "4210", "313": "4220", "3191": "4299", "3192": "4291", "3199": "4299",
    # 기계(29)
    "2911": "3810", "2912": "3820", "2913": "3831", "2914": "3832", "2915": "3899", "2916": "3840",
    "29171": "3851", "29172": "3851", "29173": "3851", "29174": "3851", "29175": "3852", "29176": "3852", "29177": "3899",
    "2918": "3891", "2919": "3899", "2921": "3911", "2922": "3920", "2923": "3920", "2924": "3912", "2925": "3991", "2926": "3992",
    "29271": "3941", "29272": "3942", "2928": "3993", "29291": "3995", "29292": "3994", "29293": "3930", "29294": "3994", "29299": "3999",
    # 전기장비(28)
    "28111": "3710", "28112": "3721", "28113": "3722", "28119": "3722", "28121": "3723", "28122": "3723", "28123": "3724",
    "282": "3730", "283": "3740", "2841": "3791", "2842": "3792", "28511": "3752", "28512": "3752", "28519": "3759", "2852": "3752", "289": "3799",
    # 의료·정밀(27)
    "271": "3611", "27215": "3613", "27216": "3613", "2721": "3612", "273": "3691", "274": "3692",
    # 전자(26)
    "2611": "3102", "26121": "3101", "26129": "3101", "26211": "3201", "2621": "3209", "2622": "3310",
    "26291": "3391", "26292": "3391", "26294": "3391", "2629": "3399", "2631": "3401", "2632": "3402", "2633": "3409",
    "2641": "3511", "26422": "3512", "2642": "3519", "2651": "3521", "26521": "3523", "2652": "3522", "266": "3399",
    # 금속가공(25) · 1차금속(24)
    "25111": "3011", "2511": "3012", "25121": "3014", "25122": "3013", "25123": "3013", "2513": "3014", "252": "3099",
    "25911": "3021", "25912": "3021", "25913": "3022", "2592": "3031", "2593": "3093", "25941": "3094", "25942": "3099",
    "25991": "3095", "2599": "3099",
    "24111": "2711", "24112": "2713", "24113": "2712", "24121": "2725", "24122": "2730", "24123": "2726", "24129": "2799",
    "2413": "2727", "24191": "2791", "2419": "2799", "24211": "2811", "24212": "2812", "24213": "2813", "2421": "2819",
    "24221": "2821", "24222": "2822", "2422": "2829", "2431": "2900", "2432": "2900",
    # 섬유·의복·가죽(13~15)
    "13104": "1119", "1310": "1111", "1321": "1121", "13221": "1141", "13222": "1141", "13224": "1141", "1322": "1141",
    "133": "1123", "134": "1130", "1391": "1149", "1392": "1149", "13993": "1122", "1399": "1149",
    "1441": "1152", "1449": "1155", "142": "1154", "14": "1151",
    "1511": "1201", "1512": "1201", "15129": "1203", "1519": "1203", "152": "1204",
    # 가구·기타(32·33) · 수리(34)
    "32011": "4319", "32019": "4319", "32021": "4311", "32022": "4312", "3202": "4319", "3209": "4319",
    "3311": "4395", "3312": "4395", "332": "4393", "333": "4392", "334": "4391", "3391": "4399", "3392": "4394", "3393": "4396", "3399": "4399",
    "34": "4402",
}
STOP = ("제조업", "제조", "업", "및", "기타", "그외", "그 외", "외", "종", "제품", "용", "서비스")


def norm(s: str) -> str:
    s = re.sub(r"\(.*?\)", " ", str(s or ""))
    s = re.sub(r"\s*외\s*\d+\s*종", " ", s)
    for w in STOP:
        s = s.replace(w, " ")
    return re.sub(r"[\s·ㆍ,.\-/]+", " ", s).strip()


def grams(s: str) -> set:
    t = s.replace(" ", "")
    return {t[i:i + 2] for i in range(len(t) - 1)} if len(t) > 1 else {t}


def score(k: str, p: str) -> float:
    a, b = grams(k), grams(p)
    if not a or not b:
        return 0.0
    j = len(a & b) / len(a | b)
    kw = {w for w in k.split() if len(w) >= 2}
    pw = {w for w in p.split() if len(w) >= 2}
    bonus = 0.3 * len(kw & pw) / max(1, len(pw))
    return j + bonus


def load_products():
    import pandas as pd
    df = pd.read_excel(CLS, header=None)
    cur = [None] * 4
    out = []
    for r in df.iloc[3:].values.tolist():
        for k, (ci, ni) in enumerate([(0, 1), (2, 3), (4, 5), (6, 7)]):
            if str(r[ci]) != "nan":
                cur[k] = (str(r[ci]).strip(), str(r[ni]).strip())
        if str(r[0]) != "nan" and re.fullmatch(r"\d{4}", str(r[0]).strip()) and cur[2] and re.fullmatch(r"\d{2}", cur[2][0]):
            out.append({"code": cur[0][0], "name": cur[0][1], "sub": cur[1], "mid": cur[2][0], "mid_name": cur[2][1], "top": cur[3]})
    return out


def main(argv: list[str]) -> int:
    min_score = float(argv[argv.index("--min-score") + 1]) if "--min-score" in argv else 0.25
    prods = load_products()
    by_mid = defaultdict(list)
    by_code = {p["code"]: p for p in prods}
    for p in prods:
        by_mid[p["mid"]].append(p)
    ksic = {}
    for r in load_all_companies():
        c = str(r.get("sector_code", "")).strip()
        if re.fullmatch(r"\d{5}", c) and c not in ksic:
            ksic[c] = str(r.get("sector", "")).strip()
    rows, method = [], Counter()
    for code, name in sorted(ksic.items()):
        cands = [p for m in DIV_MAP.get(code[:2], []) for p in by_mid.get(m, [])]
        if not cands:
            rows.append({"ksic": code, "ksic_name": name, "io": "", "io_name": "", "score": 0, "method": "대분류 미대응"})
            method["대분류 미대응"] += 1
            continue
        kn = norm(name)
        rule = next((RULES[code[:n]] for n in (5, 4, 3, 2) if code[:n] in RULES), None)
        if rule and rule in by_code:
            best, s, how = by_code[rule], 1.0, "접두어 규칙"
        else:
            best = max(cands, key=lambda p: score(kn, norm(p["name"])))
            s = score(kn, norm(best["name"]))
            how = "이름 일치"
            if s < min_score:
                # 대분류 밖에서도 이름이 뚜렷이 맞으면(옛 KSIC 판 코드 등) 그쪽으로
                g = max((p for p in prods if "08" <= p["mid"] <= "44"), key=lambda p: score(kn, norm(p["name"])))
                gs = score(kn, norm(g["name"])) if "10" <= code[:2] <= "34" else 0.0   # 제조업 코드(옛 판 포함)만
                if gs >= 0.5:
                    best, s, how = g, gs, "이름 일치(대분류 밖)"
                else:
                    mids = DIV_MAP[code[:2]]
                    fb = [p for p in cands if p["mid"] == mids[0] and p["name"].startswith("기타")] or [p for p in cands if p["mid"] == mids[0]]
                    best, how = fb[-1] if fb else best, "폴백(중분류 기타)"
        method[how] += 1
        rows.append({"ksic": code, "ksic_name": name, "io": best["code"], "io_name": best["name"], "score": round(s, 3), "method": how})
    with OUT_C.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["ksic", "ksic_name", "io", "io_name", "score", "method"])
        w.writeheader(); w.writerows(rows)
    # attract.py 가 읽는 부문분류표 형식
    import pandas as pd
    per_io = defaultdict(list)
    for r in rows:
        if r["io"]:
            per_io[r["io"]].append(r["ksic"])
    table = [["2020 기준년 상품 기본부문 ↔ 업종코드(10차 세세분류) 자동 추정 연계표 (scripts/build_io_ksic_map.py, 기업 사전에 나온 업종코드만. 제목 줄에는 검색어를 넣지 않는다)", "", "", "", "", ""],
             ["기본부문 코드", "상품명", "소분류", "중분류", "한국표준산업분류(KSIC 세세분류)", "비고"]]
    for p in prods:
        ks = per_io.get(p["code"], [])
        table.append([p["code"], p["name"], p["sub"][1] if p["sub"] else "", p["mid_name"], ", ".join(ks), f"{len(ks)}개" if ks else ""])
    pd.DataFrame(table).to_excel(OUT_X, header=False, index=False)
    mapped = sum(1 for r in rows if r["io"])
    print(f"KSIC 세세분류 {len(ksic)}개 → 기본부문 {len(per_io)}개에 연결 (연결 {mapped}, {dict(method)}) → {OUT_X.relative_to(ROOT)}, {OUT_C.relative_to(ROOT)}")
    low = [r for r in rows if r["method"].startswith("폴백")]
    print("폴백 예시:", [(r['ksic'], r['ksic_name'][:18], r['io_name'][:14]) for r in low[:12]])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
