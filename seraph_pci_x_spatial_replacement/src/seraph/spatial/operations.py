"""Spatial predicates, extents and optional GEOS-backed operations."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from .models import BoundingBox, Geometry, Point, normalize_longitude


def point_in_bbox(point: Point, bbox: BoundingBox, *, inclusive: bool = True) -> bool:
    lon = point.longitude
    lat = point.latitude
    if inclusive:
        lat_ok = bbox.south <= lat <= bbox.north
    else:
        lat_ok = bbox.south < lat < bbox.north
    if not lat_ok:
        return False
    if bbox.crosses_antimeridian:
        return lon >= bbox.west or lon <= bbox.east
    return bbox.west <= lon <= bbox.east if inclusive else bbox.west < lon < bbox.east


def bbox_contains(outer: BoundingBox, inner: BoundingBox) -> bool:
    if outer.south > inner.south or outer.north < inner.north:
        return False
    if outer.crosses_antimeridian:
        if inner.crosses_antimeridian:
            return inner.west >= outer.west and inner.east <= outer.east
        return point_in_bbox(
            Point(latitude=inner.south, longitude=inner.west), outer
        ) and point_in_bbox(
            Point(latitude=inner.north, longitude=inner.east), outer
        )
    if inner.crosses_antimeridian:
        return False
    return outer.west <= inner.west and inner.east <= outer.east


def bbox_intersects(a: BoundingBox, b: BoundingBox) -> bool:
    if a.north < b.south or b.north < a.south:
        return False
    return any(
        _plain_bbox_intersects(x, y)
        for x in a.split_antimeridian()
        for y in b.split_antimeridian()
    )


def bbox_intersection(a: BoundingBox, b: BoundingBox) -> tuple[BoundingBox, ...]:
    south = max(a.south, b.south)
    north = min(a.north, b.north)
    if south > north:
        return ()
    parts: list[BoundingBox] = []
    for left in a.split_antimeridian():
        for right in b.split_antimeridian():
            west = max(left.west, right.west)
            east = min(left.east, right.east)
            if west <= east:
                parts.append(BoundingBox(west=west, south=south, east=east, north=north))
    return _dedupe_bboxes(parts)


def bbox_union(a: BoundingBox, b: BoundingBox) -> BoundingBox:
    if bbox_contains(a, b):
        return a
    if bbox_contains(b, a):
        return b
    # Choose the minimal longitudinal arc that contains both extents.  For two
    # ordinary bboxes this reduces to min/max; for wrapped bboxes compare the
    # complementary arcs.
    samples = [a.west, a.east, b.west, b.east]
    candidates = _candidate_longitude_arcs(samples)
    best = min(
        candidates, key=lambda box: (box.longitude_width_degrees, box.west, box.east)
    )
    return BoundingBox(
        west=best.west,
        south=min(a.south, b.south),
        east=best.east,
        north=max(a.north, b.north),
    )


def bbox_from_points(points: Iterable[Point], *, minimal_longitude_arc: bool = True) -> BoundingBox:
    items = tuple(points)
    if not items:
        raise ValueError("at least one point is required")
    south = min(point.latitude for point in items)
    north = max(point.latitude for point in items)
    lons = [point.longitude for point in items]
    if not minimal_longitude_arc:
        return BoundingBox(west=min(lons), south=south, east=max(lons), north=north)
    candidates = _candidate_longitude_arcs(lons)
    best = min(candidates, key=lambda box: (box.longitude_width_degrees, box.west, box.east))
    return BoundingBox(west=best.west, south=south, east=best.east, north=north)


def geometry_bounds(
    geometry: Geometry,
) -> tuple[float, float, float, float] | tuple[float, float, float, float, float, float]:
    """Return coordinate-space bounds independent of CRS."""
    positions = list(_positions(geometry.coordinates))
    if not positions:
        raise ValueError("geometry has no positions")
    dims = {len(position) for position in positions}
    if len(dims) != 1:
        raise ValueError("geometry positions must have a consistent dimension")
    xs = [position[0] for position in positions]
    ys = [position[1] for position in positions]
    if len(positions[0]) == 2:
        return (min(xs), min(ys), max(xs), max(ys))
    zs = [position[2] for position in positions]
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def geometry_bbox(geometry: Geometry) -> BoundingBox:
    positions = list(_positions(geometry.coordinates))
    if not positions:
        raise ValueError("geometry has no positions")
    if geometry.crs.upper() in {"EPSG:4326", "OGC:CRS84", "CRS84", "EPSG:4979"}:
        points = [Point.from_xy(position[0], position[1]) for position in positions]
        return bbox_from_points(points)
    raise ValueError(
        "geometry_bbox is defined for geographic lon/lat geometries; "
        "use geometry_bounds for projected CRS"
    )


def geometry_intersects(a: Geometry, b: Geometry) -> bool:
    return bool(_shapely_predicate("intersects", a, b))


def geometry_covers(container: Geometry, target: Geometry) -> bool:
    return bool(_shapely_predicate("covers", container, target))


def geometry_within(target: Geometry, container: Geometry) -> bool:
    return bool(_shapely_predicate("within", target, container))


def geometry_contains(container: Geometry, target: Geometry) -> bool:
    return bool(_shapely_predicate("contains", container, target))


def geometry_equals(a: Geometry, b: Geometry) -> bool:
    return bool(_shapely_predicate("equals", a, b))


def geometry_intersection(a: Geometry, b: Geometry) -> Geometry:
    return _shapely_result("intersection", a, b)


def geometry_union(a: Geometry, b: Geometry) -> Geometry:
    return _shapely_result("union", a, b)


def geometry_difference(a: Geometry, b: Geometry) -> Geometry:
    return _shapely_result("difference", a, b)


def make_valid(geometry: Geometry) -> Geometry:
    try:
        from shapely import make_valid as shapely_make_valid
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("shapely is required for topology repair") from exc
    obj = _to_shapely(geometry)
    return _from_shapely(
        shapely_make_valid(obj),
        crs=geometry.crs,
        coordinate_epoch=geometry.coordinate_epoch,
    )


def set_precision(geometry: Geometry, grid_size: float) -> Geometry:
    if grid_size <= 0:
        raise ValueError("grid_size must be positive")
    try:
        from shapely import set_precision as shapely_set_precision
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("shapely is required for precision reduction") from exc
    obj = _to_shapely(geometry)
    return _from_shapely(
        shapely_set_precision(obj, grid_size),
        crs=geometry.crs,
        coordinate_epoch=geometry.coordinate_epoch,
    )


def normalize_geometry(geometry: Geometry) -> Geometry:
    """Normalize a GEOS geometry to a deterministic structural ordering."""

    try:
        from shapely import normalize
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("shapely is required for geometry normalization") from exc
    return _from_shapely(
        normalize(_to_shapely(geometry)),
        crs=geometry.crs,
        coordinate_epoch=geometry.coordinate_epoch,
    )


def _plain_bbox_intersects(a: BoundingBox, b: BoundingBox) -> bool:
    return not (a.east < b.west or b.east < a.west or a.north < b.south or b.north < a.south)


def _candidate_longitude_arcs(longitudes: Iterable[float]) -> tuple[BoundingBox, ...]:
    values = sorted(float(lon) for lon in longitudes)
    if any(value < -180.0 or value > 180.0 for value in values):
        raise ValueError("longitude must be between -180 and 180")
    if not values:
        raise ValueError("at least one longitude is required")
    if len(values) == 1:
        return (BoundingBox(west=values[0], south=-90, east=values[0], north=90),)
    candidates = [BoundingBox(west=values[0], south=-90, east=values[-1], north=90)]
    largest_gap_idx = max(
        range(len(values)),
        key=lambda i: (
            ((values[(i + 1) % len(values)] - values[i]) % 360.0),
            -i,
        ),
    )
    gap = (
        values[(largest_gap_idx + 1) % len(values)] - values[largest_gap_idx]
    ) % 360.0
    # The smallest arc containing the points is the complement of the largest gap.
    west = values[(largest_gap_idx + 1) % len(values)]
    east = values[largest_gap_idx]
    candidates.append(BoundingBox(west=west, south=-90, east=east, north=90))
    if gap == 0:
        return (candidates[0],)
    return tuple(candidates)


def _dedupe_bboxes(items: Iterable[BoundingBox]) -> tuple[BoundingBox, ...]:
    seen: set[tuple[float, float, float, float]] = set()
    result: list[BoundingBox] = []
    for item in items:
        key = item.as_tuple()
        if key not in seen:
            result.append(item)
            seen.add(key)
    return tuple(result)


def _positions(value: Any) -> Iterator[tuple[float, ...]]:
    if isinstance(value, (tuple, list)):
        if value and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
            yield tuple(float(v) for v in value)
            return
        for child in value:
            yield from _positions(child)


def _shapely_predicate(operation: str, a: Geometry, b: Geometry) -> bool:
    left, right = _to_shapely(a), _to_shapely(b)
    if a.crs != b.crs:
        raise ValueError("spatial predicates require geometries in the same CRS")
    return bool(getattr(left, operation)(right))


def _shapely_result(operation: str, a: Geometry, b: Geometry) -> Geometry:
    if a.crs != b.crs:
        raise ValueError("spatial operations require geometries in the same CRS")
    left, right = _to_shapely(a), _to_shapely(b)
    result = getattr(left, operation)(right)
    return _from_shapely(result, crs=a.crs, coordinate_epoch=a.coordinate_epoch)


def _to_shapely(geometry: Geometry) -> Any:
    try:
        from shapely.geometry import shape
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("shapely is required for GEOS-backed spatial operations") from exc
    if geometry.type == "GeometryCollection":
        return shape(
            {
                "type": "GeometryCollection",
                "geometries": [
                    {"type": child.type, "coordinates": child.coordinates}
                    for child in geometry.coordinates
                ],
            }
        )
    return shape({"type": geometry.type, "coordinates": geometry.coordinates})


def _from_shapely(obj: Any, *, crs: str, coordinate_epoch: float | None) -> Geometry:
    data = obj.__geo_interface__
    if data["type"] == "GeometryCollection":
        geometry = Geometry(
            type="GeometryCollection",
            coordinates=tuple(
                Geometry(
                    type=g["type"],
                    coordinates=g.get("coordinates"),
                    crs=crs,
                    coordinate_epoch=coordinate_epoch,
                )
                for g in data["geometries"]
            ),
            crs=crs,
            coordinate_epoch=coordinate_epoch,
        )
    else:
        geometry = Geometry(
            type=data["type"],
            coordinates=data.get("coordinates"),
            crs=crs,
            coordinate_epoch=coordinate_epoch,
        )
    return geometry.model_copy(update={"bbox": geometry_bbox(geometry).as_tuple()})
