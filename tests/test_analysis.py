import pytest

from helpers import make
from rbxecon import STRATEGIES, analyze, simulate
from rbxecon.report import fmt_time


def an_for(items, targets=(), **kw):
    cfg = make(items, targets=targets, **kw)
    res = simulate(cfg, STRATEGIES["order"])
    return cfg, res, analyze(cfg, res)


def test_target_statuses():
    items = [{"name": "A", "cost": 600, "income": 1}]  # base 1/s -> 600 s = 10 min
    targets = [
        {"item": "A", "minutes": 10},                      # pile
        {"item": "A", "minutes": 10.5},                    # dans la tolérance
        {"item": "A", "minutes": 30},                      # trop rapide
        {"item": "A", "minutes": 5},                       # trop lent
        {"item": "*", "minutes": 10},
    ]
    _, res, an = an_for(items, targets, base_income=1)
    assert [t.status for t in an.targets] == ["OK", "OK", "TOO FAST", "TOO SLOW", "OK"]
    assert an.targets[0].reached == pytest.approx(600)


def test_target_never_when_not_finished():
    items = [{"name": "A", "cost": 1, "income": 1, "requires": [{"item": "B", "count": 1}]},
             {"name": "B", "cost": 1, "requires": [{"item": "A", "count": 1}]}]
    cfg = make(items, base_income=1, targets=[{"item": "*", "minutes": 5}, {"item": "A", "minutes": 5}])
    res = simulate(cfg, STRATEGIES["order"])
    an = analyze(cfg, res)
    assert [t.status for t in an.targets] == ["NEVER", "NEVER"]


def test_dead_zones_follow_max_wait():
    items = [{"name": "Quick", "cost": 10, "income": 1}, {"name": "Slow", "cost": 4000, "income": 1}]
    _, res, an = an_for(items, base_income=1, max_wait_minutes=3)
    assert [p.item for p in an.dead_zones] == ["Slow"]
    _, res, an = an_for(items, base_income=1, max_wait_minutes=100)
    assert an.dead_zones == []
    assert an.longest[0].item == "Slow"


def test_fmt_time():
    assert fmt_time(5) == "5s"
    assert fmt_time(65) == "1m 05s"
    assert fmt_time(3725) == "1h 02m"
    assert fmt_time(3 * 86400 + 5 * 3600) == "3d 5h"
