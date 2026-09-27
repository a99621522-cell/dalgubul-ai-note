#!/usr/bin/env python3
"""정책제안 리포트(마크다운) → 한글 HWPX (공공기관 보고서 기본 양식, scripts/data/hwpx/report_basic.hwpx 를 채운다). 표준 라이브러리 + pyyaml.

본문은 개조식(운영자 지시 2026-09-27): 문장마다 한 줄, 끝은 명사형('한다'→'함', '이다'→'임', '있다'→'있음'), 문단 첫 문장 ○·나머지 -, 굵은 첫 문장 □.
양식(운영자 제공, 2026-09-27)의 문단을 원형으로 복제해 채운다: 표지(제목 2줄·날짜·부서 표), 목차, 절 머리표(Ⅰ Ⅱ …),
□(HY헤드라인M 15) → ○(휴먼명조 14) → -(14) → ※(11) 단계, 표(맑은 고딕 12). 그림은 캡션만 ※ 줄로 남긴다(SVG 는 넣지 않음).
원문 문장은 그대로 옮긴다(요약·평가 없음). 담당자 성명·연락처 칸은 '다잇다 노트'·누리집 주소로 채운다.

사용: python3 scripts/hwpx_report.py src/content/posts/<파일>.md [-o public/hwpx/<id>.hwpx]
      python3 scripts/hwpx_report.py --all        # 발행된 정책제안 리포트 전부 → public/hwpx/<id>.hwpx
      python3 scripts/hwpx_report.py --check <hwpx>  # XML 이 잘 열리는지
"""
import argparse, copy, re, sys, zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "scripts" / "data" / "hwpx" / "report_basic.hwpx"
POSTS = ROOT / "src" / "content" / "posts"
OUT_DIR = ROOT / "public" / "hwpx"
ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ", "Ⅺ", "Ⅻ"]
NS: dict[str, str] = {}
HP = ""


