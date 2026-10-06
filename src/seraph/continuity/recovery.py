from __future__ import annotations

from datetime import datetime
from math import exp


def recovery_curve(
    initial: float, target: float, start: datetime, end: datetime, rate: float
) -> tuple[tuple[datetime, float], ...]:
    if end <= start or rate <= 0:
        raise ValueError("invalid recovery parameters")
    points = []
    total = (end - start).total_seconds()
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        t = start + (end - start) * frac
        x = frac * total
        value = target - (target - initial) * exp(-rate * x)
        points.append((t, value))
    return tuple(points)
