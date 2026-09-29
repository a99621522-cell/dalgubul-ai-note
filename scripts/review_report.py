#!/usr/bin/env python3
"""정책제안 리포트 품질 검사 — 자동 발행 전 통과해야 하는 문(gate).

사용:
  python3 scripts/review_report.py src/content/posts/2026-09-25-policy-robot-physical-ai.md   # 한 편. 통과 0 / 실패 1
  python3 scripts/review_report.py --published        # 발행된(draft: false) 정책제안 리포트 전부
  python3 scripts/review_report.py --json <file>      # 결과 JSON

검사 항목(오류 = 발행 불가, 경고 = 고치는 게 좋음):
  정책  7절은 2026-09-28 부터 정책 설계 형식(문제·분석·제안·추진·대안·근거·대상 규모·지표), 6절은 제목만 인용 금지·항목마다 대구 시사점
  형식  format: brief(2026-09-29 부터, 대구정책 브리프식 개조식 정책 브리프 — review_brief(): 요약·1 배경·2 현황과 문제·3 제안(0~3개)·4 기대효과와 한계,
        주장(● 항목)마다 근거 표시 [n]/기업 사전/KOSIS, 제안 수치는 도출 근거 또는 '조사 뒤 정함', 키워드 집계를 역량·수요 근거로 쓰지 않음, 원인 문장에 근거, 현황·제안에 '미확인' 전제 금지,
        출처 ≥ BRIEF_MIN_SOURCES 이고 공식통계·기관발간물·정부문서 ≥ BRIEF_MIN_OFFICIAL, 2,000~6,000자, 개조식(명사형 종결). --gate 는 발행 가능 여부만 출력)
        format: full(2026-09-29 부터, 보고서형 — 운영자 지시: 브리프의 논리 규칙을 그대로 쓰되 절 수 자유(요약·…·'해결방안/제안' 절·'한계' 절을 제목으로 찾음),
        방안 0~5개, 출처 ≥ 10·공식 ≥ 4, 5,000~16,000자(표 행 제외), 순위·추천 표현은 본문 전체에서 금지)
        format: insight(2026-09-28 부터, 산문형 인사이트 리포트: 제목 40자 이하 헤드라인, outline 4~6, hero.prompt/caption, 2단계 절 4~8, 그림 ≥2, 제안 절 ### 3개(시/정부 건의/기업·기관, 각각 N곳·지표), 반론, 3,000~7,500자)
        format 없음/report(2026-09-27 까지): 아래 1~9절 구조
  구조  frontmatter(title "[정책제안] <분야>: <헤드라인>", category policy, tags 정책제안, summary, description, faq 3, sources ≥ MIN_SOURCES), 1~9절 제목,
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
           "정보통신기획평가원", "한국과학기술기획평가원", "대구정책연구원", "한국자동차연구원", "한국로봇융합연구원", "대구경북연구원", "한국무역협회", "대한상공회의소",
           "개인정보이노베이션존"}   # 개인정보위 지정 제도 이름(2026-09-29) — 같은 이름의 회사 '이노베이션'과 겹침


INSIGHT_MIN, INSIGHT_MAX = 3000, 7500   # 인사이트 리포트 본문(공백 제외). LG경영연구원 리포트 7쪽 ≈ 5,000자
INSIGHT_MIN_FIGS = 2                    # 그림(<figure> + /figures/<id>/) 최소 개수
TITLE_MAX = 40                          # 제목은 짧은 헤드라인(명사구 또는 "…이 열린다" 형). "…하게 한다" 식 긴 절 금지(운영자 지시 2026-09-27)
TITLE_BAD_END = r"(하게 한다|쓰게 한다|되게 한다|해야 한다|한다\.|하자)$"


def review_insight(path: Path, fm: str, body: str, errors: list, warns: list) -> None:
    """format: insight — 산문형 리포트 구조 검사. 공통 검사(출처·숫자·표현·예산)는 review() 가 이어서 한다."""
    title = fm_get(fm, "title")
    if title.startswith("[정책제안]"):
        errors.append("insight 제목에 '[정책제안]' 접두어를 붙이지 않는다(태그로 구분)")
    if len(title) > TITLE_MAX:
        errors.append(f"제목 {len(title)}자 — {TITLE_MAX}자 이하 헤드라인으로")
    if re.search(TITLE_BAD_END, title):
        errors.append(f"제목이 '…하게 한다' 식 절로 끝남 — 명사구나 짧은 문장 헤드라인으로 → {title}")
    mo = re.search(r"^outline:\s*\[(.*?)\]\s*$", fm, re.M)
    if mo:  # 한 줄 목록 ["a", "b"]
        outline = [x.strip().strip('"\'') for x in mo.group(1).split(",") if x.strip()]
    else:   # 여러 줄 목록
        mb = re.search(r"^outline:\s*\n((?:[ \t]+-.*\n?)+)", fm, re.M)
        outline = [x.strip().strip('"\'') for x in re.findall(r"^[ \t]+-\s*(.*)$", mb.group(1), re.M)] if mb else []
    if not 4 <= len(outline) <= 6:
        errors.append(f"outline(요약 상자 절 제목)은 4~6개 ({len(outline)})")
    heads = re.findall(r"^##\s+(.*)$", body, re.M)
    if not 4 <= len(heads) <= 8:
        errors.append(f"2단계 절이 4~8개여야 함 ({len(heads)})")
    for o in outline:
        if not any(o.strip() in h for h in heads):
            errors.append(f"outline 항목이 본문 절 제목에 없음: {o[:30]}")
    if not re.search(r"^hero:\s*\n\s+prompt:", fm, re.M):
        errors.append("hero.prompt 없음(대표 그림 생성 프롬프트)")
    if not re.search(r"^hero:\s*\n(?:.*\n)*?\s+caption:", fm, re.M):
        errors.append("hero.caption 없음")
    figs = re.findall(r"<figure[\s\S]*?<img[^>]+src=\"(/figures/[^\"]+)\"[\s\S]*?<figcaption>([\s\S]*?)</figcaption>[\s\S]*?</figure>", body)
    if len(figs) < INSIGHT_MIN_FIGS:
        errors.append(f"그림(<figure><img src=/figures/…><figcaption>) {len(figs)}개 < {INSIGHT_MIN_FIGS} — scripts/figure.py 로 만든 SVG")
    for src, cap in figs:
        if not src.startswith(f"/figures/{path.stem}/"):
            errors.append(f"그림 경로는 /figures/{path.stem}/ 아래여야 함: {src}")
        if "출처" not in cap and "자료" not in cap:
            warns.append(f"그림 설명에 출처가 없음: {cap[:30]}")
    # 정책 제안 절: ### 3개, (시)/(정부 건의)/(기업·기관), 각 제안에 대상(곳)·지표·추진 시점
    m = re.search(r"^##\s+[^\n]*제안[^\n]*\n(.*?)(?=^##\s|\Z)", body, re.S | re.M)
    if not m:
        errors.append("'제안' 이 든 2단계 절 없음(정책 제안 절)")
        return
    sec = m.group(1)
    props = re.findall(r"^###\s+(.*)$", sec, re.M)
    if len(props) != 3:
        errors.append(f"제안 절의 3단계 제목(제안)이 3개가 아님 ({len(props)})")
    for role in ("시", "정부 건의", "기업·기관|기관·기업|기업|기관"):
        if not any(re.search(rf"\(({role})\)", h) for h in props):
            errors.append(f"제안 제목에 '({role.split('|')[0]})' 구분 없음 (시 / 정부 건의 / 기업·기관)")
    parts = re.split(r"^###\s+.*$", sec, flags=re.M)[1:]
    for h, ptxt in zip(props, parts):
        if not re.search(r"\d[\d,]*\s*곳", ptxt):
            errors.append(f"제안 '{h[:20]}'에 대상 규모('N곳')가 없음")
        if not re.search(r"지표|1년 뒤|성공 기준", ptxt):
            errors.append(f"제안 '{h[:20]}'에 지표(1년 뒤 성공 기준)가 없음")
        if not re.search(r"20\d\d년|20\d\d-\d\d|상반기|하반기|분기", ptxt):
            warns.append(f"제안 '{h[:20]}'에 추진 시점이 없음")
        if not re.search(r"대신|대안|택하지|비교하면|보다", ptxt):
            warns.append(f"제안 '{h[:20]}'에 검토한 다른 수단(대안) 언급이 없음")
    if not re.search(r"반론|반대|틀릴 수", body):
        errors.append("반론(반대 근거와 틀릴 수 있는 이유)이 없음")
    hits = [n for n in company_names() if n in re.sub(r"\s+", "", sec) and n not in GENERIC and not any(n in g for g in GENERIC)]
    if hits:
        errors.append(f"제안 절에 기업 사전의 회사명이 있음(특정 기업 지목 금지): {hits[:5]}")
    if re.search(RANKING, sec):
        errors.append("제안 절에 순위·추천 표현: " + ", ".join(sorted(set(re.findall(RANKING, sec)))[:3]))


BRIEF_MIN, BRIEF_MAX = 2000, 6000        # 정책 브리프 본문(공백 제외). 대구정책 브리프 8쪽 ≈ 3,500자
FULL_MIN, FULL_MAX = 5000, 16000        # 보고서형(format: full, 운영자 지시 2026-09-29) 본문(공백 제외, 표 행 제외)
FULL_MIN_SOURCES, FULL_MIN_OFFICIAL, FULL_MAX_PROPS = 10, 4, 5
BRIEF_MIN_SOURCES = 5                    # 출처 하한(운영자 지시 2026-09-28: 개수 하한을 낮춤)
BRIEF_MIN_OFFICIAL = 2                   # 그중 공식통계·기관 발간물·법령·정부 문서(kind 가 official) 최소
CITE = r"\[\d+\]|\[\^[^\]\s]+\]|기업 사전|KOSIS|ECOS|사업 DB|지원 이력|report_context|data/(kosis|ecos|research|refs)"   # 근거 표시
UNITS = r"곳|건|명|개|석|%|％|억|만\s*원|원|일|주|회|기|종|톤|대|㎡|㎢|점|배"
KEYWORD_COUNT = r"낱말이 든|키워드|검색어|낱말 일치"                              # 공장등록 키워드 집계
CAPABILITY = r"역량|수요|대응|준비|수준|단계에 있|전환 전|전환 상태|SDV 대응|소프트웨어 조직"   # 키워드 집계로 말하면 안 되는 것
CAUSE = r"때문|원인은|원인이|이유는|탓|기인"
DERIVED = CITE + r"|조사 뒤 정함|계산\s*[:：]|=|÷|×|나눈|곱한|합계|합한"


def _sections_brief(body: str, titles: dict | None = None) -> dict[str, str]:
    """'## 요약', '## 1. 배경' … 절을 번호(요약은 0)로 나눈다. titles 를 주면 번호 → 절 제목도 채운다."""
    out: dict[str, str] = {}
    for m in re.finditer(r"^##\s+(요약|(\d)\.\s*[^\n]*)\n(.*?)(?=^##\s|\Z)", body, re.S | re.M):
        key = "0" if m.group(1).startswith("요약") else m.group(2)
        out[key] = m.group(3)
        if titles is not None:
            titles[key] = m.group(1)
    return out


def _claims(sec: str) -> list[tuple[str, str]]:
    """● 주장(들여쓰기 없는 '- ' 항목)과 그 아래 – 근거(들여쓴 항목)를 묶는다. ### 소제목 아래도 같은 규칙."""
    claims: list[tuple[str, str]] = []
    cur = None
    for line in sec.split("\n"):
        if re.match(r"^- ", line):
            if cur:
                claims.append(cur)
            cur = (line[2:].strip(), "")
        elif re.match(r"^\s+- ", line) and cur:
            cur = (cur[0], cur[1] + " " + line.strip()[2:])
        elif line.strip() and not line.startswith(("#", "|", "<", ">", "**")) and cur and not re.match(r"^\s", line):
            if cur:
                claims.append(cur)
            cur = None
    if cur:
        claims.append(cur)
    return claims


