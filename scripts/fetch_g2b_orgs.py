#!/usr/bin/env python3
"""조달청 「나라장터 사용자정보 서비스」(공공데이터포털 15129466) 수요기관정보조회로 대구 지자체·소속기관·공단의
수요기관명·수요기관코드·사업자등록번호를 받아 data/vat/orgs/daegu_g2b.csv 로 둔다(운영자 지시 2026-11-03 '기관 번호는 니가 넣을 수 있잖아').

사용: DATA_GO_KR_KEY=… python3 scripts/fetch_g2b_orgs.py [--probe] [--names 이름,이름]
 - 조회는 수요기관명(dminsttNm)으로 지자체·공단 이름마다 한 번. 이름 조회가 안 되면 --probe 로 응답 머리를 로그에 찍어 조회구분(inqryDiv)을 맞춘다.
 - 법인등록번호·담당자 같은 칸은 저장하지 않는다. 사업자등록번호는 기관(공공기관) 번호라 개인정보가 아니다.
공공데이터포털 키는 이 API 에 활용신청이 되어 있어야 한다(없으면 'SERVICE KEY IS NOT REGISTERED ERROR').
"""
import csv, json, os, sys, time, urllib.error, urllib.parse, urllib.request

BASE = "https://apis.data.go.kr/1230000/ao/UsrInfoService02"
OPS = [o for o in (os.environ.get("G2B_OPS") or "getDminsttInfo02,getDminsttInfo").split(",") if o.strip()]
NAMES = ["대구광역시", "대구광역시 중구", "대구광역시 동구", "대구광역시 서구", "대구광역시 남구", "대구광역시 북구", "대구광역시 수성구", "대구광역시 달서구", "대구광역시 달성군", "대구광역시 군위군",
         "달성군시설관리공단", "달성군 시설관리공단", "대구공공시설관리공단", "달서구시설관리공단", "수성구시설관리공단", "북구시설관리공단", "동구시설관리공단", "서구시설관리공단", "남구시설관리공단", "중구시설관리공단", "군위군시설관리공단",
         "대구광역시시설관리공단", "대구도시개발공사", "대구교통공사", "대구환경공단"]
OUT = "data/vat/orgs/daegu_g2b.csv"
FIELDS = ["name", "code", "bizno", "kind", "type", "addr", "valid", "regdt", "query"]


def call(op, params, key):
    q = dict(params); q["serviceKey"] = key; q["type"] = "json"
    url = f"{BASE}/{op}?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "daitda-vat (https://vat-daitda.pages.dev)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:   # 400/500 도 본문(오류 사유)을 돌려준다
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:300]}")


def items_of(text):
    try:
        j = json.loads(text)
    except Exception:
        return None, text[:300]
    body = (j.get("response") or {}).get("body") or {}
    hdr = (j.get("response") or {}).get("header") or {}
    its = body.get("items")
    if isinstance(its, dict): its = its.get("item") or []
    if isinstance(its, list) and its and not isinstance(its[0], dict): its = []
    return its if isinstance(its, list) else [], f"{hdr.get('resultCode')} {hdr.get('resultMsg')} total={body.get('totalCount')}"


def row_of(it, query):
    g = lambda *ks: next((str(it[k]).strip() for k in ks if it.get(k) not in (None, "")), "")
    return {"name": g("dminsttNm", "dmstNm", "orgNm"), "code": g("dminsttCd", "dmstCd", "orgCd"), "bizno": g("bizno", "bsnsRgstNo", "bizRegNo"),
            "kind": g("jrsdctnDivNm", "ofclDivNm"), "type": g("dminsttTyNm", "dminsttTypeNm", "orgTyNm"), "addr": g("adrs", "addr", "dminsttAdrs"),
            "valid": g("vldPrd", "validPrd"), "regdt": g("rgstDt", "regDt"), "query": query}


def main():
    key = os.environ.get("DATA_GO_KR_KEY", "")
    if not key:
        print("DATA_GO_KR_KEY 없음"); return 2
    probe = "--probe" in sys.argv
    names = NAMES
    if "--names" in sys.argv: names = [s.strip() for s in sys.argv[sys.argv.index("--names") + 1].split(",") if s.strip()]
    rows, seen = [], set()
    op_ok = None
    for nm in names:
        got = None
        for op in ([op_ok] if op_ok else OPS):
            for div in ("3", "2", "1"):
                params = {"pageNo": 1, "numOfRows": 100, "inqryDiv": div, "dminsttNm": nm}
                if div == "1": params.update({"inqryBgnDt": "199001010000", "inqryEndDt": "209912312359"})
                try:
                    text = call(op, params, key)
                except Exception as e:
                    print(f"  {op} div={div} {nm}: 요청 실패 {e}"); continue
                its, msg = items_of(text)
                if probe: print(f"  {op} div={div} {nm}: {msg} | {text[:400]}")
                if its is None: continue
                if its:
                    got = its; op_ok = op; print(f"  {op} div={div} {nm}: {len(its)}건 ({msg})"); break
                elif "00" in str(msg)[:4] or "NORMAL" in str(msg):
                    print(f"  {op} div={div} {nm}: 0건 ({msg})")
            if got: break
            if op_ok: break
        if not got: continue
        for it in got:
            if probe and got.index(it) < 2: print("   예:", {k: v for k, v in it.items() if k not in ("corpRgstNo",)})
            r = row_of(it, nm)
            if not r["bizno"] and not r["code"]: continue
            if nm not in r["name"].replace(" ", "") and nm.replace(" ", "") not in r["name"].replace(" ", ""): pass
            k = (r["code"], r["bizno"])
            if k in seen: continue
            seen.add(k); rows.append(r)
        time.sleep(0.3)
    rows.sort(key=lambda r: (r["query"], r["name"]))
    if rows:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
        print(f"저장 {OUT}: {len(rows)}행")
    else:
        print("받은 행 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
