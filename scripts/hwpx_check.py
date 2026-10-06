#!/usr/bin/env python3
"""HWPX 구조 검사기 — 한글(한컴오피스) 없이 돌리는 자동 검사(docs/prompts/site_hwpx_skill.md 2절, 2026-10-06). 표준 라이브러리만.

검사 규칙(FAIL 은 종료 코드 1, WARN 은 알림만):
  zip-mimetype   zip 첫 항목이 mimetype 이고 STORED 이며 내용이 application/hwp+zip
  files          필수 파일(content.hpf·header.xml·section0.xml·container.xml·manifest.xml·settings.xml) 존재, version.xml·Preview 는 WARN
  xml            .xml·.hpf·.rdf 가 모두 잘 열림(UTF-8, BOM 없음)
  container      META-INF/container.xml 의 rootfile 이 실제 파일을 가리킴
  hpf            content.hpf 의 manifest href 가 실제 파일이고 spine idref 가 manifest 에 있으며 section 이 spine 에 있음
  header-count   header.xml 의 itemCnt 가 실제 항목 수와 같음
  ns             section 루트의 네임스페이스 선언(hp·hs 는 FAIL, hc·hh·hp10 등 양식이 쓰는 나머지는 WARN)
  secpr          section0 첫 문단에 hp:secPr·hp:pagePr 가 있음
  ref            paraPrIDRef·charPrIDRef·styleIDRef·borderFillIDRef·tabPrIDRef·numberingIDRef 가 header.xml 에 있음
  table-grid     hp:tbl 의 rowCnt/colCnt 와 hp:tr·hp:tc 수, cellAddr·cellSpan 으로 편 격자가 겹치거나 비지 않음, 행마다 cellSz 폭 합이 표 폭과 2% 안
  pic            hc:img binaryItemIDRef 가 content.hpf manifest 와 BinData 파일에 있음
  lineseg        hp:linesegarray 가 있으면 최상위 문단들의 vertpos 가 모두 같은지(겹침 위험, 운영자 확인 2026-09-30) WARN
  text           전화번호·이메일 패턴 FAIL(개인정보), 순위·TOP·추천·우수 낱말 WARN(평가·순위 금지)
사용: python3 scripts/hwpx_check.py <파일.hwpx 또는 폴더> [...] [--json] [--quiet]
"""
import argparse, json, re, sys, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

