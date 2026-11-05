#!/usr/bin/env python3
"""조달청 「나라장터 계약정보서비스」(공공데이터포털 15129427, https://apis.data.go.kr/1230000/ao/CntrctInfoService)로
대구 본청·구·군이 계약기관이거나 수요기관인 공사·용역·물품 계약을 받아 data/vat/contracts/<gov>.json 으로 둔다
(운영자 지시 2026-11-05 '조달청 api 를 연결할 수 있어? → 그렇게해').

쓰는 곳: 지자체 부가세 절감 점검기 '지난 돈 돌려받기' 공개 지출 자료 탭의 '나라장터 계약' 표 — 공개 지출 자료(세부사업·통계목 합계, 거래처 없음)에
'어느 업체와 맺은 어느 계약'을 이어, 받아 올 세금계산서를 계약 단위로 적는다. 계약금액은 지출액과 겹치므로 공제 추정에 더하지 않는다.

오퍼레이션(나라장터 검색조건에 의한 계약현황): getCntrctInfoListCnstwkPPSSrch(공사)·getCntrctInfoListServcPPSSrch(용역)·getCntrctInfoListThngPPSSrch(물품)
 - 요청: serviceKey·pageNo·numOfRows·inqryDiv(필수)·type=json·inqryBgnDate·inqryEndDate(YYYYMMDD)·insttDivCd·insttNm …
 - 조회구분(inqryDiv)·기관구분코드(insttDivCd)의 값은 공공데이터포털 화면의 명세에 적혀 있지 않아 기본값(조회구분 1 = 계약체결일자, 기관구분 1 = 계약기관·2 = 수요기관 짐작)을 쓰고,
   --probe 가 조합마다 totalCount 와 첫 행의 칸 이름을 로그로 찍어 맞춘다(--inqry-div · --instt-div 로 바꿈).

저장하지 않는 것: 계약기관 담당자 이름·전화·팩스(cntrctInsttOfcl*), 업체 대표자 이름(corpList 안의 대표자명 칸). 업체는 상호·사업자등록번호·지분율만.
키는 DATA_GO_KR_KEY — 이 API 에 활용신청이 되어 있어야 한다(없으면 'SERVICE KEY IS NOT REGISTERED ERROR' → 종료 코드 2).
하루 호출 한도(개발계정)를 넘으면 받은 만큼 저장하고 종료 코드 3 — 다음 실행이 data/vat/contracts/state.json 의 끝난 구간을 건너뛴다.

사용: DATA_GO_KR_KEY=… python3 scripts/fetch_g2b_contracts.py [--govs daegu,dalseong] [--from 2021-01] [--to 2026-10] [--kinds 공사,용역,물품] [--probe]
"""
import argparse, datetime as dt, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

BASE = "https://apis.data.go.kr/1230000/ao/CntrctInfoService"
OPS = {"공사": "getCntrctInfoListCnstwkPPSSrch", "용역": "getCntrctInfoListServcPPSSrch", "물품": "getCntrctInfoListThngPPSSrch"}
# 나라장터에 등록된 수요기관 이름(기관명 검색은 부분 일치로 보고 결과의 기관 이름으로 다시 거른다)
GOVS = {"daegu": "대구광역시", "jung": "대구광역시 중구", "dong": "대구광역시 동구", "seo": "대구광역시 서구", "nam": "대구광역시 남구",
        "buk": "대구광역시 북구", "suseong": "대구광역시 수성구", "dalseo": "대구광역시 달서구", "dalseong": "대구광역시 달성군", "gunwi": "대구광역시 군위군"}
OUT = "data/vat/contracts"
UA = {"User-Agent": "daitda-vat (https://vat-daitda.pages.dev)"}


class Stop(Exception):
    def __init__(self, code, msg): super().__init__(msg); self.code = code


def call(op, params, key):
    q = {"serviceKey": key, "type": "json", **params}
    url = f"{BASE}/{op}?" + urllib.parse.urlencode(q, safe="%")
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                text = r.read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")
            break
        except Exception as e:   # 연결 끊김은 두 번 더
            if i == 2:
                print(f"  연결 실패 {op}: {e}", flush=True); return None
            time.sleep(5 * (i + 1))
    if "SERVICE_KEY_IS_NOT_REGISTERED" in text or "SERVICE KEY IS NOT REGISTERED" in text:
        print(f"  응답: {text[:300]}", flush=True)
        raise Stop(2, "이 키에 계약정보서비스(15129427) 활용신청이 안 되어 있습니다 — 공공데이터포털에서 활용신청 뒤 다시 실행")
    if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in text:
        raise Stop(3, "하루 호출 한도를 넘었습니다 — 받은 만큼 저장하고 다음 실행이 이어 받습니다")
    try:
        j = json.loads(text)
    except Exception:
        print(f"  JSON 아님 {op}: {text[:200]}", flush=True); return None
    resp = j.get("response") or j
    hdr = resp.get("header") or {}
    if str(hdr.get("resultCode", "00")) not in ("00", "0"):
        print(f"  결과 코드 {hdr.get('resultCode')} {hdr.get('resultMsg')} ({op} {params})", flush=True)
        return None
    body = resp.get("body") or {}
    items = body.get("items") or []
    if isinstance(items, dict):
        items = items.get("item") or []
    if isinstance(items, dict):
        items = [items]
    return {"total": int(body.get("totalCount") or 0), "items": items}


