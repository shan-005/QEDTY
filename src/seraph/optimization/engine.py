from __future__ import annotations
from .models import OptimizationResult,RankedIntervention
from .objectives import efficiency
from .constraints import feasible
from seraph.counterfactual.engine import CounterfactualEngine
class ResilienceOptimizer:
    def __init__(self,counterfactuals:CounterfactualEngine):self.counterfactuals=counterfactuals
    def rank(self,shock,entity_id,interventions,*,budget_usd:float=1_000_000_000)->OptimizationResult:
        ranked=[]
        for i in interventions:
            if not feasible(i,budget_usd):continue
            cf=self.counterfactuals.compare(shock,entity_id,i); eff=efficiency(cf.continuity_gain,i.cost_usd); ranked.append(RankedIntervention(intervention_id=i.intervention_id,continuity_gain=cf.continuity_gain,cost_usd=i.cost_usd,efficiency=eff,robust_score=cf.continuity_gain))
        ranked.sort(key=lambda x:(-x.robust_score,-x.efficiency,x.intervention_id)); return OptimizationResult(recommendations=tuple(ranked),objective="continuity_gain_then_cost_efficiency",budget_usd=budget_usd)
