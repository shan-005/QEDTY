from __future__ import annotations


def one_at_a_time(base: float, changes: dict[str, float]) -> dict[str, float]:
    return {k: v - base for k, v in changes.items()}
