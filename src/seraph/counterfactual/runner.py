from __future__ import annotations

from collections.abc import Sequence

from seraph.scenarios.models import Intervention
from seraph.scenarios.shocks import Shock

from .engine import CounterfactualEngine
from .models import CounterfactualResult


def run_many(
    engine: CounterfactualEngine,
    shock: Shock,
    entity_id: str,
    interventions: Sequence[Intervention],
) -> tuple[CounterfactualResult, ...]:
    return tuple(engine.compare(shock, entity_id, i) for i in interventions)
