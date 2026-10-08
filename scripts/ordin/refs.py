"""자치법규 조문에서 상위법령 인용을 뽑는다(정비 검토 2절).

인용 꼴: 「○○법」 제n조의m제k항제j호 / 「같은 법 시행령」 / 같은 법 제n조 / (이하 "법"이라 한다) 뒤의 '법 제n조'·'영 제n조'.
돌려주는 값: [{law, art, para, item, kind, ctx}] — law 는 원문 표기(겹낫표 안), art 는 '28' 또는 '28의2'.
"""
from __future__ import annotations

import re

NAME = r"「([^「」]{2,90})」"
ART = r"\s*제\s*(\d+)\s*조(?:\s*의\s*(\d+))?(?:\s*제\s*(\d+)\s*항)?(?:\s*제\s*(\d+)\s*호)?"
ALIAS_DEF = re.compile(NAME + r"[^「」]{0,40}?\(\s*이하\s*[“\"']([^”\"']{1,12})[”\"']\s*(?:이)?라\s*한다\s*\)")
ALIAS_DEF2 = re.compile(r"같은\s*법\s*(시행령|시행규칙)\s*\(\s*이하\s*[“\"']([^”\"']{1,12})[”\"']\s*(?:이)?라\s*한다\s*\)")
TOKEN = re.compile(NAME + r"(?:\s*\([^()]{0,60}\))?(?:" + ART + r")?|같은\s*법\s*(시행령|시행규칙)?(?:" + ART + r")?")


def norm_name(s: str) -> str:
    """비교용 법령 이름: 공백·가운뎃점 변이 제거."""
    return re.sub(r"[\s·ㆍ‧･・]", "", s or "")


def _art(m_no, m_ui):
    return f"{int(m_no)}" + (f"의{int(m_ui)}" if m_ui else "") if m_no else ""


def extract(articles: list[dict]) -> list[dict]:
    """articles: [{no: '제3조', text: '...'}] (부칙은 넣지 않는다). 조문 순서대로 읽어 '같은 법'·약칭을 풀이한다."""
    aliases: dict[str, str] = {}
    out: list[dict] = []
    last = ""
    for a in articles:
        text = a.get("text") or ""
        for m in ALIAS_DEF.finditer(text):
            aliases[m.group(2).strip()] = m.group(1).strip()
        for m in ALIAS_DEF2.finditer(text):
            if last:
                aliases[m.group(2).strip()] = f"{last} {m.group(1)}"
        # 1) 겹낫표 이름과 '같은 법'
        spans = []
        for m in TOKEN.finditer(text):
            if m.group(1):
                law = m.group(1).strip()
                no, ui, pa, it = m.group(2), m.group(3), m.group(4), m.group(5)
                kind = "named"
            else:
                if not last:
                    continue
                law = last if not m.group(6) else (re.sub(r"\s*(시행령|시행규칙)$", "", last) + " " + m.group(6))
                no, ui, pa, it = m.group(7), m.group(8), m.group(9), m.group(10)
                kind = "same"
            if not re.search(r"(법|법률|령|규칙|규정|고시|훈령|예규|지침|조례|기준|요령)$", law):
                continue   # 「 」 안이 법령 이름이 아님(서식 제목·사업명 등)
            last = law
            spans.append(m.span())
            out.append({"no": a.get("no", ""), "law": law, "art": _art(no, ui), "para": pa or "", "item": it or "", "kind": kind,
                        "ctx": text[max(0, m.start() - 30): m.end() + 50].replace("\n", " ")})
        # 2) 약칭: '법 제n조', '영 제n조', '시행령 제n조' (겹낫표·같은 법 안의 것은 건너뜀)
        if aliases:
            pat = re.compile(r"(?<![가-힣「])(" + "|".join(re.escape(k) for k in sorted(aliases, key=len, reverse=True)) + r")" + ART)
            for m in pat.finditer(text):
                if any(s <= m.start() < e for s, e in spans):
                    continue
                out.append({"no": a.get("no", ""), "law": aliases[m.group(1)], "art": _art(m.group(2), m.group(3)), "para": m.group(4) or "",
                            "item": m.group(5) or "", "kind": "alias", "ctx": text[max(0, m.start() - 30): m.end() + 50].replace("\n", " ")})
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
