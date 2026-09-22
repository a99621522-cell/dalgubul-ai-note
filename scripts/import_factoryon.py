#!/usr/bin/env python3
"""팩토리온 월간 엑셀 → scripts/data/dalseong_companies.csv / dalseong_complexes.csv 갱신 (대구광역시 전체, 파일명은 호환 유지)

사용:
  python3 scripts/import_factoryon.py "<전국(개별,계획)입주업체현황.xlsx>" ["<산단공관할단지내_입주업체리스트.xlsx>"]

1번 파일(필수): 팩토리온 자료실 "전국(개별,계획)_입주업체현황" — 대구 전체 공장(산단·농공단지·개별입지) + 종업원 수. district 열에 구·군.
2번 파일(선택): "산단공관할단지내_입주업체리스트" — 산단공 관할 단지(국가산단·달성2차·외투지역)의 등록구분·최초등록일·면적 보강.

규칙: 같은 회사가 같은 단지(또는 개별입지)에 공장 여러 개면 한 기업으로 합친다.
기존 기업은 (회사명, 단지) 기준으로 id 유지. 전화번호 등 연락처는 저장하지 않는다.
필요: pip install pandas openpyxl --break-system-packages
"""
import csv, re, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scripts" / "data"
COMP = DATA / "dalseong_companies.csv"
CX = DATA / "dalseong_complexes.csv"

CX_META = {  # 단지명 → (유형, 소재지). 파일에 없는 정보만 여기서 보강
    "성서지방산업단지": ("일반산단", "달서구·달성군 다사읍"),
    "서대구일반산업단지": ("일반산단", "서구"),
    "대구제3일반산업단지": ("일반산단", "북구"),
    "북구검단일반산업단지": ("일반산단", "북구"),
    "대구염색일반산업단지": ("일반산단", "서구"),
    "대구인쇄출판밸리": ("일반산단", "북구"),
    "대구이시아폴리스일반산업단지": ("일반산단", "동구"),
    "대구금호워터폴리스일반산업단지": ("일반산단", "북구"),
    "대구국가산업단지": ("국가산단", "달성군 구지면"),
    "대구테크노폴리스일반산업단지": ("일반산단", "달성군 유가읍·현풍읍"),
    "성서5차첨단산업단지": ("일반산단", "달성군 다사읍"),
    "달성일반산업단지": ("일반산단", "달성군 논공읍"),
    "달성2차일반산업단지": ("일반산단", "달성군 구지면"),
    "대구옥포농공단지": ("농공단지", "달성군 옥포읍"),
    "대구구지농공단지": ("농공단지", "달성군 구지면"),
    "군위농공단지": ("농공단지", "군위군"),
    "군위효령농공단지": ("농공단지", "군위군"),
    "대구연구개발특구": ("연구개발특구", "달성군·동구"),
    "대구경북경제자유구역수성의료지구": ("경제자유구역", "수성구"),
    "대구경북첨단의료복합단지도시첨단산업단지": ("첨복단지", "동구"),
    "달성외국인투자지역": ("외국인투자지역", "달성군 구지면"),
    "개별입지": ("개별입지(산단 외)", "대구 전역"),
}
SECTOR_GROUPS = {"30": "자동차부품", "29": "기계", "25": "금속가공", "28": "전기장비", "24": "1차금속", "20": "화학", "26": "전자", "13": "섬유", "22": "고무·플라스틱", "10": "식품", "23": "비금속광물", "31": "기타운송장비", "27": "의료·정밀", "21": "의약품"}

def workers_band(n):
    try: n = int(float(n))
    except Exception: return ""
    if n <= 0: return ""
    return "1~9명" if n < 10 else "10~49명" if n < 50 else "50~99명" if n < 100 else "100~299명" if n < 300 else "300명 이상"

def area_band(a):
    try: a = float(a)
    except Exception: return ""
    if a <= 0: return ""
    return "500㎡ 미만" if a < 500 else "500~2천㎡" if a < 2000 else "2천~1만㎡" if a < 10000 else "1만㎡ 이상"

def dedup(s):
    toks = [t.strip() for t in re.split(r"[,/·]", str(s)) if t.strip() and t.strip().lower() not in ("nan", "")]
    seen = []
    for t in toks:
        if t not in seen: seen.append(t)
    return ", ".join(seen)[:120]

def district(addr):
    m = re.search(r"대구광역시\s+(\S+?[구군])", str(addr))
    return m.group(1) if m else ""

def eupmyeon(addr):
    m = re.search(r"(?:달성군|군위군)\s+(\S+?[읍면])", str(addr))
    if m: return m.group(1)
    m = re.search(r"[구군]\s+(\S+?동)\b", str(addr))
    return m.group(1) if m else ""

