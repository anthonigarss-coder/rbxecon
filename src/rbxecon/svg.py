"""Courbe de revenu en SVG (sans dépendance)."""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

from .engine import Result
from .report import fmt_time

COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00"]


def income_chart(results: list[Result], title: str = "Income over time") -> str:
    w, h = 900, 440
    left, right, top, bottom = 80, 30, 50, 60
    pw, ph = w - left - right, h - top - bottom

    series = []
    for r in results:
        pts = [(0.0, r.start_income)] + [(p.time, p.income_after) for p in r.purchases]
        series.append((r, pts))
    all_inc = [v for _, pts in series for _, v in pts if v and v > 0]
    t_max = max([r.end_time for r in results] + [1.0])
    if not all_inc:
        lo, hi = 0.0, 1.0
    else:
        lo = math.floor(math.log10(min(all_inc)))
        hi = math.ceil(math.log10(max(all_inc)))
        if hi == lo:
            hi = lo + 1

    def x(t: float) -> float:
        return left + pw * t / t_max

    def y(v: float) -> float:
        return top + ph * (1 - (math.log10(max(v, 10 ** lo)) - lo) / (hi - lo))

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="sans-serif" font-size="12">',
        f'<rect width="{w}" height="{h}" fill="white"/>',
        f'<text x="{w / 2}" y="26" text-anchor="middle" font-size="16" font-weight="bold">{escape(title)}</text>',
    ]
    for d in range(int(lo), int(hi) + 1):
        yy = y(10.0 ** d)
        out.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{left + pw}" y2="{yy:.1f}" stroke="#ddd"/>')
        out.append(f'<text x="{left - 8}" y="{yy + 4:.1f}" text-anchor="end">{10.0 ** d:g}</text>')
    for i in range(6):
        t = t_max * i / 5
        xx = x(t)
        out.append(f'<line x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{top + ph}" stroke="#eee"/>')
        out.append(f'<text x="{xx:.1f}" y="{top + ph + 18}" text-anchor="middle">{escape(fmt_time(t))}</text>')
    out.append(f'<rect x="{left}" y="{top}" width="{pw}" height="{ph}" fill="none" stroke="#999"/>')
    out.append(f'<text x="{left + pw / 2}" y="{h - 14}" text-anchor="middle">time played</text>')
    out.append(f'<text x="18" y="{top + ph / 2}" text-anchor="middle" transform="rotate(-90 18 {top + ph / 2})">income per second (log scale)</text>')

    for i, (r, pts) in enumerate(series):
        color = COLORS[i % len(COLORS)]
        d = []
        prev = None
        for t, v in pts:
            if v is None or v <= 0:
                continue
            if prev is not None:
                d.append(f"L{x(t):.1f},{y(prev):.1f}")  # marche : le revenu saute à l'achat
            d.append(f"{'M' if not d else 'L'}{x(t):.1f},{y(v):.1f}")
            prev = v
        if d:
            out.append(f'<path d="{" ".join(d)}" fill="none" stroke="{color}" stroke-width="2"/>')
        lx = left + 12 + i * 130
        out.append(f'<rect x="{lx}" y="{top + 8}" width="14" height="4" fill="{color}"/>')
        out.append(f'<text x="{lx + 20}" y="{top + 14}">{escape(r.strategy)}</text>')
    out.append("</svg>")
    return "\n".join(out)
