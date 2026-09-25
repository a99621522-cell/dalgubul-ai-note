#!/usr/bin/env python3
"""그래프 생성 — data/stats/timeseries.json + 최신 월 집계 → src/generated/charts/*.svg (+ 같은 데이터의 표 .json)

빌드 때 Astro 컴포넌트(Chart.astro)가 파일을 읽어 인라인으로 넣는다. 브라우저 JS 없음.
종류는 둘뿐: 선 그래프(월별 추이, 최대 6계열) · 가로 막대(그룹 간 비교).

스타일(브리프): 선 2px, 주색 1개 + 회색, 계열이 여럿일 때만 구분색 최대 6개(색맹 안전). 축 글자 14px 이상.
마지막 값은 선 끝에 숫자로, 범례는 선 끝 라벨로 대체. <title> 과 aria-label. 색은 CSS 변수(--primary, --chart-1~6)를 쓰고 hex 는 대체값.

사용: python3 scripts/render_charts.py            # 전부 다시 생성
출력: src/generated/charts/index.json 에 {종류: {이름: 파일}} 목록. 파일명은 이름의 해시라 Astro 는 index 로 찾는다.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from industry import config as industry_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "data" / "stats"
OUT = ROOT / "src" / "generated" / "charts"

PRIMARY = "#1B4F9B"
INK, MUTED, LINE = "#1a1a1a", "#767676", "#e0e0e0"
PALETTE = ["#1B4F9B", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9"]  # --chart-1~6 (tokens.css 와 같게)
FONT = 14
COMPARE_N = 5   # 산업 비교 기본 조합: 고용 상위 5개 산업

fmt = lambda v: "—" if v is None else f"{v:,}"  # noqa: E731
slug = lambda s: hashlib.md5(s.encode("utf-8")).hexdigest()[:10]  # noqa: E731


def month_label(m: str) -> str:
    y, mm = m.split("-")
    return f"{y}.{int(mm)}"


def nice_ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    if hi <= lo:
        hi = lo + max(1, abs(lo) * 0.1)
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    start = math.floor(lo / step) * step
    ticks = []
    t = start
    while t <= hi + step * 0.001:
        ticks.append(round(t, 6))
        t += step
    return ticks


def svg_wrap(w: int, h: int, title: str, desc: str, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{escape(desc)}" '
            f'style="max-width:{w}px;height:auto;font-size:{FONT}px">\n<title>{escape(title)}</title>\n{body}</svg>\n')


# ---------------------------------------------------------------- 선 그래프
def text_w(t: str) -> int:
    """대략의 글자 폭(px, 14px 기준): 한글 14, 그 외 8."""
    return sum(14 if ord(ch) > 0x2E7F else 8 for ch in t)


def line_chart(title: str, months: list[str], series: list[tuple[str, list]], unit: str = "명", note: str = "", narrow: bool = False) -> tuple[str, dict]:
    """series: [(이름, [값 또는 None …])]. 최대 6계열. 계열 1개면 주색, 여럿이면 구분색.
    narrow: 휴대폰 폭(360px) 판 — 글자 크기는 그대로 두고 x 라벨을 줄이며 끝 라벨은 값·이름 두 줄."""
    series = series[:6]
    multi = len(series) > 1
    two_line = multi and narrow
    W, H = (360, 300) if narrow else (720, 340)
    ml, mt, mb = (60 if narrow else 72), 20 + (FONT + 6 if note else 0), 44
    labels = [(f"{fmt(max(v for v in s if v is not None))}{unit}", name) for name, s in series if any(v is not None for v in s)]
    if two_line:
        mr = 14 + max((max(text_w(a), text_w(b)) for a, b in labels), default=60)
    else:
        mr = 14 + max((text_w(a + (" " + b if multi else "")) for a, b in labels), default=60)
    mr = min(mr, W // 2)
    pw, ph = W - ml - mr, H - mt - mb
    vals = [v for _, s in series for v in s if v is not None]
    if not vals:
        body = f'<text x="{W/2}" y="{H/2}" text-anchor="middle" fill="{MUTED}">자료 없음</text>'
        return svg_wrap(W, H, title, f"{title}: 자료 없음", body), {"title": title, "columns": ["월"], "rows": []}
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.15 or max(1, abs(hi) * 0.05)
    ticks = nice_ticks(max(0, lo - pad), hi + pad)
    y0, y1 = ticks[0], ticks[-1]
    n = len(months)
    x = lambda i: ml + (pw * i / (n - 1) if n > 1 else pw / 2)  # noqa: E731
    y = lambda v: mt + ph - (v - y0) / (y1 - y0) * ph  # noqa: E731

    parts = []
    for t in ticks:  # 눈금선 + y 라벨
        parts.append(f'<line x1="{ml}" x2="{ml + pw}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="{LINE}" stroke-width="1"/>')
        parts.append(f'<text x="{ml - 8}" y="{y(t) + 5:.1f}" text-anchor="end" fill="{MUTED}">{fmt(int(t)) if float(t).is_integer() else t}</text>')
    step = (1 if n <= 4 else (3 if n <= 12 else 6)) if narrow else (1 if n <= 8 else (2 if n <= 16 else 6))
    shown = set(range(n - 1, -1, -step))
    for i, m in enumerate(months):  # x 라벨
        if i in shown:
            parts.append(f'<text x="{x(i):.1f}" y="{H - mb + 24}" text-anchor="middle" fill="{MUTED}">{month_label(m)}</text>')
    parts.append(f'<line x1="{ml}" x2="{ml + pw}" y1="{mt + ph}" y2="{mt + ph}" stroke="{MUTED}" stroke-width="1"/>')

    gap = (FONT * 2 + 6) if two_line else (FONT + 2)
    # 끝 라벨 위치: 원하는 y 를 모아 겹치지 않게 벌리되 그래프 위·아래 한계 안에 둔다
    wanted = []
    for k, (name, s) in enumerate(series):
        li = max((i for i, v in enumerate(s) if v is not None), default=None)
        wanted.append((y(s[li]) if li is not None else None, k))
    order = sorted((w for w in wanted if w[0] is not None), key=lambda w: w[0])
    top, bottom = mt + (gap / 2 if two_line else FONT / 2), mt + ph - (gap / 2 if two_line else FONT / 2)
    placed: list[float] = []
    for wy, _ in order:
        placed.append(max(wy, (placed[-1] + gap) if placed else top))
    if placed and placed[-1] > bottom:  # 아래를 넘치면 전체를 위로 밀고, 다시 겹치는 것만 정리
        shift = placed[-1] - bottom
        placed = [max(top, v - shift) for v in placed]
        for i in range(1, len(placed)):
            placed[i] = max(placed[i], placed[i - 1] + gap)
    label_y = {k: ly for (_, k), ly in zip(order, placed)}
    for k, (name, s) in enumerate(series):
        color = PALETTE[k] if multi else PRIMARY
        var = f"var(--chart-{k + 1},{color})" if multi else f"var(--primary,{color})"
        segs, cur = [], []
        for i, v in enumerate(s):
            if v is None:
                if cur:
                    segs.append(cur)
                cur = []
            else:
                cur.append((x(i), y(v)))
        if cur:
            segs.append(cur)
        for seg in segs:
            if len(seg) == 1:
                parts.append(f'<circle cx="{seg[0][0]:.1f}" cy="{seg[0][1]:.1f}" r="4" style="fill:{var}"/>')
            else:
                d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in seg)
                parts.append(f'<path d="{d}" fill="none" stroke="{color}" style="stroke:{var}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        last_i = max((i for i, v in enumerate(s) if v is not None), default=None)
        if last_i is not None:
            ly = label_y[k]
            parts.append(f'<circle cx="{x(last_i):.1f}" cy="{y(s[last_i]):.1f}" r="3.5" style="fill:{var}"/>')
            if two_line:
                parts.append(f'<text x="{x(last_i) + 8:.1f}" y="{ly - 2:.1f}" fill="{INK}" font-weight="600">{fmt(s[last_i])}{unit}</text>')
                parts.append(f'<text x="{x(last_i) + 8:.1f}" y="{ly + FONT + 1:.1f}" fill="{INK}">{escape(name)}</text>')
            else:
                text = f"{fmt(s[last_i])}{unit}" + (f" {name}" if multi else "")
                parts.append(f'<text x="{x(last_i) + 8:.1f}" y="{ly + 5:.1f}" fill="{INK}" font-weight="600">{escape(text)}</text>')
    if note:
        parts.append(f'<text x="{ml if not narrow else 8}" y="{FONT + 2}" fill="{MUTED}">{escape(note)}</text>')
    desc = f"{title}. {months[0]}부터 {months[-1]}까지 {n}개월. " + "; ".join(
        f"{name} 최근 {fmt(next((v for v in reversed(s) if v is not None), None))}{unit}" for name, s in series)
    table = {"title": title, "columns": ["월"] + [name for name, _ in series], "unit": unit,
             "rows": [[m] + [s[i] for _, s in series] for i, m in enumerate(months)], "note": note}
    return svg_wrap(W, H, title, desc, "\n".join(parts)), table


# ---------------------------------------------------------------- 가로 막대
def bar_chart(title: str, items: list[tuple[str, int | None]], unit: str = "명", note: str = "", muted_last: bool = False, narrow: bool = False) -> tuple[str, dict]:
    """items: [(라벨, 값)] 주어진 순서대로(호출자가 정렬). muted_last 면 마지막 항목('기타' 등)을 회색으로.
    narrow: 휴대폰 폭(360px) 판 — 라벨을 막대 위 줄에 둔다."""
    W = 360 if narrow else 720
    ml = 8 if narrow else 8 + max((text_w(l) for l, _ in items), default=100)
    mr = 8 + max((text_w(f"{fmt(v)}{unit}") for _, v in items), default=60)
    mt = 12 + (FONT + 8 if note else 0)
    row = (FONT + 30) if narrow else 34
    H = mt + row * len(items) + 12
    pw = W - ml - mr
    vmax = max((v for _, v in items if v is not None), default=0) or 1
    parts = []
    if note:
        parts.append(f'<text x="8" y="{FONT + 2}" fill="{MUTED}">{escape(note)}</text>')
    for i, (label, v) in enumerate(items):
        yy = mt + row * i
        bw = 0 if v is None else pw * v / vmax
        color = MUTED if (muted_last and i == len(items) - 1) else PRIMARY
        var = "var(--muted," + MUTED + ")" if color == MUTED else f"var(--primary,{PRIMARY})"
        if narrow:
            parts.append(f'<text x="{ml}" y="{yy + FONT:.1f}" fill="{INK}">{escape(label)}</text>')
            by = yy + FONT + 6
            parts.append(f'<rect x="{ml}" y="{by}" width="{bw:.1f}" height="18" fill="{color}" style="fill:{var}"/>')
            parts.append(f'<text x="{ml + bw + 6:.1f}" y="{by + 14:.1f}" fill="{INK}">{fmt(v)}{unit if v is not None else ""}</text>')
        else:
            parts.append(f'<text x="{ml - 10}" y="{yy + row / 2 + 5:.1f}" text-anchor="end" fill="{INK}">{escape(label)}</text>')
            parts.append(f'<rect x="{ml}" y="{yy + 6}" width="{bw:.1f}" height="{row - 12}" fill="{color}" style="fill:{var}"/>')
            parts.append(f'<text x="{ml + bw + 8:.1f}" y="{yy + row / 2 + 5:.1f}" fill="{INK}">{fmt(v)}{unit if v is not None else ""}</text>')
    desc = f"{title}. " + ", ".join(f"{l} {fmt(v)}{unit}" for l, v in items)
    table = {"title": title, "columns": ["구분", title], "unit": unit, "rows": [[l, v] for l, v in items], "note": note}
    return svg_wrap(W, H, title, desc, "\n".join(parts)), table


# ---------------------------------------------------------------- 생성
def write(kind: str, name: str, fn_chart, *args, index: dict, **kw) -> None:
    """넓은 판(.svg)과 좁은 판(.m.svg), 표(.json) 저장. Chart.astro 가 화면 폭에 따라 하나를 보인다."""
    fn = f"{kind}-{slug(name)}"
    svg, table = fn_chart(*args, **kw)
    svg_m, _ = fn_chart(*args, narrow=True, **kw)
    (OUT / f"{fn}.svg").write_text(svg, encoding="utf-8")
    (OUT / f"{fn}.m.svg").write_text(svg_m, encoding="utf-8")
    (OUT / f"{fn}.json").write_text(json.dumps(table, ensure_ascii=False), encoding="utf-8")
    index.setdefault(kind, {})[name] = fn


def main() -> int:
    ts = json.loads((STATS / "timeseries.json").read_text(encoding="utf-8"))
    months = ts["months"]
    if not months:
        print("timeseries.json 에 달이 없음. build_stats.py 먼저", file=sys.stderr)
        return 1
    latest = json.loads((STATS / "monthly" / f"{months[-1].replace('-', '')}.json").read_text(encoding="utf-8"))
    basis_note = ("고용 인원 = " + latest["basis_label"]) + (f", 자료 {len(months)}개월" if len(months) < 24 else "")
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()
    index: dict = {"months": months, "latest": months[-1], "basis": latest["basis_label"]}
    groups = [g["name"] for g in industry_config()["groups"]]
    key_of = {g["name"]: g["key"] for g in industry_config()["groups"]}

    # 전체
    write("total", "employment", line_chart, "대구 고용 인원 추이", months, [("전체", ts["total"]["employment"])], "명", basis_note, index=index)
    write("total", "firms", line_chart, "대구 등록 기업 수 추이", months, [("전체", ts["total"]["firms"])], "곳", f"자료 {len(months)}개월" if len(months) < 24 else "", index=index)

    # 산업별 추이 + 산단 분포
    ind = ts["by_industry"]
    for g in groups:
        if g not in ind:
            continue
        k = key_of[g]
        write("industry-employment", k, line_chart, f"{g} 고용 인원 추이", months, [(g, ind[g]["employment"])], "명", basis_note, index=index)
        write("industry-firms", k, line_chart, f"{g} 기업 수 추이", months, [(g, ind[g]["firms"])], "곳", index=index)
        cross = latest["cross"].get(g, {})
        top = list(cross.items())[:10]
        rest = sum(v["employment"] for _, v in list(cross.items())[10:])
        items = [(shorten(cx), v["employment"]) for cx, v in top] + ([("그 밖의 단지", rest)] if rest else [])
        write("industry-complex", k, bar_chart, f"{g} 산단별 고용 인원", items, "명", basis_note, index=index, muted_last=bool(rest))
        items_f = [(shorten(cx), v["firms"]) for cx, v in sorted(cross.items(), key=lambda kv: -kv[1]["firms"])[:10]]
        write("industry-complex-firms", k, bar_chart, f"{g} 산단별 기업 수", items_f, "곳", index=index)

    # 산업 간 비교 막대(최신 달) + 주력 산업 비교 선
    order = sorted((g for g in groups if g in latest["by_industry"]), key=lambda g: -latest["by_industry"][g]["employment"])
    write("industry-bar", "employment", bar_chart, "산업별 고용 인원", [(g, latest["by_industry"][g]["employment"]) for g in order], "명", basis_note, index=index)
    write("industry-bar", "firms", bar_chart, "산업별 기업 수", [(g, latest["by_industry"][g]["firms"]) for g in sorted(order, key=lambda g: -latest['by_industry'][g]['firms'])], "곳", index=index)
    main5 = [g for g in order if not g.startswith("기타")][:COMPARE_N]
    write("industry-compare", "employment", line_chart, "주력 산업 고용 인원 추이", months, [(g, ind[g]["employment"]) for g in main5], "명", basis_note, index=index)
    write("industry-compare", "firms", line_chart, "주력 산업 기업 수 추이", months, [(g, ind[g]["firms"]) for g in main5], "곳", index=index)
    index["compare_default"] = main5

    # 산단·구군: 고용 추이 + 산업 구성
    for axis, kind in (("by_complex", "complex"), ("by_district", "district")):
        for name, s in ts[axis].items():
            write(f"{kind}-employment", name, line_chart, f"{shorten(name)} 고용 인원 추이", months, [(shorten(name), s["employment"])], "명", basis_note, index=index)
            comp = []
            for g in groups:
                cell = latest["cross"].get(g, {}).get(name) if kind == "complex" else None
                if kind == "district":
                    continue
                if cell:
                    comp.append((g, cell["employment"]))
            if kind == "district":
                comp = district_composition(latest, name)
            comp.sort(key=lambda kv: -kv[1])
            write(f"{kind}-industry", name, bar_chart, f"{shorten(name)} 산업별 고용 인원", comp, "명", basis_note, index=index)

    # 입지 유형(산단 안팎): 고용 막대 + 유형별 추이 + 유형별 산업 구성
    sites = latest.get("by_site", {})
    if sites:
        write("site-bar", "employment", bar_chart, "입지 유형별 고용 인원", [(k, v["employment"]) for k, v in sorted(sites.items(), key=lambda kv: -kv[1]["employment"])], "명", basis_note, index=index)
        write("site-bar", "firms", bar_chart, "입지 유형별 기업 수", [(k, v["firms"]) for k, v in sorted(sites.items(), key=lambda kv: -kv[1]["firms"])], "곳", index=index)
        for name, s in ts.get("by_site", {}).items():
            write("site-employment", name, line_chart, f"{name} 고용 인원 추이", months, [(name, s["employment"])], "명", basis_note, index=index)
            comp = sorted(((g, latest["cross_site"].get(g, {}).get(name, {}).get("employment", 0)) for g in groups if latest["cross_site"].get(g, {}).get(name)), key=lambda kv: -kv[1])
            if comp:
                write("site-industry", name, bar_chart, f"{name} 산업별 고용 인원", comp, "명", basis_note, index=index)
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(list(OUT.glob("*.svg")))
    print(f"그래프 {n}개 → {OUT.relative_to(ROOT)} (최신 {months[-1]}, {basis_note})")
    return 0


def district_composition(latest: dict, district: str) -> list[tuple[str, int]]:
    """구·군 × 산업은 교차표에 없어 기업 파일에서 다시 센다 (companies.json 의 그룹 + 고용)."""
    import csv
    comp_json = json.loads((STATS / "companies.json").read_text(encoding="utf-8"))["companies"]
    out: dict[str, int] = {}
    for r in csv.DictReader(open(ROOT / "scripts" / "data" / "dalseong_companies.csv", encoding="utf-8")):
        if (r["district"] or "기타") != district or r["id"] not in comp_json:
            continue
        c = comp_json[r["id"]]
        if c.get("e") is not None:
            out[c["g"]] = out.get(c["g"], 0) + c["e"]
    return list(out.items())


def shorten(s: str) -> str:
    return re.sub(r"일반산업단지|첨단산업단지|지방산업단지|산업단지", "산단", s).replace("대구경북경제자유구역", "경자구역 ").replace("도시첨단산단", "")


if __name__ == "__main__":
    sys.exit(main())
