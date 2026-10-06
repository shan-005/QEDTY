from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI


def register_feature_routes(app: FastAPI, feature_provider: Callable[[], dict[str, Any]]) -> None:
    @app.get("/collections/world/features")
    def world_features() -> dict[str, Any]:
        return feature_provider()
