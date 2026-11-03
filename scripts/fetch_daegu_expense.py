#!/usr/bin/env python3
"""대구광역시 주민참여 재정 포털(jumin.daegu.go.kr) '세출현황 — 지출건별' 공개 자료 → 지자체 부가세 절감 점검기 '공개 지출 자료로 후보 찾기'
(운영자 2026-11-03 '홈택스 붙여넣는 것은 공무원이 안 할 것 같은데 방법을 찾아봐').

포털은 본청·9개 구군의 지출을 지급일자 하루 단위로만 보여 주고(회계연도·회계구분·부서명·경비구분명·세부사업명·통계목·사업개요(적요)·지출액·지급일자,
거래처·사업자번호·세액 칸은 없음) 하루치 엑셀(xls, 2023-06-12 달성군 815행)을 내려 준다. 2026-11-03 확인: 회계연도 목록은 2015~2024 이지만 건별 자료는
2023년까지만 있고 2024년 뒤는 비어 있다(차세대 e호조 전환 뒤 연계가 끊긴 것으로 보임). 경정청구 기한(법정신고기한 뒤 5년) 안 과세기간 가운데 2021년 2기~2023년 2기를 덮는다.

원본 행은 저장하지 않고(사람 이름이 적요에 들어 있을 수 있음 — '○○○ 외 2명 수당 지급' 같은 줄) (과세기간 × 회계구분 × 부서 × 세부사업 × 통계목)로 묶어
건수·지출액 합·카드결제 건수('카드' 낱말)·적요 본보기 3개(사람 이름으로 보이는 2~4자 한글 뒤에 '외'·'등'·'님'·'씨'가 붙거나 쉼표로 이어진 이름 묶음은 '(이름)'으로)만
data/vat/expense/<key>.json 에 남긴다. 값 그대로·평가 없음. 세액은 저장하지 않는다(화면이 통계목 성격에 따라 지출액 × 10/110 을 '추정'으로 보이고 그렇게 적는다).

사용: python3 scripts/fetch_daegu_expense.py [--gov dalseong,daegu] [--years 2021,2022,2023] [--days 2023-06-12,2023-06-13] [--probe]
  --probe   지자체마다 연도 목록과 한 날짜의 행 수만 로그(저장 안 함)
  --merge   받은 날짜를 기존 JSON 에 더한다(기본: 지정 연도는 새로 집계). 요청 사이 1.2초, 실패는 3회 재시도 뒤 건너뛰고 index 에 적는다.
"""
from __future__ import annotations
import argparse, datetime as dt, io, json, re, subprocess, sys, time
from collections import defaultdict
from pathlib import Path

BASE = "https://jumin.daegu.go.kr/budget/texoperate"
UA = "Mozilla/5.0 (compatible; daitda-vat/1.0; +https://vat-daitda.pages.dev/vat/)"
GOVS = [("daegu", "01", "대구광역시"), ("jung", "02", "중구"), ("dong", "03", "동구"), ("seo", "04", "서구"), ("nam", "05", "남구"), ("buk", "06", "북구"), ("suseong", "07", "수성구"), ("dalseo", "08", "달서구"), ("dalseong", "09", "달성군"), ("gunwi", "10", "군위군")]
OUT = Path("data/vat/expense"); OUT.mkdir(parents=True, exist_ok=True)
JAR = Path("/tmp/daegu_expense_cookies.txt")
NAME_RE = re.compile(r"(?:(?<![가-힣])[가-힣]{3}\s*,\s*){2,}[가-힣]{3}(?![가-힣])|(?<![가-힣])[가-힣]{3}(?=\s*(?:외\s*\d|님(?![가-힣])|씨(?![가-힣])))")   # 적요 속 사람 이름 묶음 — 3자 이름이 쉼표로 셋 이상 이어지거나 '외 N'·'님'·'씨'가 붙은 것만(토목,건축 같은 두 낱말은 남김)


def curl(url: str, post: dict | None = None, referer: str = "", timeout: int = 120) -> bytes:
    cmd = ["curl", "-sS", "-m", str(timeout), "-L", "-A", UA, "-c", str(JAR), "-b", str(JAR), "-H", "Accept-Language: ko-KR,ko;q=0.9"]
    if referer:
        cmd += ["-e", referer]
    if post is not None:
        cmd += ["-X", "POST"]
        for k, v in post.items():
            cmd += ["--data-urlencode", f"{k}={v}"]
    cmd.append(url)
    for i in range(2):   # 연결이 끊기면 한 번만 더(러너 6시간 안에 3년치를 끝내려면 실패한 날을 오래 붙들지 않는다 — 실패한 날은 failed_days 에 남아 다음 실행이 다시 받는다)
        r = subprocess.run(cmd, capture_output=True, timeout=timeout + 30)
        if r.returncode == 0 and r.stdout:
            return r.stdout
        print(f"  [{i + 1}] curl {r.returncode} {url[-40:]} {r.stderr.decode('utf-8', 'ignore')[:100].strip()}", flush=True)
        time.sleep(4 * (i + 1))
    return b""


