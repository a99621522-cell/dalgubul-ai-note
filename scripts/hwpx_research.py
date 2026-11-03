#!/usr/bin/env python3
"""연구용역 보고서 양식 HWPX(운영자 지시 2026-11-02 '보고서 양식을 이런 형태로 바꿔' — 경상북도 연구용역 보고서 PDF 를 본보기로).

본보기의 짜임: 표지(위아래 파란 띠 사이 제목·부제, 날짜) → 목차·표 목차·그림 목차 → 장마다 간지(회색 바탕·원·'제N장'·절 목록)
→ 본문 '제 N 장' / '제 N 절' / '1.' / '가.' / □ / ○ / - / • / ※, 핵심 문장 상자(점선 녹색 상자), 표(남색 머리 행·첫 열 옅은 채움, 아래 [표 n]),
그림 아래 [그림 n], 쪽 머리말(오른쪽 위 보고서 이름), 쪽 번호 '- n -', 끝에 참고문헌·발행 정보.

글은 마크다운 비슷한 원고에서 읽는다(표준 라이브러리 + pyyaml):
  ---  title / subtitle / date / header(머리말 글) / note(발행 정보 비고) / sources: [{title,url,date}]  ---
  # 요약                 → 간지 없는 요약 장
  # 제1장 제목           → 간지 + '제 1 장 제목'
  ## 제1절 제목 / ### 1. 제목 / #### 가. 제목
  !! 핵심 문장           → 점선 상자
  □ / ○ / - / • / ※ 로 시작하는 줄 → 각 문단 모양, 그 밖의 줄은 줄글
  | 표 |  다음 줄 '[표] 캡션', 그다음 줄 '*출처: …'(선택)
  <figure><img src="..."><figcaption>캡션</figcaption></figure>
  **굵게**, __굵게 밑줄__
사용: python3 scripts/hwpx_research.py 원고.md -o 결과.hwpx
"""
import argparse, re, subprocess, sys, tempfile, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hwpx_report as H  # noqa: E402
import hwpx_blocks as B  # noqa: E402

G, M, HY = "0", "5", "6"          # 맑은 고딕 / 휴먼명조 / HY헤드라인M (양식 header.xml 글꼴 id)
NAVY, BLUE, INK, GRAY = "#1F3864", "#2E75B6", "#111111", "#555555"
LN = lambda w, c, t="SOLID": (t, w, c)

