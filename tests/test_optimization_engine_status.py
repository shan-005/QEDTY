from __future__ import annotations

from types import SimpleNamespace

from qedty.optimization.engine import ResilienceOptimizer


class FakeCounterfactuals:
    def compare(
        self,
        shock: object,
        entity_id: str,
        intervention: SimpleNamespace,
    ) -> SimpleNamespace:
        del shock, entity_id
        return SimpleNamespace(
            continuity_gain=intervention.continuity_gain,
            counterfactual_capacity=0.8,
        )


def _interventions(count: int) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            intervention_id=f"intervention-{index:02d}",
            cost_usd=1.0,
            continuity_gain=float(index + 1) / 100.0,
        )
        for index in range(count)
    ]


def test_engine_reports_exact_reference_status_for_at_most_28_candidates() -> None:
    optimizer = ResilienceOptimizer(FakeCounterfactuals())

    result = optimizer.rank(
        shock="test-shock",
        entity_id="test-entity",
        interventions=_interventions(2),
        budget_usd=2.0,
    )

    assert result.status == "optimal_reference"
    assert len(result.selected_intervention_ids) == 2
    assert result.spent_usd == 2.0


def test_engine_reports_unproven_status_when_greedy_fallback_is_used() -> None:
    optimizer = ResilienceOptimizer(FakeCounterfactuals())

    result = optimizer.rank(
        shock="test-shock",
        entity_id="test-entity",
        interventions=_interventions(29),
        budget_usd=29.0,
    )

    assert result.status == "feasible_not_proven_optimal"
    assert len(result.selected_intervention_ids) == 29
    assert result.spent_usd == 29.0
