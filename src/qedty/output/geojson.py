from __future__ import annotations

from typing import Any


def feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    if any(f.get("type") != "Feature" for f in features):
        raise ValueError("all members must be GeoJSON Features")
    return {"type": "FeatureCollection", "features": features}


def feature(
    properties: dict[str, Any],
    *,
    geometry: dict[str, Any] | None = None,
    feature_id: str | int | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "Feature", "properties": dict(properties), "geometry": geometry}
    if feature_id is not None:
        out["id"] = feature_id
    return out
