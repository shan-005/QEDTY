from __future__ import annotations

from datetime import datetime
from typing import Any

from .geojson import point_feature
from .models import Point

JSON_FG_VERSION = "1.0.0"
JSON_FG_PROFILE = "http://www.opengis.net/spec/json-fg-1/1.0/conf/core"
CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"


def feature(
    entity_id: str,
    point: Point,
    *,
    feature_type: str,
    properties: dict[str, Any] | None = None,
    time: datetime | None = None,
    feature_schema: str | None = None,
) -> dict[str, Any]:
    value = point_feature(entity_id, point, properties)
    value["featureType"] = feature_type
    value["coordRefSys"] = CRS84
    value["conformsTo"] = [JSON_FG_PROFILE]
    if feature_schema:
        value["featureSchema"] = feature_schema
    if time is not None:
        timestamp = time.astimezone().isoformat().replace("+00:00", "Z")
        value["time"] = {"timestamp": timestamp}
    return value
