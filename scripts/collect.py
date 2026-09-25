#!/usr/bin/env python3
"""달구벌 AI 노트 수집·초안 생성기 (1주차 버전)

흐름: 소스 수집 → 키워드 선별 → 중복 제거 → (공고) data/notices/notices.csv 에 사실만 기록
                                        → (기업 동향·정책) Gemini 요약 → Markdown 초안 저장
공무원용 사이트라 지원사업 공고는 글로 쓰지 않는다(2026-09-25). 공고는 제목·기관·마감·링크·예산 대조 결과만 데이터로 남겨
정책제안 리포트(report_context.py)의 '타 기관 공고 동향' 근거로 쓴다. Gemini 는 공시·보도자료 초안에만 쓴다.
초안은 draft: true 로 저장되며, approve.py 로 승인해야 사이트에 노출된다.

필요 환경변수
  BIZINFO_KEY   기업마당 지원사업 API 인증키 (공공데이터포털)
  GEMINI_KEY    Google AI Studio API 키
  GEMINI_MODEL  (선택) 기본 gemini-3.5-flash-lite
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import requests
import yaml
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from programs import match_program  # 공고 ↔ 부처 예산 사업 대조 (scripts/programs.py, 표준 라이브러리)

# Windows 콘솔(cp949)에서 로그의 유니코드 문자로 죽지 않게 한다
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "src" / "content" / "posts"
STATE = ROOT / "scripts" / "state" / "seen.json"
CONFIG = ROOT / "scripts" / "sources.yml"

# 로컬 실행 편의: 프로젝트 루트에 .env 가 있으면 읽는다. 이미 있는 환경변수는 덮지 않는다.
# GitHub Actions 에서는 secrets 가 환경변수로 오므로 .env 없이 그대로 동작한다.
_ENV_FILE = ROOT / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# .strip(): GitHub Secret 에 붙여넣을 때 끝에 줄바꿈이 딸려 오면 URL 에 %0A 로 실려 API 가 500 을 낸다 (2026-09-22 실제 발생)
BIZINFO_KEY = os.environ.get("BIZINFO_KEY", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_KEY", "").strip()
# 기본 모델은 사고(thinking) 토큰을 쓰지 않는 lite 계열로 둔다. 상위 flash 는 호출마다 사고 토큰 ~1000개를
# 먼저 쓰기 때문에 maxOutputTokens 에 잘리거나 비용이 몇 배가 된다. gemini-2.5-flash 는 신규 키에 막혀 404.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
GEMINI_HEADERS = {"x-goog-api-key": GEMINI_KEY}  # 키는 URL 이 아니라 헤더로 — 오류 로그에 URL 이 찍혀도 키가 안 샌다


def redact(e: object) -> str:
    """예외 문자열에서 API 키를 지운다. requests 오류 메시지에는 요청 URL 이 통째로 들어간다."""
    return re.sub(r"AQ\.[\w\-]+|AIza[\w\-]+|key=[^&\s]+", "***", str(e), flags=re.I)
DRY_RUN = "--dry-run" in sys.argv
FAILURES: list[str] = []  # 소스·요약 실패 사유. 실행 끝에 요약으로 출력하고 Actions 결과 화면에도 띄운다
UA = {"User-Agent": "dalgubul-ai-note/0.1 (+personal blog collector)"}


# ---------------------------------------------------------------- 유틸
def load_state() -> set[str]:
    if STATE.exists():
        return set(json.loads(STATE.read_text(encoding="utf-8")))
    return set()


def save_state(seen: set[str]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=0), encoding="utf-8")


def key_of(url: str, title: str) -> str:
    return hashlib.sha1(f"{url}|{title}".encode()).hexdigest()[:16]


def slugify(title: str, k: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", title).strip("-")[:40]
    return f"{s}-{k[:6]}" if s else k


def matches(text: str, keywords: list[str]) -> bool:
    return any(kw.lower() in text.lower() for kw in keywords)


def yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # 따옴표·콜론 안전


# ---------------------------------------------------------------- 소스 1: 기업마당
# 기업마당이 hashtags 에 붙이는 지역 태그. 전국 공고에는 이 16개가 전부 붙고, 지역 한정 공고에는 해당 지역만 붙는다.
BIZINFO_REGIONS = ["서울", "부산", "대구", "인천", "전남광주", "대전", "울산", "세종",
                   "경기", "강원", "충북", "충남", "전북", "경북", "경남", "제주"]


def fetch_bizinfo(cfg: dict) -> list[dict]:
    """기업마당 지원사업정보 API (인증키는 기업마당에서 직접 발급).
    중앙부처·지자체·유관기관 지원사업 공고를 한 창구로 모아 준다.
    명세: https://www.bizinfo.go.kr/apiList.do
    응답 필드명은 버전에 따라 다를 수 있어 .get 으로 방어한다."""
    if not BIZINFO_KEY:
        print("[bizinfo] BIZINFO_KEY 없음 — 건너뜀")
        return []
    url = cfg.get("endpoint", "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do")
    params = {"crtfcKey": BIZINFO_KEY, "dataType": "json", "searchCnt": cfg.get("count", 100)}
    try:
        r = requests.get(url, params=params, headers=UA, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[bizinfo] 실패: {e}")
        FAILURES.append(f"기업마당 API 호출 실패: {str(e)[:200]}")
        return []
    items = data.get("jsonArray") or data.get("items") or []
    out = []
    for it in items:
        title = it.get("pblancNm", "").strip()
        link = it.get("pblancUrl", "")
        if link and link.startswith("/"):
            link = "https://www.bizinfo.go.kr" + link
        # 1차: 지역 태그. region(기본 대구)이 없으면 타 지역 전용 공고라 버린다.
        #      전국 공고는 16개 지역이 전부 붙어 있으므로 태그 수로 '대구 한정'과 '전국'을 가른다.
        regions = [r for r in BIZINFO_REGIONS if r in str(it.get("hashtags", ""))]
        if cfg.get("region", "대구") not in regions:
            continue
        local = len(regions) < len(BIZINFO_REGIONS) - 2
        # 2차(선택): keywords 가 비어 있으면 대구 한정·전국 공고를 전부 받는다(기본).
        #           keywords 를 채우면 전국 공고만 그 산업 키워드로 한 번 더 거른다. 대구 한정은 항상 전부.
        if cfg.get("keywords") and not local:
            hay = " ".join(str(it.get(f, "")) for f in ("pblancNm", "jrsdInsttNm", "excInsttNm", "hashtags", "bsnsSumryCn", "trgetNm"))
            if not matches(hay, cfg["keywords"]):
                continue
        # 실제 응답 필드는 reqstBeginEndDe("2026-09-21 ~ 2026-10-09" 또는 "예산 소진시까지").
        # 명세 문서(apiList.do)는 reqstDt 라 적혀 있어 둘 다 본다
        period = it.get("reqstBeginEndDe") or it.get("reqstDt") or ""
        deadline = None
        m = re.findall(r"(\d{4})[-.](\d{2})[-.](\d{2})", period) or [(d[:4], d[4:6], d[6:]) for d in re.findall(r"(\d{8})", period)]
        if m:
            y, mo, d = m[-1]
            deadline = f"{y}-{mo}-{d}"
        summary_html = it.get("bsnsSumryCn", "") or ""
        summary_txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;", " ", summary_html)).strip()
        out.append({
            "category": "grants",
            "title": title,
            "url": link,
            "source": it.get("jrsdInsttNm") or it.get("excInsttNm") or "기업마당",
            "ministry": it.get("jrsdInsttNm", ""),   # 예산 대조 때 부처 필터로 쓴다
            "deadline": deadline,
            "local": local,
            "raw": f"사업명: {title}\n공고범위: {'대구 한정' if local else '전국'}\n소관기관: {it.get('jrsdInsttNm','')}\n수행기관: {it.get('excInsttNm','')}\n"
                   f"신청기간: {period}\n지원대상: {it.get('trgetNm','')}\n분야: {it.get('pldirSportRealmLclasCodeNm','')}\n"
                   f"세부분야: {it.get('pldirSportRealmMlsfcCodeNm','')}\n접수방법: {it.get('reqstMthPapersCn','')}\n"
                   f"문의처: {it.get('refrncNm','')}\n해시태그: {it.get('hashtags','')}\n요약: {summary_txt[:2500]}",
        })
    out.sort(key=lambda x: not x["local"])  # 대구 한정 공고를 앞에
    n_local = sum(1 for x in out if x["local"])
    print(f"[bizinfo] {len(items)}건 중 {len(out)}건 선별 (대구 한정 {n_local} + 전국 {len(out) - n_local})")
    return out


# ---------------------------------------------------------------- 소스 2: RSS (정책브리핑·부처)
def fetch_rss(feed: dict) -> list[dict]:
    try:
        parsed = feedparser.parse(feed["url"], request_headers=UA)
    except Exception as e:  # noqa: BLE001
        print(f"[rss:{feed['name']}] 실패: {e}")
        return []
    out = []
    for e in parsed.entries[: feed.get("limit", 40)]:
        title = getattr(e, "title", "").strip()
        link = getattr(e, "link", "")
        desc = re.sub(r"<[^>]+>", " ", getattr(e, "summary", "") or "")
        hay = f"{title} {desc}"
        if not matches(hay, feed["keywords"]):
            continue
        out.append({
            "category": feed["category"],
            "title": title,
            "url": link,
            "source": feed["name"],
            "deadline": None,
            "raw": f"제목: {title}\n발표기관: {feed['name']}\n본문 요약: {desc[:3000]}",
        })
    print(f"[rss:{feed['name']}] {len(parsed.entries)}건 중 {len(out)}건 선별")
    return out


def fetch_article_text(url: str) -> str:
    """원문 본문을 가능한 범위에서 가져온다(실패해도 RSS 요약으로 진행)."""
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text[:8000]
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------- 소스 3: RSS 없는 게시판 (대구시·달성군·대구TP 등)
def fetch_board(b: dict) -> list[dict]:
    """게시판 목록 페이지에서 제목 링크를 뽑는다.
    sources.yml 의 item_selector(CSS)로 링크 요소를 고르고, 없으면 href 에 link_pattern 이 들어간 <a> 전체를 본다."""
    try:
        r = requests.get(b["url"], headers=UA, timeout=30)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:  # noqa: BLE001
        print(f"[board:{b['name']}] 실패: {e}")
        return []
    if b.get("item_selector"):
        anchors = soup.select(b["item_selector"])
    else:
        pat = b.get("link_pattern", "")
        anchors = [a for a in soup.find_all("a", href=True) if pat in a["href"] and len(a.get_text(strip=True)) >= 8]
    out, seen_local = [], set()
    for a in anchors[: b.get("limit", 40)]:
        title = a.get_text(" ", strip=True)
        href = a.get("href", "")
        if not title or not href or href.startswith("javascript"):
            continue
        link = urljoin(b["url"], href)
        if link in seen_local:
            continue
        seen_local.add(link)
        if b.get("keywords") and not matches(title, b["keywords"]):
            continue
        out.append({
            "category": b["category"],
            "title": title,
            "url": link,
            "source": b["name"],
            "deadline": None,
            "raw": f"제목: {title}\n발표기관: {b['name']}\n(본문은 원문 페이지에서 가져옴)",
        })
    print(f"[board:{b['name']}] 링크 {len(anchors)}개 중 {len(out)}건 선별")
    return out


# ---------------------------------------------------------------- 소스 4: 외부 크롤러 결과 받기 (scripts/inbox/*.json)
INBOX = ROOT / "scripts" / "inbox"

def fetch_inbox() -> list[dict]:
    """Claude Code 웹 크롤러 에이전트 등이 떨어뜨린 JSON을 읽는다.
    형식: [{"title","url","source","category","body"?,"deadline"?}, ...]  처리한 파일은 inbox/done/ 으로 이동."""
    if not INBOX.exists():
        return []
    out = []
    done = INBOX / "done"; done.mkdir(exist_ok=True)
    for f in sorted(INBOX.glob("*.json")):
        try:
            rows = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(rows, dict):
                rows = rows.get("items", [])
            for r in rows:
                if not r.get("title") or not r.get("url"):
                    continue
                cat = r.get("category", "economy")
                if cat not in PROMPTS:
                    cat = "policy"
                out.append({
                    "category": cat,
                    "title": r["title"].strip(),
                    "url": r["url"],
                    "source": r.get("source", f.stem),
                    "deadline": r.get("deadline"),
                    "raw": f"제목: {r['title']}\n발표기관: {r.get('source','')}\n본문: {str(r.get('body',''))[:6000]}",
                })
            if not DRY_RUN:
                f.rename(done / f.name)
        except Exception as e:  # noqa: BLE001
            print(f"[inbox:{f.name}] 읽기 실패: {e}")
    print(f"[inbox] {len(out)}건")
    return out


# ---------------------------------------------------------------- Gemini
PROMPTS = {
    "grants": """다음 지원사업 공고를 대구·달성 지역 소상공인과 기업 지원 담당 공무원이 바로 판단할 수 있게 정리하라.
