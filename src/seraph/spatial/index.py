from __future__ import annotations

from collections.abc import Callable

from .models import Point


def nearest(
    target: Point,
    candidates: dict[str, Point],
    distance_fn: Callable[[Point, Point], float],
) -> tuple[str, float] | None:
    if not candidates:
        return None
    return min(
        ((k, distance_fn(target, p)) for k, p in candidates.items()), key=lambda x: (x[1], x[0])
    )
