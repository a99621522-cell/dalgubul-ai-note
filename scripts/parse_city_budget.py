#!/usr/bin/env python3
"""대구시 본예산 세출 '사업설명서'(부서별 PDF, 홈페이지 공개용) → scripts/data/city_programs.csv (표준 라이브러리만).

입력: pdftotext -layout 로 뽑은 텍스트(쪽 구분 \f 또는 drive_ocr.py 의 '=== 쪽 N ===')나 PDF(pdftotext 가 있으면 직접).
세부사업 쪽은 첫 줄이 '사업명(계속|신규|…)' 이고 '세부사업 예산총괄' 표가 있다. 다음 세부사업 쪽 전까지가 한 사업이다.
뽑는 것: 실국·과·팀, 기능, 정책사업·단위사업, 2025 당초/최종·2026 당초·증감, 재원별(시비·국비·균특·기금 등) 2026 금액,
사업기간·근거·목적·내용(앞부분), 기업 수혜 여부(글에 기업·소상공인·창업 낱말), 쪽 번호. 담당자 성명·전화는 뽑지 않는다.
금액 단위는 자료 그대로 천원. 평가 없음 — 자료 값만 옮긴다.

사용: python3 scripts/parse_city_budget.py <txt|pdf ...> [--year 2026] [--out scripts/data/city_programs.csv] [--append]
"""
import argparse, csv, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "data" / "city_programs.csv"
COLS = ["year", "org", "dept", "team", "function", "policy_program", "unit_program", "name", "status",
        "budget_2025", "budget_2025_final", "budget_2026", "change", "change_pct",
        "fund_city", "fund_national", "fund_balanced", "fund_other", "period", "basis", "purpose", "content",
        "corp", "admin", "page", "source"]
TITLE = re.compile(r"^\s*(\S[^\n]*?)\s*\((계속|신규|종료|변경|일몰|폐지|재편)\)\s*$")
NUM = r"(-?△?[\d,]+(?:\.\d+)?)"
ADMIN = re.compile(r"기본경비|인력운영비|예수금|원리금상환|청사관리|공무원|인건비|운영비$")
CORP = re.compile(r"기업|소상공인|창업|스타트업|벤처|소공인|업체|사업자|공장|산업단지|입주")


