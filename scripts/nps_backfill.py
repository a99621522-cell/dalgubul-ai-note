#!/usr/bin/env python3
"""국민연금 가입 사업장 내역(공공데이터포털 15083277) 과거 월 되살리기 — 추세 보강 1단계(운영자 지시 2026-10-06 '국민연금은 니가 가져와').

포털은 최신 한 달 파일만 보여 주지만, 교체된 옛 파일도 첨부 id(atchFileId)로는 여전히 내려받힌다(2026-10-06 확인: 2026-08-25 등록분 FILE_000000007629828 → 2026-07 자료 116MB).
달마다 바뀌는 식별자(publicDataDetailPk uddi·atchFileId)는 웨이백 머신(web.archive.org)에 남은 자료 페이지 스냅샷에서 뽑는다(2024-02 ~ 2026-03, 17개).
  python3 scripts/nps_backfill.py --list            # 스냅샷·식별자만 출력
  python3 scripts/nps_backfill.py                   # 없는 달만 받아 data/nps/YYYYMM.csv (collect_nps.py --file)
  python3 scripts/nps_backfill.py --max 3 --force   # 앞 3개만, 있는 달도 다시
표준 라이브러리 + requests. 받은 전국 원본은 처리 뒤 지운다(저장소에 두지 않음). 개인정보 열은 collect_nps 가 저장하지 않는다.
"""
from __future__ import annotations

import argparse, json, re, subprocess, sys, tempfile, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PK = "15083277"
PAGE = f"https://www.data.go.kr/data/{PK}/fileData.do"
CDX = "https://web.archive.org/cdx/search/cdx"
WB = "https://web.archive.org/web/{ts}id_/" + PAGE
DL_NEW = "https://www.data.go.kr/tcs/dss/selectFileDataDownload.do"
DL_OLD = "https://www.data.go.kr/cmm/cmm/fileDownload.do"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
OUT = ROOT / "data" / "nps"
# 로그에서 확인한 것(웨이백에 없는 최근 달): 등록일 → (uddi, atchFileId)
KNOWN = {
    "20260825": ("uddi:b5ac0771-a9e3-4ce0-9505-ad0439d97b79", "FILE_000000007629828"),   # 2026-07 자료
    "20260923": ("uddi:8e0d590f-768e-4cbd-9560-c7168c8d13b6", "FILE_000000007692952"),   # 2026-08 자료
}


def snapshots(sess: requests.Session, since: str = "2023") -> list[str]:
    r = sess.get(CDX, params={"url": PAGE.replace("https://www.", ""), "output": "json", "from": since, "filter": "statuscode:200", "collapse": "digest"},
                 headers=UA, timeout=60)
    r.raise_for_status()
    rows = r.json()
    return [row[1] for row in rows[1:]]


def ids_from_snapshot(sess: requests.Session, ts: str) -> dict:
    """스냅샷 HTML 에서 uddi·atchFileId·자료 이름 날짜를 뽑는다."""
    r = None
    for i, wait in enumerate((0, 20, 45, 90)):   # 웨이백은 429(요청 제한)를 자주 돌려준다 — 기다렸다 다시
        if wait:
            time.sleep(wait)
        r = sess.get(WB.format(ts=ts), headers=UA, timeout=90)
        if r.status_code == 200:
            break
        if r.status_code not in (429, 503):
            return {"ts": ts, "error": f"HTTP {r.status_code}"}
    if r is None or r.status_code != 200:
        return {"ts": ts, "error": f"HTTP {r.status_code}"}
    html = r.text
    uddis = list(dict.fromkeys(re.findall(r"uddi:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", html)))
    atchs = list(dict.fromkeys(re.findall(r"FILE_\d{15}", html)))
    names = re.findall(r"국민연금 가입 사업장 내역_(\d{8})", html)
    return {"ts": ts, "uddi": uddis[0] if uddis else "", "atch": atchs, "reg": names[0] if names else ""}


