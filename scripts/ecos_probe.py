#!/usr/bin/env python3
"""ECOS 웹 화면의 내부 요청(serviceEndpoint/httpService/request.json)으로 통계표 나무를 받아 낱말이 든 항목을 찍는다(조사용, 저장소 변경 없음).

오픈API 통계표 목록(StatisticTableList)에 없는 표(지역산업연관표 세부 계수표 등)가 웹 화면의 나무에는 있는지 보려고.
site_probe.yml --xhr 로 잡은 trxCd: OSUSD01R01(outerSysYn Y, 통계표 나무 649KB)·OSUUA01R01(291KB). robots.txt 는 Disallow 없음(2026-10-06 확인).
사용: python3 scripts/ecos_probe.py [--words 지역산업,연관] [--trx OSUSD01R01,OSUUA01R01] [--full]
"""
import json, sys, time
import requests

URL = "https://ecos.bok.or.kr/serviceEndpoint/httpService/request.json"
UA = "daitda-note-bot/1.0 (+https://daitda.co.kr)"


def call(trx: str, data: dict, scr="IECOSPCM02") -> dict:
    ip = requests.get("https://ecos.bok.or.kr/serviceEndpoint/ipcheck", headers={"User-Agent": UA}, timeout=30).text.strip()
    body = {"header": {"guidSeq": 1, "trxCd": trx, "scrId": scr, "sysCd": "03", "fstChnCd": "WEB", "langDvsnCd": "KO", "envDvsnCd": "D",
                       "sndRspnDvsnCd": "S", "sndDtm": time.strftime("%Y%m%d"), "ipAddr": ip, "usrId": "IECOSPC", "pageNum": 1, "pageCnt": 1000}, "data": data}
    r = requests.post(URL, json=body, headers={"User-Agent": UA, "Content-Type": "application/json", "Referer": "https://ecos.bok.or.kr/"}, timeout=120)
    return r.json()


def walk(o, path=""):
    """중첩 dict/list 를 모두 돌며 (경로, dict) 를 낸다"""
    if isinstance(o, dict):
        yield path, o
        for k, v in o.items():
            yield from walk(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}[{i}]")


def main() -> int:
    a = sys.argv[1:]
    words = (a[a.index("--words") + 1] if "--words" in a else "지역산업,연관표,유발계수").split(",")
    trxs = (a[a.index("--trx") + 1] if "--trx" in a else "OSUSD01R01,OSUUA01R01").split(",")
    full = "--full" in a
    for trx in trxs:
        data = {"outerSysYn": "Y"} if trx == "OSUSD01R01" else {}
        try:
            res = call(trx, data)
        except Exception as e:  # noqa: BLE001
            print(f"[{trx}] 실패 {e}"); continue
        s = json.dumps(res, ensure_ascii=False)
        print(f"[{trx}] {len(s):,}자, 최상위 키 {list(res.keys())}")
        d = res.get("data") or res
        # 첫 항목 구조
        shown = 0
        for p, o in walk(d):
            if shown < 2 and isinstance(o, dict) and any(isinstance(v, str) and len(v) > 2 for v in o.values()):
                print(f"   예시 {p}: {json.dumps(o, ensure_ascii=False)[:400]}"); shown += 1
        hits = []
        for p, o in walk(d):
            txt = " ".join(str(v) for v in o.values() if isinstance(v, (str, int)))
            if any(w in txt for w in words):
                hits.append((p, o))
        print(f"   낱말 {words} 든 항목 {len(hits)}개")
        for p, o in hits[: (200 if full else 60)]:
            print(f"   - {p}: {json.dumps(o, ensure_ascii=False)[:500]}")
        time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