# 문단: (이름, 정렬, 줄간격%, 위, 아래, 왼, 오른, 첫줄(음수=내어쓰기), 다음과 함께, 테두리)
PARA = [
    ("cover_bar", "CENTER", 100, 0, 0, 0, 0, 0, 0, "bar"), ("cover_title", "CENTER", 150, 500, 200, 0, 0, 0, 1, None),
    ("cover_sub", "CENTER", 150, 200, 500, 0, 0, 0, 1, None), ("cover_date", "CENTER", 130, 0, 0, 0, 0, 0, 0, None),
    ("toc_head", "CENTER", 130, 0, 900, 15500, 15500, 0, 1, "box"), ("toc_ch", "LEFT", 150, 500, 150, 0, 0, 0, 1, None),
    ("toc_sec", "LEFT", 150, 100, 100, 700, 0, 0, 0, None), ("toc_item", "LEFT", 150, 60, 60, 1500, 0, 0, 0, None),
    ("chap", "LEFT", 130, 0, 700, 0, 0, 0, 1, None), ("sec", "LEFT", 130, 600, 450, 0, 0, 0, 1, None),
    ("item1", "LEFT", 140, 450, 300, 300, 0, 0, 1, None), ("item2", "LEFT", 140, 350, 250, 500, 0, 0, 1, None),
    ("sq", "JUSTIFY", 165, 300, 150, 1700, 0, -1000, 1, None), ("o", "JUSTIFY", 165, 220, 100, 2300, 0, -900, 0, None),
    ("dash", "JUSTIFY", 160, 100, 80, 3000, 0, -650, 0, None), ("dot", "JUSTIFY", 150, 60, 60, 3500, 0, -550, 0, None),
    ("note", "JUSTIFY", 155, 100, 100, 2800, 0, -900, 0, None), ("body", "JUSTIFY", 165, 150, 150, 1700, 0, 0, 0, None),
    ("caption", "CENTER", 130, 120, 500, 0, 0, 0, 0, None), ("src", "RIGHT", 120, 60, 0, 0, 0, 0, 1, None),
    ("fig", "CENTER", 100, 300, 100, 0, 0, 0, 1, None), ("key", "LEFT", 155, 0, 0, 0, 0, 0, 0, None),
    ("th", "CENTER", 130, 0, 0, 0, 0, 0, 0, None), ("td", "LEFT", 135, 0, 0, 0, 0, 0, 0, None), ("tdc", "CENTER", 135, 0, 0, 0, 0, 0, 0, None),
    ("hdr", "RIGHT", 100, 0, 0, 0, 0, 0, 0, "hdr"), ("ref", "JUSTIFY", 140, 60, 60, 900, 0, -900, 0, None),
    ("colo_title", "LEFT", 130, 0, 400, 0, 0, 0, 0, "colo"), ("colo", "LEFT", 170, 100, 100, 0, 0, 0, 0, None),
    ("spacer", "LEFT", 100, 0, 0, 0, 0, 0, 0, None),
]
# 글자: (이름, 글꼴, 크기×100, 색, 굵게, 밑줄)
CHAR = [
    ("cover_bar", G, 400, BLUE, False, False), ("cover_title", HY, 2600, INK, False, False), ("cover_sub", G, 1500, INK, True, False),
    ("cover_date", G, 1800, INK, True, False), ("toc_head", HY, 2000, INK, False, False), ("toc_ch", M, 1350, INK, True, False),
    ("toc_sec", M, 1200, INK, False, False), ("toc_item", M, 1100, INK, False, False),
    ("chap", HY, 2000, INK, False, False), ("sec", M, 1700, INK, True, False), ("item1", M, 1500, INK, True, False), ("item2", M, 1400, INK, True, False),
    ("sq", M, 1400, INK, False, False), ("sq_b", M, 1400, INK, True, False), ("sq_m", M, 1400, INK, True, False),
    ("o", M, 1300, INK, False, False), ("o_b", M, 1300, INK, True, False), ("o_u", M, 1300, INK, True, True),
    ("dash", M, 1200, INK, False, False), ("dash_b", M, 1200, INK, True, False), ("dash_u", M, 1200, INK, True, True),
    ("dot", G, 1000, "#333333", False, False), ("dot_b", G, 1000, "#333333", True, False), ("dot_u", G, 1000, "#333333", True, True),
    ("note", M, 1150, INK, False, False), ("note_b", M, 1150, INK, True, False), ("note_u", M, 1150, INK, True, True),
    ("body", M, 1300, INK, False, False), ("body_b", M, 1300, INK, True, False), ("body_u", M, 1300, INK, True, True),
    ("caption", M, 1050, "#333333", False, False), ("src", G, 850, GRAY, False, False),
    ("key", G, 1250, INK, True, False), ("key_mark", G, 1250, NAVY, True, False), ("key_u", G, 1250, INK, True, True),
    ("th", G, 1000, "#FFFFFF", True, False), ("td", G, 980, INK, False, False), ("td_b", G, 980, INK, True, False),
    ("hdr", G, 850, "#333333", False, False), ("hdr_mark", G, 850, "#7F7F7F", True, False),
    ("ref", G, 950, INK, False, False), ("colo_title", M, 1600, INK, False, False), ("colo", M, 1500, INK, False, False),
    ("spacer", G, 600, INK, False, False),
]
# 테두리·채움: (이름, 왼, 오른, 위, 아래, 채움)
BORDER = [
    ("none", None, None, None, None, None), ("bar", None, None, None, LN("2.0 mm", BLUE), None),
    ("box", LN("0.5 mm", INK), LN("0.5 mm", INK), LN("0.5 mm", INK), LN("0.5 mm", INK), None),
    ("hdr", None, None, None, LN("0.4 mm", INK), None), ("colo", None, None, None, LN("0.4 mm", INK), None),
    ("keybox", LN("0.25 mm", "#4E7F2E", "DASH"), LN("0.25 mm", "#4E7F2E", "DASH"), LN("0.25 mm", "#4E7F2E", "DASH"), LN("0.25 mm", "#4E7F2E", "DASH"), "#EEF5E6"),
    ("th", LN("0.12 mm", "#7F8FA6"), LN("0.12 mm", "#7F8FA6"), LN("0.12 mm", "#7F8FA6"), LN("0.12 mm", "#7F8FA6"), NAVY),
    ("td", LN("0.12 mm", "#7F8FA6"), LN("0.12 mm", "#7F8FA6"), LN("0.12 mm", "#7F8FA6"), LN("0.12 mm", "#7F8FA6"), None),
    ("td1", LN("0.12 mm", "#7F8FA6"), LN("0.12 mm", "#7F8FA6"), LN("0.12 mm", "#7F8FA6"), LN("0.12 mm", "#7F8FA6"), "#EAF0F8"),
]


