#!/usr/bin/env python3
"""리포트 그림 생성기 — 표준 라이브러리만. spec(JSON) → SVG.
  python3 scripts/figure.py spec.json -o public/figures/<post-id>/fig1.svg
  python3 scripts/figure.py --demo            # 형식 예시 출력
spec 형식 (type 마다):
  {"type": "bar",   "title": "…", "unit": "곳", "categories": ["1~9인","10~49인"], "series": [{"name": "의료기기", "values": [50, 42]}], "source": "기업 사전 2026-08"}
  {"type": "hbar",  ... 같음(가로 막대: 이름이 길 때)}
  {"type": "line",  "title": "…", "unit": "명", "x": ["2025-01", ...], "series": [{"name": "…", "values": [...]}]}
  {"type": "steps", "title": "로드맵", "steps": [{"label": "1단계", "head": "접수 1회", "items": ["…", "…"]}, ...], "current": 2}
  {"type": "compare", "title": "…", "columns": ["구분", "기존", "제안"], "rows": [["창구", "3개", "1개"], ...]}
  {"type": "scatter", "title": "…", "xlabel": "…", "ylabel": "…", "points": [{"label": "대구", "x": 1.2, "y": 0.9, "highlight": true}], "xmean": 2.5, "ymean": 0.1, "xmean_label": "전국", "ymean_label": "전국"}
  {"type": "heatmap", "title": "…", "rows": ["서울", …], "cols": ["농림어업", …], "values": [[1.2, …], …], "vmax": 3, "highlight_row": "대구"}
규칙(dataviz): 막대 ≤ 24px·끝 4px 둥글게, 선 2px, 격자 hairline, 값 라벨은 항목 12개 이하일 때만, 시리즈 2개 이상이면 범례, 색은 사이트 팔레트 고정 순서.
글자는 SVG 안에서 Pretendard/맑은 고딕/시스템 sans-serif. 원본 수치는 그대로(환산 없음)."""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
from xml.sax.saxutils import escape as esc

COLORS = ["#1B4F9B", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9"]
INK, MUTED, LINE, SURFACE, BG = "#1a1a1a", "#595959", "#e0e0e0", "#f5f6f8", "#ffffff"
FONT = "font-family=\"'Pretendard Variable',Pretendard,'Malgun Gothic','Apple SD Gothic Neo',sans-serif\""
W = 800


def fmt(v: float | int | None) -> str:
    if v is None:
        return ""
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"


def fmt_tick(v: float, step: float) -> str:
    """눈금 값: 눈금 간격이 1 보다 작으면 간격에 맞는 소수 자리로(0.0294 같은 값이 전부 0.0 으로 찍히지 않게)."""
    if step >= 1:
        return fmt(v)
    dec = 1
    while dec < 5 and abs(round(step, dec) - step) > step * 0.01:   # 간격(예 0.0125)이 그대로 보이는 자리까지
        dec += 1
    return f"{v:,.{dec}f}"


def nice_max(v: float) -> float:
    if v <= 0:
        return 1
    p = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * p:
            return m * p
    return 10 * p


def text(x, y, s, size=14, fill=INK, anchor="start", weight=400, extra=""):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" {FONT} {extra}>{esc(str(s))}</text>'


def header(spec, h):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{esc(spec.get("title", ""))}">',
           f'<rect width="{W}" height="{h}" fill="{BG}"/>']
    if spec.get("title"):
        out.append(text(24, 32, spec["title"], 17, INK, weight=700))
    return out


def footer(spec, h):
    s = spec.get("source")
    return [text(24, h - 14, f"출처: {s}" if s else "", 12, MUTED), "</svg>"]


def legend(series, x, y):
    out, cx = [], x
    for i, s in enumerate(series):
        out.append(f'<rect x="{cx}" y="{y - 10}" width="14" height="10" rx="2" fill="{COLORS[i % 6]}"/>')
        out.append(text(cx + 20, y, s["name"], 13, MUTED))
        cx += 20 + 8 * len(str(s["name"])) * 1.6 + 24
    return out


