from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
    *,
    baseline_loss_usd: float = 0,
) -> tuple[CounterfactualResult, ...]:
    results = [
        engine.compare(shock, entity_id, i, baseline_loss_usd=baseline_loss_usd)
        for i in interventions
    ]
    return tuple(sorted(results, key=lambda r: (-r.continuity_gain, r.intervention_id)))


def best_intervention(results: Sequence[CounterfactualResult]) -> CounterfactualResult:
    if not results:
        raise ValueError("results required")
    return max(
        results, key=lambda r: (r.continuity_gain, -r.economic_loss_delta_usd, r.intervention_id)
    )
