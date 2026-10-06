from __future__ import annotations

from .models import Scenario
from .state import ScenarioState


def apply_scenario(base: ScenarioState, scenario: Scenario) -> ScenarioState:
    out = base.copy()
    for entity_id, mult in scenario.parameters.items():
        out.capacities[entity_id] = max(0.0, min(1.0, out.capacities.get(entity_id, 1.0) * mult))
    return out
