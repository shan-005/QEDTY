from seraph.core.geometry import haversine_km
from seraph.spatial.models import Point


def spatial_distance(a: Point, b: Point) -> float:
    return haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)
