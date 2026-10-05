from __future__ import annotations

from seraph.continuity.engine import ContinuityEngine
from seraph.counterfactual.models import CounterfactualResult, Intervention
from seraph.shocks.models import Shock
from seraph.shocks.propagation import ShockPropagator


class CounterfactualEngine:
    """Compare a declared intervention against an explicit baseline model."""

    def __init__(self, propagator: ShockPropagator, continuity: ContinuityEngine) -> None:
        self.propagator = propagator
        self.continuity = continuity

    def compare(
        self,
        *,
        shock: Shock,
        entity_id: str,
        intervention: Intervention,
    ) -> CounterfactualResult:
        baseline_events = self.propagator.propagate(shock)
        baseline = self.continuity.simulate(
            entity_id=entity_id,
            shock=shock,
            events=baseline_events,
        )

        protected = set(intervention.protected_entities)
        reductions = {
            protected_id: intervention.transmission_reduction
            for protected_id in protected
            if intervention.transmission_reduction > 0.0
        }
        gains = {
            protected_id: intervention.capacity_gain
            for protected_id in protected
            if intervention.capacity_gain > 0.0
        }

        counterfactual_events = self.propagator.propagate(
            shock,
            node_transmission_reduction=reductions,
            node_capacity_gain=gains,
        )
        counterfactual = self.continuity.simulate(
            entity_id=entity_id,
            shock=shock,
            events=counterfactual_events,
        )

        return CounterfactualResult(
            baseline_minimum_capacity=baseline.minimum_capacity_fraction,
            counterfactual_minimum_capacity=counterfactual.minimum_capacity_fraction,
            continuity_gain=counterfactual.minimum_capacity_fraction - baseline.minimum_capacity_fraction,
            intervention_id=intervention.intervention_id,
        )
