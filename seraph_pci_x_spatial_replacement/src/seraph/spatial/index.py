"""Deterministic spatial indexes and nearest-neighbour search."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any, Generic, TypeVar

from .geodesy import distance_m
from .models import BoundingBox, Geometry, Point
from .operations import point_in_bbox

T = TypeVar("T")


def nearest(
    target: Point,
    candidates: dict[str, Point],
    distance_fn: Callable[[Point, Point], float],
) -> tuple[str, float] | None:
    """Backward-compatible deterministic nearest-point search."""

    if not candidates:
        return None
    return min(
        ((key, distance_fn(target, point)) for key, point in candidates.items()),
        key=lambda item: (item[1], item[0]),
    )


class PointGridIndex:
    """Uniform lon/lat grid with deterministic candidate enumeration.

    The grid is an acceleration structure, not the accuracy authority: final
    ranking always uses an exact geodesic distance function.
    """

    def __init__(
        self, points: dict[str, Point] | None = None, *, cell_size_deg: float = 1.0
    ) -> None:
        if not 0.01 <= cell_size_deg <= 30.0:
            raise ValueError("cell_size_deg must be between 0.01 and 30 degrees")
        self.cell_size_deg = float(cell_size_deg)
        self._points: dict[str, Point] = {}
        self._cells: defaultdict[tuple[int, int], set[str]] = defaultdict(set)
        if points:
            for key, point in points.items():
                self.add(key, point)

    def add(self, key: str, point: Point) -> None:
        if key in self._points:
            self.remove(key)
        self._points[key] = point
        self._cells[self._cell(point)].add(key)

    def remove(self, key: str) -> Point | None:
        point = self._points.pop(key, None)
        if point is None:
            return None
        cell = self._cell(point)
        self._cells[cell].discard(key)
        if not self._cells[cell]:
            del self._cells[cell]
        return point

    def __len__(self) -> int:
        return len(self._points)

    def query_bbox(self, bbox: BoundingBox) -> tuple[str, ...]:
        candidate_keys: set[str] = set()
        for part in bbox.split_antimeridian():
            for cell in self._cells_for_bbox(part):
                candidate_keys.update(self._cells.get(cell, ()))
        return tuple(
            sorted(
                key for key in candidate_keys if point_in_bbox(self._points[key], bbox)
            )
        )

    def nearest(self, target: Point, *, k: int = 1) -> tuple[tuple[str, float], ...]:
        if k <= 0:
            raise ValueError("k must be positive")
        if not self._points:
            return ()
        # Search every occupied cell for correctness, using the grid only for
        # deterministic storage/bbox pruning.  A Rust implementation can later
        # replace this with adaptive cell expansion while preserving semantics.
        ranked = [(key, distance_m(target, point)) for key, point in self._points.items()]
        ranked.sort(key=lambda item: (item[1], item[0]))
        return tuple(ranked[:k])

    def range_radius(self, target: Point, radius_m: float) -> tuple[tuple[str, float], ...]:
        if radius_m < 0:
            raise ValueError("radius_m must be non-negative")
        from .geodesy import destination

        earth_half_circumference = 20003931.4586
        if (
            radius_m >= earth_half_circumference
            or abs(target.latitude) + radius_m / 111195.080233 >= 90.0
        ):
            bbox = BoundingBox(west=-180.0, south=-90.0, east=180.0, north=90.0)
        else:
            north = destination(target, 0.0, radius_m)
            south = destination(target, 180.0, radius_m)
            east = destination(target, 90.0, radius_m)
            west = destination(target, -90.0, radius_m)
            bbox = BoundingBox(
                west=west.longitude,
                south=max(-90.0, south.latitude),
                east=east.longitude,
                north=min(90.0, north.latitude),
            )
        # A radius around the antimeridian may wrap; bbox semantics handle that.
        keys = self.query_bbox(bbox)
        ranked = [(key, distance_m(target, self._points[key])) for key in keys]
        ranked = [item for item in ranked if item[1] <= radius_m]
        ranked.sort(key=lambda item: (item[1], item[0]))
        return tuple(ranked)

    def _cell(self, point: Point) -> tuple[int, int]:
        lon_index = int((point.longitude + 180.0) // self.cell_size_deg)
        lat_index = int((point.latitude + 90.0) // self.cell_size_deg)
        return lon_index, lat_index

    def _cells_for_bbox(self, bbox: BoundingBox) -> Iterable[tuple[int, int]]:
        min_x = int((bbox.west + 180.0) // self.cell_size_deg)
        max_x = int((bbox.east + 180.0) // self.cell_size_deg)
        min_y = int((bbox.south + 90.0) // self.cell_size_deg)
        max_y = int((bbox.north + 90.0) // self.cell_size_deg)
        return (
            (x, y)
            for x in range(min_x, max_x + 1)
            for y in range(min_y, max_y + 1)
        )


class BoundingBoxIndex(Generic[T]):
    """Deterministic in-memory bbox index for arbitrary objects."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[BoundingBox, T]] = {}

    def add(self, key: str, bbox: BoundingBox, value: T) -> None:
        self._items[key] = (bbox, value)

    def remove(self, key: str) -> T | None:
        item = self._items.pop(key, None)
        return None if item is None else item[1]

    def query(self, bbox: BoundingBox) -> tuple[tuple[str, T], ...]:
        return tuple(
            (key, value)
            for key, (item_bbox, value) in sorted(self._items.items())
            if _bbox_intersects_exact(item_bbox, bbox)
        )

    def __len__(self) -> int:
        return len(self._items)


