#!/usr/bin/env python3
"""정책제안 리포트(마크다운) → 한글 HWPX (공공기관 보고서 기본 양식, scripts/data/hwpx/report_basic.hwpx 를 채운다). 표준 라이브러리 + pyyaml.

양식(운영자 제공, 2026-09-27)의 문단을 원형으로 복제해 채운다: 표지(제목 2줄·날짜·부서 표), 목차, 절 머리표(Ⅰ Ⅱ …),
□(HY헤드라인M 15) → ○(휴먼명조 14) → -(14) → ※(11) 단계, 표(맑은 고딕 12).
LG경영연구원 리포트 형식(운영자 지시 2026-09-27 「이 파일처럼 그림도 넣고 표도 넣고」)을 따라 그림·표를 본문에 넣는다:
대표 그림(public/figures/<id>/hero.png)은 요약 앞에, 본문 <figure> 의 SVG 는 rsvg-convert 로 PNG 로 바꿔 캡션과 함께,
마크다운 표는 한글 표로, 문단 첫머리의 굵은 핵심 문장은 붉은 굵은 글씨(LG 리포트의 리드 문장) 로. rsvg-convert 가 없으면 캡션만 ※ 줄로 남긴다.
원문 문장은 그대로 옮긴다(요약·평가 없음). 표지의 부서·담당·연락처 표와 날짜는 빼고, 한 쪽 요약의 소속부서 칸도 비운다(운영자 지시 2026-09-27).

사용: python3 scripts/hwpx_report.py src/content/posts/<파일>.md [-o public/hwpx/<id>.hwpx]
      python3 scripts/hwpx_report.py --all        # 발행된 정책제안 리포트 전부 → public/hwpx/<id>.hwpx
      python3 scripts/hwpx_report.py --check <hwpx>  # XML 이 잘 열리는지
"""
import argparse, copy, io, re, shutil, struct, subprocess, sys, zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "scripts" / "data" / "hwpx" / "report_basic.hwpx"
POSTS = ROOT / "src" / "content" / "posts"
OUT_DIR = ROOT / "public" / "hwpx"
PUBLIC = ROOT / "public"
PX_UNIT = 75            # 96dpi 픽셀 1 = 75 HWPUNIT(1/7200인치)
MAX_IMG_W = 42000       # 본문 그림 최대 너비(≈148mm, 본문 폭 48188 안)
LEAD_COLOR = "#C00000"  # 핵심(리드) 문장 색 — LG경영연구원 리포트의 붉은 굵은 글씨
ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ", "Ⅺ", "Ⅻ"]
NS: dict[str, str] = {}
HP = ""