def review_brief(path: Path, fm: str, body: str, errors: list, warns: list, full: bool = False) -> None:
    """format: brief — 대구정책 브리프식 개조식 정책 브리프. 논리 규칙(운영자 지시 2026-09-28):
    주장마다 근거 1개 / 제안 수치는 도출 근거 또는 '조사 뒤 정함' / 키워드 집계는 품목 등록 기업 수로만 / 원인 문장에 근거 /
    확인 안 된 전제(미확인)로 문제·제안을 쓰지 않음(한계 절에서만) / 제안 0~3개 / 출처·공식 자료 하한 / 개조식."""
    title = fm_get(fm, "title")
    if title.startswith("[정책제안]"):
        errors.append("브리프 제목에 '[정책제안]' 접두어를 붙이지 않는다")
    if len(title) > TITLE_MAX:
        errors.append(f"제목 {len(title)}자 — {TITLE_MAX}자 이하")
    if re.search(TITLE_BAD_END, title):
        errors.append(f"제목이 '…하게 한다' 식 절로 끝남 → {title}")
    titles: dict[str, str] = {}
    secs = _sections_brief(body, titles)
    if full:
        # 보고서형(운영자 지시 2026-09-29): 절 수는 자유, 절은 제목으로 찾는다 — 해결방안(또는 제안) 절 1개, 한계 절 1개
        prop_k = next((k for k in sorted(secs) if k != "0" and re.search(r"해결\s*방안|제안", titles[k])), None)
        lim_k = next((k for k in sorted(secs) if k != "0" and re.search(r"한계", titles[k])), None)
        if "0" not in secs:
            errors.append("절 없음: '## 요약'")
        if not prop_k:
            errors.append("절 없음: 제목에 '해결방안' 또는 '제안'이 든 절")
        if not lim_k:
            errors.append("절 없음: 제목에 '한계'가 든 절(기대효과와 한계)")
        if "0" not in secs or not prop_k or not lim_k:
            return
        claim_ks = [k for k in sorted(secs) if k not in ("0", lim_k)]
        max_props = FULL_MAX_PROPS
    else:
        for k, name in (("0", "요약"), ("1", "1. 배경"), ("2", "2. 현황과 문제"), ("3", "3. 제안"), ("4", "4. 기대효과와 한계")):
            if k not in secs:
                errors.append(f"절 없음: '## {name}' (요약 · 1. 배경 · 2. 대구 현황과 문제 · 3. 제안 · 4. 기대효과와 한계)")
        if any(k not in secs for k in "0123"):
            return
        prop_k, lim_k, claim_ks, max_props = "3", "4", ["1", "2", "3"], 3
    # 요약: ● 항목 3~6개
    n_sum = len(re.findall(r"^- ", secs["0"], re.M))
    if not 3 <= n_sum <= 6:
        errors.append(f"요약 ● 항목은 3~6개 ({n_sum})")
    # 주장마다 근거: 1·2·3절의 ● 항목은 자신이나 아래 – 항목에 근거 표시([n]·기업 사전·KOSIS…)가 있어야 한다
    ITEM_LABEL = r"^\**(내용|추진|대상|대안|지표|일정|효과|한계)\**\s*[:：]"   # 제안의 항목 줄은 '- 근거:' 항목이 근거를 맡는다
    for k in claim_ks:
        for claim, ev in _claims(secs[k]):
            if k == prop_k and re.match(ITEM_LABEL, claim):
                continue
            if not re.search(CITE, claim + " " + ev):
                errors.append(f"{k}절 근거 없는 주장: {claim[:40]}")
    # 원인 문장에는 근거
    for k in claim_ks:
        for line in secs[k].split("\n"):
            if re.search(CAUSE, line) and not re.search(CITE, line):
                errors.append(f"{k}절 근거 없는 원인 문장: {line.strip()[:50]}")
    # 키워드 집계를 역량·수요·대응의 근거로 쓰지 않는다
    for k in ["0"] + claim_ks:
        for line in secs[k].split("\n"):
            if re.search(KEYWORD_COUNT, line) and re.search(CAPABILITY, line):
                errors.append(f"{k}절 키워드 집계를 역량·수요·대응의 근거로 씀(품목 등록 기업 수로만): {line.strip()[:50]}")
    # 확인 안 된 전제: 현황·제안 절에 '미확인' 금지(한계 절로)
    for k in (claim_ks if full else ["2", "3"]):
        for line in secs[k].split("\n"):
            if re.search(r"미확인|확인되지 않|확인할 수 없", line):
                errors.append(f"{k}절에 확인 안 된 전제('미확인') — 사실로 쓰지 말고 4절 한계로 옮기거나 조사 제안으로: {line.strip()[:50]}")
    # 제안 0~3개, 항목: 내용·근거·추진·대상 / 조사 제안은 1개
    props = re.findall(r"^###\s+(.*)$", secs[prop_k], re.M)
    if len(props) > max_props:
        errors.append(f"제안이 {max_props}개를 넘음 ({len(props)}) — 근거가 받쳐 주는 만큼만(0~{max_props})")
    if len(props) == 0 and not re.search(r"조사 제안|제안 없음|제안하지 않", secs[prop_k]):
        errors.append("3절에 제안(### 제안 N.)이 없으면 '조사 제안' 또는 '제안 없음'과 이유를 적는다")
    survey = [h for h in props if "조사" in h]
    if survey and len(props) > 1 and not full:
        errors.append("조사 제안이 있으면 제안은 그 1개만(전제가 확인되지 않은 주제)")
    parts = re.split(r"^###\s+.*$", secs[prop_k], flags=re.M)[1:]
    for h, ptxt in zip(props, parts):
        for it in ("근거", "추진"):
            if not re.search(rf"^\s*-\s*\*?\*?{it}", ptxt, re.M):
                errors.append(f"제안 '{h[:20]}'에 '- {it}:' 항목 없음")
        # 논증 사슬(운영자 지적 2026-09-28): 목표·진단·원인·기제·기대효과 — 조사 제안은 예외
        if "조사" not in h:
            for it in ("목표", "진단", "원인", "기제", "기대효과"):
                lab = {"진단": "진단|현황", "기제": "기제|작동 방식"}.get(it, it)   # 사람이 읽는 말로 써도 된다(운영자 지시 2026-09-29)
                val = re.search(rf"^\s*-\s*\*?\*?(?:{lab})\*?\*?\s*[:：](.*)$", ptxt, re.M)
                if not val:
                    errors.append(f"제안 '{h[:20]}'에 '- {it}:' 항목 없음(논증 사슬: 목표→진단→원인→기제→기대효과)")
                elif it in ("진단", "원인", "기제") and not re.search(CITE, val.group(1)):
                    errors.append(f"제안 '{h[:20]}' '{it}' 항목에 근거 표시 없음")
                elif it == "기제" and re.search(r"정했|배치했|지정했|발표했", val.group(1)) and not re.search(r"비교우위|대구 값|대구에|기업 사전|곳", val.group(1)):
                    errors.append(f"제안 '{h[:20]}' '기제' 가 남의 계획 서술뿐(왜 이 수단이 원인을 없애고 대구가 비교우위인지 대구 값으로)")
        if "조사" not in h and not re.search(r"^\s*-\s*\*?\*?대상", ptxt, re.M):
            errors.append(f"제안 '{h[:20]}'에 '- 대상:' 항목(기업 사전 필터와 N곳) 없음")
        # 제안 수치는 도출 근거 또는 '조사 뒤 정함' (연·월·일 날짜는 제외)
        for line in ptxt.split("\n"):
            nums = re.findall(rf"\d[\d,\.]*\s*(?:{UNITS})", re.sub(r"20\d\d\s*년|\d{1,2}\s*월|\d{1,2}\s*일(?!\s*안)|20\d\d-\d\d", "", line))
            if nums and not re.search(DERIVED, line):
                errors.append(f"제안 '{h[:16]}' 수치에 도출 근거 없음(근거 표시·계산 또는 '조사 뒤 정함'): {line.strip()[:50]}")
    # 4절: 기대효과와 한계(반론)
    if not re.search(r"한계|반론|틀릴 수", secs[lim_k]):
        errors.append(f"{lim_k}절에 한계·반론이 없음")
    # 개조식: ● – 항목이 '~다.' 로 끝나면 안 된다(명사형 종결)
    bullets = [l.strip() for l in body.split("\n") if re.match(r"^\s*- ", l)]
    dah = [b for b in bullets if re.search(r"(다|요)\.\s*(\[\d+\])?\s*$", b)]
    if bullets and len(dah) > len(bullets) * 0.2:
        errors.append(f"개조식이 아님: '~다.' 로 끝나는 항목 {len(dah)}/{len(bullets)} (명사형 종결로): " + dah[0][:40])
    # 특정 기업 지목·순위(제안 절)
    hits = [n for n in company_names() if n in re.sub(r"\s+", "", secs[prop_k]) and n not in GENERIC and not any(n in g for g in GENERIC)]
    if hits:
        errors.append(f"제안 절에 기업 사전의 회사명이 있음(특정 기업 지목 금지): {hits[:5]}")
    if re.search(RANKING, body if full else secs[prop_k]):
        errors.append("순위·추천 표현: " + ", ".join(sorted(set(re.findall(RANKING, body if full else secs[prop_k])))[:3]))
    # 출처 신뢰성: kind official(공식통계·기관 발간물·법령·정부 문서) 최소 개수
    kinds = re.findall(r"^\s*-\s*\{\s*title:.*?kind:\s*\"?(\w+)\"?", fm, re.M)
    official = sum(1 for k in kinds if k in ("official", "stat", "report", "law", "gov"))
    min_off = FULL_MIN_OFFICIAL if full else BRIEF_MIN_OFFICIAL
    if official < min_off:
        errors.append(f"공식 자료 출처(kind: official/stat/report/law/gov) {official}건 < {min_off} — 통계·기관 발간물·법령·정부 문서로 받친다")
    if len(kinds) < len(re.findall(r"^\s*-\s*\{\s*title:", fm, re.M)):
        warns.append("kind 가 없는 출처가 있음(official/stat/report/law/gov/news/data 중 하나)")


