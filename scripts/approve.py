#!/usr/bin/env python3
"""초안 승인 도구. draft: true 인 글을 목록으로 보여주고 번호로 승인/삭제한다.
사용: python3 scripts/approve.py           (대화식)
      python3 scripts/approve.py --list    (목록만)
"""
import re, sys
from pathlib import Path

# Windows 콘솔(cp949)에서 한글 제목이 깨지지 않게 (collect.py 와 같은 처리)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

POSTS = Path(__file__).resolve().parent.parent / "src" / "content" / "posts"

def drafts():
    out = []
    for p in sorted(POSTS.glob("*.md")):
        head = p.read_text(encoding="utf-8").split("---", 2)
        if len(head) < 3: continue
        fm = head[1]
        if re.search(r"^draft:\s*true", fm, re.M):
            title = re.search(r'^title:\s*"?(.*?)"?\s*$', fm, re.M)
            cat = re.search(r"^category:\s*(\S+)", fm, re.M)
            out.append((p, title.group(1) if title else p.name, cat.group(1) if cat else "?"))
    return out

def main():
    ds = drafts()
    if not ds:
        print("승인 대기 초안이 없습니다."); return
    for i, (p, t, c) in enumerate(ds, 1):
        print(f"{i:2d}. [{c}] {t}   ({p.name})")
    if "--list" in sys.argv: return
    print("\n승인할 번호(쉼표 구분), 삭제는 'd3' 형식, 전체 승인은 a, 종료는 q")
    ans = input("> ").strip()
    if ans == "q": return
    targets = range(1, len(ds)+1) if ans == "a" else []
    for tok in ans.split(","):
        tok = tok.strip()
        if tok.startswith("d") and tok[1:].isdigit():
            p = ds[int(tok[1:])-1][0]; p.unlink(); print("삭제:", p.name)
        elif tok.isdigit():
            targets = list(targets) + [int(tok)]
    for n in sorted(set(targets)):
        p = ds[n-1][0]
        txt = p.read_text(encoding="utf-8").replace("draft: true", "draft: false", 1)
        p.write_text(txt, encoding="utf-8"); print("승인:", p.name)
    print("git add/commit/push 하면 Cloudflare가 자동 배포합니다.")

if __name__ == "__main__":
    main()
