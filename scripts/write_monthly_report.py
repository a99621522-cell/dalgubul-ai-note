#!/usr/bin/env python3
"""월보 생성기 — data/stats/monthly/YYYYMM.json → src/content/posts/YYYY-MM-DD-monthly-YYYYMM.md (draft, auto).

집계 파일의 숫자만 옮긴다(만들지 않는다). 값이 없으면 '자료 없음'. 평가·순위·전망 문장은 쓰지 않는다.
표: 이달 숫자 / 산업 그룹별 / 입지 유형별 / 구·군별 / 단지별 / 지원 이력(3년) / 자료 설명. 링크: /stats/YYYY-MM/, /dashboard/, /industry/.
description 은 결론 먼저의 핵심 문장, faq 3개는 본문 숫자만으로 답한다(CLAUDE.md 8항). 발행은 사람이 approve.py 로.

사용: python3 scripts/write_monthly_report.py [--month 202607] [--date 2026-09-25]
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "data" / "stats" / "monthly"
POSTS = ROOT / "src" / "content" / "posts"
GROUPS = ROOT / "config" / "industry_groups.yml"


def n(v, unit: str = "") -> str:
    return "자료 없음" if v is None else f"{v:,}{unit}"


def delta(d) -> str:
    if not d or d.get("diff") is None:
        return "자료 없음"
    s = "+" if d["diff"] > 0 else "−" if d["diff"] < 0 else ""
    pct = "" if d.get("pct") is None else f" ({s}{abs(d['pct'])}%)"
    return f"{s}{abs(d['diff']):,}{pct}"


def label(ym: str) -> str:
    return f"{ym[:4]}년 {int(ym[4:6])}월"


def yml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def main(argv: list[str]) -> int:
    months = sorted(p.stem for p in STATS.glob("??????.json"))
    if not months:
        print("집계 없음: scripts/build_stats.py 먼저")
        return 1
    ym = argv[argv.index("--month") + 1] if "--month" in argv else months[-1]
    today = argv[argv.index("--date") + 1] if "--date" in argv else date.today().isoformat()
    m = json.loads((STATS / f"{ym}.json").read_text(encoding="utf-8"))
    t = m["total"]
    L = label(ym)
    basis = m.get("basis_label", "고용 인원")
    groups = [g["name"] for g in yaml.safe_load(GROUPS.read_text(encoding="utf-8"))["groups"]]
    ind = [(g, m["by_industry"][g]) for g in groups if g in m["by_industry"]]
    extra = [(k, v) for k, v in m["by_industry"].items() if k not in groups]
    pct_cov = round(t["covered"] / t["firms"] * 100) if t["firms"] else 0
    sup = t.get("support_3y") or {}
    prev = months[months.index(ym) - 1] if ym in months and months.index(ym) > 0 else None

    # 표 문자열
    def row(*cells):
        return "| " + " | ".join(str(c) for c in cells) + " |"

    lines = []
    lines.append(f"> 월보 자동 초안({today} 생성). `data/stats/monthly/{ym}.json` 의 값을 그대로 옮겼으며 평가·전망은 없습니다. 발행 전 사람이 확인합니다.")
    lines.append("")
    lines.append("## 이달 숫자")
    lines.append("")
    lines.append(row("항목", "값", "전월 대비", "전년 동월 대비"))
    lines.append(row("---", "---:", "---:", "---:"))
    lines.append(row("기업 수", n(t["firms"], "곳"), delta((t.get("mom") or {}).get("firms")), delta((t.get("yoy") or {}).get("firms"))))
    lines.append(row(f"고용 인원({basis})", n(t["employment"], "명"), delta((t.get("mom") or {}).get("employment")), delta((t.get("yoy") or {}).get("employment"))))
    lines.append(row("집계 대상 기업", f"{n(t['covered'], '곳')} ({pct_cov}%)", "", ""))
    lines.append(row("이달 취득(가입)", n(t.get("nps_gain"), "명"), "", ""))
    lines.append(row("이달 상실", n(t.get("nps_loss"), "명"), "", ""))
    lines.append(row("새로 등록된 기업", n(t.get("new_firms"), "곳"), "", ""))
    lines.append(row("목록에서 빠진 기업", n(t.get("closed_firms"), "곳"), "", ""))
    lines.append("")
    sb = t.get("size_bands") or {}
    lines.append(f"집계 대상 기업의 규모 구간: 1~9명 {n(sb.get('1~9'), '곳')}, 10~49명 {n(sb.get('10~49'), '곳')}, 50~299명 {n(sb.get('50~299'), '곳')}, 300명 이상 {n(sb.get('300+'), '곳')}.")
    lines.append("")
    lines.append("## 산업 그룹별")
    lines.append("")
    lines.append(row("산업 그룹", "기업 수", "고용 인원", "집계 대상", "취득", "상실", "전월 대비(고용)"))
    lines.append(row("---", "---:", "---:", "---:", "---:", "---:", "---:"))
    for g, s in ind + extra:
        lines.append(row(f"[{g}](/industry/)" if g in groups else g, n(s["firms"]), n(s["employment"]), n(s["covered"]), n(s.get("nps_gain")), n(s.get("nps_loss")), delta((s.get("mom") or {}).get("employment"))))
    lines.append(row("전체", n(t["firms"]), n(t["employment"]), n(t["covered"]), n(t.get("nps_gain")), n(t.get("nps_loss")), delta((t.get("mom") or {}).get("employment"))))
    lines.append("")
    lines.append("## 입지 유형별")
    lines.append("")
    lines.append(row("입지 유형", "기업 수", "고용 인원", "집계 대상", "취득", "상실"))
    lines.append(row("---", "---:", "---:", "---:", "---:", "---:"))
    for k, s in m.get("by_site", {}).items():
        lines.append(row(k, n(s["firms"]), n(s["employment"]), n(s["covered"]), n(s.get("nps_gain")), n(s.get("nps_loss"))))
    lines.append("")
    lines.append("## 구·군별")
    lines.append("")
    lines.append(row("구·군", "기업 수", "고용 인원", "집계 대상", "전월 대비(고용)"))
    lines.append(row("---", "---:", "---:", "---:", "---:"))
    for k, s in sorted(m.get("by_district", {}).items(), key=lambda kv: kv[0]):
        if not k or k[0].isdigit():
            continue
        lines.append(row(k, n(s["firms"]), n(s["employment"]), n(s["covered"]), delta((s.get("mom") or {}).get("employment"))))
    lines.append("")
    lines.append("## 산업단지별 (가나다순)")
    lines.append("")
    lines.append(row("단지", "기업 수", "고용 인원", "집계 대상", "전월 대비(고용)"))
    lines.append(row("---", "---:", "---:", "---:", "---:"))
    cx = m.get("by_complex", {})
    for k in sorted(k for k in cx if k not in ("개별입지", "산단 외")) + [k for k in ("개별입지", "산단 외") if k in cx]:
        s = cx[k]
        lines.append(row(k, n(s["firms"]), n(s["employment"]), n(s["covered"]), delta((s.get("mom") or {}).get("employment"))))
    lines.append("")
    tags = m.get("by_tag", {})
    if tags:
        lines.append("## 공개 명단 태그별")
        lines.append("")
        lines.append(row("태그", "기업 수", "고용 인원", "집계 대상"))
        lines.append(row("---", "---:", "---:", "---:"))
        for k, s in tags.items():
            lines.append(row(k, n(s["firms"]), n(s["employment"]), n(s["covered"])))
        lines.append("")
    lines.append("## 지원 이력 (최근 3년, 공개 자료)")
    lines.append("")
    if sup:
        lines.append(f"공개 자료(공공데이터포털 과제·선정 명단)에서 확인된 최근 3년 지원 이력이 있는 기업은 {n(sup.get('firms'), '곳')}, 이력 {n(sup.get('records'), '건')}입니다."
                     + (f" 재원별: " + ", ".join(f"{k} {v:,}건" for k, v in (sup.get("by_layer") or {}).items()) + "." if sup.get("by_layer") else "")
                     + (" 금액은 원문에 있는 이력만 합산하며, 이달 기준 금액이 있는 이력은 " + n(sup.get("amount_known_records"), "건") + "입니다."))
        lines.append("")
        lines.append(row("산업 그룹", "지원 이력 기업", "이력 건수"))
        lines.append(row("---", "---:", "---:"))
        for g, s in ind:
            sp = s.get("support_3y") or {}
            lines.append(row(g, n(sp.get("firms"), "곳"), n(sp.get("records"), "건")))
        lines.append("")
        lines.append("기업별 목록은 [지원받은 기업](/support/) 페이지에 있습니다.")
    else:
        lines.append("지원 이력 집계가 없습니다.")
    lines.append("")
    lines.append("## 자료 설명과 한계")
    lines.append("")
    src = m.get("sources", {})
    fo, nps = src.get("factoryon", {}), src.get("nps") or {}
    lines.append(f"- 기업 목록: 한국산업단지공단 팩토리온 입주업체현황({fo.get('as_of', '?')} 기준) {n(fo.get('companies'), '곳')} 가운데 산단 외 목록(국민연금 사업장·벤처기업명단·첨복단지 입주) {n(m.get('sources_extra', {}).get('outside_companies'), '곳')} 포함.")
    if nps:
        lines.append(f"- 고용 인원: 국민연금 가입 사업장 내역({ym[:4]}-{ym[4:6]}, 공공데이터포털 15083277) {n(nps.get('rows'), '행')} 중 기업 사전과 이름·주소로 맞춘 {n(nps.get('matched'), '곳')}의 가입자수 합계. 법인 3인 이상·개인 10인 이상 사업장만 자료에 있어 집계 대상은 전체 기업의 {pct_cov}%입니다.")
    else:
        lines.append(f"- 고용 인원: {basis}.")
    lines.append(f"- 전월·전년 대비: {'전월 자료(' + label(prev) + ')와 비교' if prev else '이전 달 자료가 없어 이번 호에는 표시하지 않음'}. 자료가 쌓이면 자동으로 채워집니다.")
    lines.append("- 산업 그룹은 표준산업분류(KSIC) 코드·생산품 키워드 규칙(`config/industry_groups.yml`)으로 나눴습니다. 순위·평가가 아닌 사실 집계입니다.")
    lines.append(f"- 전체 표: [{L} 통계표](/stats/{ym[:4]}-{ym[4:6]}/), [현황판](/dashboard/), [산업별 현황](/industry/).")
    body = "\n".join(lines) + "\n"

    top_ind = max(ind, key=lambda kv: kv[1]["employment"] or 0)[0] if ind else ""
    desc = (f"{L} 대구 기업 {t['firms']:,}곳, 고용 인원 {t['employment']:,}명({basis}, 집계 대상 {t['covered']:,}곳). "
            f"전월 대비 고용 {delta((t.get('mom') or {}).get('employment'))}, 이달 취득 {n(t.get('nps_gain'), '명')}·상실 {n(t.get('nps_loss'), '명')}. "
            f"산업 그룹 11개·입지 유형 5·구군 9·단지별 기업 수와 고용, 최근 3년 지원 이력 {n(sup.get('firms'), '곳')}.")
    summary = f"{L} 기준 대구 기업 {t['firms']:,}곳·고용 {t['employment']:,}명. 산업·입지·구군·단지별 표와 지원 이력 요약."
    faq = [
        {"q": f"{L} 대구 기업 수와 고용 인원은?", "a": f"기업 {t['firms']:,}곳, 고용 인원 {t['employment']:,}명({basis}). 고용은 값이 있는 {t['covered']:,}곳({pct_cov}%)만 집계했습니다."},
        {"q": "고용 인원이 가장 많은 산업 그룹은?", "a": (f"{top_ind} {m['by_industry'][top_ind]['employment']:,}명(기업 {m['by_industry'][top_ind]['firms']:,}곳)입니다. 산업 그룹은 KSIC 코드 규칙으로 나눈 사실 집계입니다." if top_ind else "자료 없음")},
        {"q": "고용 인원 숫자의 출처와 한계는?", "a": (f"국민연금 가입 사업장 내역의 가입자수입니다. 법인 3인 이상·개인 10인 이상 사업장만 있어 전체 기업의 {pct_cov}%만 집계됩니다." if nps else f"{basis}입니다.")},
    ]
    fm = {
        "title": f"[월보] {L} 대구 산단·기업 현황",
        "date": today, "category": "economy", "summary": summary, "description": desc,
        "source": "한국산업단지공단 팩토리온 · 국민연금공단 가입 사업장 내역(공공데이터포털)",
        "sourceUrl": "https://www.data.go.kr/data/15083277/fileData.do",
        "tags": ["월보", "통계", L],
        "draft": True, "auto": True, "faq": faq,
        "sources": [
            {"title": "팩토리온 입주업체현황", "url": "https://www.femis.go.kr", "date": fo.get("as_of", "")},
            {"title": "국민연금공단 국민연금 가입 사업장 내역 (공공데이터포털 15083277)", "url": "https://www.data.go.kr/data/15083277/fileData.do", "date": f"{ym[:4]}-{ym[4:6]}"},
        ],
    }
    fm_text = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000)
    out = POSTS / f"{today}-monthly-{ym}.md"
    for old in POSTS.glob(f"*-monthly-{ym}.md"):  # 같은 달 초안은 하나만
        if old != out:
            old.unlink()
    out.write_text(f"---\n{fm_text}---\n\n{body}", encoding="utf-8")
    print(f"월보 초안 → {out.relative_to(ROOT)} (draft, {len(body):,}자). 발행: python3 scripts/approve.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
