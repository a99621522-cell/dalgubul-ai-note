#!/usr/bin/env python3
"""산업연관표 기반 기업유치 후보 분석 — 대구 제조 클러스터가 역외에서 사 오는 공정(빈 고리)을 찾고,
그 공정을 하는 전국 공장을 '조건 필터 결과'로 나열한다. 추천·평가가 아니다.

사용:
  python3 scripts/attract.py                                   # scripts/data/io/ 의 거래표·부문분류표 + 대구 기업 사전 (1·2단계)
  python3 scripts/attract.py --factoryon "scripts/data/raw/(2026.08월말기준)_전국(개별,계획)입주업체현황.xlsx"   # + 3·4단계 후보
  python3 scripts/attract.py --io-dir <폴더> --companies <csv> --out <폴더>   # 시험용 경로 바꾸기
  python3 scripts/attract.py --transpose                        # 거래표 행·열 방향을 강제로 뒤집기 (검증이 실패할 때)

입력 (scripts/data/io/, 파일명 자유 — 내용으로 판별):
  · 한국은행 산업연관표 생산자가격 거래표(기본부문) xlsx  — 행 = 공급(투입) 부문, 열 = 수요(산출) 부문
  · 부문분류표 xlsx — 기본부문 코드·명과 한국표준산업분류(KSIC) 코드 열
  · scripts/data/dalseong_companies.csv (대구, 팩토리온) · 전국 팩토리온 입주업체현황 xlsx(선택, 30만 공장) · scripts/data/programs_*.csv
출력 (scripts/data/io/): gaps.csv, candidates.csv, attract_brief.md, summary.json (사이트 /supply-chain/ 이 읽음)

한계: 투입계수는 전국 평균이라 대구 기업의 실제 거래 구조와 다르다. 종사자 수는 팩토리온 신고값. 후보 목록에는 연락처·평가 문구가 없다.
필요: pandas, openpyxl (import_factoryon.py 와 같음)
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scripts" / "data"
IO_DIR = DATA / "io"
COMPANIES = DATA / "dalseong_companies.csv"

# ───────────────────────── 조건 상수 (화면·brief 에 그대로 표시) ─────────────────────────
CLUSTERS: dict[str, str] = {  # 대구 주력 수요 클러스터 → IO 기본부문명 정규식 (부문 이름으로 고른다)
    "자동차부품": r"자동차\s*부품|자동차용|차체|트레일러|자동차\s*엔진|자동차\s*(전기|전자)",
    "일반기계": r"공작\s*기계|금속\s*(가공|절삭)\s*기계|일반\s*목적|특수\s*목적|산업용\s*(기계|로봇)|펌프|압축기|밸브|베어링|기어|동력\s*전달|운반\s*(기계|장비)|냉동|공기\s*조화|섬유\s*기계|반도체\s*(제조|장비)|디스플레이\s*제조\s*장비|건설\s*기계|광업용\s*기계",
    "전기장비": r"전동기|발전기|변압기|전기\s*(변환|공급|제어)|배전|제어\s*(장치|반)|전선|케이블|축전지|전지|조명\s*(장치|기구)|전기\s*장비|절연",
    "섬유": r"직물|염색|가공사|편조|부직포|섬유\s*제품|면\s*방적|화학\s*섬유|산업용\s*섬유|의복|봉제",
    "의료기기": r"의료용\s*(기기|기구|장비|측정)|의료\s*기기|정형외과|치과용|방사선|안경|의료용품|재활",
}
EXCLUDE_SUPPLY = r"전력|전기업|가스|증기|수도|폐기물|하수|석유\s*정제|코크스|원유|천연가스|채굴|광석|광업|석탄|농산|축산|수산|임산|도매|소매|운송|금융|보험|부동산|서비스|연구|교육|보건|행정|국방|음식|숙박|임대|건설|건축|토목"
MANUFACTURING_KSIC = {f"{d:02d}" for d in range(10, 34)} - {"19"}  # 제조업(10~33) 중 코크스·석유정제(19) 제외
TOP_GAPS = 15           # 클러스터별 빈 고리 상위 N 부문 → 후보 추출 대상
TOP_INPUTS = 15         # '투입계수 상위 N 안' 거래 가능성 판정
SIZE_MIN, SIZE_MAX = 30, 300    # 이전 가능 규모(종업원)
SIZE_BEST = (50, 200)           # 이 안이면 규모 적합 1.0, 밖(30~300 안)이면 0.8
REGION_WEIGHTS = {"경북": 1.0, "경남": 0.9, "울산": 0.9, "부산": 0.85, "충북": 0.75, "충남": 0.75, "대전": 0.75, "세종": 0.75,
                  "경기": 0.6, "서울": 0.6, "인천": 0.6, "강원": 0.5, "전북": 0.5, "전남": 0.5, "광주": 0.5, "전남광주": 0.5, "제주": 0.4}
EXPANSION_YEARS = 5     # 최근 N년 안 최초등록 = 확장 신호
EXPANSION_NONE = 0.5    # 확장 신호 없으면 곱하는 값 (있으면 1.0)
INCENTIVE_KEYWORDS = r"지방투자|투자촉진|지방주도형|기회발전특구|국내복귀|유턴|지역투자|지방이전|지방\s*주도|산단환경조성|산업단지환경"
VERIFY_AUTO = r"철강|플라스틱|금형|전자\s*부품"   # 자동차부품 클러스터 공급부문 상위에 나와야 하는 이름
TODAY = date.today().isoformat()


def log(*a):
    print(*a, flush=True)


# ───────────────────────── 1단계: 산업연관표·부문분류표 읽기 ─────────────────────────
def _pd():
    try:
        import pandas as pd  # noqa: WPS433
        return pd
    except ImportError:
        sys.exit("pandas·openpyxl 이 필요하다: pip install pandas openpyxl")


def is_code(v) -> bool:
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return bool(re.fullmatch(r"\d{3,4}", s))


def norm_code(v, width: int) -> str:
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(width) if s.isdigit() else s


def norm_name(s) -> str:
    return re.sub(r"[\s·ㆍ,()\-]", "", str(s or ""))


def load_sheets(path: Path) -> dict:
    pd = _pd()
    try:
        return pd.read_excel(path, sheet_name=None, header=None, dtype=object)
    except Exception as e:  # noqa: BLE001
        log(f"  읽기 실패 {path.name}: {str(e)[:80]}")
        return {}


def find_matrix(df):
    """거래표 시트에서 (행 코드 열, 행 이름 열, 열 코드 행, 코드 목록) 을 찾는다. 코드가 50개 이상 있어야 한다."""
    nrow, ncol = df.shape
    best_r = max(((i, sum(is_code(v) for v in df.iloc[i, :].tolist())) for i in range(min(nrow, 40))), key=lambda x: x[1], default=(None, 0))
    best_c = max(((j, sum(is_code(v) for v in df.iloc[:, j].tolist())) for j in range(min(ncol, 12))), key=lambda x: x[1], default=(None, 0))
    if best_r[1] < 50 or best_c[1] < 50:
        return None
    hr, cc = best_r[0], best_c[0]
    # 이름 열: 코드 열 오른쪽에서 문자열이 많은 첫 열
    nc = None
    for j in range(cc + 1, min(cc + 4, ncol)):
        col = df.iloc[hr + 1:hr + 60, j].tolist()
        if sum(isinstance(v, str) and not is_code(v) for v in col) > 30:
            nc = j
            break
    return hr, cc, nc


def load_transactions(files: list[Path]):
    """가장 큰 정방 코드 블록을 가진 시트를 거래표로. 반환: codes, names(dict), Z(list of list), X(list), info"""
    best = None
    for f in files:
        for sname, df in load_sheets(f).items():
            m = find_matrix(df)
            if not m:
                continue
            hr, cc, nc = m
            row_idx = [i for i in range(hr + 1, len(df)) if is_code(df.iat[i, cc])]
            col_idx = [j for j in range(cc + 1, df.shape[1]) if is_code(df.iat[hr, j])]
            width = max(len(str(df.iat[i, cc]).strip().replace(".0", "")) for i in row_idx)
            rcodes = [norm_code(df.iat[i, cc], width) for i in row_idx]
            ccodes = [norm_code(df.iat[hr, j], width) for j in col_idx]
            common = [c for c in rcodes if c in set(ccodes)]
            if len(common) < 50:
                continue
            if best and len(common) <= best["n"]:
                continue
            best = {"file": f, "sheet": sname, "df": df, "hr": hr, "cc": cc, "nc": nc, "row_idx": row_idx, "col_idx": col_idx,
                    "rcodes": rcodes, "ccodes": ccodes, "n": len(common), "width": width}
    if not best:
        return None
    df, hr, cc, nc = best["df"], best["hr"], best["cc"], best["nc"]
    rpos = {c: i for c, i in zip(best["rcodes"], best["row_idx"])}
    cpos = {c: j for c, j in zip(best["ccodes"], best["col_idx"])}
    codes = [c for c in best["rcodes"] if c in cpos]
    names = {}
    for c in codes:
        i = rpos[c]
        nm = df.iat[i, nc] if nc is not None else ""
        if not isinstance(nm, str) or not nm.strip():   # 이름이 열 머리글 아래 줄에 있는 경우
            nm2 = df.iat[hr + 1, cpos[c]] if hr + 1 < len(df) else ""
            nm = nm2 if isinstance(nm2, str) else ""
        names[c] = re.sub(r"\s+", " ", str(nm)).strip()

    def num(v) -> float:
        try:
            s = str(v).replace(",", "").strip()
            return float(s) if s not in ("", "-", "nan", "None", "…") else 0.0
        except ValueError:
            return 0.0

    Z = [[num(df.iat[rpos[r], cpos[c]]) for c in codes] for r in codes]
    # 총투입액(열 합계): '총투입' 행이 있으면 그 값, 없으면 중간투입(코드 행 합) + 코드 아닌 나머지 수치 행('계' 제외)
    X, x_from = None, ""
    for i in range(len(df)):
        lab = " ".join(str(df.iat[i, j]) for j in range(0, min(nc + 1 if nc is not None else cc + 1, df.shape[1]) + 0) if isinstance(df.iat[i, j], str))
        if re.search(r"총\s*투입|총\s*산출", lab):
            X = [num(df.iat[i, cpos[c]]) for c in codes]
            x_from = lab.strip()[:30]
            break
    if X is None or sum(X) == 0:
        last_code_row = max(best["row_idx"])
        va_rows = [i for i in range(last_code_row + 1, len(df))
                   if not is_code(df.iat[i, cc]) and not re.search(r"계|합|총", str(df.iat[i, cc]) + str(df.iat[i, nc] if nc is not None else ""))]
        X = [sum(Z[r][j] for r in range(len(codes))) + sum(num(df.iat[i, cpos[c]]) for i in va_rows) for j, c in enumerate(codes)]
        x_from = f"중간투입계+부가가치 항목 {len(va_rows)}행 (총투입 행 없음)"
    info = {"file": best["file"].name, "sheet": best["sheet"], "sectors": len(codes), "total_input_from": x_from}
    return codes, names, Z, X, info


def parse_ksic_codes(text: str) -> list[str]:
    """'10111, 10112~10119, 1013(일부)' → 5자리·4자리 코드 목록 (범위는 전개)"""
    t = str(text or "")
    out: list[str] = []
    for a, b in re.findall(r"(\d{5})\s*[~\-–∼]\s*(\d{5})", t):
        if int(b) - int(a) <= 200:
            out += [str(k) for k in range(int(a), int(b) + 1)]
    t2 = re.sub(r"\d{5}\s*[~\-–∼]\s*\d{5}", " ", t)
    out += re.findall(r"(?<!\d)(\d{5})(?!\d)", t2)
    out += re.findall(r"(?<!\d)(\d{4})(?!\d)", re.sub(r"\d{5}", " ", t2))
    return out


def load_classification(files: list[Path], tx_codes: list[str], tx_names: dict, width: int):
    """부문분류표 → ksic5→IO코드, ksic4→IO코드, IO코드→KSIC 대분류 집합. 거래표 코드와 안 맞으면 이름으로 잇는다."""
    best = None
    for f in files:
        for sname, df in load_sheets(f).items():
            hdr_rows = [i for i in range(min(8, len(df))) if any(isinstance(v, str) and re.search(r"표준산업|KSIC|산업분류", v) for v in df.iloc[i].tolist())]
            if not hdr_rows:
                continue
            hi = hdr_rows[0]
            heads = []
            for j in range(df.shape[1]):
                h = " ".join(str(df.iat[i, j]) for i in range(max(0, hi - 1), min(hi + 2, len(df))) if isinstance(df.iat[i, j], str))
                heads.append(h)
            kcol = next((j for j, h in enumerate(heads) if re.search(r"표준산업|KSIC|산업분류", h)), None)
            bcols = [j for j, h in enumerate(heads) if "기본" in h or "부문코드" in h or re.search(r"코드", h)]
            if kcol is None:
                continue
            # 기본부문 코드 열: 헤더에 '기본' 이 있고 값이 코드처럼 생긴 열, 없으면 kcol 왼쪽에서 코드 값이 가장 많은 열
            cand = [j for j in bcols if j != kcol and sum(is_code(v) for v in df.iloc[hi + 1:hi + 80, j].tolist()) > 20]
            if not cand:
                cand = sorted((j for j in range(kcol) if sum(is_code(v) for v in df.iloc[hi + 1:hi + 80, j].tolist()) > 20),
                              key=lambda j: -sum(is_code(v) for v in df.iloc[hi + 1:, j].tolist()))
            if not cand:
                continue
            bcol = [j for j in cand if "기본" in heads[j]] or cand
            bcol = bcol[-1] if isinstance(bcol, list) else bcol
            ncol_ = bcol + 1 if bcol + 1 < df.shape[1] and bcol + 1 != kcol else None
            n = sum(is_code(v) for v in df.iloc[hi + 1:, bcol].tolist())
            if not best or n > best["n"]:
                best = {"file": f, "sheet": sname, "df": df, "hi": hi, "bcol": bcol, "ncol": ncol_, "kcol": kcol, "n": n}
    if not best:
        return None
    df, hi, bcol, ncol_, kcol = best["df"], best["hi"], best["bcol"], best["ncol"], best["kcol"]
    name_to_tx = {norm_name(v): k for k, v in tx_names.items()}
    tx_set = set(tx_codes)
    ksic5, ksic4, io_ksic_div = {}, {}, defaultdict(set)
    cur_code, cur_name, unmatched = None, "", set()
    conflicts = 0
    for i in range(hi + 1, len(df)):
        v = df.iat[i, bcol]
        if is_code(v):
            cur_code = norm_code(v, width)
            cur_name = str(df.iat[i, ncol_]).strip() if ncol_ is not None and isinstance(df.iat[i, ncol_], str) else cur_name
        if not cur_code:
            continue
        io = cur_code
        if io not in tx_set:   # 코드 체계가 다르면 이름으로
            io = name_to_tx.get(norm_name(cur_name))
            if not io:
                unmatched.add(cur_code)
                continue
        for k in parse_ksic_codes(df.iat[i, kcol]):
            io_ksic_div[io].add(k[:2])
            if len(k) == 5:
                if k in ksic5 and ksic5[k] != io:
                    conflicts += 1
                    continue
                ksic5[k] = io
            else:
                ksic4.setdefault(k, io)
    # 4자리 폴백: 5자리 자식이 가장 많이 속한 부문
    child = defaultdict(Counter)
    for k, io in ksic5.items():
        child[k[:4]][io] += 1
    for k4, cnt in child.items():
        ksic4.setdefault(k4, cnt.most_common(1)[0][0])
    info = {"file": best["file"].name, "sheet": best["sheet"], "ksic5": len(ksic5), "ksic4": len(ksic4), "conflicts": conflicts, "io_unmatched": len(unmatched)}
    return ksic5, ksic4, io_ksic_div, info


def map_sector(code: str, ksic5: dict, ksic4: dict) -> tuple[str | None, str]:
    c = re.sub(r"\D", "", str(code or ""))[:5]
    if len(c) == 5 and c in ksic5:
        return ksic5[c], "5"
    if len(c) >= 4 and c[:4] in ksic4:
        return ksic4[c[:4]], "4"
    return None, ""


# ───────────────────────── 2단계: 빈 고리 ─────────────────────────
def region_of(addr: str) -> str:
    s = str(addr or "").strip()
    for k in ("전남광주", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"):
        if s.startswith(k):
            return k
    m = re.match(r"(충청북도|충청남도|전라북도|전라남도|경상북도|경상남도)", s)
    if m:
        return {"충청북도": "충북", "충청남도": "충남", "전라북도": "전북", "전라남도": "전남", "경상북도": "경북", "경상남도": "경남"}[m.group(1)]
    return s[:2]


def build_gaps(codes, names, A, daegu_workers: Counter, daegu_firms: Counter, io_ksic_div, transpose_note: str):
    """클러스터별 요구 규모·대구 공급·coverage·gap_score. A[i][j] = 부문 j 산출 1단위당 부문 i 투입."""
    idx = {c: k for k, c in enumerate(codes)}
    n = len(codes)

    def is_mfg(c):
        divs = io_ksic_div.get(c) or set()
        by_ksic = bool(divs & MANUFACTURING_KSIC) if divs else None
        if re.search(EXCLUDE_SUPPLY, names.get(c, "")):
            return False
        return True if by_ksic is None else by_ksic

    cluster_sectors, rows = {}, []
    for cl, pat in CLUSTERS.items():
        S = [c for c in codes if re.search(pat, names.get(c, "")) and not re.search(EXCLUDE_SUPPLY, names.get(c, ""))]
        cluster_sectors[cl] = S
        if not S:
            log(f"  [{cl}] 이름이 맞는 IO 부문이 없다 — CLUSTERS 정규식 확인")
            continue
        demand = [0.0] * n
        for j in S:
            w = daegu_workers.get(j, 0)
            if w <= 0:
                continue
            jj = idx[j]
            for i in range(n):
                demand[i] += A[i][jj] * w
        cand = [c for c in codes if c not in S and demand[idx[c]] > 0 and is_mfg(c)]
        tot = sum(demand[idx[c]] for c in cand) or 1.0
        ratios = {c: daegu_workers.get(c, 0) / demand[idx[c]] for c in cand}
        srt = sorted(ratios.values())
        ref = srt[int(len(srt) * 0.9)] if srt else 1.0   # 상위 10% 수준을 coverage 1 로
        ref = ref or 1.0
        for c in cand:
            cov = min(1.0, ratios[c] / ref)
            share = demand[idx[c]] / tot
            rows.append({"cluster": cl, "io_sector": c, "io_name": names.get(c, ""), "demand_index": round(demand[idx[c]], 1), "demand_share": round(share, 4),
                         "daegu_firms": daegu_firms.get(c, 0), "daegu_workers": daegu_workers.get(c, 0), "coverage": round(cov, 3),
                         "gap_score": round(share * (1 - cov), 5)})
    rows.sort(key=lambda r: (r["cluster"], -r["gap_score"]))
    rank = Counter()
    for r in rows:
        rank[r["cluster"]] += 1
        r["rank"] = rank[r["cluster"]]
    return rows, cluster_sectors


def verify_auto(codes, names, A, cluster_sectors, daegu_workers) -> tuple[bool, list[str]]:
    """자동차부품 클러스터 공급부문 상위 15 에 철강·플라스틱·금형·전자부품이 있는가"""
    S = cluster_sectors.get("자동차부품") or []
    if not S:
        return False, []
    idx = {c: k for k, c in enumerate(codes)}
    demand = Counter()
    for j in S:
        w = daegu_workers.get(j, 0) or 1
        for i, c in enumerate(codes):
            if c not in S:
                demand[c] += A[i][idx[j]] * w
    top = [names.get(c, "") for c, _ in demand.most_common(15)]
    hits = {m.group(0) for nm in top for m in [re.search(VERIFY_AUTO, nm)] if m}
    return len(hits) >= 2, top


# ───────────────────────── 3단계: 전국 후보 ─────────────────────────
def size_fit(w: int) -> float:
    if w < SIZE_MIN or w > SIZE_MAX:
        return 0.0
    return 1.0 if SIZE_BEST[0] <= w <= SIZE_BEST[1] else 0.8


def build_candidates(fo_path: Path, gaps: list[dict], codes, names, A, cluster_sectors, ksic5, ksic4, daegu_by_sector: dict, programs: list[dict]):
    pd = _pd()
    df = pd.read_excel(fo_path, dtype=str).fillna("")
    for c in ("회사명", "공장주소", "종업원합계", "대표업종"):
        if c not in df.columns:
            sys.exit(f"팩토리온 파일에 '{c}' 열이 없다. 있는 열: {list(df.columns)[:20]}")
    reg_col = next((c for c in df.columns if re.search(r"최초등록|등록일|설립", str(c))), None)
    log(f"  전국 공장 {len(df):,}행, 최초등록 열: {reg_col or '없음(복수 공장만 확장 신호)'}")
    df["회사명"] = df["회사명"].str.strip()
    df["region"] = df["공장주소"].map(region_of)
    df["emp"] = pd.to_numeric(df["종업원합계"], errors="coerce").fillna(0).astype(int)
    df["io"] = df["대표업종"].map(lambda c: map_sector(c, ksic5, ksic4)[0] or "")
    mapped = (df["io"] != "").mean() if len(df) else 0
    log(f"  전국 매핑률 {mapped:.1%}")
    # 빈 고리 상위 부문 → 클러스터·gap_score
    target: dict[str, list[dict]] = defaultdict(list)
    for g in gaps:
        if g["rank"] <= TOP_GAPS and g["gap_score"] > 0:
            target[g["io_sector"]].append(g)
    sub = df[df["io"].isin(target.keys()) & (df["region"] != "대구")]
    idx = {c: k for k, c in enumerate(codes)}
    # 클러스터 부문 j 의 투입 상위 15 에 i 가 드는가 → 대구 수요 기업 수·대표 업종
    top_inputs = {}
    for cl, S in cluster_sectors.items():
        for j in S:
            col = sorted(((A[i][idx[j]], c) for i, c in enumerate(codes) if c != j), reverse=True)[:TOP_INPUTS]
            top_inputs[j] = {c for _, c in col}
    this_year = date.today().year
    incent = dedupe_programs([p for p in programs if re.search(INCENTIVE_KEYWORDS, p.get("name", ""))])
    incent_s = " / ".join(f"{p.get('code', '')} {p.get('name', '')[:30]} {p.get('budget_2026', '')}백만원".strip() for p in incent[:5]) or "사업 DB에서 못 찾음"
    out = []
    for name, g in sub.groupby("회사명", sort=False):
        if not name or len(name) < 2:
            continue
        workers = int(g["emp"].sum())
        sf = size_fit(workers)
        if sf == 0:
            continue
        region = g["region"].mode().iloc[0]
        rw = REGION_WEIGHTS.get(region, 0.5)
        sites = len(g)
        years = sorted({str(y)[:4] for y in g[reg_col]} if reg_col else set())
        years = [y for y in years if y.isdigit()]
        first = min(years) if years else ""
        recent = bool(first) and int(first) >= this_year - EXPANSION_YEARS
        expansion = 1.0 if (recent or sites >= 2) else EXPANSION_NONE
        signal = "·".join(x for x in [f"최초등록 {first}" if recent else "", f"공장 {sites}개" if sites >= 2 else ""] if x) or "없음"
        io = g["io"].mode().iloc[0]
        for gap in target[io]:   # 같은 회사가 여러 클러스터의 빈 고리에 해당하면 클러스터마다 한 행 (gap_score 가 다르다)
            cl = gap["cluster"]
            # 대구 수요 기업: 이 부문을 투입 상위 안에 두는 클러스터 부문들의 대구 기업 수와 대표 업종 3개
            dem_secs = [j for j in cluster_sectors[cl] if io in top_inputs.get(j, set())]
            dem_firms = sum(len(daegu_by_sector.get(j, [])) for j in dem_secs)
            dem_top = sorted(((len(daegu_by_sector.get(j, [])), names.get(j, j)) for j in dem_secs), reverse=True)[:3]
            matched = f"{dem_firms}곳: " + " · ".join(f"{n}({k})" for k, n in dem_top) if dem_firms else "0곳"
            fit = gap["gap_score"] * sf * rw * expansion
            out.append({"io_sector": io, "io_name": names.get(io, ""), "cluster": cl, "company": name, "region": region,
                        "workers": workers, "sites": sites, "first_registered": first, "expansion_signal": signal,
                        "size_fit": sf, "region_weight": rw, "expansion": expansion, "gap_score": gap["gap_score"],
                        "fit_score": round(fit * 1000, 3), "matched_daegu_demand": matched, "incentive": incent_s})
    out.sort(key=lambda r: (-r["fit_score"], r["company"]))
    return out, mapped, incent


def dedupe_programs(rows: list[dict]) -> list[dict]:
    """같은 사업이 두 자료(programs_motie·programs_budget_motie)에 있으면 한 번만, 2026 예산 큰 순"""
    seen, out = set(), []
    for p in sorted(rows, key=lambda p: -float((p.get("budget_2026") or "0").replace(",", "") or 0)):
        k = (p.get("code", ""), re.sub(r"\s", "", p.get("name", "")))
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


# ───────────────────────── 4단계: 산출물 ─────────────────────────
def write_csv(path: Path, rows: list[dict], cols: list[str]):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def write_brief(path: Path, base_year: str, gaps: list[dict], cands: list[dict], incent: list[dict], summ: dict):
    L = [f"# 대구 제조 클러스터 빈 고리와 유치 후보 (조건 필터 결과) — {TODAY}", "",
         f"근거: 한국은행 산업연관표 {base_year} 생산자가격 거래표(기본부문) 전국 평균 투입계수 × 대구 기업 사전(팩토리온 {summ.get('companies_as_of', '')}) 종사자. "
         f"전국 후보는 팩토리온 전국 입주업체현황({summ.get('factoryon_file') or '없음'})에서 조건으로 거른 목록이며 **추천·평가가 아니다**. 연락처 없음.", "",
         f"매핑률: 대구 {summ['daegu_mapping']['rate']:.1%}(5자리 {summ['daegu_mapping']['by5']}, 4자리 폴백 {summ['daegu_mapping']['by4']}, 실패 {summ['daegu_mapping']['unmapped']}) · "
         f"전국 {summ.get('national_mapping_rate', 0):.1%}", "",
         "필터 조건: " + summ["filters"], ""]
    for cl in CLUSTERS:
        g = [r for r in gaps if r["cluster"] == cl][:3]
        L += [f"## {cl}", "", "빈 고리 상위 3 (요구 규모 지수 · 대구 공급 기업/종사자 · coverage)", ""]
        L += [f"- {r['io_name']} ({r['io_sector']}): 요구 {r['demand_index']:,} · 대구 {r['daegu_firms']}곳/{r['daegu_workers']:,}명 · coverage {r['coverage']:.2f}" for r in g] or ["- (계산 안 됨)"]
        c = [r for r in cands if r["cluster"] == cl][:10]
        L += ["", "후보 상위 10 (fit_score 순, 회사·지역·종업원·확장 신호·부문)", ""]
        L += [f"- {r['company']} · {r['region']} · {r['workers']}명 · {r['expansion_signal']} · {r['io_name']} · fit {r['fit_score']}" for r in c] or ["- (전국 팩토리온 파일이 없어 후보 없음)"]
        L.append("")
    L += ["## 관련 국비 사업 (사업 DB, 2026 예산 백만 원)", ""]
    L += [f"- {p.get('ministry', '')} {p.get('code', '')} {p.get('name', '')}: {p.get('budget_2026', '')}" for p in incent[:10]] or ["- 사업 DB에서 못 찾음"]
    L += ["", "한계: 투입계수는 전국 평균이라 대구 기업의 실제 거래와 다르다. 종사자는 팩토리온 신고값. coverage 는 클러스터 안 상위 10% 수준을 1 로 둔 상대값."]
    path.write_text("\n".join(L), encoding="utf-8")


def main(argv: list[str]) -> int:
    io_dir = Path(argv[argv.index("--io-dir") + 1]) if "--io-dir" in argv else IO_DIR
    comp_path = Path(argv[argv.index("--companies") + 1]) if "--companies" in argv else COMPANIES
    out_dir = Path(argv[argv.index("--out") + 1]) if "--out" in argv else IO_DIR
    fo_path = Path(argv[argv.index("--factoryon") + 1]) if "--factoryon" in argv else None
    force_t = "--transpose" in argv
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in io_dir.glob("*.xls*") if not p.name.startswith("~"))
    if not files:
        log(f"산업연관표 엑셀이 없다: {io_dir}/ 에 거래표(기본부문)·부문분류표를 넣을 것 (scripts/data/io/README.md)")
        return 1
    log("== 1단계 산업연관표 읽기")
    tx = load_transactions(files)
    if not tx:
        log("  거래표(코드 50개 이상의 정방 블록)를 못 찾았다")
        return 1
    codes, names, Z, X, tinfo = tx
    log(f"  거래표: {tinfo['file']} [{tinfo['sheet']}] 부문 {tinfo['sectors']} · 총투입: {tinfo['total_input_from']}")
    base_year = (re.search(r"(20\d\d)", tinfo["file"] + " " + tinfo["sheet"]) or [None, "기준연도 미확인"])[1]
    cl = load_classification(files, codes, names, len(codes[0]))
    if not cl:
        log("  부문분류표(KSIC 열)를 못 찾았다")
        return 1
    ksic5, ksic4, io_ksic_div, cinfo = cl
    log(f"  부문분류표: {cinfo['file']} [{cinfo['sheet']}] KSIC5 {cinfo['ksic5']} · KSIC4 {cinfo['ksic4']} · 충돌 {cinfo['conflicts']} · 거래표와 안 맞는 부문 {cinfo['io_unmatched']}")

    # 대구 기업 매핑
    comps = list(csv.DictReader(open(comp_path, encoding="utf-8")))
    as_of = comps[0].get("as_of", "") if comps else ""
    by5 = by4 = 0
    fails = Counter()
    daegu_workers, daegu_firms, daegu_by_sector = Counter(), Counter(), defaultdict(list)
    for r in comps:
        io, how = map_sector(r.get("sector_code", ""), ksic5, ksic4)
        r["io_sector"] = io or ""
        if not io:
            fails[r.get("sector_code", "")[:5]] += 1
            continue
        by5 += how == "5"
        by4 += how == "4"
        daegu_firms[io] += 1
        daegu_by_sector[io].append(r["id"])
        w = r.get("workers", "")
        daegu_workers[io] += int(w) if w.isdigit() else 0
    unmapped = sum(fails.values())
    rate = (len(comps) - unmapped) / len(comps) if comps else 0
    log(f"  대구 매핑률 {rate:.1%} (5자리 {by5}, 4자리 폴백 {by4}, 실패 {unmapped}) 실패 코드 상위: {fails.most_common(8)}")
    if unmapped / max(1, len(comps)) > 0.10:
        log("  ⚠ 실패 10% 초과 — 4자리 폴백을 이미 적용했다. 부문분류표의 KSIC 열이 부분 코드만 담았을 수 있다")

    log("== 2단계 빈 고리")
    n = len(codes)

    def coef(Zm):
        return [[(Zm[i][j] / X[j] if X[j] else 0.0) for j in range(n)] for i in range(n)]

    orient = "행=투입(공급) 부문, 열=산출(수요) 부문"
    A = coef([[Z[j][i] for j in range(n)] for i in range(n)]) if force_t else coef(Z)
    gaps, cluster_sectors = build_gaps(codes, names, A, daegu_workers, daegu_firms, io_ksic_div, orient)
    ok, top = verify_auto(codes, names, A, cluster_sectors, daegu_workers)
    if not ok and not force_t:
        A2 = coef([[Z[j][i] for j in range(n)] for i in range(n)])
        ok2, top2 = verify_auto(codes, names, A2, cluster_sectors, daegu_workers)
        if ok2:
            A, gaps, top, ok, orient = A2, build_gaps(codes, names, A2, daegu_workers, daegu_firms, io_ksic_div, "")[0], top2, True, "행·열을 뒤집음(원본이 행=수요였음)"
            log("  자동차부품 검증이 원래 방향에서 실패 → 행·열을 뒤집어 통과")
    log(f"  자동차부품 검증 {'통과' if ok else '실패'} — 공급 상위: {', '.join(top[:8])}")
    for cl_name in CLUSTERS:
        S = cluster_sectors.get(cl_name, [])
        top3 = [r for r in gaps if r["cluster"] == cl_name][:3]
        log(f"  [{cl_name}] 부문 {len(S)}개 · 대구 기업 {sum(daegu_firms.get(c, 0) for c in S)}곳 · 빈 고리 상위 3: " + " / ".join(f"{r['io_name']}({r['coverage']:.2f})" for r in top3))
    gcols = ["cluster", "rank", "io_sector", "io_name", "demand_index", "demand_share", "daegu_firms", "daegu_workers", "coverage", "gap_score"]
    write_csv(out_dir / "gaps.csv", gaps, gcols)

    programs = []
    for f in sorted(DATA.glob("programs_*.csv")):
        programs += list(csv.DictReader(open(f, encoding="utf-8")))
    cands, nat_rate, incent = [], 0.0, dedupe_programs([p for p in programs if re.search(INCENTIVE_KEYWORDS, p.get("name", ""))])
    fo_name = ""
    if fo_path and fo_path.exists():
        log("== 3단계 전국 후보")
        cands, nat_rate, incent = build_candidates(fo_path, gaps, codes, names, A, cluster_sectors, ksic5, ksic4, daegu_by_sector, programs)
        fo_name = fo_path.name
        log(f"  후보 {len(cands)}곳 (빈 고리 상위 {TOP_GAPS} 부문 × 대구 제외 × {SIZE_MIN}~{SIZE_MAX}명)")
    else:
        log("== 3단계 건너뜀: 전국 팩토리온 파일 없음 (--factoryon <xlsx>)")
    ccols = ["io_sector", "io_name", "cluster", "company", "region", "workers", "sites", "first_registered", "expansion_signal", "size_fit", "region_weight", "expansion",
             "gap_score", "fit_score", "matched_daegu_demand", "incentive"]
    write_csv(out_dir / "candidates.csv", cands, ccols)

    filters = (f"소재지 대구 제외(거리 가중 {', '.join(f'{k} {v}' for k, v in REGION_WEIGHTS.items())}) · 종업원 {SIZE_MIN}~{SIZE_MAX}명({SIZE_BEST[0]}~{SIZE_BEST[1]}명 1.0, 그 밖 0.8) · "
               f"확장 신호(최근 {EXPANSION_YEARS}년 최초등록 또는 복수 공장) 없으면 ×{EXPANSION_NONE} · 클러스터 부문 투입계수 상위 {TOP_INPUTS} 안 · 빈 고리 상위 {TOP_GAPS} 부문")
    summ = {"generated": TODAY, "base_year": base_year, "orientation": orient, "transactions": tinfo, "classification": cinfo,
            "companies_as_of": as_of, "daegu_mapping": {"rate": rate, "by5": by5, "by4": by4, "unmapped": unmapped, "fail_codes": fails.most_common(10)},
            "national_mapping_rate": nat_rate, "factoryon_file": fo_name, "verify_auto": {"ok": ok, "top_supply": top},
            "clusters": {k: [{"code": c, "name": names.get(c, ""), "firms": daegu_firms.get(c, 0), "workers": daegu_workers.get(c, 0)} for c in v] for k, v in cluster_sectors.items()},
            "filters": filters, "top_gaps": TOP_GAPS, "gaps": len(gaps), "candidates": len(cands),
            "incentives": [{"ministry": p.get("ministry", ""), "code": p.get("code", ""), "name": p.get("name", ""), "budget_2026": p.get("budget_2026", "")} for p in incent[:10]]}
    (out_dir / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    write_brief(out_dir / "attract_brief.md", base_year, gaps, cands, incent, summ)
    log(f"\n완료 → {out_dir}/gaps.csv({len(gaps)}), candidates.csv({len(cands)}), attract_brief.md, summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
