from __future__ import annotations

from math import sqrt
from typing import TYPE_CHECKING

from .calibration import finite_sample_quantile
from .models import Interval, SampleSummary

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


def add(a: Interval, b: Interval) -> Interval:
    return Interval(
        lower=a.lower + b.lower,
        estimate=a.estimate + b.estimate,
        upper=a.upper + b.upper,
        confidence_level=min(a.confidence_level, b.confidence_level),
        method="interval-arithmetic:add",
    )


def multiply_nonnegative(a: Interval, b: Interval) -> Interval:
    if a.lower < 0 or b.lower < 0:
        raise ValueError("nonnegative multiplication requires nonnegative lower bounds")
    return Interval(
        lower=a.lower * b.lower,
        estimate=a.estimate * b.estimate,
        upper=a.upper * b.upper,
        confidence_level=min(a.confidence_level, b.confidence_level),
        method="interval-arithmetic:multiply",
    )


def monte_carlo(
    evaluator: Callable[[tuple[float, ...]], float],
    samples: Sequence[tuple[float, ...]],
    confidence_level: float = 0.9,
) -> SampleSummary:
    if not samples or not 0 < confidence_level < 1:
        raise ValueError("invalid Monte Carlo input")
    values = [float(evaluator(s)) for s in samples]
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / len(values)
    alpha = 1 - confidence_level
    lower = finite_sample_quantile(values, alpha / 2)
    upper = finite_sample_quantile(values, 1 - alpha / 2)
    med = finite_sample_quantile(values, 0.5)
    return SampleSummary(
        mean=mean,
        std=sqrt(var),
        lower=lower,
        median=med,
        upper=upper,
        quantile_level=confidence_level,
        method="empirical-Monte-Carlo-quantiles",
        n=len(values),
    )
