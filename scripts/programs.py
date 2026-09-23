#!/usr/bin/env python3
"""부처 사업설명자료 DB(scripts/data/programs_*.csv)와 공고 제목을 잇는 공용 모듈. 표준 라이브러리만 쓴다.

- norm()          사업명·제목 정규화 (match_daegu.py 와 같은 규칙 — 여기 한 곳에만 둔다)
- clean_title()   공고 제목에서 연도·차수·'모집 공고' 같은 꼬리를 떼어 사업명에 가깝게 만든다
- match_program() 제목(+소관부처) → 유사도 0.85 이상인 사업 1건 또는 None

원칙: 틀린 예산을 붙이는 것이 안 붙이는 것보다 나쁘다(CLAUDE.md 글 작성 원칙 1).
그래서 부처가 다르면 후보에서 빼고, 문턱은 0.85 로 둔다. 결과에는 유사도를 함께 실어 글에서 '자동 대조'임을 밝힌다.

시험: python3 scripts/programs.py "2026년 산업기술국제협력(양자-스페인) 접수 공고" 산업통상부
"""
import csv
import difflib
import glob
import re
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
THRESHOLD = 0.85


def norm(s: str) -> str:
    """공백·구분기호와 (R&D) 같은 꼬리표를 떼고 비교용 문자열로. match_daegu.py 가 쓰던 규칙 그대로."""
    return re.sub(r"\(R&D\)|\(정보화\)|\(국가직접지원\)|\(국가직접지|원\)|\(자율\)|\(1단계전환\)|\(2단계전환\)|\s|[·ㆍ‧,()/]", "", s or "").lower()


_TAIL = re.compile(
    r"(참여|참가|수혜|지원)?\s*(기업|업체|과제|스타트업|참가업체|수혜기업|참여기업|사업자)?\s*"
    r"(모집|접수|선정|시행|추진|신청)?\s*(계획)?\s*(재?공고|안내|알림)\s*$"
)


def clean_title(title: str, ministry: str = "") -> str:
    """'[대구] 2026년 2차 ○○ 지원사업 참여기업 모집 공고' → '○○ 지원사업'."""
    t = re.sub(r"^\[[^\]]+\]\s*", "", title or "")
    if ministry:
        t = t.replace(ministry, " ")
    t = re.sub(r"20\d\d년도?\s*", "", t)
    t = re.sub(r"(제\s?\d+차년도|제\s?\d+차|\d+차년도|\d+차|상반기|하반기|추가|연장|변경|재)\s*", "", t)
    t = re.sub(r"\([^)]*\)", "", t)
    t = _TAIL.sub("", t)
    return t.strip()


def ministry_norm(m: str) -> str:
    m = re.sub(r"\s", "", m or "")
    return re.sub(r"(부|처|청|위원회)$", "", m)


def ministry_compatible(a: str, b: str) -> bool:
    """부처가 다르면 False. 어느 쪽이든 비어 있으면 막지 않는다(제목 유사도 문턱이 지킨다).
    '산업통상자원부'(옛 이름) 와 '산업통상부' 처럼 한쪽이 다른 쪽을 포함하면 같은 부처로 본다."""
    a, b = ministry_norm(a), ministry_norm(b)
    if not a or not b:
        return True
    return a == b or a in b or b in a


_cache: list[dict] | None = None


def load_programs() -> list[dict]:
    """programs_*.csv 전부. 각 행에 _src(파일), _n(정규화 사업명)을 붙여 둔다."""
    global _cache
    if _cache is not None:
        return _cache
    rows: list[dict] = []
    for f in sorted(glob.glob(str(DATA / "programs_*.csv"))):
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                if not (r.get("name") or "").strip():
                    continue
                r["_src"] = Path(f).stem.replace("programs_", "")
                r["_n"] = norm(r["name"])
                rows.append(r)
    _cache = rows
    return rows


def _score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    sc = difflib.SequenceMatcher(None, a, b).ratio()
    # 한쪽이 다른 쪽을 통째로 품으면 같은 사업일 가능성이 높다. 단, 품긴 쪽이 6자 미만이면(예: '장애인기업', '마케팅')
    # 그 낱말이 들어간 아무 공고나 붙어 버리므로 보정하지 않는다
    if min(len(a), len(b)) >= 6 and (a in b or b in a):
        sc = max(sc, 0.9)
    return sc


_GENERIC_TAIL = re.compile(r"(지원)?사업$|육성$")


def match_program(title: str, ministry: str = "", threshold: float = THRESHOLD) -> dict | None:
    """공고 제목(+소관부처) 과 가장 비슷한 사업. threshold 미만이면 None.
    반환: {"code","name","ministry","budget_2026","score","src"}"""
    n = norm(clean_title(title, ministry))
    n2 = _GENERIC_TAIL.sub("", n)
    best: tuple[float, dict | None] = (0.0, None)
    for r in load_programs():
        if not ministry_compatible(ministry, r.get("ministry", "")):
            continue
        rn = r["_n"]
        sc = _score(n, rn)
        rn2 = _GENERIC_TAIL.sub("", rn)
        if len(n2) >= 4 and len(rn2) >= 4:   # '○○지원사업' 꼬리만 다른 경우. 너무 짧아지면 비교하지 않는다
            sc = max(sc, _score(n2, rn2))
        if sc > best[0]:
            best = (sc, r)
    if best[1] is None or best[0] < threshold:
        return None
    r = best[1]
    return {
        "code": (r.get("code") or "").strip(),
        "name": (r.get("name") or "").strip(),
        "ministry": (r.get("ministry") or "").strip(),
        "budget_2026": (r.get("budget_2026") or "").strip(),
        "score": round(best[0], 2),
        "src": r["_src"],
    }


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    title = sys.argv[1]
    ministry = sys.argv[2] if len(sys.argv) > 2 else ""
    print("정리한 제목:", clean_title(title, ministry), "→", norm(clean_title(title, ministry)))
    print("결과:", match_program(title, ministry))