# ───────── 마크다운 → 블록 ─────────
def inline(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", s)
    s = s.replace("`", "").replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", s).strip()


def split_front(text: str):
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    return yaml.safe_load(parts[1]) or {}, parts[2]


def body_blocks(md: str) -> list[tuple[str, object]]:
    """(kind, payload): section(제목) / box(□) / o(○) / dash(-) / note(※) / table(rows)"""
    out: list[tuple[str, object]] = []
    lines = md.replace("\r", "").split("\n")
    buf: list[str] = []
    i = 0

    def flush():
        if not buf:
            return
        text = inline(" ".join(buf)); buf.clear()
        if not text:
            return
        m = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", " ".join(buf) if False else "")  # placeholder
        out.append(("o", text))

    while i < len(lines):
        l = lines[i]
        if not l.strip() or re.match(r"^---+\s*$", l):
            flush(); i += 1; continue
        h = re.match(r"^(#{1,4})\s+(.*)$", l)
        if h:
            flush()
            title = inline(h[2])
            if len(h[1]) <= 2:
                out.append(("section", re.sub(r"^\d+\.\s*", "", title)))
            else:
                out.append(("sub", re.sub(r"^\d+\.\s*", "", title)))
            i += 1; continue
        if l.lstrip().startswith("<figure"):
            flush(); blk = l
            while "</figure>" not in blk and i + 1 < len(lines):
                i += 1; blk += "\n" + lines[i]
            cap = re.search(r"<figcaption>([\s\S]*?)</figcaption>", blk)
            src = re.search(r'<img[^>]*src="([^"]+)"', blk)
            out.append(("figure", (src.group(1) if src else "", inline(cap.group(1)) if cap else ""))); i += 1; continue
        if l.lstrip().startswith("<"):
            i += 1; continue
        if l.startswith("|"):
            flush(); rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [inline(c) for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c.strip()) for c in cells if c.strip()) or not any(c.strip() for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                out.append(("table", rows))
            continue
        if re.match(r"^>\s?", l):
            flush(); q = []
            while i < len(lines) and re.match(r"^>\s?", lines[i]):
                q.append(re.sub(r"^>\s?", "", lines[i])); i += 1
            out.append(("note", inline(" ".join(q)))); continue
        li = re.match(r"^(\s*)([-*]|\d+[.)])\s+(.*)$", l)
        if li:
            flush(); text = li[3]
            while i + 1 < len(lines) and re.match(r"^\s+\S", lines[i + 1]) and not re.match(r"^\s*([-*]|\d+[.)])\s+", lines[i + 1]):
                i += 1; text += " " + lines[i].strip()
            num = li[2] if re.match(r"\d", li[2]) else ""
            out.append(("dash", (num + " " if num else "") + inline(text))); i += 1; continue
        # 문단: 굵은 첫 문장(인사이트 형식의 핵심 문장)은 붉은 굵은 리드 + 같은 문단의 나머지(LG 리포트 식).
        # '**표 1. 제목**' 처럼 표 제목만 있는 줄은 표 캡션.
        m = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", l.strip())
        if m and not buf:
            flush()
            lead, rest = inline(m[1]), [m[2]] if m[2].strip() else []
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^(#|\||<|>|\s*[-*]\s|---)", lines[i + 1]):
                i += 1; rest.append(lines[i].strip())
            if not rest and re.match(r"^표\s*\d", lead):
                out.append(("caption", lead))
            else:
                out.append(("lead", (lead, inline(" ".join(rest)))))
            i += 1; continue
        buf.append(l.strip()); i += 1
    flush()
    return out


# ───────── HWPX 조작 ─────────
def t_elems(p): return list(p.iter(HP + "t"))


def text_of(e) -> str: return "".join(t.text or "" for t in e.iter(HP + "t"))


def set_para_text(p, text: str) -> None:
    """문단의 글 run 하나만 남기고 텍스트를 넣는다(줄 배치 캐시는 원형 것을 둔다)."""
    runs = p.findall(HP + "run")
    keep = None
    for r in runs:
        if r.find(HP + "t") is not None:
            keep = r; break
    if keep is None:
        keep = runs[0] if runs else ET.SubElement(p, HP + "run")
    for r in runs:
        if r is not keep and r.find(HP + "t") is not None and r.find(HP + "ctrl") is None and r.find(HP + "tbl") is None:
            p.remove(r)
    ts = keep.findall(HP + "t")
    for t in ts[1:]:
        keep.remove(t)
    t = ts[0] if ts else ET.SubElement(keep, HP + "t")
    for c in list(t):
        t.remove(c)
    t.text = text


def replace_t(e, old: str, new: str) -> bool:
    for t in e.iter(HP + "t"):
        if t.text and old in t.text:
            t.text = t.text.replace(old, new); return True
    return False


def clear_t(e, old: str) -> None:
    for t in e.iter(HP + "t"):
        if t.text and old in t.text:
            t.text = ""


def clone(e):
    return copy.deepcopy(e)


def set_para_runs(p, segs: list[tuple[str, str | None]]) -> None:
    """문단을 (텍스트, charPrIDRef) 조각들로 채운다. None 이면 원형 run 의 글자 모양."""
    set_para_text(p, "")
    runs = [r for r in p.findall(HP + "run") if r.find(HP + "t") is not None]
    proto = runs[0]
    p.remove(proto)
    lineseg = p.find(HP + "linesegarray")
    for text, cp in segs:
        r = clone(proto)
        if cp:
            r.set("charPrIDRef", cp)
        r.find(HP + "t").text = text
        if lineseg is not None:
            p.insert(list(p).index(lineseg), r)
        else:
            p.append(r)


def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    return 800, 450


def svg_to_png(svg: Path) -> bytes | None:
    """rsvg-convert(librsvg2-bin) 로 SVG → PNG(폭 1600px). 없으면 None."""
    if not shutil.which("rsvg-convert"):
        return None
    r = subprocess.run(["rsvg-convert", "-w", "1600", "-b", "white", str(svg)], capture_output=True)
    return r.stdout if r.returncode == 0 and r.stdout[:4] == b"\x89PNG" else None


def load_image(src: str) -> tuple[bytes, str, int, int] | None:
    """사이트 경로(/figures/…) → (바이트, 확장자, 픽셀 너비, 높이). 큰 PNG(대표 그림)는 JPEG 로 줄인다."""
    path = PUBLIC / src.lstrip("/")
    if not path.exists():
        return None
    ext = path.suffix.lower().lstrip(".")
    data = svg_to_png(path) if ext == "svg" else path.read_bytes()
    if not data:
        return None
    ext = "png" if ext == "svg" else ext
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)); im.load()
        if ext in ("png", "jpg", "jpeg") and len(data) > 400_000:
            im = im.convert("RGB"); im.thumbnail((1400, 1400))
            b = io.BytesIO(); im.save(b, "JPEG", quality=85, optimize=True); data, ext = b.getvalue(), "jpg"
        w, h = im.size
    except Exception:
        w, h = png_size(data)
    return data, ext, w, h


