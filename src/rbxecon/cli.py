"""Ligne de commande : rbxecon init | check | sim | luau."""

from __future__ import annotations

import argparse
import sys
from importlib import resources
from pathlib import Path

from . import __version__
from .analysis import analyze
from .config import ConfigError, load, validate
from .engine import simulate
from .luau import to_luau
from .report import render_csv, render_json, render_text
from .strategies import STRATEGIES
from .svg import income_chart


def _write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def cmd_init(args) -> int:
    dest = Path(args.path)
    if dest.exists() and not args.force:
        print(f"rbxecon: '{dest}' already exists (use --force to overwrite).", file=sys.stderr)
        return 2
    text = resources.files("rbxecon").joinpath("example.toml").read_text(encoding="utf-8")
    _write(str(dest), text)
    print(f"Wrote {dest}. Edit it, then run: rbxecon sim {dest}")
    return 0


def _load_checked(path: str):
    cfg = load(path)
    issues = validate(cfg)
    errors = [i for i in issues if i.level == "error"]
    return cfg, issues, errors


def cmd_check(args) -> int:
    cfg, issues, errors = _load_checked(args.config)
    for i in issues:
        print(f"{i.level.upper():<8} {i.code:<16} {i.message}")
    print(f"\n{len(cfg.items)} item(s), {len(cfg.targets)} target(s): "
          f"{len(errors)} error(s), {len(issues) - len(errors)} warning(s).")
    return 1 if errors else 0


def cmd_sim(args) -> int:
    cfg, issues, errors = _load_checked(args.config)
    if errors:
        for i in errors:
            print(f"ERROR    {i.code:<16} {i.message}", file=sys.stderr)
        print("rbxecon: fix the errors above first (see `rbxecon check`).", file=sys.stderr)
        return 2

    names = list(STRATEGIES) if args.strategy == "all" else [args.strategy]
    runs = []
    for n in names:
        res = simulate(cfg, STRATEGIES[n], max_hours=args.max_hours)
        runs.append((res, analyze(cfg, res)))

    if args.json:
        print(render_json(cfg, runs))
    else:
        for w in (i for i in issues if i.level == "warning"):
            print(f"warning: {w.message}")
        for res, an in runs:
            print(render_text(cfg, res, an, timeline=args.timeline))
            print()
    if args.csv:
        _write(args.csv, render_csv([r for r, _ in runs]))
    if args.svg:
        _write(args.svg, income_chart([r for r, _ in runs], title=f"Income over time ({cfg.source or 'config'})"))

    missed = any(not t.ok for _, an in runs for t in an.targets)
    return 1 if missed else 0


def cmd_luau(args) -> int:
    cfg, issues, errors = _load_checked(args.config)
    if errors:
        for i in errors:
            print(f"ERROR    {i.code:<16} {i.message}", file=sys.stderr)
        return 2
    code = to_luau(cfg)
    if args.output:
        _write(args.output, code)
        print(f"Wrote {args.output}")
    else:
        sys.stdout.write(code)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rbxecon",
        description="Simulate the economy of a Roblox tycoon and export the same numbers to Luau.",
    )
    p.add_argument("-V", "--version", action="version", version=f"rbxecon {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="write an example config file")
    s.add_argument("path", nargs="?", default="economy.toml")
    s.add_argument("--force", action="store_true", help="overwrite an existing file")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("check", help="validate a config file")
    s.add_argument("config")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser(
        "sim", help="simulate a playthrough",
        description="Simulate a playthrough. Exit code 1 if a pacing target is missed, 2 on bad input.",
    )
    s.add_argument("config")
    s.add_argument("-s", "--strategy", choices=["all", *STRATEGIES], default="all",
                   help="how the simulated player behaves (default: all) - "
                        + "; ".join(f"{k}: {v.description}" for k, v in STRATEGIES.items()))
    s.add_argument("--max-hours", type=float, default=24.0, help="stop after this much play time (default 24)")
    s.add_argument("--timeline", type=int, default=0, metavar="N", help="also print the first N purchases")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.add_argument("--csv", metavar="FILE", help="write every purchase to a CSV file")
    s.add_argument("--svg", metavar="FILE", help="write an income-over-time chart (SVG)")
    s.set_defaults(func=cmd_sim)

    s = sub.add_parser("luau", help="export the config as a Luau module")
    s.add_argument("config")
    s.add_argument("-o", "--output", metavar="FILE", help="write to a file instead of the screen")
    s.set_defaults(func=cmd_luau)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as e:
        print(f"rbxecon: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
