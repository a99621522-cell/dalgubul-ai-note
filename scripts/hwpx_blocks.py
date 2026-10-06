#!/usr/bin/env python3
"""Block 목록 → HWPX(양식 복제, docs/prompts/site_hwpx_skill.md 3절, 2026-10-06). 표준 라이브러리 + hwpx_report.py.

브라우저 판(src/scripts/hwpx.ts)과 같은 입력(Block)을 받아 같은 양식(scripts/data/hwpx/report_basic.hwpx)·같은 스타일 id 로 파일을 만든다.
시험 파일(hwpx_test.py)과 러너에서 미리 만드는 문서가 쓴다. 양식 문단·표·칸은 ET 로 복제(deepcopy)하고 글자만 바꾼다.
  Block = {"p": 문단 모양 이름, "segs": [[글, 글자 모양 이름], ...]}
        | {"table": rows, "head": bool, "widths": [HWPUNIT...], "fill": 테두리 key, "margin": n}
  칸    = str | {"t": 글, "cs": colspan, "rs": rowspan, "p": 문단 모양, "char": 글자 모양} | [Block, ...]
  그림  = {"pic": "public/ 아래 경로 또는 절대 경로", "caption": 글}
옵션: all_ns=True 면 section 루트에 양식의 네임스페이스 선언을 모두 둔다(ET 는 쓰인 것만 남긴다 — 1절 진단 항목 ⑩).
      lineseg=True 면 최상위 문단마다 줄 배치(hp:linesegarray)를 어림으로 넣는다(실험 — 한글이 없는 값을 다시 계산하는지, 있는 값을 믿는지 가리기 위함).
"""
import re, sys, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hwpx_report as H  # noqa: E402

NUMERIC = re.compile(r"[\d,.%~\-–\s곳명건개년월억원만천+]+")


class Ctx:
    def __init__(self):
        self.z = zipfile.ZipFile(H.TEMPLATE)
        sec_xml = self.z.read("Contents/section0.xml").decode("utf-8")
        H.NS.clear(); H.NS.update(dict(re.findall(r'xmlns:(\w+)="([^"]+)"', sec_xml[:3000])))
        for k, v in H.NS.items():
            ET.register_namespace(k, v)
        H.HP = "{%s}" % H.NS["hp"]
        self.root_tag = re.search(r"<hs:sec\b[^>]*>", sec_xml).group(0)
        self.root = ET.fromstring(sec_xml)
        top = list(self.root)
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


def cell_parts(cell):
    if isinstance(cell, dict):
        return str(cell.get("t", "")), int(cell.get("cs", 1) or 1), int(cell.get("rs", 1) or 1), cell.get("p"), cell.get("char")
    return cell, 1, 1, None, None


