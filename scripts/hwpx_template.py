#!/usr/bin/env python3
"""브라우저용 한글(HWPX) 양식 묶음 → public/hwpx/template.json (v3, 공무원 양식 복제 — 운영자 지시 2026-10-06)

기업 카드·통계표·검토 의견서를 방문자 브라우저에서 바로 HWPX 로 만들 수 있게(서버 없음) 운영자 양식(scripts/data/hwpx/report_basic.hwpx)의
header.xml **그대로**와 양식에서 뽑은 원형 XML 조각(절 머리표·□·○·-·※·빈 문단·표·표지·그림 run)을 JSON 하나로 내보낸다.
src/scripts/hwpx.ts 가 이 파일을 받아 DOMParser 로 원형을 복제(cloneNode)해 글자만 바꾸고 XMLSerializer 로 section0.xml 을 쓴 뒤 zip 으로 묶는다.
스타일을 덧붙이지 않으므로 id 충돌이 없다. 역할 ↔ 양식 문단 인덱스는 scripts/hwpx_blocks.py FORM(= config/hwpx_forms.yml).

양식을 바꾸면 다시 실행해 커밋한다. 사용: python3 scripts/hwpx_template.py [--check] [--detect <양식.hwpx>]
"""
import base64, json, re, sys, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hwpx_report as H  # noqa: E402
import hwpx_blocks as B  # noqa: E402

OUT = H.ROOT / "public" / "hwpx" / "template.json"
SKIP = ("Preview/PrvImage.png", "Preview/PrvText.txt", "Contents/section0.xml")
NOLSEG = lambda x: re.sub(r"<hp:linesegarray>.*?</hp:linesegarray>", "", x, flags=re.S)


def strip_ns_decl(xml: str) -> str:
    return re.sub(r'\s+xmlns:\w+="[^"]+"', "", xml, count=30)


def frag(el) -> str:
    return strip_ns_decl(NOLSEG(ET.tostring(el, encoding="unicode")))


def export() -> dict:
    ctx = B.Ctx(form=True)
    root_tag = ctx.root_tag
    sec_open = ET.tostring(ctx.root, encoding="unicode")
    assert sec_open.endswith("</hs:sec>"), sec_open[-40:]
    sec_open = re.sub(r"^<hs:sec\b[^>]*>", root_tag, NOLSEG(sec_open[: -len("</hs:sec>")]), count=1)
    proto = {k: frag(v) for k, v in ctx.proto.items()}
    # 그림 run 원형(※ 글자 모양, 빈 문단 모양)
    note_run = ctx.proto["note"].find(H.HP + "run")
    ids = {"char": {"caption": note_run.get("charPrIDRef"), "body": note_run.get("charPrIDRef")}, "para": {"fig": ctx.proto["blank"].get("paraPrIDRef")}}
    proto["pic"] = frag(H.pic_paragraph(ids, "image9", 1, 1, "그림"))
    files = {}
    for n in ctx.z.namelist():
        if n in SKIP:
            continue
        files[n] = base64.b64encode(ctx.z.read(n)).decode("ascii")
    hpf = ctx.z.read("Contents/content.hpf").decode("utf-8")
    return {"version": 3, "text_w": H.TEXT_W, "ns": dict(re.findall(r'xmlns:(\w+)="([^"]+)"', root_tag)), "marks": B.MARK, "roles": B.ROLE,
            "roman": B.ROMAN, "sec_open": sec_open, "sec_close": "</hs:sec>", "proto": proto, "hpf": hpf, "files": files}


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
    print(f"→ {OUT.relative_to(H.ROOT)} ({OUT.stat().st_size:,} bytes, 파일 {len(d['files'])}개, 원형 {len(d['proto'])}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
