from rbxecon import config


def make(items, *, start_cash=0, base_income=0, targets=(), round_costs=False, max_wait_minutes=3):
    """Construit une config à partir de dictionnaires d'items (même clés que le TOML)."""
    return config.parse({
        "economy": {"start_cash": start_cash, "base_income": base_income, "round_costs": round_costs},
        "analysis": {"max_wait_minutes": max_wait_minutes},
        "item": list(items),
        "target": list(targets),
    })
