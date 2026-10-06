from collections.abc import Callable

from .models import BoundingBox, Point


def filter_points(
    points: dict[str, Point],
    bbox: BoundingBox,
    contains: Callable[[Point, BoundingBox], bool],
) -> tuple[str, ...]:
    return tuple(sorted(k for k, p in points.items() if contains(p, bbox)))
