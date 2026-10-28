#!/usr/bin/env python3
"""유권해석·판례 원문 받기(운영자 지시 2026-10-28 '니가 받아서 붙여') — data/vat/rules.yml `rulings` 의 항목마다
  law_id: 국가법령정보센터 판례일련번호(DRF lawService target=prec, 게스트 OC=test) → 판시사항·판결요지·참조조문·참조판례·판례내용
  ulex:   U-LEX(2차 게재) 질의회신 쪽 → 답변사항·답변요지·이유(사실관계·질의내용·관련법령)
  tt:     조세심판원 결정문 보기 주소(/mUser/common/xmlViewer.do?dem_no=…) → 사건번호·결정요지·주문·이유 전문
을 받아 data/vat/rulings/<id>.txt(+index.json)로. 원문 글자 그대로, 사람 이름은 원문이 가린 대로(☆☆시·甲 등). 평가 없음.
사용: python3 scripts/fetch_vat_rulings.py [--only id,id] [--curl]
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "data" / "vat" / "rules.yml"
OUT = ROOT / "data" / "vat" / "rulings"
UA = "Mozilla/5.0 daitda-note-bot/1.0 (+https://daitda.co.kr)"
USE_CURL = "--curl" in sys.argv


def get(url: str, post: dict | None = None, tries: int = 4) -> str:
    for i in range(tries):
        try:
            if USE_CURL:
                cmd = ["curl", "-sS", "-m", "60", "-L", "-A", UA]
                if post:
                    cmd += ["-X", "POST"]
                    for k, v in post.items():
                        cmd += ["--data-urlencode", f"{k}={v}"]
                cmd.append(url)
                r = subprocess.run(cmd, capture_output=True, timeout=90)
                if r.returncode == 0 and r.stdout:
                    return r.stdout.decode("utf-8", "ignore")
            else:
                import requests
                r2 = requests.post(url, data=post, headers={"User-Agent": UA}, timeout=60) if post else requests.get(url, headers={"User-Agent": UA}, timeout=60)
                if r2.ok and r2.text:
                    return r2.text
        except Exception as e:  # noqa: BLE001
            print(f"  [{i + 1}] {url[:80]} 실패: {str(e)[:100]}")
        time.sleep(3 + i * 3)
    return ""


def strip(t: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", t, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"[ \t　]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def tag(x: str, t: str) -> str:
    m = re.search(f"<{t}>(.*?)</{t}>", x, re.S)
    return strip(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1))) if m else ""


def from_law(law_id: str) -> tuple[str, dict]:
    x = get(f"https://www.law.go.kr/DRF/lawService.do?OC=test&target=prec&ID={law_id}&type=XML")
    if not x or "<사건번호>" not in x:
        return "", {}
    meta = {k: tag(x, k) for k in ("사건명", "사건번호", "선고일자", "법원명", "판결유형")}
    parts = [f"{meta['법원명']} {meta['선고일자'][:4]}. {int(meta['선고일자'][4:6])}. {int(meta['선고일자'][6:8])}. 선고 {meta['사건번호']} {meta['판결유형']} [{meta['사건명']}]", ""]
    for k in ("판시사항", "판결요지", "참조조문", "참조판례"):
        v = tag(x, k)
        if v:
            parts += [f"【{k}】", v, ""]
    body = tag(x, "판례내용")
    if body:
        parts += ["【판결 이유(원문)】", body]
    parts += ["", f"출처: 국가법령정보센터 판례(DRF lawService target=prec ID={law_id}), https://www.law.go.kr/DRF/lawService.do?OC=test&target=prec&ID={law_id}&type=HTML"]
    return "\n".join(parts), meta


def from_ulex(url: str) -> str:
    x = get(url)
    if not x:
        return ""
    t = strip(x)
    i = t.find("【답변사항】")
    if i < 0:
        i = t.find("【")
    j = t.find("관련 문서", i) if i >= 0 else -1
    body = t[i:] if i >= 0 else t
    body = re.split(r"\n\s*(?:관련문서|관련 문서|함께 본 문서|AI분석 결과)\s*\n", body)[0]
    return body.strip() + f"\n\n출처: U-LEX 법률우주(2차 게재, 국세청 질의회신 원문), {url}"


def from_tt(url: str) -> str:
    """조세심판원: 결정례 검색(searchDemList.do POST taxDivs=doc·txtKeyword=사건번호) → searchEngineDemViewPopup.do(껍데기) → 본문은 /mUser/common/xmlViewer.do?dem_no=…&mode=popup&db=s. 러너·이 세션 모두 열림(2026-10-28)"""
    x = get(url)
    if not x:
        return ""
    t = strip(x).replace("xmlViewer \n", "", 1)
    i = t.find("[사건번호]")
    body = t[i:] if i >= 0 else t
    return body.strip() + f"\n\n출처: 조세심판원 결정례(결정문 보기), {url}"


def main() -> int:
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    cfg = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    idx_p = OUT / "index.json"
    idx = json.loads(idx_p.read_text(encoding="utf-8")) if idx_p.exists() else {}
    for r in cfg.get("rulings", []):
        if only and r["id"] not in only:
            continue
        text, meta = "", {}
        if r.get("law_id"):
            text, meta = from_law(str(r["law_id"]))
        elif r.get("ulex"):
            text = from_ulex(r["ulex"])
        elif r.get("tt"):
            text = from_tt(r["tt"])
        else:
            continue
        if not text or len(text) < 200:
            print(f"[rulings] {r['id']}: 못 받음({len(text)}자)")
            continue
        (OUT / f"{r['id']}.txt").write_text(text, encoding="utf-8")
        idx[r["id"]] = {"no": r["no"], "chars": len(text), "fetched": time.strftime("%Y-%m-%d"), **meta}
        print(f"[rulings] {r['id']}: {len(text):,}자 {meta.get('사건번호', '')}")
        time.sleep(2)
    idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
