from seraph.core.geometry import haversine_km

from .models import Point


def distance_km(a: Point, b: Point) -> float:
    return haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)
