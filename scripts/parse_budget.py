#!/usr/bin/env python3
"""국회 공통요구자료 Ⅱ-1 사업설명자료(부처 예산 사업설명서) → CSV
사용: python3 scripts/parse_budget.py <PDF경로> [--ministry 부처명] [--out scripts/data/programs_xxx.csv]
  목차가 있으면 목차로, 없으면 '사 업 명' 표지 페이지로 사업 경계를 찾는다.
  AI 예산사업 통합 설명자료(국가AI전략위), 산업부·중기부·과기부 사업설명자료 모두 같은 양식.
구조: 목차(사업번호. 부처_사업명 쪽) → 각 사업은 '사 업 명' 표지 → 사업 코드 정보 → 예산 총괄표 → 사업설명자료(목적·개요·산출근거·효과)
"""
import csv, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "data" / "programs_ai.csv"

def load_pages(pdf: str):
    """PDF 는 pdftotext, .txt/.txt.gz(fetch_budget_docs 가 만든 본문)는 그대로. 쪽 구분은 form feed."""
    if pdf.endswith(".txt.gz"):
        import gzip
        txt = gzip.open(pdf, "rt", encoding="utf-8").read()
    elif pdf.endswith(".txt"):
        txt = Path(pdf).read_text(encoding="utf-8")
    else:
        txt = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
    return txt.split("\f")

def parse_toc(pages):
    toc = []
    for p in pages[:60]:
        if "사       업        명" in p: break
        for m in re.finditer(r"^\s*(\d+)\.\s+(.+?)\s+(\d+)\s*$", p, re.M):
            toc.append((int(m.group(1)), m.group(2).strip(), int(m.group(3))))
    return toc

def clean(s): return re.sub(r"\s+", " ", s or "").strip()

def grab(text, start_pat, end_pat, maxlen=1500):
    m = re.search(start_pat, text)
    if not m: return ""
    rest = text[m.end():]
    e = re.search(end_pat, rest)
    seg = rest[:e.start()] if e else rest[:maxlen*2]
    return clean(seg)[:maxlen]

def num(s):
    s = clean(s).replace(",", "")
    return s if re.fullmatch(r"-?\d+(\.\d+)?", s) else ""

def parse_program(text, name_hint, ministry):
    d = {}
    m = re.search(r"\((\d+)\)\s+(.+?)\s*\((\d{4}-\d{3})\)", text)
    d["name"] = clean(m.group(2)) if m else name_hint
    d["code"] = m.group(3) if m else ""
    # 회계
    acc = re.search(r"코드\s+(\S+?)\s+(?:과학기술정보|산업통상|중소벤처|[가-힣]+)\s", text)
    d["account"] = ""
    for k in ["일반회계", "지역균형발전", "정보통신진흥기금", "방송통신발전기금", "과학기술진흥기금", "소재부품장비", "에너지및자원", "기후대응기금", "고등·평생교육", "국가균형발전"]:
        if k in text[:1500]: d["account"] = k; break
    # 신규/계속
    seg = text[text.find("□ 사업 성격"):text.find("□ 사업 지원 형태")] if "□ 사업 성격" in text else ""
    d["new_or_continue"] = "신규" if re.search(r"신규\s*계속\s*완료\s*\n[^\n]*\n?\s*◯", seg) and re.search(r"\n\s{0,4}◯", seg) else ""
    # 지원 형태: 첫 ◯ 위치로 판단
    f = text[text.find("□ 사업 지원 형태"):text.find("□ 사업 소관부처")] if "□ 사업 지원 형태" in text else ""
    ftypes = ["직접", "출자", "출연", "보조", "융자"]
    d["support_type"] = ""
    hdr = re.search(r"직접\s+출자\s+출연\s+보조.*\n(.*)", f)
    if hdr:
        line = hdr.group(1)
        pos = line.find("◯")
        if pos >= 0:
            heads = [(f.find(x, hdr.start()) - hdr.start(), x) for x in ftypes]
            heads = [(abs(pos - (h - (hdr.group(0).find(hdr.group(1))))), x) for h, x in heads]
            d["support_type"] = min(heads)[1]
    gr = re.search(r"국고보조율\(%\)[^\n]*\n[^\n]*?(\d{1,3})\s*$", f, re.M)
    d["subsidy_rate"] = gr.group(1) if gr else ""
    ex = re.search(r"-\s*사업시행주체\s*:\s*([^\n]+)", text)
    d["executor"] = clean(ex.group(1))[:120] if ex else grab(text, r"사업시행주체\s+", r"\n", 80)
    be = re.search(r"-\s*사업\s*수혜자\s*:\s*([^\n]+(?:\n\s{6,}[^\n-]+)?)", text)
    if not be:  # 콜론이 다음 줄로 밀린 레이아웃(중기부 등)
        be = re.search(r"사업\s*수혜자\s+([^\n:]+)", text)
    d["beneficiary"] = clean(re.sub(r"^[:\-\s]+", "", be.group(1)))[:200] if be else ""
    if not d["executor"] or d["executor"] in ("", ":"):
        ex2 = re.search(r"사업시행주체\s+([^\n:]+)", text)
        d["executor"] = clean(ex2.group(1))[:120] if ex2 else d["executor"]
    d["period"] = grab(text, r"사업기간\s*:\s*", r"\n", 60)
    if not d["period"] or d["period"].startswith("년"):
        pm = re.search(r"사업기간\s*([^\n]+)", text); d["period"] = clean(re.sub(r"[:\s]+", " ", pm.group(1)))[:60] if pm else d["period"]
    d["total_cost"] = grab(text, r"총사업비\(해당되는 경우에만 기재\)\s*:\s*", r"\n", 80)
    d["purpose"] = grab(text, r"◯\s*사업목적", r"2\)\s*사업개요|□ 사업근거", 800)
    d["basis"] = grab(text, r"3\)\s*2026년도\s*예산\s*산출\s*근거", r"2025년 제2회 추가경정예산|4\)\s*사업효과", 800)
    d["history"] = grab(text, r"②\s*추진경위", r"□ 주요내용|① 사업규모", 500)
    # 예산: 총괄표 첫 사업명 행의 숫자들
    tb = text[text.find("가. 예산 총괄표"):text.find("□ 기능별 내역사업별")] if "가. 예산 총괄표" in text else ""
    nums = re.findall(r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)(?![\d,])", tb.split("(B-A)/A")[-1] if "(B-A)/A" in tb else tb)
    nums = [n for n in nums if n not in ("2024", "2025", "2026")]
    d["budget_nums"] = "|".join(nums[:8])
    # 5년 사업비 행
    y = re.search(r"사업비\s+([-\d,\s]+?)\n", text)
    d["cost_5y"] = clean(y.group(1)) if y else ""
    # 2026 예산: 사업비 5년 행 → 없으면 총괄표 행(2024결산, 2025본, 2025추경(A), 2026요구, 2026본(B))
    prev = d["cost_5y"].split()
    last = [n for n in prev if n != "-"]
    d["budget_2026"] = last[-1].replace(",", "") if len(prev) >= 5 and last else ""
    d["budget_2025"] = (prev[-2].replace(",", "") if prev[-2] != "-" else "0") if len(prev) >= 5 else ""
    if not d["budget_2026"] and "(B-A)/A" in tb:
        after = tb.split("(B-A)/A", 1)[1]
        for line in after.splitlines():
            toks = re.findall(r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+|-)(?![\d,])", line)
            toks = [t for t in toks if t not in ("2024", "2025", "2026")]
            if len(toks) >= 5:
                d["budget_2025"] = "0" if toks[1] == "-" else toks[1].replace(",", "")
                d["budget_2026"] = "" if toks[4] == "-" else toks[4].replace(",", "")
                break
    hay = " ".join([d["name"], d["executor"], d["beneficiary"], d["purpose"], d["history"], d["basis"]])
    d["daegu_mention"] = "Y" if re.search(r"대구|달성군|DGIST|대경권|대구경북", hay) else ""
    d["region_scope"] = "전국" if re.search(r"전국|국민|중소기업|기업 등|산·학·연|산학연", d["beneficiary"]) else ("지역지정" if re.search(r"광주|대구|부산|전북|강원|충북|충남|경남|경북|대전|울산|세종|제주|전남|인천|경기", hay[:600]) else "")
    d["ministry"] = ministry
    return d

