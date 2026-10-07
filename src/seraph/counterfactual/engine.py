from __future__ import annotations

from typing import TYPE_CHECKING

from .constraints import validate_intervention
from .models import CounterfactualResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from seraph.continuity.engine import ContinuityEngine
    from seraph.propagation.engine import PropagationEngine
    from seraph.scenarios.models import Intervention
    from seraph.scenarios.shocks import Shock


class CounterfactualEngine:
    def __init__(self, propagation: PropagationEngine, continuity: ContinuityEngine):
        self.propagation = propagation
        self.continuity = continuity

    def compare(
        self,
        shock: Shock,
        entity_id: str,
        intervention: Intervention,
        *,
        baseline_loss_usd: float = 0,
        loss_function: Callable[[float], float] | None = None,
    ) -> CounterfactualResult:
        validate_intervention(intervention)
        if baseline_loss_usd < 0:
            raise ValueError("baseline_loss_usd must be non-negative")
        base = self.propagation.propagate(shock)
        b = self.continuity.simulate(entity_id, shock, base)
        reductions = dict.fromkeys(
            intervention.protected_entity_ids, intervention.transmission_reduction
        )
        gains = dict.fromkeys(intervention.protected_entity_ids, intervention.capacity_gain)
        cf = self.propagation.propagate(
            shock, transmission_reduction=reductions, capacity_gain=gains
        )
        c = self.continuity.simulate(entity_id, shock, cf)
        economic_delta = -baseline_loss_usd
        if loss_function is not None:
            economic_delta = loss_function(c.minimum_capacity_fraction) - loss_function(
                b.minimum_capacity_fraction
            )
        status = "counterfactual"
        return CounterfactualResult(
            baseline_capacity=b.minimum_capacity_fraction,
            counterfactual_capacity=c.minimum_capacity_fraction,
            continuity_gain=c.minimum_capacity_fraction - b.minimum_capacity_fraction,
            economic_loss_delta_usd=economic_delta,
            intervention_id=intervention.intervention_id,
            status=status,
            baseline_digest=b.digest,
            counterfactual_digest=c.digest,
            assumptions=(
                "intervention is an explicit modeled action",
                "counterfactual result is conditional on propagation and continuity semantics",
            ),
        )
