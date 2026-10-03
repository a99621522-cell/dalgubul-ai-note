#!/usr/bin/env python3
"""한국관광 데이터랩(datalab.visitkorea.or.kr) 로그인 없이 열리는 화면의 내부 요청(qid) 확인용(한 번 실행, 수집기 아님).
화면을 열고 화면 스크립트 속 qid 이름을 모은 뒤, 같은 화면 안에서 지역 코드만 바꿔(대구) 몇 개를 다시 불러 응답 앞부분을 찍는다.
로그인 화면으로 넘어가는 메뉴(이동통신 방문자수·신용카드 관광지출액)는 다루지 않는다(로그인 뒤 자료 수집 금지).
사용: python3 scripts/datalab_probe.py <화면 주소> [지역코드=27] [최대 qid 수=40]
  최대 qid 수가 0 이면 qid 를 다시 부르지 않고, 화면이 보내는 요청의 지역만 바꿔(대구) 화면이 그린 글자(단위·표)를 찍는다.
"""
import json, re, sys, time
from playwright.sync_api import sync_playwright

UA = "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"


def main():
    url = sys.argv[1]
    sgg = sys.argv[2] if len(sys.argv) > 2 else "27"
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    posts = []

    def on_req(req):
        if "getTempleteData" in req.url and req.post_data:
            posts.append(req.post_data)

    from urllib.parse import quote
    nm = {"27": "대구광역시"}.get(sgg, "")

    def swap(route):   # 화면이 고른 기본 지역을 대구로 바꿔 보낸다(화면이 대구를 그리게)
        d = route.request.post_data or ""
        if cap == 0 and "SGG_CD=" in d:
            d = re.sub(r"SGG_CD=\d+", f"SGG_CD={sgg}", d)
            d = re.sub(r"SGG_NM=[^&]*", "SGG_NM=" + quote(nm), d)
            return route.continue_(post_data=d)
        route.continue_()

    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(user_agent=UA, viewport={"width": 1400, "height": 1000})
        pg.on("request", on_req)
        pg.route("**/visualize/getTempleteData.do", swap)
        pg.goto(url, wait_until="networkidle", timeout=90000); pg.wait_for_timeout(5000)
        print(f"== {pg.title()} | {pg.url}")
        if "Login" in pg.url:
            print("!! 로그인 화면으로 넘어감 — 다루지 않는다"); b.close(); return
        for s in pg.query_selector_all("select")[:10]:
            opts = s.evaluate("e => Array.from(e.options).map(o => o.value + ':' + o.text.trim()).slice(0, 40)")
            print(f"== select {s.get_attribute('id') or s.get_attribute('name')}: {opts}")
        # 화면이 보낸 요청(기본 지역)
        print(f"== 화면이 보낸 getTempleteData {len(posts)}개")
        for d in posts[:30]: print("   " + d[:400])
        if cap == 0:
            pg.wait_for_timeout(8000)
            main = pg.evaluate("""() => { const c = document.querySelector('#contents, .contents, #container, main') || document.body;
                return c.innerText; }""")
            i = main.find("지역별 관광 현황", 200)
            print("== 화면 글자(대구로 바꿔 그린 것) ==\n" + main[max(0, i - 200):][:15000])
            for t in pg.query_selector_all("table")[:20]:
                print("== 표: " + re.sub(r"\s+", " ", t.inner_text())[:800])
            b.close(); return
        # 화면 스크립트 속 qid
        srcs = pg.evaluate("() => Array.from(document.scripts).map(s => s.src).filter(Boolean)")
        text = pg.content()
        for s in srcs:
            if "datalab.visitkorea" in s or s.startswith("/"):
                try: text += pg.evaluate("u => fetch(u).then(r => r.text())", s)
                except Exception: pass
        qids = sorted(set(re.findall(r"""qid['"]?\s*[:=,]\s*['"]([A-Za-z]{2}_[A-Za-z0-9_]+)['"]""", text)) | set(re.findall(r"""['"]((?:LN|MN|MM|SN|AN|RN)_[A-Z0-9_]{4,})['"]""", text)))
        print(f"== 스크립트 속 qid {len(qids)}개: {' '.join(qids)}")
        # 같은 요청을 지역 코드만 대구로 바꿔 다시
        base = {}
        for d in posts:
            for kv in d.split("&"):
                k, _, v = kv.partition("=")
                if k in ("SGG_CD", "SGG_NM", "qid", "BASE_YR", "chartId", "fileWriteYn"): continue
                base.setdefault(k, v)
        tried = 0
        for q in ([re.search(r"qid=([^&]+)", d).group(1) for d in posts if "qid=" in d] + qids):
            if tried >= cap: break
            body = "&".join(f"{k}={v}" for k, v in base.items()) + f"&SGG_CD={sgg}&qid={q}"
            r = pg.evaluate("""b => fetch('/visualize/getTempleteData.do', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8','X-Requested-With':'XMLHttpRequest'}, body:b}).then(r => r.text())""", body)
            tried += 1
            print(f"\n## qid={q} len={len(r)}\n   " + re.sub(r"\s+", " ", r[:900]))
            time.sleep(1)
        b.close()


if __name__ == "__main__":
    main()
