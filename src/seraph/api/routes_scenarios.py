from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI


def register_scenario_routes(app: FastAPI, scenario_provider: Callable[[], list[object]]) -> None:
    @app.get("/scenarios")
    def scenarios() -> list[object]:
        return scenario_provider()
