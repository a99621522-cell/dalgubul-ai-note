#!/usr/bin/env python3
"""지방재정365(lofin365.go.kr) 대구 세출예산 요청 확인용 — 로그만 찍고 저장소는 바꾸지 않는다(2026-10-05, GRDP 기여 계산 내부 초안용).
조사 메모 docs/drafts/lofin365-endpoints.md 의 '다음에 확인할 것' 1~3: 대구 지역 코드, 기능별 열 이름, 성질별 세출 데이터셋, Sheet 내려받기 요청.
robots.txt Allow /, 로그인 없는 화면만. 요청 사이 1초.
사용: python3 scripts/lofin_probe.py [--no-browser]
"""
from __future__ import annotations

import json
import re
import sys
import time

import requests

BASE = "https://www.lofin365.go.kr"
UA = {"User-Agent": "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"}
S = requests.Session()
S.headers.update(UA)
MENU = {"menuUrl": "/lf/lnncGramStst/laf/bdgSvi/retvLstByacBfae.do", "menuNm": "기능별 회계별 세출예산", "menuParaCn": "STST",
        "menuId": "LF3110102", "uprMenuId": "LF3110100", "crtrLvl": "", "subCode": ""}


def show(title: str, text: str, n: int = 4000) -> None:
    print(f"\n===== {title} ({len(text)}자) =====")
    print(text[:n])


def post(path: str, **kw):
    time.sleep(1)
    try:
        r = S.post(BASE + path, timeout=60, **kw)
        return r
    except Exception as e:  # noqa: BLE001
        print(f"[실패] {path}: {str(e)[:200]}")
        return None


