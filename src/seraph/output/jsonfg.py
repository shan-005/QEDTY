from __future__ import annotations

from typing import Any

from seraph.spatial.jsonfg import JSON_FG_VERSION


def collection(
    features: list[dict[str, Any]], *, conformance: tuple[str, ...] = ("core",)
) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": features,
        "json-fg-version": JSON_FG_VERSION,
        "conformsTo": list(conformance),
    }
