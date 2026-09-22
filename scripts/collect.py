#!/usr/bin/env python3
"""달구벌 AI 노트 수집·초안 생성기 (1주차 버전)

흐름: 소스 수집 → 키워드 선별 → 중복 제거 → Gemini 요약 → Markdown 초안 저장
초안은 draft: true 로 저장되며, approve.py 로 승인해야 사이트에 노출된다.

필요 환경변수
  BIZINFO_KEY   기업마당 지원사업 API 인증키 (공공데이터포털)
  GEMINI_KEY    Google AI Studio API 키
  GEMINI_MODEL  (선택) 기본 gemini-2.5-flash
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

BIZINFO_KEY = os.environ.get("BIZINFO_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
DRY_RUN = "--dry-run" in sys.argv
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
        return []
    items = data.get("jsonArray") or data.get("items") or []
    out = []
    for it in items:
        title = it.get("pblancNm", "").strip()
        link = it.get("pblancUrl", "")
        if link and link.startswith("/"):
            link = "https://www.bizinfo.go.kr" + link
        hay = " ".join(str(it.get(f, "")) for f in ("pblancNm", "jrsdInsttNm", "excInsttNm", "hashtags", "bsnsSumryCn", "trgetNm"))
        if not matches(hay, cfg["keywords"]):
            continue
        # 명세상 신청기간 필드는 reqstDt("20220727 ~ 20220930"). 과거 응답의 reqstBeginEndDe 도 함께 본다
        period = it.get("reqstDt") or it.get("reqstBeginEndDe") or ""
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
            "deadline": deadline,
            "raw": f"사업명: {title}\n소관기관: {it.get('jrsdInsttNm','')}\n수행기관: {it.get('excInsttNm','')}\n"
                   f"신청기간: {period}\n지원대상: {it.get('trgetNm','')}\n분야: {it.get('pldirSportRealmLclasCodeNm','')}\n"
                   f"세부분야: {it.get('pldirSportRealmMlsfcCodeNm','')}\n접수방법: {it.get('reqstMthPapersCn','')}\n"
                   f"문의처: {it.get('refrncNm','')}\n해시태그: {it.get('hashtags','')}\n요약: {summary_txt[:2500]}",
        })
    print(f"[bizinfo] {len(items)}건 중 {len(out)}건 선별")
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


def gemini(prompt: str, text: str) -> tuple[str, str]:
    """(요약 한 줄, 본문 Markdown) 반환. 키가 없으면 원문 일부로 대체."""
    if not GEMINI_KEY:
        return ("(요약 생성 안 됨 — GEMINI_KEY 필요)", text[:1500])
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    body = {
        "contents": [{"parts": [{"text": f"{prompt}\n\n마지막 줄에 'SUMMARY: ' 뒤에 60자 이내 한 줄 요약을 따로 써라.\n\n[자료]\n{text}"}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1500},
    }
    for attempt in range(3):
        try:
            r = requests.post(url, json=body, timeout=60)
            r.raise_for_status()
            out = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            m = re.search(r"SUMMARY:\s*(.+)$", out, flags=re.M)
            summary = m.group(1).strip() if m else out.splitlines()[0][:60]
            md = re.sub(r"\n?SUMMARY:.*$", "", out, flags=re.M).strip()
            return (summary, md)
        except Exception as e:  # noqa: BLE001
            print(f"[gemini] {attempt+1}차 실패: {e}")
            time.sleep(3 * (attempt + 1))
    return ("(요약 실패)", text[:1500])


def seo_meta(title: str, summary: str, md: str, category: str) -> dict:
    """검색용 제목·메타 설명·태그 5개. 실패하면 빈 dict (글 저장은 계속)."""
    if not GEMINI_KEY:
        return {}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
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
        r = requests.post(url, json=body, timeout=40)
        r.raise_for_status()
        out = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        out = re.sub(r"^```(json)?|```$", "", out.strip(), flags=re.M).strip()
        d = json.loads(out)
        tags = [str(t).strip() for t in d.get("tags", [])][:5]
        faq = [{"q": str(x.get("q","")).strip(), "a": str(x.get("a","")).strip()} for x in d.get("faq", []) if x.get("q") and x.get("a")][:3]
        return {"seoTitle": str(d.get("seoTitle", ""))[:60], "description": str(d.get("description", ""))[:160], "tags": tags, "faq": faq}
    except Exception as e:  # noqa: BLE001
        print(f"[seo] 실패(건너뜀): {e}")
        return {}


# ---------------------------------------------------------------- 저장
def write_post(item: dict, summary: str, md: str, k: str, seo: dict | None = None) -> Path:
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
    fm += ["draft: true", "auto: true", "---", ""]
    path.write_text("\n".join(fm) + md + "\n", encoding="utf-8")
    return path


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
    limit = cfg.get("max_per_run", 8)
    if len(new) > limit:
        print(f"1회 상한 {limit}건으로 잘라냄")
        new = new[:limit]

    written = []
    for it in new:
        text = it["raw"]
        if it["category"] != "grants" and it.get("url"):
            body = fetch_article_text(it["url"])
            if len(body) > 500:
                text += "\n\n[원문 본문]\n" + body
        if DRY_RUN:
            print("  · [dry-run]", it["category"], it["title"])
            continue
        summary, md = gemini(PROMPTS[it["category"]], text)
        seo = seo_meta(it["title"], summary, md, it["category"])
        p = write_post(it, summary, md, it["_key"], seo)
        seen.add(it["_key"])
        written.append(p)
        print("  · 저장:", p.name)
        time.sleep(1)

    if not DRY_RUN:
        save_state(seen)
    print(f"완료: 초안 {len(written)}건. 승인은 `python3 scripts/approve.py`")


if __name__ == "__main__":
    main()
