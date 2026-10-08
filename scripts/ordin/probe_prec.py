"""실측: 국가법령정보센터 판례(target=prec) 검색·본문 — 조례 관련 대법원 판결을 어떻게 거를지(로그만, 러너 전용)."""
import os
import re
import xml.etree.ElementTree as ET

import requests

OC = os.environ.get("LAW_OC", "test").strip() or "test"
B = "https://www.law.go.kr/DRF"
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"


def get(path, **p):
    p.setdefault("OC", OC)
    p.setdefault("type", "XML")
    try:
        r = S.get(f"{B}/{path}", params=p, timeout=60)
        return r.status_code, r.content
    except Exception as e:  # noqa: BLE001
        return 0, str(e).encode()


first_id = None
for q, sm in [("조례", 1), ("조례안", 1), ("조례안재의결무효확인", 1), ("조례", 2), ("조례무효", 1), ("자치법규", 2)]:
    st, b = get("lawSearch.do", target="prec", query=q, search=sm, display=5)
    print(f"## query={q} search={sm} HTTP {st} {len(b)}B")
    try:
        root = ET.fromstring(b)
    except Exception as e:  # noqa: BLE001
        print("  XML 오류", e, b[:300]); continue
    print("  totalCnt", root.findtext("totalCnt"), "| 루트 태그", [c.tag for c in root][:12])
    for it in list(root.iter("prec"))[:5]:
        d = {c.tag: (c.text or "").strip() for c in it}
        print("   ", d)
        first_id = first_id or d.get("판례일련번호")
# 법원·사건종류로 거르는 인자 실측
for extra in [{"curt": "대법원"}, {"org": "400201"}, {"nb": "추"}]:
    st, b = get("lawSearch.do", target="prec", query="조례", search=1, display=3, **extra)
    try:
        root = ET.fromstring(b); print("## 추가 인자", extra, "totalCnt", root.findtext("totalCnt"), [ (it.findtext('사건번호'), it.findtext('법원명')) for it in root.iter('prec')][:3])
    except Exception as e:  # noqa: BLE001
        print("## 추가 인자", extra, "오류", b[:200])
if first_id:
    st, b = get("lawService.do", target="prec", ID=first_id)
    print("## 본문 ID", first_id, "HTTP", st, len(b), "B")
    try:
        root = ET.fromstring(b)
        for c in root:
            print("  ", c.tag, (c.text or "").strip()[:200].replace("\n", " "))
    except Exception as e:  # noqa: BLE001
        print("  XML 오류", e, b[:500])
