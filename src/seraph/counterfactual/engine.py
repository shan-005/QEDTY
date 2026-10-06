from __future__ import annotations

from seraph.continuity.engine import ContinuityEngine
from seraph.propagation.engine import PropagationEngine
from seraph.scenarios.models import Intervention
from seraph.scenarios.shocks import Shock

from .constraints import validate_intervention
from .models import CounterfactualResult


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
    ) -> CounterfactualResult:
        validate_intervention(intervention)
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
        # Economic delta is a caller-provided baseline placeholder only; the economic engine remains separately provenance-bound.
        return CounterfactualResult(
            baseline_capacity=b.minimum_capacity_fraction,
            counterfactual_capacity=c.minimum_capacity_fraction,
            continuity_gain=c.minimum_capacity_fraction - b.minimum_capacity_fraction,
            economic_loss_delta_usd=0.0 - baseline_loss_usd,
            intervention_id=intervention.intervention_id,
        )