def main(main_path: str, kicox_path: str | None = None):
    m = re.search(r"(\d{4})[._](\d{2})", Path(main_path).name)
    as_of = f"{m.group(1)}-{m.group(2)}" if m else pd.Timestamp.today().strftime("%Y-%m")

    df = pd.read_excel(main_path, dtype=str).fillna("")
    d = df[df["공장주소"].str.startswith("대구", na=False)].copy()
    d["회사명"] = d["회사명"].str.strip()
    d["complex"] = d["단지명"].where(d["단지명"].str.strip() != "", "개별입지")
    d["district"] = d["공장주소"].map(district)
    d["eupmyeon"] = d["공장주소"].map(eupmyeon)
    d["emp"] = pd.to_numeric(d["종업원합계"], errors="coerce").fillna(0).astype(int)

    # 산단공 파일 보강(선택)
    enrich = {}
    if kicox_path:
        k = pd.read_excel(kicox_path, dtype=str).fillna("")
        k = k[k["시도"] == "대구광역시"]
        order = ["", "500㎡ 미만", "500~2천㎡", "2천~1만㎡", "1만㎡ 이상"]
        for (name, cx), g in k.assign(회사명=k["회사명"].str.strip()).groupby(["회사명", "단지명"]):
            years = [str(y)[:4] for y in g["최초등록일"] if str(y)[:4].isdigit()]
            bands = [area_band(a) for a in g["제조시설면적"]]
            enrich[(name, cx)] = {"reg_type": "등록" if (g["등록구분"] == "등록").any() else "승인",
                                  "first_registered": min(years) if years else "",
                                  "mfg_area_band": max(bands, key=order.index) if bands else ""}

    old = pd.read_csv(COMP, dtype=str).fillna("") if COMP.exists() else pd.DataFrame(columns=["id", "name", "complex"])
    key2id = {(r["name"], r["complex"]): r["id"] for _, r in old.iterrows()}
    nxt = max([int(i[1:]) for i in key2id.values()] or [0]) + 1

    rows = []
    for (name, cx), g in d.groupby(["회사명", "complex"], sort=False):
        cid = key2id.get((name, cx))
        if not cid:
            cid = f"c{nxt:04d}"; nxt += 1
        sectors = [x for x in g["업종명"] if x]
        code = str(g["대표업종"].iloc[0])
        e = enrich.get((name, cx), {})
        emp = int(g["emp"].sum())
        rows.append({
            "id": cid, "name": name, "complex": cx,
            "district": g["district"].mode().iloc[0] if g["district"].any() else "",
            "eupmyeon": g["eupmyeon"].mode().iloc[0] if g["eupmyeon"].any() else "",
            "sector_code": code, "sector": sectors[0] if sectors else "",
            "sector_group": SECTOR_GROUPS.get(code[:2], "기타"),
            "product": dedup(", ".join(g["생산품"])),
            "workers_band": workers_band(emp), "workers": str(emp) if emp > 0 else "",
            "reg_type": e.get("reg_type", ""), "first_registered": e.get("first_registered", ""), "mfg_area_band": e.get("mfg_area_band", ""),
            "address": " / ".join(dict.fromkeys(a.strip() for a in g["공장주소"] if a.strip())),
            "sites": str(len(g)),
            "source": "팩토리온 전국(개별,계획) 입주업체현황", "as_of": as_of,
        })
    new = pd.DataFrame(rows)
    keys_new = set(zip(new["name"], new["complex"]))
    gone = old[~old.apply(lambda r: (r["name"], r["complex"]) in keys_new, axis=1)] if len(old) else old
    out = pd.concat([new, gone], ignore_index=True).fillna("").sort_values(["complex", "name"])
    out.to_csv(COMP, index=False, quoting=csv.QUOTE_MINIMAL, encoding="utf-8")
    print(f"기업 {len(new)}건 갱신 (공장 {len(d)}개), 이전 목록에서 사라진 {len(gone)}건 유지, as_of {as_of}")

    # 단지 현황 재생성 (파일에서 계산되는 값 + 메타)
    old_cx = pd.read_csv(CX, dtype=str).fillna("") if CX.exists() else pd.DataFrame()
    cx_rows = []
    for cx, g in new.groupby("complex"):
        typ, loc = CX_META.get(cx, ("산단", g["district"].mode().iloc[0] if g["district"].any() else ""))
        top = g["sector_group"].value_counts()
        top = "·".join([t for t in top.index[:3] if t != "기타"]) if len(top) else ""
        prev = old_cx[old_cx["name"] == cx].iloc[0].to_dict() if len(old_cx) and (old_cx["name"] == cx).any() else {}
        cx_rows.append({"name": cx, "type": typ, "location": loc,
                        "completed": prev.get("completed", ""), "area_km2": prev.get("area_km2", ""),
                        "firms": str(len(g)), "sites": str(g["sites"].astype(int).sum()),
                        "workers": str(int(g["workers"].replace("", "0").astype(int).sum())),
                        "main_sectors": top, "source": "팩토리온 전국(개별,계획) 입주업체현황", "as_of": as_of})
    order = list(CX_META.keys())
    cxdf = pd.DataFrame(cx_rows)
    cxdf["o"] = cxdf["name"].map(lambda n: order.index(n) if n in order else 99)
    cxdf.sort_values("o").drop(columns="o").to_csv(CX, index=False, encoding="utf-8")
    print("단지 현황 갱신:", len(cx_rows), "행")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