BIZNO = re.compile(r"^\d{3}-?\d{2}-?\d{5}$")
def parse_corps(s):
    """업체목록 '[순번^구분^상호^대표자^…^지분율^사업자등록번호],[…]' 꼴(칸 순서는 판마다 다를 수 있어 모양으로 고른다).
    대표자 이름은 읽지 않는다 — 상호(법인 표기나 4글자 이상), 사업자등록번호(10자리), 지분율(0~100 숫자)만."""
    out = []
    for grp in re.findall(r"\[([^\]]*)\]", s or ""):
        parts = [p.strip() for p in grp.split("^")]
        no = next((p.replace("-", "") for p in parts if BIZNO.match(p)), "")
        name = ""
        for p in parts:
            if not p or BIZNO.match(p) or re.fullmatch(r"[\d.]+", p) or p in ("대표사", "구성사", "단독", "공동", "대한민국", "국내", "국외"):
                continue
            if re.search(r"주식회사|\(주\)|㈜|\(유\)|\(합\)|유한|건설|산업|공사|엔지니어링|기술|개발|종합|전기|통신|조경|토건|기업|상사|협동조합|재단|사단", p) or len(p) >= 5:
                name = p; break
        sh = next((p for p in parts if re.fullmatch(r"\d{1,3}(\.\d+)?", p) and float(p) <= 100 and p not in (parts[0],)), "")
        if name or no:
            out.append({"nm": name, "no": no, **({"sh": sh} if sh else {})})
    return out


def parse_instts(s):
    """수요기관목록 '[순번^기관코드^기관명^…]' → 기관 이름만"""
    names = []
    for grp in re.findall(r"\[([^\]]*)\]", s or ""):
        for p in grp.split("^"):
            p = p.strip()
            if re.search(r"[가-힣]{2,}", p) and not re.fullmatch(r"\d+", p):
                names.append(p); break
    return names


def months(a, b):
    y, m = map(int, a.split("-")); y2, m2 = map(int, b.split("-"))
    while (y, m) <= (y2, m2):
        first = dt.date(y, m, 1); last = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))
        yield f"{y:04d}-{m:02d}", first.strftime("%Y%m%d"), last.strftime("%Y%m%d")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def row_of(kind, it):
    num = lambda v: int(float(str(v).replace(",", "") or 0)) if str(v or "").replace(",", "").replace(".", "").isdigit() else 0
    return {"k": kind, "no": it.get("untyCntrctNo") or it.get("dcsnCntrctNo") or "", "nm": it.get("cnstwkNm") or it.get("cntrctNm") or "",
            "inst": it.get("cntrctInsttNm") or "", "dept": it.get("cntrctInsttChrgDeptNm") or "", "dmn": parse_instts(it.get("dminsttList")),
            "date": (it.get("cntrctCnclsDate") or it.get("cntrctDate") or "")[:10], "prd": it.get("cntrctPrd") or "",
            "tot": num(it.get("totCntrctAmt")), "amt": num(it.get("thtmCntrctAmt")), "mth": it.get("cntrctCnclsMthdNm") or "",
            "lng": it.get("lngtrmCtnuDivNm") or "", "cls": it.get("pubPrcrmntClsfcNm") or it.get("pubPrcrmntMidClsfcNm") or "",
            "corps": parse_corps(it.get("corpList")), "url": it.get("cntrctDtlInfoUrl") or it.get("cntrctInfoUrl") or "",
            "bgn": it.get("cbgnDate") or it.get("wbgnDate") or "", "end": it.get("ttalCcmpltDate") or it.get("ttalScmpltDate") or "", "chg": it.get("chgDt") or it.get("rgstDt") or ""}


