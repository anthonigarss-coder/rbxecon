import csv
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from rbxecon import STRATEGIES, load, simulate
from rbxecon.cli import main
from rbxecon.luau import to_luau
from rbxecon.svg import income_chart

EXAMPLE = Path(__file__).parents[1] / "src" / "rbxecon" / "example.toml"


@pytest.fixture
def cfg_path(tmp_path):
    p = tmp_path / "economy.toml"
    p.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    return p


# ------------------------------------------------------------------- CLI
def test_init_writes_example_and_refuses_overwrite(tmp_path, capsys):
    dest = tmp_path / "mine.toml"
    assert main(["init", str(dest)]) == 0
    assert dest.read_text(encoding="utf-8") == EXAMPLE.read_text(encoding="utf-8")
    assert main(["init", str(dest)]) == 2
    assert main(["init", str(dest), "--force"]) == 0


def test_check_ok_and_failing(cfg_path, tmp_path, capsys):
    assert main(["check", str(cfg_path)]) == 0
    bad = tmp_path / "bad.toml"
    bad.write_text('[[item]]\nname = "A"\ncost = 1\nrequires = ["Ghost"]\n[economy]\nbase_income = 1\n')
    assert main(["check", str(bad)]) == 1
    assert "UNKNOWN_REQ" in capsys.readouterr().out


def test_sim_json_has_every_strategy(cfg_path, capsys):
    main(["sim", str(cfg_path), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert [d["strategy"] for d in data] == list(STRATEGIES)
    assert all(d["status"] == "finished" and d["timeline"] for d in data)


def test_sim_exit_code_follows_targets(cfg_path, tmp_path, capsys):
    # l'exemple contient des objectifs que certaines stratégies ratent
    assert main(["sim", str(cfg_path), "-s", "roi"]) == 1
    easy = tmp_path / "easy.toml"
    easy.write_text('[economy]\nbase_income = 1\n[[item]]\nname = "A"\ncost = 60\n[[target]]\nitem = "A"\nminutes = 1\n')
    assert main(["sim", str(easy)]) == 0


def test_sim_text_report_content(cfg_path, capsys):
    main(["sim", str(cfg_path), "-s", "order", "--timeline", "3"])
    out = capsys.readouterr().out
    assert "Strategy: order" in out and "Dead zones" in out and "Targets:" in out
    assert "First 3 purchases" in out


def test_sim_refuses_invalid_config(tmp_path, capsys):
    bad = tmp_path / "bad.toml"
    bad.write_text('[[item]]\nname = "A"\ncost = 5\nincome = 1\n')  # joueur bloqué : aucun revenu au départ
    assert main(["sim", str(bad)]) == 2
    assert "STUCK_START" in capsys.readouterr().err


def test_bad_inputs(tmp_path, capsys):
    assert main(["sim", str(tmp_path / "nope.toml")]) == 2
    broken = tmp_path / "broken.toml"
    broken.write_text("[[item")
    assert main(["check", str(broken)]) == 2


def test_csv_and_svg_outputs(cfg_path, tmp_path):
    csv_path, svg_path = tmp_path / "t.csv", tmp_path / "c.svg"
    main(["sim", str(cfg_path), "--csv", str(csv_path), "--svg", str(svg_path)])
    rows = list(csv.reader(io.StringIO(csv_path.read_text())))
    assert rows[0] == ["strategy", "time_seconds", "item", "number", "cost", "wait_seconds", "income_after"]
    assert len(rows) == 1 + 3 * 34
    root = ET.fromstring(svg_path.read_text())
    assert root.tag.endswith("svg")


def test_max_hours_stops_the_run(cfg_path, capsys):
    main(["sim", str(cfg_path), "-s", "order", "--max-hours", "0.05", "--json"])
    (d,) = json.loads(capsys.readouterr().out)
    assert d["status"] == "timeout" and d["never_bought"]


# ------------------------------------------------------------------ SVG
def test_svg_is_valid_and_escapes_titles():
    cfg = load(EXAMPLE)
    results = [simulate(cfg, s) for s in STRATEGIES.values()]
    svg = income_chart(results, title='A & B <test>')
    root = ET.fromstring(svg)
    paths = [e for e in root.iter() if e.tag.endswith("path")]
    assert len(paths) == 3
    assert "A &amp; B &lt;test&gt;" in svg


def test_svg_handles_empty_result():
    cfg = load(EXAMPLE)
    res = simulate(cfg, STRATEGIES["order"], max_hours=0)
    ET.fromstring(income_chart([res]))


# ----------------------------------------------------------------- Luau
def test_luau_module_content():
    code = to_luau(load(EXAMPLE))
    assert code.startswith("--!strict")
    assert "Economy.StartCash = 100" in code
    assert "Economy.BaseIncome = 2" in code
    assert "Economy.RoundCosts = true" in code
    assert '["Dumbbell Rack"] = {' in code
    assert 'requires = { { item = "Dumbbell Rack", count = 1 } }' in code
    assert 'appliesTo' in code and code.rstrip().endswith("return Economy")
    assert "function Economy.getCost(" in code and "function Economy.incomePerSecond(" in code
    assert code.count("{") == code.count("}")  # accolades équilibrées


def test_luau_order_matches_file_order():
    cfg = load(EXAMPLE)
    code = to_luau(cfg)
    expected = ", ".join(f'"{it.name}"' for it in cfg.items)
    assert f"Economy.Order = {{ {expected} }}" in code


def test_luau_escapes_names():
    from rbxecon import parse

    cfg = parse({"economy": {"base_income": 1}, "item": [{"name": 'Say "hi"\\now', "cost": 1}]})
    code = to_luau(cfg)
    assert '"Say \\"hi\\"\\\\now"' in code


def test_luau_cli_output_file(cfg_path, tmp_path):
    out = tmp_path / "Economy.luau"
    assert main(["luau", str(cfg_path), "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("--!strict")


def test_luau_cli_prints_when_no_output(cfg_path, capsys):
    assert main(["luau", str(cfg_path)]) == 0
    assert "return Economy" in capsys.readouterr().out


def test_luau_refuses_invalid_config(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text('[[item]]\nname = "A"\ncost = 5\nincome = 1\n')
    assert main(["luau", str(bad)]) == 2
