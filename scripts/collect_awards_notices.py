#!/usr/bin/env python3
"""대구 기업지원기관 공지 가운데 '선정·결과·확정·발표·명단' 게시글을 모아 Gemini 로 선정기업을 뽑는다.
→ scripts/data/awards/awards.json (누적, URL 키), scripts/state/seen_notices.json (처리한 URL)

설정은 scripts/config/award_sources.yml 하나만 읽는다(기관·약칭·URL·상태·link_pattern/selector).
  status 가 allowed_static 인 기관만 수집한다. js(브라우저 필요)·blocked(robots 차단)·unreachable·url_pending 은 건너뛰고 요약에 적는다.

한 게시글 처리
  1) 목록: 제목에 keywords 중 하나 + 날짜가 since_days 이내 + seen 에 없는 것
  2) robots.txt: 그 호스트의 User-agent * Disallow 경로면 건너뜀(매 실행 호스트당 1회 확인)
  3) 본문 텍스트 + 첨부: PDF 는 pdftotext(있을 때), XLSX 는 zip 안의 XML 에서 문자열만. HWP/HWPX 는 읽지 않는다(권장안)
  4) Gemini 1회: {사업명, 주관기관, 연도, 선정기업[], 금액, confidence} JSON. 본문에 없는 기업명을 만들지 말 것을 명시
  5) 선정기업에서 개인 성명으로 보이는 이름은 뺀다(sources_common.looks_like_person)
하루 Gemini 상한 max_per_run. 그 뒤 후보는 다음 실행으로 넘긴다(seen 에 넣지 않음).

사용: python3 scripts/collect_awards_notices.py [--dry-run] [--limit N] [--source KIAPI]
환경: GEMINI_KEY (scripts/env.py). 없으면 후보 목록만 만들고 추출은 건너뛴다
"""
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib import robotparser

import requests
import yaml
from bs4 import BeautifulSoup

from env import get as env_get
from sources_common import looks_like_person

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "scripts" / "config" / "award_sources.yml"
OUT = ROOT / "scripts" / "data" / "awards" / "awards.json"
SEEN = ROOT / "scripts" / "state" / "seen_notices.json"
UA = {"User-Agent": "dalgubul-ai-note/0.1 (+personal blog collector)"}
DRY = "--dry-run" in sys.argv


def arg(name: str, default):
    if name in sys.argv:
        i = sys.argv.index(name)
        return type(default)(sys.argv[i + 1]) if i + 1 < len(sys.argv) else default
    return default


