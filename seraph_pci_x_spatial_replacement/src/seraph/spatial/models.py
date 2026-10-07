"""Canonical spatial domain models for SERAPH-PCI-X.

The Python layer is the semantic reference implementation.  Models in this
module deliberately carry named longitude/latitude semantics while external
encodings use the GeoJSON/JSON-FG position order ``[x, y, ...]``.
"""

from __future__ import annotations

from collections.abc import Iterator
from math import isfinite
from typing import Any, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GeometryType = Literal[
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
    "GeometryCollection",
]

Coordinate = tuple[float, float]
Coordinate3D = tuple[float, float, float]
Coordinate4D = tuple[float, float, float, float]


def _finite(value: float, label: str) -> float:
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _validate_position(position: object, *, geographic: bool = True) -> tuple[float, ...]:
    if not isinstance(position, (tuple, list)):
        raise ValueError("position must be an array")
    if len(position) not in (2, 3, 4):
        raise ValueError("position must contain 2, 3, or 4 numbers (XY, XYZ/XYM, or XYZM)")
    values = tuple(
        float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else x
        for x in position
    )
    if not all(isinstance(x, float) for x in values):
        raise ValueError("position members must be numbers")
    for i, value in enumerate(values):
        _finite(value, f"position[{i}]")
    if geographic:
        lon, lat = values[:2]
        if not -180.0 <= lon <= 180.0:
            raise ValueError("longitude must be between -180 and 180")
        if not -90.0 <= lat <= 90.0:
            raise ValueError("latitude must be between -90 and 90")
    return values


def _walk_positions(value: object, *, geographic: bool = True) -> Iterator[tuple[float, ...]]:
    if isinstance(value, (tuple, list)):
        if value and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
            yield _validate_position(value, geographic=geographic)
            return
        for child in value:
            yield from _walk_positions(child, geographic=geographic)
        return
    raise ValueError("coordinates must be a nested array of positions")


def _dimension(value: object, *, geographic: bool = True) -> int:
    dims = {len(position) for position in _walk_positions(value, geographic=geographic)}
    if len(dims) != 1:
        raise ValueError("all positions must use the same coordinate dimension")
    return next(iter(dims))


class Point(BaseModel):
    """Geographic point using WGS-style longitude/latitude semantics.

    ``latitude`` and ``longitude`` remain named fields for domain clarity;
    GeoJSON serialization uses ``[longitude, latitude, height?]``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    height_m: float | None = Field(default=None)
    measure: float | None = Field(default=None)

    _finite_fields: ClassVar[tuple[str, ...]] = ("latitude", "longitude", "height_m", "measure")

    @model_validator(mode="after")
    def valid(self) -> Self:
        for field_name in self._finite_fields:
            value = getattr(self, field_name)
            if value is not None:
                _finite(value, field_name)
        return self

    @property
    def dimension(self) -> int:
        if self.height_m is not None and self.measure is not None:
            return 4
        if self.height_m is not None or self.measure is not None:
            return 3
        return 2

    @property
    def lonlat(self) -> Coordinate | Coordinate3D:
        if self.height_m is None:
            return (self.longitude, self.latitude)
        return (self.longitude, self.latitude, self.height_m)

    @property
    def xy(self) -> Coordinate:
        return (self.longitude, self.latitude)

    def as_position(self, *, include_measure: bool = False) -> tuple[float, ...]:
        values: tuple[float, ...] = self.lonlat
        if include_measure and self.measure is not None:
            return values + (self.measure,)
        return values

    @classmethod
    def from_xy(
        cls,
        x: float,
        y: float,
        z: float | None = None,
        *,
        measure: float | None = None,
    ) -> Point:
        return cls(latitude=y, longitude=x, height_m=z, measure=measure)


class CoordinatePoint(BaseModel):
    """Coordinate point in an arbitrary declared CRS.

    Unlike :class:`Point`, this model does not assume longitude/latitude
    bounds and is therefore suitable for projected CRS coordinates.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    x: float
    y: float
    z: float | None = None
    m: float | None = None
    crs: str = "EPSG:4326"

    @model_validator(mode="after")
    def finite(self) -> Self:
        for name in ("x", "y", "z", "m"):
            value = getattr(self, name)
            if value is not None:
                _finite(value, name)
        if not self.crs.strip():
            raise ValueError("CRS must not be empty")
        return self

    @property
    def dimension(self) -> int:
        return 3 if self.z is not None else 2

    def as_position(self) -> tuple[float, ...]:
        if self.z is None:
            return (self.x, self.y)
        return (self.x, self.y, self.z)


