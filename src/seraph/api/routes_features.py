from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI


def register_feature_routes(app: FastAPI, feature_provider: Callable[[], dict[str, Any]]) -> None:
    @app.get("/collections/world")
    def world_collection() -> dict[str, Any]:
        return {
            "id": "world",
            "title": "SERAPH World Features",
            "itemType": "feature",
            "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
        }

    @app.get("/collections/world/features")
    def world_features() -> dict[str, Any]:
        return feature_provider()
