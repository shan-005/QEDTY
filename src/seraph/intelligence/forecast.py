from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class Forecast:
    estimate: float
    lower: float
    upper: float
    horizon: str
    method: str = "persistence"
    confidence: float = 0.5

    def __post_init__(self) -> None:
        if not all(isfinite(x) for x in (self.estimate, self.lower, self.upper, self.confidence)):
            raise ValueError("forecast values must be finite")
        if self.lower > self.estimate or self.estimate > self.upper:
            raise ValueError("forecast interval ordering invalid")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0,1]")


def persistence(value: float, uncertainty: float, horizon: str) -> Forecast:
    if uncertainty < 0 or not isfinite(value) or not isfinite(uncertainty):
        raise ValueError("invalid persistence inputs")
    return Forecast(value, max(0, value - uncertainty), value + uncertainty, horizon)


def holt_linear(
    values: Sequence[float], horizon: str, *, damp: float = 1.0, confidence: float = 0.8
) -> Forecast:
    """Damped Holt-style trend forecast with a robust residual scale.

    This is deliberately dependency-light.  It uses a deterministic level/trend
    recursion and MAD-derived uncertainty rather than pretending to estimate a
    fully specified stochastic state-space model.
    """
    if len(values) < 2 or any(not isfinite(v) for v in values):
        raise ValueError("at least two finite observations are required")
    if not 0 < damp <= 1 or not 0 < confidence <= 1:
        raise ValueError("invalid damp/confidence")
    alpha = 0.35
    beta = 0.20
    level = float(values[0])
    trend = float(values[1] - values[0])
    fitted: list[float] = [level]
    for obs in values[1:]:
        prev_level = level
        level = alpha * obs + (1 - alpha) * (level + damp * trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
        fitted.append(prev_level + damp * trend)
    residuals = [values[i] - fitted[i] for i in range(1, len(values))]
    center = mean(residuals) if residuals else 0.0
    mad = sorted(abs(r - center) for r in residuals)[len(residuals) // 2] if residuals else 0.0
    scale = max(1e-12, 1.4826 * mad)
    estimate = level + damp * trend
    # A conservative z proxy; exact Gaussian coverage is not claimed.
    z = 1.2815515655446004 if confidence <= 0.8 else 1.6448536269514722
    half = z * scale
    return Forecast(estimate, estimate - half, estimate + half, horizon, "holt_mad", confidence)
