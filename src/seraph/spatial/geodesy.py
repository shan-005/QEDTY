"""Ellipsoidal geodesy for SERAPH-PCI-X.

WGS 84 geodesic work delegates to PROJ/GeographicLib through pyproj when
available.  The fallback is a spherical haversine implementation for local,
non-authoritative use; callers needing ellipsoidal accuracy should keep pyproj
installed.
"""

from __future__ import annotations

import itertools
from math import atan2, cos, degrees, radians, sin, sqrt
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from seraph.core.geometry import haversine_km

from .models import Point

if TYPE_CHECKING:
    from collections.abc import Iterable

WGS84_A_M = 6378137.0
WGS84_INV_F = 298.257223563


class GeodesicInverse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    distance_m: float
    initial_azimuth_deg: float
    final_azimuth_deg: float

    @property
    def distance_km(self) -> float:
        return self.distance_m / 1000.0


class GeodesicDirect(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    point: Point
    final_azimuth_deg: float


def normalize_azimuth(azimuth_deg: float) -> float:
    normalized = (azimuth_deg + 180.0) % 360.0 - 180.0
    if normalized == -180.0 and azimuth_deg > 0:
        return 180.0
    return normalized


def inverse(a: Point, b: Point, *, ellipsoid: str = "WGS84") -> GeodesicInverse:
    geod = _geod(ellipsoid)
    if geod is not None:
        az1, az2, distance = geod.inv(a.longitude, a.latitude, b.longitude, b.latitude)
        return GeodesicInverse(
            distance_m=float(distance),
            initial_azimuth_deg=normalize_azimuth(float(az1)),
            final_azimuth_deg=normalize_azimuth(float(az2)),
        )
    return _spherical_inverse(a, b)


def distance_m(a: Point, b: Point, *, ellipsoid: str = "WGS84") -> float:
    return inverse(a, b, ellipsoid=ellipsoid).distance_m


def distance_km(a: Point, b: Point) -> float:
    """Backward-compatible distance helper using WGS 84 geodesic distance."""

    return distance_m(a, b) / 1000.0


def bearing_deg(a: Point, b: Point) -> float:
    return inverse(a, b).initial_azimuth_deg


def direct(
    start: Point,
    azimuth_deg: float,
    distance_meters: float,
    *,
    ellipsoid: str = "WGS84",
) -> GeodesicDirect:
    if distance_meters < 0:
        raise ValueError("distance_meters must be non-negative")
    geod = _geod(ellipsoid)
    if geod is not None:
        lon, lat, az2 = geod.fwd(start.longitude, start.latitude, azimuth_deg, distance_meters)
        return GeodesicDirect(
            point=Point(latitude=float(lat), longitude=float(lon), height_m=start.height_m),
            final_azimuth_deg=normalize_azimuth(float(az2)),
        )
    return _spherical_direct(start, azimuth_deg, distance_meters)


def destination(start: Point, bearing: float, distance_meters: float) -> Point:
    return direct(start, bearing, distance_meters).point


def midpoint(a: Point, b: Point) -> Point:
    result = inverse(a, b)
    return destination(a, result.initial_azimuth_deg, result.distance_m / 2.0)


def interpolate(a: Point, b: Point, fraction: float) -> Point:
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between 0 and 1")
    if fraction == 0.0:
        return a
    if fraction == 1.0:
        return b
    result = inverse(a, b)
    return destination(a, result.initial_azimuth_deg, result.distance_m * fraction)


def polyline_length_m(points: Iterable[Point]) -> float:
    items = tuple(points)
    if len(items) < 2:
        return 0.0
    return sum(distance_m(a, b) for a, b in itertools.pairwise(items))


def polygon_area_perimeter_m2_m(points: Iterable[Point]) -> tuple[float, float]:
    """Return signed geodesic area (m²) and perimeter (m) for a closed ring."""

    items = tuple(points)
    if len(items) < 4 or items[0] != items[-1]:
        raise ValueError("polygon ring must be closed and contain at least four points")
    geod = _geod("WGS84")
    if geod is None:  # pragma: no cover
        raise RuntimeError("pyproj is required for authoritative polygon geodesic area")
    lons = [point.longitude for point in items]
    lats = [point.latitude for point in items]
    area_m2, perimeter_m = geod.polygon_area_perimeter(lons, lats)
    return float(area_m2), float(perimeter_m)


def polygon_area_m2(outer: Iterable[Point], holes: Iterable[Iterable[Point]] = ()) -> float:
    """Return absolute geodesic area of an outer ring minus hole areas."""
    outer_area, _ = polygon_area_perimeter_m2_m(outer)
    area = abs(outer_area)
    for hole in holes:
        hole_area, _ = polygon_area_perimeter_m2_m(hole)
        area -= abs(hole_area)
    if area < 0:
        raise ValueError("hole area exceeds outer polygon area")
    return float(area)


def _geod(ellipsoid: str) -> Any | None:
    try:
        from pyproj import Geod
    except ImportError:
        return None
    return Geod(ellps=ellipsoid)


def _spherical_inverse(a: Point, b: Point) -> GeodesicInverse:
    distance = haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) * 1000.0
    phi1, phi2 = radians(a.latitude), radians(b.latitude)
    dl = radians(b.longitude - a.longitude)
    y = sin(dl) * cos(phi2)
    x = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dl)
    az1 = degrees(atan2(y, x))
    reverse_y = sin(-dl) * cos(phi1)
    reverse_x = cos(phi2) * sin(phi1) - sin(phi2) * cos(phi1) * cos(-dl)
    reverse_azimuth = degrees(atan2(reverse_y, reverse_x))
    return GeodesicInverse(
        distance_m=distance,
        initial_azimuth_deg=normalize_azimuth(az1),
        final_azimuth_deg=normalize_azimuth(reverse_azimuth + 180.0),
    )


def _spherical_direct(start: Point, azimuth_deg: float, distance_meters: float) -> GeodesicDirect:
    radius = 6371008.8
    delta = distance_meters / radius
    phi1 = radians(start.latitude)
    lam1 = radians(start.longitude)
    theta = radians(azimuth_deg)

    sin_phi2 = sin(phi1) * cos(delta) + cos(phi1) * sin(delta) * cos(theta)
    sin_phi2 = max(-1.0, min(1.0, sin_phi2))
    phi2 = atan2(sin_phi2, sqrt(max(0.0, 1.0 - sin_phi2 * sin_phi2)))
    lam2 = lam1 + atan2(
        sin(theta) * sin(delta) * cos(phi1),
        cos(delta) - sin(phi1) * sin(phi2),
    )
    lon = degrees(lam2)
    lat = degrees(phi2)
    return GeodesicDirect(
        point=Point(
            latitude=lat,
            longitude=((lon + 180.0) % 360.0) - 180.0,
            height_m=start.height_m,
        ),
        final_azimuth_deg=normalize_azimuth(azimuth_deg),
    )
