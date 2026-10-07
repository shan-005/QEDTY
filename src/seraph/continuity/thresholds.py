from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


def validate_threshold(value: float) -> float:
    if not 0 < value < 1:
        raise ValueError("threshold must be in (0,1)")
    return value


def time_to_threshold(points: tuple[tuple[datetime, float], ...], threshold: float) -> float | None:
    validate_threshold(threshold)
    if not points:
        return None
    start = points[0][0]
    for timestamp, capacity in points:
        if capacity >= threshold:
            return max(0.0, (timestamp - start).total_seconds() / 3600.0)
    return None
