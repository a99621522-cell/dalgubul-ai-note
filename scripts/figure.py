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
    vmax = nice_max(max(v for s in series for v in s["values"] if v is not None))
    out = header(spec, h)
    if k > 1:
        out += legend(series, left, 54)
    for t in range(5):
        y = top + ph - ph * t / 4
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + pw}" y2="{y:.1f}" stroke="{LINE}" stroke-width="1"/>')
        out.append(text(left - 8, y + 4, fmt(vmax * t / 4), 12, MUTED, "end"))
    group = pw / n
    bw = min(24, (group * 0.7) / k)
    for i, c in enumerate(cats):
        gx = left + group * i + group / 2 - (bw * k + 4 * (k - 1)) / 2
        for j, s in enumerate(series):
            v = s["values"][i]
            if v is None:
                continue
            bh = ph * v / vmax
            x, y = gx + j * (bw + 4), top + ph - bh
            out.append(f'<path d="M{x:.1f},{top + ph:.1f} v{-max(bh - 4, 0):.1f} q0,-4 4,-4 h{bw - 8:.1f} q4,0 4,4 v{max(bh - 4, 0):.1f} z" fill="{COLORS[j % 6]}"/>')
            if n * k <= 12:
                out.append(text(x + bw / 2, y - 6, fmt(v), 12, INK, "middle", 600))
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
        out.append(text(x, top + rowh * n + 18, fmt(vmax * t / 4), 12, MUTED, "middle"))
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
                out.append(text(left + bw + 6, y + 11, fmt(v) + (spec.get("unit", "") if k == 1 else ""), 12, INK, "start", 600))
    return "\n".join(out + footer(spec, h))


def line(spec):
    xs, series = spec["x"], spec["series"]
    k, n = len(series), len(xs)
    h = 400
    top, left, right, bottom = 60 + (22 if k > 1 else 0), 70, 40, 70
    pw, ph = W - left - right, h - top - bottom
    vals = [v for s in series for v in s["values"] if v is not None]
    vmax = nice_max(max(vals)); vmin = 0 if min(vals) >= 0 else min(vals)
    out = header(spec, h)
    if k > 1:
        out += legend(series, left, 54)
    for t in range(5):
        y = top + ph - ph * t / 4
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + pw}" y2="{y:.1f}" stroke="{LINE}"/>')
        out.append(text(left - 8, y + 4, fmt(vmin + (vmax - vmin) * t / 4), 12, MUTED, "end"))
    step = pw / max(n - 1, 1)
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
            out.append(text(min(x + 8, W - right), y + 4, fmt(s["values"][-1]) + spec.get("unit", ""), 12, INK, "start", 600))
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


RENDER = {"bar": bar, "hbar": hbar, "line": line, "steps": steps, "compare": compare}
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
