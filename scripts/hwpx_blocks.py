#!/usr/bin/env python3
"""Block 목록 → HWPX(양식 복제, docs/prompts/site_hwpx_skill.md 3절). 표준 라이브러리 + hwpx_report.py.

**형식은 운영자가 Drive 에 올린 공무원 한글 양식 그대로**(운영자 지시 2026-10-06 '내가 올린 공무원 한글 파일 형식이 아니다'):
scripts/data/hwpx/report_basic.hwpx 의 문단·표를 deepcopy 해 글자만 바꾼다 — 절 머리표(Ⅰ Ⅱ … 표), □ HY헤드라인M 15pt, ○ 휴먼명조 14pt, - 14pt,
※ 11pt, 표(맑은 고딕 12pt, 머리 행·본문 행·첫/가운데/끝 열의 테두리 모양 그대로), 표지(제목 표). header.xml 은 양식 그대로(스타일을 덧붙이지 않는다 → id 충돌 없음).
브라우저 판(src/scripts/hwpx.ts)은 hwpx_template.py 가 내보낸 같은 원형 조각을 쓴다. 디자인 스타일 판(hwpx_report.py 의 PARA_SPECS)은 form=False.
  Block = {"p": 문단 모양 이름, "segs": [[글, 글자 모양 이름], ...]}   # 이름 → 양식 역할: title/h2 → 절 머리표, h3 → □, body → ○, bullet → -, note/caption/src → ※
        | {"table": rows, "head": bool, "headRows": n, "widths": [HWPUNIT...]}
        | {"pic": "public/ 아래 경로 또는 파일 경로", "caption": 글}
  칸    = str | {"t": 글, "cs": colspan, "rs": rowspan} | [Block, ...]
옵션: cover=True 면 표지(제목 표)를 앞에 두고 첫 절은 새 쪽에서 시작. lineseg=True 는 줄 배치 어림값 실험. all_ns 는 루트 네임스페이스 선언 14개 유지.
"""
import copy, re, sys, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hwpx_report as H  # noqa: E402

ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ", "Ⅺ", "Ⅻ"]
# 양식 문단 인덱스(config/hwpx_forms.yml 과 같다)
FORM = {"cover": 3, "sec": 19, "h1": 26, "o": 27, "dash": 28, "note": 29, "blank": 35, "tbl": 64}
# Block 문단 이름 → 양식 역할
ROLE = {"title": "sec", "h2": "sec", "h3": "h1", "box_title": "h1", "faq_q": "h1", "body": "o", "box_body": "o", "lead": "o", "td": "o", "th": "o",
        "bullet": "dash", "box_item": "dash", "note": "note", "caption": "note", "src": "note", "kicker": "note", "spacer": "blank", "rule": None, "fig": "blank"}
MARK = {"h1": "□ ", "o": "○ ", "dash": "- ", "note": "※ "}


def _text(e) -> str: return "".join(t.text or "" for t in e.iter(H.HP + "t"))


class Ctx:
    def __init__(self, form: bool = True):
        self.z = zipfile.ZipFile(H.TEMPLATE)
        sec_xml = self.z.read("Contents/section0.xml").decode("utf-8")
        H.NS.clear(); H.NS.update(dict(re.findall(r'xmlns:(\w+)="([^"]+)"', sec_xml[:3000])))
        for k, v in H.NS.items():
            ET.register_namespace(k, v)
        H.HP = "{%s}" % H.NS["hp"]
        self.root_tag = re.search(r"<hs:sec\b[^>]*>", sec_xml).group(0)
        self.root = ET.fromstring(sec_xml)
        top = [p for p in self.root if p.tag == H.HP + "p"]
        self.form = form
        if form:
            self.header_xml = self.z.read("Contents/header.xml").decode("utf-8")   # 양식 그대로
            self.ids = None
            self.proto = {k: copy.deepcopy(top[i]) for k, i in FORM.items()}
            H.drop_linesegs(self.root)
        else:
            self.header_xml, self.ids = H.add_design_styles(self.z.read("Contents/header.xml").decode("utf-8"))
            self.tbl_proto = top[64]
        first = top[0]
        for run in first.findall(H.HP + "run"):
            for ctrl in run.findall(H.HP + "ctrl"):
                if ctrl.find(H.HP + "header") is not None or ctrl.find(H.HP + "footer") is not None:
                    run.remove(ctrl)
        for p in top[1:]:
            self.root.remove(p)
        self.images = H.Images()
        self.tbl_seq = 0
        self.sec_n = 0