class Images:
    """본문에 넣는 그림 모음: BinData/imageN.<ext> + content.hpf manifest 항목."""

    def __init__(self, start: int = 2):
        self.n = start
        self.files: list[tuple[str, bytes, str]] = []   # (id, bytes, ext)

    def add(self, data: bytes, ext: str) -> str:
        bid = f"image{self.n}"; self.n += 1
        self.files.append((bid, data, ext))
        return bid


def pic_paragraph(proto, bid: str, px_w: int, px_h: int, comment: str):
    """가운데 정렬 문단 하나에 그림(글자처럼 취급)을 넣는다."""
    w = min(px_w * PX_UNIT, MAX_IMG_W)
    h = int(px_h * PX_UNIT * (w / (px_w * PX_UNIT)))
    xml = (f'<hp:run xmlns:hp="{NS["hp"]}" xmlns:hc="{NS["hc"]}" charPrIDRef="24"><hp:pic id="{2000000000 + hash(bid) % 100000000}" zOrder="{10 + int(bid[5:])}" numberingType="PICTURE" '
           f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="0" instid="{1100000000 + int(bid[5:])}" reverse="0">'
           f'<hp:offset x="0" y="0"/><hp:orgSz width="{w}" height="{h}"/><hp:curSz width="{w}" height="{h}"/><hp:flip horizontal="0" vertical="0"/>'
           f'<hp:rotationInfo angle="0" centerX="{w // 2}" centerY="{h // 2}" rotateimage="1"/><hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
           f'<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/><hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
           f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/><hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/></hp:imgRect>'
           f'<hp:imgClip left="0" right="{px_w * PX_UNIT}" top="0" bottom="{px_h * PX_UNIT}"/><hp:inMargin left="0" right="0" top="0" bottom="0"/>'
           f'<hc:img binaryItemIDRef="{bid}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/><hp:effects/>'
           f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
           f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
           f'<hp:outMargin left="0" right="0" top="283" bottom="283"/><hp:shapeComment>{comment}</hp:shapeComment></hp:pic><hp:t/></hp:run>')
    run = ET.fromstring(xml)
    p = clone(proto)
    for r in p.findall(HP + "run"):
        p.remove(r)
    lineseg = p.find(HP + "linesegarray")
    p.insert(list(p).index(lineseg) if lineseg is not None else 0, run)
    p.set("paraPrIDRef", "20")   # 가운데 정렬
    return p


