#!/usr/bin/env python3
"""행정안전부 「감사(감찰)계획 및 결과공개」 게시판(bbsId=BBSMSTR_000000000002)의 정부합동감사 결과 PDF 를 받아 '부가가치세' 가 든 지적 항목만 발췌한다
(운영자 지시 2026-11-03 '부가세 신고 관련 감사 결과를 참고하면 되잖아'). 원문 PDF 는 저장하지 않고 발췌(data/vat/audits/<nttId>.txt)와 목록(index.json)만.

사용: python3 scripts/fetch_audit_vat.py <nttId> [<nttId> …]   (예: 126735 대구 2025)
      python3 scripts/fetch_audit_vat.py --list [--pages 4]       게시판에서 '합동감사 결과' 글 번호를 찾아 찍는다
발췌 규칙: pdftotext -layout 글자에서 '부가가치세|부가세|매입세액' 이 든 줄의 앞뒤를 묶되, 그 줄이 속한 지적 항목(직전 '제     목' 줄부터 다음 '제     목' 전까지) 전체를 한 덩어리로 둔다(최대 220줄). 목차의 짧은 줄은 따로 '목차' 로.
"""
import json, os, re, subprocess, sys, tempfile, urllib.parse, urllib.request

BOARD = "https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardList.do?bbsId=BBSMSTR_000000000002"
ART = "https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000002&nttId={id}"
OUT = "data/vat/audits"
UA = {"User-Agent": "Mozilla/5.0 (vat-daitda research; https://vat-daitda.pages.dev)"}
KW = re.compile(r"부가가치세|부가세|매입세액|세금계산서")


def get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
        return data if binary else data.decode("utf-8", "replace")


def list_posts(pages=4):
    out = []
    for p in range(1, pages + 1):
        html = get(BOARD + f"&pageIndex={p}")
        for m in re.finditer(r"nttId=(\d+)[^>]*>\s*([^<]{3,120}?)\s*<", html):
            t = re.sub(r"\s+", " ", m.group(2))
            if "감사 결과" in t or "감사결과" in t: out.append((m.group(1), t))
    seen = set(); res = []
    for i, t in out:
        if i in seen: continue
        seen.add(i); res.append((i, t)); print(i, t)
    return res


def extract(txt):
    lines = txt.split("\n")
    heads = [i for i, l in enumerate(lines) if re.match(r"^\s*제\s{2,}목\s", l)]
    blocks, toc = [], []
    used = set()
    for i, l in enumerate(lines):
        if not KW.search(l): continue
        if len(l.strip()) < 90 and re.search(r"\s(시정|주의|통보|권고|개선|징계)\s", l) and not heads or (heads and i < heads[0]):
            toc.append(l.strip()); continue
        start = max([h for h in heads if h <= i], default=max(0, i - 40))
        if start in used: continue
        used.add(start)
        end = min([h for h in heads if h > i], default=min(len(lines), i + 120))
        end = min(end, start + 220)
        blocks.append("\n".join(lines[start:end]).rstrip())
    return toc, blocks


def one(ntt):
    html = get(ART.format(id=ntt))
    title = re.search(r"<title>([^<]*)</title>", html)
    files = re.findall(r"FileDown\.do\?atchFileId=([^&\"]+)&amp;fileSn=(\d+)", html)
    names = re.findall(r"([^<>\n\t]*\.pdf)", html)
    print(f"[{ntt}] {title.group(1).strip() if title else ''} 첨부 {len(files)}개 {names[:2]}")
    os.makedirs(OUT, exist_ok=True)
    res = {"nttId": ntt, "title": (names[0].strip() if names else (title.group(1).strip() if title else "")), "url": ART.format(id=ntt), "files": [], "toc": [], "blocks": 0}
    out_txt = []
    for fid, sn in files:
        url = f"https://www.mois.go.kr/cmm/fms/FileDown.do?atchFileId={fid}&fileSn={sn}"
        data = get(url, binary=True)
        if data[:4] != b"%PDF":
            print("   PDF 아님", url[:80], data[:20]); continue
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as t:
            t.write(data); pdf = t.name
        txt = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
        os.unlink(pdf)
        toc, blocks = extract(txt)
        print(f"   {len(data):,} bytes, {txt.count(chr(10)):,}줄, 목차 {len(toc)}, 지적 블록 {len(blocks)}")
        res["files"].append({"url": url, "bytes": len(data)}); res["toc"] += toc; res["blocks"] += len(blocks)
        out_txt.append(f"##### {url}\n### 목차·요약 줄\n" + "\n".join(toc) + "\n\n### 지적 항목 발췌\n" + "\n\n----------\n\n".join(blocks))
    with open(f"{OUT}/{ntt}.txt", "w", encoding="utf-8") as f:
        f.write(f"# {res['title']}\n# {res['url']}\n# '부가가치세·부가세·매입세액·세금계산서' 가 든 지적 항목 발췌(원문 PDF 는 저장하지 않음)\n\n" + "\n\n".join(out_txt))
    return res


def main():
    if "--list" in sys.argv:
        pages = int(sys.argv[sys.argv.index("--pages") + 1]) if "--pages" in sys.argv else 4
        list_posts(pages); return
    ids = [a for a in sys.argv[1:] if a.isdigit()]
    idx_p = f"{OUT}/index.json"
    idx = json.load(open(idx_p, encoding="utf-8")) if os.path.exists(idx_p) else {}
    for i in ids:
        try: idx[i] = one(i)
        except Exception as e: print(f"[{i}] 실패 {e}")
    os.makedirs(OUT, exist_ok=True)
    json.dump(idx, open(idx_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
