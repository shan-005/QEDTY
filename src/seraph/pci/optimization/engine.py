from __future__ import annotations

from seraph.pci.counterfactual.engine import CounterfactualEngine
from seraph.pci.counterfactual.models import Intervention
from seraph.pci.optimization.models import OptimizationResult, RankedIntervention
from seraph.pci.shocks.models import Shock


class ResilienceOptimizer:
    def __init__(self, counterfactuals: CounterfactualEngine) -> None:
        self.counterfactuals = counterfactuals

    def rank(self, *, shock: Shock, entity_id: str, interventions: tuple[Intervention, ...]) -> OptimizationResult:
        ranked: list[RankedIntervention] = []
        for intervention in interventions:
            result = self.counterfactuals.compare(shock=shock, entity_id=entity_id, intervention=intervention)
            denominator = intervention.cost_usd / 1_000_000.0
            efficiency = result.continuity_gain / denominator if denominator > 0 else result.continuity_gain
            ranked.append(RankedIntervention(intervention=intervention, continuity_gain=result.continuity_gain, gain_per_million_usd=efficiency, rank_score=efficiency))
        ranked.sort(key=lambda item: (-item.rank_score, item.intervention.intervention_id))
        return OptimizationResult(recommendations=tuple(ranked))