def cell_parts(cell):
    if isinstance(cell, dict):
        return str(cell.get("t", "")), int(cell.get("cs", 1) or 1), int(cell.get("rs", 1) or 1)
    return cell, 1, 1


def _set_text(p, text: str, keep_run_style=True) -> None:
    """문단의 글 run 하나만 남기고 글자를 바꾼다(양식의 글자 모양 유지)."""
    H.set_para_text(p, text)


def form_para(ctx: Ctx, role: str, text: str):
    p = copy.deepcopy(ctx.proto[role])
    H.drop_linesegs(p)
    _set_text(p, (MARK.get(role, "") + text) if text else "")
    return p


def form_section(ctx: Ctx, title: str, page_break: bool = False):
    """절 머리표(Ⅰ | | 제목) 복제."""
    ctx.sec_n += 1
    p = copy.deepcopy(ctx.proto["sec"]); H.drop_linesegs(p)
    tbl = p.find(".//" + H.HP + "tbl"); ctx.tbl_seq += 1; tbl.set("id", str(2085243000 + ctx.tbl_seq))
    tcs = tbl.findall(".//" + H.HP + "tc")
    H.set_para_text(tcs[0].find(".//" + H.HP + "p"), ROMAN[(ctx.sec_n - 1) % len(ROMAN)])
    H.set_para_text(tcs[2].find(".//" + H.HP + "p"), " " + title)
    # 양식의 절 머리표는 쪽을 새로 시작(pageBreak=1). 첫 절은 표지가 있을 때만 새 쪽, 없으면 본문 첫머리에서 시작
    p.set("pageBreak", "1" if (page_break or ctx.sec_n > 1) else "0")
    return p


def form_cover(ctx: Ctx, title: str, sub: str = ""):
    """표지 제목 표(제목 두 줄). 부서·담당·연락처·날짜는 넣지 않는다(운영자 지시 2026-09-27)."""
    p = copy.deepcopy(ctx.proto["cover"]); H.drop_linesegs(p)
    tbl = p.find(".//" + H.HP + "tbl"); ctx.tbl_seq += 1; tbl.set("id", str(2085243000 + ctx.tbl_seq))
    mid = tbl.findall(H.HP + "tr")[1].find(H.HP + "tc"); sl = mid.find(H.HP + "subList")
    ps = sl.findall(H.HP + "p")
    H.set_para_text(ps[0], title)
    if len(ps) > 1:
        H.set_para_text(ps[1], sub)
    return p


