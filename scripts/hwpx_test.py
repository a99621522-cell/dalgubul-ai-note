#!/usr/bin/env python3
"""한글(HWPX) 시험 파일 매트릭스 → public/hwpx/test/ (docs/prompts/site_hwpx_skill.md 4절, 2026-10-06).

표 4종(단순·머리 두 줄·병합·긴 표) × 생성 경로 2개(py = scripts/hwpx_blocks.py 양식 복제 / js = src/scripts/hwpx.ts 를 실제 크로미움에서 돌린 것)
+ 줄 배치(lineseg) 실험 변형 + 그림 + 기업 카드 + 검토 의견서. 값은 사이트의 실제 집계(data/stats/monthly 최신, 기업 사전 CSV)에서 가져오고
개인정보 열은 없다(상호에 법인 표기가 있는 기업만, 대표자·연락처 열 없음). 평가·순위 문장 없음.
운영자가 국내 PC 의 한글에서 열어 docs/design/hwpx-compat.md 표를 채우고 data/hwpx/compat.json 에 결과를 적는다.
사용: python3 scripts/hwpx_test.py [--no-browser]   # 결과 목록은 public/hwpx/test/index.json
"""
import csv, json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hwpx_blocks as B  # noqa: E402
import hwpx_check as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "hwpx" / "test"
STATS = ROOT / "data" / "stats" / "monthly"
COMPANIES = ROOT / "scripts" / "data" / "dalseong_companies.csv"
SRC = "자료: 다잇다(daitda.co.kr) 시험 파일 — 공개 자료를 같은 형식으로 옮긴 것이며 평가·순위·추천이 아닙니다"
LEGAL = re.compile(r"\(주\)|\(유\)|주식회사|유한회사|\(사\)|\(재\)")
fmt = lambda v: "—" if v is None else (f"{v:,}" if isinstance(v, int) else (f"{v:,.1f}" if isinstance(v, float) else str(v)))


