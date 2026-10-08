"""자치법규 조문에서 상위법령 인용을 뽑는다(정비 검토 2절).

인용 꼴: 「○○법」 제n조의m제k항제j호 / 「같은 법 시행령」 / 같은 법 제n조 / (이하 "법"이라 한다) 뒤의 '법 제n조'·'영 제n조'.
돌려주는 값: [{law, art, para, item, kind, ctx}] — law 는 원문 표기(겹낫표 안), art 는 '28' 또는 '28의2'.
"""
from __future__ import annotations

import html
import re

NAME = r"「([^「」]{2,90})」"
ART = r"\s*제\s*(\d+)\s*조(?:\s*의\s*(\d+)(?!\s*호))?(?:\s*제\s*(\d+)\s*항)?(?:\s*제\s*(\d+)\s*호)?"
ALIAS_DEF = re.compile(NAME + r"\s*(시행령|시행규칙)?(?:(?!같은|및|와|과)[^「」]){0,40}?\(\s*이하\s*[“\"']([^”\"']{1,12})[”\"']\s*(?:이)?라\s*한다\s*\)")
ALIAS_DEF2 = re.compile(r"같은\s*법\s*(시행령|시행규칙)\s*\(\s*이하\s*[“\"']([^”\"']{1,12})[”\"']\s*(?:이)?라\s*한다\s*\)")
TOKEN = re.compile(NAME + r"(?:\s*(시행령|시행규칙)(?![가-힣]))?(?:\s*\([^()]{0,60}\))?(?:" + ART + r")?|같은\s*법\s*(시행령|시행규칙)?(?:" + ART + r")?")


def norm_name(s: str) -> str:
    """비교용 법령 이름: 문자 참조(&#8231;) 풀고 공백·가운뎃점·쉼표 변이 제거."""
    return re.sub(r"[\s·ㆍ‧･・‧,，]", "", html.unescape(s or ""))


def _art(m_no, m_ui):
    return f"{int(m_no)}" + (f"의{int(m_ui)}" if m_ui else "") if m_no else ""


def extract(articles: list[dict]) -> list[dict]:
    """articles: [{no: '제3조', text: '...'}] (부칙은 넣지 않는다). 조문 순서대로 읽어 '같은 법'·약칭을 풀이한다."""
    aliases: dict[str, str] = {}
    out: list[dict] = []
    last = ""        # 마지막으로 인용한 '법률'(…법·…법률) — '같은 법'이 가리키는 것. 시행령·조례는 넣지 않는다
    for a in articles:
        text = html.unescape(a.get("text") or "")
        for m in ALIAS_DEF.finditer(text):   # 「…법」 시행령(이하 "영") 처럼 겹낫표 밖에 붙인 시행령·시행규칙도 이름에 넣는다
            aliases[m.group(3).strip()] = re.sub(r"\s+", " ", m.group(1).strip()) + (f" {m.group(2)}" if m.group(2) else "")
        for m in ALIAS_DEF2.finditer(text):
            # '같은 법 시행령(이하 "영")' — 바로 앞에 나온 법률 이름(겹낫표)을 찾는다
            prev = [x for x in re.finditer(NAME, text[: m.start()]) if re.search(r"(법|법률)$", x.group(1).strip())]
            base = re.sub(r"\s+", " ", prev[-1].group(1).strip()) if prev else last
            if base:
                aliases[m.group(2).strip()] = f"{base} {m.group(1)}"
        # 겹낫표 이름·'같은 법'·약칭('법 제n조')을 글 순서대로 읽는다 — '같은 법'은 바로 앞에 나온 법률(약칭 포함)을 가리킨다
        toks = [(m.start(), "t", m) for m in TOKEN.finditer(text)]
        if aliases:
            pat = re.compile(r"(?<![가-힣「])(?<!같은 )(?<!같은)(" + "|".join(re.escape(k) for k in sorted(aliases, key=len, reverse=True)) + r")" + ART)
            toks += [(m.start(), "a", m) for m in pat.finditer(text)]
        toks.sort(key=lambda x: x[0])
        spans = []
        for pos, kind, m in toks:
            if kind == "a":
                if any(s0 <= pos < e0 for s0, e0 in spans):
                    continue
                law = aliases[m.group(1)]
                no, ui, pa, it = m.group(2), m.group(3), m.group(4), m.group(5)
                k = "alias"
            elif m.group(1):
                law = re.sub(r"\s+", " ", m.group(1).strip()) + (f" {m.group(2)}" if m.group(2) else "")
                no, ui, pa, it = m.group(3), m.group(4), m.group(5), m.group(6)
                k = "named"
            else:
                if not last:
                    continue
                # 앞 인용과 이 '같은 법' 사이에 겹낫표 없이 쓴 법률 인용('지방세징수법 제27조')이 끼면 무엇을 가리키는지 알 수 없어 건너뛴다
                gap = text[(spans[-1][1] if spans else max(0, m.start() - 80)): m.start()]
                if re.search(r"[가-힣]+법(률)?\s*제\s*\d+\s*조", gap) and not re.search(r"(?<![가-힣])(법|영)\s*제\s*\d+\s*조", gap):
                    continue
                law = last if not m.group(7) else f"{last} {m.group(7)}"
                no, ui, pa, it = m.group(8), m.group(9), m.group(10), m.group(11)
                k = "same"
            if not re.search(r"(법|법률|령|규칙|규정|고시|훈령|예규|지침|요령|기준|조례)$", law):
                continue   # 「 」 안이 법령 이름이 아님(서식 제목·사업명 등)
            if re.search(r"(법|법률)$", law):
                last = law
            if kind == "t":
                spans.append(m.span())
            out.append({"no": a.get("no", ""), "law": law, "art": _art(no, ui), "para": pa or "", "item": it or "", "kind": k,
                        "ctx": text[max(0, m.start() - 30): m.end() + 50].replace("\n", " ")})
    return out


if __name__ == "__main__":
    import gzip, sys
    txt = gzip.open(sys.argv[1], "rt", encoding="utf-8").read()
    arts, cur = [], None
    for line in txt.splitlines():
        m = re.match(r"(제\d+조(?:의\d+)?)\s*\(", line)
        if m:
            cur = {"no": m.group(1), "text": line}
            arts.append(cur)
        elif cur:
            cur["text"] += "\n" + line
    for r in extract(arts):
        print(r["no"], r["kind"], r["law"], r["art"], r["para"], r["item"], "|", r["ctx"][:70])
