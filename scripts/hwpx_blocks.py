#!/usr/bin/env python3
"""Block 목록 → HWPX(양식 복제, docs/prompts/site_hwpx_skill.md 3절). 표준 라이브러리 + hwpx_report.py.

**형식은 운영자가 Drive 에 올린 공무원 한글 양식 그대로**(운영자 지시 2026-10-06 '내가 올린 공무원 한글 파일 형식이 아니다'):
scripts/data/hwpx/report_basic.hwpx 의 문단·표를 deepcopy 해 글자만 바꾼다 — 절 머리표(Ⅰ Ⅱ … 표), □ HY헤드라인M 15pt, ○ 휴먼명조 14pt, - 14pt,
※ 11pt, 표(맑은 고딕 12pt, 머리 행·본문 행·첫/가운데/끝 열의 테두리 모양 그대로), 표지(제목 표). header.xml 은 양식 그대로(스타일을 덧붙이지 않는다 → id 충돌 없음).
브라우저 판(src/scripts/hwpx.ts)은 hwpx_template.py 가 내보낸 같은 원형 조각을 쓴다. 디자인 스타일 판(hwpx_report.py 의 PARA_SPECS)은 form=False.
  Block = {"p": 문단 모양 이름, "segs": [[글, 글자 모양 이름], ...]}   # 이름 → 양식 역할: title/h2 → 절 머리표, h3 → □, body → ○, bullet → -, note/caption/src → ※
        | {"table": rows, "head": bool, "headRows": n, "widths": [HWPUNIT...]}
        | {"pic": "public/ 아래 경로 또는 파일 경로", "caption": 글}
        | {"chart": {"type": "bar"|"hbar"|"line", "title": 글, "unit": 글, "categories": [...], "series": [{"name": 글, "values": [...]}]},
           "caption": 글, "png": 그림(한글이 아닌 프로그램용 대체 그림, 없어도 됨)}
          → 한글 차트 개체(hp:chart + Chart/chartN.xml, ECMA-376 chartML) — 한글에서 차트 편집·데이터 고치기가 된다(운영자 지시 2026-10-29
            '그래프도 한글 프로그램 형식으로'). png 가 있으면 한글 저장 방식처럼 hp:switch(case ooxmlchart → 차트, default → 그림)로 감싼다.
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


C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
CHART_COLORS = ["1B4F9B", "E69F00", "009E73", "D55E00", "CC79A7", "56B4E9"]   # figure.py 팔레트와 같은 순서


def _x(t) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def chart_xml(spec: dict) -> str:
    """막대(세로·가로)·꺾은선 chartML. 값은 캐시(strCache·numCache)로 넣는다 — 한글은 이 캐시로 그리고, 데이터 편집 창에도 이 값이 뜬다."""
    kind = spec.get("type", "bar")
    cats = [str(c) for c in spec["categories"]]
    series = spec["series"]
    font = '<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="{sz}"{b}><a:latin typeface="맑은 고딕"/><a:ea typeface="맑은 고딕"/></a:defRPr></a:pPr><a:endParaRPr lang="ko-KR"/></a:p></c:txPr>'
    col = lambda i: chr(ord("B") + i)
    sers = []
    for i, se in enumerate(series):
        pts_c = "".join(f'<c:pt idx="{k}"><c:v>{_x(c)}</c:v></c:pt>' for k, c in enumerate(cats))
        pts_v = "".join(f'<c:pt idx="{k}"><c:v>{v}</c:v></c:pt>' for k, v in enumerate(se["values"]) if v is not None)
        color = CHART_COLORS[i % len(CHART_COLORS)]
        sp = (f'<c:spPr><a:ln w="28575" cap="rnd"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln></c:spPr><c:marker><c:symbol val="circle"/><c:size val="5"/></c:marker>'
              if kind == "line" else f'<c:spPr><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></c:spPr><c:invertIfNegative val="0"/>')
        n = len(cats) + 1
        sers.append(f'<c:ser><c:idx val="{i}"/><c:order val="{i}"/>'
                    f'<c:tx><c:strRef><c:f>Sheet1!${col(i)}$1</c:f><c:strCache><c:ptCount val="1"/><c:pt idx="0"><c:v>{_x(se.get("name", ""))}</c:v></c:pt></c:strCache></c:strRef></c:tx>{sp}'
                    f'<c:dLbls><c:numFmt formatCode="General" sourceLinked="0"/><c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>{font.format(sz=900, b="")}'
                    f'<c:showLegendKey val="0"/><c:showVal val="1"/><c:showCatName val="0"/><c:showSerName val="0"/><c:showPercent val="0"/><c:showBubbleSize val="0"/></c:dLbls>'
                    f'<c:cat><c:strRef><c:f>Sheet1!$A$2:$A${n}</c:f><c:strCache><c:ptCount val="{len(cats)}"/>{pts_c}</c:strCache></c:strRef></c:cat>'
                    f'<c:val><c:numRef><c:f>Sheet1!${col(i)}$2:${col(i)}${n}</c:f><c:numCache><c:formatCode>General</c:formatCode><c:ptCount val="{len(cats)}"/>{pts_v}</c:numCache></c:numRef></c:val>'
                    + ('<c:smooth val="0"/>' if kind == "line" else "") + '</c:ser>')
    ax = '<c:axId val="50010001"/><c:axId val="50010002"/>'
    if kind == "line":
        plot = f'<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>{"".join(sers)}<c:marker val="1"/>{ax}</c:lineChart>'
    else:
        plot = (f'<c:barChart><c:barDir val="{"bar" if kind == "hbar" else "col"}"/><c:grouping val="clustered"/><c:varyColors val="0"/>{"".join(sers)}'
                f'<c:gapWidth val="80"/>{ax}</c:barChart>')
    hbar = kind == "hbar"
    grid = '<c:majorGridlines><c:spPr><a:ln w="6350"><a:solidFill><a:srgbClr val="D9D9D9"/></a:solidFill></a:ln></c:spPr></c:majorGridlines>'
    line = '<c:spPr><a:ln w="6350"><a:solidFill><a:srgbClr val="BFBFBF"/></a:solidFill></a:ln></c:spPr>'
    cat_ax = (f'<c:catAx><c:axId val="50010001"/><c:scaling><c:orientation val="{"maxMin" if hbar else "minMax"}"/></c:scaling><c:delete val="0"/>'
              f'<c:axPos val="{"l" if hbar else "b"}"/><c:numFmt formatCode="General" sourceLinked="0"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/>'
              f'<c:tickLblPos val="nextTo"/>{line}{font.format(sz=1000, b="")}<c:crossAx val="50010002"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/></c:catAx>')
    unit = spec.get("unit") or ""
    val_title = (f'<c:title><c:tx><c:rich><a:bodyPr rot="{0 if hbar else -5400000}" vert="horz"/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="900" b="0"><a:latin typeface="맑은 고딕"/><a:ea typeface="맑은 고딕"/></a:defRPr></a:pPr>'
                 f'<a:r><a:rPr lang="ko-KR" sz="900" b="0"><a:latin typeface="맑은 고딕"/><a:ea typeface="맑은 고딕"/></a:rPr><a:t>{_x(unit)}</a:t></a:r></a:p></c:rich></c:tx><c:overlay val="0"/></c:title>') if unit else ""
    val_ax = (f'<c:valAx><c:axId val="50010002"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="{"b" if hbar else "l"}"/>{grid}{val_title}'
              f'<c:numFmt formatCode="#,##0.##" sourceLinked="0"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
              f'<c:spPr><a:ln><a:noFill/></a:ln></c:spPr>{font.format(sz=900, b="")}<c:crossAx val="50010001"/><c:crosses val="{"max" if hbar else "autoZero"}"/><c:crossBetween val="between"/></c:valAx>')
    title = spec.get("title") or ""
    t = (f'<c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="1200" b="1"><a:latin typeface="맑은 고딕"/><a:ea typeface="맑은 고딕"/></a:defRPr></a:pPr>'
         f'<a:r><a:rPr lang="ko-KR" sz="1200" b="1"><a:latin typeface="맑은 고딕"/><a:ea typeface="맑은 고딕"/></a:rPr><a:t>{_x(title)}</a:t></a:r></a:p></c:rich></c:tx><c:overlay val="0"/></c:title>'
         '<c:autoTitleDeleted val="0"/>') if title else '<c:autoTitleDeleted val="1"/>'
    legend = (f'<c:legend><c:legendPos val="b"/><c:overlay val="0"/>{font.format(sz=900, b="")}</c:legend>') if len(series) > 1 else ""
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<c:chartSpace xmlns:c="{C_NS}" xmlns:a="{A_NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<c:date1904 val="0"/><c:lang val="ko-KR"/><c:roundedCorners val="0"/>'
            f'<c:chart>{t}<c:plotArea><c:layout/>{plot}{cat_ax}{val_ax}<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr></c:plotArea>{legend}'
            '<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart>'
            '<c:spPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:ln><a:noFill/></a:ln></c:spPr>'
            f'{font.format(sz=1000, b="")}</c:chartSpace>')


def form_chart(ctx: Ctx, spec: dict, caption: str, png: str = ""):
    """한글 차트 개체 문단(가운데, 글자처럼 취급) + ※ 캡션."""
    if not hasattr(ctx, "charts"):
        ctx.charts = []
    n = len(ctx.charts) + 1
    path = f"Chart/chart{n}.xml"
    ctx.charts.append((path, chart_xml(spec).encode("utf-8")))
    w = H.MAX_IMG_W
    h = int(spec.get("height") or (min(26000, 9000 + 2200 * len(spec["categories"])) if spec.get("type") == "hbar" else 22000))
    HPN = H.NS["hp"]
    oid = 1900000000 + n
    chart = (f'<hp:chart xmlns:hp="{HPN}" id="{oid}" zOrder="{20 + n}" numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" chartIDRef="{path}">'
             f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
             '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
             '<hp:outMargin left="0" right="0" top="0" bottom="0"/></hp:chart>')
    blank = ctx.proto["blank"]
    p = copy.deepcopy(blank)
    for r in p.findall(H.HP + "run"):
        p.remove(r)
    char_id = ctx.proto["note"].find(H.HP + "run").get("charPrIDRef")
    run = ET.SubElement(p, H.HP + "run", {"charPrIDRef": char_id})
    el = ET.fromstring(chart)
    if png and Path(png).exists():
        # 한글 저장 방식처럼 hp:switch — 차트를 읽는 프로그램은 차트, 그 밖은 그림
        pic_p = form_pic(ctx, png, "")[0]
        pic = pic_p.find(f".//{H.HP}pic")
        sw = ET.SubElement(run, H.HP + "switch")
        case = ET.SubElement(sw, H.HP + "case", {H.HP + "required-namespace": H.NS["ooxmlchart"]})
        case.append(el)
        if pic is not None:
            pic.find(H.HP + "sz").set("width", str(w)); pic.find(H.HP + "sz").set("height", str(h))
            ET.SubElement(sw, H.HP + "default").append(pic)
    else:
        run.append(el)
    ET.SubElement(run, H.HP + "t")
    return [p, form_para(ctx, "note", caption)] if caption else [p]


def block_elems(ctx: Ctx, b: dict) -> list:
    """Block 하나 → 양식 문단 원소 목록(그림은 캡션까지 두 개)."""
    if "table" in b:
        return [form_table(ctx, b["table"], head=b.get("head", True), widths=b.get("widths"), head_rows=b.get("headRows"))]
    if "pic" in b:
        return form_pic(ctx, str(b["pic"]), str(b.get("caption") or ""))
    if "chart" in b:
        return form_chart(ctx, b["chart"], str(b.get("caption") or ""), str(b.get("png") or ""))
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
    out = Path(out)
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
        for path, data in getattr(ctx, "charts", []):   # 차트 부분은 manifest 에 올리지 않는다(한글 저장 파일과 같음)
            zo.writestr(zipfile.ZipInfo(path), data, compress_type=zipfile.ZIP_DEFLATED)
    return out


if __name__ == "__main__":
    import json
    if len(sys.argv) < 3:
        print("사용: python3 scripts/hwpx_blocks.py <blocks.json> <out.hwpx> [--cover] [--design] [--lineseg] [--no-ns]"); sys.exit(1)
    blocks = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    build_hwpx(blocks, Path(sys.argv[2]), all_ns="--no-ns" not in sys.argv, lineseg="--lineseg" in sys.argv, form="--design" not in sys.argv, cover="--cover" in sys.argv)
    print("→", sys.argv[2])
