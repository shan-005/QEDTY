from __future__ import annotations

from .models import Point


def nearest(target: Point, candidates: dict[str, Point], distance_fn) -> tuple[str, float] | None:
    if not candidates:
        return None
    return min(
        ((k, distance_fn(target, p)) for k, p in candidates.items()), key=lambda x: (x[1], x[0])
    )
