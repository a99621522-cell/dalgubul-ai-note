"""자치법규 정비 검토 화면 문구 검사 — 판정·평가·순위 낱말과 개인 연락처가 화면 틀(템플릿·설정)에 없는지 본다.
자치법규·법령 원문 인용은 검사하지 않는다(원문에 '무효' 같은 낱말이 있을 수 있음). 실패면 종료 코드 1."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [*ROOT.glob("src/pages/ordinance/**/*.astro"), ROOT / "src/components/OrdinCand.astro", ROOT / "src/lib/ordinance.ts",
         ROOT / "config/ordinance_signals.yml"]
BAD = re.compile(r"(?<!상)위법|무효|방치|미정비\s*기관|순위|TOP|최다|우수|부실|잘못")
PHONE = re.compile(r"0\d{1,2}-\d{3,4}-\d{4}")
bad = 0
for f in FILES:
    for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip().startswith(("//", "/**", "*", "#")):
            continue
        for rx in (BAD, PHONE):
            for m in rx.finditer(line):
                print(f"{f.relative_to(ROOT)}:{i}: '{m.group(0)}' — {line.strip()[:90]}")
                bad += 1
print(f"검사 파일 {len(FILES)} · 걸린 곳 {bad}")
sys.exit(1 if bad else 0)
