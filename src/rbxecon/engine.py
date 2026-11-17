"""Moteur de simulation : le revenu ne change qu'aux achats, donc on saute d'achat en achat."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from .config import BASE_GROUP, Config, Item

DAY = 24 * 3600


def rnd(x: float) -> int:
    """Arrondi 'à la Luau' : math.floor(x + 0.5) (identique côté jeu)."""
    return math.floor(x + 0.5)


@dataclass
class Purchase:
    time: float  # secondes, moment de l'achat
    item: str
    number: int  # n-ième exemplaire de cet item
    cost: float
    wait: float  # temps passé à attendre l'argent
    income_after: float


@dataclass
class Result:
    strategy: str
    purchases: list[Purchase] = field(default_factory=list)
    end_time: float = 0.0
    final_income: float = 0.0
    start_income: float = 0.0
    status: str = "finished"  # finished | blocked | stuck | timeout
    detail: str = ""
    never_bought: list[str] = field(default_factory=list)

    @property
    def finished(self) -> bool:
        return self.status == "finished"

    def time_of(self, item: str, count: int = 1) -> float | None:
        for p in self.purchases:
            if p.item == item and p.number == count:
                return p.time
        return None


class Sim:
    """État d'une partie simulée."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.counts: dict[str, int] = {it.name: 0 for it in cfg.items}
        self.cash = cfg.start_cash
        self.time = 0.0
        self._income_items = [it for it in cfg.items if it.kind == "income"]
        self._mults = [it for it in cfg.items if it.kind == "multiplier"]
        self._rebuild()

    def _rebuild(self) -> None:
        """Recalcule les agrégats (appelé une fois par achat) ; income_after() les réutilise."""
        self._sums: dict[str, float] = defaultdict(float)
        self._sums[BASE_GROUP] = self.cfg.base_income
        for it in self._income_items:
            if self.counts[it.name]:
                self._sums[it.group] += it.income * self.counts[it.name]
        self._mall = 1.0
        self._mg: dict[str, float] = defaultdict(lambda: 1.0)
        for m in self._mults:
            n = self.counts[m.name]
            if n:
                if m.applies_to is None:
                    self._mall *= m.multiplier ** n
                else:
                    self._mg[m.applies_to] *= m.multiplier ** n
        self.income = sum(v * self._mg[g] for g, v in self._sums.items()) * self._mall

    # ---- économie -------------------------------------------------------
    def income_for(self, counts: dict[str, int]) -> float:
        sums: dict[str, float] = defaultdict(float)
        sums[BASE_GROUP] = self.cfg.base_income
        for it in self._income_items:
            n = counts.get(it.name, 0)
            if n:
                sums[it.group] += it.income * n
        mult_all = 1.0
        mult_group: dict[str, float] = defaultdict(lambda: 1.0)
        for m in self._mults:
            n = counts.get(m.name, 0)
            if not n:
                continue
            factor = m.multiplier ** n
            if m.applies_to is None:
                mult_all *= factor
            else:
                mult_group[m.applies_to] *= factor
        return sum(v * mult_group[g] for g, v in sums.items()) * mult_all

    def price(self, it: Item, owned: int | None = None) -> float:
        n = self.counts[it.name] if owned is None else owned
        try:
            raw = it.cost * (it.cost_growth ** n)
        except OverflowError:
            return math.inf
        if math.isinf(raw):
            return raw
        return rnd(raw) if self.cfg.round_costs else raw

    def income_after(self, it: Item) -> float:
        """Revenu si on achetait un exemplaire de plus (calcul direct, sans tout recalculer)."""
        if it.kind == "income":
            return self.income + it.income * self._mg[it.group] * self._mall
        if it.applies_to is None:
            return self.income * it.multiplier
        group_part = self._sums.get(it.applies_to, 0.0) * self._mg[it.applies_to] * self._mall
        return self.income + group_part * (it.multiplier - 1)

    # ---- disponibilité ---------------------------------------------------
    def unlocked(self, it: Item) -> bool:
        return all(self.counts.get(r, 0) >= c for r, c in it.requires)

    def available(self) -> list[Item]:
        return [it for it in self.cfg.items if self.counts[it.name] < it.max and self.unlocked(it)]

    def remaining(self) -> list[Item]:
        return [it for it in self.cfg.items if self.counts[it.name] < it.max]

    # ---- action ----------------------------------------------------------
    def buy(self, it: Item, max_seconds: float) -> Purchase | None:
        """Attend l'argent puis achète. None si impossible (bloqué ou délai dépassé)."""
        cost = self.price(it)
        wait = 0.0
        if self.cash < cost:
            if self.income <= 0:
                return None
            wait = (cost - self.cash) / self.income
        if self.time + wait > max_seconds:
            return None
        self.time += wait
        self.cash = max(self.cash + wait * self.income - cost, 0.0)
        self.counts[it.name] += 1
        self._rebuild()
        return Purchase(self.time, it.name, self.counts[it.name], cost, wait, self.income)


def simulate(cfg: Config, strategy, max_hours: float = 24.0) -> Result:
    """Joue une partie complète avec `strategy` (voir strategies.py)."""
    sim = Sim(cfg)
    max_seconds = max_hours * 3600
    res = Result(strategy=strategy.name, start_income=sim.income)
    while True:
        avail = sim.available()
        if not avail:
            left = [it.name for it in sim.remaining()]
            if left:
                res.status, res.never_bought = "blocked", left
                res.detail = "No item can be unlocked any more."
            break
        choice = strategy.pick(sim, avail)
        bought = sim.buy(choice, max_seconds)
        if bought is None:
            if sim.income <= 0 and sim.cash < sim.price(choice):
                res.status = "stuck"
                res.detail = f"Income is 0 and '{choice.name}' costs {sim.price(choice):,.0f}."
            else:
                res.status = "timeout"
                res.detail = f"Not finished after {max_hours:g} h of play."
            res.never_bought = [it.name for it in sim.remaining()]
            break
        res.purchases.append(bought)
    res.end_time = res.purchases[-1].time if res.purchases else 0.0
    res.final_income = sim.income
    return res
