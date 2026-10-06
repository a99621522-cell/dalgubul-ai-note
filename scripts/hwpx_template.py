#!/usr/bin/env python3
"""브라우저용 한글(HWPX) 양식 묶음 → public/hwpx/template.json (v2, 양식 복제 방식 — docs/prompts/site_hwpx_skill.md 3절, 2026-10-06)

기업 카드·통계표·검토 의견서를 방문자 브라우저에서 바로 HWPX 로 만들 수 있게(서버 없음, 기업 1만여 곳의 파일을 미리 만들지 않음)
hwpx_report.py 의 디자인 스타일(문단·글자·테두리 모양)을 더한 header.xml 과 양식에서 뽑은 **원형 XML 조각**(문단·run·표 문단·칸·그림 run)을 JSON 하나로 내보낸다.
src/scripts/hwpx.ts 가 이 파일을 받아 DOMParser 로 원형을 복제(cloneNode)해 글자만 바꾸고 XMLSerializer 로 section0.xml 을 쓴 뒤 zip 으로 묶는다
(문자열 템플릿으로 hp:p·hp:tc 를 새로 쓰지 않는다 — 스킬 원칙). 역할 ↔ 양식 문단 인덱스는 config/hwpx_forms.yml.

양식(scripts/data/hwpx/report_basic.hwpx)이나 hwpx_report.py 의 스타일 스펙, hwpx_forms.yml 을 바꾸면 다시 실행해 커밋한다.
사용: python3 scripts/hwpx_template.py [--check] [--detect <양식.hwpx>]
  --detect: 양식의 최상위 문단을 훑어 역할 후보(표지·목차·□○-※ 단계·표·그림)를 짐작해 yml 초안을 출력한다(운영자가 확인해 hwpx_forms.yml 에 적는다)
"""
import base64, json, re, sys, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hwpx_report as H  # noqa: E402
import hwpx_blocks as B  # noqa: E402

OUT = H.ROOT / "public" / "hwpx" / "template.json"
FORMS = H.ROOT / "config" / "hwpx_forms.yml"
SKIP = ("Preview/PrvImage.png", "Preview/PrvText.txt", "Contents/section0.xml")   # 미리보기 글과 본문은 JS 가 만든다
NOLSEG = lambda x: re.sub(r"<hp:linesegarray>.*?</hp:linesegarray>", "", x, flags=re.S)


def strip_ns_decl(xml: str) -> str:
    """ET.tostring 이 조각마다 붙이는 xmlns 선언을 뗀다(브라우저는 루트의 선언을 쓴다)."""
    return re.sub(r'\s+xmlns:\w+="[^"]+"', "", xml, count=20)


def export() -> dict:
    ctx = B.Ctx()
    HP = H.HP; ids = ctx.ids
    root_tag = ctx.root_tag
    sec_open = ET.tostring(ctx.root, encoding="unicode")
    assert sec_open.endswith("</hs:sec>"), sec_open[-40:]
    sec_open = re.sub(r"^<hs:sec\b[^>]*>", root_tag, NOLSEG(sec_open[: -len("</hs:sec>")]), count=1)
    # 원형 문단(양식 복제): 글 run 하나 — hwpx.ts 가 cloneNode 뒤 paraPrIDRef·charPrIDRef·hp:t 만 바꾼다
    p_proto = strip_ns_decl(NOLSEG(ET.tostring(H.para(ids, "body", [("", "body")]), encoding="unicode")))
    # 원형 표 문단(1×1, 디자인 스타일) — hwpx.ts 가 tr 을 지우고 칸 원형(tc)을 복제해 격자를 만든다
    t = B.merge_table(ctx, [["원형"]], head=False, widths=[H.TEXT_W], fill="td_alt", margin=320)
    tbl_proto = strip_ns_decl(NOLSEG(ET.tostring(t, encoding="unicode")))
    tc_proto = re.search(r"<hp:tc\b.*</hp:tc>", tbl_proto, re.S).group(0)
    # 원형 그림 문단(1×1 px 자리) — hwpx.ts 가 binaryItemIDRef·크기만 바꾼다
    pic_proto = strip_ns_decl(ET.tostring(H.pic_paragraph(ids, "image9", 1, 1, "그림"), encoding="unicode"))
    files = {}
    for n in ctx.z.namelist():
        if n in SKIP:
            continue
        data = ctx.header_xml.encode("utf-8") if n == "Contents/header.xml" else ctx.z.read(n)
        files[n] = base64.b64encode(data).decode("ascii")
    hpf = ctx.z.read("Contents/content.hpf").decode("utf-8")
    return {"version": 2, "ids": ids, "text_w": H.TEXT_W, "ns": dict(re.findall(r'xmlns:(\w+)="([^"]+)"', root_tag)),
            "sec_open": sec_open, "sec_close": "</hs:sec>", "proto": {"p": p_proto, "tbl": tbl_proto, "tc": tc_proto, "pic": pic_proto},
            "hpf": hpf, "files": files}


def detect(form: Path) -> str:
    """양식 최상위 문단의 역할 후보를 yml 초안으로."""
    z = zipfile.ZipFile(form)
    sec_xml = z.read("Contents/section0.xml").decode("utf-8")
    ns = dict(re.findall(r'xmlns:(\w+)="([^"]+)"', sec_xml[:3000])); HP = "{%s}" % ns["hp"]
    root = ET.fromstring(sec_xml)
    out = [f"# {form.name} 역할 후보(자동 짐작, 운영자 확인 뒤 hwpx_forms.yml 에 옮긴다)", "paragraphs:"]
    for i, p in enumerate(root):
        if p.tag != HP + "p":
            continue
        text = "".join(t.text or "" for t in p.iter(HP + "t")).strip()
        kind = "table" if p.find(f".//{HP}tbl") is not None else "pic" if p.find(f".//{HP}pic") is not None else "secpr" if p.find(f".//{HP}secPr") is not None else "text"
        role = ""
        if kind == "text" and text:
            role = {"□": "h1_box", "○": "h2_circle", "-": "dash", "※": "note"}.get(text[0], "")
            if re.match(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]", text): role = "section_head"
            if re.match(r"^\d{4}\.\s*\d", text): role = "date"
        if kind == "table" and ("목차" in text or "Contents" in text): role = "toc"
        out.append(f"  - {{index: {i}, kind: {kind}, role: '{role}', text: {json.dumps(text[:30], ensure_ascii=False)}}}")
    return "\n".join(out)


def main() -> int:
    if "--detect" in sys.argv:
        print(detect(Path(sys.argv[sys.argv.index("--detect") + 1]))); return 0
    d = export()
    if "--check" in sys.argv:
        ET.fromstring(d["sec_open"] + d["sec_close"])
        decl = " ".join('xmlns:%s="%s"' % (a, b) for a, b in d["ns"].items())
        for k, v in d["proto"].items():
            ET.fromstring(f"<x {decl}>{v}</x>")
        print("ok"); return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"→ {OUT.relative_to(H.ROOT)} ({OUT.stat().st_size:,} bytes, 파일 {len(d['files'])}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
