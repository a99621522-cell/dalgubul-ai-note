#!/usr/bin/env python3
"""정책제안 리포트 품질 검사 — 자동 발행 전 통과해야 하는 문(gate).

사용:
  python3 scripts/review_report.py src/content/posts/2026-09-25-policy-robot-physical-ai.md   # 한 편. 통과 0 / 실패 1
  python3 scripts/review_report.py --published        # 발행된(draft: false) 정책제안 리포트 전부
  python3 scripts/review_report.py --json <file>      # 결과 JSON

검사 항목(오류 = 발행 불가, 경고 = 고치는 게 좋음):
  정책  7절은 2026-09-28 부터 정책 설계 형식(문제·분석·제안·추진·대안·근거·대상 규모·지표), 6절은 제목만 인용 금지·항목마다 대구 시사점
  구조  frontmatter(title "[정책제안] <분야>: …", category policy, tags 정책제안, summary, description, faq 3, sources ≥ MIN_SOURCES), 1~9절 제목,
        7절 제안 3개와 다섯 항목(문제·제안·근거·대상 규모·지표), 시/정부 건의/기업·기관 구분, 본문 길이
  숫자  숫자 없는 문단 없음(제목·표·인용 제외), 대상 규모에 '곳'
  예산  본문에 사업코드·예산액·국비/시비·재원 언급 없음(정책제안서는 예산을 참조하지 않는다, 운영자 지시 2026-09-25)
  표현  금지 형용사(급성장·위기·획기적…), 평가·비판·기관 입장 표현, 순위·추천 표현, 7절에 기업 사전의 회사명(특정 기업 지목) 없음
  출처  sources 의 url 이 http 로 시작·중복 없음, 날짜 확인(미확인 불가)·MAX_SOURCE_AGE 안, 최근 RECENT_DAYS 안 60% 이상 권장, 검색 요지만 쓴 경우 본문에 '요지' 표시
CLAUDE.md 글 작성 원칙 1·4·5·8 과 루틴 사양(docs/ROUTINE_PROMPT.md)을 코드로 옮긴 것. 통과가 '사실이 맞다'는 뜻은 아니다 — 수치 대조는 작성 세션의 자기 검토 항목.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "src" / "content" / "posts"
COMPANIES = ROOT / "scripts" / "data" / "dalseong_companies.csv"

MIN_SOURCES = 8
MAX_SOURCE_AGE = 365     # 출처 발행일이 리포트 날짜보다 이보다 오래되면 오류
RECENT_DAYS = 120        # 이 안의 출처가 60% 미만이면 경고
BODY_MIN, BODY_MAX = 2000, 6500          # 공백 제외 글자 수 (사양 2,500~3,500 에 표·머리말 여유)
BANNED_ADJ = r"급성장|급증세|위기|획기적|비약적|폭발적|압도적|혁신적인|눈부신|가파른|파격적|전례 없는|역대급"
EVALUATIVE = r"미흡하|부족하다|실패했|잘못됐|잘못된|무능|비판|안일|방치|늑장|졸속|전시행정|생색|무책임|실효성이 없|의문이다|우려된다|바람직하지"
STANCE = r"대구시는 .{0,20}(입장이다|밝혔다고 본다|것이다)|우리 시는|본 시는|시의 입장"
RANKING = r"\d+위\b|최고의|최상위|추천한다|추천하는|유망 기업|우수 기업|선도 기업으로 꼽|가장 뛰어난"
SECTIONS = ["1. 결론 먼저", "2. 지난 제안 점검", "3. 현재 위치", "4. 글로벌 변화", "5. 정부·타도시", "6. 연구기관", "7. 정책 제안", "8. 반론", "9. 출처"]
ITEMS = ["문제", "제안", "근거", "대상 규모", "지표"]                                   # 2026-09-27 까지 발행본
ITEMS_V2 = ["문제", "분석", "제안", "추진", "대안", "근거", "대상 규모", "지표"]          # 2026-09-28 부터: 정책 설계 형식(운영자 지시 2026-09-26 — 스크랩이 아니라 정책)
V2_FROM = date(2026, 9, 28)
BUDGET = r"\d{4}-\d{3}|예산(?!정책처)|국비|시비|지방비|백만\s*원|사업설명자료|세출|기금운용|재원"   # 정책제안서에는 예산을 참조하지 않는다(운영자 지시 2026-09-25)


def split(text: str) -> tuple[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    return (m.group(1), m.group(2)) if m else ("", text)


def parse_date(s: str):
    """'2026-09-25' · '2026-09' · '2026' → date (월·일이 없으면 1일). 그 밖('미확인' 등)은 None."""
    m = re.match(r"^\s*(20\d{2})(?:[-./](\d{1,2}))?(?:[-./](\d{1,2}))?\s*$", str(s or ""))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1))
    except ValueError:
        return None


def fm_get(fm: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.*)$", fm, re.M)
    return (m.group(1).strip().strip('"') if m else "")


def company_names() -> list[str]:
    if not COMPANIES.exists():
        return []
    names = set()
    for r in csv.DictReader(open(COMPANIES, encoding="utf-8")):
        n = re.sub(r"\((주|유|합|재)\)|㈜|주식회사|유한회사|유한책임회사|합자회사|합명회사|\s+", "", r.get("name", ""))
        n = re.sub(r"(제?\d*공장|[가-힣]*\d?(공장|지점|사업장|지사))$", "", n)   # '○○ 성서3공장' → '○○'
        if len(n) >= 3 and not re.fullmatch(r"[가-힣]{3}", n):   # 3자 한글 상호는 일반 명사와 겹쳐 뺀다
            names.add(n)
    return sorted(names, key=len, reverse=True)


GENERIC = {"대구광역시", "대구테크노파크", "한국로봇산업진흥원", "대구기계부품연구원", "대구디지털혁신진흥원", "경북대학교", "계명대학교", "영남대학교", "한국생산기술연구원",
           "한국전자통신연구원", "대구경북첨단의료산업진흥재단", "한국섬유개발연구원", "다이텍연구원", "대구창조경제혁신센터", "한국산업단지공단", "산업통상부", "중소벤처기업부",
           "과학기술정보통신부", "지능형자동차부품진흥원", "대구경북과학기술원", "한국은행", "대구상공회의소", "산업연구원", "한국산업기술기획평가원", "한국산업기술진흥원",
           "정보통신기획평가원", "한국과학기술기획평가원", "대구정책연구원", "한국자동차연구원", "한국로봇융합연구원", "대구경북연구원", "한국무역협회", "대한상공회의소"}


def review(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    fm, body = split(text)
    errors, warns = [], []
    title = fm_get(fm, "title")
    if not re.match(r"^\[정책제안\]\s*\S+.*:\s*\S", title):
        errors.append(f"title 형식: '[정책제안] <분야>: <핵심 제안 한 줄>' 이어야 함 → {title[:60]}")
    if fm_get(fm, "category") != "policy":
        errors.append("category 가 policy 가 아님")
    if "정책제안" not in fm_get(fm, "tags"):
        errors.append("tags 에 '정책제안' 없음")
    for k in ("summary", "description", "date"):
        if not fm_get(fm, k):
            errors.append(f"{k} 없음")
    if len(fm_get(fm, "description")) < 60:
        warns.append("description 이 짧다(결론 먼저의 핵심 문장 60자 이상 권장)")
    nq = len(re.findall(r"^\s*-\s*q:", fm, re.M))
    na = len(re.findall(r"^\s*a:", fm, re.M))
    if nq != 3 or na != 3:
        errors.append(f"faq 는 q/a 3쌍이어야 함 (q {nq}, a {na})")
    srcs = re.findall(r"^\s*-\s*\{\s*title:\s*\"(.*?)\",\s*url:\s*\"(.*?)\"", fm, re.M)
    if len(srcs) < MIN_SOURCES:
        errors.append(f"sources {len(srcs)}건 < {MIN_SOURCES}")
    urls = [u for _, u in srcs]
    if any(not u.startswith("http") for u in urls):
        errors.append("sources url 중 http 로 시작하지 않는 것이 있음")
    if len(set(urls)) != len(urls):
        warns.append("sources url 중복")
    # 출처 날짜: 날짜를 확인하지 못한 출처는 쓰지 않는다. 리포트 날짜 기준 MAX_SOURCE_AGE 일보다 오래된 출처는 오류(옛 자료로 정책 제안을 쓰지 않는다)
    rdate = parse_date(fm_get(fm, "date")) or date.today()
    dates = re.findall(r"^\s*-\s*\{\s*title:\s*\"(.*?)\".*?date:\s*\"?([^\"}]*?)\"?\s*\}", fm, re.M)
    undated = [t for t, d in dates if not parse_date(d)]
    if len(dates) < len(srcs):
        undated += ["(date 항목 없음)"] * (len(srcs) - len(dates))
    if undated:
        errors.append(f"출처 {len(undated)}건 날짜 미확인·누락 — 날짜를 확인할 수 없는 출처는 뺀다: " + "; ".join(t[:30] for t in undated[:5]))
    old = [(t, d) for t, d in dates if parse_date(d) and (rdate - parse_date(d)).days > MAX_SOURCE_AGE]
    if old:
        errors.append(f"출처 {len(old)}건이 {MAX_SOURCE_AGE}일보다 오래됨: " + "; ".join(f"{d} {t[:30]}" for t, d in old[:5]))
    recent_n = sum(1 for t, d in dates if parse_date(d) and (rdate - parse_date(d)).days <= RECENT_DAYS)
    if dates and recent_n < len(dates) * 0.6:
        warns.append(f"최근 {RECENT_DAYS}일 안 출처가 {recent_n}/{len(dates)}건 — 60% 이상 권장")
    if not re.search(r"^auto:\s*true", fm, re.M):
        warns.append("auto: true 표시 없음")

    # 절 구조
    for s in SECTIONS:
        if not re.search(rf"^##\s*{re.escape(s)}", body, re.M):
            errors.append(f"절 없음: {s}")
    sec7 = ""
    m = re.search(r"^##\s*7\. 정책 제안(.*?)(?=^##\s*8\.|\Z)", body, re.S | re.M)
    if m:
        sec7 = m.group(1)
        props = re.findall(r"^###\s*제안\s*\d", sec7, re.M)
        if len(props) != 3:
            errors.append(f"7절 제안이 3개가 아님 ({len(props)})")
        items_req = ITEMS_V2 if rdate >= V2_FROM else ITEMS
        for it in items_req:
            n = len(re.findall(rf"^\s*-\s*{it}(?:\s*비교|\s*체계|\s*주체)?\s*[:：]", sec7, re.M))
            if n < 3:
                errors.append(f"7절 '{it}' 항목이 제안 3개에 다 없음 ({n})" + (" — 정책 설계 형식: 문제·분석·제안·추진·대안·근거·대상 규모·지표" if rdate >= V2_FROM else ""))
        if rdate >= V2_FROM:
            # 분석 항목에는 원인·대구 특이점이, 대안 항목에는 택하지 않은 수단이 있어야 한다(숫자 포함은 문단 검사가 본다)
            for lab, need in (("분석", r"때문|원인|이유|구조|대구"), ("대안", r"대신|대안|비교|택하지|않은|보다")):
                vals = re.findall(rf"^\s*-\s*{lab}(?:\s*비교)?\s*[:：](.*)$", sec7, re.M)
                if any(not re.search(need, v) for v in vals):
                    warns.append(f"7절 '{lab}' 항목이 형식만 있고 내용이 얕은 제안이 있음({need.split('|')[0]} 등 표현 없음)")
    # 6절: 제목만 보고 인용 금지, 항목마다 대구 시사점
    m6 = re.search(r"^##\s*6\. 연구기관(.*?)(?=^##\s*7\.|\Z)", body, re.S | re.M)
    if m6:
        sec6 = m6.group(1)
        if re.search(r"제목 기준|본문 미확인|제목만", sec6):
            (errors if rdate >= V2_FROM else warns).append("6절에 제목만 보고 인용한 항목('제목 기준'·'본문 미확인') — 요지·본문을 읽지 못한 자료는 인용하지 않는다")
        bullets = [b for b in re.findall(r"^\s*-\s*\*\*(.*)$", sec6, re.M)]
        lacking = [b[:30] for b in bullets if "대구" not in b]
        if bullets and lacking and rdate >= V2_FROM:
            errors.append(f"6절 기관 시각 {len(lacking)}건에 대구 시사점(대구 …) 문장이 없음: " + "; ".join(lacking[:3]))
        elif lacking:
            warns.append(f"6절 기관 시각 {len(lacking)}건에 대구 시사점 문장이 없음")
        for role in ("시", "정부 건의", "기업·기관|기관·기업|기업|기관"):
            if not re.search(rf"###\s*제안\s*\d\s*\(({role})\)", sec7):
                errors.append(f"7절 제안 구분 '({role.split('|')[0]})' 없음 (시 / 정부 건의 / 기업·기관)")
        gun = re.findall(r"^\s*-\s*대상 규모\s*[:：](.*)$", sec7, re.M)
        if any("곳" not in g for g in gun):
            errors.append("7절 '대상 규모' 에 기업 수('곳')가 없는 제안이 있음")
        # 특정 기업 지목
        hits = [n for n in company_names() if n in re.sub(r"\s+", "", sec7) and n not in GENERIC and not any(n in g for g in GENERIC)]
        if hits:
            errors.append(f"7절에 기업 사전의 회사명이 있음(특정 기업 지목 금지): {hits[:5]}")
        if re.search(RANKING, sec7):
            errors.append("7절에 순위·추천 표현: " + ", ".join(sorted(set(re.findall(RANKING, sec7)))[:3]))

    # 문단마다 숫자
    no_num = []
    for para in re.split(r"\n\s*\n", body):
        p = para.strip()
        if not p or p.startswith(("#", "|", ">", "<", "!")) or re.match(r"^-{3,}$", p):
            continue
        for line in [p] if not p.startswith("-") else [x for x in p.split("\n") if x.strip()]:
            if not re.search(r"\d", line) and len(line) > 25:
                no_num.append(line[:50])
    if no_num:
        errors.append(f"숫자 없는 문단 {len(no_num)}개: " + " / ".join(no_num[:3]))

    # 예산 참조 금지 (본문 전체)
    bud = sorted(set(re.findall(BUDGET, body)))
    if bud:
        errors.append("예산 참조(사업코드·예산액·국비/시비·재원): " + ", ".join(bud[:6]))
    # 표현
    for name, pat, is_err in (("금지 형용사", BANNED_ADJ, True), ("평가·비판 표현", EVALUATIVE, True), ("기관 입장 표현", STANCE, True)):
        found = sorted(set(re.findall(pat, body)))
        if found:
            (errors if is_err else warns).append(f"{name}: {', '.join(found[:5])}")

    # 길이·요지
    n = len(re.sub(r"\s", "", body))
    if n < BODY_MIN or n > BODY_MAX:
        errors.append(f"본문 {n:,}자(공백 제외) — {BODY_MIN:,}~{BODY_MAX:,} 범위 밖")
    elif n > 4500:
        warns.append(f"본문 {n:,}자 — 사양 2,500~3,500 보다 길다")
    if "검색 결과 요지" in body and body.count("요지") < 5:
        warns.append("검색 요지로 썼다면서 '요지' 표시가 적다")

    rel = str(path.resolve().relative_to(ROOT)) if path.resolve().is_relative_to(ROOT) else str(path)
    return {"file": rel, "ok": not errors, "errors": errors, "warnings": warns, "chars": n, "sources": len(srcs)}


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    files = [Path(a) for a in argv if not a.startswith("--")]
    if "--published" in argv:
        files = [p for p in sorted(POSTS.glob("*-policy-*.md")) if re.search(r"^draft:\s*false", p.read_text(encoding="utf-8"), re.M)]
    if not files:
        print(__doc__)
        return 2
    results = [review(p) for p in files]
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    else:
        for r in results:
            print(f"{'통과' if r['ok'] else '실패'}  {r['file']}  ({r['chars']:,}자, 출처 {r['sources']})")
            for e in r["errors"]:
                print(f"   ✗ {e}")
            for w in r["warnings"]:
                print(f"   △ {w}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