형식은 Markdown, 아래 항목을 표로 먼저 쓰고 그 아래 3~4문장으로 '누가 노려볼 만한가'를 적는다.
표 항목: 지원대상 / 지원규모 / 신청기간 / 신청방법·창구 / 대구 기업 해당 여부
규칙: 원문에 없는 수치·날짜를 만들지 말 것. 불명확하면 '원문 확인 필요'라고 쓸 것. 과장·홍보 문구 금지. 존댓말 대신 개조식·평서문.""",
    "economy": """다음 보도자료를 대구 경제 관점에서 정리하라. Markdown 형식.
1) 핵심 3줄 요약(각 한 문장)  2) 대구·달성 기업에 미치는 영향 또는 연결되는 지원사업(2~3문장)  3) 확인해야 할 후속 일정이 있으면 한 줄.
규칙: 원문에 없는 수치·날짜를 만들지 말 것. 원문 문장을 그대로 옮기지 말고 완전히 다시 쓸 것. 정책에 대한 평가·비판은 하지 말 것.""",
    "policy": """다음 자료를 대구 기업에 영향을 주는 산업 정책·예산·규제 변화 관점에서 정리하라. Markdown 형식.
1) 핵심 3줄 요약  2) 대구 기업·산단에 미치는 영향 또는 연결되는 지원사업(2~3문장)  3) 시행·공고·마감 등 후속 일정이 있으면 한 줄.
규칙: 원문에 없는 수치·날짜를 만들지 말 것. 원문 문장을 그대로 옮기지 말 것. 정책 평가·비판은 하지 말 것.""",
}

# 출처별 프롬프트 재정의. 자료가 얇은 소스(DART 공시 목록)는 일반 economy 프롬프트의 '영향' 항목이 추측을 부르므로
# 사실만 쓰는 전용 프롬프트를 쓴다. 키는 항목의 source 값과 정확히 같아야 한다.
PROMPT_BY_SOURCE = {
    "금융감독원 전자공시(DART)": """다음은 금융감독원 전자공시(DART)의 공시 '목록' 정보다. 공시 본문이 아니라 제목·회사·접수일·원문 링크뿐이다.