def merge_table(ctx: Ctx, rows, head=True, widths=None, fill=None, margin=320, head_rows=None):
    """병합(colspan·rowspan) 표. 각 행은 '덮이지 않은 칸'만 나열한다(HTML 과 같은 규칙). 격자 자리는 cellAddr 로 적는다."""
    HP = H.HP; ids = ctx.ids
    # 격자 폭 세기
    occ: set = set(); ncol = 0; placed = []   # (ri, ci, cs, rs, cell)
    for ri, row in enumerate(rows):
        col = 0; rp = []
        for cell in row:
            while (ri, col) in occ: col += 1
            _, cs, rs, _, _ = cell_parts(cell)
            for dr in range(rs):
                for dc in range(cs): occ.add((ri + dr, col + dc))
            rp.append((ri, col, cs, rs, cell)); col += cs
        ncol = max(ncol, col); placed.append(rp)
    # 비는 자리는 빈 칸으로 채운다
    for ri in range(len(rows)):
        for ci in range(ncol):
            if (ri, ci) not in occ:
                placed[ri].append((ri, ci, 1, 1, "")); occ.add((ri, ci))
        placed[ri].sort(key=lambda x: x[1])
    if not widths or len(widths) != ncol:
        lens = [max([len(cell_parts(c)[0]) for (r, ci, cs, rs, c) in sum(placed, []) if ci == col and cs == 1] + [6]) for col in range(ncol)]
        tot = sum(lens); widths = [max(int(H.TEXT_W * l / tot), int(H.TEXT_W * 0.08)) for l in lens]
    scale = H.TEXT_W / sum(widths); widths = [int(w * scale) for w in widths]
    widths[-1] += H.TEXT_W - sum(widths)
    p = H.clone(ctx.tbl_proto); p.set("paraPrIDRef", ids["para"]["body"])
    tbl = p.find(".//" + HP + "tbl")
    ctx.tbl_seq += 1; tbl.set("id", str(2085242905 + ctx.tbl_seq))
    trs = tbl.findall(HP + "tr"); tr_proto = trs[1] if len(trs) > 1 else trs[0]
    for tr in trs: tbl.remove(tr)
    nhead = int(head_rows) if head_rows is not None else (1 if head else 0)
    tbl.set("borderFillIDRef", ids["border"]["none"]); tbl.set("repeatHeader", "1" if nhead else "0")
    tbl.find(HP + "sz").set("width", str(H.TEXT_W)); tbl.find(HP + "sz").set("height", str(max(1, len(rows)) * 1460))
    im = tbl.find(HP + "inMargin")
    if im is not None:
        im.set("left", str(margin)); im.set("right", str(margin)); im.set("top", "230"); im.set("bottom", "230")
    tc_proto = tr_proto.findall(HP + "tc")[0]
    for ri, rp in enumerate(placed):
        tr = ET.SubElement(tbl, HP + "tr"); is_head = ri < nhead
        for (_, ci, cs, rs, cell) in rp:
            text, _, _, pname, cname = cell_parts(cell)
            tc = H.clone(tc_proto)
            tc.set("header", "1" if is_head else "0")
            tc.set("borderFillIDRef", ids["border"][fill or ("th" if is_head else ("td_alt" if ri % 2 == 0 else "td"))])
            sl = tc.find(HP + "subList")
            for old in sl.findall(HP + "p"): sl.remove(old)
            sl.set("vertAlign", "CENTER" if (is_head or rs > 1) else "TOP")
            if isinstance(cell, list):
                for b in cell: sl.append(block_elem(ctx, b))
            else:
                pn = pname or ("th" if is_head else ("tdc" if NUMERIC.fullmatch(text or "x") else "td"))
                sl.append(H.para(ids, pn, [(text, cname or ("th" if is_head else "td"))]))
            tc.find(HP + "cellAddr").set("colAddr", str(ci)); tc.find(HP + "cellAddr").set("rowAddr", str(ri))
            tc.find(HP + "cellSpan").set("colSpan", str(cs)); tc.find(HP + "cellSpan").set("rowSpan", str(rs))
            csz = tc.find(HP + "cellSz"); csz.set("width", str(sum(widths[ci:ci + cs]))); csz.set("height", str(1460 * rs))
            cm = tc.find(HP + "cellMargin")
            if cm is not None:
                cm.set("left", str(margin)); cm.set("right", str(margin)); cm.set("top", "230"); cm.set("bottom", "230")
            tr.append(tc)
    tbl.set("rowCnt", str(len(rows))); tbl.set("colCnt", str(ncol))
    return p


