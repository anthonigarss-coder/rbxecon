import pytest

from helpers import make
from rbxecon import ConfigError, load, parse, validate
from pathlib import Path

EXAMPLE = Path(__file__).parents[1] / "src" / "rbxecon" / "example.toml"


def codes(cfg):
    return {i.code for i in validate(cfg)}


def errors(cfg):
    return {i.code for i in validate(cfg) if i.level == "error"}


def test_example_is_valid_and_complete():
    cfg = load(EXAMPLE)
    assert not [i for i in validate(cfg) if i.level == "error"]
    assert len(cfg.items) == 9 and len(cfg.targets) == 3
    assert cfg.item("Bench").requires == (("Dumbbell Rack", 1),)
    assert cfg.item("Marketing Campaign").kind == "multiplier"


def test_requires_accepts_plain_names():
    cfg = parse({"item": [{"name": "A", "cost": 1}, {"name": "B", "cost": 1, "requires": ["A"]}]})
    assert cfg.item("B").requires == (("A", 1),)


@pytest.mark.parametrize("data,fragment", [
    ({}, "at least one"),
    ({"item": [{"cost": 1}]}, "name"),
    ({"item": [{"name": "A"}]}, "cost"),
    ({"item": [{"name": "A", "cost": "10"}]}, "number"),
    ({"item": [{"name": "A", "cost": 1, "kind": "bonus"}]}, "kind"),
    ({"item": [{"name": "A", "cost": 1, "max": 1.5}]}, "whole number"),
    ({"item": [{"name": "A", "cost": 1, "requires": [3]}]}, "requires"),
    ({"item": [{"name": "A", "cost": 1}], "target": [{"item": "A"}]}, "minutes"),
])
def test_parse_errors_are_readable(data, fragment):
    with pytest.raises(ConfigError, match=fragment):
        parse(data)


def test_load_errors(tmp_path):
    with pytest.raises(ConfigError, match="Cannot read"):
        load(tmp_path / "missing.toml")
    bad = tmp_path / "bad.toml"
    bad.write_text("[[item]\nname = ")
    with pytest.raises(ConfigError, match="Invalid TOML"):
        load(bad)


def test_validation_rules():
    ok = {"name": "A", "cost": 1, "income": 1}
    assert errors(make([ok, ok], base_income=1)) == {"DUP_ITEM"}
    assert "UNKNOWN_REQ" in errors(make([dict(ok, requires=["Nope"])], base_income=1))
    assert "SELF_REQ" in errors(make([dict(ok, requires=["A"])], base_income=1))
    assert "REQ_TOO_HIGH" in errors(make([ok, {"name": "B", "cost": 1, "requires": [{"item": "A", "count": 2}]}], base_income=1))
    assert "BAD_MAX" in errors(make([dict(ok, max=0)], base_income=1))
    assert "BAD_COST" in errors(make([dict(ok, cost=-1)], base_income=1))
    assert "NEG_INCOME" in errors(make([dict(ok, income=-1)], base_income=1))
    assert "BAD_GROWTH" in errors(make([dict(ok, cost_growth=0)], base_income=1))
    assert "BAD_NAME" in errors(make([dict(ok, name="*")], base_income=1))


def test_cycle_detected():
    cfg = make([
        {"name": "A", "cost": 1, "income": 1, "requires": ["B"]},
        {"name": "B", "cost": 1, "income": 1, "requires": ["A"]},
    ], base_income=1)
    assert "CYCLE" in errors(cfg)


def test_player_must_be_able_to_earn():
    assert "NO_INCOME" in errors(make([{"name": "A", "cost": 1}]))
    assert "STUCK_START" in errors(make([{"name": "A", "cost": 50, "income": 1}], start_cash=10))
    assert not errors(make([{"name": "A", "cost": 5, "income": 1}], start_cash=10))


def test_warnings():
    cfg = make([
        {"name": "A", "cost": 0, "income": 1, "cost_growth": 0.9},
        {"name": "M", "cost": 1, "kind": "multiplier", "multiplier": 1, "applies_to": "ghost"},
    ], base_income=1)
    assert {"ZERO_COST", "CHEAPER_GROWTH", "MULT_NOOP", "UNKNOWN_GROUP"} <= codes(cfg)


def test_target_validation():
    items = [{"name": "A", "cost": 1, "income": 1, "max": 2}]
    assert "TARGET_UNKNOWN" in errors(make(items, base_income=1, targets=[{"item": "Z", "minutes": 1}]))
    assert "TARGET_COUNT" in errors(make(items, base_income=1, targets=[{"item": "A", "count": 3, "minutes": 1}]))
    assert "BAD_TARGET" in errors(make(items, base_income=1, targets=[{"item": "A", "minutes": 0}]))
    assert not errors(make(items, base_income=1, targets=[{"item": "*", "minutes": 1}]))