def add_styles(header_xml: str):
    ids = {"para": {}, "char": {}, "border": {}}

    def next_id(tag):
        v = [int(x) for x in re.findall(r'<hh:%s id="(\d+)"' % tag, header_xml)]
        return (max(v) + 1) if v else 0

    def line(tag, s):
        return f'<hh:{tag} type="{s[0]}" width="{s[1]}" color="{s[2]}"/>' if s else f'<hh:{tag} type="NONE" width="0.1 mm" color="#000000"/>'
    b0, x = next_id("borderFill"), ""
    for i, (n, l, r, t, b, fill) in enumerate(BORDER):
        ids["border"][n] = str(b0 + i)
        x += (f'<hh:borderFill id="{b0 + i}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0"><hh:slash type="NONE" Crooked="0" isCounter="0"/>'
              '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>' + line("leftBorder", l) + line("rightBorder", r) + line("topBorder", t) + line("bottomBorder", b)
              + '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
              + (f'<hc:fillBrush><hc:winBrush faceColor="{fill}" hatchColor="#000000" alpha="0"/></hc:fillBrush>' if fill else "") + "</hh:borderFill>")
    n = int(re.search(r'<hh:borderFills itemCnt="(\d+)"', header_xml).group(1)) + len(BORDER)
    header_xml = re.sub(r'<hh:borderFills itemCnt="\d+"', f'<hh:borderFills itemCnt="{n}"', header_xml, 1).replace("</hh:borderFills>", x + "</hh:borderFills>", 1)
    c0, x = next_id("charPr"), ""
    for i, (nm, font, size, color, bold, ul) in enumerate(CHAR):
        ids["char"][nm] = str(c0 + i)
        x += (f'<hh:charPr id="{c0 + i}" height="{size}" textColor="{color}" shadeColor="none" useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="{ids["border"]["none"]}">'
              f'<hh:fontRef hangul="{font}" latin="{font}" hanja="{font}" japanese="{font}" other="{font}" symbol="{font}" user="{font}"/>'
              '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/><hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
              '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/><hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
              + ("<hh:bold/>" if bold else "") + ('<hh:underline type="BOTTOM" shape="SOLID" color="#000000"/>' if ul else "") + "</hh:charPr>")
    n = int(re.search(r'<hh:charProperties itemCnt="(\d+)"', header_xml).group(1)) + len(CHAR)
    header_xml = re.sub(r'<hh:charProperties itemCnt="\d+"', f'<hh:charProperties itemCnt="{n}"', header_xml, 1).replace("</hh:charProperties>", x + "</hh:charProperties>", 1)
    p0, x = next_id("paraPr"), ""
    for i, (nm, al, ls, prev, nxt, left, right, ind, keep, bd) in enumerate(PARA):
        ids["para"][nm] = str(p0 + i)
        off = ' offsetLeft="400" offsetRight="400" offsetTop="300" offsetBottom="300"' if bd == "box" else ' offsetLeft="0" offsetRight="0" offsetTop="0" offsetBottom="150"' if bd in ("hdr", "colo") else ' offsetLeft="0" offsetRight="0" offsetTop="0" offsetBottom="0"'
        x += (f'<hh:paraPr id="{p0 + i}" tabPrIDRef="0" condense="0" fontLineHeight="0" snapToGrid="0" suppressLineNumbers="0" checked="0"><hh:align horizontal="{al}" vertical="BASELINE"/>'
              '<hh:heading type="NONE" idRef="0" level="0"/>'
              f'<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" widowOrphan="1" keepWithNext="{keep}" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
              '<hh:autoSpacing eAsianEng="1" eAsianNum="1"/>'
              f'<hh:margin><hc:intent value="{ind}" unit="HWPUNIT"/><hc:left value="{left}" unit="HWPUNIT"/><hc:right value="{right}" unit="HWPUNIT"/><hc:prev value="{prev}" unit="HWPUNIT"/><hc:next value="{nxt}" unit="HWPUNIT"/></hh:margin>'
              f'<hh:lineSpacing type="PERCENT" value="{ls}" unit="HWPUNIT"/><hh:border borderFillIDRef="{ids["border"][bd or "none"]}"{off} connect="0" ignoreMargin="0"/></hh:paraPr>')
    n = int(re.search(r'<hh:paraProperties itemCnt="(\d+)"', header_xml).group(1)) + len(PARA)
    header_xml = re.sub(r'<hh:paraProperties itemCnt="\d+"', f'<hh:paraProperties itemCnt="{n}"', header_xml, 1).replace("</hh:paraProperties>", x + "</hh:paraProperties>", 1)
    return header_xml, ids


