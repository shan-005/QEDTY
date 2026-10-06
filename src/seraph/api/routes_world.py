from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI

from seraph.ontology.world import WorldModel


def register_world_routes(app: FastAPI, world_provider: Callable[[], WorldModel]) -> None:
    @app.get("/world/summary")
    def world_summary() -> dict[str, int]:
        return world_provider().summary()
