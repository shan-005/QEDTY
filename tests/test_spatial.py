import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from seraph.spatial import (
    CRS84,
    BoundingBox,
    Geometry,
    Point,
    SpatialQuery,
    bbox_contains,
    bbox_from_points,
    bbox_intersection,
    bbox_intersects,
    bbox_union,
    describe_crs,
    destination,
    distance_m,
    geometry_bbox,
    geometry_bounds,
    geometry_contains,
    geometry_covers,
    geometry_intersection,
    geometry_intersects,
    geometry_within,
    h3_cell,
    inverse,
    make_valid,
    midpoint,
    normalize_longitude,
    point_in_bbox,
    points_within_distance,
    polygon_area_m2,
    polyline_length_m,
    query_geometries,
    query_points,
    transform_geometry,
    transform_point,
    validate_crs,
)
from seraph.spatial.geojson import dumps, feature_collection, point_feature
from seraph.spatial.index import (
    BoundingBoxIndex,
    PointGridIndex,
    STRtreeIndex,
    s2_cell_token,
)
from seraph.spatial.jsonfg import decode_feature
from seraph.spatial.jsonfg import feature as jsonfg_feature


def test_existing_bbox_contract() -> None:
    assert point_in_bbox(
        Point(latitude=17.4, longitude=78.4), BoundingBox(west=78, south=17, east=79, north=18)
    )


def test_point_rejects_nonfinite() -> None:
    with pytest.raises(ValueError):
        Point(latitude=float("nan"), longitude=0.0)
    with pytest.raises(ValueError):
        Point(latitude=0.0, longitude=float("inf"))


def test_point_position_order_is_lon_lat() -> None:
    point = Point(latitude=17.4, longitude=78.4, height_m=650.0)
    assert point.as_position() == (78.4, 17.4, 650.0)
    assert point.xy == (78.4, 17.4)


def test_normalize_longitude() -> None:
    assert normalize_longitude(190.0) == -170.0
    assert normalize_longitude(-190.0) == 170.0
    assert normalize_longitude(180.0) == 180.0


def test_antimeridian_bbox() -> None:
    bbox = BoundingBox(west=170.0, south=-10.0, east=-170.0, north=10.0)
    assert bbox.crosses_antimeridian
    assert point_in_bbox(Point(latitude=0.0, longitude=179.0), bbox)
    assert point_in_bbox(Point(latitude=0.0, longitude=-179.0), bbox)
    assert not point_in_bbox(Point(latitude=0.0, longitude=0.0), bbox)
    assert bbox.split_antimeridian()[0].east == 180.0


def test_bbox_relations() -> None:
    a = BoundingBox(west=0.0, south=0.0, east=10.0, north=10.0)
    b = BoundingBox(west=5.0, south=5.0, east=15.0, north=15.0)
    c = BoundingBox(west=20.0, south=20.0, east=30.0, north=30.0)
    assert bbox_intersects(a, b)
    assert not bbox_intersects(a, c)
    assert bbox_contains(a, BoundingBox(west=1.0, south=1.0, east=9.0, north=9.0))
    intersections = bbox_intersection(a, b)
    assert intersections == (BoundingBox(west=5.0, south=5.0, east=10.0, north=10.0),)
    assert bbox_union(a, b) == BoundingBox(west=0.0, south=0.0, east=15.0, north=15.0)


def test_bbox_from_points_uses_minimal_arc() -> None:
    bbox = bbox_from_points(
        [Point(latitude=0.0, longitude=179.0), Point(latitude=0.0, longitude=-179.0)]
    )
    assert bbox.crosses_antimeridian
    assert bbox.longitude_width_degrees == pytest.approx(2.0)


def test_geometry_validation_and_bounds() -> None:
    polygon = Geometry(
        type="Polygon",
        coordinates=(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)),),
        crs="EPSG:4326",
    )
    assert geometry_bounds(polygon) == (0.0, 0.0, 1.0, 1.0)
    assert geometry_bbox(polygon) == BoundingBox(west=0.0, south=0.0, east=1.0, north=1.0)
    with pytest.raises(ValueError):
        Geometry(
            type="LineString",
            coordinates=((181.0, 0.0), (182.0, 1.0)),
            crs="EPSG:4326",
        )


def test_zm_geometry_dimension_and_measure_bounds() -> None:
    geometry = Geometry(
        type="Point",
        coordinates=(78.4, 17.4, 650.0, 42.0),
        crs="EPSG:4326",
    )
    assert geometry.dimension == 4
    assert geometry_bounds(geometry) == (78.4, 17.4, 650.0, 78.4, 17.4, 650.0)