def latest_stats() -> dict:
    files = sorted(STATS.glob("*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else {}


def head(title: str, kicker: str) -> list[dict]:
    return [{"p": "kicker", "segs": [[kicker, "kicker"]]}, {"p": "title", "segs": [[title, "title"]]}, {"p": "rule", "segs": [["", "caption"]]}]


def tail(note: str = "") -> list[dict]:
    out = [{"p": "spacer", "segs": [["", "caption"]]}]
    if note: out.append({"p": "note", "segs": [[note, "note"]]})
    out.append({"p": "src", "segs": [[SRC, "src"]]})
    return out


def cases() -> list[dict]:
    st = latest_stats(); month = st.get("month", "")
    ind = st.get("by_industry", {}); dist = st.get("by_district", {}); cross = st.get("cross", {})
    kick = f"시험 · 기준월 {month}" if month else "시험"
    out = []
    # t01 단순 표
    rows = [["산업 그룹", "기업 수(곳)", "고용(명)", "국민연금 가입 확인(곳)"]] + [[k, fmt(v.get("firms")), fmt(v.get("employment")), fmt(v.get("covered"))] for k, v in list(ind.items())[:8]]
    out.append({"id": "t01-simple", "desc": "단순 표 9×4(머리 한 줄, 숫자 오른쪽)", "items": ["열림", "테두리", "글꼴", "숫자 정렬"],
                "blocks": head("산업 그룹별 기업 수·고용", kick) + [{"p": "body", "segs": [["표 1. 산업 그룹별 기업 수와 고용(국민연금 가입자 기준). ", "body"], ["숫자는 집계 값 그대로.", "lead"]]}, {"table": rows, "head": True}] + tail()})
    # t02 머리 두 줄(colspan·rowspan)
    bands = ["1~9", "10~49", "50~299", "300+"]
    rows2 = [[{"t": "산업 그룹", "rs": 2}, {"t": "규모별 기업 수(곳)", "cs": 4}, {"t": "고용(명)", "rs": 2}], [{"t": b + "명"} for b in bands]]
    rows2 += [[k] + [fmt(v.get("size_bands", {}).get(b)) for b in bands] + [fmt(v.get("employment"))] for k, v in list(ind.items())[:6]]
    out.append({"id": "t02-twohead", "desc": "머리 두 줄(colspan 4·rowspan 2) 8×6", "items": ["병합 셀", "머리 행 반복", "열 폭"],
                "blocks": head("산업 그룹 × 규모별 기업 수", kick) + [{"table": rows2, "head": True, "headRows": 2}] + tail("규모는 국민연금 가입자 수 구간.")})
    # t03 본문 병합(rowspan)
    rows3 = [["산업 그룹", "단지", "기업 수(곳)", "고용(명)"]]
    for k, cx in list(cross.items())[:3]:
        top = sorted(cx.items(), key=lambda x: -(x[1].get("firms") or 0))[:3]
        for i, (cname, v) in enumerate(top):
            cell0 = [{"t": k, "rs": len(top)}] if i == 0 else []
            rows3.append(cell0 + [cname, fmt(v.get("firms")), fmt(v.get("employment"))])
    out.append({"id": "t03-merged", "desc": "본문 병합(rowspan 3) 10×4", "items": ["병합 셀", "세로 가운데"],
                "blocks": head("산업 그룹 × 단지(기업 수 많은 단지 3곳)", kick) + [{"table": rows3, "head": True}] + tail("단지 순서는 기업 수가 많은 순으로 고른 예시이며 순위·평가가 아님.")})
    # t04 긴 표 60행(기업 사전, 법인 표기 있는 상호만)
    rows4 = [["기업", "구·군", "단지", "산업 그룹", "규모"]]
    if COMPANIES.exists():
        with COMPANIES.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if LEGAL.search(r.get("name", "")) and r.get("district"):
                    rows4.append([r["name"], r["district"], r.get("complex", ""), r.get("sector_group", ""), r.get("workers_band", "") or "—"])
                if len(rows4) > 60: break
    out.append({"id": "t04-long", "desc": "긴 표 60행(쪽 넘김·머리 행 반복)", "items": ["쪽 넘김", "머리 행 반복", "줄바꿈"],
                "blocks": head("기업 사전 발췌 60곳", kick) + [{"table": rows4, "head": True, "widths": [16000, 6000, 10000, 9000, 7188]}] + tail("팩토리온 입주업체현황의 상호·소재지·업종을 그대로 옮김(대표자 등 개인정보 없음).")})
    # t05 그림
    hero = next(iter(sorted((ROOT / "public" / "figures").glob("*/hero.png"))), None)
    if hero:
        out.append({"id": "t05-figure", "desc": "그림 1장(PNG BinData) + 캡션", "items": ["그림 삽입", "캡션"],
                    "blocks": head("그림 삽입 시험", kick) + [{"p": "body", "segs": [["아래 그림은 리포트 대표 그림(AI 생성 이미지)입니다.", "body"]]},
                                                           {"pic": "/" + str(hero.relative_to(ROOT / "public")), "caption": "그림 1. 대표 그림"}, {"p": "caption", "segs": [["그림 1. 대표 그림(AI 생성 이미지)", "caption"]]}] + tail()})
    # t06 기업 카드(공개 항목만)
    comp = next((r for r in rows4[1:]), None)
    if comp:
        name, district, complex_, grp, band = comp
        card = head(name, f"기업 카드  ·  {district}") + [{"p": "body", "segs": [[f"{name} — {district} {complex_}, 산업 그룹 {grp}, 규모 {band}. 팩토리온 입주업체현황 기준.", "body"]]},
                                                     {"p": "h3", "segs": [["개요", "h3"]]},
                                                     {"table": [["소재", f"{district} · {complex_}"], ["산업 그룹", grp], ["규모(종사자 구간)", band], ["출처", "팩토리온 입주업체현황"]], "head": False, "widths": [11000, 37188]},
                                                     {"p": "h3", "segs": [["지원사업 이력(최근 3년)", "h3"]]}, {"p": "note", "segs": [["공개 자료(NTIS 과제·대구시 보조금 공개·기관 선정 공고)에서 확인된 이력만 싣는다. 비공개 자료는 싣지 않는다.", "note"]]}] + tail()
        out.append({"id": "t06-company-card", "desc": "기업 카드 한 장(개요 표 head 없음·소제목·주석)", "items": ["표 head 없음", "소제목", "주석"], "blocks": card})
    # t07 검토 의견서(가로형 5열)
    rows7 = [["판정", "검토 항목", "문서에서 찾은 것", "고칠 방법", "근거"],
             ["보완 필요", "예산 산출근거", "항목별 단가·수량 없음", "단가 × 수량 × 횟수 표로 보완", "보조금 관리에 관한 법률 시행령 제○조"],
             ["계획에 있음", "성과지표", "지표 2개와 목표값", "—", "국가연구개발혁신법 시행령 제○조"],
             ["집행 때 확인", "정산 계획", "정산 보고 시점 명시", "집행 뒤 증빙 대조", "지방보조금 관리 지침"]]
    out.append({"id": "t07-review", "desc": "지침 검토 의견서(5열, 긴 글 칸 줄바꿈)", "items": ["칸 안 줄바꿈", "열 폭"],
                "blocks": head("「시험 지침」 대조 결과", "지침 검토 의견서  ·  시험") + [{"p": "body", "segs": [["브라우저 규칙 검토 결과이며 최종 판단은 담당자가 한다. 조문 번호는 시험용 자리표시.", "body"]]},
                                                                            {"table": rows7, "head": True, "widths": [5000, 12000, 10000, 13188, 8000]}] + tail()})
    return out


def main() -> int:
    no_browser = "--no-browser" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.hwpx"): f.unlink()
    index = []
    for c in cases():
        bj = OUT / f"{c['id']}.blocks.json"; bj.write_text(json.dumps(c["blocks"], ensure_ascii=False), encoding="utf-8")
        files = []
        py = OUT / f"{c['id']}-py.hwpx"; B.build_hwpx(c["blocks"], py, preview=c["desc"]); files.append(("py", py.name))
        if c["id"] == "t01-simple":
            ls = OUT / f"{c['id']}-py-lineseg.hwpx"; B.build_hwpx(c["blocks"], ls, preview=c["desc"], lineseg=True); files.append(("py-lineseg", ls.name))
        if not no_browser:
            js = OUT / f"{c['id']}-js.hwpx"
            try:
                subprocess.run(["node", str(ROOT / "scripts" / "hwpx_browser.mjs"), str(bj), str(js), c["desc"]], check=True, capture_output=True, text=True, timeout=300)
                files.append(("js", js.name))
            except Exception as e:  # noqa: BLE001
                print(f"브라우저 경로 실패 {c['id']}: {getattr(e, 'stderr', e)}"[:800])
        bj.unlink()
        index.append({"id": c["id"], "desc": c["desc"], "items": c["items"], "files": [{"path": p, "file": n} for p, n in files]})
    (OUT / "index.json").write_text(json.dumps({"generated": __import__("datetime").date.today().isoformat(), "cases": index}, ensure_ascii=False, indent=1), encoding="utf-8")
    reports = [C.check_file(f) for f in sorted(OUT.glob("*.hwpx"))]
    for r in reports:
        print(f"{'FAIL' if r.failed else 'PASS'}  {Path(r.path).name}  " + "; ".join(f"{i['rule']}:{i['msg']}" for i in r.items if i["level"] == "FAIL"))
    print(f"→ {OUT.relative_to(ROOT)}: 파일 {len(reports)}개, PASS {sum(not r.failed for r in reports)}")
    return 1 if any(r.failed for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
