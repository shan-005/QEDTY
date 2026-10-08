from __future__ import annotations

from math import exp
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


def _check(start: datetime, end: datetime) -> None:
    if end <= start:
        raise ValueError("end must be after start")
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("recovery datetimes must be timezone-aware")


def linear_recovery(
    initial: float,
    target: float,
    start: datetime,
    end: datetime,
    *,
    steps: int = 8,
) -> tuple[tuple[datetime, float], ...]:
    if not 0 <= initial <= 1 or not 0 <= target <= 1 or steps < 1:
        raise ValueError("invalid recovery parameters")
    _check(start, end)
    return tuple(
        (start + (end - start) * (i / steps), initial + (target - initial) * (i / steps))
        for i in range(steps + 1)
    )


def exponential_recovery(
    initial: float,
    target: float,
    start: datetime,
    end: datetime,
    rate: float,
    *,
    steps: int = 8,
) -> tuple[tuple[datetime, float], ...]:
    if not 0 <= initial <= 1 or not 0 <= target <= 1 or rate <= 0 or steps < 1:
        raise ValueError("invalid recovery parameters")
    _check(start, end)
    total_seconds = (end - start).total_seconds()
    return tuple(
        (
            start + (end - start) * (i / steps),
            target - (target - initial) * exp(-rate * (i / steps) * total_seconds),
        )
        for i in range(steps + 1)
    )


def recovery_curve(
    initial: float,
    target: float,
    start: datetime,
    end: datetime,
    rate: float,
) -> tuple[tuple[datetime, float], ...]:
    """Backward-compatible exponential recovery helper."""
    return exponential_recovery(initial, target, start, end, rate, steps=4)


def append_hold(
    points: tuple[tuple[datetime, float], ...], end: datetime
) -> tuple[tuple[datetime, float], ...]:
    if not points:
        raise ValueError("points required")
    t, value = points[-1]
    if end < t:
        raise ValueError("end precedes final point")
    return (*points, (end, value)) if end != t else points
