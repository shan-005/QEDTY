"""Bounded uncertainty aggregation operations used by QEDTY's reference layer."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

MAX_WEIGHTED_MEAN_ITEMS = 100_000


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    """Return a numerically scaled weighted mean under the shared v1 contract.

    Inputs must be equal-length, non-empty finite arrays; every weight is
    non-negative and at least one weight is positive. Scaling avoids overflowing
    ``value * weight`` when the mathematical mean remains representable.
    """
    if len(values) != len(weights) or not values:
        raise ValueError("weights must be non-empty and match the values array")
    if len(values) > MAX_WEIGHTED_MEAN_ITEMS:
        raise ValueError("weighted mean resource limit exceeded")
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float)) for value in values
    ) or any(
        isinstance(weight, bool) or not isinstance(weight, (int, float)) for weight in weights
    ):
        raise ValueError("values and weights must contain only numeric values")
    vals = tuple(float(value) for value in values)
    ws = tuple(float(weight) for weight in weights)
    if any(not math.isfinite(value) for value in vals) or any(
        not math.isfinite(weight) for weight in ws
    ):
        raise ValueError("values and weights must be finite")
    if any(weight < 0.0 for weight in ws):
        raise ValueError("weights must be non-negative")
    max_abs_value = max(abs(value) for value in vals)
    max_weight = max(ws)
    if max_weight == 0.0:
        raise ValueError("weights must have a positive sum")
    if max_abs_value == 0.0:
        return 0.0
    weighted_sum = 0.0
    total_weight = 0.0
    for value, weight in zip(vals, ws, strict=True):
        normalized_weight = weight / max_weight
        weighted_sum += (value / max_abs_value) * normalized_weight
        total_weight += normalized_weight
    if not math.isfinite(weighted_sum) or not math.isfinite(total_weight) or total_weight <= 0.0:
        raise ValueError("weighted mean intermediate result is invalid")
    normalized_mean = max(-1.0, min(1.0, weighted_sum / total_weight))
    result = max_abs_value * normalized_mean
    if not math.isfinite(result):
        raise ValueError("weighted mean result must be finite")
    return result