def add_lead_charpr(header_xml: str, base_id: str = "16") -> tuple[str, str]:
    """header.xml 에 리드 문장용 글자 모양(원형 base_id + 굵게 + 붉은색)을 추가하고 (새 header, 새 id) 를 돌려준다."""
    m = re.search(r'<hh:charPr id="%s".*?</hh:charPr>' % base_id, header_xml, re.S)
    cnt = re.search(r'<hh:charProperties itemCnt="(\d+)"', header_xml)
    if not m or not cnt:
        return header_xml, base_id
    new_id = cnt.group(1)
    cp = m.group(0).replace(f'id="{base_id}"', f'id="{new_id}"', 1).replace('textColor="#000000"', f'textColor="{LEAD_COLOR}"', 1)
    cp = cp.replace("<hh:strikeout", "<hh:bold/><hh:strikeout", 1) if "<hh:strikeout" in cp else cp.replace("</hh:charPr>", "<hh:bold/></hh:charPr>")
    header_xml = header_xml.replace(cnt.group(0), f'<hh:charProperties itemCnt="{int(new_id) + 1}"', 1).replace("</hh:charProperties>", cp + "</hh:charProperties>", 1)
    return header_xml, new_id


def fmt_date(d) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return f"{d.year}. {d.month}. {d.day}."