def form_table(ctx: Ctx, rows, head=True, widths=None, head_rows=None):
    """양식 표(top[64]) 복제: 머리 행은 0행 칸, 본문은 1행 칸을 원형으로, 첫/가운데/끝 열의 테두리 모양을 그대로. 병합은 cellSpan 으로."""
    HP = H.HP
    nhead = int(head_rows) if head_rows is not None else (1 if head else 0)
    occ: set = set(); ncol = 0; placed = []
    for ri, row in enumerate(rows):
        col = 0; rp = []
        for cell in row:
            while (ri, col) in occ: col += 1
            _, cs, rs = cell_parts(cell)
            for dr in range(rs):
                for dc in range(cs): occ.add((ri + dr, col + dc))
            rp.append((ri, col, cs, rs, cell)); col += cs
        ncol = max(ncol, col); placed.append(rp)
    for ri in range(len(rows)):
        for ci in range(ncol):
            if (ri, ci) not in occ:
                placed[ri].append((ri, ci, 1, 1, "")); occ.add((ri, ci))
        placed[ri].sort(key=lambda x: x[1])
    p = copy.deepcopy(ctx.proto["tbl"]); H.drop_linesegs(p)
    tbl = p.find(".//" + HP + "tbl"); ctx.tbl_seq += 1; tbl.set("id", str(2085243000 + ctx.tbl_seq))
    W = int(tbl.find(HP + "sz").get("width"))
    if not widths or len(widths) != ncol:
        lens = [max([len(cell_parts(c)[0]) for (r, ci, cs, rs, c) in sum(placed, []) if ci == col and cs == 1] + [4]) for col in range(ncol)]
        tot = sum(lens); widths = [max(int(W * l / tot), int(W * 0.08)) for l in lens]
    scale = W / sum(widths); widths = [int(w * scale) for w in widths]; widths[-1] += W - sum(widths)
    trs = tbl.findall(HP + "tr")
    head_tcs = trs[0].findall(HP + "tc"); body_tcs = trs[1].findall(HP + "tc")
    for tr in trs: tbl.remove(tr)
    pick = lambda protos, ci: protos[0] if ci == 0 else (protos[-1] if ci + 0 >= ncol - 1 else protos[1])
    for ri, rp in enumerate(placed):
        tr = ET.SubElement(tbl, HP + "tr"); is_head = ri < nhead
        for (_, ci, cs, rs, cell) in rp:
            proto = pick(head_tcs if is_head else body_tcs, ci if cs == 1 else (0 if ci == 0 else (ncol - 1 if ci + cs >= ncol else 1)))
            tc = copy.deepcopy(proto)
            tc.set("header", "1" if is_head else "0")
            sl = tc.find(HP + "subList"); cp = sl.find(HP + "p")
            for old in sl.findall(HP + "p")[1:]: sl.remove(old)
            if isinstance(cell, list):
                sl.remove(cp)
                for b in cell: sl.append(block_elem(ctx, b))
            else:
                H.set_para_text(cp, cell_parts(cell)[0])
            sl.set("vertAlign", "CENTER")
            tc.find(HP + "cellAddr").set("colAddr", str(ci)); tc.find(HP + "cellAddr").set("rowAddr", str(ri))
            tc.find(HP + "cellSpan").set("colSpan", str(cs)); tc.find(HP + "cellSpan").set("rowSpan", str(rs))
            csz = tc.find(HP + "cellSz"); csz.set("width", str(sum(widths[ci:ci + cs]))); csz.set("height", str(1800 * rs))
            tr.append(tc)
    tbl.set("rowCnt", str(len(rows))); tbl.set("colCnt", str(ncol)); tbl.set("repeatHeader", "1" if nhead else "0")
    tbl.find(HP + "sz").set("height", str(1800 * len(rows)))
    return p