class BoundingBox(BaseModel):
    """Longitude/latitude extent.

    A wrapped bbox is encoded with ``west > east`` and represents an extent
    crossing the antimeridian.  Latitude is always south <= north.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)

    @model_validator(mode="after")
    def valid(self) -> Self:
        for name in ("west", "south", "east", "north"):
            _finite(getattr(self, name), name)
        if self.north < self.south:
            raise ValueError("north must be greater than or equal to south")
        return self

    @property
    def crosses_antimeridian(self) -> bool:
        return self.west > self.east

    @property
    def longitude_width_degrees(self) -> float:
        if self.crosses_antimeridian:
            return (180.0 - self.west) + (self.east + 180.0)
        return self.east - self.west

    @property
    def latitude_height_degrees(self) -> float:
        return self.north - self.south

    @property
    def center(self) -> Point:
        if self.crosses_antimeridian:
            lon = normalize_longitude(self.west + self.longitude_width_degrees / 2.0)
        else:
            lon = (self.west + self.east) / 2.0
        return Point(latitude=(self.south + self.north) / 2.0, longitude=lon)

    def split_antimeridian(self) -> tuple[BoundingBox, ...]:
        if not self.crosses_antimeridian:
            return (self,)
        return (
            BoundingBox(west=self.west, south=self.south, east=180.0, north=self.north),
            BoundingBox(west=-180.0, south=self.south, east=self.east, north=self.north),
        )

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.west, self.south, self.east, self.north)


def normalize_longitude(longitude: float) -> float:
    """Normalize longitude into the closed interval [-180, 180]."""

    _finite(longitude, "longitude")
    normalized = (longitude + 180.0) % 360.0 - 180.0
    if normalized == -180.0 and longitude > 0:
        return 180.0
    return normalized


class Geometry(BaseModel):
    """GeoJSON-compatible geometry with explicit CRS metadata.

    The ``crs`` member is SERAPH-native metadata and is omitted from GeoJSON
    output; JSON-FG uses ``coordRefSys`` for non-default CRS declarations.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    type: GeometryType
    coordinates: Any
    bbox: tuple[float, ...] | None = None
    crs: str = "EPSG:4326"
    coordinate_epoch: float | None = None

    @field_validator("crs")
    @classmethod
    def crs_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("CRS must not be empty")
        return value

    @field_validator("coordinate_epoch")
    @classmethod
    def epoch_finite(cls, value: float | None) -> float | None:
        if value is not None:
            _finite(value, "coordinate_epoch")
        return value

    @model_validator(mode="after")
    def validate_geometry(self) -> Self:
        geographic = self.crs.upper() in {"EPSG:4326", "OGC:CRS84", "CRS84", "EPSG:4979"}
        _validate_coordinates_for_type(self.type, self.coordinates, geographic=geographic)
        object.__setattr__(self, "coordinates", _freeze_coordinates(self.coordinates))
        if self.bbox is not None:
            if len(self.bbox) not in (4, 6):
                raise ValueError("bbox must contain 4 or 6 values")
            for i, value in enumerate(self.bbox):
                _finite(value, f"bbox[{i}]")
        return self

    @property
    def dimension(self) -> int:
        if self.type == "GeometryCollection":
            dimensions = {child.dimension for child in self.coordinates}
            if len(dimensions) != 1:
                raise ValueError("GeometryCollection members must use a consistent dimension")
            return next(iter(dimensions))
        geographic = self.crs.upper() in {"EPSG:4326", "OGC:CRS84", "CRS84", "EPSG:4979"}
        return _dimension(self.coordinates, geographic=geographic)


def _validate_coordinates_for_type(
    geometry_type: str, coordinates: object, *, geographic: bool = True
) -> None:
    if geometry_type == "Point":
        _validate_position(coordinates, geographic=geographic)
        return
    if geometry_type == "LineString":
        positions = list(_walk_positions(coordinates, geographic=geographic))
        if len(positions) < 2:
            raise ValueError("LineString requires at least two positions")
        return
    if geometry_type == "Polygon":
        rings = coordinates
        if not isinstance(rings, (tuple, list)) or not rings:
            raise ValueError("Polygon requires at least one linear ring")
        for ring in rings:
            positions = list(_walk_positions(ring, geographic=geographic))
            if len(positions) < 4:
                raise ValueError("linear ring requires at least four positions")
            if positions[0] != positions[-1]:
                raise ValueError("linear ring must be closed")
        return
    if geometry_type == "MultiPoint":
        list(_walk_positions(coordinates, geographic=geographic))
        return
    if geometry_type == "MultiLineString":
        lines = coordinates
        if not isinstance(lines, (tuple, list)):
            raise ValueError("MultiLineString coordinates must be nested arrays")
        for line in lines:
            positions = list(_walk_positions(line, geographic=geographic))
            if len(positions) < 2:
                raise ValueError("each LineString requires at least two positions")
        return
    if geometry_type == "MultiPolygon":
        polygons = coordinates
        if not isinstance(polygons, (tuple, list)):
            raise ValueError("MultiPolygon coordinates must be nested arrays")
        for polygon in polygons:
            _validate_coordinates_for_type("Polygon", polygon, geographic=geographic)
        return
    if geometry_type == "GeometryCollection":
        if not isinstance(coordinates, (tuple, list)):
            raise ValueError("GeometryCollection coordinates must be a sequence")
        for geometry in coordinates:
            if not isinstance(geometry, Geometry):
                raise ValueError("GeometryCollection coordinates must contain Geometry models")
        return
    raise ValueError(f"unsupported geometry type: {geometry_type}")


def _freeze_coordinates(value: object) -> object:
    if isinstance(value, Geometry):
        return value
    if isinstance(value, (tuple, list)):
        if value and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
            return tuple(float(v) for v in value)
        return tuple(_freeze_coordinates(child) for child in value)
    raise ValueError("coordinates must be nested arrays or Geometry members")


def geometry_from_point(point: Point, *, crs: str = "EPSG:4326") -> Geometry:
    return Geometry(type="Point", coordinates=point.as_position(), crs=crs)
