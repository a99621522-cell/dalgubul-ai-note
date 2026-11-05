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
    """업체목록 '[순번^구분^공동수급방식^상호^대표자^국적^지분율^상호^…^사업자등록번호],[…]' (2026-11-05 probe 로 확인).
    대표자 이름(5번째 칸)은 읽지 않는다 — 상호·사업자등록번호·지분율만. 칸 수가 다르면 모양으로 고른다."""
    out = []
    for grp in re.findall(r"\[([^\]]*)\]", s or ""):
        parts = [p.strip() for p in grp.split("^")]
        no = next((p.replace("-", "") for p in reversed(parts) if BIZNO.match(p)), "")
        if len(parts) >= 7:
            name = parts[3] or (parts[7] if len(parts) > 7 else "")
            sh = parts[6] if re.fullmatch(r"\d{1,3}(\.\d+)?", parts[6] or "") else ""
        else:
            name = next((p for p in parts if re.search(r"주식회사|\(주\)|㈜|\(유\)|유한|협동조합|재단|사단", p)), "")
            sh = ""
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


GU = {"중구": "jung", "동구": "dong", "서구": "seo", "남구": "nam", "북구": "buk", "수성구": "suseong", "달서구": "dalseo", "달성군": "dalseong", "군위군": "gunwi"}
def gov_of(name):
    """기관 이름 → 지자체 키. '대구광역시 달성군 …' → dalseong, '대구광역시 …'(본청·사업소·소방·의회) → daegu, 교육청·그 밖 → None.
    군위군은 2023-07 편입 전 '경상북도 군위군' 계약은 '대구광역시' 검색에 잡히지 않는다."""
    n = (name or "").replace(" ", "")
    if not n.startswith("대구광역시") or re.search(r"교육청|교육지원청", n):   # 대구광역시교육청·동부·서부·남부·달성교육청 소속 학교
        return None
    m = re.match(r"대구광역시(중구|동구|서구|남구|북구|수성구|달서구|달성군|군위군)", n)
    return GU[m.group(1)] if m else "daegu"


def claim_from(today=None):
    """경정청구(국세기본법 제45조의2 — 법정신고기한 뒤 5년)가 아직 되는 가장 이른 과세기간의 첫 달.
    제1기(1~6월) 확정신고기한 7월 25일, 제2기(7~12월) 다음 해 1월 25일."""
    t = today or dt.date.today()
    for y in range(t.year - 6, t.year + 1):
        for half, deadline in ((1, dt.date(y, 7, 25)), (2, dt.date(y + 1, 1, 25))):
            if deadline.replace(year=deadline.year + 5) >= t:
                return f"{y}-{'01' if half == 1 else '07'}"
    return t.strftime("%Y-%m")


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
            "corps": parse_corps(it.get("corpList")), "url": short_url(it.get("cntrctDtlInfoUrl") or it.get("cntrctInfoUrl") or ""),
            "chg": it.get("chgDt") or it.get("rgstDt") or ""}


URL_HEAD, URL_TAIL = "https://www.g2b.go.kr/link/FIUA027_01/single/?", "&srchName=ctrtCrst&openUrl=Y"
def short_url(u):
    """나라장터 계약 상세 주소는 앞뒤가 늘 같다 — 가운데 인자만 둔다(화면이 앞뒤를 붙임). 꼴이 다르면 그대로."""
    return u[len(URL_HEAD):-len(URL_TAIL)] if u.startswith(URL_HEAD) and u.endswith(URL_TAIL) else u


def ctrt_id(r):
    """나라장터 원계약번호·변경 차수 — 상세 주소의 ctrtNo·ctrtChgOrd(변경계약마다 통합계약번호가 새로 붙어 같은 계약이 여러 줄이 된다)"""
    u = r.get("url") or ""
    m, o = re.search(r"ctrtNo=([^&]+)", u), re.search(r"ctrtChgOrd=([^&]+)", u)
    return (m.group(1) if m else ""), (o.group(1) if o else "")