def block_elem(ctx: Ctx, b: dict):
    if "table" in b:
        return merge_table(ctx, b["table"], head=b.get("head", True), widths=b.get("widths"), fill=b.get("fill"), margin=int(b.get("margin", 320)), head_rows=b.get("headRows"))
    if "pic" in b:
        src = str(b["pic"])
        img = H.load_image(src) if src.startswith("/") else None   # 사이트 경로(/figures/…)
        if img is None and Path(src).exists():                      # 파일 경로
            data = Path(src).read_bytes(); w, h = H.png_size(data); img = (data, Path(src).suffix.lstrip(".").lower() or "png", w, h)
        if img is None:
            return H.para(ctx.ids, "note", [(f"[그림] {b.get('caption', '')}", "note")])
        data, ext, pw, ph = img
        return H.pic_paragraph(ctx.ids, ctx.images.add(data, ext), pw, ph, str(b.get("caption") or "그림"))
    segs = [(str(t), str(c)) for t, c in (b.get("segs") or [])] or [("", "body")]
    return H.para(ctx.ids, b.get("p", "body") if b.get("p", "body") in ctx.ids["para"] else "body", [(t, c if c in ctx.ids["char"] else "body") for t, c in segs])


def add_linesegs(ctx: Ctx) -> None:
    """실험: 최상위 문단마다 줄 배치를 어림으로 넣는다(양식 값의 규칙: vertsize=textheight=글자 크기, baseline≈0.85, spacing=크기×(줄간격−100)/100, vertpos 누적)."""
    HP = H.HP
    size_of = {v: s for (n, f, s, c, b) in H.CHAR_SPECS for k, v in ctx.ids["char"].items() if k == n}
    ls_of = {v: ls for (n, al, ls, pv, nx, lf, it, kp, bd) in H.PARA_SPECS for k, v in ctx.ids["para"].items() if k == n}
    y = 0
    for p in [e for e in ctx.root if e.tag == HP + "p"]:
        if p.find(HP + "linesegarray") is not None:
            continue
        run = p.find(HP + "run"); tbl = p.find(f".//{HP}tbl"); pic = p.find(f".//{HP}pic")
        if tbl is not None: size = int(tbl.find(HP + "sz").get("height", 1460))
        elif pic is not None: size = int(pic.find(HP + "sz").get("height", 3000))
        else: size = size_of.get(run.get("charPrIDRef") if run is not None else "", 1000)
        ls = ls_of.get(p.get("paraPrIDRef"), 160) if tbl is None and pic is None else 100
        spacing = int(size * (ls - 100) / 100)
        lsa = ET.SubElement(p, HP + "linesegarray")
        ET.SubElement(lsa, HP + "lineseg", {"textpos": "0", "vertpos": str(y), "vertsize": str(size), "textheight": str(size), "baseline": str(int(size * 0.85)),
                                           "spacing": str(spacing), "horzpos": "0", "horzsize": str(H.TEXT_W), "flags": "393216"})
        y += size + spacing


def build_hwpx(blocks: list[dict], out: Path, preview: str = "", all_ns: bool = True, lineseg: bool = False, plain: bool = False) -> Path:
    """plain=True: 덧붙인 테두리·채움 모양에서 채움(hc:fillBrush)을 모두 빼고 글자 모양의 테두리 참조를 양식 기본(id 3)으로 — 채움·테두리 참조가 깨짐 원인인지 가르는 실험(2026-10-06 운영자 화면: 본문 전체가 검게 칠해짐)"""
    ctx = Ctx()
    if plain:
        ctx.header_xml = re.sub(r"<hc:fillBrush>.*?</hc:fillBrush>", "", ctx.header_xml, flags=re.S)
        none_id = ctx.ids["border"]["none"]
        ctx.header_xml = ctx.header_xml.replace(f'borderFillIDRef="{none_id}"', 'borderFillIDRef="3"')
    for b in blocks:
        ctx.root.append(block_elem(ctx, b))
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
        print("사용: python3 scripts/hwpx_blocks.py <blocks.json> <out.hwpx> [--lineseg] [--no-ns]"); sys.exit(1)
    blocks = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    build_hwpx(blocks, Path(sys.argv[2]), all_ns="--no-ns" not in sys.argv, lineseg="--lineseg" in sys.argv)
    print("→", sys.argv[2])