def segs(text: str, base: str, ids) -> list:
    """**굵게** → base_b, __굵게 밑줄__ → base_u (없으면 base)."""
    out = []
    for part in re.split(r"(\*\*.+?\*\*|__.+?__)", text):
        if not part:
            continue
        if part.startswith("**"):
            out.append((part[2:-2], base + "_b" if base + "_b" in ids["char"] else base))
        elif part.startswith("__"):
            out.append((part[2:-2], base + "_u" if base + "_u" in ids["char"] else base))
        else:
            out.append((part, base))
    return out or [("", base)]


def plain(text: str) -> str: return re.sub(r"\*\*|__", "", text)


def parse(md: str):
    lines = md.splitlines(); i = 0; items = []
    while i < len(lines):
        l = lines[i].rstrip(); s = l.strip()
        if not s:
            i += 1; continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            items.append(({1: "chap", 2: "sec", 3: "item1", 4: "item2"}[len(m.group(1))], m.group(2).strip())); i += 1; continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                r = lines[i].strip()
                if not re.match(r"^\|\s*:?-", r):
                    rows.append([c.strip() for c in r.strip("|").split("|")])
                i += 1
            cap = src = ""
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and lines[i].strip().startswith("[표]"):
                cap = lines[i].strip()[3:].strip(); i += 1
            if i < len(lines) and re.match(r"^\*(출처|자료)", lines[i].strip()):
                src = lines[i].strip().lstrip("*"); i += 1
            items.append(("table", rows, cap, src)); continue
        fm = re.match(r'<figure><img src="([^"]+)"[^>]*><figcaption>(.*?)</figcaption></figure>', s)
        if fm:
            items.append(("fig", fm.group(1), fm.group(2))); i += 1; continue
        if s.startswith("!!"):
            items.append(("key", s[2:].strip())); i += 1; continue
        for mark, kind in (("□ ", "sq"), ("○ ", "o"), ("- ", "dash"), ("• ", "dot"), ("※ ", "note")):
            if s.startswith(mark):
                items.append((kind, s[len(mark):].strip())); break
        else:
            items.append(("body", s))
        i += 1
    return items