def resolve_atch(sess: requests.Session, uddi: str) -> tuple[str, str]:
    """live 포털에 옛 uddi 로 물어 그 판의 atchFileId·파일 이름을 받는다(JSON). 안 되면 빈 값."""
    try:
        r = sess.post(DL_NEW, data={"publicDataPk": PK, "publicDataDetailPk": uddi, "fileDetailSn": "1"}, headers={**UA, "Referer": PAGE}, timeout=60)
        body = r.text.strip()
        if body.startswith("{"):
            j = json.loads(body)
            s = json.dumps(j, ensure_ascii=False)
            m = re.search(r'"atchFileId":\s*"(FILE_\d+)"', s)
            n = re.search(r'"orginlFileNm":\s*"([^"]+)"', s) or re.search(r'"dataNm":\s*"([^"]+)"', s)
            return (m.group(1) if m else "", n.group(1) if n else "")
    except Exception as e:  # noqa: BLE001
        print(f"   uddi 조회 실패 {uddi}: {e}")
    return ("", "")


def download(sess: requests.Session, atch: str, dest: Path) -> bool:
    for sn in ("1", "2"):
        try:
            with sess.get(DL_OLD, params={"atchFileId": atch, "fileDetailSn": sn}, headers={**UA, "Referer": PAGE}, timeout=600, stream=True) as r:
                ct = r.headers.get("Content-Type", "")
                if r.status_code != 200 or "text/html" in ct:
                    print(f"   {atch} sn={sn}: HTTP {r.status_code} {ct[:40]} — 파일 아님")
                    continue
                n = 0
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk); n += len(chunk)
                print(f"   받음 {atch}: {n:,} bytes")
                return n > 1_000_000
        except Exception as e:  # noqa: BLE001
            print(f"   내려받기 실패 {atch}: {e}")
    return False


def have_months() -> set[str]:
    return {p.stem for p in OUT.glob("*.csv") if re.fullmatch(r"\d{6}", p.stem)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="식별자만 출력")
    ap.add_argument("--max", type=int, default=0, help="받을 최대 개수(0=전부)")
    ap.add_argument("--force", action="store_true", help="이미 있는 달도 다시 받음")
    ap.add_argument("--since", default="2023", help="웨이백 스냅샷 시작 연도")
    a = ap.parse_args(argv)
    sess = requests.Session()
    cands: dict[str, dict] = {}   # uddi → info
    try:
        tss = snapshots(sess, a.since)
        print(f"웨이백 스냅샷 {len(tss)}개")
    except Exception as e:  # noqa: BLE001
        print(f"웨이백 CDX 실패: {e}"); tss = []
    for ts in tss:
        info = ids_from_snapshot(sess, ts)
        print(f"  {ts}: {info}")
        if info.get("uddi") and info["uddi"] not in cands:
            cands[info["uddi"]] = info
        time.sleep(6)
    for reg, (uddi, atch) in KNOWN.items():
        cands.setdefault(uddi, {"ts": "", "uddi": uddi, "atch": [atch], "reg": reg})
    print(f"후보 판 {len(cands)}개")
    if a.list:
        return 0
    have = have_months()
    done = 0
    for uddi, info in cands.items():
        if a.max and done >= a.max:
            break
        atch, fname = resolve_atch(sess, uddi)
        if not atch:
            atch = next((x for x in info.get("atch", []) if x), "")
        reg = re.sub(r"\D", "", fname)[:8] or info.get("reg", "")
        print(f"[{reg or '?'}] uddi {uddi} → atch {atch or '없음'} {fname}")
        if not atch:
            continue
        # 등록일(YYYYMMDD)의 전달이 자료 달(포털 안내: 23일쯤 전월 자료). 파일 안 자료생성년월이 최종 기준이라 어림값은 건너뛰기 판단에만 쓴다
        guess = ""
        if re.fullmatch(r"\d{8}", reg):
            y, m = int(reg[:4]), int(reg[4:6]); m -= 1
            if m == 0: y, m = y - 1, 12
            guess = f"{y}{m:02d}"
        if guess and guess in have and not a.force:
            print(f"   {guess} 이미 있음 — 건너뜀"); continue
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / f"nps_{reg or uddi[5:13]}.csv"
            if not download(sess, atch, raw):
                continue
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "collect_nps.py"), "--file", str(raw)], capture_output=True, text=True)
            print("   " + (r.stdout.strip().splitlines() or ["(출력 없음)"])[-1])
            if r.returncode != 0:
                print("   collect_nps 실패: " + r.stderr[-400:])
                continue
        done += 1
        have = have_months()
        time.sleep(2)
    print(f"완료: {done}개 달 반영 → {sorted(have_months())}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