def review(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    fm, body = split(text)
    errors, warns = [], []
    insight = bool(re.search(r"^format:\s*insight", fm, re.M))
    full = bool(re.search(r"^format:\s*full", fm, re.M))      # 보고서형(운영자 지시 2026-09-29): 브리프 논리 규칙 + 절·방안 수 확대
    brief = full or bool(re.search(r"^format:\s*brief", fm, re.M))
    title = fm_get(fm, "title")
    if not insight and not brief and not re.match(r"^(\[정책제안\]\s*)?\S+.*:\s*\S", title):   # 접두어는 선택(2026-09-27 목록 표기 통일로 뗌)
        errors.append(f"title 형식: '<분야>: <헤드라인>' 이어야 함 → {title[:60]}")
    if not insight and not brief and re.search(TITLE_BAD_END, title):
        errors.append(f"제목이 '…하게 한다' 식 절로 끝남 — 짧은 헤드라인으로 → {title[:60]}")
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
    min_src = FULL_MIN_SOURCES if full else BRIEF_MIN_SOURCES if brief else MIN_SOURCES
    if len(srcs) < min_src:
        errors.append(f"sources {len(srcs)}건 < {min_src}")
    urls = [u for _, u in srcs]
    if any(not u.startswith("http") for u in urls):
        errors.append("sources url 중 http 로 시작하지 않는 것이 있음")
    if len(set(urls)) != len(urls):
        warns.append("sources url 중복")
    # 출처 날짜: 날짜를 확인하지 못한 출처는 쓰지 않는다. 리포트 날짜 기준 MAX_SOURCE_AGE 일보다 오래된 출처는 오류(옛 자료로 정책 제안을 쓰지 않는다)
    rdate = parse_date(fm_get(fm, "date")) or date.today()
    dates = re.findall(r"^\s*-\s*\{\s*title:\s*\"(.*?)\".*?date:\s*\"?([^\",}]*?)\"?\s*(?:,|\})", fm, re.M)   # date 뒤에 kind 등 다른 항목이 와도 된다
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
    sec7 = ""
    if insight:
        review_insight(path, fm, body, errors, warns)
    if brief:
        review_brief(path, fm, body, errors, warns, full=full)
    for s in ([] if (insight or brief) else SECTIONS):
        if not re.search(rf"^##\s*{re.escape(s)}", body, re.M):
            errors.append(f"절 없음: {s}")
    m = None if (insight or brief) else re.search(r"^##\s*7\. 정책 제안(.*?)(?=^##\s*8\.|\Z)", body, re.S | re.M)
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
    m6 = None if (insight or brief) else re.search(r"^##\s*6\. 연구기관(.*?)(?=^##\s*7\.|\Z)", body, re.S | re.M)
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

    # 문단마다 숫자 (그림 <figure> 블록은 제외)
    no_num = []
    body_nf = re.sub(r"<figure[\s\S]*?</figure>", "", body)
    for para in re.split(r"\n\s*\n", body_nf):
        p = para.strip()
        if not p or p.startswith(("#", "|", ">", "<", "!")) or re.match(r"^-{3,}$", p):
            continue
        for line in [p] if not p.startswith("-") else [x for x in p.split("\n") if x.strip()]:
            if not re.search(r"\d", line) and len(line) > 25:
                no_num.append(line[:50])
    if no_num and not brief:   # 브리프는 '문단마다 숫자' 대신 '주장마다 근거'(운영자 지시 2026-09-28)
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
    n_src = body_nf
    if brief:   # 브리프는 표 행을 길이에서 뺀다(표는 근거 자료라 길이 상한의 대상이 아님 — 운영자 지시 2026-09-30: 앵커 사업장 표에 기업명 기재)
        n_src = "\n".join(l for l in body_nf.split("\n") if not l.lstrip().startswith("|"))
    n = len(re.sub(r"\s", "", n_src))
    lo, hi = (FULL_MIN, FULL_MAX) if full else (BRIEF_MIN, BRIEF_MAX) if brief else (INSIGHT_MIN, INSIGHT_MAX) if insight else (BODY_MIN, BODY_MAX)
    if n < lo or n > hi:
        errors.append(f"본문 {n:,}자(공백 제외) — {lo:,}~{hi:,} 범위 밖")
    elif not insight and not full and n > 4500:
        warns.append(f"본문 {n:,}자 — 사양 2,500~3,500 보다 길다")
    if "검색 결과 요지" in body and body.count("요지") < 5:
        warns.append("검색 요지로 썼다면서 '요지' 표시가 적다")

    rel = str(path.resolve().relative_to(ROOT)) if path.resolve().is_relative_to(ROOT) else str(path)
    return {"file": rel, "ok": not errors, "errors": errors, "warnings": warns, "chars": n, "sources": len(srcs), "format": "full" if full else "brief" if brief else "insight" if insight else "report"}


def main(argv: list[str]) -> int:
    """--gate <file>: 발행 문. 오류 0 이고 format brief 이면 'PASS', 아니면 'FAIL' 과 사유(발행은 PASS 일 때만, 운영자 지시 2026-09-28: 충분한 자료와 신뢰성이 있을 때 발간)."""
    as_json = "--json" in argv
    files = [Path(a) for a in argv if not a.startswith("--")]
    if "--published" in argv:
        files = [p for p in sorted(POSTS.glob("*-policy-*.md")) if re.search(r"^draft:\s*false", p.read_text(encoding="utf-8"), re.M)]
    if not files:
        print(__doc__)
        return 2
    results = [review(p) for p in files]
    if "--gate" in argv:
        ok = all(r["ok"] and r["format"] in ("brief", "full") for r in results)
        print("PASS" if ok else "FAIL")
        for r in results:
            for e in r["errors"]:
                print(f"   ✗ {e}")
            if r["format"] not in ("brief", "full"):
                print(f"   ✗ format 이 brief/full 이 아님({r['format']}) — 2026-09-29 부터 브리프·보고서형만 발행")
        return 0 if ok else 1
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
