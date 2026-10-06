from .models import BoundingBox, Point


def filter_points(points: dict[str, Point], bbox: BoundingBox, contains) -> tuple[str, ...]:
    return tuple(sorted(k for k, p in points.items() if contains(p, bbox)))
