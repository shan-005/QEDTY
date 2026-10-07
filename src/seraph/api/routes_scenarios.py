from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI


def register_scenario_routes(app: FastAPI, scenario_provider: Callable[[], list[object]]) -> None:
    @app.get("/scenarios")
    def scenarios() -> list[Any]:
        return scenario_provider()
