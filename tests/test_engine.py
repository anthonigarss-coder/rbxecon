import pytest

from helpers import make
from rbxecon import STRATEGIES, simulate
from rbxecon.engine import Sim, rnd


def run(cfg, strategy="order", **kw):
    return simulate(cfg, STRATEGIES[strategy], **kw)


def test_hand_computed_timeline():
    # revenu 1/s ; A coûte 10 puis 20 ; chaque exemplaire rapporte +1/s
    cfg = make([{"name": "A", "cost": 10, "income": 1, "cost_growth": 2, "max": 2}], base_income=1)
    res = run(cfg)
    assert res.finished
    assert [p.time for p in res.purchases] == pytest.approx([10, 20])
    assert [p.income_after for p in res.purchases] == pytest.approx([2, 3])
    assert [p.cost for p in res.purchases] == [10, 20]
    assert res.end_time == pytest.approx(20)
    assert res.final_income == pytest.approx(3)


def test_start_cash_is_spent_first_without_waiting():
    cfg = make([{"name": "A", "cost": 10, "income": 1}], start_cash=25, base_income=1)
    (p,) = run(cfg).purchases
    assert p.wait == 0 and p.time == 0


def test_leftover_cash_carries_over():
    # start 25, A coûte 10 : il reste 15, B (20) demande 5 s de plus à 1/s (+1 d'A = 2/s -> 2.5 s)
    cfg = make([{"name": "A", "cost": 10, "income": 1}, {"name": "B", "cost": 20}], start_cash=25, base_income=1)
    a, b = run(cfg).purchases
    assert b.wait == pytest.approx(2.5)


def test_rounding_matches_luau_floor_plus_half():
    assert rnd(2.5) == 3 and rnd(0.5) == 1 and rnd(12.4) == 12 and rnd(12.5) == 13
    cfg = make([{"name": "A", "cost": 10, "cost_growth": 1.15, "max": 3}], round_costs=True)
    sim = Sim(cfg)
    it = cfg.items[0]
    assert [sim.price(it, n) for n in range(3)] == [10, 12, 13]  # 10, 11.5, 13.225
    cfg_raw = make([{"name": "A", "cost": 10, "cost_growth": 1.15, "max": 3}], round_costs=False)
    assert Sim(cfg_raw).price(cfg_raw.items[0], 1) == pytest.approx(11.5)


def test_income_groups_and_multipliers():
    cfg = make([
        {"name": "G", "cost": 1, "income": 5, "group": "g", "max": 2},
        {"name": "H", "cost": 1, "income": 7, "group": "h"},
        {"name": "MG", "cost": 1, "kind": "multiplier", "multiplier": 3, "applies_to": "g"},
        {"name": "MALL", "cost": 1, "kind": "multiplier", "multiplier": 2, "max": 2},
    ], base_income=10)
    sim = Sim(cfg)
    assert sim.income_for({}) == 10
    # (base 10 + g 5*2 *3 + h 7) * 2^2
    got = sim.income_for({"G": 2, "H": 1, "MG": 1, "MALL": 2})
    assert got == pytest.approx((10 + 30 + 7) * 4)


def test_requirements_gate_purchases():
    cfg = make([
        {"name": "A", "cost": 10, "income": 1, "max": 2},
        {"name": "B", "cost": 5, "income": 1, "requires": [{"item": "A", "count": 2}]},
    ], start_cash=1000)
    names = [f"{p.item}{p.number}" for p in run(cfg, "cheapest").purchases]
    assert names.index("B1") > names.index("A2")


def test_stuck_when_no_income():
    cfg = make([{"name": "A", "cost": 5, "income": 1}])
    res = run(cfg)
    assert res.status == "stuck" and res.never_bought == ["A"]


def test_blocked_when_requirement_can_never_be_met():
    cfg = make([
        {"name": "A", "cost": 1, "income": 1},
        {"name": "B", "cost": 1, "requires": [{"item": "A", "count": 2}]},
    ], base_income=1)
    res = run(cfg)
    assert res.status == "blocked" and res.never_bought == ["B"]


def test_timeout():
    cfg = make([{"name": "A", "cost": 10**9, "income": 1}], base_income=1)
    res = run(cfg, max_hours=1)
    assert res.status == "timeout"


def test_cheapest_vs_roi_choice():
    items = [
        {"name": "Slow", "cost": 10, "income": 0.5},    # payback 20 s
        {"name": "Fast", "cost": 100, "income": 10},    # payback 10 s
    ]
    cfg = make(items, start_cash=100, base_income=1)
    assert run(cfg, "cheapest").purchases[0].item == "Slow"
    assert run(cfg, "roi").purchases[0].item == "Fast"
    assert run(cfg, "order").purchases[0].item == "Slow"


def test_roi_buys_unlock_gate_when_it_leads_to_a_great_item():
    cfg = make([
        {"name": "Filler", "cost": 50, "income": 1},                      # payback 50
        {"name": "Gate", "cost": 10},                                     # aucun revenu direct
        {"name": "Star", "cost": 100, "income": 20, "requires": ["Gate"]},  # (10+100)/20 = 5.5
    ], start_cash=1000, base_income=1)
    assert run(cfg, "roi").purchases[0].item == "Gate"


def test_all_strategies_finish_same_content_with_same_final_income():
    cfg = make([
        {"name": "A", "cost": 10, "income": 1, "cost_growth": 1.3, "max": 4},
        {"name": "B", "cost": 200, "income": 9, "requires": [{"item": "A", "count": 2}]},
        {"name": "M", "cost": 80, "kind": "multiplier", "multiplier": 1.5},
    ], base_income=2)
    finals = {n: run(cfg, n).final_income for n in STRATEGIES}
    assert len({round(v, 6) for v in finals.values()}) == 1
    assert all(run(cfg, n).finished for n in STRATEGIES)


def test_income_after_matches_full_recompute():
    import random

    rng = random.Random(7)
    items = [
        {"name": f"I{i}", "cost": 5 + i, "income": rng.uniform(0.5, 9), "group": rng.choice(["a", "b", "c"]), "max": 6}
        for i in range(8)
    ] + [
        {"name": "MA", "cost": 9, "kind": "multiplier", "multiplier": 1.4, "max": 3},
        {"name": "MB", "cost": 9, "kind": "multiplier", "multiplier": 1.7, "applies_to": "b", "max": 3},
        {"name": "MBase", "cost": 9, "kind": "multiplier", "multiplier": 2, "applies_to": "base"},
    ]
    cfg = make(items, base_income=3)
    sim = Sim(cfg)
    for _ in range(40):
        it = rng.choice(cfg.items)
        expect = sim.income_for({**sim.counts, it.name: sim.counts[it.name] + 1})
        assert sim.income_after(it) == pytest.approx(expect)
        if sim.counts[it.name] < it.max:
            sim.cash = 10**9
            sim.buy(it, 10**12)
            assert sim.income == pytest.approx(sim.income_for(sim.counts))


def test_huge_cost_growth_does_not_crash():
    cfg = make([{"name": "A", "cost": 10, "income": 1, "cost_growth": 3, "max": 800}], base_income=5)
    res = simulate(cfg, STRATEGIES["order"], max_hours=10)
    assert res.status == "timeout" and res.purchases
