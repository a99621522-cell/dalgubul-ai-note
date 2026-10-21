#!/usr/bin/env python3
"""복지서비스 수집 — 한국사회보장정보원(복지로) 오픈API로 중앙부처 + 대구광역시·구군 복지서비스를 모은다.

/welfare/ (복지서비스 찾기)의 재료. 운영자 지시 2026-10-21 '복지분야 … 일단 해봐'.
  - 중앙부처: B554287/NationalWelfareInformationsV001 (NationalWelfarelistV001 → NationalWelfaredetailedV001)
  - 지자체:   B554287/LocalGovernmentWelfareInformations (LcgvWelfarelist ctpvNm=대구광역시 → LcgvWelfaredetailed)
출력: data/welfare/services.json  (목록 + 상세. 상세는 증분 — 새 항목·수정된 항목만 다시 받는다)

사용:
  python3 scripts/collect_welfare.py --probe          # 목록 1쪽 + 상세 1건씩 원문 XML 을 data/welfare/_probe/ 에 저장·출력(구조 확인)
  python3 scripts/collect_welfare.py                  # 수집 (DATA_GO_KR_KEY 필요, 공공데이터포털에서 두 API 활용신청)
  python3 scripts/collect_welfare.py --max-detail 300 # 1회 상세 호출 상한(API별). 개발계정 일 1,000건 한도라 기본 900

원칙: 공개 API 값 그대로 (요약·평가 없음), 개인정보 없음(담당 부서 전화는 기관 대표 문의처라 싣는다).
이 세션 환경은 data.go.kr 접속이 막혀 GitHub Actions(.github/workflows/welfare.yml)가 돌린다. 실패는 로그만 남긴다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "welfare"
OUT = OUT_DIR / "services.json"
PROBE_DIR = OUT_DIR / "_probe"

BASE = "https://apis.data.go.kr/B554287"
CENTRAL_LIST = f"{BASE}/NationalWelfareInformationsV001/NationalWelfarelistV001"
CENTRAL_DETAIL = f"{BASE}/NationalWelfareInformationsV001/NationalWelfaredetailedV001"
LOCAL_LIST = f"{BASE}/LocalGovernmentWelfareInformations/LcgvWelfarelist"
LOCAL_DETAIL = f"{BASE}/LocalGovernmentWelfareInformations/LcgvWelfaredetailed"

SIDO = "대구광역시"
SGG = ["중구", "동구", "서구", "남구", "북구", "수성구", "달서구", "달성군", "군위군"]
UA = {"User-Agent": "daitda-welfare/1.0 (+https://daitda.co.kr)"}
KST = timezone(timedelta(hours=9))


class LimitHit(Exception):
    """일일 호출 한도·키 오류 — 그 API 의 나머지 호출을 멈춘다."""


def key_param() -> str:
    k = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not k:
        return ""
    # 인코딩 키(%2B 등)는 그대로, 디코딩 키(+ / =)는 URL 인코딩
    return k if "%" in k else urllib.parse.quote(k, safe="")


def get_xml(url: str, params: dict, key: str, tries: int = 3) -> ET.Element:
    q = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in params.items())
    full = f"{url}?serviceKey={key}&{q}"
    last = None
    for t in range(tries):
        try:
            r = requests.get(full, headers=UA, timeout=40)
            body = r.text.strip()
            if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in body or "SERVICE_KEY_IS_NOT_REGISTERED" in body or "SERVICE ACCESS DENIED" in body.upper():
                raise LimitHit(body[:200])
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {body[:200]}")
            root = ET.fromstring(body.encode("utf-8"))
            code = (root.findtext(".//resultCode") or "").strip()
            if code and code not in ("0", "00", "000"):
                msg = (root.findtext(".//resultMessage") or root.findtext(".//resultMsg") or "").strip()
                if code in ("22", "30", "31", "32", "20"):
                    raise LimitHit(f"resultCode={code} {msg}")
                raise RuntimeError(f"resultCode={code} {msg}")
            return root
        except LimitHit:
            raise
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + t * 3)
    raise RuntimeError(str(last))


def text(el: ET.Element | None, tag: str) -> str:
    if el is None:
        return ""
    v = el.findtext(tag)
    return re.sub(r"[ \t]+", " ", v).strip() if v else ""


def split_names(v: str) -> list[str]:
    return [s.strip() for s in re.split(r"[,|]", v or "") if s.strip()]


def list_text(root: ET.Element, list_tag: str) -> list[str]:
    """상세 응답의 반복 목록(문의처·근거법령·신청방법 등) → 항목마다 자식 텍스트를 이어 붙인 한 줄."""
    out = []
    for it in root.iter(list_tag):
        parts = []
        for ch in it:
            v = (ch.text or "").strip()
            if not v or ch.tag.lower().endswith(("cd", "code")) or re.fullmatch(r"https?://\S+", v):
                continue
            if v not in parts:
                parts.append(v)
        line = " ".join(parts).strip()
        if line and line not in out:
            out.append(line)
    return out


def first(root: ET.Element, *tags: str) -> str:
    for t in tags:
        v = root.findtext(f".//{t}")
        if v and v.strip():
            return v.strip()
    return ""


# ---------------- 목록 ----------------
def fetch_list(url: str, base_params: dict, key: str, label: str) -> list[ET.Element]:
    items, page, total = [], 1, None
    while page <= 60:
        root = get_xml(url, {**base_params, "pageNo": page, "numOfRows": 100}, key)
        if total is None:
            try:
                total = int(root.findtext(".//totalCount") or 0)
            except ValueError:
                total = 0
            print(f"[{label}] totalCount={total}")
        got = list(root.iter("servList"))
        if not got:
            break
        items.extend(got)
        if total and len(items) >= total:
            break
        page += 1
        time.sleep(0.3)
    return items


def norm_central(it: ET.Element) -> dict:
    sid = text(it, "servId")
    return {
        "id": sid, "scope": "중앙", "sido": "", "sgg": "",
        "name": text(it, "servNm"),
        "org": text(it, "jurMnofNm"), "dept": text(it, "jurOrgNm"),
        "summary": text(it, "servDgst"),
        "life": split_names(text(it, "lifeArray") or text(it, "lifeNmArray")),
        "target": split_names(text(it, "trgterIndvdlArray") or text(it, "trgterIndvdlNmArray")),
        "theme": split_names(text(it, "intrsThemaArray") or text(it, "intrsThemaNmArray")),
        "cycle": text(it, "sprtCycNm"), "provision": text(it, "srvPvsnNm"),
        "online": text(it, "onapPsbltYn"),
        "contact": text(it, "rprsCtadr"),
        "views": int(text(it, "inqNum") or 0) if text(it, "inqNum").isdigit() else 0,
        "lastMod": text(it, "svcfrstRegTs") or text(it, "lastModYmd"),
        "link": text(it, "servDtlLink") or f"https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId={sid}",
    }


def norm_local(it: ET.Element) -> dict:
    sid = text(it, "servId")
    sgg = text(it, "sggNm")
    return {
        "id": sid, "scope": "구군" if sgg else "대구시", "sido": text(it, "ctpvNm") or SIDO, "sgg": sgg,
        "name": text(it, "servNm"),
        "org": (f"{SIDO} {sgg}" if sgg else SIDO), "dept": text(it, "bizChrDeptNm"),
        "summary": text(it, "servDgst"),
        "life": split_names(text(it, "lifeNmArray") or text(it, "lifeArray")),
        "target": split_names(text(it, "trgterIndvdlNmArray") or text(it, "trgterIndvdlArray")),
        "theme": split_names(text(it, "intrsThemaNmArray") or text(it, "intrsThemaArray")),
        "cycle": text(it, "sprtCycNm"), "provision": text(it, "srvPvsnNm"),
        "apply": text(it, "aplyMtdNm"),
        "views": int(text(it, "inqNum")) if text(it, "inqNum").isdigit() else 0,
        "lastMod": text(it, "lastModYmd"),
        "link": text(it, "servDtlLink") or f"https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId={sid}&wlfareInfoReldBztpCd=02",
    }


# ---------------- 상세 ----------------
def parse_detail(root: ET.Element, scope: str) -> dict:
    d = {
        "target": first(root, "sprtTrgtCn", "tgtrDtlCn"),
        "crit": first(root, "slctCritCn"),
        "benefit": first(root, "alwServCn"),
        "how": first(root, "aplyMtdCn"),
        "since": first(root, "enfcBgngYmd"),
        "until": first(root, "enfcEndYmd"),
        "lastMod": first(root, "lastModYmd", "crtrYr"),
    }
    # 반복 목록: 지자체는 *List 안에 wlfareInfoReldNm/Cn, 중앙은 servSeDetailNm/Link
    d["contacts"] = list_text(root, "inqplCtadrList")
    d["laws"] = list_text(root, "baslawList")
    if not d["how"]:
        d["how"] = "\n".join(list_text(root, "applmetList"))
    forms = list_text(root, "basfrmList")
    if forms:
        d["forms"] = forms
    return {k: v for k, v in d.items() if v}


def fetch_detail(url: str, sid: str, key: str, scope: str) -> dict:
    params = {"servId": sid}
    if scope == "중앙":
        params = {"callTp": "D", "servId": sid}
    root = get_xml(url, params, key)
    return parse_detail(root, scope)


# ---------------- 실행 ----------------
def now_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def probe(key: str) -> None:
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    for label, url, params in [
        ("central_list", CENTRAL_LIST, {"callTp": "L", "srchKeyCode": "003", "pageNo": 1, "numOfRows": 3}),
        ("local_list", LOCAL_LIST, {"ctpvNm": SIDO, "pageNo": 1, "numOfRows": 3}),
    ]:
        try:
            root = get_xml(url, params, key)
            raw = ET.tostring(root, encoding="unicode")
            (PROBE_DIR / f"{label}.xml").write_text(raw, encoding="utf-8")
            print(f"==== {label}\n{raw[:2500]}\n")
            sid = text(next(root.iter("servList"), None), "servId")
            if sid:
                durl = CENTRAL_DETAIL if label.startswith("central") else LOCAL_DETAIL
                dp = {"callTp": "D", "servId": sid} if label.startswith("central") else {"servId": sid}
                droot = get_xml(durl, dp, key)
                draw = ET.tostring(droot, encoding="unicode")
                (PROBE_DIR / f"{label.replace('list', 'detail')}.xml").write_text(draw, encoding="utf-8")
                print(f"==== {label} → detail {sid}\n{draw[:4000]}\n")
                print("parsed:", json.dumps(parse_detail(droot, ""), ensure_ascii=False)[:1500])
        except Exception as e:  # noqa: BLE001
            print(f"[probe] {label} 실패: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--max-detail", type=int, default=900, help="API별 1회 상세 호출 상한")
    a = ap.parse_args()

    key = key_param()
    if not key:
        print("DATA_GO_KR_KEY 없음 — 건너뜀")
        return 0
    if a.probe:
        probe(key)
        return 0

    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    prev_items = {(i["scope"] == "중앙", i["id"]): i for i in prev.get("items", [])}

    lists: dict[str, list[dict]] = {}
    try:
        lists["central"] = [norm_central(x) for x in fetch_list(CENTRAL_LIST, {"callTp": "L", "srchKeyCode": "003"}, key, "중앙부처")]
    except Exception as e:  # noqa: BLE001
        print(f"[중앙부처] 목록 실패: {e}")
    try:
        lists["local"] = [norm_local(x) for x in fetch_list(LOCAL_LIST, {"ctpvNm": SIDO}, key, "대구")]
    except Exception as e:  # noqa: BLE001
        print(f"[대구] 목록 실패: {e}")

    # API 장애로 목록이 크게 줄면 이전 것을 유지
    for kind, is_c in (("central", True), ("local", False)):
        old = [i for i in prev.get("items", []) if (i["scope"] == "중앙") == is_c]
        new = lists.get(kind)
        if not new or (old and len(new) < len(old) * 0.7):
            print(f"[{kind}] 목록 {len(new or [])}건 (이전 {len(old)}건) — 이전 목록 유지")
            lists[kind] = old

    items: list[dict] = []
    seen = set()
    for it in lists["central"] + lists["local"]:
        k = (it["scope"] == "중앙", it["id"])
        if not it.get("id") or k in seen:
            continue
        seen.add(k)
        old = prev_items.get(k)
        if old and old.get("detail") and old.get("lastMod") == it.get("lastMod"):
            it["detail"] = old["detail"]
        items.append(it)

    # 상세: 새 항목 → 수정된 항목 순, 조회수 높은 것부터
    for is_c, url, label in ((True, CENTRAL_DETAIL, "중앙부처"), (False, LOCAL_DETAIL, "대구")):
        queue = [i for i in items if (i["scope"] == "중앙") == is_c and not i.get("detail")]
        queue.sort(key=lambda i: (prev_items.get((is_c, i["id"])) is not None, -i.get("views", 0)))
        done = fail = 0
        print(f"[{label}] 상세 받을 {len(queue)}건 (이번 상한 {a.max_detail})")
        for i in queue:
            if done >= a.max_detail:
                break
            try:
                i["detail"] = fetch_detail(url, i["id"], key, i["scope"])
                done += 1
                time.sleep(0.25)
            except LimitHit as e:
                print(f"[{label}] 한도·키 오류로 중단: {e}")
                break
            except Exception as e:  # noqa: BLE001
                fail += 1
                old = prev_items.get((is_c, i["id"]))
                if old and old.get("detail"):
                    i["detail"] = old["detail"]  # 실패하면 예전 상세라도
                print(f"  상세 실패 {i['id']} {i['name']}: {e}")
                if fail >= 30:
                    print(f"[{label}] 실패 30건 — 중단")
                    break
        print(f"[{label}] 상세 {done}건 받음, 실패 {fail}건")

    def cnt(pred):
        return sum(1 for i in items if pred(i))

    out = {
        "fetchedAt": now_kst(),
        "source": "한국사회보장정보원 복지로 오픈API(중앙부처복지서비스·지자체복지서비스), 공공데이터포털",
        "counts": {
            "central": cnt(lambda i: i["scope"] == "중앙"),
            "city": cnt(lambda i: i["scope"] == "대구시"),
            "gugun": cnt(lambda i: i["scope"] == "구군"),
            "detail": cnt(lambda i: bool(i.get("detail"))),
        },
        "items": sorted(items, key=lambda i: (i["scope"] != "중앙", i["scope"] != "대구시", i["sgg"], i["name"])),
    }
    if not items:
        print("항목 0건 — 저장하지 않음")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    tmp.replace(OUT)
    print(f"[완료] {json.dumps(out['counts'], ensure_ascii=False)} → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