def image_size(data: bytes) -> tuple[int, int]:
    """PNG 는 머리에서, 그 밖(JPEG)은 PIL 이 있으면 PIL 로 픽셀 크기."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return H.png_size(data)
    try:
        from PIL import Image
        import io
        return Image.open(io.BytesIO(data)).size
    except Exception:
        return H.png_size(data)


def form_pic(ctx: Ctx, src: str, caption: str):
    img = H.load_image(src) if src.startswith("/") else None
    if img is None and Path(src).exists():
        data = Path(src).read_bytes(); w, h = image_size(data); img = (data, Path(src).suffix.lstrip(".").lower() or "png", w, h)
    if img is None:
        return [form_para(ctx, "note", f"[그림] {caption}")]
    data, ext, pw, ph = img
    note = ctx.proto["note"]; run = note.find(H.HP + "run")
    ids = {"char": {"caption": run.get("charPrIDRef"), "body": run.get("charPrIDRef")}, "para": {"fig": ctx.proto["blank"].get("paraPrIDRef")}}
    pic = H.pic_paragraph(ids, ctx.images.add(data, ext), pw, ph, caption or "그림")
    return [pic, form_para(ctx, "note", caption)] if caption else [pic]


def block_elems(ctx: Ctx, b: dict) -> list:
    """Block 하나 → 양식 문단 원소 목록(그림은 캡션까지 두 개)."""
    if "table" in b:
        return [form_table(ctx, b["table"], head=b.get("head", True), widths=b.get("widths"), head_rows=b.get("headRows"))]
    if "pic" in b:
        return form_pic(ctx, str(b["pic"]), str(b.get("caption") or ""))
    text = "".join(str(t) for t, _ in (b.get("segs") or []))
    role = ROLE.get(b.get("p", "body"), "o")
    if role is None or (role == "note" and b.get("p") == "kicker"):
        return []
    if role == "sec":
        return [form_section(ctx, text, page_break=(ctx.sec_n == 0 and getattr(ctx, "cover_on", False)))]
    if role == "blank":
        return [form_para(ctx, "blank", "")]
    if not text:
        return [form_para(ctx, "blank", "")]
    return [form_para(ctx, role, text)]


def block_elem(ctx: Ctx, b: dict):
    els = block_elems(ctx, b)
    return els[0] if els else form_para(ctx, "blank", "")


# ── 디자인 스타일 판(form=False, hwpx_report 와 같은 모양) — 이전 경로 유지 ──
def merge_table(ctx: Ctx, rows, head=True, widths=None, fill=None, margin=320, head_rows=None):
    HP = H.HP; ids = ctx.ids
    nhead = int(head_rows) if head_rows is not None else (1 if head else 0)
    occ: set = set(); ncol = 0; placed = []
    for ri, row in enumerate(rows):
        col = 0; rp = []
        for cell in row:
            while (ri, col) in occ: col += 1
            _, cs, rs = cell_parts(cell)
            for dr in range(rs):
                for dc in range(cs): occ.add((ri + dr, col + dc))
            rp.append((ri, col, cs, rs, cell)); col += cs
        ncol = max(ncol, col); placed.append(rp)
    for ri in range(len(rows)):
        for ci in range(ncol):
            if (ri, ci) not in occ:
                placed[ri].append((ri, ci, 1, 1, "")); occ.add((ri, ci))
        placed[ri].sort(key=lambda x: x[1])
    if not widths or len(widths) != ncol:
        lens = [max([len(cell_parts(c)[0]) for (r, ci, cs, rs, c) in sum(placed, []) if ci == col and cs == 1] + [6]) for col in range(ncol)]
        tot = sum(lens); widths = [max(int(H.TEXT_W * l / tot), int(H.TEXT_W * 0.08)) for l in lens]
    scale = H.TEXT_W / sum(widths); widths = [int(w * scale) for w in widths]; widths[-1] += H.TEXT_W - sum(widths)
    p = H.clone(ctx.tbl_proto); p.set("paraPrIDRef", ids["para"]["body"])
    tbl = p.find(".//" + HP + "tbl"); ctx.tbl_seq += 1; tbl.set("id", str(2085242905 + ctx.tbl_seq))
    trs = tbl.findall(HP + "tr"); tr_proto = trs[1] if len(trs) > 1 else trs[0]
    for tr in trs: tbl.remove(tr)
    tbl.set("borderFillIDRef", ids["border"]["none"]); tbl.set("repeatHeader", "1" if nhead else "0")
    tbl.find(HP + "sz").set("width", str(H.TEXT_W)); tbl.find(HP + "sz").set("height", str(max(1, len(rows)) * 1460))
    im = tbl.find(HP + "inMargin")
    if im is not None:
        im.set("left", str(margin)); im.set("right", str(margin)); im.set("top", "230"); im.set("bottom", "230")
    tc_proto = tr_proto.findall(HP + "tc")[0]
    NUMERIC = re.compile(r"[\d,.%~\-–\s곳명건개년월억원만천+]+")
    for ri, rp in enumerate(placed):
        tr = ET.SubElement(tbl, HP + "tr"); is_head = ri < nhead
        for (_, ci, cs, rs, cell) in rp:
            text = cell_parts(cell)[0]
            tc = H.clone(tc_proto); tc.set("header", "1" if is_head else "0")
            tc.set("borderFillIDRef", ids["border"][fill or ("th" if is_head else ("td_alt" if ri % 2 == 0 else "td"))])
            sl = tc.find(HP + "subList")
            for old in sl.findall(HP + "p"): sl.remove(old)
            sl.set("vertAlign", "CENTER" if (is_head or rs > 1) else "TOP")
            if isinstance(cell, list):
                for b in cell: sl.append(block_elem(ctx, b))
            else:
                pn = "th" if is_head else ("tdc" if NUMERIC.fullmatch(text or "x") else "td")
                sl.append(H.para(ids, pn, [(text, "th" if is_head else "td")]))
            tc.find(HP + "cellAddr").set("colAddr", str(ci)); tc.find(HP + "cellAddr").set("rowAddr", str(ri))
            tc.find(HP + "cellSpan").set("colSpan", str(cs)); tc.find(HP + "cellSpan").set("rowSpan", str(rs))
            csz = tc.find(HP + "cellSz"); csz.set("width", str(sum(widths[ci:ci + cs]))); csz.set("height", str(1460 * rs))
            cm = tc.find(HP + "cellMargin")
            if cm is not None:
                cm.set("left", str(margin)); cm.set("right", str(margin)); cm.set("top", "230"); cm.set("bottom", "230")
            tr.append(tc)
    tbl.set("rowCnt", str(len(rows))); tbl.set("colCnt", str(ncol))
    return p


def design_elem(ctx: Ctx, b: dict):
    if "table" in b:
        return merge_table(ctx, b["table"], head=b.get("head", True), widths=b.get("widths"), fill=b.get("fill"), margin=int(b.get("margin", 320)), head_rows=b.get("headRows"))
    if "pic" in b:
        src = str(b["pic"]); img = H.load_image(src) if src.startswith("/") else None
        if img is None and Path(src).exists():
            data = Path(src).read_bytes(); w, h = image_size(data); img = (data, Path(src).suffix.lstrip(".").lower() or "png", w, h)
        if img is None:
            return H.para(ctx.ids, "note", [(f"[그림] {b.get('caption', '')}", "note")])
        data, ext, pw, ph = img
        return H.pic_paragraph(ctx.ids, ctx.images.add(data, ext), pw, ph, str(b.get("caption") or "그림"))
    segs = [(str(t), str(c)) for t, c in (b.get("segs") or [])] or [("", "body")]
    return H.para(ctx.ids, b.get("p", "body") if b.get("p", "body") in ctx.ids["para"] else "body", [(t, c if c in ctx.ids["char"] else "body") for t, c in segs])


def add_linesegs(ctx: Ctx) -> None:
    """실험: 최상위 문단마다 줄 배치 어림값(vertsize=글자 크기, baseline≈0.85, spacing=크기×(줄간격−100)/100, vertpos 누적)."""
    HP = H.HP
    h = ctx.header_xml
    cps = {m.group(1): int(m.group(2)) for m in re.finditer(r'<hh:charPr id="(\d+)" height="(\d+)"', h)}
    pps = {m.group(1): int(m.group(2)) for m in re.finditer(r'<hh:paraPr id="(\d+)".*?<hh:lineSpacing type="\w+" value="(\d+)"', h, re.S)}
    y = 0
    for p in [e for e in ctx.root if e.tag == HP + "p"]:
        if p.find(HP + "linesegarray") is not None:
            continue
        run = p.find(HP + "run"); tbl = p.find(f".//{HP}tbl"); pic = p.find(f".//{HP}pic")
        if tbl is not None: size = int(tbl.find(HP + "sz").get("height", 1460))
        elif pic is not None: size = int(pic.find(HP + "sz").get("height", 3000))
        else: size = cps.get(run.get("charPrIDRef") if run is not None else "", 1000)
        ls = pps.get(p.get("paraPrIDRef"), 160) if tbl is None and pic is None else 100
        spacing = int(size * (ls - 100) / 100)
        lsa = ET.SubElement(p, HP + "linesegarray")
        ET.SubElement(lsa, HP + "lineseg", {"textpos": "0", "vertpos": str(y), "vertsize": str(size), "textheight": str(size), "baseline": str(int(size * 0.85)),
                                           "spacing": str(spacing), "horzpos": "0", "horzsize": str(H.TEXT_W), "flags": "393216"})
        y += size + spacing


def build_hwpx(blocks: list[dict], out: Path, preview: str = "", all_ns: bool = True, lineseg: bool = False, form: bool = True, cover: bool = False, plain: bool = False) -> Path:
    ctx = Ctx(form=form)
    if form:
        ctx.cover_on = cover
        if cover:
            title = next((("".join(str(t) for t, _ in b.get("segs") or [])) for b in blocks if b.get("p") == "title"), "")
            kick = next((("".join(str(t) for t, _ in b.get("segs") or [])) for b in blocks if b.get("p") == "kicker"), "")
            ctx.root.append(form_cover(ctx, title, kick))
        for b in blocks:
            if cover and b.get("p") == "title":
                continue   # 표지에 넣었으므로 절 머리표로 또 만들지 않는다
            for e in block_elems(ctx, b):
                ctx.root.append(e)
    else:
        if plain:
            ctx.header_xml = re.sub(r"<hc:fillBrush>.*?</hc:fillBrush>", "", ctx.header_xml, flags=re.S)
            ctx.header_xml = ctx.header_xml.replace(f'borderFillIDRef="{ctx.ids["border"]["none"]}"', 'borderFillIDRef="3"')
        for b in blocks:
            ctx.root.append(design_elem(ctx, b))
    H.drop_linesegs(ctx.root)
    if lineseg:
        add_linesegs(ctx)
    sec = ET.tostring(ctx.root, encoding="unicode")
    if all_ns:
        sec = re.sub(r"^<hs:sec\b[^>]*>", ctx.root_tag, sec, count=1)
    new_sec = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' + sec
    manifest = "".join(f'<opf:item id="{bid}" href="BinData/{bid}.{ext}" media-type="image/{"jpeg" if ext == "jpg" else ext}" isEmbeded="1"/>' for bid, _, ext in ctx.images.files)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as zo:
        for n in ctx.z.namelist():
            data = ctx.z.read(n)
            if n == "Contents/section0.xml": data = new_sec.encode("utf-8")
            elif n == "Contents/header.xml": data = ctx.header_xml.encode("utf-8")
            elif n == "Contents/content.hpf": data = data.decode("utf-8").replace("</opf:manifest>", manifest + "</opf:manifest>", 1).encode("utf-8")
            elif n == "Preview/PrvText.txt": data = (preview or "").encode("utf-8")
            zo.writestr(zipfile.ZipInfo(n), data, compress_type=zipfile.ZIP_STORED if n == "mimetype" else zipfile.ZIP_DEFLATED)
        for bid, data, ext in ctx.images.files:
            zo.writestr(zipfile.ZipInfo(f"BinData/{bid}.{ext}"), data, compress_type=zipfile.ZIP_DEFLATED)
    return out


if __name__ == "__main__":
    import json
    if len(sys.argv) < 3:
        print("사용: python3 scripts/hwpx_blocks.py <blocks.json> <out.hwpx> [--cover] [--design] [--lineseg] [--no-ns]"); sys.exit(1)
    blocks = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    build_hwpx(blocks, Path(sys.argv[2]), all_ns="--no-ns" not in sys.argv, lineseg="--lineseg" in sys.argv, form="--design" not in sys.argv, cover="--cover" in sys.argv)
    print("→", sys.argv[2])