def chap_parts(t: str):
    m = re.match(r"제\s*(\d+)\s*장\s*(.*)", t)
    return (int(m.group(1)), m.group(2).strip()) if m else (None, t)


def divider_png(num: int, title: str, secs: list, out: Path) -> Path:
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;")
    lines = "".join(f'<text x="168" y="{575 + k * 26}" font-size="15" fill="#222">{esc(t)}</text>' for k, t in enumerate(secs[:8]))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="595" height="842" viewBox="0 0 595 842">'
           '<rect width="595" height="842" fill="#D6D6D6"/><rect y="38" width="595" height="40" fill="#E8E8E8"/><rect y="104" width="595" height="3" fill="#BDBDBD"/>'
           '<circle cx="470" cy="560" r="330" fill="#FFFFFF"/><circle cx="560" cy="250" r="7" fill="#EFEFEF"/><circle cx="270" cy="300" r="11" fill="#EFEFEF"/>'
           '<circle cx="130" cy="740" r="10" fill="#E9E9E9"/><circle cx="90" cy="610" r="34" fill="#E4E4E4"/>'
           '<circle cx="168" cy="420" r="50" fill="#D0D0D0"/><circle cx="168" cy="420" r="40" fill="#F7F7F7" stroke="#8C8C8C" stroke-width="2"/>'
           f'<text x="168" y="428" font-size="20" font-weight="700" text-anchor="middle" fill="#333">제{num}장</text>'
           f'<text x="490" y="520" font-size="40" font-weight="800" text-anchor="end" fill="#222">{esc(title)}</text>'
           '<rect x="500" y="470" width="6" height="64" fill="#7A7A7A"/><line x1="508" y1="560" x2="508" y2="760" stroke="#9A9A9A" stroke-width="1"/>'
           f'{lines}<circle cx="555" cy="790" r="9" fill="#9A9A9A"/></svg>')
    svgp = out.with_suffix(".svg"); svgp.write_text(svg, encoding="utf-8")
    js = out.parent / "svg2png_research.cjs"   # 임시 폴더에 둔다(저장소에 남기지 않음)
    if not js.exists():
        js.write_text("const { chromium } = require('playwright'); const fs = require('fs');\n(async () => { const b = await chromium.launch();\n"
                      " for (const f of process.argv.slice(2)) { const svg = fs.readFileSync(f, 'utf8'); const m = svg.match(/width=\"(\\d+)\" height=\"(\\d+)\"/);\n"
                      "  const w = +m[1], h = +m[2]; const pg = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });\n"
                      "  await pg.setContent(`<html><body style=\"margin:0\">${svg}</body></html>`); await pg.screenshot({ path: f.replace(/\\.svg$/, '.png'), clip: { x: 0, y: 0, width: w, height: h } }); await pg.close(); }\n"
                      " await b.close(); })();\n", encoding="utf-8")
    subprocess.run(["node", str(js), str(svgp)], check=True, capture_output=True)
    return out.with_suffix(".png")