def build(meta: dict, body_md: str, area: str, out: Path, post_id: str = "") -> None:
    global HP
    z = zipfile.ZipFile(TEMPLATE)
    names = z.namelist()
    sec_xml = z.read("Contents/section0.xml").decode("utf-8")
    NS.clear(); NS.update(dict(re.findall(r'xmlns:(\w+)="([^"]+)"', sec_xml[:3000])))
    for k, v in NS.items():
        ET.register_namespace(k, v)
    HP = "{%s}" % NS["hp"]
    root = ET.fromstring(sec_xml)
    top = list(root)
    header_xml, lead_cp = add_lead_charpr(z.read("Contents/header.xml").decode("utf-8"))
    images = Images()
    post_id = post_id or out.stem
    title = re.sub(r"^\[정책제안\]\s*", "", str(meta.get("title", "")))
    line1 = f"정책제안 리포트{' · ' + area if area else ''}"
    # 표지
    replace_t(top[3], "2027년 회계연도 ", line1)
    replace_t(top[3], "회계감사인 선임 제안 요청서", title)
    set_para_text(top[8], "")   # 표지 날짜도 넣지 않는다(운영자 지시 2026-09-27)
    # 표지의 부서·담당·연락처 표와 부서 이름 상자는 넣지 않는다(운영자 지시 2026-09-27)
    root.remove(top[12]); root.remove(top[15])
    # 본문 블록 → 절
    blocks = body_blocks(body_md)
    sections: list[tuple[str, list]] = []
    summary: list = []
    desc = inline(str(meta.get("description") or meta.get("summary") or ""))
    hero = meta.get("hero") if isinstance(meta.get("hero"), dict) else {}
    if (PUBLIC / "figures" / post_id / "hero.png").exists():
        summary.append(("figure", (f"/figures/{post_id}/hero.png", inline(str(hero.get("caption") or "대표 그림 (AI 생성 이미지)")))))
    if desc:
        summary.append(("o", desc))
    for o in meta.get("outline") or []:
        summary.append(("dash", inline(str(o))))
    if summary:
        sections.append(("요약", summary))
    cur: list = []
    cur_title = ""
    for kind, payload in blocks:
        if kind == "section":
            if cur_title or cur:
                sections.append((cur_title or "들어가며", cur))
            cur_title, cur = str(payload), []
        else:
            cur.append((kind, payload))
    if cur_title or cur:
        sections.append((cur_title or "들어가며", cur))
    faq = meta.get("faq") or []
    if faq:
        sections.append(("자주 묻는 질문", [x for qa in faq for x in (("box", inline(str(qa.get("q", "")))), ("o", inline(str(qa.get("a", "")))))]))
    srcs = meta.get("sources") or []
    if srcs:
        sections.append(("참고 자료", [("dash", f"{inline(str(s.get('title', '')))} — {s.get('url', '')}") for s in srcs if isinstance(s, dict)]))
    # 목차
    toc_tbl = top[17]
    entry_proto = sub_proto = spacer_proto = None
    toc_list = None
    for sl in toc_tbl.iter(HP + "subList"):
        for p in sl.findall(HP + "p"):
            tx = text_of(p)
            if tx.strip().startswith("Ⅰ.") and entry_proto is None:
                entry_proto, toc_list = p, sl
            elif re.match(r"^\s*1\.\s", tx) and sub_proto is None:
                sub_proto = p
            elif entry_proto is not None and not tx.strip() and spacer_proto is None:
                spacer_proto = p
    if toc_list is not None and entry_proto is not None:
        ps = toc_list.findall(HP + "p")
        start = ps.index(entry_proto)
        for p in ps[start:]:
            toc_list.remove(p)
        for si, (stitle, sblocks) in enumerate(sections):
            e = clone(entry_proto); set_para_text(e, f" {ROMAN[si % len(ROMAN)]}. {stitle} "); toc_list.append(e)
            n = 0
            for kind, payload in sblocks:
                if kind == "sub" and sub_proto is not None and n < 8:
                    n += 1; s = clone(sub_proto); set_para_text(s, f"  {n}. {payload} "); toc_list.append(s)
            if spacer_proto is not None:
                toc_list.append(clone(spacer_proto))
    # 본문 원형
    head_proto, box_proto, o_proto, dash_proto, note_proto, blank_proto, tbl_proto = top[19], top[20], top[21], top[22], top[23], top[24], top[64]
    for p in top[19:]:
        root.remove(p)
    for si, (stitle, sblocks) in enumerate(sections):
        h = clone(head_proto)
        if si > 0:
            h.set("pageBreak", "1")
        replace_t(h, "Ⅰ", ROMAN[si % len(ROMAN)]); replace_t(h, " 사업 개요", f" {stitle}")
        root.append(h)
        for kind, payload in sblocks:
            if kind in ("box", "sub"):
                e = clone(box_proto); set_para_text(e, f" □ {payload}")
            elif kind == "lead":
                lead, rest = payload  # type: ignore[misc]
                e = clone(o_proto); set_para_runs(e, [("  ○ ", None), (lead, lead_cp)] + ([(" " + rest, None)] if rest else []))
            elif kind == "caption":
                e = clone(note_proto); set_para_text(e, str(payload)); e.set("paraPrIDRef", "20")
            elif kind == "figure":
                src, cap = payload  # type: ignore[misc]
                img = load_image(src) if src else None
                if img is None:
                    e = clone(note_proto); set_para_text(e, f"       ※ [그림] {cap}")
                else:
                    data, ext, pw, ph = img
                    bid = images.add(data, ext)
                    root.append(pic_paragraph(blank_proto, bid, pw, ph, f"그림: {cap[:120]}"))
                    e = clone(note_proto); set_para_text(e, cap); e.set("paraPrIDRef", "20")
            elif kind == "o":
                e = clone(o_proto); set_para_text(e, f"  ○ {payload}")
            elif kind == "dash":
                e = clone(dash_proto); set_para_text(e, f"   - {payload}")
            elif kind == "note":
                e = clone(note_proto); set_para_text(e, f"       ※ {payload}")
            elif kind == "table":
                e = make_table(tbl_proto, payload)  # type: ignore[arg-type]
            else:
                continue
            root.append(e)
        root.append(clone(blank_proto))
    ET.indent(root, space="") if hasattr(ET, "indent") else None
    new_sec = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' + ET.tostring(root, encoding="unicode")
    preview = "\n".join([line1, title] + [f"{ROMAN[i % 12]}. {s}" for i, (s, _) in enumerate(sections)])
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = "".join(f'<opf:item id="{bid}" href="BinData/{bid}.{ext}" media-type="image/{"jpeg" if ext == "jpg" else ext}" isEmbeded="1"/>' for bid, _, ext in images.files)
    with zipfile.ZipFile(out, "w") as zo:
        for n in names:
            data = z.read(n)
            if n == "Contents/section0.xml":
                data = new_sec.encode("utf-8")
            elif n == "Contents/header.xml":
                data = header_xml.encode("utf-8")
            elif n == "Contents/content.hpf":
                data = data.decode("utf-8").replace("</opf:manifest>", manifest + "</opf:manifest>", 1).encode("utf-8")
            elif n == "Preview/PrvText.txt":
                data = preview.encode("utf-8")
            zo.writestr(zipfile.ZipInfo(n), data, compress_type=zipfile.ZIP_STORED if n == "mimetype" else zipfile.ZIP_DEFLATED)
        for bid, data, ext in images.files:
            zo.writestr(zipfile.ZipInfo(f"BinData/{bid}.{ext}"), data, compress_type=zipfile.ZIP_DEFLATED)
    print(f"→ {out} ({out.stat().st_size:,} bytes, 절 {len(sections)}개, 그림 {len(images.files)}개)")