def test_projected_geometry_is_supported_as_arbitrary_coordinates() -> None:
    projected = Geometry(type="Point", coordinates=(1000.0, 2000.0), crs="EPSG:3857")
    assert geometry_bounds(projected) == (1000.0, 2000.0, 1000.0, 2000.0)


def test_geodesic_distance_and_inverse() -> None:
    a = Point(latitude=0.0, longitude=0.0)
    b = Point(latitude=0.0, longitude=1.0)
    result = inverse(a, b)
    assert result.distance_m == pytest.approx(111_319.4908, abs=0.01)
    assert distance_m(a, b) == pytest.approx(result.distance_m)
    assert result.initial_azimuth_deg == pytest.approx(90.0)


def test_geodesic_direct_midpoint_and_interpolate() -> None:
    a = Point(latitude=0.0, longitude=0.0)
    b = destination(a, 90.0, 100_000.0)
    assert b.longitude > 0.8
    mid = midpoint(a, b)
    quarter = midpoint(a, mid)
    assert mid.longitude == pytest.approx(b.longitude / 2, rel=0.02)
    assert quarter.longitude < mid.longitude


def test_polyline_and_polygon_area() -> None:
    line = [
        Point(latitude=0.0, longitude=0.0),
        Point(latitude=0.0, longitude=1.0),
        Point(latitude=1.0, longitude=1.0),
    ]
    assert polyline_length_m(line) > 200_000
    ring = [*line, Point(latitude=0.0, longitude=0.0)]
    area = polygon_area_m2(ring)
    assert area == pytest.approx(6.15e9, rel=0.02)


def test_crs_introspection_and_transform() -> None:
    assert validate_crs("epsg:4326") == "EPSG:4326"
    assert describe_crs("EPSG:4326").is_geographic
    point = Point(latitude=17.385, longitude=78.4867)
    projected = transform_point(point, "EPSG:3857")
    assert projected.crs == "EPSG:3857"
    assert projected.x > 1_000_000
    geometry = Geometry(type="Point", coordinates=(78.4867, 17.385), crs="EPSG:4326")
    round_trip = transform_geometry(transform_geometry(geometry, "EPSG:3857"), "EPSG:4326")
    assert round_trip.coordinates[0] == pytest.approx(78.4867, abs=1e-8)
    assert round_trip.coordinates[1] == pytest.approx(17.385, abs=1e-8)


def test_geojson_round_trip_surface() -> None:
    point = Point(latitude=17.4, longitude=78.4)
    document = point_feature("entity-1", point, {"kind": "demo"})
    assert document["geometry"]["coordinates"] == [78.4, 17.4]
    encoded = dumps(document)
    assert '"type":"Feature"' in encoded
    assert feature_collection([document])["features"] == [document]