def years_of(code: str) -> list[str]:
    raw = curl(f"{BASE}/selectFisYearJiList.do?localGovCd={code}", referer=f"{BASE}/texoperateExpenditureAll.do?localGovCd={code}")
    try:
        return [str(x.get("fisYear")) for x in json.loads(raw.decode("utf-8", "ignore")) if x.get("fisYear")]
    except Exception:
        return []


def day_rows(code: str, year: str, ymd: str) -> list[list[str]] | None:
    """하루치 엑셀(xls) → 행 목록(머리글 제외). 실패면 None, 자료 없음이면 []"""
    data = curl(f"{BASE}/expenditureAllExcel.do", post={"pgMv": "", "localGovCd": code, "fisYear": year, "fisFgCd": "All", "deptCd": "All", "dbizCd": "All", "payCmdYmd": ymd, "pageIndex": "1"}, referer=f"{BASE}/texoperateExpenditureAll.do?localGovCd={code}", timeout=90)
    if not data:
        return None
    if data[:4] != b"\xd0\xcf\x11\xe0":   # OLE2 가 아니면 오류 화면
        return None if b"<html" in data[:400].lower() and b"\xec\x97\x86" not in data else []
    try:
        import xlrd
        wb = xlrd.open_workbook(file_contents=data)
        sh = wb.sheet_by_index(0)
    except Exception as e:
        print(f"  xls 못 읽음 {ymd}: {e}")
        return None
    if sh.nrows < 2:
        return []
    head = [str(sh.cell_value(0, c)).strip() for c in range(sh.ncols)]
    if "세부사업명" not in head or "지출액" not in head:
        print(f"  머리글 다름 {ymd}: {head}")
        return None
    rows = []
    for r in range(1, sh.nrows):
        rows.append([str(sh.cell_value(r, c)).strip() for c in range(sh.ncols)])
    return rows


def period_of(ymd: str) -> str:
    y, m = ymd[:4], int(ymd[5:7])
    return f"{y}-{1 if m <= 6 else 2}"


def mask(s: str) -> str:
    return NAME_RE.sub("(이름)", s)


