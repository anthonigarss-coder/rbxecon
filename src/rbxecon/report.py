"""Affichage texte, JSON et CSV des résultats."""

from __future__ import annotations

import csv
import io
import json

from .analysis import Analysis
from .config import Config
from .engine import Result
from .strategies import STRATEGIES


def fmt_time(seconds: float) -> str:
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    if h < 48:
        return f"{h}h {m:02d}m"
    d, h = divmod(h, 24)
    return f"{d}d {h}h"


def fmt_num(x: float) -> str:
    if abs(x) >= 1e15:
        return f"{x:.3g}"
    if abs(x) >= 100 or x == int(x):
        return f"{x:,.0f}"
    return f"{x:,.2f}"


def render_text(cfg: Config, res: Result, an: Analysis, timeline: int = 0) -> str:
    strat = STRATEGIES[res.strategy]
    out = [f"Strategy: {res.strategy}  ({strat.description})"]
    n = len(res.purchases)
    if res.finished:
        out.append(f"  Finished everything in {fmt_time(res.end_time)}  |  {n} purchases  |  final income {fmt_num(res.final_income)}/s")
    else:
        out.append(f"  NOT FINISHED ({res.status}): {res.detail}")
        out.append(f"  Reached {fmt_time(res.end_time)}  |  {n} purchases  |  income {fmt_num(res.final_income)}/s")
        if res.never_bought:
            shown = ", ".join(res.never_bought[:8]) + (" ..." if len(res.never_bought) > 8 else "")
            out.append(f"  Never bought: {shown}")
    if res.purchases:
        top = an.longest[0]
        out.append(f"  Waits: median {fmt_time(an.median_wait)}, longest {fmt_time(top.wait)} ({top.item} #{top.number})")
    limit = cfg.max_wait_minutes
    if an.dead_zones:
        out.append(f"  Dead zones (waits over {limit:g} min): {len(an.dead_zones)}")
        for p in sorted(an.dead_zones, key=lambda p: -p.wait)[:5]:
            out.append(f"    - at {fmt_time(p.time)}: waited {fmt_time(p.wait)} for {p.item} #{p.number}")
    else:
        out.append(f"  Dead zones (waits over {limit:g} min): none")
    if an.targets:
        out.append("  Targets:")
        for t in an.targets:
            label = "everything" if t.item == "*" else f"{t.item} #{t.count}"
            got = "never" if t.reached is None else fmt_time(t.reached)
            out.append(f"    {t.status:<8} {label}: wanted {t.minutes:g} min (+/-{t.tolerance:.0%}), got {got}")
    if timeline and res.purchases:
        out.append(f"  First {min(timeline, n)} purchases:")
        out.append(f"    {'time':>9}  {'item':<24} {'cost':>12} {'wait':>8} {'income/s':>12}")
        for p in res.purchases[:timeline]:
            out.append(f"    {fmt_time(p.time):>9}  {(p.item + ' #' + str(p.number)):<24} {fmt_num(p.cost):>12} {fmt_time(p.wait):>8} {fmt_num(p.income_after):>12}")
    return "\n".join(out)


def to_dict(cfg: Config, res: Result, an: Analysis) -> dict:
    return {
        "strategy": res.strategy,
        "status": res.status,
        "detail": res.detail,
        "end_seconds": res.end_time,
        "final_income": res.final_income,
        "purchases": len(res.purchases),
        "never_bought": res.never_bought,
        "median_wait_seconds": an.median_wait,
        "dead_zones": [
            {"time": p.time, "wait": p.wait, "item": p.item, "number": p.number} for p in an.dead_zones
        ],
        "targets": [
            {
                "item": t.item, "count": t.count, "minutes": t.minutes, "tolerance": t.tolerance,
                "reached_seconds": t.reached, "status": t.status,
            }
            for t in an.targets
        ],
        "timeline": [
            {"time": p.time, "item": p.item, "number": p.number, "cost": p.cost,
             "wait": p.wait, "income_after": p.income_after}
            for p in res.purchases
        ],
    }


def render_json(cfg: Config, results: list[tuple[Result, Analysis]]) -> str:
    return json.dumps([to_dict(cfg, r, a) for r, a in results], indent=2)


def render_csv(results: list[Result]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["strategy", "time_seconds", "item", "number", "cost", "wait_seconds", "income_after"])
    for r in results:
        for p in r.purchases:
            w.writerow([r.strategy, f"{p.time:.3f}", p.item, p.number, f"{p.cost:.6g}", f"{p.wait:.3f}", f"{p.income_after:.6g}"])
    return buf.getvalue()
