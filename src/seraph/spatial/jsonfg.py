"""OGC JSON-FG 1.0.0 interoperability for SERAPH-PCI-X."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from seraph.core.time import ensure_utc
from seraph.temporal.intervals import Interval

from .crs import CRS84, CRS84H, crs_uri
from .geojson import geometry_object, point_feature
from .models import Geometry, Point

JSON_FG_VERSION = "1.0.0"
JSON_FG_CORE_CONFORMANCE = "http://www.opengis.net/spec/json-fg-1/1.0/conf/core"
JSON_FG_TYPES_SCHEMAS_CONFORMANCE = "http://www.opengis.net/spec/json-fg-1/1.0/conf/types-schemas"


def feature(
    entity_id: str,
    point: Point,
    *,
    feature_type: str,
    properties: dict[str, Any] | None = None,
    time: datetime | Interval | None = None,
    feature_schema: str | None = None,
    coord_ref_sys: str | None = None,
    place: Geometry | None = None,
) -> dict[str, Any]:
    result = point_feature(entity_id, point, properties)
    result["featureType"] = feature_type
    result["coordRefSys"] = coord_ref_sys or (CRS84H if point.height_m is not None else CRS84)
    result["conformsTo"] = [JSON_FG_CORE_CONFORMANCE]
    if feature_schema:
        result["featureSchema"] = feature_schema
        result["conformsTo"].append(JSON_FG_TYPES_SCHEMAS_CONFORMANCE)
    if place is None and point.measure is not None:
        measure_coordinates = point.as_position(include_measure=True)
        place = Geometry(type="Point", coordinates=measure_coordinates, crs="EPSG:4326")
        result["measures"] = {"enabled": True}
        result["conformsTo"].append("http://www.opengis.net/spec/json-fg-1/1.0/conf/measures")
    if place is not None:
        result["place"] = geometry_object(place, enforce_wgs84=False)
        place_ref: str | dict[str, Any] = crs_uri(place.crs)
        if place.coordinate_epoch is not None:
            place_ref = {
                "type": "Reference",
                "href": crs_uri(place.crs),
                "epoch": place.coordinate_epoch,
            }
        result["place"]["coordRefSys"] = place_ref
    if time is not None:
        result["time"] = encode_time(time)
    return result


def encode_time(value: datetime | Interval) -> dict[str, Any]:
    if isinstance(value, Interval):
        return {
            "interval": [
                _timestamp(value.start),
                _timestamp(value.end),
            ]
        }
    return {"timestamp": _timestamp(value)}


def parse_time(value: Mapping[str, Any]) -> datetime | Interval:
    if "timestamp" in value:
        raw = value["timestamp"]
        if not isinstance(raw, str):
            raise ValueError("timestamp must be a string")
        return _parse_timestamp(raw)
    if "interval" in value:
        raw = value["interval"]
        if not isinstance(raw, list) or len(raw) != 2 or not all(isinstance(x, str) for x in raw):
            raise ValueError("interval must contain exactly two RFC 3339 timestamps")
        return Interval(start=_parse_timestamp(raw[0]), end=_parse_timestamp(raw[1]))
    if "date" in value:
        raw = value["date"]
        if not isinstance(raw, str):
            raise ValueError("date must be a string")
        return datetime.fromisoformat(raw).replace(tzinfo=UTC)
    raise ValueError("unsupported JSON-FG time object")


def decode_feature(
    document: Mapping[str, Any],
) -> tuple[str | int | float, Geometry, dict[str, Any] | None, datetime | Interval | None]:
    if document.get("type") != "Feature":
        raise ValueError("document is not a JSON-FG Feature")
    if "id" not in document:
        raise ValueError("JSON-FG Feature requires an id")
    geometry_document = document.get("geometry")
    if not isinstance(geometry_document, Mapping):
        raise ValueError("JSON-FG Feature requires a geometry object")
    from .geojson import parse_geometry

    geometry = parse_geometry(geometry_document, crs="EPSG:4326")
    feature_id = document["id"]
    if isinstance(feature_id, bool) or not isinstance(feature_id, (str, int, float)):
        raise ValueError("JSON-FG Feature id must be a string or JSON number")
    properties = document.get("properties")
    temporal = document.get("time")
    parsed_time = parse_time(temporal) if isinstance(temporal, Mapping) else None
    return feature_id, geometry, properties if isinstance(properties, dict) else None, parsed_time


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return ensure_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("JSON-FG timestamps must use UTC Z")
    return datetime.fromisoformat(value)
