"""Lecture d'un résultat de simulation : temps morts, rythme, objectifs."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from .config import Config
from .engine import Purchase, Result


@dataclass
class TargetResult:
    item: str
    count: int
    minutes: float
    tolerance: float
    reached: float | None  # secondes, None = jamais
    status: str  # OK | TOO FAST | TOO SLOW | NEVER

    @property
    def ok(self) -> bool:
        return self.status == "OK"


@dataclass
class Analysis:
    dead_zones: list[Purchase]  # achats précédés d'une attente trop longue
    longest: list[Purchase]
    median_wait: float
    targets: list[TargetResult]


def analyze(cfg: Config, res: Result) -> Analysis:
    limit = cfg.max_wait_minutes * 60
    waits = [p.wait for p in res.purchases]
    dead = [p for p in res.purchases if p.wait > limit]
    longest = sorted(res.purchases, key=lambda p: -p.wait)[:5]
    median = statistics.median(waits) if waits else 0.0

    targets: list[TargetResult] = []
    for t in cfg.targets:
        reached = res.end_time if t.item == "*" and res.finished else (
            None if t.item == "*" else res.time_of(t.item, t.count)
        )
        goal = t.minutes * 60
        if reached is None:
            status = "NEVER"
        elif reached < goal * (1 - t.tolerance):
            status = "TOO FAST"
        elif reached > goal * (1 + t.tolerance):
            status = "TOO SLOW"
        else:
            status = "OK"
        targets.append(TargetResult(t.item, t.count, t.minutes, t.tolerance, reached, status))
    return Analysis(dead, longest, median, targets)
