from __future__ import annotations

import math

from .models import Interval


def finite_sample_quantile(values: list[float], alpha: float) -> float:
    if not values or not 0 < alpha < 1:
        raise ValueError("invalid calibration input")
    ordered = sorted(values)
    rank = max(1, min(len(ordered), math.ceil((len(ordered) + 1) * (1 - alpha))))
    return ordered[rank - 1]


def split_conformal_interval(
    predictions: list[float], observations: list[float], confidence_level: float = 0.9
) -> Interval:
    if len(predictions) != len(observations) or not predictions:
        raise ValueError("predictions and observations must have equal nonzero length")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be in (0,1)")
    residuals = [abs(y - yhat) for y, yhat in zip(observations, predictions, strict=True)]
    q = finite_sample_quantile(residuals, 1 - confidence_level)
    estimate = sum(predictions) / len(predictions)
    return Interval(
        lower=estimate - q,
        estimate=estimate,
        upper=estimate + q,
        confidence_level=confidence_level,
        method="split-conformal:finite-sample",
    )


def empirical_coverage(intervals: list[Interval], observations: list[float]) -> float:
    if len(intervals) != len(observations) or not intervals:
        raise ValueError("intervals and observations must have equal nonzero length")
    return sum(i.lower <= y <= i.upper for i, y in zip(intervals, observations, strict=True)) / len(
        intervals
    )
