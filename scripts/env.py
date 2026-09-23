#!/usr/bin/env python3
"""수집 스크립트가 함께 쓰는 .env 로더 (표준 라이브러리만).

- load_env()             프로젝트 루트의 .env 를 읽어 os.environ 에 넣는다. 이미 있는 환경변수(예: Actions secrets)가 우선.
                         값의 앞뒤 공백·따옴표·줄바꿈은 떼어 낸다(Secret 붙여넣기 때 엔터가 딸려 오는 사고 방지)
- get(name, default="")  strip 한 값
- missing(*names)        비어 있는 키 이름 목록
- require(*names)        비어 있는 키가 있으면 어느 키인지 찍고 종료(코드 2). 그 키 없이는 아무 일도 못 하는 도구용
  (매일 무인 실행되는 collect.py 처럼 '해당 소스만 건너뛰면 되는' 경우는 require 대신 missing 으로 이름만 찍고 계속 간다)
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_loaded = False


def load_env(path: Path | None = None) -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    p = path or (ROOT / ".env")
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split("  #", 1)[0].strip().strip('"').strip("'")   # 줄 끝 주석·따옴표 제거
        os.environ.setdefault(k.strip(), v)


def get(name: str, default: str = "") -> str:
    load_env()
    return (os.environ.get(name) or default).strip()


def missing(*names: str) -> list[str]:
    return [n for n in names if not get(n)]


def require(*names: str) -> None:
    m = missing(*names)
    if m:
        print(f"[env] 비어 있는 키: {', '.join(m)} — .env 또는 GitHub Secrets 에 넣어 주세요 (.env.example 참고)")
        sys.exit(2)