이 자료에 있는 사실만으로 짧게 정리하라. Markdown 형식.
1) 공시 사실(개조식 3줄 이내): 회사명·시장 구분·본사 소재지(자료에 적힌 대로)·공시 종류·접수일
2) 원문에서 확인할 항목(개조식): 금액·규모·일정·상대방 등 이 자료에 없는 것을 '원문 확인 필요' 항목으로 나열
3) 기업 사전 링크가 자료에 있으면 한 줄로 안내
금지: 회사의 업종·규모·평판 등 자료에 없는 설명, 영향·전망·기대·권고("~할 수 있다", "~할 필요가 있다", "긍정적", "도움") 문장,
정책·기업에 대한 평가. 자료에 없는 수치·날짜를 만들지 말 것. 존댓말 대신 개조식·평서문.""",
}


def gemini(prompt: str, text: str) -> tuple[str, str] | None:
    """(요약 한 줄, 본문 Markdown) 반환. 키가 없으면 원문 일부로 대체.
    API 호출이 끝내 실패하면 None — 호출한 쪽이 글을 저장하지 않고 seen 에도 넣지 않아 다음 실행에 다시 시도한다."""
    if not GEMINI_KEY:
        return ("(요약 생성 안 됨 — GEMINI_KEY 필요)", text[:1500])
    body = {
        "contents": [{"parts": [{"text": f"{prompt}\n\n마지막 줄에 'SUMMARY: ' 뒤에 60자 이내 한 줄 요약을 따로 써라.\n\n[자료]\n{text}"}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1500},
    }
    for attempt in range(3):
        try:
            r = requests.post(GEMINI_URL, json=body, headers=GEMINI_HEADERS, timeout=60)
            r.raise_for_status()
            out = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            m = re.search(r"SUMMARY:\s*(.+)$", out, flags=re.M)
            summary = m.group(1).strip() if m else out.splitlines()[0][:60]
            md = re.sub(r"\n?SUMMARY:.*$", "", out, flags=re.M).strip()
            return (summary, md)
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            print(f"[gemini] {attempt+1}차 실패: HTTP {code} {redact(e)}")
            if code in (400, 401, 403, 404):  # 키·모델·요청 형식 문제는 다시 보내도 같다
                FAILURES.append(f"Gemini HTTP {code}: {redact(e)[:200]}")
                break
            time.sleep(3 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            print(f"[gemini] {attempt+1}차 실패: {redact(e)}")
            time.sleep(3 * (attempt + 1))
    FAILURES.append(f"Gemini 요약 실패(3회): {redact(e)[:200]}")
    return None


def seo_meta(title: str, summary: str, md: str, category: str) -> dict:
    """검색용 제목·메타 설명·태그 5개. 실패하면 빈 dict (글 저장은 계속)."""
    if not GEMINI_KEY:
        return {}
    prompt = (
        "아래 블로그 글의 검색·AI답변 최적화 정보를 JSON 하나로만 출력하라. 다른 문장 금지.\n"
        '형식: {"seoTitle": "...", "description": "...", "tags": ["...","...","...","...","..."], '
        '"faq": [{"q": "...", "a": "..."}, {"q": "...", "a": "..."}, {"q": "...", "a": "..."}]}\n'
        "규칙: seoTitle 은 40자 이내, 대구/달성 같은 지역어와 핵심어를 앞에 둘 것. "
        "description 은 90~120자의 '핵심 문장' — 결론을 먼저, 수식어 없이 기관명·수치·기간 같은 사실로 쓸 것. "
        "tags 는 5개, 짧은 명사구. faq 는 독자가 AI에게 물을 법한 질문 3개와 본문 근거만으로 쓴 답(각 답 1~2문장, 두괄식). "
        "본문에 없는 사실은 답에 넣지 말고 '원문 확인 필요'라고 쓸 것.\n\n"
        f"[분류] {category}\n[제목] {title}\n[요약] {summary}\n[본문]\n{md[:2500]}"
    )
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700, "responseMimeType": "application/json"}}
    try:
        r = requests.post(GEMINI_URL, json=body, headers=GEMINI_HEADERS, timeout=40)
        r.raise_for_status()
        out = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        out = re.sub(r"^```(json)?|```$", "", out.strip(), flags=re.M).strip()
        d = json.loads(out)
        tags = [str(t).strip() for t in d.get("tags", [])][:5]
        faq = [{"q": str(x.get("q","")).strip(), "a": str(x.get("a","")).strip()} for x in d.get("faq", []) if x.get("q") and x.get("a")][:3]
        return {"seoTitle": str(d.get("seoTitle", ""))[:60], "description": str(d.get("description", ""))[:160], "tags": tags, "faq": faq}
    except Exception as e:  # noqa: BLE001
        print(f"[seo] 실패(건너뜀): {redact(e)}")
        return {}


# ---------------------------------------------------------------- 저장
def write_post(item: dict, summary: str, md: str, k: str, seo: dict | None = None, program: dict | None = None) -> Path:
    today = date.today().isoformat()
    slug = slugify(item["title"], k)
    path = POSTS / f"{today}-{slug}.md"
    fm = [
        "---",
        f"title: {yaml_str(item['title'])}",
        f"date: {today}",
        f"category: {item['category']}",
        f"summary: {yaml_str(summary)}",
        f"source: {yaml_str(item['source'])}",
    ]
    if item.get("url"):
        fm.append(f"sourceUrl: {yaml_str(item['url'])}")
    if item.get("deadline"):
        fm.append(f"deadline: {item['deadline']}")
    seo = seo or {}
    if seo.get("seoTitle"):
        fm.append(f"seoTitle: {yaml_str(seo['seoTitle'])}")
    if seo.get("description"):
        fm.append(f"description: {yaml_str(seo['description'])}")
    if seo.get("tags"):
        fm.append("tags: [" + ", ".join(yaml_str(t) for t in seo["tags"]) + "]")
    if seo.get("faq"):
        fm.append("faq:")
        for x in seo["faq"]:
            fm.append(f"  - q: {yaml_str(x['q'])}")
            fm.append(f"    a: {yaml_str(x['a'])}")
    if program:  # 예산 원천(자동 대조). 글 페이지의 BudgetSource 상자와 /programs/ 의 '공고 중' 배지가 이 값을 쓴다
        fm += [
            f"program_code: {yaml_str(program['code'])}",
            f"program_name: {yaml_str(program['name'])}",
            f"program_ministry: {yaml_str(program['ministry'])}",
            f"program_budget_2026: {yaml_str(program['budget_2026'])}",
            f"program_score: {program['score']}",
        ]
    fm += ["draft: true", "auto: true", "---", ""]
    path.write_text("\n".join(fm) + md + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------- 공고 → 데이터 (data/notices/notices.csv)
NOTICES = ROOT / "data" / "notices" / "notices.csv"
NOTICE_COLS = ["collected", "title", "source", "ministry", "scope", "deadline", "url", "areas",
               "program_code", "program_name", "program_ministry", "program_budget_2026", "program_score"]
_area_pats: list[tuple[str, "re.Pattern"]] | None = None


def notice_areas(text: str) -> str:
    """공약 분야 키워드(config/pledge_areas.yml)에 걸리는 분야 key 를 ';' 로. 리포트가 분야별 공고 동향을 세는 데 쓴다."""
    global _area_pats
    if _area_pats is None:
        _area_pats = []
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from report_context import cfg as pledge_cfg, kw_pattern
            _area_pats = [(a["key"], kw_pattern(a.get("keywords", []))) for a in pledge_cfg()["areas"] if a.get("keywords")]
        except Exception as e:  # noqa: BLE001
            print(f"[notices] 분야 키워드 로드 실패(분야 없이 기록): {e}")
    return ";".join(k for k, pat in _area_pats if pat.search(text))


def record_notice(item: dict, program: dict | None) -> None:
    """공고 한 건을 사실만(제목·기관·마감·링크·예산 대조) CSV 에 덧붙인다. 원문 요약·재작성 없음."""
    import csv
    NOTICES.parent.mkdir(parents=True, exist_ok=True)
    new_file = not NOTICES.exists()
    scope = "대구 한정" if item.get("local") or item["title"].startswith("[대구]") else "전국"
    row = {"collected": date.today().isoformat(), "title": item["title"], "source": item.get("source", ""), "ministry": item.get("ministry", ""),
           "scope": scope, "deadline": item.get("deadline") or "", "url": item.get("url", ""),
           "areas": notice_areas(item["title"] + " " + item.get("raw", "")[:600]),
           "program_code": (program or {}).get("code", ""), "program_name": (program or {}).get("name", ""),
           "program_ministry": (program or {}).get("ministry", ""), "program_budget_2026": (program or {}).get("budget_2026", ""),
           "program_score": (program or {}).get("score", "")}
    with open(NOTICES, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=NOTICE_COLS)
        if new_file:
            w.writeheader()
        w.writerow(row)


# ---------------------------------------------------------------- 메인
def company_keywords() -> list[str]:
    """scripts/data/dalseong_companies.csv 의 기업명을 대구 경제 키워드에 자동 추가."""
    f = ROOT / "scripts" / "data" / "dalseong_companies.csv"
    if not f.exists():
        return []
    import csv
    names = []
    with f.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            n = (row.get("name") or "").strip()
            n = re.sub(r"^\(주\)|^주식회사\s*|\(주\)$|^㈜|^\(유\)|^\(사\)|^\(재\)", "", n).strip()
            if len(n) >= 3 and not n.startswith("(예시)"):
                names.append(n)
    return sorted(set(names))


def main() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    extra = company_keywords()
    if extra:
        for feed in cfg.get("rss", []) + cfg.get("boards", []):
            if feed.get("category") == "economy":
                feed["keywords"] = list(feed.get("keywords", [])) + extra
        print(f"[data] 기업명 키워드 {len(extra)}개 추가")
    seen = load_state()
    items: list[dict] = []
    items += fetch_bizinfo(cfg["bizinfo"])
    for feed in cfg.get("rss", []):
        items += fetch_rss(feed)
    for b in cfg.get("boards", []):
        items += fetch_board(b)
    items += fetch_inbox()

    new = []
    for it in items:
        k = key_of(it["url"], it["title"])
        if k in seen:
            continue
        it["_key"] = k
        new.append(it)
    print(f"신규 {len(new)}건 (전체 {len(items)}건)")
    n_new_total = len(new)  # 상한 적용 전 신규 건수 — 요약에는 이 값을 쓴다

    # 공고(grants)는 글을 만들지 않고 data/notices/notices.csv 에 사실만 기록한다 (Gemini 호출 없음, 상한 없음)
    notices = [it for it in new if it["category"] == "grants"]
    new = [it for it in new if it["category"] != "grants"]
    n_notice = 0
    for it in notices:
        pm = match_program(it["title"], it.get("ministry") or it.get("source", ""))
        if DRY_RUN:
            print("  · [dry-run 공고]", it["title"][:60], f"| 예산 대조 {pm['code']}" if pm else "")
            continue
        record_notice(it, pm)
        seen.add(it["_key"])
        n_notice += 1
    if notices:
        print(f"[notices] 공고 {n_notice}건 기록 → {NOTICES.relative_to(ROOT)}")

    limit = cfg.get("max_per_run", 8)
    if len(new) > limit:
        print(f"1회 상한 {limit}건으로 잘라냄")
        new = new[:limit]

    written = []
    skipped = 0
    for it in new:
        text = it["raw"]
        if it["category"] != "grants" and it.get("url"):
            body = fetch_article_text(it["url"])
            if len(body) > 500:
                text += "\n\n[원문 본문]\n" + body
        pm = None
        if DRY_RUN:
            print("  · [dry-run]", it["category"], it["title"])
            continue
        res = gemini(PROMPT_BY_SOURCE.get(it.get("source", ""), PROMPTS[it["category"]]), text)
        if res is None:
            skipped += 1
            print("  · 건너뜀(요약 실패, 다음 실행에 재시도):", it["title"][:50])
            continue
        summary, md = res
        seo = seo_meta(it["title"], summary, md, it["category"])
        if pm: print(f"  · 예산 대조: {pm['ministry']} {pm['name']} ({pm['code']}, 유사도 {pm['score']})")
        p = write_post(it, summary, md, it["_key"], seo, pm)
        seen.add(it["_key"])
        written.append(p)
        print("  · 저장:", p.name)
        time.sleep(1)

    if not DRY_RUN:
        save_state(seen)
    print(f"완료: 공고 기록 {n_notice}건, 초안 {len(written)}건. 승인은 `python3 scripts/approve.py`")
    report_run(len(items), n_new_total, len(new) + n_notice, len(written) + n_notice, skipped)


def report_run(n_items: int, n_new: int, n_proc: int, n_written: int, n_skipped: int) -> None:
    """실행 요약. GitHub Actions 안이면 결과 화면(Job Summary)과 주석(annotation)에도 띄운다.
    '후보는 있었는데 한 건도 못 썼다'는 상황이 초록 체크 뒤에 숨지 않게 하는 게 목적이다.
    CLAUDE.md 원칙대로 외부 API 실패로 프로세스를 죽이지는 않는다(종료코드 0 유지)."""
    lines = [f"수집 {n_items}건 · 신규 {n_new}건 · 이번 처리 {n_proc}건(상한) · 저장 {n_written}건 · 요약실패 건너뜀 {n_skipped}건"]
    if FAILURES:
        seen_msgs: list[str] = []
        for f in FAILURES:
            if f not in seen_msgs:
                seen_msgs.append(f)
        lines.append("실패 사유: " + " | ".join(seen_msgs[:5]))
    print("[요약] " + " / ".join(lines))
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    md = ["## 수집 결과", "", "| 항목 | 건수 |", "|---|---|",
          f"| 소스에서 받은 항목 | {n_items} |", f"| 그중 신규(seen 제외) | {n_new} |",
          f"| 이번 실행 처리 대상(max_per_run 상한) | {n_proc} |",
          f"| 초안 저장 | {n_written} |", f"| 요약 실패로 건너뜀 | {n_skipped} |", ""]
    if FAILURES:
        md += ["**실패 사유**", ""] + [f"- {f}" for f in dict.fromkeys(FAILURES)] + [""]
    if n_items == 0:
        md.append("> 소스에서 아무것도 받지 못했다. API 키·네트워크·IP 차단을 의심할 것.")
        print("::error title=수집 0건::소스에서 항목을 하나도 받지 못함 — 위 실패 사유 확인")
    elif n_proc > 0 and n_written == 0 and not DRY_RUN:
        md.append("> 처리 대상은 있었지만 한 건도 저장하지 못했다. 요약(Gemini) 단계 실패를 의심할 것.")
        print(f"::error title=초안 0건::처리 대상 {n_proc}건 중 0건 저장 — 요약 단계 실패 의심")
    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write(chr(10).join(md) + chr(10))


if __name__ == "__main__":
    main()
