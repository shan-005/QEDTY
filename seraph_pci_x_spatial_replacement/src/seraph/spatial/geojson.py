"""RFC 7946 GeoJSON serialization and parsing."""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .models import Geometry, Point

GEOJSON_VERSION = "RFC 7946"


def point_feature(
    entity_id: str,
    point: Point,
    properties: dict[str, Any] | None = None,
    *,
    bbox: tuple[float, ...] | None = None,
) -> dict[str, Any]:
    return feature(
        entity_id,
        geometry_from_point(point),
        properties=properties,
        bbox=bbox,
    )


def geometry_object(
    geometry: Geometry, *, precision: int | None = None, enforce_wgs84: bool = True
) -> dict[str, Any]:
    if enforce_wgs84 and geometry.crs.upper() not in {
        "EPSG:4326", "OGC:CRS84", "CRS84", "EPSG:4979"
    }:
        raise ValueError("RFC 7946 GeoJSON requires WGS 84 longitude/latitude coordinates")
    coordinates = geometry.coordinates
    if precision is not None:
        if precision < 0:
            raise ValueError("precision must be non-negative")
        coordinates = _round_coordinates(coordinates, precision)
    result: dict[str, Any] = {"type": geometry.type}
    if geometry.type == "GeometryCollection":
        result["geometries"] = [
            geometry_object(child, precision=precision, enforce_wgs84=enforce_wgs84)
            for child in geometry.coordinates
        ]
    else:
        result["coordinates"] = _json_coordinates(coordinates)
    if geometry.bbox is not None:
        result["bbox"] = list(geometry.bbox)
    return result


def feature(
    entity_id: str,
    geometry: Geometry,
    *,
    properties: dict[str, Any] | None = None,
    bbox: tuple[float, ...] | None = None,
    precision: int | None = None,
) -> dict[str, Any]:
    if not entity_id:
        raise ValueError("entity_id must not be empty")
    data: dict[str, Any] = {
        "type": "Feature",
        "id": entity_id,
        "geometry": geometry_object(geometry, precision=precision),
        "properties": {} if properties is None else properties,
    }
    if bbox is not None:
        data["bbox"] = list(bbox)
    return data


def feature_collection(
    features: list[dict[str, Any]] | tuple[dict[str, Any], ...]
) -> dict[str, Any]:
    if not all(feature_value.get("type") == "Feature" for feature_value in features):
        raise ValueError("all members must be GeoJSON Features")
    return {"type": "FeatureCollection", "features": list(features)}


def parse_geometry(document: Mapping[str, Any], *, crs: str = "EPSG:4326") -> Geometry:
    geometry_type = document.get("type")
    if geometry_type == "GeometryCollection":
        geometries = document.get("geometries")
        if not isinstance(geometries, list):
            raise ValueError("GeometryCollection requires a geometries array")
        return Geometry(
            type="GeometryCollection",
            coordinates=tuple(parse_geometry(item, crs=crs) for item in geometries),
            bbox=_tuple_bbox(document.get("bbox")),
            crs=crs,
        )
    coordinates = document.get("coordinates")
    return Geometry(
        type=geometry_type,
        coordinates=coordinates,
        bbox=_tuple_bbox(document.get("bbox")),
        crs=crs,
    )


def parse_feature(
    document: Mapping[str, Any], *, crs: str = "EPSG:4326"
) -> tuple[str | int | float, Geometry, dict[str, Any] | None]:
    if document.get("type") != "Feature":
        raise ValueError("document is not a GeoJSON Feature")
    if "id" not in document:
        raise ValueError("Feature requires an id for SERAPH entity mapping")
    geometry_doc = document.get("geometry")
    if geometry_doc is None:
        raise ValueError("SERAPH spatial features require a concrete geometry")
    geometry = parse_geometry(geometry_doc, crs=crs)
    properties = document.get("properties")
    if properties is not None and not isinstance(properties, dict):
        raise ValueError("Feature properties must be an object or null")
    feature_id = document["id"]
    if isinstance(feature_id, bool) or not isinstance(feature_id, (str, int, float)):
        raise ValueError("Feature id must be a string or JSON number")
    return feature_id, geometry, properties


def dumps(document: Mapping[str, Any], *, sort_keys: bool = True, indent: int | None = None) -> str:
    """Canonical JSON serialization suitable for hashes and fixtures."""

    separators = None if indent is not None else (",", ":")
    return json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=sort_keys,
        separators=separators,
        indent=indent,
    )


def geometry_from_point(point: Point) -> Geometry:
    return Geometry(type="Point", coordinates=point.as_position(), crs="EPSG:4326")


def _json_coordinates(value: Any) -> Any:
    if isinstance(value, (tuple, list)):
        return [_json_coordinates(item) for item in value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if isinstance(value, float) else value
    raise ValueError("coordinates contain a non-numeric value")


def _round_coordinates(value: Any, precision: int) -> Any:
    if isinstance(value, (tuple, list)):
        if value and all(
            isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
        ):
            return [_round_number(float(item), precision) for item in value]
        return [_round_coordinates(item, precision) for item in value]
    return value


def _round_number(value: float, precision: int) -> float:
    quantizer = Decimal(1).scaleb(-precision)
    return float(Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP))


def _tuple_bbox(value: Any) -> tuple[float, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) not in (4, 6):
        raise ValueError("bbox must be an array of length 4 or 6")
    return tuple(float(item) for item in value)
