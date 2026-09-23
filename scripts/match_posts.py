#!/usr/bin/env python3
"""이미 있는 글(src/content/posts/*.md)에 예산 사업 대조 결과를 소급해 넣는다.
collect.py 는 새 초안을 만들 때만 대조하므로, 사업 DB(programs_*.csv)가 갱신됐거나
대조 규칙이 바뀌었을 때 한 번 돌린다. 이미 program_code 가 있는 글은 건드리지 않는다.

사용: python3 scripts/match_posts.py            # 적용
      python3 scripts/match_posts.py --dry-run  # 결과만 보기
      python3 scripts/match_posts.py --force    # 기존 program_* 도 다시 계산
"""
import json
import re
import sys
from pathlib import Path

from programs import match_program

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

POSTS = Path(__file__).resolve().parent.parent / "src" / "content" / "posts"
DRY = "--dry-run" in sys.argv
FORCE = "--force" in sys.argv
FIELDS = ("program_code", "program_name", "program_ministry", "program_budget_2026", "program_score")


def q(s: str) -> str:
    """YAML 큰따옴표 문자열(JSON 규칙과 호환)."""
    return json.dumps(s, ensure_ascii=False)


def fm_value(fm: str, key: str) -> str:
    m = re.search(rf'^{key}:\s*"?(.*?)"?\s*$', fm, re.M)
    return m.group(1) if m else ""


def main() -> None:
    matched = skipped = untouched = 0
    for p in sorted(POSTS.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        _, fm, body = parts
        if "program_code:" in fm and not FORCE:
            untouched += 1
            continue
        title, source = fm_value(fm, "title"), fm_value(fm, "source")
        pm = match_program(title, source)
        if not pm:
            skipped += 1
            if FORCE and not DRY and any(l.startswith(FIELDS) for l in fm.split("\n")):
                lines = [l for l in fm.split("\n") if not l.startswith(FIELDS)]
                p.write_text("---" + "\n".join(lines) + "---" + body, encoding="utf-8")
                print(f"  - 해제 {title[:44]} (기준 미달로 기존 대조 제거)")
            continue
        matched += 1
        print(f"  ★ {pm['score']:.2f} {title[:44]} → {pm['ministry']} {pm['name']} ({pm['code']})")
        if DRY:
            continue
        lines = [l for l in fm.split("\n") if not l.startswith(FIELDS)]  # --force 일 때 기존 값 제거
        add = [
            f"program_code: {q(pm['code'])}",
            f"program_name: {q(pm['name'])}",
            f"program_ministry: {q(pm['ministry'])}",
            f"program_budget_2026: {q(pm['budget_2026'])}",
            f"program_score: {pm['score']}",
        ]
        # draft: 줄 앞에 넣어 프론트매터 끝부분에 모아 둔다
        idx = next((i for i, l in enumerate(lines) if l.startswith("draft:")), len(lines) - 1)
        lines[idx:idx] = add
        p.write_text("---" + "\n".join(lines) + "---" + body, encoding="utf-8")
    print(f"\n대조 완료: 매칭 {matched} · 미매칭 {skipped} · 이미 있음 {untouched}" + (" (dry-run, 파일 미변경)" if DRY else ""))


if __name__ == "__main__":
    main()