def test_jsonfg_time_and_conformance() -> None:
    point = Point(latitude=17.4, longitude=78.4)
    document = jsonfg_feature(
        "entity-1",
        point,
        feature_type="Infrastructure",
        time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert CRS84 in document["coordRefSys"]
    assert document["time"]["timestamp"].endswith("Z")
    assert "http://www.opengis.net/spec/json-fg-1/1.0/conf/core" in document["conformsTo"]
    decoded_id, geometry, properties, time = decode_feature(document)
    assert decoded_id == "entity-1"
    assert geometry.crs == "EPSG:4326"
    assert properties == {}
    assert time == datetime(2026, 1, 1, tzinfo=UTC)


def test_zm_measure_is_valid_and_encoded_separately() -> None:
    point = Point(latitude=17.4, longitude=78.4, height_m=650.0, measure=42.0)
    document = jsonfg_feature("zm", point, feature_type="Tower")
    assert document["geometry"]["coordinates"] == [78.4, 17.4, 650.0]
    assert document["place"]["coordinates"] == [78.4, 17.4, 650.0, 42.0]
    assert document["measures"]["enabled"] is True
    decoded_id, geometry, properties, _time = decode_feature(document)
    assert decoded_id == "zm"
    assert geometry.dimension == 3
    assert properties == {}


def test_jsonfg_measure_is_explicit() -> None:
    point = Point(latitude=17.4, longitude=78.4, measure=42.0)
    document = jsonfg_feature("m", point, feature_type="Road")
    assert document["measures"]["enabled"] is True
    assert any("conf/measures" in value for value in document["conformsTo"])
    assert document["place"]["coordinates"] == [78.4, 17.4, 42.0]


def test_geos_predicates_and_repair() -> None:
    outer = Geometry(
        type="Polygon", coordinates=(((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 0.0)),)
    )
    inner = Geometry(type="Point", coordinates=(2.0, 1.0))
    assert geometry_covers(outer, inner)
    assert geometry_contains(outer, inner)
    assert geometry_within(inner, outer)
    assert geometry_intersects(outer, inner)
    cross = geometry_intersection(
        outer,
        Geometry(
            type="Polygon", coordinates=(((2.0, -1.0), (5.0, -1.0), (5.0, 2.0), (2.0, -1.0)),)
        ),
    )
    assert cross.type in {"Polygon", "MultiPolygon"}

    invalid = Geometry(
        type="Polygon",
        coordinates=(((0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0), (0.0, 0.0)),),
    )
    repaired = make_valid(invalid)
    assert repaired.type in {"MultiPolygon", "GeometryCollection"}


def test_grid_and_bbox_indexes() -> None:
    a = Point(latitude=17.385, longitude=78.4867)
    b = Point(latitude=17.4, longitude=78.5)
    index = PointGridIndex({"a": a, "b": b})
    assert index.query_bbox(BoundingBox(west=78.0, south=17.0, east=79.0, north=18.0)) == ("a", "b")
    assert index.nearest(a, k=2)[0] == ("a", 0.0)
    assert index.range_radius(a, 3_000_000)[0][0] == "a"

    bbox_index: BoundingBoxIndex[str] = BoundingBoxIndex()
    bbox_index.add("a", BoundingBox(west=0.0, south=0.0, east=1.0, north=1.0), "A")
    assert bbox_index.query(BoundingBox(west=0.5, south=0.5, east=2.0, north=2.0)) == (("a", "A"),)


def test_strtree_index_and_high_level_queries() -> None:
    polygon = Geometry(
        type="Polygon", coordinates=(((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 0.0)),)
    )
    point = Geometry(type="Point", coordinates=(2.0, 1.0))
    index = STRtreeIndex({"poly": polygon, "point": point})
    assert index.query(point) == ("point", "poly")
    assert index.nearest(point)[0][0] in {"point", "poly"}
    assert query_geometries({"poly": polygon, "point": point}, point) == ("point", "poly")


def test_spatial_query_distance_ordering() -> None:
    target = Point(latitude=0.0, longitude=0.0)
    candidates = {
        "near": Point(latitude=0.0, longitude=0.1),
        "far": Point(latitude=0.0, longitude=1.0),
    }
    query = SpatialQuery(center=target, radius_m=20_000, limit=1)
    result = query_points(candidates, query)
    assert result == (result[0],)
    assert result[0].key == "near"
    assert points_within_distance(target, candidates, 20_000)[0].key == "near"


def test_geometry_query_rejects_cross_crs_operation() -> None:
    a = Geometry(type="Point", coordinates=(0.0, 0.0), crs="EPSG:4326")
    b = Geometry(type="Point", coordinates=(0.0, 0.0), crs="EPSG:3857")
    with pytest.raises(ValueError):
        geometry_intersects(a, b)


def test_strtree_rejects_cross_crs_query() -> None:
    geometry = Geometry(type="Point", coordinates=(0.0, 0.0), crs="EPSG:4326")
    index = STRtreeIndex({"p": geometry})
    projected = Geometry(type="Point", coordinates=(0.0, 0.0), crs="EPSG:3857")
    with pytest.raises(ValueError, match="CRS"):
        index.query(projected)


def test_spatial_golden_vectors() -> None:
    vectors = json.loads(
        Path(__file__).with_name("spatial_golden_vectors.json").read_text(encoding="utf-8")
    )["vectors"]
    assert vectors[0]["expected_lonlat"] == [78.4, 17.4]
    inverse_vector = vectors[2]
    a = Point(**inverse_vector["input"]["a"])
    b = Point(**inverse_vector["input"]["b"])
    assert inverse(a, b).distance_m == pytest.approx(
        inverse_vector["expected_distance_m"], abs=inverse_vector["tolerance_m"]
    )
    transform_vector = vectors[3]
    projected = transform_point(
        Point(**{k: transform_vector["input"][k] for k in ("latitude", "longitude")}),
        transform_vector["input"]["target_crs"],
    )
    assert projected.x == pytest.approx(
        transform_vector["expected_x"], abs=transform_vector["tolerance_m"]
    )
    assert projected.y == pytest.approx(
        transform_vector["expected_y"], abs=transform_vector["tolerance_m"]
    )


def test_optional_global_index_adapters_fail_cleanly_without_dependency() -> None:
    point = Point(latitude=17.385, longitude=78.4867)
    with pytest.raises(RuntimeError, match="required"):
        h3_cell(point, 9)
    with pytest.raises(RuntimeError, match="required"):
        s2_cell_token(point, 12)