def bar(spec):
    cats, series = spec["categories"], spec["series"]
    n, k = len(cats), len(series)
    h = 420
    top, left, right, bottom = 60 + (22 if k > 1 else 0), 70, 24, 70
    pw, ph = W - left - right, h - top - bottom
    vals = [v for s in series for v in s["values"] if v is not None]
    if min(vals) < 0:   # 음수(증가율 등)는 0 기준선 아래로 그린다. 눈금은 0 을 지나도록 한 칸 크기로 위아래를 채운다
        stepv = nice_max(max(max(vals), -min(vals))) / 4
        vmax = math.ceil(max(max(vals), 0) / stepv) * stepv
        vmin = -math.ceil(-min(vals) / stepv + 0.35) * stepv   # 가장 낮은 막대 아래에 값 표시 자리(눈금 1/3 이상)를 남긴다
        ticks = [vmin + stepv * t for t in range(int(round((vmax - vmin) / stepv)) + 1)]
    else:
        vmax = nice_max(max(vals)); vmin = 0
        ticks = [vmax * t / 4 for t in range(5)]
    span = vmax - vmin or 1
    y0 = top + ph - ph * (0 - vmin) / span          # 0 기준선
    out = header(spec, h)
    if k > 1:
        out += legend(series, left, 54)
    tstep = (ticks[1] - ticks[0]) if len(ticks) > 1 else 1
    for val in ticks:
        y = top + ph - ph * (val - vmin) / span
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + pw}" y2="{y:.1f}" stroke="{LINE}" stroke-width="1"/>')
        out.append(text(left - 8, y + 4, fmt_tick(val, tstep), 12, MUTED, "end"))
    if vmin < 0:
        out.append(f'<line x1="{left}" y1="{y0:.1f}" x2="{left + pw}" y2="{y0:.1f}" stroke="{MUTED}" stroke-width="1"/>')
    group = pw / n
    bw = min(24, (group * 0.7) / k)
    for i, c in enumerate(cats):
        gx = left + group * i + group / 2 - (bw * k + 4 * (k - 1)) / 2
        for j, s in enumerate(series):
            v = s["values"][i]
            if v is None:
                continue
            bh = ph * abs(v) / span
            x = gx + j * (bw + 4)
            if v >= 0:
                y = y0 - bh
                out.append(f'<path d="M{x:.1f},{y0:.1f} v{-max(bh - 4, 0):.1f} q0,-4 4,-4 h{bw - 8:.1f} q4,0 4,4 v{max(bh - 4, 0):.1f} z" fill="{COLORS[j % 6]}"/>')
                ly = y - 6
            else:
                out.append(f'<path d="M{x:.1f},{y0:.1f} v{max(bh - 4, 0):.1f} q0,4 4,4 h{bw - 8:.1f} q4,0 4,-4 v{-max(bh - 4, 0):.1f} z" fill="{COLORS[j % 6]}"/>')
                ly = y0 + bh + 14
            if n * k <= 12:
                out.append(text(x + bw / 2, ly, fmt_tick(v, tstep) if tstep < 1 else fmt(v), 12, INK, "middle", 600))
        out.append(text(left + group * i + group / 2, top + ph + 22, c, 13, INK, "middle"))
    out.append(text(W - right, h - 36, spec.get("unit", ""), 12, MUTED, "end"))
    return "\n".join(out + footer(spec, h))


def hbar(spec):
    cats, series = spec["categories"], spec["series"]
    n, k = len(cats), len(series)
    rowh = 18 * k + 14
    top = 60 + (22 if k > 1 else 0)
    h = top + rowh * n + 60
    left, right = 24 + max(len(str(c)) for c in cats) * 13 + 8, 80
    pw = W - left - right
    vmax = nice_max(max(v for s in series for v in s["values"] if v is not None))
    out = header(spec, h)
    if k > 1:
        out += legend(series, 24, 54)
    for t in range(5):
        x = left + pw * t / 4
        out.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + rowh * n}" stroke="{LINE}"/>')
        out.append(text(x, top + rowh * n + 18, fmt_tick(vmax * t / 4, vmax / 4), 12, MUTED, "middle"))
    for i, c in enumerate(cats):
        y0 = top + rowh * i + 7
        out.append(text(left - 8, y0 + (rowh - 14) / 2 + 5, c, 13, INK, "end"))
        for j, s in enumerate(series):
            v = s["values"][i]
            if v is None:
                continue
            bw = pw * v / vmax
            y = y0 + j * 18
            out.append(f'<path d="M{left},{y} h{max(bw - 4, 0):.1f} q4,0 4,4 v6 q0,4 -4,4 h{-max(bw - 4, 0):.1f} z" fill="{COLORS[j % 6]}"/>')
            if n * k <= 12:
                out.append(text(left + bw + 6, y + 11, (fmt_tick(v, vmax / 4) if vmax < 4 else fmt(v)) + (spec.get("unit", "") if k == 1 else ""), 12, INK, "start", 600))
    return "\n".join(out + footer(spec, h))


