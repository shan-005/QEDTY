from __future__ import annotations

from typing import TYPE_CHECKING

from seraph.core.hash import sha256_hex

from .constraints import feasible
from .models import OptimizationResult, RankedIntervention
from .objectives import efficiency
from .portfolio import knapsack_portfolio

if TYPE_CHECKING:
    from collections.abc import Sequence

    from seraph.counterfactual.engine import CounterfactualEngine
    from seraph.scenarios.models import Intervention
    from seraph.scenarios.shocks import Shock


class ResilienceOptimizer:
    def __init__(self, counterfactuals: CounterfactualEngine):
        self.counterfactuals = counterfactuals

    def rank(
        self,
        shock: Shock,
        entity_id: str,
        interventions: Sequence[Intervention],
        *,
        budget_usd: float = 1_000_000_000,
    ) -> OptimizationResult:
        if budget_usd < 0:
            raise ValueError("budget_usd must be non-negative")
        ranked: list[RankedIntervention] = []
        for i in interventions:
            if not feasible(i, budget_usd):
                continue
            cf = self.counterfactuals.compare(shock, entity_id, i)
            gain = cf.continuity_gain
            eff = efficiency(gain, i.cost_usd)
            ranked.append(
                RankedIntervention(
                    intervention_id=i.intervention_id,
                    continuity_gain=gain,
                    cost_usd=i.cost_usd,
                    efficiency=eff,
                    robust_score=gain,
                    risk_score=max(0.0, 1.0 - getattr(cf, "counterfactual_capacity", 0.0)),
                    rationale="counterfactual continuity gain normalized by intervention cost",
                )
            )
        ranked.sort(key=lambda x: (-x.robust_score, -x.efficiency, x.intervention_id))
        selected, spent = knapsack_portfolio(ranked, budget_usd)
        selected_ids = tuple(x.intervention_id for x in selected)
        selected_set = set(selected_ids)
        final = tuple(
            x.model_copy(update={"selected": x.intervention_id in selected_set}) for x in ranked
        )
        digest = sha256_hex(
            {
                "shock": shock,
                "entity_id": entity_id,
                "recommendations": final,
                "budget_usd": budget_usd,
            }
        )
        floor = min((x.robust_score for x in final), default=0.0)
        return OptimizationResult(
            recommendations=final,
            objective="robust_continuity_gain_then_cost_efficiency",
            budget_usd=budget_usd,
            selected_intervention_ids=selected_ids,
            spent_usd=spent,
            robust_floor=floor,
            digest=digest,
        )
