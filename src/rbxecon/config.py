"""Lecture et validation de la configuration TOML d'une économie de tycoon."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

BASE_GROUP = "base"  # groupe réservé au revenu de base
DEFAULT_GROUP = "default"


class ConfigError(Exception):
    """Fichier de config illisible ou mal formé."""


@dataclass(frozen=True)
class Item:
    name: str
    cost: float
    income: float = 0.0
    kind: str = "income"  # "income" ou "multiplier"
    multiplier: float = 1.0
    group: str = DEFAULT_GROUP  # groupe de revenu (items "income")
    applies_to: str | None = None  # cible d'un multiplicateur (None = tout)
    cost_growth: float = 1.0
    max: int = 1
    requires: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class Target:
    item: str  # nom d'item, ou "*" = tout acheter
    minutes: float
    count: int = 1
    tolerance: float = 0.25


@dataclass(frozen=True)
class Config:
    items: tuple[Item, ...]
    targets: tuple[Target, ...] = ()
    start_cash: float = 0.0
    base_income: float = 0.0
    round_costs: bool = True
    max_wait_minutes: float = 3.0
    source: str = ""

    def item(self, name: str) -> Item | None:
        for it in self.items:
            if it.name == name:
                return it
        return None


@dataclass
class Issue:
    level: str  # "error" | "warning"
    code: str
    message: str


# ------------------------------------------------------------------ lecture


def load(path: str | Path) -> Config:
    p = Path(path)
    try:
        with p.open("rb") as fh:
            data = tomllib.load(fh)
    except OSError as e:
        raise ConfigError(f"Cannot read '{p}': {e.strerror or e}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in '{p}': {e}") from e
    cfg = parse(data)
    return Config(
        items=cfg.items, targets=cfg.targets, start_cash=cfg.start_cash,
        base_income=cfg.base_income, round_costs=cfg.round_costs,
        max_wait_minutes=cfg.max_wait_minutes, source=p.name,
    )


def _num(value, what: str, *, allow_none: bool = False):
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{what} must be a number (got {value!r})")
    return float(value)


def _int(value, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{what} must be a whole number (got {value!r})")
    return value


def parse(data: dict) -> Config:
    eco = data.get("economy", {})
    ana = data.get("analysis", {})
    if not isinstance(eco, dict) or not isinstance(ana, dict):
        raise ConfigError("[economy] and [analysis] must be tables")

    raw_items = data.get("item", [])
    if not isinstance(raw_items, list) or not raw_items:
        raise ConfigError("Define at least one [[item]]")

    items = []
    for i, raw in enumerate(raw_items, 1):
        if not isinstance(raw, dict):
            raise ConfigError(f"item #{i} must be a table")
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"item #{i} needs a text 'name'")
        where = f"item '{name}'"
        if "cost" not in raw:
            raise ConfigError(f"{where} needs a 'cost'")
        kind = raw.get("kind", "income")
        if kind not in ("income", "multiplier"):
            raise ConfigError(f"{where}: kind must be 'income' or 'multiplier'")
        reqs = []
        for r in raw.get("requires", []):
            if isinstance(r, str):
                reqs.append((r, 1))
            elif isinstance(r, dict) and isinstance(r.get("item"), str):
                reqs.append((r["item"], _int(r.get("count", 1), f"{where} requires count")))
            else:
                raise ConfigError(f"{where}: each 'requires' entry is a name or {{ item = \"...\", count = N }}")
        group = raw.get("group", DEFAULT_GROUP)
        applies_to = raw.get("applies_to")
        if not isinstance(group, str) or (applies_to is not None and not isinstance(applies_to, str)):
            raise ConfigError(f"{where}: 'group' and 'applies_to' must be text")
        items.append(Item(
            name=name,
            cost=_num(raw["cost"], f"{where} cost"),
            income=_num(raw.get("income", 0), f"{where} income"),
            kind=kind,
            multiplier=_num(raw.get("multiplier", 1), f"{where} multiplier"),
            group=group,
            applies_to=applies_to,
            cost_growth=_num(raw.get("cost_growth", 1), f"{where} cost_growth"),
            max=_int(raw.get("max", 1), f"{where} max"),
            requires=tuple(reqs),
        ))

    targets = []
    for i, raw in enumerate(data.get("target", []), 1):
        if not isinstance(raw, dict) or not isinstance(raw.get("item"), str):
            raise ConfigError(f"target #{i} needs an 'item' name (or \"*\")")
        if "minutes" not in raw:
            raise ConfigError(f"target '{raw['item']}' needs 'minutes'")
        targets.append(Target(
            item=raw["item"],
            minutes=_num(raw["minutes"], f"target '{raw['item']}' minutes"),
            count=_int(raw.get("count", 1), f"target '{raw['item']}' count"),
            tolerance=_num(raw.get("tolerance", 0.25), f"target '{raw['item']}' tolerance"),
        ))

    return Config(
        items=tuple(items),
        targets=tuple(targets),
        start_cash=_num(eco.get("start_cash", 0), "start_cash"),
        base_income=_num(eco.get("base_income", 0), "base_income"),
        round_costs=bool(eco.get("round_costs", True)),
        max_wait_minutes=_num(ana.get("max_wait_minutes", 3), "max_wait_minutes"),
    )


# --------------------------------------------------------------- validation


def validate(cfg: Config) -> list[Issue]:
    issues: list[Issue] = []
    err = lambda code, msg: issues.append(Issue("error", code, msg))  # noqa: E731
    warn = lambda code, msg: issues.append(Issue("warning", code, msg))  # noqa: E731

    names = [it.name for it in cfg.items]
    seen: set[str] = set()
    for n in names:
        if n in seen:
            err("DUP_ITEM", f"Item '{n}' is defined more than once.")
        seen.add(n)
        if n == "*":
            err("BAD_NAME", "'*' is reserved (it means 'everything' in targets).")

    by_name = {it.name: it for it in cfg.items}
    groups_used = {BASE_GROUP} | {it.group for it in cfg.items if it.kind == "income"}

    for it in cfg.items:
        if it.cost < 0:
            err("BAD_COST", f"'{it.name}': cost is negative.")
        elif it.cost == 0:
            warn("ZERO_COST", f"'{it.name}': cost is 0 (free item).")
        if it.cost_growth <= 0:
            err("BAD_GROWTH", f"'{it.name}': cost_growth must be above 0.")
        elif it.cost_growth < 1:
            warn("CHEAPER_GROWTH", f"'{it.name}': cost_growth is below 1, so each copy gets cheaper.")
        if it.max < 1:
            err("BAD_MAX", f"'{it.name}': max must be at least 1.")
        if it.income < 0:
            err("NEG_INCOME", f"'{it.name}': income is negative.")
        if it.kind == "multiplier":
            if it.multiplier <= 0:
                err("BAD_MULT", f"'{it.name}': multiplier must be above 0.")
            elif it.multiplier == 1:
                warn("MULT_NOOP", f"'{it.name}': multiplier is 1, it changes nothing.")
            if it.income:
                warn("MULT_INCOME", f"'{it.name}': 'income' is ignored on a multiplier item.")
            if it.applies_to is not None and it.applies_to not in groups_used:
                warn("UNKNOWN_GROUP", f"'{it.name}': applies_to '{it.applies_to}' matches no income group.")
        else:
            if it.multiplier != 1:
                warn("INCOME_MULT", f"'{it.name}': 'multiplier' is ignored on an income item (use kind = \"multiplier\").")
        for req, count in it.requires:
            if req == it.name:
                err("SELF_REQ", f"'{it.name}' requires itself.")
            elif req not in by_name:
                err("UNKNOWN_REQ", f"'{it.name}' requires unknown item '{req}'.")
            else:
                if count < 1:
                    err("BAD_REQ_COUNT", f"'{it.name}': required count of '{req}' must be at least 1.")
                elif count > by_name[req].max:
                    err("REQ_TOO_HIGH", f"'{it.name}' needs {count} x '{req}' but only {by_name[req].max} can ever be bought.")

    # cycles de dépendances
    state: dict[str, int] = {}

    def visit(n: str, trail: list[str]) -> None:
        if state.get(n) == 2 or n not in by_name:
            return
        if state.get(n) == 1:
            cyc = trail[trail.index(n):] + [n]
            err("CYCLE", "Requirement loop: " + " -> ".join(cyc))
            return
        state[n] = 1
        for req, _ in by_name[n].requires:
            visit(req, trail + [n])
        state[n] = 2

    for n in names:
        visit(n, [])

    # le joueur peut-il gagner de l'argent ?
    earns = cfg.base_income > 0 or any(it.kind == "income" and it.income > 0 for it in cfg.items)
    if not earns:
        err("NO_INCOME", "No income at all: base_income is 0 and no item produces money.")
    elif cfg.base_income <= 0:
        free_start = [it for it in cfg.items if it.kind == "income" and it.income > 0
                      and not it.requires and it.cost <= cfg.start_cash]
        if not free_start:
            err("STUCK_START", "base_income is 0 and no income item is affordable at the start: the player is stuck.")

    for t in cfg.targets:
        if t.minutes <= 0:
            err("BAD_TARGET", f"Target '{t.item}': minutes must be above 0.")
        if t.tolerance < 0:
            err("BAD_TARGET", f"Target '{t.item}': tolerance cannot be negative.")
        if t.item != "*":
            target_item = by_name.get(t.item)
            if target_item is None:
                err("TARGET_UNKNOWN", f"Target refers to unknown item '{t.item}'.")
            elif t.count < 1 or t.count > target_item.max:
                err("TARGET_COUNT", f"Target '{t.item}': count must be between 1 and {target_item.max}.")
    return issues