def find_titles(pages):
    out = []
    for i, p in enumerate(pages):
        head = p[:400]
        if re.search(r"사\s+업\s+명", head):
            m = re.search(r"\((\d+)\)\s+(.+?)\s*\((\d{4}-\d{3})\)", p)
            if m: out.append((int(m.group(1)), m.group(2).strip(), i + 1))
    return out

def main(pdf, ministry=None, out=None):
    global OUT
    if out: OUT = Path(out)
    pages = load_pages(pdf)
    toc = parse_toc(pages)
    titles = find_titles(pages)
    # AI 통합자료는 목차가 '부처_사업명' 형식. 그 외(부처 개별 설명자료)는 표지 페이지 기준이 정확함
    if len(toc) < 5 or sum("_" in t[1] for t in toc) < len(toc) * 0.8 or len(titles) > len(toc) * 1.2:
        toc = [(n, f"{ministry or ''}_{name}", pg) for n, name, pg in find_titles(pages)]
    rows = []
    for i, (n, title, pg) in enumerate(toc):
        end = toc[i + 1][2] if i + 1 < len(toc) else len(pages)
        text = "\n".join(pages[pg - 1:end - 1])
        ministry_t, _, name_hint = title.partition("_")
        d = parse_program(text, name_hint, ministry or ministry_t)
        bu = re.search(r"실국\(기관\)[\s\S]{0,200}?\n[^\n]*?(\S+?(?:정책관|정책실|산업국|산업정책관|산업본부|국|관))\s", text[:1500])
        d["bureau"] = bu.group(1) if bu else ""
        d["no"] = n; d["page"] = pg; d["source"] = "국가AI전략위 AI 예산사업 통합 설명자료(2026.3)"
        rows.append(d)
    cols = ["no", "ministry", "bureau", "name", "code", "account", "new_or_continue", "support_type", "subsidy_rate", "executor", "beneficiary",
            "period", "total_cost", "budget_2025", "budget_2026", "cost_5y", "budget_nums", "daegu_mention", "region_scope", "purpose", "history", "basis", "page", "source"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for r in rows: w.writerow({c: r.get(c, "") for c in cols})
    print(f"{len(rows)}건 → {OUT}")

if __name__ == "__main__":
    args = sys.argv[1:]
    m = args[args.index("--ministry") + 1] if "--ministry" in args else None
    o = args[args.index("--out") + 1] if "--out" in args else None
    main(args[0], m, o)
