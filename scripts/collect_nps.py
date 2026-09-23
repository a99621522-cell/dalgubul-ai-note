#!/usr/bin/env python3
"""국민연금공단 「국민연금 가입 사업장 내역」(월간 CSV, 전국 약 59만 건) → 대구 사업장만 골라
scripts/data/sources/nps_YYYYMMDD.json 으로 저장한다(최근 2개월치만 보관). 키 불필요.

받는 곳(순서대로 시도)
  1) 공공데이터포털 파일데이터 15083277 페이지에서 현재 첨부 링크(/cmm/cmm/fileDownload.do?atchFileId=…)를 찾아 내려받음
     — 매달 새 파일로 바뀌므로 링크를 매번 페이지에서 다시 읽는다 (2026-08 기준 116MB CSV, cp949)
  2) 국민연금공단 공개자료 게시글 첨부(fileDown.do) — 포털이 막힐 때의 예비. 2025-09 파일 고정 id

무엇을 남기나 (공통 스키마 + 국민연금 고유 항목)
  name, address(읍면동까지만 제공됨), sector_code, sector, product(없음 → ""), source="nps", collected,
  bizr6(사업자등록번호 앞 6자리 — 파일이 6자리까지만 제공), corp_type(법인/개인), status(등록/탈퇴),
  district(구·군), emd(읍면동), bjd_code(법정동코드), subscribers(가입자수), applied(적용일자), withdrawn(탈퇴일자),
  new_month/lost_month(그달 신규취득·상실 인원 — 월별 파일을 쌓으면 고용 추이가 됨),
  zone_hint(알파시티·첨복단지·테크노폴리스·성서특구 — 해당 '동' 소재라는 뜻이지 단지 입주 확인이 아님)

포함 범위: 파일 자체가 가입자 3인 이상 법인 / 10인 이상 개인사업장만 담는다. 기본은 '등록' 상태만 남긴다.
저장하지 않는 것: 당월고지금액(사업장 재무 추정에 악용될 수 있어 제외), 우편번호.

사용: python3 scripts/collect_nps.py [--keep-withdrawn] [--dry-run]
"""
import csv
import io
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "scripts" / "data" / "sources"
UA = {"User-Agent": "Mozilla/5.0 (compatible; dalgubul-ai-note/0.1; +personal blog collector)"}
PORTAL_PAGE = "https://www.data.go.kr/data/15083277/fileData.do"
NPS_FALLBACK = "https://m.nps.or.kr/fileDown.do?atchFileId=FL25002880&atchFileSn=1"   # 2025-09 파일(zip)
DRY = "--dry-run" in sys.argv
KEEP_WITHDRAWN = "--keep-withdrawn" in sys.argv

ZONES = {  # (구·군, 읍면동들) → 표시명. '동 소재'일 뿐 단지 입주 확인이 아니다
    "알파시티": ("수성구", ("대흥동",)),
    "첨복단지": ("동구", ("신서동", "각산동")),
    "테크노폴리스": ("달성군", ("유가읍", "현풍읍")),
    "성서특구": ("달서구", ("호림동", "월암동")),
}


def find_portal_link() -> tuple[str, str]:
    """포털 페이지에서 현재 첨부 링크와 파일명을 찾는다."""
    r = requests.get(PORTAL_PAGE, headers=UA, timeout=60)
    r.raise_for_status()
    m = re.search(r'https://www\.data\.go\.kr/cmm/cmm/fileDownload\.do\?atchFileId=[A-Z0-9_]+&fileDetailSn=\d+[^"\'<>\s]*', r.text)
    t = re.search(r"<title>([^<]*)</title>", r.text)
    if not m:
        raise RuntimeError("포털 페이지에서 첨부 링크를 찾지 못함")
    return m.group(0).replace("&amp;", "&"), (t.group(1).strip() if t else "")