def requests_part() -> None:
    try:
        S.get(BASE + "/portal/LF3110102.do", timeout=30)
    except Exception as e:  # noqa: BLE001
        print("첫 화면 실패", e)
        return
    r = post("/lf/lnncGramStst/laf/bdgSvi/sidoLF03002M2Ajax.do", data={"fyr": "2026"})
    if r is not None:
        show("시도 목록 sidoLF03002M2Ajax", r.text, 3000)
    # HTML 조각: 열 이름(th)·스크립트 속 요청 주소
    r = post("/lf/lnncGramStst/laf/bdgSvi/retvLstByacBfae.do", data={**MENU, "inqYmd": "2026"})
    if r is not None:
        t = r.text
        print("\n===== 조각 retvLstByacBfae.do 스크립트 속 요청 주소 =====")
        print(sorted(set(re.findall(r"[\"'](/lf/[^\"']+\.do)", t))))
        ths = [re.sub(r"<[^>]+>|\s+", " ", x).strip() for x in re.findall(r"<th[^>]*>(.*?)</th>", t, re.S)]
        print("th:", [x for x in ths if x][:80])
        for m in re.finditer(r"(inqCap|inqSgg|amt\d+)[^\n]{0,160}", t):
            print("  ", m.group(0)[:200])
    for cap, sgg in [("2700000", ""), ("2700000", "2700000"), ("27", ""), ("", "")]:
        r = post("/lf/lnncGramStst/laf/bdgSvi/retvLstByacBfaeAjax.do", data={**MENU, "inqYmd": "2026", "inqCap": cap, "inqSgg": sgg})
        if r is None:
            continue
        try:
            j = r.json()
            rows = (j.get("result") or {}).get("byacBfaeIxRsltDto") or []
            show(f"기능별 inqCap={cap!r} inqSgg={sgg!r}: 행 {len(rows)}, paramDto", json.dumps(j.get("paramDto"), ensure_ascii=False), 1500)
            for x in rows[:20]:
                print(json.dumps(x, ensure_ascii=False)[:700])
        except Exception:  # noqa: BLE001
            show(f"기능별 {cap}/{sgg} (JSON 아님) HTTP {r.status_code}", r.text, 800)
    for fy in ("2024", "2025", "2026"):
        r = post("/lf/lnncGramStst/lnncIpaByatcBdgCrtr/bfaeSvi/retvLstBfaeGov.do",
                 json={"menuId": "LCTBMM000", "rgnzDvCd": "02", "fyr": fy, "byatcClsTy": "LCTBBDG01", "pfaIndcCd": "A129", "tab": "gov", "waLafCd": ""})
        if r is None:
            continue
        try:
            d = [x for x in r.json().get("bfaeIxInqRsltDto", []) if str(x.get("lafCd", "")).startswith("27")]
            print(f"\n===== 통합공시 세출예산 {fy} 대구(27…) {len(d)}곳 =====")
            for x in d:
                print(json.dumps(x, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            show(f"통합공시 {fy} JSON 아님", r.text, 500)


def browser_part() -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(user_agent=UA["User-Agent"])
        log: list[str] = []

        def on_resp(resp):
            req = resp.request
            if req.method == "POST" and "lofin365" in req.url:
                try:
                    body = resp.text()
                except Exception:  # noqa: BLE001
                    body = ""
                log.append(f"POST {req.url}\n  body: {(req.post_data or '')[:600]}\n  resp({len(body)}): {body[:1200]}")
        pg.on("response", on_resp)

        def content_text() -> str:
            return pg.evaluate("""() => { const m = document.querySelector('#contents, #content, main, .contents, .sub_contents') || document.body;
                                   return m.innerText; }""")

        for q in ("성질별", "세출결산", "성질별 세출"):
            log.clear()
            try:
                pg.goto(f"{BASE}/portal/LF5100000.do?srchCrstCn={q}&frstParamYn=Y", wait_until="networkidle", timeout=90000)
                pg.wait_for_timeout(2500)
                t = content_text()
                i = t.find("검색결과")
                show(f"데이터셋 검색 '{q}' 화면 글자", t[i if i > 0 else 0:], 6000)
                links = pg.evaluate("""() => [...document.querySelectorAll('a[onclick], a[href*=pdtaId], [data-pdta-id], [onclick*=pdta]')]
                                         .map(a => (a.innerText||'').trim().slice(0,60) + ' | ' + (a.getAttribute('onclick')||a.getAttribute('href')||'')).filter(s => /pdta|Dtst|dtst/.test(s)).slice(0,80)""")
                print("링크:", *links, sep="\n  ")
                print("\n--- POST 요청 ---\n" + "\n".join(log[-8:]))
            except Exception as e:  # noqa: BLE001
                print(f"[검색 {q} 실패] {str(e)[:200]}")
            time.sleep(1)

        # Sheet 화면: 내려받기 요청 주소·인자
        pid = "RL5CZ30XLWDXZAKXS5LP134169"   # 구조별 기능별 세출예산
        log.clear()
        try:
            pg.goto(f"{BASE}/portal/LF5110000.do?pdtaId={pid}&rdIncrYn=Y", wait_until="networkidle", timeout=90000)
            pg.wait_for_timeout(2500)
            ctl = pg.evaluate("""() => [...document.querySelectorAll('input, select, button, a')].map(e => [e.tagName, e.id, e.name||'', (e.innerText||e.value||'').trim().slice(0,30), (e.getAttribute('onclick')||'').slice(0,160)].join(' | '))
                                      .filter(s => /csv|CSV|json|JSON|xlsx|XLSX|down|Down|srch|inq|fyr|lafNm|rgn|검색|조회/.test(s)).slice(0,80)""")
            print("\n===== Sheet 화면 조작 요소 =====", *ctl, sep="\n  ")
            print("\n--- Sheet 첫 POST ---\n" + "\n".join(log[-4:]))
            for label in ("CSV", "csv"):
                loc = pg.get_by_text(label, exact=True)
                if loc.count():
                    log.clear()
                    try:
                        with pg.expect_download(timeout=60000) as dl:
                            loc.first.click()
                        d = dl.value
                        print(f"\n내려받기: {d.url} 파일 {d.suggested_filename}")
                        path = d.path()
                        raw = open(path, "rb").read() if path else b""
                        print("앞부분:", raw[:1500].decode("utf-8", "replace"))
                    except Exception as e:  # noqa: BLE001
                        print(f"[CSV 누름] {str(e)[:200]}")
                    print("\n--- CSV 누를 때 POST ---\n" + "\n".join(log[-4:]))
                    break
        except Exception as e:  # noqa: BLE001
            print(f"[Sheet 실패] {str(e)[:200]}")
        b.close()


if __name__ == "__main__":
    requests_part()
    if "--no-browser" not in sys.argv:
        browser_part()