# ───────── 개조식 변환 ─────────
def _syl(ch: str):
    code = ord(ch) - 0xAC00
    return (code // 588, (code % 588) // 28, code % 28) if 0 <= code < 11172 else None


def _compose(cho: int, jung: int, jong: int) -> str:
    return chr(0xAC00 + cho * 588 + jung * 28 + jong)


def nominalize(sent: str) -> str:
    """서술형 문장 끝을 개조식 명사형으로: '한다'→'함', '이다'→'임', '있다'→'있음', '않는다'→'않음', '합니다'→'함'. 마지막 마침표는 뗀다."""
    t = sent.strip().rstrip(".。")
    m = re.match(r"^(.*?)([가-힣]+)((?:\([^()]*\)|[)\]」』\"”'’])*)$", t)   # 끝의 '(요지)' 같은 괄호 묶음은 꼬리로
    if not m:
        return t
    head, w, tail = m.groups()
    if w == "다" and head:                                                # '44%다' → '44%임'
        w2 = "임"
    elif w.endswith("다") and w[:-1] in ("하나", "둘", "셋", "넷", "다섯", "여섯", "일곱", "여덟", "아홉", "열"):
        w2 = w[:-1] + "임"
    elif w.endswith("습니다"):
        w2 = w[:-3] + "음"
    elif w.endswith("니다") and len(w) >= 3 and _syl(w[-3]) and _syl(w[-3])[2] == 17:   # 합니다·됩니다·입니다
        c, j, _ = _syl(w[-3]); w2 = w[:-3] + _compose(c, j, 16)
    elif w.endswith("다") and len(w) >= 2:
        base = w[:-1]
        if base.endswith("는") and len(base) >= 2:                      # 않는다·먹는다 → 않음·먹음
            w2 = base[:-1] + "음"
        else:
            sy = _syl(base[-1])
            if sy is None:
                return t
            c, j, jong = sy
            if len(base) == 1 and head and head[-1].isdigit():             # '3개다'·'5곳이다' 처럼 숫자+단위 뒤의 '다' 는 '임'
                w2 = base + "임"
            elif jong == 0:                                              # 이다·크다·되다·하다(하→함)
                w2 = base[:-1] + _compose(c, j, 16)
            elif jong == 4:                                            # 한다·된다·낸다·쓴다·부른다 → 함·됨·냄·씀·부름
                w2 = base[:-1] + _compose(c, j, 16)
            else:                                                      # 있다·없다·했다·같다·많다 → 있음·없음·했음·같음·많음
                w2 = base + "음"
    else:
        return t
    return head + w2 + tail


def sentences(text: str) -> list[str]:
    """문장 나누기: 숫자 뒤 마침표('2026. 9.', '3.1')는 문장 끝으로 보지 않는다."""
    parts = re.split(r"(?<=[^\d\s])\.\s+(?=\S)", text.strip())
    return [x.strip() for x in parts if x.strip()]


def gaejo(text: str) -> list[str]:
    """문단 → 개조식 줄 목록(문장마다 한 줄, 끝은 명사형)."""
    return [nominalize(x) for x in sentences(text)]


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
        lines_ = gaejo(text)
        if lines_:
            out.append(("o", lines_[0]))
            out.extend(("dash", x) for x in lines_[1:])

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
            out.append(("note", "[그림] " + nominalize(inline(cap.group(1))) if cap else "[그림]")); i += 1; continue
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
            out.extend(("note", x) for x in gaejo(inline(" ".join(q)))); continue
        li = re.match(r"^(\s*)([-*]|\d+[.)])\s+(.*)$", l)
        if li:
            flush(); text = li[3]
            while i + 1 < len(lines) and re.match(r"^\s+\S", lines[i + 1]) and not re.match(r"^\s*([-*]|\d+[.)])\s+", lines[i + 1]):
                i += 1; text += " " + lines[i].strip()
            num = li[2] if re.match(r"\d", li[2]) else ""
            gl = gaejo(inline(text)) or [""]
            out.append(("dash", (num + " " if num else "") + gl[0]))
            out.extend(("dash", "  " + x) for x in gl[1:]); i += 1; continue
        # 문단: 굵은 첫 문장(인사이트 형식의 핵심 문장)은 □ 로, 나머지는 ○
        m = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", l.strip())
        if m and not buf:
            flush(); out.append(("box", nominalize(inline(m[1]))))
            rest = m[2]
            if rest.strip():
                buf.append(rest)
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


def fmt_date(d) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return f"{d.year}. {d.month}. {d.day}."


def build(meta: dict, body_md: str, area: str, out: Path) -> None:
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
    title = re.sub(r"^\[정책제안\]\s*", "", str(meta.get("title", "")))
    line1 = f"정책제안 리포트{' · ' + area if area else ''}"
    # 표지
    replace_t(top[3], "2027년 회계연도 ", line1)
    replace_t(top[3], "회계감사인 선임 제안 요청서", title)
    set_para_text(top[8], fmt_date(meta.get("date", date.today())))
    for old, new in [("전 략 실", "다잇다 노트"), ("(전 략 부)", "(정책제안 리포트)"), ("홍길동 팀장", "운영자"), ("(123)456-7891", "note.daitda.co.kr"),
                     ("박진미 과장", ""), ("(123)456-7892", "")]:
        replace_t(top[12], old, new)
    for t in top[15].iter(HP + "t"):
        if t.text and "전" in t.text and "략" in t.text:
            t.text = "다잇다 노트" if t.text.strip() else t.text
    # 본문 블록 → 절
    blocks = body_blocks(body_md)
    sections: list[tuple[str, list]] = []
    summary: list = []
    desc = inline(str(meta.get("description") or meta.get("summary") or ""))
    for k, x in enumerate(gaejo(desc)):
        summary.append(("o" if k == 0 else "dash", x))
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
        fq = []
        for qa in faq:
            fq.append(("box", inline(str(qa.get("q", "")))))
            fq.extend(("o" if k == 0 else "dash", x) for k, x in enumerate(gaejo(inline(str(qa.get("a", ""))))))
        sections.append(("자주 묻는 질문", fq))
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
    preview = "\n".join([line1, title, fmt_date(meta.get("date", date.today()))] + [f"{ROMAN[i % 12]}. {s}" for i, (s, _) in enumerate(sections)])
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as zo:
        for n in names:
            data = z.read(n)
            if n == "Contents/section0.xml":
                data = new_sec.encode("utf-8")
            elif n == "Preview/PrvText.txt":
                data = preview.encode("utf-8")
            zo.writestr(zipfile.ZipInfo(n), data, compress_type=zipfile.ZIP_STORED if n == "mimetype" else zipfile.ZIP_DEFLATED)
    print(f"→ {out} ({out.stat().st_size:,} bytes, 절 {len(sections)}개)")


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
    desc_l = gaejo(inline(str(meta.get("description") or meta.get("summary") or "")))
    desc = " / ".join(desc_l[:1]); desc2 = " / ".join(desc_l[1:3])
    # 반론 절의 첫 문장들
    counter = []
    grab = False
    for k, p in blocks:
        if k == "section":
            grab = "반론" in str(p)
        elif grab and k in ("o", "box", "dash") and len(counter) < 3:
            counter.append(str(p)[:120])
    d = fmt_date(meta.get("date", date.today()))
    fills = [("OOO 신사업 보고서", title), ("폰트 HY헤드라인M, 크기 18", f"정책제안 리포트{' · ' + area if area else ''}"),
             ("<소속부서 : OOOO부서, 2022.12.31.>", f"<다잇다 노트, {d}>"),
             ("(본 문서를 한 페이지로 나타내기 위한 내용 작성 1줄 또는 2줄 이내)", desc),
             ("최신 기술을 접목한 OOOO 시스템의 사용자 친화적 UI/UX 개선을 위한 용역사업 추진", desc2),
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
            data = new_sec.encode("utf-8") if n == "Contents/section0.xml" else (f"{title}\n{d}".encode("utf-8") if n == "Preview/PrvText.txt" else z.read(n))
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
        print("ok:", a.check, z.namelist()[:3]); return 0
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
        build(meta, body, area_of(meta), out)
        build_summary(meta, body, area_of(meta), out.with_name(out.stem + "-요약.hwpx"), f.stem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
