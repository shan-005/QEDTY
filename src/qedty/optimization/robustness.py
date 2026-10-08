from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def robust_floor(scores: list[float]) -> float:
    if not scores:
        return 0.0
    return min(scores)


def cvar_score(scores: Sequence[float], alpha: float = 0.9) -> float:
    if not scores:
        return 0.0
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0,1)")
    ordered = sorted(float(s) for s in scores)
    k = max(1, int((1 - alpha) * len(ordered) + 0.999999))
    return sum(ordered[:k]) / k


def dominance_score(scores: Sequence[float]) -> float:
    """Minimum score relative to the scenario mean; 1 is uniformly stable."""
    if not scores:
        return 0.0
    ordered = [float(s) for s in scores]
    mean = sum(ordered) / len(ordered)
    if mean == 0:
        return 1.0
    return min(ordered) / mean
