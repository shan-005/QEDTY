"""Coordinate-reference-system semantics and transformations.

PROJ/pyproj is used as the reference geodetic transformation engine.  The
module keeps the dependency optional at import time so lightweight SERAPH
installations can still use models and pure-Python longitude/latitude logic.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .models import BoundingBox, CoordinatePoint, Geometry, Point

DEFAULT_CRS = "EPSG:4326"
CRS84 = "http://www.opengis.net/def/crs/OGC/0/CRS84"
CRS84H = "http://www.opengis.net/def/crs/OGC/0/CRS84h"
GREGORIAN_DATETIME_CRS = "http://www.opengis.net/def/crs/OGC/0/GregorianDateTime"


def validate_crs(crs: str) -> str:
    """Normalize and structurally validate a CRS identifier.

    Supported forms include ``EPSG:4326``, ``OGC:CRS84``, URIs and WKT/PROJ
    strings accepted by pyproj.  The result preserves WKT/PROJ content while
    normalizing authority/code identifiers.
    """

    if not isinstance(crs, str):
        raise TypeError("CRS must be a string")
    value = crs.strip()
    if not value:
        raise ValueError("CRS must not be empty")
    if ":" in value and value.upper().split(":", 1)[0] in {
        "EPSG", "OGC", "ESRI", "IAU"
    }:
        authority, code = value.split(":", 1)
        if not code.strip():
            raise ValueError("CRS code must not be empty")
        return f"{authority.upper()}:{code.strip()}"
    if value.startswith(("http://", "https://")):
        return value
    return value


@dataclass(frozen=True, slots=True)
class CRSInfo:
    """Immutable normalized CRS metadata."""

    identifier: str
    name: str | None
    is_geographic: bool
    is_projected: bool
    axis_order: tuple[str, ...]
    units: tuple[str, ...]
    area_of_use: tuple[float, float, float, float] | None
    dynamic: bool


def describe_crs(crs: str = DEFAULT_CRS) -> CRSInfo:
    normalized = validate_crs(crs)
    obj = _pyproj_crs(normalized)
    axis_order = tuple(axis.abbrev or axis.name for axis in obj.axis_info)
    units = tuple(axis.unit_name for axis in obj.axis_info if axis.unit_name)
    bounds = None
    if obj.area_of_use is not None:
        bounds = (
            obj.area_of_use.west,
            obj.area_of_use.south,
            obj.area_of_use.east,
            obj.area_of_use.north,
        )
    dynamic = _contains_dynamic_marker(obj.to_json_dict())
    return CRSInfo(
        identifier=normalized,
        name=obj.name,
        is_geographic=obj.is_geographic,
        is_projected=obj.is_projected,
        axis_order=axis_order,
        units=units,
        area_of_use=bounds,
        dynamic=dynamic,
    )


def crs_uri(crs: str = DEFAULT_CRS) -> str:
    """Return an OGC-style CRS URI when an authority/code is available."""

    normalized = validate_crs(crs)
    if normalized.upper() == "EPSG:4326":
        return CRS84
    if normalized.upper() == "EPSG:4979":
        return CRS84H
    if ":" in normalized and normalized.split(":", 1)[0].upper() in {
        "EPSG", "OGC", "ESRI", "IAU"
    }:
        authority, code = normalized.split(":", 1)
        return f"http://www.opengis.net/def/crs/{authority.upper()}/0/{code}"
    if normalized.startswith(("http://", "https://")):
        return normalized
    return normalized


def transform_point(
    point: Point,
    target_crs: str,
    *,
    source_crs: str = DEFAULT_CRS,
    area_of_interest: BoundingBox | None = None,
    allow_ballpark: bool = False,
    only_best: bool = False,
    force_over: bool = False,
    coordinate_epoch: float | None = None,
) -> Point | CoordinatePoint:
    target_info = describe_crs(target_crs)
    if not target_info.is_geographic:
        transformed = _transform_position(
            point.as_position(),
            target_crs,
            source_crs=source_crs,
            area_of_interest=area_of_interest,
            allow_ballpark=allow_ballpark,
            only_best=only_best,
            force_over=force_over,
            coordinate_epoch=coordinate_epoch,
        )
        return CoordinatePoint(
            x=transformed[0],
            y=transformed[1],
            z=transformed[2] if point.height_m is not None and len(transformed) == 3 else None,
            m=point.measure,
            crs=target_crs,
        )
    transformer = make_transformer(
        source_crs,
        target_crs,
        area_of_interest=area_of_interest,
        allow_ballpark=allow_ballpark,
        only_best=only_best,
        force_over=force_over,
    )
    if coordinate_epoch is None:
        x, y, z = transformer.transform(
            point.longitude, point.latitude, point.height_m
        )
    else:
        x, y, z, _t = transformer.transform(
            point.longitude,
            point.latitude,
            point.height_m or 0.0,
            coordinate_epoch,
        )
    if z is None or point.height_m is None:
        z_value = None
    else:
        z_value = float(z)
    return Point(latitude=float(y), longitude=float(x), height_m=z_value, measure=point.measure)


def transform_coordinates(
    coordinates: Sequence[float],
    target_crs: str,
    *,
    source_crs: str = DEFAULT_CRS,
    area_of_interest: BoundingBox | None = None,
    allow_ballpark: bool = False,
    only_best: bool = False,
    force_over: bool = False,
    coordinate_epoch: float | None = None,
) -> tuple[float, ...]:
    values = tuple(float(v) for v in coordinates)
    if len(values) not in (2, 3):
        raise ValueError("coordinates must contain 2 or 3 values")
    transformer = make_transformer(
        source_crs,
        target_crs,
        area_of_interest=area_of_interest,
        allow_ballpark=allow_ballpark,
        only_best=only_best,
        force_over=force_over,
    )
    if coordinate_epoch is None:
        if len(values) == 2:
            x, y = transformer.transform(values[0], values[1])
            return (float(x), float(y))
        x, y, z = transformer.transform(values[0], values[1], values[2])
        return (float(x), float(y), float(z))
    x, y, z, _t = transformer.transform(
        values[0],
        values[1],
        values[2] if len(values) == 3 else 0.0,
        coordinate_epoch,
    )
    if len(values) == 2:
        return (float(x), float(y))
    return (float(x), float(y), float(z))


def transform_geometry(
    geometry: Geometry,
    target_crs: str,
    *,
    source_crs: str | None = None,
    area_of_interest: BoundingBox | None = None,
    allow_ballpark: bool = False,
    only_best: bool = False,
    force_over: bool = False,
    coordinate_epoch: float | None = None,
) -> Geometry:
    """Transform all positions recursively while preserving geometry type."""

    src = source_crs or geometry.crs
    transformer = make_transformer(
        src,
        target_crs,
        area_of_interest=area_of_interest,
        allow_ballpark=allow_ballpark,
        only_best=only_best,
        force_over=force_over,
    )

    def convert(value: Any) -> Any:
        if isinstance(value, Geometry):
            return transform_geometry(
                value,
                target_crs,
                source_crs=value.crs,
                area_of_interest=area_of_interest,
                allow_ballpark=allow_ballpark,
                only_best=only_best,
                force_over=force_over,
                coordinate_epoch=coordinate_epoch,
            )
        if isinstance(value, (tuple, list)):
            if value and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in value
            ):
                return transform_coordinates(
                    value,
                    target_crs,
                    source_crs=src,
                    area_of_interest=area_of_interest,
                    allow_ballpark=allow_ballpark,
                    only_best=only_best,
                    force_over=force_over,
                    coordinate_epoch=coordinate_epoch,
                )
            return tuple(convert(child) for child in value)
        return value

    transformed = convert(geometry.coordinates)
    bbox = None
    if geometry.bbox is not None and len(geometry.bbox) in (4, 6):
        from .operations import geometry_bounds

        temp = Geometry(
            type=geometry.type,
            coordinates=transformed,
            bbox=None,
            crs=target_crs,
            coordinate_epoch=coordinate_epoch or geometry.coordinate_epoch,
        )
        bounds = geometry_bounds(temp)
        bbox = bounds
    del transformer
    return Geometry(
        type=geometry.type,
        coordinates=transformed,
        bbox=bbox,
        crs=target_crs,
        coordinate_epoch=coordinate_epoch or geometry.coordinate_epoch,
    )


def _transform_position(
    position: tuple[float, ...],
    target_crs: str,
    *,
    source_crs: str,
    area_of_interest: BoundingBox | None,
    allow_ballpark: bool,
    only_best: bool,
    force_over: bool,
    coordinate_epoch: float | None,
) -> tuple[float, ...]:
    transformer = make_transformer(
        source_crs, target_crs, area_of_interest=area_of_interest, allow_ballpark=allow_ballpark,
        only_best=only_best, force_over=force_over,
    )
    if coordinate_epoch is None:
        if len(position) == 2:
            x, y = transformer.transform(position[0], position[1])
            return (float(x), float(y))
        x, y, z = transformer.transform(position[0], position[1], position[2])
    else:
        x, y, z, _t = transformer.transform(
            position[0], position[1], position[2] if len(position) == 3 else 0.0, coordinate_epoch
        )
    if len(position) == 2:
        return (float(x), float(y))
    return (float(x), float(y), float(z))


def make_transformer(
    source_crs: str,
    target_crs: str,
    *,
    area_of_interest: BoundingBox | None = None,
    allow_ballpark: bool = False,
    only_best: bool = False,
    force_over: bool = False,
) -> Any:
    """Create a pyproj Transformer using GIS-style longitude/latitude order."""

    source = validate_crs(source_crs)
    target = validate_crs(target_crs)
    try:
        from pyproj import Transformer
        from pyproj.aoi import AreaOfInterest
    except ImportError as exc:  # pragma: no cover - exercised by minimal installs
        raise RuntimeError("pyproj is required for CRS transformations") from exc

    aoi = None
    if area_of_interest is not None:
        aoi = AreaOfInterest(
            west_lon_degree=area_of_interest.west,
            south_lat_degree=area_of_interest.south,
            east_lon_degree=area_of_interest.east,
            north_lat_degree=area_of_interest.north,
        )
    return Transformer.from_crs(
        source,
        target,
        always_xy=True,
        area_of_interest=aoi,
        allow_ballpark=allow_ballpark,
        only_best=only_best,
        force_over=force_over,
    )


def _contains_dynamic_marker(value: object) -> bool:
    if isinstance(value, dict):
        return any(_contains_dynamic_marker(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_dynamic_marker(item) for item in value)
    return isinstance(value, str) and "dynamic" in value.lower()


def _pyproj_crs(crs: str) -> Any:
    try:
        from pyproj import CRS
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pyproj is required for CRS introspection") from exc
    try:
        return CRS.from_user_input(validate_crs(crs))
    except Exception as exc:
        raise ValueError(f"invalid CRS: {crs!r}") from exc