class Doc:
    def __init__(self, meta):
        H.add_design_styles = add_styles          # Ctx(form=False) 가 이 함수로 스타일을 붙인다
        self.ctx = B.Ctx(form=False); self.ids = self.ctx.ids; self.meta = meta
        self.root = self.ctx.root; self.tn = 0; self.fn = 0; self.tmp = Path(tempfile.mkdtemp())

    def p(self, pname, sg, page_break=False):
        e = H.para(self.ids, pname, sg)
        if page_break:
            e.set("pageBreak", "1")
        self.root.append(e); return e

    def table(self, rows, keybox=False):
        proto = self.ctx.tbl_proto
        p = H.clone(proto); p.set("paraPrIDRef", self.ids["para"]["body"])
        tbl = p.find(".//" + H.HP + "tbl"); trs = tbl.findall(H.HP + "tr"); trp = trs[1] if len(trs) > 1 else trs[0]
        for tr in trs:
            tbl.remove(tr)
        ncol = max(len(r) for r in rows); W = H.TEXT_W - (1700 if keybox else 0)
        lens = [max(6, max(len(plain(r[c])) if c < len(r) else 0 for r in rows)) for c in range(ncol)]
        lens = [min(l, 60) for l in lens]; tot = sum(lens)
        widths = [max(int(W * l / tot), int(W * 0.1)) for l in lens]; sc = W / sum(widths); widths = [int(w * sc) for w in widths]
        tbl.set("borderFillIDRef", self.ids["border"]["none"]); tbl.set("repeatHeader", "0" if keybox else "1")
        tbl.find(H.HP + "sz").set("width", str(W))
        tcp = trp.findall(H.HP + "tc")[0]
        for ri, row in enumerate(rows):
            tr = ET.SubElement(tbl, H.HP + "tr"); head = (ri == 0 and not keybox)
            for ci in range(ncol):
                tc = H.clone(tcp); tc.set("header", "1" if head else "0")
                bf = "keybox" if keybox else ("th" if head else ("td1" if ci == 0 and ncol > 2 else "td"))
                tc.set("borderFillIDRef", self.ids["border"][bf])
                sl = tc.find(H.HP + "subList")
                for old in sl.findall(H.HP + "p"):
                    sl.remove(old)
                sl.set("vertAlign", "CENTER")
                cell = row[ci] if ci < len(row) else ""
                if keybox:
                    sl.append(H.para(self.ids, "key", [("▮ ", "key_mark")] + segs(cell, "key", self.ids)))
                elif head:
                    sl.append(H.para(self.ids, "th", [(plain(cell), "th")]))
                else:
                    pn = "tdc" if (ci == 0 and ncol > 2) or re.fullmatch(r"[\d,.%~\-–\s곳명건개년월억원만천점대]+", plain(cell) or "x") else "td"
                    sl.append(H.para(self.ids, pn, [(t, "td_b" if c.endswith("_b") or c.endswith("_u") else "td") for t, c in segs(cell, "td", self.ids)]))
                tc.find(H.HP + "cellAddr").set("colAddr", str(ci)); tc.find(H.HP + "cellAddr").set("rowAddr", str(ri))
                tc.find(H.HP + "cellSpan").set("colSpan", "1"); tc.find(H.HP + "cellSpan").set("rowSpan", "1")
                cs = tc.find(H.HP + "cellSz"); cs.set("width", str(widths[ci])); cs.set("height", "900")
                cm = tc.find(H.HP + "cellMargin")
                if cm is not None:
                    for k, v in (("left", "450" if keybox else "300"), ("right", "450" if keybox else "300"), ("top", "350" if keybox else "180"), ("bottom", "350" if keybox else "180")):
                        cm.set(k, v)
                tr.append(tc)
        tbl.set("rowCnt", str(len(rows))); tbl.set("colCnt", str(ncol))
        if keybox:
            p.set("paraPrIDRef", self.ids["para"]["sq"])
        self.root.append(p)

    def pic(self, path, caption=None, big=False):
        data = Path(path).read_bytes(); w, h = B.image_size(data)
        old = (H.MAX_IMG_W, H.MAX_IMG_H)
        if big:
            H.MAX_IMG_W, H.MAX_IMG_H = 48000, 61000
        e = H.pic_paragraph(self.ids, self.ctx.images.add(data, Path(path).suffix.lstrip(".") or "png"), w, h, caption or "그림")
        H.MAX_IMG_W, H.MAX_IMG_H = old
        self.root.append(e); return e

    def header_footer(self, text):
        first = self.root.find(H.HP + "p")
        vis = first.find(".//" + H.HP + "visibility")
        if vis is not None:
            vis.set("hideFirstHeader", "1"); vis.set("hideFirstPageNum", "1")
        run = ET.SubElement(first, H.HP + "run", {"charPrIDRef": self.ids["char"]["hdr"]})
        ctrl = ET.SubElement(run, H.HP + "ctrl")
        hd = ET.SubElement(ctrl, H.HP + "header", {"id": "1", "applyPageType": "BOTH"})
        sl = ET.SubElement(hd, H.HP + "subList", {"id": "", "textDirection": "HORIZONTAL", "lineWrap": "BREAK", "vertAlign": "BOTTOM", "linkListIDRef": "0",
                                                  "linkListNextIDRef": "0", "textWidth": str(H.TEXT_W), "textHeight": "4251", "hasTextRef": "0", "hasNumRef": "0"})
        sl.append(H.para(self.ids, "hdr", [(text + " ", "hdr"), ("▐▌", "hdr_mark")]))


