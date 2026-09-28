#!/usr/bin/env python3
"""HWP(5.0, 한글 2002 이후 OLE 형식) 본문 글자 추출 — olefile + zlib 만 쓴다(pyhwp 의 hwp5txt 가 없거나 실패할 때의 대체).

구조: OLE 저장소 안 FileHeader(속성 플래그: bit0 압축, bit1 암호화, bit2 배포용) + BodyText/Section0..N(레코드 스트림, 보통 zlib raw deflate).
레코드 헤더 4바이트 = 태그(10비트) | 레벨(10비트) | 크기(12비트, 0xFFF 이면 다음 4바이트가 크기). 본문 글자는 HWPTAG_PARA_TEXT(0x10+51=67)
레코드의 UTF-16LE 문자열이며, 제어문자(0~31) 가운데 0·10·13·24~31 은 1글자, 나머지(인라인·확장 컨트롤)는 8글자(16바이트)를 차지한다.
표 안 글자도 같은 섹션의 PARA_TEXT 레코드라 함께 나온다. 암호화·배포용 문서는 풀지 않고 빈 글자를 돌려준다(로그만).

사용: python3 scripts/hwp_text.py 파일.hwp [파일2.hwp ...]   # 표준출력으로 글자
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

try:
    import olefile
except ImportError:  # pragma: no cover
    olefile = None

PARA_TEXT = 0x10 + 51
ONE_CHAR_CTRL = {0, 10, 13} | set(range(24, 32))


def _records(data: bytes):
    i, n = 0, len(data)
    while i + 4 <= n:
        (h,) = struct.unpack_from("<I", data, i)
        tag, size = h & 0x3FF, (h >> 20) & 0xFFF
        i += 4
        if size == 0xFFF:
            if i + 4 > n:
                break
            (size,) = struct.unpack_from("<I", data, i)
            i += 4
        yield tag, data[i:i + size]
        i += size


def _para_text(payload: bytes) -> str:
    """제어문자를 걷어낸 UTF-16LE 조각을 모아 한 번에 풀어 서로게이트 쌍(보충 문자)이 깨지지 않게 한다."""
    out, buf, i, n = [], [], 0, len(payload) - (len(payload) % 2)

    def flush():
        if buf:
            out.append(b"".join(buf).decode("utf-16-le", errors="replace"))
            buf.clear()
    while i + 2 <= n:
        (ch,) = struct.unpack_from("<H", payload, i)
        if ch < 32:
            flush()
            if ch in (10, 13):
                out.append("\n")
            elif ch == 9:
                out.append("\t")
            i += 2 if (ch in ONE_CHAR_CTRL or ch == 9) else 16   # 인라인·확장 컨트롤: 8 WCHAR
            continue
        buf.append(payload[i:i + 2])
        i += 2
    flush()
    return "".join(out).encode("utf-8", errors="replace").decode("utf-8")


def extract(path: str | Path) -> str:
    """HWP 5 본문 글자. 읽을 수 없으면 '' (이유는 표준오류)."""
    if olefile is None:
        print("hwp_text: olefile 없음(pip install olefile)", file=sys.stderr)
        return ""
    try:
        ole = olefile.OleFileIO(str(path))
    except Exception as e:  # noqa: BLE001
        print(f"hwp_text: OLE 아님 {path}: {str(e)[:60]}", file=sys.stderr)
        return ""
    try:
        if not ole.exists("FileHeader"):
            print(f"hwp_text: FileHeader 없음 {path}", file=sys.stderr)
            return ""
        head = ole.openstream("FileHeader").read()
        flags = struct.unpack_from("<I", head, 36)[0] if len(head) >= 40 else 0
        compressed, encrypted, distribution = flags & 1, flags & 2, flags & 4
        if encrypted or distribution:
            print(f"hwp_text: 암호화/배포용 문서라 본문을 읽지 않음 {path}", file=sys.stderr)
            return ""
        sections = sorted((e for e in ole.listdir() if len(e) == 2 and e[0] == "BodyText" and e[1].startswith("Section")),
                          key=lambda e: int("".join(c for c in e[1] if c.isdigit()) or 0))
        paras = []
        for e in sections:
            raw = ole.openstream(e).read()
            if compressed:
                try:
                    raw = zlib.decompress(raw, -15)
                except zlib.error:
                    try:
                        raw = zlib.decompress(raw)
                    except zlib.error as ze:
                        print(f"hwp_text: 압축 해제 실패 {e}: {ze}", file=sys.stderr)
                        continue
            for tag, payload in _records(raw):
                if tag == PARA_TEXT:
                    t = _para_text(payload).strip("\n")
                    if t.strip():
                        paras.append(t)
        return "\n".join(paras)
    finally:
        ole.close()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(extract(p))
