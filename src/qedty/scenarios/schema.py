"""Language-neutral scenario contract metadata."""

from __future__ import annotations

from typing import Any

from .models import (
    Intervention,
    Scenario,
    ScenarioBranch,
    ScenarioGuard,
    ScenarioRun,
    Shock,
    StatePatch,
)
from .state import ScenarioState

NAME = "qedty-scenarios"
VERSION = "1.0.0"
KEY = f"{NAME}@{VERSION}"
CONTRACT_PROFILE = "QEDTY scenario contract v1"
SCENARIO_STATE_TYPE = ScenarioState


def json_schema() -> dict[str, Any]:
    """Return a bundled JSON Schema generated from the canonical Pydantic models."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": KEY,
        "title": "QEDTY Scenario Contract",
        "type": "object",
        "properties": {
            "scenario": Scenario.model_json_schema(),
            "shock": Shock.model_json_schema(),
            "intervention": Intervention.model_json_schema(),
            "state_patch": StatePatch.model_json_schema(),
            "scenario_guard": ScenarioGuard.model_json_schema(),
            "scenario_branch": ScenarioBranch.model_json_schema(),
            "scenario_run": ScenarioRun.model_json_schema(),
            "scenario_state": {
                "type": "object",
                "required": [
                    "capacities",
                    "attributes",
                    "transmission_reductions",
                    "active_shock_ids",
                    "applied_intervention_ids",
                    "lineage",
                ],
            },
        },
        "required": ["scenario"],
        "$defs": {
            "Scenario": Scenario.model_json_schema(),
            "Shock": Shock.model_json_schema(),
            "Intervention": Intervention.model_json_schema(),
            "StatePatch": StatePatch.model_json_schema(),
            "ScenarioGuard": ScenarioGuard.model_json_schema(),
            "ScenarioBranch": ScenarioBranch.model_json_schema(),
            "ScenarioRun": ScenarioRun.model_json_schema(),
            "ScenarioState": {
                "type": "object",
                "properties": {
                    "capacities": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                    },
                    "attributes": {"type": "object"},
                    "transmission_reductions": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                    },
                    "active_shock_ids": {"type": "array", "items": {"type": "string"}},
                    "applied_intervention_ids": {"type": "array", "items": {"type": "string"}},
                    "lineage": {"type": "array", "items": {"type": "string"}},
                    "world_digest": {"type": ["string", "null"]},
                    "evaluated_at": {"type": ["string", "null"], "format": "date-time"},
                },
                "required": [
                    "capacities",
                    "attributes",
                    "transmission_reductions",
                    "active_shock_ids",
                    "applied_intervention_ids",
                    "lineage",
                ],
                "additionalProperties": False,
            },
        },
    }
