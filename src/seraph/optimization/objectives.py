from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def efficiency(gain: float, cost_usd: float) -> float:
    if gain < 0 or cost_usd < 0 or not isfinite(gain) or not isfinite(cost_usd):
        raise ValueError("invalid objective inputs")
    return gain / (cost_usd / 1_000_000) if cost_usd else gain


def weighted_score(
    gain: float,
    cost_usd: float,
    risk: float = 0.0,
    *,
    gain_weight: float = 1.0,
    cost_weight: float = 1.0,
    risk_weight: float = 1.0,
) -> float:
    if any(
        x < 0 or not isfinite(x)
        for x in (gain, cost_usd, risk, gain_weight, cost_weight, risk_weight)
    ):
        raise ValueError("objective inputs must be finite and non-negative")
    return gain_weight * gain - cost_weight * (cost_usd / 1_000_000) - risk_weight * risk


def cvar(scores: Sequence[float], alpha: float = 0.9) -> float:
    if not scores:
        raise ValueError("scores empty")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0,1)")
    ordered = sorted(scores)
    # Lower-tail CVaR is the mean of the worst q fraction.
    k = max(1, int((1 - alpha) * len(ordered) + 0.999999))
    return sum(ordered[:k]) / k