def download(url: str, dst: Path, referer: str) -> None:
    with requests.get(url, headers={**UA, "Referer": referer}, timeout=600, stream=True) as r:
        r.raise_for_status()
        with dst.open("wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)


def open_csv(path: Path):
    """zip 이면 안의 CSV, 아니면 그대로. cp949 우선."""
    head = path.read_bytes()[:4]
    if head.startswith(b"PK"):
        import zipfile
        z = zipfile.ZipFile(path)
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        raw = z.open(name)
    else:
        raw = path.open("rb")
    return io.TextIOWrapper(raw, encoding="cp949", errors="replace", newline="")


def col(hdr: list[str], *names: str) -> int:
    for n in names:
        for i, h in enumerate(hdr):
            if n in h:
                return i
    raise KeyError(names)


def main() -> None:
    tmp = Path(tempfile.gettempdir()) / "nps_workplaces.csv"
    src_label = ""
    try:
        url, title = find_portal_link()
        print(f"[nps] 포털 첨부: {title[:60]}")
        download(url, tmp, PORTAL_PAGE)
        src_label = "공공데이터포털 15083277"
    except Exception as e:  # noqa: BLE001
        print(f"[nps] 포털 실패({e}) → 공단 예비 링크 시도")
        try:
            download(NPS_FALLBACK, tmp, "https://m.nps.or.kr/")
            src_label = "국민연금공단 공개자료(2025-09 파일)"
        except Exception as e2:  # noqa: BLE001
            print(f"[nps] 예비 링크도 실패: {e2} — 종료")
            return
    print(f"[nps] 내려받음 {tmp.stat().st_size/1024/1024:.0f} MB ({src_label})")

    fh = open_csv(tmp)
    rd = csv.reader(fh)
    hdr = [h.strip() for h in next(rd)]
    i = {
        "ym": col(hdr, "자료생성년월"), "name": col(hdr, "사업장명"), "bizr": col(hdr, "사업자등록번호"),
        "status": col(hdr, "가입상태"), "addr_j": col(hdr, "지번상세주소"), "addr_r": col(hdr, "도로명상세주소"),
        "bjd": col(hdr, "고객법정동주소코드"), "sido": col(hdr, "광역시도코드"), "ctype": col(hdr, "형태구분"),
        "ind_code": col(hdr, "업종코드"), "ind": col(hdr, "업종코드명"), "applied": col(hdr, "적용일자"),
        "withdrawn": col(hdr, "탈퇴일자"), "subs": col(hdr, "가입자수"),
        "new": col(hdr, "신규취득자수"), "lost": col(hdr, "상실가입자수"),   # 그달의 고용 흐름 — 현황판 전월 대비·12개월 합계 재료
    }
    today = date.today().isoformat()
    rows: list[dict] = []
    total = 0
    data_ym = ""
    for r in rd:
        if len(r) < len(hdr) - 2:
            continue
        total += 1
        addr = (r[i["addr_j"]] or r[i["addr_r"]] or "").strip()
        if not (addr.startswith("대구") or r[i["sido"]].strip() == "27"):
            continue
        status = "등록" if r[i["status"]].strip() == "1" else "탈퇴"
        if status == "탈퇴" and not KEEP_WITHDRAWN:
            continue
        data_ym = data_ym or r[i["ym"]].strip()
        toks = addr.split()
        district = toks[1] if len(toks) > 1 else ""
        emd = toks[2] if len(toks) > 2 else ""
        zone = next((z for z, (gu, emds) in ZONES.items() if district == gu and emd in emds), "")
        rows.append({
            "name": r[i["name"]].strip(),
            "address": addr,                      # 읍면동까지만 제공
            "district": district, "emd": emd, "bjd_code": r[i["bjd"]].strip(),
            "sector_code": r[i["ind_code"]].strip(), "sector": r[i["ind"]].strip(), "product": "",
            "bizr6": r[i["bizr"]].strip(),
            "corp_type": "법인" if r[i["ctype"]].strip() == "1" else "개인",
            "status": status,
            "subscribers": int(r[i["subs"]] or 0) if (r[i["subs"]] or "").strip().isdigit() else None,
            "applied": r[i["applied"]].strip(), "withdrawn": r[i["withdrawn"]].strip(),
            "new_month": int(r[i["new"]]) if (r[i["new"]] or "").strip().isdigit() else None,
            "lost_month": int(r[i["lost"]]) if (r[i["lost"]] or "").strip().isdigit() else None,
            "zone_hint": zone,
            "source": "nps", "collected": today,
        })
    fh.close()
    zones = {z: sum(1 for x in rows if x["zone_hint"] == z) for z in ZONES}
    corp = sum(1 for x in rows if x["corp_type"] == "법인")
    print(f"[nps] 전국 {total:,} → 대구 {len(rows):,} (법인 {corp:,}) · 자료 {data_ym} · 동 기준 {zones}")
    if DRY:
        print("[nps] dry-run — 파일 안 씀")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ym_digits = re.sub(r"[^0-9]", "", data_ym)[:6]            # "2026-07" → "202607"
    stamp = ym_digits + "01" if len(ym_digits) == 6 else today.replace("-", "")
    meta = {"source": src_label, "data_ym": data_ym, "collected": today, "total_kr": total, "daegu": len(rows),
            "note": "가입자 3인 이상 법인/10인 이상 개인사업장만 포함. 주소는 읍면동까지. 사업자등록번호는 앞 6자리만 제공됨."}
    payload = {"meta": meta, "rows": rows}
    dated = OUT_DIR / f"nps_{stamp}.json"
    dated.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # 월별 파일은 최근 2개만 남긴다(각 5MB 안팎)
    old = sorted(OUT_DIR.glob("nps_20*.json"))[:-2]
    for p in old:
        p.unlink()
    print(f"[nps] 저장: {dated.name} ({dated.stat().st_size/1024/1024:.1f} MB)" + (f", 오래된 월별 파일 정리 {len(old)}개" if old else ""))
    sp = os.environ.get("GITHUB_STEP_SUMMARY")
    if sp:
        with open(sp, "a", encoding="utf-8") as f:
            f.write(f"## 국민연금 사업장\n\n- 전국 {total:,} → 대구 {len(rows):,} (법인 {corp:,}), 자료 {data_ym}\n\n")


if __name__ == "__main__":
    main()
