#!/usr/bin/env python3
"""브라우저용 한글(HWPX) 양식 묶음 → public/hwpx/template.json

기업 카드·통계표를 방문자 브라우저에서 바로 HWPX 로 만들 수 있게(서버 없음, 기업 1만여 곳의 파일을 미리 만들지 않음)
hwpx_report.py 의 디자인 스타일(문단·글자·테두리 모양)을 더한 header.xml 과 용지 설정 문단, 표 원형을 JSON 하나로 내보낸다.
src/scripts/hwpx.ts 가 이 파일을 받아 section0.xml 만 만들고 zip 으로 묶는다.

양식(scripts/data/hwpx/report_basic.hwpx)이나 hwpx_report.py 의 스타일 스펙을 바꾸면 다시 실행해 커밋한다.
사용: python3 scripts/hwpx_template.py [--check]
"""
import base64, json, re, sys, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hwpx_report as H  # noqa: E402

OUT = H.ROOT / "public" / "hwpx" / "template.json"
SKIP = ("Preview/PrvImage.png", "Preview/PrvText.txt", "Contents/section0.xml")   # 미리보기 글은 JS 가 만들고, 본문은 JS 가 만든다


def export() -> dict:
    z = zipfile.ZipFile(H.TEMPLATE)
    sec_xml = z.read("Contents/section0.xml").decode("utf-8")
    H.NS.clear(); H.NS.update(dict(re.findall(r'xmlns:(\w+)="([^"]+)"', sec_xml[:3000])))
    for k, v in H.NS.items():
        ET.register_namespace(k, v)
    H.HP = "{%s}" % H.NS["hp"]
    HP = H.HP
    root = ET.fromstring(sec_xml)
    top = list(root)
    header_xml, ids = H.add_design_styles(z.read("Contents/header.xml").decode("utf-8"))
    tbl_proto = top[64]
    first = top[0]
    for run in first.findall(HP + "run"):
        for ctrl in run.findall(HP + "ctrl"):
            if ctrl.find(HP + "header") is not None or ctrl.find(HP + "footer") is not None:
                run.remove(ctrl)
    for p in top[1:]:
        root.remove(p)
    sec_open = ET.tostring(root, encoding="unicode")
    assert sec_open.endswith("</hs:sec>"), sec_open[-40:]
    sec_open = sec_open[: -len("</hs:sec>")]
    # 1×1 표를 만들어 표 머리·칸·꼬리로 쪼갠다 (칸의 속성은 자리표시로)
    t = H.design_table(tbl_proto, ids, [["@@CELL@@"]], head=False, widths=[H.TEXT_W], fill_key="td_alt", margin=320)
    txml = ET.tostring(t, encoding="unicode")
    a, b = txml.index("<hp:tr>"), txml.rindex("</hp:tr>") + len("</hp:tr>")
    tbl_open, tr_xml, tbl_close = txml[:a], txml[a:b], txml[b:]
    tc = re.search(r"<hp:tc\b.*</hp:tc>", tr_xml, re.S).group(0)
    tc = re.sub(r'<hp:p\b[^>]*>.*?</hp:p>', "@@PARAS@@", tc, count=1, flags=re.S)
    assert "@@CELL@@" not in tc
    tc = tc.replace('header="0"', 'header="@@H@@"', 1).replace(f'borderFillIDRef="{ids["border"]["td_alt"]}"', 'borderFillIDRef="@@BF@@"', 1)
    tc = tc.replace('vertAlign="TOP"', 'vertAlign="@@VA@@"', 1).replace('colAddr="0"', 'colAddr="@@COL@@"', 1).replace('rowAddr="0"', 'rowAddr="@@ROW@@"', 1)
    tc = re.sub(r'(<hp:cellSz width=")\d+(")', r"\1@@W@@\2", tc, count=1)
    tc = re.sub(r'(<hp:cellMargin left=")\d+(" right=")\d+(")', r"\1@@M@@\2@@M@@\3", tc, count=1)
    for mark in ("@@H@@", "@@BF@@", "@@VA@@", "@@COL@@", "@@ROW@@", "@@W@@", "@@M@@", "@@PARAS@@"):
        assert mark in tc, mark
    files = {}
    for n in z.namelist():
        if n in SKIP:
            continue
        data = header_xml.encode("utf-8") if n == "Contents/header.xml" else z.read(n)
        files[n] = base64.b64encode(data).decode("ascii")
    nolseg = lambda x: re.sub(r"<hp:linesegarray>.*?</hp:linesegarray>", "", x, flags=re.S)
    sec_open, tbl_open, tbl_close, tc = nolseg(sec_open), nolseg(tbl_open), nolseg(tbl_close), nolseg(tc)
    return {"ids": ids, "text_w": H.TEXT_W, "sec_open": sec_open, "sec_close": "</hs:sec>", "tbl_open": tbl_open, "tbl_close": tbl_close, "tc": tc,
            # 줄 배치 캐시(linesegarray)는 넣지 않는다 — 같은 값을 모든 문단에 넣으면 한글이 문단을 한 자리에 겹쳐 그린다(2026-09-30). 한글이 열 때 새로 계산
            "lineseg": "",
            "files": files}


def main() -> int:
    d = export()
    if "--check" in sys.argv:
        ET.fromstring(d["sec_open"] + d["sec_close"])
        print("ok"); return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"→ {OUT.relative_to(H.ROOT)} ({OUT.stat().st_size:,} bytes, 파일 {len(d['files'])}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
