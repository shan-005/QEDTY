"""Seraph — Planetary Continuity Intelligence platform."""

try:
    from seraph._version import version as version
except ModuleNotFoundError as exc:
    if exc.name != "seraph._version":
        raise
    version = "0.3.0.dev0"

__version__ = version

__all__ = ["__version__"]