def latest_by_contract(rows):
    """같은 원계약번호는 마지막 변경 한 줄만(금액·업체는 마지막 변경, 계약일은 처음 계약일) — 2026-11-05 달성군 25,319줄 → 12,176건.
    장기계속·계속비의 차수 계약은 원계약번호가 따로라 그대로 남고, 총계약금액이 차수마다 되풀이되므로 화면은 금차 계약금액(amt)을 쓴다."""
    best, first = {}, {}
    for r in rows:
        cid, ord_ = ctrt_id(r); k = cid or r["no"] or f"{r['k']}|{r['nm']}|{r['date']}"
        cur = best.get(k)
        if cur is None or (ord_, r.get("chg") or "") > (ctrt_id(cur)[1], cur.get("chg") or ""): best[k] = r
        if r["date"] and (k not in first or r["date"] < first[k]): first[k] = r["date"]
    return [{**r, "date": first.get(k, r["date"])} for k, r in best.items()]


def mask(v):   # probe 로그에서 사람 이름처럼 보이는 3글자를 가린다
    return re.sub(r"(?<![가-힣])[가-힣]{3}(?![가-힣])", "○○○", str(v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--govs", default=",".join(GOVS))
    ap.add_argument("--from", dest="frm", default="", help="비우면 경정청구가 아직 되는 가장 이른 과세기간부터")
    ap.add_argument("--to", default=dt.date.today().strftime("%Y-%m"))
    ap.add_argument("--kinds", default="공사,용역,물품")
    ap.add_argument("--inqry-div", default=os.environ.get("G2B_INQRY_DIV", "1"))
    ap.add_argument("--instt-div", default=os.environ.get("G2B_INSTT_DIV", "1,2"), help="기관구분코드 — 쉼표로 여럿(계약기관·수요기관)")
    ap.add_argument("--one", default="", help="지자체 하나만(그 이름으로 묻고 그 지자체 행만) — 운영자 2026-11-05 '한 지자체 다하고 다음 지자체'. daegu 는 '대구광역시'로 묻는다")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--max-calls", type=int, default=3000)
    ap.add_argument("--rows", type=int, default=999, help="한 쪽 행 수(주지 않으면 100 으로)")
    a = ap.parse_args()
    # 계약일이 청구 기간보다 앞서도 기성·준공 세금계산서는 청구 기간 안에 나올 수 있어 계약일로 1년 앞까지 둔다
    y, m = map(int, claim_from().split("-")); keep_from = f"{y - 1}-{m:02d}"
    a.frm = a.frm or keep_from
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
        # 한 번 훑기: 기관명 '대구광역시'(부분 일치 — 본청·사업소·구·군·교육청까지 잡힘)로 받아 계약기관·수요기관 이름으로 지자체를 가른다.
        # 지자체마다 따로 물으면 같은 행을 열 번 받게 된다(2026-11-05 probe: 2026-09 공사 1,292건 대부분 교육청·학교).
        one0 = a.one if a.one in GOVS else ""
        st_path = f"{OUT}/state_{one0}.json" if one0 else f"{OUT}/state.json"   # 지자체마다 따로 — 여러 지자체를 동시에 받아도 서로 덮지 않게
        state = json.load(open(st_path, encoding="utf-8")) if os.path.exists(st_path) else {}
        done = set(state.get("sweep", []))
        if one0 and os.path.exists(f"{OUT}/state.json"): done |= {t for t in json.load(open(f"{OUT}/state.json", encoding="utf-8")).get("sweep", []) if not t.startswith(tuple(f"{g}|" for g in GOVS))}   # 예전 한꺼번에 받은 달
        store, olds = {}, {}
        for g in GOVS:
            path = f"{OUT}/{g}.json"
            olds[g] = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
            store[g] = {r["no"] or f"{r['k']}|{r['nm']}|{r['date']}": {**{k: v for k, v in r.items() if k not in ("bgn", "end")}, "url": short_url(r.get("url", ""))}
                        for r in (olds[g] or {}).get("rows", []) if g in {gov_of(x) for x in [r["inst"], *r["dmn"]]}}   # 가르기 규칙이 바뀌면 옛 행도 다시 가른다
        one = a.one if a.one in GOVS else ""
        want = {one} if one else set(govs)
        qname = GOVS[one] if one else "대구광역시"   # 구·군 이름으로 물으면 그 구·군(과 소속 기관) 계약만 온다
        size = a.rows
        this_month = dt.date.today().strftime("%Y-%m")
        fails_in_row = 0   # 연결 실패로 못 받은 달은 끝난 것으로 적지 않는다(2026-11-05 — 시간 초과가 이어진 달을 '0행·끝'으로 적어 다시 받지 않던 것)
        try:
            for kind in kinds:
                for ym, b, e in months(a.frm, a.to):
                    tag = f"{kind}|{ym}|{a.inqry_div}|{a.instt_div}"; tag1 = f"{one}|{tag}" if one else tag
                    if (tag in done or tag1 in done) and ym < this_month:
                        continue
                    got, seen = {g: 0 for g in GOVS}, 0; failed = False
                    for cdiv in [c for c in a.instt_div.split(",") if c] or [""]:
                        page, recv = 1, 0
                        while True:
                            if calls >= a.max_calls:
                                raise Stop(3, f"이번 실행 호출 상한 {a.max_calls} — 다음 실행이 이어 받습니다")
                            p = {"pageNo": page, "numOfRows": size, "inqryDiv": a.inqry_div, "inqryBgnDate": b, "inqryEndDate": e, "insttNm": qname}
                            if cdiv: p["insttDivCd"] = cdiv
                            r = call(OPS[kind], p, key); calls += 1; time.sleep(0.3)
                            if not r: failed = True; break
                            if page == 1 and size > 100 and r["total"] > len(r["items"]) and len(r["items"]) < size:
                                print(f"  한 쪽 {size}행을 주지 않음({len(r['items'])}행) — 100행으로 다시", flush=True)
                                size = 100; continue
                            recv += len(r["items"]); seen += len(r["items"])
                            for it in r["items"]:
                                row = row_of(kind, it)
                                k = row["no"] or f"{row['k']}|{row['nm']}|{row['date']}"
                                for g in ({gov_of(x) for x in [row["inst"], *row["dmn"]]} - {None}) & (want if one else set(GOVS)):
                                    if k not in store[g] or (row["chg"] or "") >= (store[g][k].get("chg") or ""):
                                        store[g][k] = row; got[g] += 1
                            if not r["items"] or recv >= r["total"]: break
                            page += 1
                    if failed:
                        fails_in_row += 1
                        print(f"  {one or '전체'} {kind} {ym}: 받지 못함 — 끝난 달로 적지 않음(다음 실행이 다시)", flush=True)
                        if fails_in_row >= 4: raise Stop(4, '조달청 API 가 잇달아 응답하지 않습니다 — 받은 데까지 저장하고 멈춥니다')
                        continue
                    fails_in_row = 0
                    done.add(tag1)
                    print(f"  {one or '전체'} {kind} {ym}: 받은 {seen}행 → " + " ".join(f"{g} {n}" for g, n in got.items() if n) + f" (호출 {calls})", flush=True)
        finally:
            state["sweep"] = sorted(done)
            state.pop("done", None)
            for g in want:
                path = f"{OUT}/{g}.json"
                out = {"v": 1, "key": g, "name": GOVS[g], "fetched": dt.date.today().isoformat(), "from": keep_from, "to": a.to,
                       "source": "조달청 나라장터 계약정보서비스(공공데이터포털 15129427) — 나라장터 검색조건에 의한 계약현황 공사·용역·물품",
                       "note": "나라장터를 거친 계약만(카드 결제·공공요금·나라장터 밖 소액 계약은 없음). 계약금액은 지출액과 다르다(선금·기성·여러 해). 담당자·대표자 이름은 저장하지 않음."
                               + (" 2023-07 편입 전 경상북도 군위군 계약은 없음." if g == "gunwi" else ""),
                       "rows": sorted((r for r in latest_by_contract(store[g].values()) if (r["date"] or "9")[:7] >= keep_from), key=lambda r: (r["date"], r["no"]))}
                if out["rows"] or olds[g]:
                    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
                print(f"[contracts] {GOVS[g]}: {len(store[g])}건 → {path}", flush=True)
            json.dump(state, open(st_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    except Stop as s:
        print(f"[contracts] 멈춤: {s}", flush=True)
        return s.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