def aggregate(rows: list[list[str]], head: list[str], agg: dict, days_seen: set[str]):
    ix = {h: i for i, h in enumerate(head)}
    for r in rows:
        g = lambda k: r[ix[k]] if k in ix and ix[k] < len(r) else ""
        ymd = g("지급일자")[:10]
        if not re.match(r"\d{4}-\d{2}-\d{2}", ymd):
            continue
        days_seen.add(ymd)
        amt = re.sub(r"[^\d\-]", "", g("지출액"))
        amt = int(amt) if amt not in ("", "-") else 0
        key = (period_of(ymd), g("회계구분"), g("부서명"), g("세부사업명"), g("통계목"))
        a = agg[key]
        a["n"] += 1; a["amt"] += amt
        memo = g("사업개요(적요)")
        if "카드" in memo:
            a["card"] += 1
        if g("경비구분명") == "일상경비":
            a["petty"] += 1
        if amt > 0 and len(a["memo"]) < 3:
            m = mask(memo)[:60]
            if m and m not in a["memo"]:
                a["memo"].append(m)
        if amt > a["max"]:
            a["max"] = amt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gov", default="")
    ap.add_argument("--years", default="2021,2022,2023")
    ap.add_argument("--days", default="")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--merge", action="store_true", help="(기본) 있는 JSON 에 이어 받는다 — 받은 날은 건너뛰고 실패한 날은 다시")
    ap.add_argument("--fresh", action="store_true", help="있는 JSON 을 버리고 처음부터")
    ap.add_argument("--sleep", type=float, default=1.2)
    a = ap.parse_args()
    govs = [g for g in GOVS if not a.gov or g[0] in a.gov.split(",")]
    for key, code, name in govs:
        yrs = years_of(code)
        print(f"[expense] {name}({code}) 연도 목록: {yrs}", flush=True)
        if a.probe:
            d = "2023-06-12"
            rows = day_rows(code, "2023", d)
            print(f"  probe {d}: {'실패' if rows is None else f'{len(rows)}행'}", flush=True)
            if rows:
                print("  ", rows[0])
            continue
        path = OUT / f"{key}.json"
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() and not a.fresh else None   # 기본 이어 받기(러너가 시간 초과로 끊겨도 중간 저장분부터)
        agg: dict = defaultdict(lambda: {"n": 0, "amt": 0, "card": 0, "petty": 0, "max": 0, "memo": []})
        days_seen: set[str] = set(); failed: list[str] = []; empty = 0
        if old:
            for r in old.get("rows", []):
                k = (r["p"], r["acct"], r["dept"], r["biz"], r["mok"])
                agg[k].update({"n": r["n"], "amt": r["amt"], "card": r["card"], "petty": r["petty"], "max": r["max"], "memo": r["memo"]})
            days_seen.update(old.get("days", []))
        head = ["회계연도", "회계구분", "부서명", "경비구분명", "세부사업명", "통계목", "사업개요(적요)", "지출액", "지급일자"]
        if a.days:
            days = a.days.split(",")
        else:
            days = []
            for y in a.years.split(","):
                d0 = dt.date(int(y), 1, 1)
                while d0.year == int(y):
                    days.append(d0.isoformat()); d0 += dt.timedelta(days=1)
        days = [d for d in days if d not in days_seen]
        t0 = time.time()
        def save_partial():   # 60일마다 중간 저장 — 러너가 시간 초과로 죽어도 받은 만큼은 남는다(다음 실행이 이어 받음)
            rows_p = [{"p": k[0], "acct": k[1], "dept": k[2], "biz": k[3], "mok": k[4], **v} for k, v in sorted(agg.items())]
            path.write_text(json.dumps({"v": 1, "key": key, "code": code, "name": name, "source": "대구광역시 주민참여 재정 포털 세출현황 지출건별(부분 저장)", "fetched": dt.date.today().isoformat(), "years": sorted({d[:4] for d in days_seen}), "periods": sorted({r["p"] for r in rows_p}), "days": sorted(days_seen), "failed_days": sorted(set(failed)), "note": "부분 저장(수집 중)", "rows": rows_p}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        for i, d in enumerate(days):
            rows = day_rows(code, d[:4], d)
            if rows is None:
                failed.append(d)
            elif not rows:
                empty += 1; days_seen.add(d)
            else:
                aggregate(rows, head, agg, days_seen)
            if i % 30 == 29:
                print(f"  {name} {d} … {i + 1}/{len(days)} 묶음 {len(agg)} 실패 {len(failed)} ({int(time.time() - t0)}s)", flush=True)
            if i % 60 == 59:
                save_partial()
            time.sleep(a.sleep)
        def write_out():
            rows_out = [{"p": k[0], "acct": k[1], "dept": k[2], "biz": k[3], "mok": k[4], **v} for k, v in sorted(agg.items())]
            periods = sorted({r["p"] for r in rows_out})
            out = {"v": 1, "key": key, "code": code, "name": name, "source": "대구광역시 주민참여 재정 포털 세출현황 지출건별(jumin.daegu.go.kr/budget/texoperate/texoperateExpenditureAll.do), 지급일자 하루 단위 엑셀",
                   "fetched": dt.date.today().isoformat(), "years": sorted({d[:4] for d in days_seen}), "periods": periods, "days": sorted(days_seen), "failed_days": sorted(set(failed + ([d for d in old.get("failed_days", []) if d not in days_seen] if old else []))),
                   "note": "거래처·사업자번호·세액 칸이 없는 공개 자료 — 세액은 통계목 성격에 따른 추정(지출액 × 10/110)일 뿐이며, 실제 공제는 세금계산서 원본으로 확인한다. 2024년 이후 건별 자료는 포털에 없음(2026-11-03)",
                   "rows": rows_out}
            path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            return rows_out
        rows_out = write_out()
        print(f"[expense] {name}: 묶음 {len(rows_out)} · 날짜 {len(days_seen)}(빈 날 {empty}) · 실패 {len(failed)} → {path} {path.stat().st_size // 1024}KB", flush=True)
    idx = {p.stem: {"name": json.loads(p.read_text(encoding='utf-8'))["name"], "fetched": json.loads(p.read_text(encoding='utf-8'))["fetched"], "periods": json.loads(p.read_text(encoding='utf-8'))["periods"], "rows": len(json.loads(p.read_text(encoding='utf-8'))["rows"])} for p in sorted(OUT.glob("*.json")) if p.stem != "index"}
    (OUT / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
