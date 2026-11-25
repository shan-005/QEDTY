from __future__ import annotations

from typing import TYPE_CHECKING

from qedty.core.hash import sha256_hex

from .constraints import feasible
from .models import OptimizationResult, RankedIntervention
from .objectives import efficiency
from .portfolio import select_portfolio

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qedty.counterfactual.engine import CounterfactualEngine
    from qedty.scenarios.models import Intervention
    from qedty.scenarios.shocks import Shock


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
        for intervention in interventions:
            if not feasible(intervention, budget_usd):
                continue

            counterfactual = self.counterfactuals.compare(
                shock,
                entity_id,
                intervention,
            )
            gain = counterfactual.continuity_gain
            item_efficiency = efficiency(gain, intervention.cost_usd)

            ranked.append(
                RankedIntervention(
                    intervention_id=intervention.intervention_id,
                    continuity_gain=gain,
                    cost_usd=intervention.cost_usd,
                    efficiency=item_efficiency,
                    robust_score=gain,
                    risk_score=max(
                        0.0,
                        1.0 - getattr(counterfactual, "counterfactual_capacity", 0.0),
                    ),
                    rationale=("counterfactual continuity gain normalized by intervention cost"),
                )
            )

        ranked.sort(
            key=lambda item: (
                -item.robust_score,
                -item.efficiency,
                item.intervention_id,
            )
        )

        selection = select_portfolio(ranked, budget_usd)
        selected_ids = selection.selected_intervention_ids
        selected_set = set(selected_ids)
        final = tuple(
            item.model_copy(update={"selected": item.intervention_id in selected_set})
            for item in ranked
        )

        # Keep the historical digest preimage and public v1 wire surface unchanged.
        # The internal status is corrected so a greedy fallback is never reported
        # as a proven optimum by OptimizationResult's default value.
        digest = sha256_hex(
            {
                "shock": shock,
                "entity_id": entity_id,
                "recommendations": final,
                "budget_usd": budget_usd,
            }
        )
        floor = min((item.robust_score for item in final), default=0.0)

        return OptimizationResult(
            recommendations=final,
            objective="robust_continuity_gain_then_cost_efficiency",
            budget_usd=budget_usd,
            selected_intervention_ids=selected_ids,
            spent_usd=selection.spent_usd,
            robust_floor=floor,
            status=selection.status,
            digest=digest,
        )