def line(spec):
    xs, series = spec["x"], spec["series"]
    k, n = len(series), len(xs)
    h = 400
    top, left, right, bottom = 60 + (22 if k > 1 else 0), 70, 40, 70
    pw, ph = W - left - right, h - top - bottom
    vals = [v for s in series for v in s["values"] if v is not None]
    vmax = nice_max(max(vals)); vmin = 0 if min(vals) >= 0 else min(vals)
    if spec.get("ymin") is not None:   # 지수(2015=100)처럼 0 에서 시작하면 변화가 눌리는 그림은 축 아래를 지정(출처 줄에 밝힘)
        vmin = spec["ymin"]; vmax = nice_max(max(vals) - vmin) + vmin
    out = header(spec, h)
    if k > 1:
        out += legend(series, left, 54)
    for t in range(5):
        y = top + ph - ph * t / 4
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + pw}" y2="{y:.1f}" stroke="{LINE}"/>')
        out.append(text(left - 8, y + 4, fmt(vmin + (vmax - vmin) * t / 4), 12, MUTED, "end"))
    step = pw / max(n - 1, 1)
    # 끝 값 표시가 겹치지 않게: 마지막 점의 y 를 모아 14px 이상 떨어뜨린다
    ends = sorted(((top + ph - ph * (s["values"][-1] - vmin) / (vmax - vmin), j) for j, s in enumerate(series) if s["values"] and s["values"][-1] is not None))
    label_y = {}
    prev = None
    for y, j in ends:
        if prev is not None and y - prev < 14:
            y = prev + 14
        label_y[j] = y; prev = y
    lab_every = max(1, math.ceil(n / 8))
    for i, x in enumerate(xs):
        if i % lab_every == 0 or i == n - 1:
            out.append(text(left + step * i, top + ph + 22, x, 12, MUTED, "middle"))
    for j, s in enumerate(series):
        pts = [(left + step * i, top + ph - ph * (v - vmin) / (vmax - vmin)) for i, v in enumerate(s["values"]) if v is not None]
        if len(pts) > 1:
            out.append('<path d="' + " ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts)) + f'" fill="none" stroke="{COLORS[j % 6]}" stroke-width="2" stroke-linejoin="round"/>')
        for (x, y) in ([pts[0], pts[-1]] if len(pts) > 2 else pts):
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{COLORS[j % 6]}" stroke="{BG}" stroke-width="2"/>')
        if pts:
            x, y = pts[-1]
            out.append(text(min(x + 8, W - right), label_y.get(j, y) + 4, fmt(s["values"][-1]) + spec.get("unit", ""), 12, INK, "start", 600))
    return "\n".join(out + footer(spec, h))


def wrap(s: str, width: int) -> list[str]:
    words, lines, cur = str(s).split(" "), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def steps(spec):
    st = spec["steps"]; n = len(st)
    gap, left = 16, 24
    bw = (W - left * 2 - gap * (n - 1)) / n
    cw = int(bw / 13)
    body_lines = [sum(len(wrap("· " + it, cw)) for it in s.get("items", [])) for s in st]
    bh = 62 + 20 * max(body_lines + [1])
    h = 60 + bh + 50
    out = header(spec, h)
    cur = spec.get("current")
    for i, s in enumerate(st):
        x = left + i * (bw + gap); y = 56
        out.append(f'<rect x="{x}" y="{y}" width="{bw:.1f}" height="{bh}" rx="6" fill="{SURFACE}" stroke="{LINE}"/>')
        out.append(f'<rect x="{x}" y="{y}" width="{bw:.1f}" height="30" rx="6" fill="{COLORS[0]}"/>')
        out.append(f'<rect x="{x}" y="{y + 20}" width="{bw:.1f}" height="10" fill="{COLORS[0]}"/>')
        out.append(text(x + 10, y + 20, s.get("label", f"{i + 1}단계"), 13, "#ffffff", weight=700))
        out.append(text(x + 10, y + 50, s.get("head", ""), 14, INK, weight=700))
        yy = y + 70
        for it in s.get("items", []):
            for ln in wrap("· " + it, cw):
                out.append(text(x + 10, yy, ln, 12, MUTED)); yy += 18
        if i < n - 1:
            ax = x + bw + 2
            out.append(f'<path d="M{ax},{y + bh / 2 - 6} l{gap - 4},6 l{-(gap - 4)},6 z" fill="{MUTED}"/>')
        if cur is not None and cur == i + 1:
            out.append(text(x + bw / 2, y - 8, "▼ 현재", 12, COLORS[3], "middle", 700))
    return "\n".join(out + footer(spec, h))


def compare(spec):
    cols, rows = spec["columns"], spec["rows"]
    n = len(cols)
    left = 24; tw = W - 48
    cw = [tw * (0.22 if i == 0 else 0.78 / (n - 1)) for i in range(n)]
    charw = [int(c / 12.5) for c in cw]
    lines = [[wrap(str(cell), charw[i]) for i, cell in enumerate(r)] for r in rows]
    rh = [max(len(c) for c in r) * 19 + 16 for r in lines]
    h = 60 + 36 + sum(rh) + 50
    out = header(spec, h)
    y = 56
    out.append(f'<rect x="{left}" y="{y}" width="{tw}" height="36" fill="{SURFACE}" stroke="{LINE}"/>')
    x = left
    for i, c in enumerate(cols):
        out.append(text(x + cw[i] / 2, y + 23, c, 13, INK, "middle", 700)); x += cw[i]
    y += 36
    for r, hgt in zip(lines, rh):
        out.append(f'<rect x="{left}" y="{y}" width="{tw}" height="{hgt}" fill="{BG}" stroke="{LINE}"/>')
        x = left
        for i, cell in enumerate(r):
            for li, ln in enumerate(cell):
                out.append(text(x + (12 if i == 0 else cw[i] / 2), y + 24 + li * 19, ln, 13, INK if i else INK, "start" if i == 0 else "middle", 700 if i == 0 else 400))
            if i:
                out.append(f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + hgt}" stroke="{LINE}"/>')
            x += cw[i]
        y += hgt
    return "\n".join(out + footer(spec, h))


def scatter(spec):
    """산점도: 점마다 이름표, 평균선(x·y), 강조 점(highlight)은 주황·굵게. 회귀선은 그리지 않는다(값 그대로)."""
    pts = spec["points"]
    h = 480
    left, top, pw, ph = 70, 56, W - 100, h - 56 - 80
    xs = [p["x"] for p in pts] + ([spec["xmean"]] if spec.get("xmean") is not None else [])
    ys = [p["y"] for p in pts] + ([spec["ymean"]] if spec.get("ymean") is not None else [])
    xmin, xmax = spec.get("xmin", min(xs)), spec.get("xmax", max(xs))
    ymin, ymax = spec.get("ymin", min(ys)), spec.get("ymax", max(ys))
    xpad, ypad = (xmax - xmin or 1) * 0.08, (ymax - ymin or 1) * 0.1
    xmin, xmax, ymin, ymax = xmin - xpad, xmax + xpad, ymin - ypad, ymax + ypad
    sx = lambda v: left + (v - xmin) / (xmax - xmin) * pw
    sy = lambda v: top + ph - (v - ymin) / (ymax - ymin) * ph
    out = header(spec, h)
    out.append(f'<rect x="{left}" y="{top}" width="{pw}" height="{ph}" fill="none" stroke="{LINE}"/>')
    # 눈금 5개
    for i in range(6):
        xv = xmin + (xmax - xmin) * i / 5; yv = ymin + (ymax - ymin) * i / 5
        out.append(text(sx(xv), top + ph + 18, f"{xv:.{spec.get('xdec', 2)}f}", 11, MUTED, "middle"))
        out.append(text(left - 6, sy(yv) + 4, f"{yv:.{spec.get('ydec', 1)}f}", 11, MUTED, "end"))
        out.append(f'<line x1="{left}" y1="{sy(yv):.1f}" x2="{left + pw}" y2="{sy(yv):.1f}" stroke="{LINE}" stroke-dasharray="2,3"/>')
    if spec.get("xmean") is not None:
        out.append(f'<line x1="{sx(spec["xmean"]):.1f}" y1="{top}" x2="{sx(spec["xmean"]):.1f}" y2="{top + ph}" stroke="{COLORS[2]}" stroke-width="1.5" stroke-dasharray="6,4"/>')
        out.append(text(sx(spec["xmean"]) + 4, top + 14, f"{spec.get('xmean_label', '평균')}: {spec['xmean']:.{spec.get('xdec', 2)}f}", 11, COLORS[2]))
    if spec.get("ymean") is not None:
        out.append(f'<line x1="{left}" y1="{sy(spec["ymean"]):.1f}" x2="{left + pw}" y2="{sy(spec["ymean"]):.1f}" stroke="{COLORS[2]}" stroke-width="1.5" stroke-dasharray="6,4"/>')
        out.append(text(left + 4, sy(spec["ymean"]) - 5, f"{spec.get('ymean_label', '평균')}: {spec['ymean']:.{spec.get('ydec', 1)}f}", 11, COLORS[2]))
    placed = []   # 이름표 겹침 방지: 가까운 점의 이름표는 아래쪽으로 밀어 낸다
    for p_ in pts:
        hl = p_.get("highlight")
        out.append(f'<circle cx="{sx(p_["x"]):.1f}" cy="{sy(p_["y"]):.1f}" r="{7 if hl else 5}" fill="{COLORS[1] if hl else COLORS[0]}" stroke="{BG}" stroke-width="2"/>')
        lx, ly = sx(p_["x"]) + 8, sy(p_["y"]) - 6
        for (qx, qy) in placed:
            if abs(qx - lx) < 44 and abs(qy - ly) < 13:
                ly = qy + 13
        placed.append((lx, ly))
        out.append(text(lx, ly, p_["label"], 12 if hl else 11, INK if hl else MUTED, weight=700 if hl else 400))
    out.append(text(left + pw / 2, h - 36, spec.get("xlabel", ""), 12, MUTED, "middle"))
    out.append(text(16, top - 8, spec.get("ylabel", ""), 12, MUTED))
    return "\n".join(out + footer(spec, h))


def heatmap(spec):
    """히트맵: 값이 클수록 붉게(1 기준 흰색 → vmax 진한 붉음). 강조 행은 테두리."""
    rows, cols, vals = spec["rows"], spec["cols"], spec["values"]
    left, top = 90, 56
    cw = min(44, (W - left - 24) / max(1, len(cols))); rh = 22
    h = top + rh * len(rows) + 150
    vmin, vmax = spec.get("vmin", 0), spec.get("vmax", max(max(r) for r in vals) or 1)
    out = header(spec, h)
    for i, r in enumerate(rows):
        y = top + i * rh
        hl = r == spec.get("highlight_row")
        out.append(text(left - 6, y + rh - 6, r, 11, INK if hl else MUTED, "end", 700 if hl else 400))
        for j, v in enumerate(vals[i]):
            t = 0 if v is None else max(0, min(1, (v - vmin) / (vmax - vmin)))
            rch, gch, bch = 255, int(255 - 200 * t), int(255 - 210 * t)
            out.append(f'<rect x="{left + j * cw:.1f}" y="{y}" width="{cw - 1:.1f}" height="{rh - 1}" fill="rgb({rch},{gch},{bch})"/>')
        if hl:
            out.append(f'<rect x="{left}" y="{y}" width="{cw * len(cols):.1f}" height="{rh - 1}" fill="none" stroke="{INK}" stroke-width="1.5"/>')
    for j, c in enumerate(cols):
        x = left + j * cw + cw / 2
        out.append(f'<text x="{x:.1f}" y="{top + rh * len(rows) + 6}" font-size="10" fill="{MUTED}" text-anchor="end" transform="rotate(-60 {x:.1f},{top + rh * len(rows) + 6})" {FONT}>{esc(str(c))}</text>')
    out.append(text(left, h - 34, f"색: 흰색 {vmin:g} → 붉은색 {vmax:g} 이상 (값이 클수록 특화)", 11, MUTED))
    return "\n".join(out + footer(spec, h))


RENDER = {"bar": bar, "hbar": hbar, "line": line, "steps": steps, "compare": compare, "scatter": scatter, "heatmap": heatmap}
DEMO = {"type": "bar", "title": "대구 의료용 기기 제조 기업 규모 분포", "unit": "곳", "categories": ["1~9인", "10~49인", "50인 이상", "미기재"], "series": [{"name": "기업 수", "values": [50, 42, 21, 9]}], "source": "기업 사전 2026-08(팩토리온), KSIC 271(안경 제외)"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args(argv)
    spec = DEMO if a.demo else json.loads(Path(a.spec).read_text(encoding="utf-8"))
    if spec.get("type") not in RENDER:
        print(f"type 은 {list(RENDER)} 중 하나", file=sys.stderr); return 2
    svg = RENDER[spec["type"]](spec)
    if a.out:
        p = Path(a.out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(svg, encoding="utf-8"); print(f"→ {p}")
    else:
        print(svg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
