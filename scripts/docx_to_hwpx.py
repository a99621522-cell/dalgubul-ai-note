#!/usr/bin/env python3
"""Word(.docx) → 한글(HWPX, 공무원 양식 복제 hwpx_blocks.py). 표준 라이브러리(+PIL 있으면 그림 크기).

리포트 자료(public/files/*.docx)를 한글로도 내려받게 한다(운영자 지시 2026-10-06 '옮긴 리포트도 한글로 다운 받을 수 있게').
  python3 scripts/docx_to_hwpx.py public/files/daegu-industry-structure.docx public/hwpx/daegu-industry-structure.hwpx
문단 역할: Title → 표지 제목, heading 1 → 절 머리표(Ⅰ Ⅱ …, 앞의 'Ⅰ.'·'제1장' 은 뺌), heading 2·3 → □, 목록 → -, Caption·'주:'·'자료:'·'※'·'<그림 n>'·'표 n.' → ※,
그 밖 글 문단 → ○. 표는 병합(gridSpan·vMerge) 보존, 그림은 word/media 를 넣는다(사진·큰 그림은 JPEG 로 줄임, PIL 없으면 PNG 만). 차례(TOC)는 뺀다. 글자 모양(굵게 등)은 양식 그대로라 옮기지 않는다.
"""
import argparse, io, re, sys, tempfile, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hwpx_blocks as B  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
ROMAN_RE = re.compile(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+\s*[.．]?\s*")
NOTE_RE = re.compile(r"^(※|주\s*[:：]|자료\s*[:：]|출처\s*[:：]|\d{1,2}\)\s)")
CAP_RE = re.compile(r"^[<〈\[\(]?\s*(그림|표|요약)\s*[\d\-–.]+")


def ptext(p) -> str:
    out = []
    for e in p.iter():
        if e.tag == W + "t": out.append(e.text or "")
        elif e.tag == W + "tab": out.append(" ")
        elif e.tag in (W + "br", W + "cr"): out.append(" ")
    return re.sub(r"\s+", " ", "".join(out)).strip()


def style_names(z) -> dict:
    names = {}
    try:
        st = ET.fromstring(z.read("word/styles.xml"))
        for s in st.iter(W + "style"):
            n = s.find(W + "name")
            if n is not None: names[s.get(W + "styleId")] = (n.get(W + "val") or "").lower()
    except KeyError:
        pass
    return names


def rels(z) -> dict:
    out = {}
    try:
        for r in ET.fromstring(z.read("word/_rels/document.xml.rels")):
            out[r.get("Id")] = r.get("Target")
    except KeyError:
        pass
    return out


def convert(src: Path, out: Path, cover: bool = True) -> list[dict]:
    z = zipfile.ZipFile(src)
    names = style_names(z); rel = rels(z)
    body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
    tmp = Path(tempfile.mkdtemp(prefix="docx2hwpx_"))
    blocks: list[dict] = []; have_title = False; nimg = 0

    def img_path(blip) -> str | None:
        nonlocal nimg
        tgt = rel.get(blip.get(R + "embed") or "")
        if not tgt: return None
        name = "word/" + tgt.lstrip("/") if not tgt.startswith("word/") else tgt
        if name not in z.namelist(): return None
        data = z.read(name); nimg += 1
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(data)); im.load()
            if max(im.size) > 1400: im.thumbnail((1400, 1400))
            # 사진(JPEG)·큰 그림은 JPEG 로 줄여 파일 크기를 누른다(Cloudflare Pages 파일 25MB 제한), 작은 PNG 는 PNG 그대로
            if name.lower().endswith((".jpg", ".jpeg")) or len(data) > 300_000:
                p = tmp / f"img{nimg}.jpg"; im.convert("RGB").save(p, "JPEG", quality=82, optimize=True)
            else:
                p = tmp / f"img{nimg}.png"; im.save(p, "PNG", optimize=True)
        except Exception:
            if data[:8] != b"\x89PNG\r\n\x1a\n": return None
            p = tmp / f"img{nimg}.png"; p.write_bytes(data)
        return str(p)

    def para(p, in_table=False):
        nonlocal have_title
        st = p.find(W + "pPr/" + W + "pStyle"); sname = names.get(st.get(W + "val"), "") if st is not None else ""
        text = ptext(p)
        pics = [img_path(b) for b in p.iter(A + "blip")]
        pics = [x for x in pics if x]
        if pics:
            return [{"pic": x, "caption": ""} for x in pics] + ([{"p": "caption", "segs": [[text, ""]]}] if text else [])
        if not text: return []
        if in_table: return [{"p": "body", "segs": [[text, ""]]}]
        if text == "차례" or text.startswith("※ 차례가") or re.fullmatch(r"제\s*\d+\s*장", text): return []
        if sname == "title" or (not have_title and not blocks):
            have_title = True; return [{"p": "title", "segs": [[text, ""]]}]
        if have_title and len(blocks) == 1 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return [{"p": "kicker", "segs": [[text, ""]]}]
        if sname.startswith("heading 1") or sname == "heading1":
            return [{"p": "h2", "segs": [[ROMAN_RE.sub("", text), ""]]}]
        if sname.startswith("heading"): return [{"p": "h3", "segs": [[text, ""]]}]
        if "list" in sname or p.find(W + "pPr/" + W + "numPr") is not None: return [{"p": "bullet", "segs": [[text, ""]]}]
        if sname == "caption" or CAP_RE.match(text): return [{"p": "caption", "segs": [[text, ""]]}]
        if NOTE_RE.match(text): return [{"p": "note", "segs": [[text, ""]]}]
        return [{"p": "body", "segs": [[text, ""]]}]

    def table(t):
        grid = [int(g.get(W + "w") or 0) for g in t.iter(W + "gridCol")]
        trs = t.findall(W + "tr"); raw = []
        for tr in trs:
            row = []
            for tc in tr.findall(W + "tc"):
                pr = tc.find(W + "tcPr"); cs = 1; vm = None
                if pr is not None:
                    g = pr.find(W + "gridSpan"); cs = int(g.get(W + "val") or 1) if g is not None else 1
                    v = pr.find(W + "vMerge"); vm = (v.get(W + "val") or "continue") if v is not None else None
                txt = " ".join(ptext(p) for p in tc.findall(W + "p") if ptext(p))
                row.append([txt, cs, vm])
            raw.append(row)
        # vMerge: restart 칸의 rowSpan = 아래 continue 칸 수 + 1, continue 칸은 뺀다(같은 열 위치 기준)
        pos = []
        for row in raw:
            c = 0; pr = []
            for cell in row: pr.append(c); c += cell[1]
            pos.append(pr)
        rows = []
        for ri, row in enumerate(raw):
            out = []
            for ci, cell in enumerate(row):
                txt, cs, vm = cell
                if vm == "continue": continue
                rs = 1
                if vm == "restart":
                    for rj in range(ri + 1, len(raw)):
                        nxt = [raw[rj][k] for k in range(len(raw[rj])) if pos[rj][k] == pos[ri][ci]]
                        if nxt and nxt[0][2] == "continue": rs += 1
                        else: break
                out.append({"t": txt, "cs": cs, "rs": rs} if (cs > 1 or rs > 1) else txt)
            rows.append(out)
        return {"table": rows, "head": True, "widths": grid if grid and len(grid) == max(sum(c[1] for c in r) for r in raw) else None}

    for el in body:
        tag = el.tag[len(W):]
        if tag == "p": blocks.extend(para(el))
        elif tag == "tbl": blocks.append(table(el))
        # sdt(차례)·sectPr 은 뺀다
    # 첫 절 머리표 앞의 짧은 글 문단(마침표 없음, 20자 이하)은 서론 제목으로 보고 절 머리표로(예: '한국 제조업의 지형')
    first_h2 = next((i for i, b in enumerate(blocks) if b.get("p") == "h2"), len(blocks))
    for b in blocks[:first_h2]:
        if b.get("p") == "body":
            t = "".join(x for x, _ in b["segs"])
            if len(t) <= 20 and not re.search(r"[.。,:%\d]", t): b["p"] = "h2"
    title = next(("".join(t for t, _ in b["segs"]) for b in blocks if b.get("p") == "title"), src.stem)
    B.build_hwpx(blocks, out, preview=title, cover=cover)
    return blocks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src"); ap.add_argument("out"); ap.add_argument("--no-cover", action="store_true")
    a = ap.parse_args()
    blocks = convert(Path(a.src), Path(a.out), cover=not a.no_cover)
    kinds = {}
    for b in blocks: k = "table" if "table" in b else ("pic" if "pic" in b else b["p"]); kinds[k] = kinds.get(k, 0) + 1
    print(f"{a.out}: {Path(a.out).stat().st_size // 1024}KB, 블록 {len(blocks)} {kinds}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
