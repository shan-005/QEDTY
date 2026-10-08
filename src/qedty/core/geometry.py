from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, isfinite, radians, sin, sqrt
from typing import Final

from .enums import CoordinateReferenceSystem
from .errors import GeometryError

WGS84_A_M: Final[float] = 6_378_137.0
WGS84_INV_F: Final[float] = 298.257223563
WGS84_F: Final[float] = 1.0 / WGS84_INV_F
WGS84_B_M: Final[float] = WGS84_A_M * (1.0 - WGS84_F)
MEAN_EARTH_RADIUS_KM: Final[float] = 6371.0088


@dataclass(frozen=True, slots=True)
class GeodeticPoint:
    latitude: float
    longitude: float
    height_m: float = 0.0

    def __post_init__(self) -> None:
        validate_latitude(self.latitude)
        validate_longitude(self.longitude)
        if not isfinite(self.height_m):
            raise GeometryError("height must be finite")

    @property
    def crs(self) -> CoordinateReferenceSystem:
        return CoordinateReferenceSystem.WGS84_3D


@dataclass(frozen=True, slots=True)
class GeodesicResult:
    distance_m: float
    forward_azimuth_deg: float
    reverse_azimuth_deg: float
    backend: str
    crs: str = CoordinateReferenceSystem.WGS84_2D.value

    @property
    def distance_km(self) -> float:
        return self.distance_m / 1000.0


def validate_latitude(latitude: float) -> float:
    if not isfinite(latitude) or not -90.0 <= latitude <= 90.0:
        raise GeometryError(f"latitude out of range: {latitude!r}")
    return latitude


def validate_longitude(longitude: float) -> float:
    if not isfinite(longitude) or not -180.0 <= longitude <= 180.0:
        raise GeometryError(f"longitude out of range: {longitude!r}")
    return longitude


def normalize_longitude(longitude: float) -> float:
    """Normalize longitude into the canonical interval [-180, 180)."""
    validate_longitude(longitude)
    normalized = ((longitude + 180.0) % 360.0) - 180.0
    if normalized == -0.0:
        return 0.0
    return normalized


def central_angle_rad(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    validate_latitude(lat1)
    validate_latitude(lat2)
    validate_longitude(lon1)
    validate_longitude(lon2)
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2.0) ** 2
    return 2.0 * atan2(sqrt(a), sqrt(max(0.0, 1.0 - a)))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Spherical great-circle approximation using the standard mean Earth radius."""
    return MEAN_EARTH_RADIUS_KM * central_angle_rad(lat1, lon1, lat2, lon2)


def chord_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line chord distance through a sphere, not surface distance."""
    angle = central_angle_rad(lat1, lon1, lat2, lon2)
    return 2.0 * MEAN_EARTH_RADIUS_KM * sin(angle / 2.0)


def geodetic_to_ecef(point: GeodeticPoint) -> tuple[float, float, float]:
    """Convert WGS-84 geodetic latitude/longitude/height to ECEF metres."""
    lat = radians(point.latitude)
    lon = radians(point.longitude)
    sin_lat = sin(lat)
    cos_lat = cos(lat)
    n = WGS84_A_M / sqrt(1.0 - (2.0 * WGS84_F - WGS84_F**2) * sin_lat**2)
    x = (n + point.height_m) * cos_lat * cos(lon)
    y = (n + point.height_m) * cos_lat * sin(lon)
    z = ((1.0 - WGS84_F) ** 2 * n + point.height_m) * sin_lat
    return x, y, z


def ecef_to_geodetic(
    x_m: float, y_m: float, z_m: float, *, tolerance_m: float = 1e-8
) -> GeodeticPoint:
    """Convert WGS-84 ECEF metres to geodetic coordinates.

    This is a robust iterative Bowring-style solution for ordinary operational
    use. High-precision geodetic production workflows should use a tested
    geodesy library such as PROJ/GeographicLib and retain its metadata.
    """
    for value in (x_m, y_m, z_m, tolerance_m):
        if not isfinite(value):
            raise GeometryError("ECEF coordinates and tolerance must be finite")
    if tolerance_m <= 0:
        raise GeometryError("tolerance_m must be positive")
    p = sqrt(x_m * x_m + y_m * y_m)
    if p == 0.0 and z_m == 0.0:
        raise GeometryError("ECEF origin has no unique geodetic coordinate")
    e2 = 2.0 * WGS84_F - WGS84_F**2
    lon = atan2(y_m, x_m)
    lat = (
        atan2(z_m, p * (1.0 - e2))
        if p
        else (3.141592653589793 / 2.0 if z_m > 0 else -3.141592653589793 / 2.0)
    )
    height = 0.0
    for _ in range(20):
        sin_lat = sin(lat)
        n = WGS84_A_M / sqrt(1.0 - e2 * sin_lat**2)
        height = abs(z_m) - WGS84_B_M if abs(cos(lat)) < 1e-15 else p / cos(lat) - n
        new_lat = atan2(z_m, p * (1.0 - e2 * n / (n + height))) if p else lat
        if abs(new_lat - lat) * WGS84_A_M < tolerance_m:
            lat = new_lat
            break
        lat = new_lat
    return GeodeticPoint(degrees(lat), degrees(lon), height)


def geodesic_inverse(first: GeodeticPoint, second: GeodeticPoint) -> GeodesicResult:
    """Solve the WGS-84 inverse geodesic problem using PROJ when installed."""
    try:
        from pyproj import Geod
    except ImportError as exc:
        raise GeometryError(
            "high-accuracy ellipsoidal geodesics require the optional 'pyproj' extra"
        ) from exc
    geod = Geod(ellps="WGS84")
    forward_azimuth, reverse_azimuth, distance_m = geod.inv(
        first.longitude,
        first.latitude,
        second.longitude,
        second.latitude,
    )
    return GeodesicResult(
        distance_m=float(distance_m),
        forward_azimuth_deg=float(forward_azimuth),
        reverse_azimuth_deg=float(reverse_azimuth),
        backend="PROJ/WGS84",
    )


def geodesic_distance_km(first: GeodeticPoint, second: GeodeticPoint) -> float:
    """Return ellipsoidal WGS-84 surface distance in kilometres."""
    return geodesic_inverse(first, second).distance_km


def destination(point: GeodeticPoint, azimuth_deg: float, distance_m: float) -> GeodeticPoint:
    """Solve the WGS-84 direct geodesic problem via PROJ."""
    if not isfinite(azimuth_deg) or not isfinite(distance_m):
        raise GeometryError("azimuth and distance must be finite")
    if distance_m < 0:
        raise GeometryError("distance_m must be non-negative")
    try:
        from pyproj import Geod
    except ImportError as exc:
        raise GeometryError(
            "high-accuracy ellipsoidal geodesics require the optional 'pyproj' extra"
        ) from exc
    lon, lat, _ = Geod(ellps="WGS84").fwd(point.longitude, point.latitude, azimuth_deg, distance_m)
    return GeodeticPoint(float(lat), float(lon), point.height_m)