def _bbox_intersects_exact(a: BoundingBox, b: BoundingBox) -> bool:
    from .operations import bbox_intersects

    return bbox_intersects(a, b)


class STRtreeIndex(Generic[T]):
    """Optional GEOS STRtree index for arbitrary SERAPH geometries."""

    def __init__(self, geometries: dict[str, Geometry]) -> None:
        try:
            from shapely import STRtree
            from shapely.geometry import shape
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("shapely is required for STRtreeIndex") from exc
        self._keys = tuple(sorted(geometries))
        self._geometries = dict(geometries)
        crs_values = {geometry.crs for geometry in self._geometries.values()}
        if len(crs_values) > 1:
            raise ValueError("STRtreeIndex requires a single CRS for all geometries")
        self.crs = next(iter(crs_values), "EPSG:4326")
        self._shapes = [
            shape({"type": geometry.type, "coordinates": geometry.coordinates})
            if geometry.type != "GeometryCollection"
            else shape({"type": "GeometryCollection", "geometries": [
                {"type": child.type, "coordinates": child.coordinates}
                for child in geometry.coordinates
            ]})
            for geometry in (geometries[key] for key in self._keys)
        ]
        self._tree = STRtree(self._shapes)

    def query(
        self, geometry: Geometry, *, predicate: str = "intersects"
    ) -> tuple[str, ...]:
        self._require_same_crs(geometry)
        shape = self._shape(geometry)
        indexes = self._tree.query(shape, predicate=predicate)
        return tuple(sorted(self._keys[int(index)] for index in indexes))

    def nearest(self, geometry: Geometry, *, k: int = 1) -> tuple[tuple[str, float], ...]:
        self._require_same_crs(geometry)
        if k <= 0:
            raise ValueError("k must be positive")
        shape = self._shape(geometry)
        indexes = self._tree.query_nearest(shape, all_matches=True, return_distance=True)
        index_array, distances = indexes
        ranked = sorted(
            (
                (self._keys[int(index)], float(distance))
                for index, distance in zip(index_array, distances, strict=True)
            ),
            key=lambda item: (item[1], item[0]),
        )
        return tuple(ranked[:k])

    def _require_same_crs(self, geometry: Geometry) -> None:
        if geometry.crs != self.crs:
            raise ValueError("STRtreeIndex query geometry must use the index CRS")

    @staticmethod
    def _shape(geometry: Geometry) -> Any:
        try:
            from shapely.geometry import shape
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("shapely is required for STRtreeIndex") from exc
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


def h3_cell(point: Point, resolution: int) -> str:
    """Return the H3 cell containing a point using optional h3-py 4.x."""
    if not 0 <= resolution <= 15:
        raise ValueError("H3 resolution must be between 0 and 15")
    try:
        import h3
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("h3-py is required for H3 indexing") from exc
    if hasattr(h3, "latlng_to_cell"):
        return str(h3.latlng_to_cell(point.latitude, point.longitude, resolution))
    return str(h3.latLngToCell(point.latitude, point.longitude, resolution))


def h3_cells_for_polygon(
    geometry: Geometry, resolution: int, *, containment: str = "center"
) -> tuple[str, ...]:
    """Return H3 cells for a lon/lat polygon using an explicit containment policy."""
    if geometry.type != "Polygon":
        raise ValueError("H3 polygon covering currently requires a Polygon geometry")
    if geometry.crs.upper() not in {"EPSG:4326", "OGC:CRS84", "CRS84"}:
        raise ValueError("H3 covering requires longitude/latitude geometry")
    if not 0 <= resolution <= 15:
        raise ValueError("H3 resolution must be between 0 and 15")
    if containment not in {"center", "full", "overlap", "bbox_overlap"}:
        raise ValueError("unsupported H3 containment mode")
    try:
        import h3
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("h3-py is required for H3 polygon covering") from exc
    outer = [(float(pos[1]), float(pos[0])) for pos in geometry.coordinates[0]]
    holes = [[(float(pos[1]), float(pos[0])) for pos in ring] for ring in geometry.coordinates[1:]]
    if hasattr(h3, "LatLngPoly"):
        shape = h3.LatLngPoly(outer, *holes)
        if containment == "center" and hasattr(h3, "h3shape_to_cells"):
            return tuple(sorted(str(cell) for cell in h3.h3shape_to_cells(shape, resolution)))
        if hasattr(h3, "h3shape_to_cells_experimental"):
            return tuple(
                sorted(
                    str(cell)
                    for cell in h3.h3shape_to_cells_experimental(
                        shape, resolution, contain=containment
                    )
                )
            )
    if hasattr(h3, "polyfill_geojson"):
        coords = [geometry.coordinates[0], *geometry.coordinates[1:]]
        return tuple(
            sorted(
                str(cell)
                for cell in h3.polyfill_geojson(
                    {"type": "Polygon", "coordinates": coords}, resolution
                )
            )
        )
    raise RuntimeError("installed h3-py does not expose a supported polygon-covering API")


def s2_cell_token(point: Point, level: int = 12) -> str:
    """Return a normalized S2 CellId token using optional s2sphere."""
    if not 0 <= level <= 30:
        raise ValueError("S2 level must be between 0 and 30")
    try:
        from s2sphere import CellId, LatLng
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("s2sphere is required for S2 indexing") from exc
    cell = CellId.from_lat_lng(LatLng.from_degrees(point.latitude, point.longitude)).parent(level)
    return cell.to_token()
