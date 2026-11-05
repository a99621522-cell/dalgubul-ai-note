#!/usr/bin/env python3
"""조달청 「나라장터 사용자정보 서비스」(공공데이터포털 15129466) 수요기관정보조회로 대구 지자체·소속기관·공단의
수요기관명·수요기관코드·사업자등록번호를 받아 data/vat/orgs/daegu_g2b.csv 로 둔다(운영자 지시 2026-11-03 '기관 번호는 니가 넣을 수 있잖아').

사용: DATA_GO_KR_KEY=… python3 scripts/fetch_g2b_orgs.py [--probe] [--names 이름,이름]
 - 조회는 수요기관명(dminsttNm)으로 지자체·공단 이름마다 한 번. 이름 조회가 안 되면 --probe 로 응답 머리를 로그에 찍어 조회구분(inqryDiv)을 맞춘다.
 - 법인등록번호·담당자 같은 칸은 저장하지 않는다. 사업자등록번호는 기관(공공기관) 번호라 개인정보가 아니다.
공공데이터포털 키는 이 API 에 활용신청이 되어 있어야 한다(없으면 'SERVICE KEY IS NOT REGISTERED ERROR').
"""
import csv, datetime as dt, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

BASE = "https://apis.data.go.kr/1230000/ao/UsrInfoService02"
OPS = [o for o in (os.environ.get("G2B_OPS") or "getDminsttInfo02").split(",") if o.strip()]
NAMES_OLD = ["대구광역시", "대구광역시 중구", "대구광역시 동구", "대구광역시 서구", "대구광역시 남구", "대구광역시 북구", "대구광역시 수성구", "대구광역시 달서구", "대구광역시 달성군", "대구광역시 군위군",
         "달성군시설관리공단", "달성군 시설관리공단", "대구공공시설관리공단", "달서구시설관리공단", "수성구시설관리공단", "북구시설관리공단", "동구시설관리공단", "서구시설관리공단", "남구시설관리공단", "중구시설관리공단", "군위군시설관리공단",
         "대구광역시시설관리공단", "대구도시개발공사", "대구교통공사", "대구환경공단"]
OUT = "data/vat/orgs/daegu_g2b.csv"
FIELDS = ["name", "code", "bizno", "kind", "type", "top", "addr", "valid", "regdt", "query"]   # 전화·팩스는 두지 않는다


def call(op, params, key):
    q = dict(params); q["serviceKey"] = key; q["type"] = "json"
    url = f"{BASE}/{op}?" + urllib.parse.urlencode(q, safe="%")   # 인코딩 키(%2B…)를 다시 인코딩하지 않는다
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
    clean = lambda v: v.replace(",", " ").replace("\n", " ")   # vat.ts 가 CSV 를 쉼표로만 나눈다
    return {"name": clean(g("dminsttNm")), "code": g("dminsttCd"), "bizno": g("bizno"),
            "kind": g("jrsdctnDivNm"), "type": clean(" / ".join(x for x in (g("insttTyCdLrgclsfcNm"), g("insttTyCdMidclsfcNm")) if x)),
            "addr": clean(" ".join(x for x in (g("rgnNm"), g("adrs")) if x)), "top": clean(g("toplvlInsttNm")), "dlt": g("dltYn"),
            "valid": g("vldPrdEndDt"), "regdt": g("rgstDt")[:10], "query": query}


def in_daegu(r):
    """대구에 있는 기관(지역명·주소·최상위 기관)만 — 교육청·교육지원청 소속 학교는 뺀다(점검기는 지자체·공단 신고용)"""
    where = " ".join((r["addr"], r["top"], r["name"]))
    return ("대구" in where) and not re.search(r"교육청|교육지원청", r["name"] + r["top"]) and r["dlt"] != "Y"


def main():
    """수요기관정보조회(getDminsttInfo02) — 참고문서(조달청_OpenAPI참고자료_나라장터_사용자정보서비스): 조회구분 1 = 등록일 기준(시작·종료 일시 필수),
    2 = 변경일 기준, 3 = 사업자등록번호 기준. 기관 이름(dminsttNm)은 조회구분 1·2 의 선택 조건이라 등록 연도마다 기간을 나눠 묻는다
    (1990~2099 한 번에는 '입력범위값 초과', 2026-11-05 확인). 한 해가 넘치면 달로 나눈다."""
    key = os.environ.get("DATA_GO_KR_KEY", "")
    if not key:
        print("DATA_GO_KR_KEY 없음"); return 2
    probe = "--probe" in sys.argv
    names = ["대구", "시설관리공단", "시설공단"]
    if "--names" in sys.argv: names = [s.strip() for s in sys.argv[sys.argv.index("--names") + 1].split(",") if s.strip()]
    y0 = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 2000
    op = OPS[0]
    rows, seen, calls = {}, set(), 0

    def ask(nm, b, e):
        nonlocal calls
        out, page = [], 1
        while True:
            params = {"pageNo": page, "numOfRows": 999, "inqryDiv": "1", "inqryBgnDt": b, "inqryEndDt": e, "dminsttNm": nm}
            try:
                text = call(op, params, key); calls += 1
            except Exception as ex:
                print(f"  {nm} {b[:8]}~{e[:8]}: 요청 실패 {str(ex)[:200]}"); return None
            if "SERVICE_KEY_IS_NOT_REGISTERED" in text:
                print("  활용신청이 안 된 키(15129466)"); raise SystemExit(2)
            if '"resultCode": "07"' in text or '"resultCode":"07"' in text:
                return "range"
            its, msg = items_of(text)
            if probe and page == 1: print(f"  {nm} {b[:8]}~{e[:8]}: {msg}" + ("" if its else f" | {text[:200]}"))
            if its is None: return None
            out += its
            try: total = int(json.loads(text)["response"]["body"]["totalCount"])
            except Exception: total = len(out)
            if not its or len(out) >= total: return out
            page += 1; time.sleep(0.3)

    for nm in names:
        for y in range(y0, dt.date.today().year + 1):
            spans = [(f"{y}01010000", f"{y}12312359")]
            got = ask(nm, *spans[0])
            if got == "range":   # 한 해가 넘치면 달로
                got = []
                for m in range(1, 13):
                    last = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
                    r = ask(nm, f"{y}{m:02d}010000", f"{y}{m:02d}{last}2359")
                    if isinstance(r, list): got += r
                    time.sleep(0.3)
            if not isinstance(got, list): continue
            n0 = len(rows)
            for it in got:
                r = row_of(it, nm)
                if probe and len(rows) < 3 and n0 == 0: print("   예:", {k: v for k, v in r.items()})
                if not in_daegu(r) or not (r["bizno"] or r["code"]): continue
                rows[(r["code"], r["bizno"])] = r
            if len(rows) > n0 or probe: print(f"  {nm} {y}: 받은 {len(got)}행 → 대구 {len(rows) - n0}곳 더함 (누적 {len(rows)}, 호출 {calls})", flush=True)
            time.sleep(0.3)
    out = sorted(rows.values(), key=lambda r: (r["top"], r["name"]))
    if out:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore"); w.writeheader(); w.writerows(out)
        print(f"저장 {OUT}: {len(out)}행 (호출 {calls})")
    else:
        print(f"받은 행 없음 (호출 {calls})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
