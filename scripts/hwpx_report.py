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
      python3 scripts/hwpx_report.py <md> --public -o public/files/<이름>.hwpx   # 리포트 메뉴 게시용(FAQ·요약본 없음)
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
MAX_IMG_W = 46000       # 본문 그림 최대 너비(≈162mm, 본문 폭 48188 안)
MAX_IMG_H = 60000       # 본문 그림 최대 높이(≈212mm) — 세로로 긴 쪽 사진이 한 쪽을 넘지 않게
LEAD_COLOR = "#C00000"  # 핵심(리드) 문장 색 — LG경영연구원 리포트의 붉은 굵은 글씨
ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ", "Ⅺ", "Ⅻ"]
NS: dict[str, str] = {}
HP = ""


# ───────── 마크다운 → 블록 ─────────
def inline(s: str) -> str:
    # 마크다운 역슬래시 이스케이프(\* \_ …)를 먼저 자리표시로 감싸 굵게·기울임 규칙이 먹지 않게 하고 끝에 글자로 되돌린다
    s = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|<>~])", lambda m: f"\x00{ord(m[1])}\x00", s)
    s = re.sub(r"</?[A-Za-z][^>]*>", "", s)   # HTML 태그만(〈참고 1〉 같은 한글 꺾쇠 글은 남긴다)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", s)
    s = s.replace("`", "").replace("&nbsp;", " ").replace("&amp;", "&")
    s = re.sub(r"\x00(\d+)\x00", lambda m: chr(int(m[1])), s)
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
            out.append(("dash2" if len(li[1]) >= 2 else "dash", (num + " " if num else "") + inline(text))); i += 1; continue   # 들여쓴 항목은 dash2(양식의 '-' 단계), 첫 단계는 ○
        # 문단: 굵은 첫 문장(인사이트 형식의 핵심 문장)은 붉은 굵은 리드 + 같은 문단의 나머지(LG 리포트 식).
        # '**표 1. 제목**' 처럼 표 제목만 있는 줄은 표 캡션.
        m = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", l.strip())
        if m and not buf:
            flush()
            lead, rest = inline(m[1]), [m[2]] if m[2].strip() else []
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^(#|\||<|>|\s*[-*]\s|---)", lines[i + 1]):
                i += 1; rest.append(lines[i].strip())
            if not rest and re.match(r"^[〈<]?표\s*[\d부]", lead):
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


def pic_paragraph(ids: dict, bid: str, px_w: int, px_h: int, comment: str):
    """가운데 정렬 문단 하나에 그림(글자처럼 취급)을 넣는다."""
    scale = min(1.0, MAX_IMG_W / (px_w * PX_UNIT), MAX_IMG_H / (px_h * PX_UNIT))
    w, h = int(px_w * PX_UNIT * scale), int(px_h * PX_UNIT * scale)
    xml = (f'<hp:run xmlns:hp="{NS["hp"]}" xmlns:hc="{NS["hc"]}" charPrIDRef="{ids["char"]["caption"]}"><hp:pic id="{2000000000 + int(bid[5:])}" zOrder="{10 + int(bid[5:])}" numberingType="PICTURE" '
           f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="0" instid="{1100000000 + int(bid[5:])}" reverse="0">'
           f'<hp:offset x="0" y="0"/><hp:orgSz width="{w}" height="{h}"/><hp:curSz width="{w}" height="{h}"/><hp:flip horizontal="0" vertical="0"/>'
           f'<hp:rotationInfo angle="0" centerX="{w // 2}" centerY="{h // 2}" rotateimage="1"/><hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
           f'<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/><hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
           f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/><hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/></hp:imgRect>'
           f'<hp:imgClip left="0" right="{px_w * PX_UNIT}" top="0" bottom="{px_h * PX_UNIT}"/><hp:inMargin left="0" right="0" top="0" bottom="0"/>'
           f'<hc:img binaryItemIDRef="{bid}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/><hp:effects/>'
           f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
           f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
           f'<hp:outMargin left="0" right="0" top="0" bottom="0"/><hp:shapeComment>{comment}</hp:shapeComment></hp:pic><hp:t/></hp:run>')
    p = para(ids, "fig", [])
    for r in p.findall(HP + "run"):
        p.remove(r)
    p.insert(0, ET.fromstring(xml))
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


# ───────── 디자인(LG경영연구원 리포트를 본보기로 한 전문가 편집 판, 운영자 지시 2026-09-27) ─────────
TEXT_W = 48188            # A4, 좌우 여백 5669 → 본문 폭(HWPUNIT)
NAVY, NAVY2, INK, INK2, MUTE, RED = "#0F2A5F", "#1F3A93", "#1F2933", "#374151", "#6B7280", "#B91C1C"
GOTHIC, MYEONGJO = "0", "5"      # header.xml 글꼴 id: 맑은 고딕 / 휴먼명조
# 문단 모양: (이름, 정렬, 줄간격%, 앞 간격, 뒤 간격, 왼쪽 여백, 첫 줄 들여쓰기, keepWithNext, 문단 테두리 key)
PARA_SPECS = [
    ("kicker", "LEFT", 150, 0, 150, 0, 0, 1, None), ("title", "LEFT", 128, 0, 450, 0, 0, 1, None), ("rule", "LEFT", 60, 0, 700, 0, 0, 0, "rule"),
    ("body", "JUSTIFY", 172, 0, 650, 0, 0, 0, None), ("h2", "LEFT", 140, 1700, 450, 0, 0, 1, "h2"), ("h3", "LEFT", 140, 900, 300, 0, 0, 1, None),
    ("fig", "CENTER", 100, 500, 150, 0, 0, 1, None), ("caption", "CENTER", 145, 0, 950, 0, 0, 0, None),
    ("bullet", "JUSTIFY", 165, 0, 230, 900, -560, 0, None), ("note", "JUSTIFY", 158, 150, 700, 900, 0, 0, "note"),
    ("box_title", "LEFT", 140, 0, 350, 0, 0, 1, None), ("box_body", "JUSTIFY", 165, 0, 300, 0, 0, 0, None), ("box_item", "LEFT", 160, 0, 120, 700, -450, 0, None),
    ("th", "CENTER", 140, 0, 0, 0, 0, 0, None), ("td", "LEFT", 145, 0, 0, 0, 0, 0, None), ("tdc", "CENTER", 145, 0, 0, 0, 0, 0, None),
    ("src", "JUSTIFY", 145, 0, 160, 800, -800, 0, None), ("faq_q", "LEFT", 150, 500, 150, 0, 0, 1, None), ("spacer", "LEFT", 100, 0, 0, 0, 0, 0, None),
]
# 글자 모양: (이름, 글꼴 id, 크기 pt×100, 색, 굵게)
CHAR_SPECS = [
    ("kicker", GOTHIC, 950, MUTE, True), ("title", GOTHIC, 2300, "#111827", True), ("body", MYEONGJO, 1050, INK, False), ("lead", MYEONGJO, 1050, RED, True),
    ("h2", GOTHIC, 1500, NAVY, True), ("h3", GOTHIC, 1200, NAVY2, True), ("caption", GOTHIC, 850, MUTE, False), ("note", MYEONGJO, 950, INK2, False),
    ("box_title", GOTHIC, 950, NAVY, True), ("box_body", GOTHIC, 1000, INK, False), ("box_item", GOTHIC, 1000, INK, False), ("box_mark", GOTHIC, 1000, NAVY2, True),
    ("th", GOTHIC, 950, NAVY, True), ("td", GOTHIC, 950, INK, False), ("src", GOTHIC, 850, INK2, False), ("faq_q", GOTHIC, 1050, "#111827", True), ("bullet_mark", GOTHIC, 1050, NAVY2, False),
]
# 테두리·채움: (이름, 왼, 오른, 위, 아래, 채움색)  — 선은 (type, width, color) 또는 None
LN = lambda w, c: ("SOLID", w, c)
BORDER_SPECS = [
    ("none", None, None, None, None, None), ("rule", None, None, None, LN("0.5 mm", NAVY2), None), ("h2", None, None, None, LN("0.12 mm", "#C7D2E3"), None),
    ("note", LN("0.6 mm", "#C7D2E3"), None, None, None, None), ("box", None, None, None, None, "#F3F6FB"),
    ("th", None, None, LN("0.4 mm", NAVY), LN("0.15 mm", "#9DB0CC"), "#EEF3FA"), ("td", None, None, None, LN("0.12 mm", "#D9DEE7"), None), ("td_alt", None, None, None, LN("0.12 mm", "#D9DEE7"), "#FAFBFD"),
]


def add_design_styles(header_xml: str) -> tuple[str, dict]:
    """header.xml 에 위 스펙의 문단·글자·테두리 모양을 덧붙이고 이름 → id 사전을 돌려준다."""
    ids: dict = {"para": {}, "char": {}, "border": {}}
    # id 는 itemCnt 가 아니라 '있는 id 의 최댓값 + 1' 부터(2026-10-06 확인: 양식의 borderFill 은 id 1~32 라 itemCnt(32)부터 매기면 양식 id 32(진회색 채움·파란 테두리)와 겹쳐
    # 모든 문단·글자가 검은 바탕에 파란 테두리로 그려졌다 — 운영자 화면 2026-10-06. charPr·paraPr 는 0부터라 우연히 안 겹쳤을 뿐이다)
    def next_id(tag: str) -> int:
        ids_ = [int(x) for x in re.findall(r'<hh:%s id="(\d+)"' % tag, header_xml)]
        return (max(ids_) + 1) if ids_ else 0
    bcnt = next_id("borderFill")
    bxml = ""
    for i, (name, l, r, t, b, fill) in enumerate(BORDER_SPECS):
        bid = bcnt + i; ids["border"][name] = str(bid)
        def line(tag, spec):
            return f'<hh:{tag} type="{spec[0]}" width="{spec[1]}" color="{spec[2]}"/>' if spec else f'<hh:{tag} type="NONE" width="0.1 mm" color="#000000"/>'
        bxml += (f'<hh:borderFill id="{bid}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0"><hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
                 + line("leftBorder", l) + line("rightBorder", r) + line("topBorder", t) + line("bottomBorder", b) + '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
                 + (f'<hc:fillBrush><hc:winBrush faceColor="{fill}" hatchColor="#000000" alpha="0"/></hc:fillBrush>' if fill else "") + "</hh:borderFill>")
    nb = int(re.search(r'<hh:borderFills itemCnt="(\d+)"', header_xml).group(1)) + len(BORDER_SPECS)
    header_xml = re.sub(r'<hh:borderFills itemCnt="\d+"', f'<hh:borderFills itemCnt="{nb}"', header_xml, 1).replace("</hh:borderFills>", bxml + "</hh:borderFills>", 1)
    ccnt = next_id("charPr")
    cxml = ""
    for i, (name, font, size, color, bold) in enumerate(CHAR_SPECS):
        cid = ccnt + i; ids["char"][name] = str(cid)
        cxml += (f'<hh:charPr id="{cid}" height="{size}" textColor="{color}" shadeColor="none" useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="{ids["border"]["none"]}">'
                 f'<hh:fontRef hangul="{font}" latin="{font}" hanja="{font}" japanese="{font}" other="{font}" symbol="{font}" user="{font}"/>'
                 '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/><hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
                 '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/><hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
                 + ("<hh:bold/>" if bold else "") + "</hh:charPr>")
    nc = int(re.search(r'<hh:charProperties itemCnt="(\d+)"', header_xml).group(1)) + len(CHAR_SPECS)
    header_xml = re.sub(r'<hh:charProperties itemCnt="\d+"', f'<hh:charProperties itemCnt="{nc}"', header_xml, 1).replace("</hh:charProperties>", cxml + "</hh:charProperties>", 1)
    pcnt = next_id("paraPr")
    pxml = ""
    for i, (name, align, ls, prev, nxt, left, intent, keep, border) in enumerate(PARA_SPECS):
        pid = pcnt + i; ids["para"][name] = str(pid)
        bf = ids["border"][border or "none"]
        boff = ' offsetLeft="0" offsetRight="0" offsetTop="0" offsetBottom="0"' if border != "note" else ' offsetLeft="500" offsetRight="0" offsetTop="0" offsetBottom="0"'
        pxml += (f'<hh:paraPr id="{pid}" tabPrIDRef="0" condense="0" fontLineHeight="0" snapToGrid="0" suppressLineNumbers="0" checked="0"><hh:align horizontal="{align}" vertical="BASELINE"/>'
                 '<hh:heading type="NONE" idRef="0" level="0"/>'
                 f'<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" widowOrphan="1" keepWithNext="{keep}" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
                 '<hh:autoSpacing eAsianEng="1" eAsianNum="1"/>'
                 f'<hh:margin><hc:intent value="{intent}" unit="HWPUNIT"/><hc:left value="{left}" unit="HWPUNIT"/><hc:right value="0" unit="HWPUNIT"/><hc:prev value="{prev}" unit="HWPUNIT"/><hc:next value="{nxt}" unit="HWPUNIT"/></hh:margin>'
                 f'<hh:lineSpacing type="PERCENT" value="{ls}" unit="HWPUNIT"/><hh:border borderFillIDRef="{bf}"{boff} connect="0" ignoreMargin="0"/></hh:paraPr>')
    np_ = int(re.search(r'<hh:paraProperties itemCnt="(\d+)"', header_xml).group(1)) + len(PARA_SPECS)
    header_xml = re.sub(r'<hh:paraProperties itemCnt="\d+"', f'<hh:paraProperties itemCnt="{np_}"', header_xml, 1).replace("</hh:paraProperties>", pxml + "</hh:paraProperties>", 1)
    return header_xml, ids


def para(ids: dict, pname: str, segs: list[tuple[str, str]]):
    """문단 원소: segs = [(글, 글자 모양 이름)]."""
    p = ET.Element(HP + "p", {"id": "0", "paraPrIDRef": ids["para"][pname], "styleIDRef": "0", "pageBreak": "0", "columnBreak": "0", "merged": "0"})
    for text, cname in segs or [("", "body")]:
        r = ET.SubElement(p, HP + "run", {"charPrIDRef": ids["char"][cname]})
        ET.SubElement(r, HP + "t").text = text
    return p


def drop_linesegs(root) -> None:
    """줄 배치 캐시(hp:linesegarray)를 모두 뺀다. 한글은 이 값을 그대로 믿어, 모든 문단에 같은 값(세로 위치 0·한 줄)을 넣으면
    문단들이 한 자리에 겹쳐 그려진다(운영자 확인 2026-09-30: 글자가 겹치고 그림 양옆이 검게 뭉침). 없으면 한글이 열 때 줄을 새로 계산한다."""
    for parent in root.iter():
        for ch in [c for c in parent if c.tag == HP + "linesegarray"]:
            parent.remove(ch)


def design_table(proto, ids: dict, rows: list[list[str]], head: bool = True, widths: list[int] | None = None, fill_key: str | None = None, margin: int = 320):
    """원형 표를 복제해 디자인 스타일(머리 행 남색 선·옅은 채움, 본문 행 얇은 밑줄)로 채운다. rows 의 각 칸은 str 또는 문단 원소 목록."""
    p = clone(proto)
    p.set("paraPrIDRef", ids["para"]["body"])
    tbl = p.find(".//" + HP + "tbl")
    trs = tbl.findall(HP + "tr")
    tr_proto = trs[1] if len(trs) > 1 else trs[0]
    for tr in trs:
        tbl.remove(tr)
    tbl.set("borderFillIDRef", ids["border"]["none"]); tbl.set("repeatHeader", "1" if head else "0")
    ncol = max(len(r) for r in rows)
    if not widths:
        lens = [max(len(str(r[c])) if c < len(r) and isinstance(r[c], str) else 12 for r in rows) for c in range(ncol)]
        lens = [max(l, 6) for l in lens]; tot = sum(lens)
        widths = [max(int(TEXT_W * l / tot), int(TEXT_W * 0.14)) for l in lens]
    scale = TEXT_W / sum(widths); widths = [int(w * scale) for w in widths]
    tbl.find(HP + "sz").set("width", str(TEXT_W))
    im = tbl.find(HP + "inMargin")
    if im is not None:
        for k in ("left", "right"):
            im.set(k, str(margin))
        for k in ("top", "bottom"):
            im.set(k, "230")
    tc_proto = tr_proto.findall(HP + "tc")[0]
    for ri, row in enumerate(rows):
        tr = ET.SubElement(tbl, HP + "tr")
        is_head = head and ri == 0
        for ci in range(ncol):
            tc = clone(tc_proto)
            tc.set("header", "1" if is_head else "0")
            tc.set("borderFillIDRef", ids["border"][fill_key or ("th" if is_head else ("td_alt" if ri % 2 == 0 else "td"))])
            sl = tc.find(HP + "subList")
            for old in sl.findall(HP + "p"):
                sl.remove(old)
            sl.set("vertAlign", "CENTER" if is_head else "TOP")
            cell = row[ci] if ci < len(row) else ""
            if isinstance(cell, str):
                sl.append(para(ids, "th" if is_head else ("tdc" if re.fullmatch(r"[\d,.%~\-–\s곳명건개년월억원만천]+", cell or "x") else "td"), [(cell, "th" if is_head else "td")]))
            else:
                for e in cell:
                    sl.append(e)
            tc.find(HP + "cellAddr").set("colAddr", str(ci)); tc.find(HP + "cellAddr").set("rowAddr", str(ri))
            tc.find(HP + "cellSpan").set("colSpan", "1"); tc.find(HP + "cellSpan").set("rowSpan", "1")
            csz = tc.find(HP + "cellSz"); csz.set("width", str(widths[ci])); csz.set("height", "1000")
            cm = tc.find(HP + "cellMargin")
            if cm is not None:
                cm.set("left", str(margin)); cm.set("right", str(margin)); cm.set("top", "230"); cm.set("bottom", "230")
            tr.append(tc)
    tbl.set("rowCnt", str(len(rows))); tbl.set("colCnt", str(ncol))
    return p


def build(meta: dict, body_md: str, area: str, out: Path, post_id: str = "", kicker: str | None = None, faq_on: bool = True) -> None:
    """운영자 공무원 양식 그대로(2026-10-06 '안 바뀌었어' — 리포트도 디자인 판이 아니라 양식 복제로): 표지(제목·머리 글자) → Ⅰ 요약(○ 핵심 문장, - 요약 항목)
    → 본문 절마다 절 머리표(Ⅱ Ⅲ …)·□ 소제목·○ 문단·- 목록·※ 주석·표·그림 → 자주 묻는 질문(□ Q / ○ A) → 참고 자료(※). 실제 조립은 hwpx_blocks.build_hwpx(form=True)."""
    import hwpx_blocks as B
    post_id = post_id or out.stem
    title = re.sub(r"^\[정책제안\]\s*", "", str(meta.get("title", "")))
    kicker = kicker or ("정책제안 리포트" + (f"  ·  {area}" if area else ""))
    P = lambda name, text: {"p": name, "segs": [[text, name]]}
    blocks: list[dict] = [P("kicker", kicker), P("title", title)]
    # 요약: 핵심 문장 + 요약 항목(+ 대표 그림)
    desc = inline(str(meta.get("description") or meta.get("summary") or ""))
    outline = [inline(str(o)) for o in (meta.get("outline") or [])]
    hero = meta.get("hero") if isinstance(meta.get("hero"), dict) else {}
    hero_path = f"/figures/{post_id}/hero.png"
    body_kinds = body_blocks(body_md)
    has_summary = any(k == "section" and str(v).strip() in ("요약", "핵심 요약") for k, v in body_kinds)
    if (desc or outline) and not has_summary:
        blocks.append(P("h2", "요약"))
        if desc:
            blocks.append(P("body", desc))
        for o in outline:
            blocks.append(P("bullet", o))
    if (PUBLIC / hero_path.lstrip("/")).exists():
        blocks.append({"pic": hero_path, "caption": inline(str(hero.get("caption") or "대표 그림 (AI 생성 이미지)"))})
    fig_n = 0
    for kind, payload in body_kinds:
        if kind == "section":
            blocks.append(P("h2", str(payload)))
        elif kind == "sub":
            blocks.append(P("h3", str(payload)))
        elif kind == "lead":
            lead, rest = payload  # type: ignore[misc]
            blocks.append(P("body", (lead + (" " + rest if rest else "")).strip()))
        elif kind in ("o", "box"):
            blocks.append(P("body", str(payload)))
        elif kind in ("dash", "dash2"):
            txt = str(payload); m = re.match(r"^(\d+[.)])\s+(.*)$", txt)
            blocks.append(P("body" if kind == "dash" else "bullet", (m[1] + " " + m[2]) if m else txt))   # 마크다운 첫 단계 항목 = ○, 들여쓴 항목 = -
        elif kind == "note":
            blocks.append(P("note", str(payload)))
        elif kind == "caption":
            blocks.append(P("caption", str(payload)))
        elif kind == "figure":
            src, cap = payload  # type: ignore[misc]
            if src and (PUBLIC / str(src).lstrip("/")).exists():
                fig_n += 1
                blocks.append({"pic": src, "caption": cap or f"그림 {fig_n}"})
            else:
                blocks.append(P("note", f"[그림] {cap}"))
        elif kind == "table":
            blocks.append({"table": payload, "head": True})
    faq = (meta.get("faq") or []) if faq_on else []
    if faq:
        blocks.append(P("h2", "자주 묻는 질문"))
        for qa in faq:
            blocks.append(P("h3", "Q. " + inline(str(qa.get("q", "")))))
            blocks.append(P("body", inline(str(qa.get("a", "")))))
    srcs = [s_ for s_ in (meta.get("sources") or []) if isinstance(s_, dict)]
    if srcs:
        blocks.append(P("h2", "참고 자료"))
        for i, s_ in enumerate(srcs, 1):
            d = str(s_.get("date") or "")[:10]
            blocks.append(P("note", f"{i}. " + inline(str(s_.get("title", ""))) + (f" ({d})" if d else "") + f" — {s_.get('url', '')}"))
    blocks.append(P("note", "daitda.co.kr · 공개 자료만 인용, 평가·순위 없음"))
    preview = "\n".join([kicker, title] + outline)
    B.build_hwpx(blocks, out, preview=preview, form=True, cover=True)
    print(f"→ {out} ({out.stat().st_size:,} bytes, 양식 복제)")


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
             ("붙임1 참고", f"전체 리포트: https://daitda.co.kr/posts/{post_id}/"),
             ("사업 추진일정", "전체 리포트(본문·그림·출처)"), ("개요", "요약 상자"), ("추진체계", "제안 3개(시 · 정부 건의 · 기업·기관)"), ("일정", "반론")]
    for old, new in fills:
        for t in root.iter(HP + "t"):
            if t.text == old or (t.text and t.text.strip() == old.strip()):
                t.text = new
                break
    drop_linesegs(root)
    new_sec = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' + re.sub(r"^<hs:sec\b[^>]*>", re.search(r"<hs:sec\b[^>]*>", sec_xml).group(0), ET.tostring(root, encoding="unicode"), count=1)   # 네임스페이스 선언은 양식 그대로
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
    ap.add_argument("--public", action="store_true", help="게시용(리포트 메뉴): 머리 글자 '리포트'(또는 frontmatter kicker), FAQ·한 쪽 요약본 없음")
    a = ap.parse_args()
    if a.check:   # 구조 검사는 hwpx_check.py 로 옮겼다(2026-10-06): zip 순서·참조 무결성·표 격자·그림 manifest·개인정보
        import hwpx_check
        r = hwpx_check.check_file(Path(a.check))
        for i in r.items:
            if i["level"] != "PASS":
                print(f'   {i["level"]:4} {i["rule"]:12} {i["where"]}  {i["msg"]}')
        print(("FAIL: " if r.failed else "ok: ") + a.check); return 1 if r.failed else 0
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
        if a.public:
            build(meta, body, area_of(meta), out, f.stem, kicker=str(meta.get("kicker") or "리포트"), faq_on=False)
            continue
        build(meta, body, area_of(meta), out, f.stem)
        build_summary(meta, body, area_of(meta), out.with_name(out.stem + "-요약.hwpx"), f.stem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