LIMIT = arg("--limit", 0)
SINCE_DAYS = arg("--since", 0)          # 기간(일) 재정의. 시험·소급용
INBOX = ROOT / "scripts" / "inbox"       # 주간 루틴(브라우저)이 JS 게시판에서 떨군 awards-*.json 도 같은 추출 경로를 탄다
ONLY = arg("--source", "")
GEMINI_KEY = env_get("GEMINI_KEY")
GEMINI_MODEL = env_get("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
DATE_RE = re.compile(r"(20\d\d)[.\-/년]\s?(\d{1,2})[.\-/월]\s?(\d{1,2})")
_robots: dict[str, robotparser.RobotFileParser | None] = {}
CALLS = 0


def redact(e: object) -> str:
    return re.sub(r"AQ\.[\w\-]+|AIza[\w\-]+|key=[^&\s]+", "***", str(e), flags=re.I)


def allowed(url: str) -> bool:
    host = urlparse(url).scheme + "://" + urlparse(url).netloc
    if host not in _robots:
        rp = robotparser.RobotFileParser()
        try:
            r = requests.get(host + "/robots.txt", headers=UA, timeout=15)
            rp.parse(r.text.replace("Disllow", "Disallow").splitlines() if r.status_code == 200 else [])
        except Exception:  # noqa: BLE001
            rp.parse([])
        _robots[host] = rp
    return _robots[host].can_fetch("*", url)


def parse_date(text: str) -> date | None:
    m = DATE_RE.search(text or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _page_url(base: str, param: str, n: int) -> str:
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{param}={n}"


def list_posts(src: dict, keywords: list[str], since: date) -> list[dict]:
    """목록 페이지들에서 (제목, 링크, 날짜) — 키워드·기간 필터. page_param 이 있으면 쪽을 넘기며 모은다
    (새 링크가 없거나 그 쪽의 날짜가 전부 since 이전이면 중단, 최대 max_pages)."""
    if not allowed(src["url"]):
        print(f"[awards] {src['abbr']}: robots 차단 경로 — 건너뜀")
        return []
    out, seen_local = [], set()
    n_anchors = 0
    pages = int(src.get("max_pages", 40)) if src.get("page_param") else 1
    for pg in range(1, pages + 1):
        url = _page_url(src["url"], src["page_param"], pg) if src.get("page_param") else src["url"]
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
        except Exception as e:  # noqa: BLE001
            print(f"[awards] {src['abbr']}: 목록 실패({pg}쪽) {e}")
            break
        soup = BeautifulSoup(r.text, "html.parser")
        anchors = soup.select(src["selector"]) if src.get("selector") else [a for a in soup.find_all("a", href=True) if src.get("link_pattern", "") in a["href"]]
        new_links, page_dates = 0, []
        for a in anchors:
            new_links, page_dates = _collect(a, src, keywords, since, out, seen_local, new_links, page_dates)
        n_anchors += len(anchors)
        if new_links == 0 or (page_dates and max(page_dates) < since):
            break
        time.sleep(0.5)
    print(f"[awards] {src['abbr']}: 링크 {n_anchors}개 → 키워드·기간 통과 {len(out)}건")
    return out


def _collect(a, src, keywords, since, out, seen_local, new_links, page_dates):
    if True:
        title = a.get_text(" ", strip=True)
        href = a.get("href", "")
        if not title or not href or href.startswith("javascript"):
            return new_links, page_dates
        link = urljoin(src["url"], href.replace("&amp;", "&"))
        if link in seen_local:
            return new_links, page_dates
        seen_local.add(link)
        new_links += 1
        row = a.find_parent(["tr", "li", "div"])                     # 날짜: 링크가 든 행(tr/li) 안에서 찾는다
        d = parse_date(row.get_text(" ", strip=True) if row else "") or parse_date(title)
        if d:
            page_dates.append(d)
        if not any(k in title for k in keywords):
            return new_links, page_dates
        if d and d < since:
            return new_links, page_dates
        out.append({"title": title, "url": link, "date": d.isoformat() if d else "", "org": src["name"], "abbr": src["abbr"], "field": src.get("field", "")})
    return new_links, page_dates


def body_text(url: str, cfg_att: list[str]) -> tuple[str, list[str]]:
    """본문 텍스트 + 첨부 텍스트(PDF·XLSX). 반환 (텍스트, 건너뛴 첨부 이름)."""
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer"]):
        t.decompose()
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
    skipped: list[str] = []
    parts: list[str] = []
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        name = (a.get_text(" ", strip=True) or href).lower()
        ext = next((e for e in ("pdf", "xlsx", "hwp", "hwpx") if name.endswith("." + e) or href.lower().split("?")[0].endswith("." + e)), "")
        if not ext:
            continue
        if ext not in cfg_att:
            skipped.append(name[:40])
            continue
        try:
            b = requests.get(href, headers=UA, timeout=60).content
            if ext == "pdf" and shutil.which("pdftotext"):
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
                    fh.write(b); p = fh.name
                parts.append(subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True, timeout=120).stdout)
                Path(p).unlink(missing_ok=True)
            elif ext == "xlsx":
                z = zipfile.ZipFile(io.BytesIO(b))
                strings = re.findall(r"<t[^>]*>([^<]*)</t>", z.read("xl/sharedStrings.xml").decode("utf-8", "replace")) if "xl/sharedStrings.xml" in z.namelist() else []
                parts.append("\n".join(strings))
            else:
                skipped.append(name[:40])
        except Exception as e:  # noqa: BLE001
            skipped.append(f"{name[:30]}(실패)")
    full = text + ("\n\n[첨부]\n" + "\n".join(parts) if parts else "")
    return full[:24000], skipped


PROMPT = """아래는 대구 기업지원기관의 공지 게시글(제목·본문·첨부 텍스트)이다. 선정 결과 공고라면 다음 JSON 하나만 출력하라. 다른 문장 금지.
{"program": "사업명", "org": "주관기관(본문 기준, 없으면 게시 기관)", "year": 2026, "selected": ["기업명", ...], "amount": "금액 문구(없으면 빈 문자열)", "confidence": 0.0~1.0, "is_selection_notice": true/false}
규칙: selected 에는 본문·첨부에 실제로 적힌 기업·기관 이름만 넣는다. 없는 이름을 만들지 말 것. 개인 이름(사람)은 넣지 말 것.
선정 결과가 아닌 글(모집 공고·행사 안내 등)이면 is_selection_notice 를 false 로 하고 selected 는 빈 배열로.
연도는 본문에 없으면 게시일 연도. 금액은 본문에 있는 문구 그대로."""


def extract(post: dict, text: str) -> dict | None:
    global CALLS
    body = {"contents": [{"parts": [{"text": f"{PROMPT}\n\n[기관] {post['org']}\n[게시일] {post['date']}\n[제목] {post['title']}\n[본문]\n{text}"}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1200, "responseMimeType": "application/json"}}
    try:
        CALLS += 1
        r = requests.post(GEMINI_URL, json=body, headers={"x-goog-api-key": GEMINI_KEY}, timeout=90)
        r.raise_for_status()
        out = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        d = json.loads(re.sub(r"^```(json)?|```$", "", out.strip(), flags=re.M).strip())
    except Exception as e:  # noqa: BLE001
        print(f"   추출 실패: {redact(e)[:120]}")
        return None
    sel = [str(x).strip() for x in d.get("selected", []) if str(x).strip()]
    dropped = [x for x in sel if looks_like_person(x)]
    d["selected"] = [x for x in sel if x not in dropped]
    d["dropped_person_names"] = len(dropped)
    return d


def main() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    dflt = cfg.get("defaults", {})
    keywords = dflt.get("keywords", ["선정", "결과", "확정", "발표", "명단"])
    since = date.today() - timedelta(days=int(SINCE_DAYS or dflt.get("since_days", 365)))
    max_run = LIMIT or int(dflt.get("max_per_run", 30))
    atts = [a.lower() for a in dflt.get("attachments", ["pdf", "xlsx"])]
    seen: dict = json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}
    awards: dict = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    skipped_orgs: dict[str, list[str]] = {}
    cands: list[dict] = []
    for src in cfg["sources"]:
        if ONLY and src["abbr"] != ONLY and src["name"] != ONLY:
            continue
        st = src.get("status", "url_pending")
        if st != "allowed_static":
            skipped_orgs.setdefault(st, []).append(src["abbr"])
            continue
        for p in list_posts(src, src.get("keywords", keywords), since):
            if p["url"] not in seen:
                cands.append(p)
    n_inbox = 0
    for f in sorted(INBOX.glob("awards-*.json")) if INBOX.exists() else []:
        try:
            for r in json.loads(f.read_text(encoding="utf-8")):
                if r.get("title") and r.get("url") and r["url"] not in seen and any(k in r["title"] for k in keywords):
                    cands.append({"title": r["title"], "url": r["url"], "date": r.get("date", ""), "org": r.get("org", f.stem), "abbr": r.get("abbr", r.get("org", f.stem)),
                                  "field": r.get("field", ""), "body": r.get("body", "")})
                    n_inbox += 1
        except Exception as e:  # noqa: BLE001
            print(f"[awards] inbox {f.name} 읽기 실패: {e}")
    print(f"[awards] 후보 {len(cands)}건 (기간 {since} 이후, 처리 완료 {len(seen)}건 제외" + (f", inbox {n_inbox}건 포함" if n_inbox else "") + ")")
    for st, names in skipped_orgs.items():
        print(f"[awards] 제외({st}): {', '.join(names)}")
    if DRY:
        for p in cands[:40]:
            print(f"  · [dry-run] {p['abbr']:8} {p['date'] or '----------'} {p['title'][:60]}")
        return
    if not GEMINI_KEY:
        print("[env] 비어 있는 키: GEMINI_KEY — 추출 건너뜀(후보만 셈)")
        return
    done = 0
    for p in cands:
        if done >= max_run:
            break
        try:
            text, skipped = (p["body"][:24000], []) if p.get("body") else body_text(p["url"], atts)
        except Exception as e:  # noqa: BLE001
            print(f"  · 본문 실패 {p['abbr']} {p['title'][:40]}: {e}")
            continue
        d = extract(p, text)
        done += 1
        if d is None:
            continue
        rec = {**p, "extracted": d, "skipped_attachments": skipped, "processed": date.today().isoformat()}
        awards[p["url"]] = rec
        seen[p["url"]] = date.today().isoformat()
        flag = "선정" if d.get("is_selection_notice") else "비선정"
        print(f"  · {flag} {p['abbr']:8} {p['title'][:44]} → {d.get('program','')[:30]} · 기업 {len(d.get('selected', []))}곳 · conf {d.get('confidence')}" + (f" · 첨부 건너뜀 {len(skipped)}" if skipped else ""))
        time.sleep(1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(awards, ensure_ascii=False, indent=0), encoding="utf-8")
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(seen, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    n_sel = sum(1 for v in awards.values() if v["extracted"].get("is_selection_notice"))
    n_firms = sum(len(v["extracted"].get("selected", [])) for v in awards.values())
    line = f"[요약] 후보 {len(cands)} · 이번 처리 {done}(Gemini {CALLS}회) · 누적 게시글 {len(awards)}(선정 공고 {n_sel}) · 선정기업 언급 {n_firms}건 · 남은 후보 {max(0, len(cands)-done)}"
    print(line)
    import os
    sp = os.environ.get("GITHUB_STEP_SUMMARY")
    if sp:
        with open(sp, "a", encoding="utf-8") as fh:
            fh.write("## 선정 공고 수집\n\n- " + line.replace("[요약] ", "") + "\n" + "".join(f"- 제외({st}): {', '.join(n)}\n" for st, n in skipped_orgs.items()) + "\n")


if __name__ == "__main__":
    main()
