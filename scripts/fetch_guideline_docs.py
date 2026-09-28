#!/usr/bin/env python3
"""기관 관리지침 수집기 — config/guideline_docs.yml 의 대구 기업지원기관 공고·규정 게시판에서 사업 관리지침·운영지침·사업비 집행(정산) 지침 첨부를
받아 본문 글자를 data/guidelines/docs/<org>/<파일>.txt.gz 로 남기고, data/guidelines/index.json 에 'doc-<org>-<번호>' 항목으로 넣는다
(법령정보센터 지침 fetch_guidelines.py 와 같은 창고, 같은 페이지 /programs/guidelines/ 에 '기관 관리지침(홈페이지 첨부)' 묶음으로 보인다).

운영자 지시 2026-09-28 「대구시 기업지원기관 홈페이지 공고문에 들어가 관리지침을 다 반영」. 사업 지침 검토(예산요구서·집행·결산서)의 근거이므로
지침 내용을 평가하지 않고 본문을 그대로 둔다. 공공기관 공개 게시판만, robots.txt 존중, 하루 1회, 기관당 max_posts_per_org 글·max_files_per_org 파일.
이 세션 환경은 기관 사이트가 막혀 있어 GitHub Actions(.github/workflows/guideline_docs.yml, Playwright)가 대신 돈다. 실패는 로그만.

사용: python3 scripts/fetch_guideline_docs.py [--only riia,ttp] [--dry-run]
      python3 scripts/fetch_guideline_docs.py --list          # 받아 둔 문서 목록
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_budget_docs import download, kind_of, links_of, render, safe, to_text, years_in  # noqa: E402
from scrape_institution_boards import UA, _goto, browser, robots_ok, text_of  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "guideline_docs.yml"
RAW = ROOT / "data" / "raw" / "guideline_docs"
OUT = ROOT / "data" / "guidelines" / "docs"
INDEX = ROOT / "data" / "guidelines" / "index.json"
TODAY = date.today().isoformat()
POST_HREF = re.compile(r"view|read|detail|nttId|boardRead|articleView|seq=|idx=|no=|wr_id|contentsView|BoardView|getBoard|/board/[^/]+/view", re.I)
FILE_HINT = re.compile(r"fileDown|FileDown|download|atchFile|fileSn|attach|\.(pdf|hwpx?|zip)(\?|$)", re.I)
DATE_RE = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")


def load_index() -> dict:
    if INDEX.exists():
        return json.loads(INDEX.read_text(encoding="utf-8"))
    return {"fetched": "", "items": {}}


def open_post(list_url: str, label: str, href: str) -> tuple[str, str]:
    """글을 연다: 주소가 있으면 렌더링, 자바스크립트 링크면 목록에서 제목을 눌러 연다."""
    if href.startswith("http"):
        return render(href)
    b = browser()
    if not b:
        return "", ""
    page = b.new_page(user_agent=UA, locale="ko-KR")
    try:
        if not _goto(page, list_url):
            return "", ""
        loc = page.get_by_text(label[:40], exact=False).first
        try:
            with page.expect_navigation(timeout=15000):
                loc.click(timeout=8000)
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(2500)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:  # noqa: BLE001
            pass
        return page.content(), page.url
    except Exception as e:  # noqa: BLE001
        print(f"    [browser] 글 열기 실패 {label[:30]}: {str(e)[:60]}")
        return "", ""
    finally:
        page.close()


def click_attachment(post_url: str, label: str) -> tuple[str, bytes] | None:
    """글 페이지에서 첨부 글자를 눌러 내려받기를 기다린다(자바스크립트 첨부)."""
    b = browser()
    if not b:
        return None
    page = b.new_page(user_agent=UA, locale="ko-KR", accept_downloads=True)
    try:
        if not _goto(page, post_url):
            return None
        with page.expect_download(timeout=120000) as dl:
            page.get_by_text(label[:50], exact=False).first.click(timeout=8000)
        f = dl.value
        return (f.suggested_filename or label, Path(f.path()).read_bytes())
    except Exception as e:  # noqa: BLE001
        print(f"    첨부 클릭 실패 {label[:40]}: {str(e)[:60]}")
        return None
    finally:
        page.close()


def list_posts(html: str, base: str, post_re: re.Pattern, link_re: re.Pattern, excl_re: re.Pattern) -> tuple[list[tuple[str, str]], list[str]]:
    """목록 페이지에서 (제목, 주소 또는 javascript) 와 다음 쪽 링크."""
    posts, pages, seen = [], [], set()
    for label, href, onclick in links_of(html, base):
        t = label.strip()
        if len(t) < 6:
            if re.fullmatch(r"\d{1,2}", t) and href.startswith("http") and href not in pages:
                pages.append(href)
            continue
        if not (post_re.search(t) or link_re.search(t)) or excl_re.search(t):
            continue
        if href.startswith("http") and not POST_HREF.search(href) and not POST_HREF.search(onclick):
            continue
        k = t + "|" + href
        if k in seen:
            continue
        seen.add(k)
        posts.append((t, href if href.startswith("http") else ""))
    return posts, pages


def attachments_of(html: str, base: str, link_re: re.Pattern, excl_re: re.Pattern, ext_re: re.Pattern, title_hit: bool) -> list[tuple[str, str]]:
    out, seen = [], set()
    for label, href, onclick in links_of(html, base):
        t = label.strip()
        is_file = bool(ext_re.search(href)) or bool(FILE_HINT.search(href + " " + onclick)) or bool(re.search(r"\.(pdf|hwpx?|zip)\s*$", t, re.I))
        if not is_file:
            continue
        if excl_re.search(t):
            continue
        if not (title_hit or link_re.search(t)):
            continue
        k = (t, href)
        if k in seen:
            continue
        seen.add(k)
        out.append((t, href if href.startswith("http") else ""))
    return out


def eff_of(name: str, text: str) -> str:
    """시행일 추정: 파일 이름의 (YYYYMMDD) 또는 본문 앞부분의 '시행 2025. 4. 4.' 꼴. 없으면 ''."""
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", name)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    head = text[:4000]
    m = re.search(r"시행\s*[:：]?\s*(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})", head) or DATE_RE.search(head)
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"
    return ""


def crawl(org: dict, cfg: dict, sess: requests.Session, robots: dict, idx: dict, dry: bool) -> list[dict]:
    key = org["key"]
    link_re, post_re, excl_re = re.compile(cfg["link_pattern"]), re.compile(cfg["post_pattern"]), re.compile(cfg["exclude_pattern"])
    ext_re = re.compile(rf"\.({cfg['file_ext']})(\?|$)", re.I)
    home_re = re.compile(org["home_pattern"]) if org.get("home_pattern") else None
    min_year = int(cfg.get("min_year") or 0)
    raw_dir, out_dir = RAW / key, OUT / key
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    got, hashes, opened, files = [], set(), 0, 0
    existing = {v.get("sha") for v in idx["items"].values() if v.get("sha")}
    boards = list(org["seeds"])
    print(f"\n== {org['name']}")
    seen_boards: set[str] = set()
    while boards and opened < cfg["max_posts_per_org"] and files < cfg["max_files_per_org"]:
        board = boards.pop(0)
        if board in seen_boards or len(seen_boards) > 12:
            continue
        seen_boards.add(board)
        if not robots_ok(board, robots):
            print(f"  robots 차단: {board}")
            continue
        html, final = render(board)
        if not html:
            continue
        host = urlparse(final).netloc
        posts, pages = list_posts(html, final, post_re, link_re, excl_re)
        # 첫 화면(seed 가 홈)이면 게시판 링크를 찾아 들어간다
        if not posts and home_re:
            for label, href, _ in links_of(html, final):
                if href.startswith("http") and urlparse(href).netloc == host and home_re.search(label) and href not in seen_boards:
                    boards.append(href)
        print(f"  {board[:90]} → 글 후보 {len(posts)}개, 쪽 {len(pages)}개")
        if len(posts) <= 2:   # 단서가 적으면 링크 표본을 남겨 설정(post_pattern·seeds)을 고칠 수 있게
            sample = [(l[:30], h[-55:], oc[:40]) for l, h, oc in links_of(html, final) if len(l.strip()) >= 6][:25]
            print(f"    링크 표본 {len(sample)}: {sample}")
        for p in pages[: max(0, cfg["max_pages_per_board"] - 1)]:
            if p not in seen_boards:
                boards.insert(0, p)
        for title, href in posts:
            if opened >= cfg["max_posts_per_org"] or files >= cfg["max_files_per_org"]:
                break
            if min_year and years_in(title) and max(years_in(title)) < min_year:
                continue
            opened += 1
            phtml, purl = open_post(final, title, href)
            if not phtml:
                continue
            title_hit = bool(link_re.search(title))
            atts = attachments_of(phtml, purl, link_re, excl_re, ext_re, title_hit)
            if not atts:
                files_seen = [(l[:40], h[-50:]) for l, h, oc in links_of(phtml, purl) if ext_re.search(h) or FILE_HINT.search(h + " " + oc) or re.search(r"\.(pdf|hwpx?|zip)\s*$", l, re.I)][:8]
                if files_seen:
                    print(f"  글 '{title[:40]}' 첨부 {len(files_seen)}개 있으나 지침 이름 아님: {files_seen[:4]}")
                continue
            print(f"  글 '{title[:50]}' → 첨부 후보 {len(atts)}개")
            for label, ahref in atts[:8]:
                if files >= cfg["max_files_per_org"]:
                    break
                if min_year and years_in(label) and max(years_in(label)) < min_year:
                    print(f"    옛 자료 건너뜀: {label[:50]}")
                    continue
                if ahref and not robots_ok(ahref, robots):
                    continue
                if dry:
                    print(f"    (dry) {label[:60]} {ahref[:60]}")
                    continue
                got_file = download(ahref, purl, sess) if ahref else click_attachment(purl, label)
                if not got_file:
                    continue
                name, data = got_file
                kind = kind_of(name, data)
                if not kind:
                    continue
                items = [(safe(name), data, kind)]
                if kind == "zip":
                    items = []
                    try:
                        with zipfile.ZipFile(io.BytesIO(data)) as z:
                            for zi in z.infolist()[:30]:
                                try:
                                    zname = zi.filename.encode("cp437").decode("cp949")
                                except Exception:  # noqa: BLE001
                                    zname = zi.filename
                                if excl_re.search(zname) or not link_re.search(zname):
                                    continue
                                zd = z.read(zi)
                                zk = kind_of(zname, zd)
                                if zk and zk != "zip":
                                    items.append((safe(Path(zname).name), zd, zk))
                    except Exception as e:  # noqa: BLE001
                        print(f"    zip 실패 {name[:40]}: {str(e)[:50]}")
                for fn, fd, fk in items:
                    sha = hashlib.sha256(fd).hexdigest()[:16]
                    if sha in hashes or sha in existing:
                        print(f"    같은 내용 건너뜀: {fn[:50]}")
                        continue
                    hashes.add(sha)
                    (raw_dir / fn).write_bytes(fd)
                    txt = to_text(fk, raw_dir / fn)
                    if txt.startswith("(본문 추출 실패"):
                        print(f"    {txt[:100]}: {fn[:50]}")
                        continue
                    if len(txt.strip()) < 500:
                        print(f"    본문 없음(스캔 PDF 등, {len(txt.strip())}자): {fn[:50]}")
                        continue
                    if min_year and years_in(fn) and max(years_in(fn)) < min_year:
                        continue
                    files += 1
                    n = len([k for k in idx["items"] if k.startswith(f"doc-{key}-")]) + len([g for g in got]) + 1
                    dkey = f"doc-{key}-{n:02d}"
                    with gzip.open(out_dir / (fn + ".txt.gz"), "wt", encoding="utf-8") as gz:
                        gz.write(f"# {fn}\n# 기관: {org['name']}\n# 글: {title}\n# 출처: {purl}\n# 받은 날짜: {TODAY}\n\n{txt}")
                    entry = {"key": dkey, "name": Path(fn).stem.replace("_", " "), "kind": "기관 첨부(관리지침)", "issuer": org["name"],
                             "source": {"type": "url", "name": purl}, "applies": {"layer": "기관", "ministry": org["name"], "program_type": ["전체"]},
                             "review": ["예산요구서", "집행", "결산서"], "fetched": TODAY, "status": "OK", "found": Path(fn).stem.replace("_", " "),
                             "found_kind": f"기관 첨부({fk})", "found_issuer": org["name"], "id": sha, "sha": sha, "date": "", "eff": eff_of(fn, txt),
                             "url": purl, "chars": len(txt), "file": f"docs/{key}/{fn}.txt.gz", "post": title[:120], "attachment": label[:120],
                             "articles": len(re.findall(r"제\d+조", txt)), "annexes": []}
                    idx["items"][dkey] = entry
                    got.append(entry)
                    print(f"    받음 {fn[:60]} ({fk}, {len(fd):,} bytes, 본문 {len(txt):,}자) ← {label[:40]}")
                time.sleep(1)
            time.sleep(1)
    print(f"  → {org['name']}: 글 {opened}개 열어 문서 {len(got)}개 (data/guidelines/docs/{key}/)")
    return got


def write_docs_index(idx: dict) -> None:
    docs = {k: v for k, v in idx["items"].items() if k.startswith("doc-")}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.json").write_text(json.dumps({"fetched": TODAY, "count": len(docs), "items": docs}, ensure_ascii=False, indent=1), encoding="utf-8")
    L = ["# 기관 관리지침(홈페이지 첨부) — data/guidelines/docs", "", f"받은 날짜: {TODAY}. config/guideline_docs.yml 의 게시판에서 받은 관리지침·운영지침·사업비 지침 본문. 평가 없음.", "",
         "| key | 기관 | 문서 | 글 | 시행일(추정) | 글자 | 출처 |", "|---|---|---|---|---|---|---|"]
    for k, e in sorted(docs.items()):
        eff = e.get("eff", "")
        eff = f"{eff[:4]}-{eff[4:6]}-{eff[6:]}" if len(eff) == 8 else eff
        L.append(f"| {k} | {e.get('issuer', '')} | {e.get('name', '')} | {e.get('post', '')} | {eff} | {e.get('chars', 0):,} | {e.get('url', '')} |")
    (OUT / "README.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    idx = load_index()
    if "--list" in argv:
        for k, e in sorted(idx["items"].items()):
            if k.startswith("doc-"):
                print(f"{k} | {e.get('issuer')} | {e.get('name')} | {e.get('eff')} | {e.get('chars'):,}자 | {e.get('url')}")
        return 0
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    dry = "--dry-run" in argv
    sess = requests.Session()
    robots: dict = {}
    total = 0
    for org in cfg["organizations"]:
        if only and org["key"] not in only:
            continue
        try:
            total += len(crawl(org, cfg, sess, robots, idx, dry))
        except Exception as e:  # noqa: BLE001
            print(f"  [{org['key']}] 실패: {type(e).__name__} {str(e)[:100]}")
    if not dry:
        idx["fetched"] = TODAY
        INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
        write_docs_index(idx)
        try:
            from fetch_guidelines import write_summary  # noqa: WPS433
            write_summary(idx)
        except Exception as e:  # noqa: BLE001
            print(f"  summary.md 갱신 실패: {str(e)[:60]}")
    print(f"\n완료: 문서 {total}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
