#!/usr/bin/env python3
"""성장 정책 대안 프롬프트를 Gemini 로 돌린다(운영자 지시 2026-10-05: '조사 항목 수집부터 하고 제미나이로 돌려봐').

scripts/policy_lever_prompt.py 가 만든 프롬프트(docs/prompts/policy_levers_<area>.md)를 그대로 보내고, 답을
docs/drafts/policy-levers-<area>.md 에 **내부 초안**으로 저장한다(사이트에 싣지 않는다 — docs/ 는 빌드 대상이 아님, 원칙 5).

검사(자동, 사람 검토를 대신하지 않음)
- 숫자: 답에 나온 숫자가 프롬프트 [자료]에 없고, 같은 줄의 계산식(a × b ÷ c = d) 결과도 아니면 '확인할 숫자'로 적는다.
  처음 답에 그런 숫자가 많으면(5개 넘게) 목록을 붙여 한 번 다시 쓰게 한다.
- 계산식: '…= d' / '…≈ d' 꼴의 사칙연산을 다시 계산해 5% 넘게 어긋나면 '계산 확인'으로 적는다.
- 금지 표현: 평가·비판·과장 낱말과 '정부 건의'가 나오면 적는다.
검사 결과는 초안 맨 위 '자동 검사' 절에 남긴다.

사용: GEMINI_KEY=… python3 scripts/policy_lever_run.py --area service|mfg|all
키: GEMINI_KEY. 모델: GEMINI_MODEL(기본 growth_commentary 와 같음).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
GEMINI_KEY = os.environ.get("GEMINI_KEY", "").strip()
GEMINI_MODEL = (os.environ.get("GEMINI_MODEL", "") or "gemini-3.5-flash-lite").strip()
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

BANNED = ["획기적", "혁신적", "대폭", "부족하다", "미흡", "실패", "잘못", "바람직", "정부 건의", "시급", "반드시 해야"]
NUM = r"-?\d(?:[\d,]*\d)?(?:\.\d+)?"


def nums(s: str) -> set[str]:
    out = set()
    for m in re.findall(NUM, s):
        v = m.replace(",", "").lstrip("-")
        out.add(v)
        if "." in v:
            out.add(v.rstrip("0").rstrip("."))
    return out


def _f(x: str) -> float:
    return float(x.replace(",", ""))


def assumptions(text: str) -> set[str]:
    """대안 표의 '겨냥 성장' 칸 값 — 모델이 고른 가정이라 [자료]에 없어도 피연산자로 허용한다."""
    out, col = set(), None
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            col = None if not line.strip() else col
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if any("겨냥" in c for c in cells):
            col = next(i for i, c in enumerate(cells) if "겨냥" in c)
            continue
        if col is not None and col < len(cells):
            out |= nums(cells[col])
    return out


EXPR = re.compile(rf"((?:{NUM}\s*(?:%p|%|조 원|억 원|조|억)?\s*[×÷*/+\-−]\s*)+{NUM})\s*(?:%p|%|조 원|억 원|조|억)?\s*[=≈]\s*\+?({NUM})")


def calc_checks(text: str, base: set[str] | None = None) -> tuple[set[str], list[str]]:
    """'a × b ÷ c = d' 꼴을 앞에서부터 다시 계산한다. 맞는 식의 결과 d 는 허용 숫자가 되고, 어긋나면 목록.
    base(허용 숫자)를 주면 피연산자가 그 안에 없는 식도 '근거 없는 값으로 계산'으로 적는다(식은 맞아도 출발 값이 지어낸 것)."""
    ok, bad = set(), []
    for m in EXPR.finditer(text):
        expr, res = m.group(1), m.group(2)
        e = re.sub(r"%p|%|조 원|억 원|조|억", "", expr).replace("×", "*").replace("÷", "/").replace("−", "-").replace(",", "")
        if not re.fullmatch(r"[\d.\s*/+\-()]+", e):
            continue
        try:
            v = eval(e, {"__builtins__": {}})  # noqa: S307 — 숫자와 사칙연산 기호만 남긴 식
        except Exception:  # noqa: BLE001
            continue
        r = _f(res)
        if base is not None:
            ops = [o.replace(",", "").lstrip("-") for o in re.findall(NUM, expr)]
            miss = [o for o in ops if o not in base | ok and o.rstrip("0").rstrip(".") not in base | ok and o not in ("100",)]
            if miss:
                bad.append(f"{expr.strip()} = {res} (근거 없는 값 {', '.join(miss)})")
                continue
        # 결과는 단위가 바뀌어 적히기도 한다(비중 % × 성장 %p ÷ 100). 그대로·×100·÷100 가운데 하나가 맞으면 통과
        if not any(abs(c - r) <= max(0.05 * abs(r), 0.011) for c in (v, v * 100, v / 100)):
            bad.append(f"{expr.strip()} = {res} (다시 계산 {v:,.4g})")
            continue
        w = res.replace(",", "").lstrip("-")
        ok |= {w, w.rstrip("0").rstrip(".") if "." in w else w}
    return ok, bad


def number_check(answer: str, prompt: str) -> list[str]:
    allowed = nums(prompt) | assumptions(answer)
    ok, _ = calc_checks(answer, allowed)
    allowed |= ok
    out = []
    for m in re.findall(NUM, answer):
        v = m.replace(",", "").lstrip("-")
        w = v.rstrip("0").rstrip(".") if "." in v else v
        if v in allowed or w in allowed:
            continue
        if "." not in v and (int(v) <= 12 or 2000 <= int(v) <= 2100):   # 번호·연도
            continue
        out.append(m)
    return sorted(set(out), key=out.index)


def gemini(prompt: str) -> str:
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.3, "maxOutputTokens": 12000}}
    for attempt in range(3):
        try:
            r = requests.post(GEMINI_URL, json=body, headers={"x-goog-api-key": GEMINI_KEY}, timeout=240)
            r.raise_for_status()
            return "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"]).strip()
        except Exception as e:  # noqa: BLE001
            print(f"[levers] Gemini {attempt + 1}차 실패: {str(e)[:200]}")
            time.sleep(5 * (attempt + 1))
    return ""


def run(area: str) -> int:
    subprocess.run([sys.executable, str(ROOT / "scripts/policy_lever_prompt.py"), "--area", area], check=True)
    prompt = (ROOT / "docs/prompts" / f"policy_levers_{area}.md").read_text(encoding="utf-8")
    answer = gemini(prompt)
    if not answer:
        print(f"[levers] {area}: 답 없음")
        return 0
    base = lambda a: nums(prompt) | assumptions(a)
    bad = number_check(answer, prompt)
    calc_bad = calc_checks(answer, base(answer))[1]
    if len(bad) > 3 or calc_bad:
        print(f"[levers] {area}: 확인할 숫자 {len(bad)}개·식 {len(calc_bad)}개 → 다시 쓰게 함: {bad[:15]} {calc_bad[:5]}")
        again = gemini(prompt + "\n\n---\n앞선 답의 문제:\n- [자료]에도 계산식 결과에도 없는 숫자: " + (", ".join(bad[:30]) or "없음")
                       + "\n- 틀리거나 근거 없는 값으로 계산한 식: " + ("; ".join(calc_bad[:10]) or "없음")
                       + "\n이 숫자를 빼거나 [자료] 값에서 출발하는 계산식으로 다시 써라. 합계는 표의 값을 그대로 더한 식으로. 값이 없으면 '조사 뒤 정함'.")
        if again:
            bad2, calc2 = number_check(again, prompt), calc_checks(again, base(again))[1]
            if len(bad2) + 3 * len(calc2) <= len(bad) + 3 * len(calc_bad):
                answer, bad, calc_bad = again, bad2, calc2
    banned = [w for w in BANNED if w in answer]
    head = [f"<!-- scripts/policy_lever_run.py 가 만든 초안. 사이트에 싣지 않는다. 사람 검토 전 -->",
            f"# {'서비스업' if area == 'service' else '제조업'} 성장 정책 대안 — Gemini 초안({date.today().isoformat()})", "",
            f"- 프롬프트: `docs/prompts/policy_levers_{area}.md` · 모델 {GEMINI_MODEL}",
            "- 상태: **초안(검토 전)**. 숫자·계산·표현은 아래 자동 검사와 사람 검토를 거쳐 쓴다.", "",
            "## 자동 검사", "",
            f"- [자료]·계산식에 없는 숫자({len(bad)}개): {', '.join(bad) if bad else '없음'}",
            f"- 어긋나거나 근거 없는 값으로 계산한 식({len(calc_bad)}개): {'; '.join(calc_bad) if calc_bad else '없음'}",
            f"- 금지·주의 표현: {', '.join(banned) if banned else '없음'}", "", "---", ""]
    out = ROOT / "docs/drafts" / f"policy-levers-{area}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(head) + answer + "\n", encoding="utf-8")
    print(f"[levers] {area}: 저장 {out.relative_to(ROOT)} ({len(answer):,}자) · 확인할 숫자 {len(bad)} · 계산 {len(calc_bad)} · 표현 {banned}")
    return 0


def main(argv: list[str]) -> int:
    area = argv[argv.index("--area") + 1] if "--area" in argv else "all"
    if not GEMINI_KEY:
        print("GEMINI_KEY 없음")
        return 0
    for a in (["service", "mfg"] if area == "all" else [area]):
        run(a)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