def load_pages(path: Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        t = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout
        return t.split("\f")
    t = path.read_text(encoding="utf-8", errors="replace")
    if "=== 쪽 " in t:
        return [p for p in re.split(r"=== 쪽 \d+ ===\n?", t)][1:]
    return t.split("\f")


def n2i(s: str):
    s = (s or "").replace(",", "").replace("△", "-").strip()
    try:
        return int(float(s))
    except ValueError:
        return ""


def clean(lines: list[str]) -> str:
    """줄을 잇고 pdftotext 가 흩뿌린 한 글자 조각(' , ', ' 2 ')은 뺀다."""
    out = []
    for l in lines:
        s = re.sub(r"\s+", " ", l).strip()
        if not s or re.fullmatch(r"[\d,.:()·\-*\s]+", s) or re.fullmatch(r"-\s*\d+\s*-", s) or (len(s) <= 2 and not re.search(r"[가-힣A-Za-z]{2}", s)):
            continue
        out.append(s)
    return " ".join(out)


def section(text: str, start: str, ends: list[str]) -> list[str]:
    m = re.search(start, text)
    if not m:
        return []
    rest = text[m.end():]
    cut = len(rest)
    for e in ends:
        k = re.search(e, rest)
        if k:
            cut = min(cut, k.start())
    return rest[:cut].split("\n")


def parse_block(pages: list[tuple[int, str]], year: int, source: str) -> dict:
    pno, first = pages[0]
    text = "\n".join(p for _, p in pages)
    m = TITLE.match(next(l for l in first.split("\n") if l.strip()))
    name, status = m.group(1).strip(), m.group(2)
    name = re.sub(r"\s{2,}", " ", name)
    org = re.search(r"조\s*직\s*:?\s*([^\n:]+?)(?=\s{2,}담\s*당|\s{3,}|\n)", text)
    orgs = re.sub(r"\s+", " ", org.group(1)).strip() if org else ""
    # '원스톱기업투자센터 투자유치과 투자기획팀' → 실국 / 과 / 팀. 붙어 있으면(예: '미래혁신성장실산업정책과…') 과·팀 낱말로 자른다
    parts = orgs.split(" ")
    # 실국과 과가 붙어 나오면('원스톱기업투자센터투자유치과') 실·국·단·본부·센터·청 뒤에서 자른다
    split_parts = []
    for p in parts:
        mm = re.match(r"^(.+?(?:실|국|단|본부|센터|청))(\S+?(?:과|관))$", p)
        split_parts += [mm.group(1), mm.group(2)] if mm else [p]
    parts = split_parts
    dept = next((p for p in parts if re.search(r"과$|관$", p)), "")
    team = next((p for p in parts if re.search(r"팀$", p)), "")
    top = parts[0] if parts else ""
    func = re.search(r"기\s*능\s*:?\s*([^\n:]+?)(?:\s{3,}|\n)", text)
    pol = re.search(r"정책사업\s*:?\s*([^\n:]+?)\s*(?=단위사업|\s{3,}|\n)", text)
    unit = re.search(r"단위사업\s*:\s*([^\n:]+?)(?:\s{3,}|\n)", text)
    if not unit or not unit.group(1).strip():   # '단위사업' 뒤에 값이 없고 다음 줄에 ':   지역대학 육성 지원' 로 오는 서식
        after = text[text.find("단위사업"):].split("\n")[1:4] if "단위사업" in text else []
        for l in after:
            mm = re.search(r":\s*([가-힣A-Za-z][^\n:]*?)\s*$", l)
            if mm:
                unit = mm; break
    # 예산총괄: '세부사업 예산총괄' 뒤 첫 숫자 5개 줄
    b = ["", "", "", "", ""]
    k = text.find("예산총괄")
    if k >= 0:
        mm = re.search(rf"^\s*{NUM}\s+{NUM}\s+{NUM}\s+{NUM}\s+{NUM}%?\s*$", text[k:], re.M)
        if mm:
            b = [mm.group(i) for i in range(1, 6)]
    # 재원별 내역: '시비 350,252 350,252 286,871 …' → 2026 열(세 번째 숫자)
    funds = {"city": "", "national": "", "balanced": "", "other": ""}
    for l in section(text, r"□\s*재원별\s*내역", [r"□"]):
        mm = re.match(rf"^\s*([가-힣·()\s]+?)\s+{NUM}\s+{NUM}\s+{NUM}", l)
        if not mm:
            continue
        lab = re.sub(r"\s", "", mm.group(1))
        v = n2i(mm.group(4))
        if lab == "계":
            continue
        if "시비" in lab or "지방비" in lab:
            funds["city"] = v
        elif "균특" in lab or "균형" in lab:
            funds["balanced"] = v
        elif "국비" in lab or "국고" in lab:
            funds["national"] = v
        else:
            funds["other"] = (funds["other"] or 0) + (v or 0)
    period = re.search(r"사업기간\s*:?\s*([^\n]+)", text)
    basis = clean(section(text, r"□\s*사업근거", [r"□"]))
    purpose = clean(section(text, r"□\s*사업목적", [r"□"]))
    content = clean(section(text, r"○\s*사업내용", [r"□"]))
    if not content:   # '사업내용' 소제목이 없는 서식이면 사업개요 전체(기간·사업비 줄은 뺀다)
        content = clean([l for l in section(text, r"□\s*사업개요", [r"□"]) if not re.search(r"사업기간|사\s*업\s*비", l)])
    hay = f"{name} {purpose} {content}"
    return {"year": year, "org": top, "dept": dept, "team": team,
            "function": re.sub(r"\s+", " ", func.group(1)).strip() if func else "",
            "policy_program": re.sub(r"\s+", " ", pol.group(1)).strip() if pol else "", "unit_program": re.sub(r"\s+", " ", unit.group(1)).strip() if unit else "",
            "name": name, "status": status,
            "budget_2025": n2i(b[0]), "budget_2025_final": n2i(b[1]), "budget_2026": n2i(b[2]), "change": n2i(b[3]),
            "change_pct": b[4].replace("△", "-") if b[4] else "",
            "fund_city": funds["city"], "fund_national": funds["national"], "fund_balanced": funds["balanced"], "fund_other": funds["other"],
            "period": re.sub(r"\s+", " ", period.group(1)).strip()[:40] if period else "",
            "basis": basis[:300], "purpose": purpose[:300], "content": content[:400],
            "corp": "Y" if CORP.search(hay) else "", "admin": "Y" if ADMIN.search(name) else "",
            "page": pno, "source": source}


ROW = re.compile(r"^(\s*)(\S.*?)\s{2,}" + NUM + r"\s+" + NUM + r"\s+" + NUM + r"\s*$")


def parse_itemized(pages: list[str], year: int, source: str) -> list[dict]:
    """세출예산 사업명세서: 쪽 머리의 실국·부서·정책·단위 아래 '세부사업  예산액  전년도  증감' 행. 편성목(3자리)·통계목(2자리) 행은
    그 사업의 산출 항목('○…')과 함께 content 로 모은다. 목적·근거·재원별은 이 서식에 없다."""
    rows, cur = [], None
    org = dept = policy = unit = ""
    for pno, p in enumerate(pages, 1):
        mh = re.search(r"실국\s*:\s*(\S+)\s+부서\s*:\s*(\S+)", p)
        if mh:
            org, dept = mh.group(1), mh.group(2)
        mp = re.search(r"정책\s*:\s*([^\n]+?)\s*$", p, re.M)
        mu = re.search(r"단위\s*:\s*([^\n]+?)(?:\s{2,}\(단위|\s*$)", p, re.M)
        if mp:
            policy = mp.group(1).strip()
        if mu:
            unit = mu.group(1).strip()
        lines = p.split("\n")
        for i, l in enumerate(lines):
            m = ROW.match(l)
            if not m:
                if cur and re.match(r"^\s*○", l):   # 산출 항목
                    cur["_items"].append(re.sub(r"\s*[\d,]+원\b.*$", "", re.sub(r"\s+", " ", l.split("○", 1)[1])).strip())
                elif cur and cur["_wrap"] and l.strip() and not re.search(r"[\d,]{3,}", l) and len(l) - len(l.lstrip()) >= 3:
                    cur["name"] += l.strip(); cur["_wrap"] = False   # 긴 사업명이 다음 줄로 넘어간 것
                continue
            name = re.sub(r"\s+", " ", m.group(2)).strip()
            b26, b25, diff = m.group(3), m.group(4), m.group(5)
            indent = len(m.group(1))
            if cur:
                cur["_wrap"] = False
            if re.match(r"^\d{2,3}\s", name) or re.match(r"^(국|균|기|시|채|도)\s", name) or name in (org, dept):
                continue
            # 들여쓰기 1 = 정책사업, 2 = 단위사업(쪽 중간에 바뀌는 것도 따라간다), 3 이상 = 세부사업
            if indent <= 1 or name == policy:
                policy = name; continue
            if indent == 2 or name == unit:
                unit = name; continue
            cur = {"year": year, "org": org, "dept": dept, "team": "", "function": "", "policy_program": policy, "unit_program": unit,
                   "name": name, "status": "", "budget_2025": n2i(b25), "budget_2025_final": "", "budget_2026": n2i(b26), "change": n2i(diff),
                   "change_pct": round((n2i(b26) - n2i(b25)) / n2i(b25) * 100, 2) if n2i(b25) else "",
                   "fund_city": "", "fund_national": "", "fund_balanced": "", "fund_other": "", "period": "", "basis": "", "purpose": "", "content": "",
                   "corp": "", "admin": "Y" if ADMIN.search(name) else "", "page": pno, "source": source, "_items": [], "_wrap": not name.endswith(")") and len(name) > 25}
            rows.append(cur)
    for r in rows:
        r["content"] = " · ".join(dict.fromkeys(r.pop("_items")))[:400]
        r.pop("_wrap", None)
        r["status"] = "신규" if not r["budget_2025"] and r["budget_2026"] else "계속"
        r["corp"] = "Y" if CORP.search(f"{r['name']} {r['content']}") else ""
    return rows


def debug_dump(path: Path, pages: list[str]) -> None:
    """서식이 안 맞을 때 러너 로그로 확인할 진단: 쪽 수, 제목형 줄, '예산총괄' 이 있는 첫 쪽 앞부분."""
    titles = [(i, l.strip()) for i, p in enumerate(pages, 1) for l in p.split("\n")[:3] if TITLE.match(l)]
    print(f"[debug] {path.name}: {len(pages)}쪽, 제목형 줄 {len(titles)}개 (앞 5: {titles[:5]})")
    k = next((i for i, p in enumerate(pages) if "예산총괄" in p), None)
    print(f"[debug] '예산총괄' 첫 쪽: {k + 1 if k is not None else '없음'}")
    if k is not None:
        print("[debug] ---- 그 쪽 앞 40줄 ----")
        print("\n".join(pages[k].split("\n")[:40]))
    else:
        print("[debug] ---- 3쪽 앞 30줄 ----")
        print("\n".join((pages[2] if len(pages) > 2 else pages[0]).split("\n")[:30]))


def parse_file(path: Path, year: int, debug: bool = False) -> list[dict]:
    pages = load_pages(path)
    if debug:
        debug_dump(path, pages)
    head3 = "\n".join(pages[:3])
    if re.search(r"사\s*업\s*명\s*세\s*서", head3) and re.search(r"실국\s*:", head3):
        mo = re.search(r"실국\s*:\s*(\S+)", head3)
        return parse_itemized(pages, year, f"{year}년 본예산 세출예산 사업명세서({mo.group(1) if mo else path.stem})")
    # 표지의 '[원스톱기업투자센터]' 나 파일명에서 출처 이름
    head = "\n".join(pages[:3])
    mm = re.search(r"\[([^\]]+)\]", head)
    org_name = re.sub(r"\s+", "", mm.group(1)) if mm else ""   # 표지는 글자 사이가 벌어져 있다(원 스 톱 …)
    source = f"{year}년 본예산 사업설명서({org_name})" if org_name else re.sub(r"\.(txt|pdf)$", "", path.name)
    blocks, cur = [], []
    for i, p in enumerate(pages, 1):
        lines = [l for l in p.split("\n") if l.strip()]
        if lines and TITLE.match(lines[0]) and "예산총괄" in p and "회계연도" in p:
            if cur:
                blocks.append(cur)
            cur = [(i, p)]
        elif cur:
            cur.append((i, p))
    if cur:
        blocks.append(cur)
    rows = []
    for blk in blocks:
        try:
            rows.append(parse_block(blk, year, source))
        except Exception as e:  # 한 사업이 깨져도 나머지는 살린다
            print(f"::warning::{path.name} p.{blk[0][0]} 파싱 실패: {e}", file=sys.stderr)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--append", action="store_true", help="기존 CSV 에 더한다(같은 출처는 갈아끼움)")
    ap.add_argument("--debug", action="store_true", help="서식 진단 출력(러너 로그용)")
    a = ap.parse_args()
    rows = []
    for f in a.files:
        r = parse_file(Path(f), a.year, a.debug)
        print(f"{f}: 세부사업 {len(r)}건 (기업 수혜 {sum(1 for x in r if x['corp'])}, 행정경비 {sum(1 for x in r if x['admin'])})")
        rows += r
    out = Path(a.out)
    if a.append and out.exists():
        srcs = {r["source"] for r in rows}
        old = [r for r in csv.DictReader(open(out, encoding="utf-8")) if r["source"] not in srcs]
        rows = old + rows
    # 같은 실국에 사업설명서(목적·내용·재원이 있는 판)가 있으면 사업명세서(표만 있는 판) 행은 뺀다 — 같은 사업이 두 번 실리지 않게
    rich = {(r["org"], r["dept"]) for r in rows if "명세서" not in r["source"]}   # 부서 단위(설명서가 권별로 나뉘어 올 수 있다)
    n0 = len(rows)
    rows = [r for r in rows if not ("명세서" in r["source"] and (r["org"], r["dept"]) in rich)]
    if n0 != len(rows):
        print(f"사업설명서가 있는 실국의 명세서 행 {n0 - len(rows)}건 제외")
    rows.sort(key=lambda r: (r["source"], r["org"], r["dept"], int(r["page"] or 0)))
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"→ {out} {len(rows)}건")


if __name__ == "__main__":
    main()
