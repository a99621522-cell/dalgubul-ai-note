"""외감 재무 행 검사 — collect_dart_audit.py(수집)·audit_compare.py(집계)가 같이 쓴다."""
from __future__ import annotations


def scale_check(row: dict) -> str:
    """손익 표만 단위·열을 잘못 읽은 행 거르기(2026-11-03 대성테크: 재무상태표는 맞고 매출만 1,000배·전기 매출 음수).
    audit_compare.py 도 같은 규칙으로 옛 행을 거른다."""
    def f(k):
        try:
            return float(row.get(k)) if row.get(k) not in (None, "") else None
        except (TypeError, ValueError):
            return None
    s, a = f("sales"), f("assets")
    if s is not None and s < 0:
        return "매출 음수"
    if s and a and a > 0 and s / a > 30:
        return "매출·자산 규모 어긋남"
    return ""