REQUIRED = ["mimetype", "Contents/content.hpf", "Contents/header.xml", "Contents/section0.xml", "META-INF/container.xml", "META-INF/manifest.xml", "settings.xml"]
OPTIONAL = ["version.xml", "Preview/PrvText.txt"]
NS_FAIL = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph", "hs": "http://www.hancom.co.kr/hwpml/2011/section"}
NS_WARN = ["hc", "hh", "hp10", "ha", "hm", "hpf", "hhs", "dc", "opf", "ooxmlchart", "epub", "config"]
HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
HC = "{http://www.hancom.co.kr/hwpml/2011/core}"
HH = "{http://www.hancom.co.kr/hwpml/2011/head}"
REF_ATTRS = {"paraPrIDRef": "paraPr", "charPrIDRef": "charPr", "styleIDRef": "style", "borderFillIDRef": "borderFill", "tabPrIDRef": "tabPr", "numberingIDRef": "numbering"}
PHONE = re.compile(r"(?<!\d)0\d{1,2}-\d{3,4}-\d{4}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
BANNED = re.compile(r"순위|TOP\s*\d|추천 기업|우수 기업|우수기업")


class Report:
    def __init__(self, path: str):
        self.path = path; self.items: list[dict] = []
    def add(self, level: str, rule: str, where: str, msg: str):
        self.items.append({"level": level, "rule": rule, "where": where, "msg": msg})
    def fail(self, *a): self.add("FAIL", *a)
    def warn(self, *a): self.add("WARN", *a)
    def ok(self, rule, msg=""): self.add("PASS", rule, "", msg)
    @property
    def failed(self): return any(i["level"] == "FAIL" for i in self.items)


def check_file(path: Path) -> Report:
    r = Report(str(path))
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:  # noqa: BLE001
        r.fail("zip", "", f"zip 아님: {e}"); return r
    infos = z.infolist(); names = [i.filename for i in infos]
    # zip-mimetype
    if not infos or infos[0].filename != "mimetype":
        r.fail("zip-mimetype", names[0] if names else "", "첫 항목이 mimetype 이 아님")
    else:
        if infos[0].compress_type != zipfile.ZIP_STORED:
            r.fail("zip-mimetype", "mimetype", "STORED(압축 없음)가 아님")
        if z.read("mimetype") != b"application/hwp+zip":
            r.fail("zip-mimetype", "mimetype", f"내용이 다름: {z.read('mimetype')[:40]!r}")
        if not r.items: r.ok("zip-mimetype")
    # files
    for n in REQUIRED:
        if n not in names: r.fail("files", n, "필수 파일 없음")
    for n in OPTIONAL:
        if n not in names: r.warn("files", n, "없음(한글은 보통 넣는다)")
    # xml
    docs: dict[str, ET.Element] = {}
    for n in names:
        if n.endswith((".xml", ".hpf", ".rdf")):
            raw = z.read(n)
            if raw.startswith(b"\xef\xbb\xbf"): r.warn("xml", n, "UTF-8 BOM 있음")
            try:
                docs[n] = ET.fromstring(raw)
            except ET.ParseError as e:
                r.fail("xml", n, f"XML 오류: {e}")
    if "Contents/section0.xml" not in docs or "Contents/header.xml" not in docs:
        return r
    # container
    c = docs.get("META-INF/container.xml")
    if c is not None:
        for rf in c.iter():
            if rf.tag.endswith("rootfile"):
                fp = rf.get("full-path", "")
                if fp not in names: r.fail("container", fp, "rootfile 이 가리키는 파일 없음")
    # hpf
    hpf = docs.get("Contents/content.hpf")
    man_ids: set[str] = set()
    if hpf is not None:
        for it in hpf.iter():
            if it.tag.endswith("}item"):
                man_ids.add(it.get("id", ""))
                if it.get("href", "") not in names: r.fail("hpf", it.get("href", ""), "manifest 항목 파일 없음")
        spine = [it.get("idref", "") for it in hpf.iter() if it.tag.endswith("}itemref")]
        for s in spine:
            if s not in man_ids: r.fail("hpf", s, "spine idref 가 manifest 에 없음")
        secs = [n for n in names if re.fullmatch(r"Contents/section\d+\.xml", n)]
        for s in secs:
            sid = next((it.get("id") for it in hpf.iter() if it.tag.endswith("}item") and it.get("href") == s), None)
            if sid is None: r.fail("hpf", s, "section 이 manifest 에 없음")
            elif sid not in spine: r.fail("hpf", s, "section 이 spine 에 없음")
    # header ids + counts
    head = docs["Contents/header.xml"]
    ids: dict[str, set[str]] = {k: set() for k in REF_ATTRS.values()}
    groups = {"borderFills": "borderFill", "charProperties": "charPr", "tabProperties": "tabPr", "numberings": "numbering", "paraProperties": "paraPr", "styles": "style"}
    for grp in head.iter():
        tag = grp.tag.split("}")[-1]
        if tag in groups:
            kind = groups[tag]
            found = [e for e in grp if e.tag.split("}")[-1] == kind]
            for e in found: ids[kind].add(e.get("id", ""))
            cnt = grp.get("itemCnt")
            if cnt is not None and int(cnt) != len(found): r.fail("header-count", tag, f"itemCnt={cnt} 인데 항목 {len(found)}개")
    if not ids["style"]: ids["style"] = {"0"}
    # sections
    secs = sorted(n for n in docs if re.fullmatch(r"Contents/section\d+\.xml", n))
    for sn in secs:
        raw = z.read(sn).decode("utf-8", "replace")
        root_tag = re.search(r"<hs:sec\b[^>]*>", raw[:6000])
        decl = dict(re.findall(r'xmlns:(\w+)="([^"]+)"', root_tag.group(0))) if root_tag else {}
        for k, v in NS_FAIL.items():
            if decl.get(k) != v: r.fail("ns", sn, f"xmlns:{k} 선언 없음/다름")
        miss = [k for k in NS_WARN if k not in decl]
        if miss: r.warn("ns", sn, "양식이 선언하는 네임스페이스 빠짐: " + ", ".join(miss))
        sec = docs[sn]
        tops = [e for e in sec if e.tag == HP + "p"]
        if not tops: r.fail("secpr", sn, "문단이 없음")
        else:
            if tops[0].find(f".//{HP}secPr") is None: r.fail("secpr", sn, "첫 문단에 hp:secPr 없음")
            if tops[0].find(f".//{HP}pagePr") is None: r.fail("secpr", sn, "첫 문단에 hp:pagePr 없음")
        # refs
        bad: dict[str, set[str]] = {}
        for e in sec.iter():
            for attr, kind in REF_ATTRS.items():
                v = e.get(attr)
                if v is not None and v != "" and v not in ids[kind]:
                    bad.setdefault(f"{attr}={v}", set()).add(e.tag.split("}")[-1])
        for k, tags in sorted(bad.items()): r.fail("ref", sn, f"{k} 가 header.xml 에 없음 ({', '.join(sorted(tags))})")
        if not bad: r.ok("ref", f"{sn} 참조 {sum(1 for e in sec.iter() for a in REF_ATTRS if e.get(a))}개 확인")
        # tables
        ntbl = 0
        for ti, tbl in enumerate(sec.iter(HP + "tbl")):
            ntbl += 1; where = f"{sn} tbl#{ti + 1}(id {tbl.get('id')})"
            trs = tbl.findall(HP + "tr"); rc, cc = int(tbl.get("rowCnt", 0)), int(tbl.get("colCnt", 0))
            if len(trs) != rc: r.fail("table-grid", where, f"rowCnt={rc} 인데 tr {len(trs)}개")
            occ: set[tuple[int, int]] = set(); width_total = int((tbl.find(HP + "sz").get("width") if tbl.find(HP + "sz") is not None else 0) or 0)
            colw: dict[int, int] = {}   # 병합 없는 칸에서 읽은 열 폭
            for ri, tr in enumerate(trs):
                col = 0
                for tc in tr.findall(HP + "tc"):
                    while (ri, col) in occ: col += 1
                    addr = tc.find(HP + "cellAddr"); span = tc.find(HP + "cellSpan"); sz = tc.find(HP + "cellSz")
                    if addr is None or span is None or sz is None: r.fail("table-grid", where, f"행 {ri} 칸에 cellAddr/cellSpan/cellSz 없음"); continue
                    ca, ra = int(addr.get("colAddr", -1)), int(addr.get("rowAddr", -1))
                    cs, rs = int(span.get("colSpan", 1)), int(span.get("rowSpan", 1))
                    if (ca, ra) != (col, ri): r.fail("table-grid", where, f"행 {ri} 칸 cellAddr=({ca},{ra}) 인데 격자 위치는 ({col},{ri})")
                    for dr in range(rs):
                        for dc in range(cs):
                            if (ri + dr, col + dc) in occ: r.fail("table-grid", where, f"칸 ({col},{ri}) span {cs}x{rs} 가 다른 칸과 겹침")
                            occ.add((ri + dr, col + dc))
                    if cs == 1: colw.setdefault(col, int(sz.get("width", 0)))
                    col += cs
                while (ri, col) in occ: col += 1   # 위 행의 rowspan 이 덮는 끝 열
                if col != cc: r.fail("table-grid", where, f"행 {ri} 가 {col}열까지 채움(colCnt={cc})")
            if width_total and len(colw) == cc and abs(sum(colw.values()) - width_total) > width_total * 0.02:
                r.warn("table-grid", where, f"열 폭 합 {sum(colw.values())} ≠ 표 폭 {width_total}")
            for ri in range(rc):
                for ci in range(cc):
                    if (ri, ci) not in occ: r.fail("table-grid", where, f"격자 ({ci},{ri}) 가 비어 있음")
        if ntbl: r.ok("table-grid", f"{sn} 표 {ntbl}개")
        # pics
        for img in sec.iter(HC + "img"):
            bid = img.get("binaryItemIDRef", "")
            if bid not in man_ids: r.fail("pic", sn, f"binaryItemIDRef={bid} 가 content.hpf manifest 에 없음")
            if not any(n.startswith(f"BinData/{bid}.") for n in names): r.fail("pic", sn, f"BinData/{bid}.* 파일 없음")
        # lineseg
        segs = [p.find(f"{HP}linesegarray/{HP}lineseg") for p in tops]
        segs = [s for s in segs if s is not None]
        if segs:
            vp = {s.get("vertpos") for s in segs}
            if len(segs) > 3 and len(vp) == 1: r.warn("lineseg", sn, f"최상위 문단 {len(segs)}개의 lineseg vertpos 가 모두 {vp.pop()} — 한글이 문단을 겹쳐 그릴 수 있음")
            else: r.ok("lineseg", f"{sn} lineseg {len(segs)}개(없는 문단 {len(tops) - len(segs)})")
        else:
            r.ok("lineseg", f"{sn} linesegarray 없음(한글이 열 때 계산)")
        # text
        text = " ".join(t.text or "" for t in sec.iter(HP + "t"))
        for m in PHONE.findall(text): r.fail("text", sn, f"전화번호 패턴: {m}")
        for m in EMAIL.findall(text): r.fail("text", sn, f"이메일 패턴: {m}")
        scan = re.sub(r"순위[^.。]{0,14}(아닙니다|아니며|아님|없음|없습니다|없이|하지 않)", "", text)   # '순위가 아닙니다' 같은 안내 문구는 뺀다
        for m in set(BANNED.findall(scan)): r.warn("text", sn, f"평가·순위 낱말: {m}")
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+"); ap.add_argument("--json", action="store_true"); ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    files: list[Path] = []
    for p in a.paths:
        p = Path(p)
        files += sorted(p.rglob("*.hwpx")) if p.is_dir() else [p]
    reports = [check_file(f) for f in files]
    if a.json:
        print(json.dumps([{"file": r.path, "fail": r.failed, "items": r.items} for r in reports], ensure_ascii=False, indent=1))
    else:
        for r in reports:
            nf = sum(i["level"] == "FAIL" for i in r.items); nw = sum(i["level"] == "WARN" for i in r.items)
            print(f"{'FAIL' if r.failed else 'PASS'}  {r.path}  (FAIL {nf}, WARN {nw})")
            for i in r.items:
                if i["level"] == "PASS" and a.quiet: continue
                if i["level"] != "PASS" or not a.quiet:
                    print(f"   {i['level']:4} {i['rule']:12} {i['where']}  {i['msg']}")
        print(f"— {len(reports)}개 중 PASS {sum(not r.failed for r in reports)}")
    return 1 if any(r.failed for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
