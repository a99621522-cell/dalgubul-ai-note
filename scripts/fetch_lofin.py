#!/usr/bin/env python3
"""지방재정365(lofin365.go.kr) 재정 데이터셋 → 대구(본청·구군) 행만 data/lofin/<key>.csv (2026-10-05, GRDP 기여 계산 내부 초안용).

대구시 예산은 사이트에 싣지 않는다(운영자 지시 2026-09-30) — 이 파일은 docs/drafts 의 내부 계산에만 쓴다.
로그인 없는 '재정 데이터셋 - Sheet' 의 CSV 내려받기와 같은 요청(POST /lf/pfinDtaOpen/dtst/dtstSvi/retvDtstDtsExcelDown.do,
JSON 본문: pdtaId·curPage·pageSize·inqWaLafHgNm(시도명) …)을 쪽마다 1초 쉬며 부른다. robots.txt Allow /.
데이터셋 번호(pdtaId)는 목록 검색(retvLstDtst.do) 조각에서 제목 옆 번호를 찾는다. 금액 단위 원, 값은 그대로.
사용: python3 scripts/fetch_lofin.py [--only key]
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "lofin"
BASE = "https://www.lofin365.go.kr"
UA = {"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"}
SIDO = "대구"
# key: (데이터셋 제목, 알려진 pdtaId 또는 "")
SETS = {
    "nature_settle": ("성질별 단체별 세출결산", ""),
    "func_settle": ("기능별 단체별 세출결산", ""),
    "struct_func_settle": ("구조별 기능별 세출결산", ""),
    "struct_func_budget": ("구조별 기능별 세출예산", "RL5CZ30XLWDXZAKXS5LP134169"),
}
PAGE = 2000
S = requests.Session()
S.headers.update(UA)


def find_id(title: str) -> str:
    data = {"menuUrl": "/lf/pfinDtaOpen/dtst/dtstSvi/retvLstDtst.do", "menuNm": "재정 데이터셋", "menuParaCn": "CJG", "menuId": "LF5100000",
            "uprMenuId": "LF5000000", "sysDvCd": "", "logReg": "true", "srchCrstCn": title, "frstParamYn": "Y"}
    try:
        r = S.post(BASE + "/lf/pfinDtaOpen/dtst/dtstSvi/retvLstDtst.do", data=data, timeout=60)
    except Exception as e:  # noqa: BLE001
        print(f"[lofin] 목록 검색 실패 {title}: {str(e)[:120]}")
        return ""
    t = r.text
    i = t.find(title)
    while i >= 0:
        win = t[max(0, i - 2500): i + 2500]
        ids = re.findall(r"['\"=(,\s]([A-Z0-9]{26})['\")&,\s]", win)
        if ids:
            # 제목에 가장 가까운 번호
            best = min(ids, key=lambda x: abs(win.find(x) - min(2500, i)))
            return best
        i = t.find(title, i + 1)
    head = re.sub(r"\s+", " ", t)[:400]
    print(f"[lofin] {title}: 번호 못 찾음 — 조각 앞부분: {head}")
    return ""


def fetch(key: str, title: str, pid: str) -> None:
    if not pid:
        pid = find_id(title)
        time.sleep(1)
    if not pid:
        return
    print(f"[lofin] {key}: {title} pdtaId={pid}")
    try:
        S.get(f"{BASE}/portal/LF5110000.do?pdtaId={pid}&rdIncrYn=Y", timeout=60)
    except Exception:  # noqa: BLE001
        pass
    rows: list[dict] = []
    for page in range(1, 400):
        body = {"menuUrl": "/lf/pfinDtaOpen/dtst/dtstSvi/retvDtstDtsSheet.do", "menuNm": "재정 데이터셋 - Sheet", "menuParaCn": "CJG",
                "menuId": "LF5110000", "uprMenuId": "LF5100000", "crtrLvl": "", "curPage": page, "pdtaId": pid, "pdtaSvTyCntt": "S",
                "rdIncrYn": "", "frstParamYn": "", "ext": "csv", "title": title, "srchCndDvSubCd": "", "srchCndDvSubCd2": "",
                "srchCndDvSubCd3": "", "srchCndDvCd": "", "srchCrstCn": "", "ststPrvdYn": "", "inqFyr": "", "inqWaLafHgNm": SIDO,
                "inqLafHgNm": "", "pageSize": PAGE}
        try:
            r = S.post(BASE + "/lf/pfinDtaOpen/dtst/dtstSvi/retvDtstDtsExcelDown.do", json=body, timeout=120)
            lst = r.json().get("resultList") or []
        except Exception as e:  # noqa: BLE001
            print(f"[lofin] {key} {page}쪽 실패: {str(e)[:160]}")
            break
        if not lst:
            break
        got = [x for x in lst if str(x.get("waLafHgNm", "")).startswith(SIDO) or str(x.get("lafCd", "")).startswith("27")]
        rows += got
        if page == 1:
            print(f"[lofin] {key} 1쪽: {len(lst)}행 중 대구 {len(got)}행 · 열 {list(lst[0].keys())}")
        if len(lst) < PAGE:
            break
        time.sleep(1)
    if not rows:
        print(f"[lofin] {key}: 대구 행 없음 — 저장 안 함")
        return
    cols = list(dict.fromkeys(k for x in rows for k in x if k != "rn"))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{key}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    yrs = sorted({str(x.get("fyr", "")) for x in rows})
    meta = {"title": title, "pdtaId": pid, "rows": len(rows), "years": [yrs[0], yrs[-1]] if yrs else [], "unit": "원",
            "source": "행정안전부 지방재정365 재정 데이터셋", "url": f"{BASE}/portal/LF5110000.do?pdtaId={pid}&rdIncrYn=Y", "fetched": time.strftime("%Y-%m-%d")}
    (OUT / f"{key}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[lofin] {key}: 대구 {len(rows)}행 · {meta['years']} 저장")


def main(argv: list[str]) -> int:
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    try:
        S.get(BASE + "/portal/LF5100000.do", timeout=60)
    except Exception as e:  # noqa: BLE001
        print("[lofin] 첫 화면 실패", str(e)[:120])
        return 0
    for key, (title, pid) in SETS.items():
        if only and key not in only:
            continue
        fetch(key, title, pid)
        time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