def make_table(proto, rows: list[list[str]]):
    """원형 표(머리 1행 + 본문 행)를 복제해 rows 로 채운다. 열 수는 본문 rows 에 맞춘다."""
    p = clone(proto)
    tbl = p.find(".//" + HP + "tbl")
    trs = tbl.findall(HP + "tr")
    head_tr, body_tr = trs[0], trs[1]
    for tr in trs:
        tbl.remove(tr)
    ncol = max(len(r) for r in rows)
    sz = tbl.find(HP + "sz")
    total_w = int(sz.get("width")) if sz is not None else 47000

    def fit(tr, cells):
        tcs = tr.findall(HP + "tc")
        while len(tcs) < ncol:
            tr.append(clone(tcs[-1])); tcs = tr.findall(HP + "tc")
        for extra in tcs[ncol:]:
            tr.remove(extra)
        tcs = tr.findall(HP + "tc")
        for ci, tc in enumerate(tcs):
            addr = tc.find(HP + "cellAddr")
            if addr is not None:
                addr.set("colAddr", str(ci))
            csz = tc.find(HP + "cellSz")
            if csz is not None:
                csz.set("width", str(total_w // ncol))
            sl = tc.find(HP + "subList")
            ps = sl.findall(HP + "p") if sl is not None else []
            if ps:
                set_para_text(ps[0], cells[ci] if ci < len(cells) else "")
                for extra in ps[1:]:
                    sl.remove(extra)
        return tr

    tbl.append(fit(head_tr, rows[0]))
    for ri, r in enumerate(rows[1:], 1):
        tr = fit(clone(body_tr), r)
        for tc in tr.findall(HP + "tc"):
            addr = tc.find(HP + "cellAddr")
            if addr is not None:
                addr.set("rowAddr", str(ri))
        tbl.append(tr)
    tbl.set("rowCnt", str(len(rows))); tbl.set("colCnt", str(ncol))
    return p


SUMMARY_TEMPLATE = ROOT / "scripts" / "data" / "hwpx" / "report_summary.hwpx"


def build_summary(meta: dict, body_md: str, area: str, out: Path, post_id: str) -> None:
    """한 쪽 요약(양식2): 제목·부서·개요·추진방안 3(제안 3개)·실행방안(요약 상자)·예산(인용 안 함)·기타(반론)·붙임(전체 리포트 주소)."""
    global HP
    z = zipfile.ZipFile(SUMMARY_TEMPLATE)
    sec_xml = z.read("Contents/section0.xml").decode("utf-8")
    NS.clear(); NS.update(dict(re.findall(r'xmlns:(\w+)="([^"]+)"', sec_xml[:3000])))
    for k, v in NS.items():
        ET.register_namespace(k, v)
    HP = "{%s}" % NS["hp"]
    root = ET.fromstring(sec_xml)
    title = re.sub(r"^\[정책제안\]\s*", "", str(meta.get("title", "")))
    blocks = body_blocks(body_md)
    subs = [str(p) for k, p in blocks if k == "sub"]
    props = [s for s in subs if re.match(r"^제안\s*\d", s)] or subs[:3]
    outline = [inline(str(o)) for o in (meta.get("outline") or [])]
    desc = inline(str(meta.get("description") or meta.get("summary") or ""))
    # 반론 절의 첫 문장들
    counter = []
    grab = False
    for k, p in blocks:
        if k == "section":
            grab = "반론" in str(p)
        elif grab and k in ("o", "box") and len(counter) < 3:
            counter.append(str(p)[:120])
    d = fmt_date(meta.get("date", date.today()))
    fills = [("OOO 신사업 보고서", title), ("폰트 HY헤드라인M, 크기 18", f"정책제안 리포트{' · ' + area if area else ''}"),
             ("<소속부서 : OOOO부서, 2022.12.31.>", ""),
             ("(본 문서를 한 페이지로 나타내기 위한 내용 작성 1줄 또는 2줄 이내)", desc[:160]),
             ("최신 기술을 접목한 OOOO 시스템의 사용자 친화적 UI/UX 개선을 위한 용역사업 추진", desc[160:400] if len(desc) > 160 else ""),
             ("추진방안 1 : 사용자 온라인 수요조사 수행 ", props[0] if len(props) > 0 else ""),
             ("추진방안 2 : 용역 공고를 통한 UI/UX 경험을 가진 전문 업체의 선정", props[1] if len(props) > 1 else ""),
             ("추진방안 3 : 2024년도까지 시스템 오픈을 위한 일정 준수", props[2] if len(props) > 2 else ""),
             ("추진전략에 따른 내용 작성 ", outline[0] if outline else ""), ("내용1", outline[1] if len(outline) > 1 else ""), ("내용2", " · ".join(outline[2:5])),
             ("수요조사 : 00억원 ", "정책제안서이므로 예산액·사업코드를 인용하지 않는다"), ("시스템개발 : 00억원 ", ""), ("시스템 안정화 : 00억원", ""),
             ("OO부서의 협력 필요 ", counter[0] if counter else ""), ("환율 문제로 인한 리스크 대응 필요 ", counter[1] if len(counter) > 1 else ""),
             ("서비스 오픈을 위한 일정 준수 필요", counter[2] if len(counter) > 2 else ""),
             ("붙임1 참고", f"전체 리포트: https://note.daitda.co.kr/posts/{post_id}/"),
             ("사업 추진일정", "전체 리포트(본문·그림·출처)"), ("개요", "요약 상자"), ("추진체계", "제안 3개(시 · 정부 건의 · 기업·기관)"), ("일정", "반론")]
    for old, new in fills:
        for t in root.iter(HP + "t"):
            if t.text == old or (t.text and t.text.strip() == old.strip()):
                t.text = new
                break
    new_sec = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' + ET.tostring(root, encoding="unicode")
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as zo:
        for n in z.namelist():
            data = new_sec.encode("utf-8") if n == "Contents/section0.xml" else (f"{title}".encode("utf-8") if n == "Preview/PrvText.txt" else z.read(n))
            zo.writestr(zipfile.ZipInfo(n), data, compress_type=zipfile.ZIP_STORED if n == "mimetype" else zipfile.ZIP_DEFLATED)
    print(f"→ {out} ({out.stat().st_size:,} bytes, 요약)")


def area_of(meta: dict) -> str:
    tags = [str(t) for t in (meta.get("tags") or [])]
    return next((t for t in tags if t != "정책제안"), "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("post", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--check")
    a = ap.parse_args()
    if a.check:
        z = zipfile.ZipFile(a.check)
        for n in z.namelist():
            if n.endswith(".xml") or n.endswith(".hpf"):
                ET.fromstring(z.read(n))
        sec = z.read("Contents/section0.xml").decode("utf-8"); hpf = z.read("Contents/content.hpf").decode("utf-8")
        refs = set(re.findall(r'binaryItemIDRef="([^"]+)"', sec))
        missing = [r for r in refs if f'id="{r}"' not in hpf or not any(n.startswith(f"BinData/{r}.") for n in z.namelist())]
        if missing:
            print("그림 참조 오류:", missing); return 1
        print("ok:", a.check, f"그림 {len(refs)}개"); return 0
    targets = []
    if a.all:
        for f in sorted(POSTS.glob("*.md")):
            meta, _ = split_front(f.read_text(encoding="utf-8"))
            if meta.get("category") == "policy" and "정책제안" in (meta.get("tags") or []) and not meta.get("draft"):
                targets.append(f)
    elif a.post:
        targets.append(Path(a.post))
    else:
        ap.print_help(); return 1
    for f in targets:
        meta, body = split_front(f.read_text(encoding="utf-8"))
        out = Path(a.out) if (a.out and not a.all) else OUT_DIR / f"{f.stem}.hwpx"
        build(meta, body, area_of(meta), out, f.stem)
        build_summary(meta, body, area_of(meta), out.with_name(out.stem + "-요약.hwpx"), f.stem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
