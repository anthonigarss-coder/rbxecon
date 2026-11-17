"""Façons de jouer simulées."""

from __future__ import annotations

from .config import Item
from .engine import Sim


class Strategy:
    name = ""
    description = ""

    def pick(self, sim: Sim, avail: list[Item]) -> Item:  # pragma: no cover
        raise NotImplementedError


class Order(Strategy):
    name = "order"
    description = "buys in the order of the file (the path you designed)"

    def pick(self, sim: Sim, avail: list[Item]) -> Item:
        return avail[0]


class Cheapest(Strategy):
    name = "cheapest"
    description = "always buys the cheapest thing (a casual player)"

    def pick(self, sim: Sim, avail: list[Item]) -> Item:
        return min(avail, key=lambda it: (sim.price(it), sim.cfg.items.index(it)))


class Roi(Strategy):
    name = "roi"
    description = "buys what pays itself back fastest (an optimizing player)"

    def pick(self, sim: Sim, avail: list[Item]) -> Item:
        best: tuple[float, int, Item] | None = None
        gates = _gate_paybacks(sim, avail)
        for idx, it in enumerate(sim.cfg.items):
            if it not in avail:
                continue
            gain = sim.income_after(it) - sim.income
            if gain > 1e-12:
                pb = sim.price(it) / gain
            else:
                pb = gates.get(it.name, float("inf"))
            if pb != float("inf") and (best is None or (pb, idx) < (best[0], best[1])):
                best = (pb, idx, it)
        if best is None:  # rien ne rapporte : on prend le moins cher
            return Cheapest().pick(sim, avail)
        return best[2]


def _gate_paybacks(sim: Sim, avail: list[Item]) -> dict[str, float]:
    """Pour les items sans gain direct (portes de déblocage) : rentabilité de la
    voie complète « acheter ce qui manque + l'item verrouillé qu'il ouvre »."""
    out: dict[str, float] = {}
    avail_names = {it.name for it in avail}
    for target in sim.cfg.items:
        if sim.counts[target.name] >= target.max or sim.unlocked(target):
            continue
        missing = {r: c - sim.counts.get(r, 0) for r, c in target.requires if sim.counts.get(r, 0) < c}
        if not all(r in avail_names for r in missing):
            continue  # prérequis imbriqués : on ne regarde qu'un niveau
        counts = dict(sim.counts)
        total_cost = 0.0
        for r, need in missing.items():
            item = sim.cfg.item(r)
            for k in range(need):
                total_cost += sim.price(item, counts[r])
                counts[r] += 1
        total_cost += sim.price(target)
        counts[target.name] += 1
        gain = sim.income_for(counts) - sim.income
        if gain <= 1e-12:
            continue
        pb = total_cost / gain
        for r in missing:
            out[r] = min(out.get(r, float("inf")), pb)
    return out


STRATEGIES: dict[str, Strategy] = {s.name: s for s in (Roi(), Cheapest(), Order())}