def mask(v):   # probe 로그에서 사람 이름처럼 보이는 3글자를 가린다
    return re.sub(r"(?<![가-힣])[가-힣]{3}(?![가-힣])", "○○○", str(v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--govs", default=",".join(GOVS))
    ap.add_argument("--from", dest="frm", default="2021-01")
    ap.add_argument("--to", default=dt.date.today().strftime("%Y-%m"))
    ap.add_argument("--kinds", default="공사,용역,물품")
    ap.add_argument("--inqry-div", default=os.environ.get("G2B_INQRY_DIV", "1"))
    ap.add_argument("--instt-div", default=os.environ.get("G2B_INSTT_DIV", "1,2"), help="기관구분코드 — 쉼표로 여럿(계약기관·수요기관)")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--max-calls", type=int, default=900)
    a = ap.parse_args()
    key = os.environ.get("DATA_GO_KR_KEY", "")
    if not key:
        print("DATA_GO_KR_KEY 가 없습니다"); return 2
    os.makedirs(OUT, exist_ok=True)
    kinds = [k for k in a.kinds.split(",") if k in OPS]
    govs = [g for g in a.govs.split(",") if g in GOVS]
    calls = 0
    try:
        if a.probe:   # 조합마다 totalCount 와 첫 행 칸
            g = govs[0]; ym, b, e = list(months(a.frm, a.frm))[0]
            for kind in kinds:
                for idiv in ["1", "2", "3"]:
                    for cdiv in ["", "1", "2", "3"]:
                        p = {"pageNo": 1, "numOfRows": 3, "inqryDiv": idiv, "inqryBgnDate": b, "inqryEndDate": e, "insttNm": GOVS[g]}
                        if cdiv: p["insttDivCd"] = cdiv
                        r = call(OPS[kind], p, key); calls += 1; time.sleep(0.4)
                        print(f"[probe] {kind} inqryDiv={idiv} insttDivCd={cdiv or '-'} {GOVS[g]} {ym}: total={r and r['total']}", flush=True)
                        if r and r["items"]:
                            it = r["items"][0]
                            print("   칸:", ", ".join(sorted(it.keys())))
                            for f in ("cntrctInsttNm", "dminsttList", "corpList", "cntrctCnclsDate", "totCntrctAmt", "cnstwkNm", "cntrctNm"):
                                if f in it: print(f"   {f} = {mask(it[f])[:300]}")
                            print("   읽은 행:", json.dumps(row_of(kind, it), ensure_ascii=False)[:500])
            return 0
        st_path = f"{OUT}/state.json"
        state = json.load(open(st_path, encoding="utf-8")) if os.path.exists(st_path) else {"done": {}}
        for g in govs:
            path = f"{OUT}/{g}.json"
            old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
            rows = {r["no"] or f"{r['k']}|{r['nm']}|{r['date']}": r for r in (old or {}).get("rows", [])}
            done = set(state["done"].get(g, []))
            name = GOVS[g]
            try:
                for kind in kinds:
                    for ym, b, e in months(a.frm, a.to):
                        tag = f"{kind}|{ym}|{a.inqry_div}|{a.instt_div}"
                        if tag in done and ym < dt.date.today().strftime("%Y-%m"):
                            continue
                        got = 0
                        for cdiv in [c for c in a.instt_div.split(",") if c] or [""]:
                            page = 1
                            while True:
                                if calls >= a.max_calls:
                                    raise Stop(3, f"이번 실행 호출 상한 {a.max_calls} — 다음 실행이 이어 받습니다")
                                p = {"pageNo": page, "numOfRows": 100, "inqryDiv": a.inqry_div, "inqryBgnDate": b, "inqryEndDate": e, "insttNm": name}
                                if cdiv: p["insttDivCd"] = cdiv
                                r = call(OPS[kind], p, key); calls += 1; time.sleep(0.3)
                                if not r: break
                                for it in r["items"]:
                                    row = row_of(kind, it)
                                    # 기관명 검색은 부분 일치('대구광역시'가 구·군·소속기관까지 잡음) — 계약기관 또는 수요기관 이름이 그 지자체와 같은 행만
                                    if name not in [row["inst"], *row["dmn"]] and not (g == "daegu" and any(x.startswith("대구광역시") and not re.search(r"(중|동|서|남|북|수성|달서)구|달성군|군위군", x) for x in [row["inst"], *row["dmn"]])):
                                        continue
                                    k = row["no"] or f"{row['k']}|{row['nm']}|{row['date']}"
                                    if k not in rows or (row["chg"] or "") >= (rows[k].get("chg") or ""):
                                        rows[k] = row; got += 1
                                if page * 100 >= r["total"]: break
                                page += 1
                        done.add(tag)
                        print(f"  {name} {kind} {ym}: {got}건 (누적 {len(rows)}, 호출 {calls})", flush=True)
            finally:
                state["done"][g] = sorted(done)
                out = {"v": 1, "key": g, "name": name, "fetched": dt.date.today().isoformat(), "from": a.frm, "to": a.to,
                       "source": "조달청 나라장터 계약정보서비스(공공데이터포털 15129427) — 나라장터 검색조건에 의한 계약현황 공사·용역·물품",
                       "note": "나라장터를 거친 계약만(카드 결제·공공요금·나라장터 밖 소액 계약은 없음). 계약금액은 지출액과 다르다(선금·기성·여러 해). 담당자·대표자 이름은 저장하지 않음.",
                       "rows": sorted(rows.values(), key=lambda r: (r["date"], r["no"]))}
                if out["rows"] or old:
                    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
                json.dump(state, open(st_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
                print(f"[contracts] {name}: {len(rows)}건 → {path}", flush=True)
    except Stop as s:
        print(f"[contracts] 멈춤: {s}", flush=True)
        return s.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
