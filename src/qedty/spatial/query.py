"""High-level spatial query semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .geodesy import distance_m
from .operations import geometry_covers, geometry_intersects, point_in_bbox

if TYPE_CHECKING:
    from collections.abc import Callable

    from .models import BoundingBox, Geometry, Point


class SpatialQuery(BaseModel):
    """A portable spatial query specification."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    bbox: BoundingBox | None = None
    center: Point | None = None
    radius_m: float | None = Field(default=None, ge=0)
    limit: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def coherent(self) -> SpatialQuery:
        if self.radius_m is not None and self.center is None:
            raise ValueError("center is required when radius_m is provided")
        if self.bbox is None and self.center is None:
            raise ValueError("at least bbox or center must be provided")
        return self


@dataclass(frozen=True, slots=True)
class SpatialMatch:
    key: str
    distance_m: float | None = None


def filter_points(
    points: dict[str, Point],
    bbox: BoundingBox,
    contains: Callable[[Point, BoundingBox], bool] = point_in_bbox,
) -> tuple[str, ...]:
    return tuple(sorted(key for key, point in points.items() if contains(point, bbox)))


def query_points(
    points: dict[str, Point],
    query: SpatialQuery,
) -> tuple[SpatialMatch, ...]:
    candidate_keys = tuple(sorted(points))
    if query.bbox is not None:
        candidate_keys = tuple(
            key for key in candidate_keys if point_in_bbox(points[key], query.bbox)
        )
    matches: list[SpatialMatch] = []
    for key in candidate_keys:
        point = points[key]
        distance = None
        if query.center is not None:
            distance = distance_m(query.center, point)
            if query.radius_m is not None and distance > query.radius_m:
                continue
        matches.append(SpatialMatch(key=key, distance_m=distance))
    matches.sort(
        key=lambda item: (
            item.distance_m if item.distance_m is not None else 0.0,
            item.key,
        )
    )
    if query.limit is not None:
        matches = matches[: query.limit]
    return tuple(matches)


def nearest_point(
    target: Point,
    candidates: dict[str, Point],
) -> SpatialMatch | None:
    if not candidates:
        return None
    key, distance = min(
        ((key, distance_m(target, point)) for key, point in candidates.items()),
        key=lambda item: (item[1], item[0]),
    )
    return SpatialMatch(key=key, distance_m=distance)


def points_within_distance(
    target: Point,
    candidates: dict[str, Point],
    radius_m: float,
) -> tuple[SpatialMatch, ...]:
    return query_points(
        candidates,
        SpatialQuery(center=target, radius_m=radius_m),
    )


def query_geometries(
    geometries: dict[str, Geometry],
    target: Geometry,
    *,
    predicate: str = "intersects",
    limit: int | None = None,
) -> tuple[str, ...]:
    matcher: Callable[[Geometry, Geometry], bool]
    if predicate == "intersects":
        matcher = geometry_intersects
    elif predicate == "covers":
        matcher = geometry_covers
    else:
        raise ValueError("predicate must be 'intersects' or 'covers'")

    result = tuple(sorted(key for key, geometry in geometries.items() if matcher(geometry, target)))
    return result if limit is None else result[:limit]
