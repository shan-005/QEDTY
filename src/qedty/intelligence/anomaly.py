from __future__ import annotations

from dataclasses import dataclass
from math import fabs, isfinite, sqrt
from statistics import median
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class AnomalyScore:
    """Deterministic anomaly assessment with an explicit method and threshold."""

    value: float
    score: float
    threshold: float
    anomalous: bool
    method: str

    def __post_init__(self) -> None:
        if not all(isfinite(x) for x in (self.value, self.score, self.threshold)):
            raise ValueError("anomaly values must be finite")
        if self.threshold < 0:
            raise ValueError("threshold must be non-negative")


def zscore(value: float, mean: float, std: float) -> float:
    if not all(isfinite(x) for x in (value, mean, std)) or std <= 0:
        raise ValueError("std must be finite and positive")
    return (value - mean) / std


def robust_zscore(value: float, center: float, mad: float, *, consistency: float = 1.4826) -> float:
    """Median/MAD standardized residual; stable against a minority of outliers."""
    if (
        not all(isfinite(x) for x in (value, center, mad, consistency))
        or mad <= 0
        or consistency <= 0
    ):
        raise ValueError("MAD and consistency must be finite and positive")
    return (value - center) / (consistency * mad)


def is_anomaly(value: float, mean: float, std: float, threshold: float = 3.0) -> bool:
    if threshold < 0:
        raise ValueError("threshold must be non-negative")
    return abs(zscore(value, mean, std)) >= threshold


def score(value: float, history: Sequence[float], *, threshold: float = 3.5) -> AnomalyScore:
    """Score a value against historical values using a robust MAD baseline.

    A zero MAD falls back to the sample standard deviation.  A constant history
    therefore produces a neutral score for an identical value and an explicit
    error for an incomparable non-identical value.
    """
    if not history:
        raise ValueError("history must not be empty")
    if any(not isfinite(x) for x in history) or not isfinite(value):
        raise ValueError("history and value must be finite")
    center = median(history)
    deviations = [abs(x - center) for x in history]
    mad = median(deviations)
    if mad > 0:
        s = fabs(robust_zscore(value, center, mad))
        method = "median_mad"
    else:
        n = len(history)
        variance = sum((x - center) ** 2 for x in history) / max(n, 1)
        std = sqrt(variance)
        if std > 0:
            s = fabs((value - center) / std)
            method = "mean_std_fallback"
        else:
            s = 0.0 if value == center else threshold
            method = "constant_baseline"
    return AnomalyScore(value, s, threshold, s >= threshold, method)


def ewma(values: Sequence[float], alpha: float = 0.2) -> tuple[float, ...]:
    if not values or any(not isfinite(x) for x in values):
        raise ValueError("values must be non-empty and finite")
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0, 1]")
    out: list[float] = [float(values[0])]
    for x in values[1:]:
        out.append(alpha * x + (1 - alpha) * out[-1])
    return tuple(out)


def cusum(
    values: Sequence[float], *, target: float = 0.0, drift: float = 0.0, threshold: float = 1.0
) -> tuple[int, ...]:
    """Two-sided CUSUM alarms; output is the deterministic alarm index sequence."""
    if not values or any(not isfinite(x) for x in values):
        raise ValueError("values must be non-empty and finite")
    if threshold <= 0 or drift < 0 or not isfinite(target):
        raise ValueError("invalid CUSUM parameters")
    pos = neg = 0.0
    alarms: list[int] = []
    for idx, value in enumerate(values):
        pos = max(0.0, pos + value - target - drift)
        neg = min(0.0, neg + value - target + drift)
        if pos >= threshold or -neg >= threshold:
            alarms.append(idx)
            pos = neg = 0.0
    return tuple(alarms)
