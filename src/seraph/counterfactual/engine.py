from __future__ import annotations

from dataclasses import replace

from seraph.continuity.engine import ContinuityEngine
from seraph.counterfactual.models import CounterfactualResult, Intervention
from seraph.shocks.models import Shock
from seraph.shocks.propagation import ShockPropagator


class CounterfactualEngine:
    def __init__(self, propagator: ShockPropagator, continuity: ContinuityEngine) -> None:
        self.propagator = propagator
        self.continuity = continuity

    def compare(self, *, shock: Shock, entity_id: str, intervention: Intervention) -> CounterfactualResult:
        events = self.propagator.propagate(shock)
        baseline = self.continuity.simulate(entity_id=entity_id, shock=shock, events=events)
        target = next((event for event in events if event.entity_id == entity_id), None)
        severity = 0.0 if target is None else target.severity
        if entity_id in intervention.protected_entities:
            counterfactual_severity = max(0.0, severity * (1.0 - intervention.transmission_reduction) - intervention.capacity_gain)
            if target is None:
                adjusted_events = events
            else:
                adjusted = replace(target, severity=min(1.0, counterfactual_severity))
                adjusted_events = tuple(adjusted if event.entity_id == entity_id else event for event in events)
        else:
            adjusted_events = events
        counterfactual = self.continuity.simulate(entity_id=entity_id, shock=shock, events=adjusted_events)
        return CounterfactualResult(
            baseline_minimum_capacity=baseline.minimum_capacity_fraction,
            counterfactual_minimum_capacity=counterfactual.minimum_capacity_fraction,
            continuity_gain=counterfactual.minimum_capacity_fraction - baseline.minimum_capacity_fraction,
            intervention_id=intervention.intervention_id,
        )
