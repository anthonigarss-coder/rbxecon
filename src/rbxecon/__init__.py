"""rbxecon : simule l'économie d'un tycoon Roblox et exporte les mêmes chiffres vers Luau."""

from .analysis import analyze
from .config import Config, ConfigError, load, parse, validate
from .engine import Result, simulate
from .strategies import STRATEGIES

__version__ = "0.1.0"
__all__ = [
    "STRATEGIES", "Config", "ConfigError", "Result", "analyze",
    "load", "parse", "simulate", "validate", "__version__",
]