def build(md_path: Path, out: Path) -> Path:
    raw = md_path.read_text(encoding="utf-8")
    _, fm, body = raw.split("---", 2)
    meta = yaml.safe_load(fm) or {}
    items = parse(body)
    d = Doc(meta); ids = d.ids
    d.header_footer(meta.get("header") or meta.get("title", ""))
    # 표지
    for _ in range(6):
        d.p("spacer", [("", "spacer")])
    d.p("cover_bar", [("", "cover_bar")])
    for k, line in enumerate(str(meta.get("title", "")).split("\n")):
        d.p("cover_title", [(line, "cover_title")])
    if meta.get("subtitle"):
        d.p("cover_sub", [(f"- {meta['subtitle']} -", "cover_sub")])
    d.p("cover_bar", [("", "cover_bar")])
    for _ in range(10):
        d.p("spacer", [("", "spacer")])
    d.p("cover_date", [(str(meta.get("date", "")), "cover_date")])
    # 목차(쪽 번호 없이 — 한글에서 [도구-차례 새로 고침]은 제목 문단 스타일 기준이라 여기서는 목록만)
    d.p("toc_head", [("목      차", "toc_head")], page_break=True)
    tabs, figs, tn, fn = [], [], 0, 0
    for it in items:
        if it[0] == "chap":
            num, t = chap_parts(it[1]); d.p("toc_ch", [(f"제 {num} 장  {t}" if num else t, "toc_ch")])
        elif it[0] == "sec":
            d.p("toc_sec", [(re.sub(r"^제\s*(\d+)\s*절", r"제 \1 절", it[1]), "toc_sec")])
        elif it[0] == "item1":
            d.p("toc_item", [(it[1], "toc_item")])
        elif it[0] == "table" and it[2]:
            tn += 1; tabs.append(f"[표 {tn}] {plain(it[2])}")
        elif it[0] == "fig":
            fn += 1; figs.append(f"[그림 {fn}] {plain(it[2])}")
    if tabs:
        d.p("toc_head", [("표  목  차", "toc_head")], page_break=True)
        for t in tabs:
            d.p("toc_item", [(t, "toc_item")])
    if figs:
        d.p("toc_head", [("그 림 목 차", "toc_head")], page_break=not tabs)
        for t in figs:
            d.p("toc_item", [(t, "toc_item")])
    # 본문
    for idx, it in enumerate(items):
        k = it[0]
        if k == "chap":
            num, t = chap_parts(it[1])
            if num:
                secs = []
                for jt in items[idx + 1:]:
                    if jt[0] == "chap":
                        break
                    if jt[0] == "sec":
                        secs.append(re.sub(r"^제\s*(\d+)\s*절\s*", r"제\1절 ", jt[1]))
                png = divider_png(num, t, secs, d.tmp / f"div{num}.svg")
                e = d.pic(png, f"제{num}장 간지", big=True); e.set("pageBreak", "1")
                d.p("chap", [(f"제 {num} 장 {t}", "chap")], page_break=True)
            else:
                d.p("chap", [(t, "chap")], page_break=True)
        elif k == "sec":
            d.p("sec", [(re.sub(r"^제\s*(\d+)\s*절", r"제 \1 절", it[1]), "sec")])
        elif k in ("item1", "item2"):
            d.p(k, [(it[1], k)])
        elif k == "key":
            d.table([[it[1]]], keybox=True)
        elif k in ("sq", "o", "dash", "dot", "note"):
            mark = {"sq": "□ ", "o": "○ ", "dash": "- ", "dot": "• ", "note": "※ "}[k]
            sg = segs(it[1], k, ids)
            d.p(k, [(mark, k if k != "sq" else "sq")] + sg)
        elif k == "body":
            d.p("body", segs(it[1], "body", ids))
        elif k == "table":
            d.table(it[1])
            if it[3]:
                d.p("src", [("*" + it[3], "src")])
            if it[2]:
                d.tn += 1; d.p("caption", [(f"[표 {d.tn}] {plain(it[2])}", "caption")])
        elif k == "fig":
            src = it[1]; fp = Path(src) if Path(src).exists() else (H.ROOT / "public" / src.lstrip("/"))
            if fp.exists():
                d.pic(fp, it[2])
            d.fn += 1; d.p("caption", [(f"[그림 {d.fn}] {plain(it[2])}", "caption")])
    # 참고문헌
    srcs = meta.get("sources") or []
    if srcs:
        d.p("chap", [("참고문헌", "chap")], page_break=True)
        for n, s in enumerate(srcs, 1):
            d.p("ref", [(f"[{n}] {s.get('title', '')}, {s.get('date', '')}, {s.get('url', '')}", "ref")])
    # 발행 정보
    for _ in range(14):
        d.p("spacer", [("", "spacer")], page_break=(_ == 0))
    d.p("colo_title", [(str(meta.get("title", "")).replace("\n", " "), "colo_title")])
    d.p("colo", [(f"발 행 일 : {meta.get('date', '')}", "colo")])
    if meta.get("note"):
        d.p("colo", [(f"비     고 : {meta['note']}", "colo")])
    # 저장(hwpx_blocks.build_hwpx 의 저장 부분과 같은 방식)
    H.drop_linesegs(d.root)
    sec = ET.tostring(d.root, encoding="unicode")
    sec = re.sub(r"^<hs:sec\b[^>]*>", d.ctx.root_tag, sec, count=1)
    new_sec = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' + sec
    manifest = "".join(f'<opf:item id="{bid}" href="BinData/{bid}.{ext}" media-type="image/{"jpeg" if ext == "jpg" else ext}" isEmbeded="1"/>' for bid, _, ext in d.ctx.images.files)
    out.parent.mkdir(parents=True, exist_ok=True)
    preview = re.sub(r"\s+", " ", " ".join(plain(it[1]) for it in items if isinstance(it[1], str)))[:1000]
    with zipfile.ZipFile(out, "w") as zo:
        for n in d.ctx.z.namelist():
            data = d.ctx.z.read(n)
            if n == "Contents/section0.xml": data = new_sec.encode("utf-8")
            elif n == "Contents/header.xml": data = d.ctx.header_xml.encode("utf-8")
            elif n == "Contents/content.hpf": data = data.decode("utf-8").replace("</opf:manifest>", manifest + "</opf:manifest>", 1).encode("utf-8")
            elif n == "Preview/PrvText.txt": data = preview.encode("utf-8")
            zo.writestr(zipfile.ZipInfo(n), data, compress_type=zipfile.ZIP_STORED if n == "mimetype" else zipfile.ZIP_DEFLATED)
        for bid, data, ext in d.ctx.images.files:
            zo.writestr(zipfile.ZipInfo(f"BinData/{bid}.{ext}"), data, compress_type=zipfile.ZIP_DEFLATED)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("md"); ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    print("→", build(Path(a.md), Path(a.out)))
