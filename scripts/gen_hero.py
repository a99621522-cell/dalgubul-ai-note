#!/usr/bin/env python3
"""리포트 대표 그림(hero) 생성 — Gemini 이미지 모델. GitHub Actions(GEMINI_KEY)에서 돌린다(이 세션 환경은 외부 접속 차단).
  python3 scripts/gen_hero.py src/content/posts/2026-09-27-policy-healthcare-medical-data.md   # 한 편
  python3 scripts/gen_hero.py --all [--force]     # format: insight 인 발행 리포트 가운데 hero.png 없는 것 전부
frontmatter:
  hero:
    prompt: "…(장면 묘사, 글자 없음, 사진 느낌)"
    caption: "…를 형상화 (AI 생성 이미지)"
결과: public/figures/<post-id>/hero.png. 실패는 로그만 남기고 건너뛴다(무인 실행)."""
from __future__ import annotations
import base64, json, os, re, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "src" / "content" / "posts"
OUT = ROOT / "public" / "figures"
KEY = os.environ.get("GEMINI_KEY", "").strip()
MODELS = [m.strip() for m in os.environ.get("GEMINI_IMAGE_MODELS", "gemini-2.5-flash-image,gemini-3-pro-image-preview,gemini-2.0-flash-preview-image-generation").split(",") if m.strip()]
STYLE = ("사실적인 사진 느낌의 장면. 글자·로고·숫자·간판 문구 없음. 특정 실존 기업·인물·건물 식별 불가. "
         "차분한 색, 자연광, 16:9. 대구광역시의 산업·도시 분위기.")


def fm_of(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    return m.group(1) if m else ""


def hero_prompt(fm: str) -> str:
    m = re.search(r"^hero:\s*\n((?:[ \t]+.*\n?)+)", fm, re.M)
    if not m:
        return ""
    p = re.search(r"^\s+prompt:\s*\"?(.*?)\"?\s*$", m.group(1), re.M)
    return p.group(1).strip() if p else ""


def redact(s: str) -> str:
    return re.sub(r"AIza[\w\-]+|key=[^&\s]+", "***", s)


def generate(prompt: str) -> bytes | None:
    if not KEY:
        print("GEMINI_KEY 없음"); return None
    body = {"contents": [{"parts": [{"text": f"{prompt}\n\n{STYLE}"}]}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"], "imageConfig": {"aspectRatio": "16:9"}}}
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(2):
            try:
                b = dict(body)
                if attempt == 1:  # imageConfig 를 못 받는 모델이면 빼고 다시
                    b = {"contents": body["contents"], "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}}
                r = requests.post(url, json=b, headers={"x-goog-api-key": KEY}, timeout=120)
                if r.status_code == 400 and attempt == 0:
                    print(f"[{model}] 400 — imageConfig 없이 재시도"); continue
                r.raise_for_status()
                for part in r.json().get("candidates", [{}])[0].get("content", {}).get("parts", []):
                    if "inlineData" in part:
                        return base64.b64decode(part["inlineData"]["data"])
                print(f"[{model}] 이미지 파트 없음"); break
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                print(f"[{model}] HTTP {code} {redact(str(e))[:160]}")
                if code in (401, 403):
                    return None
                break
            except Exception as e:  # noqa: BLE001
                print(f"[{model}] 실패 {redact(str(e))[:160]}"); time.sleep(3)
    return None


def run(path: Path, force: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    fm = fm_of(text)
    if not re.search(r"^format:\s*insight", fm, re.M):
        return False
    prompt = hero_prompt(fm)
    if not prompt:
        print(f"{path.name}: hero.prompt 없음"); return False
    out = OUT / path.stem / "hero.png"
    if out.exists() and not force:
        return False
    img = generate(prompt)
    if not img:
        print(f"{path.name}: 생성 실패"); return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img)
    print(f"{path.name}: → {out.relative_to(ROOT)} ({len(img):,} bytes)")
    return True


def main(argv: list[str]) -> int:
    force = "--force" in argv
    files = [Path(a) for a in argv if not a.startswith("--")]
    if "--all" in argv:
        files = [p for p in sorted(POSTS.glob("*-policy-*.md")) if re.search(r"^draft:\s*false", p.read_text(encoding="utf-8"), re.M)]
    n = sum(run(p, force) for p in files)
    print(f"생성 {n}건")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
