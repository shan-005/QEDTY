from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from qedty.economics.currency_v2 import (
    CurrencyMetadata,
    CurrencyMetadataProfile,
    FxRate,
    FxSnapshot,
    MoneyAmount,
)
from qedty.optimization.portfolio_v2 import (
    PortfolioCandidateV2,
    PortfolioObjectiveV2,
    PortfolioRequestV2,
    optimize_portfolio_v2,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)
T2 = datetime(2026, 1, 3, tzinfo=UTC)


def currency_profile() -> CurrencyMetadataProfile:
    return CurrencyMetadataProfile(
        "portfolio-fixture-v1",
        (
            CurrencyMetadata("AAA", 2),
            CurrencyMetadata("BBB", 2),
            CurrencyMetadata("CCC", 2),
        ),
    )


def fx_snapshot(*rates: FxRate) -> FxSnapshot:
    return FxSnapshot(
        snapshot_id="portfolio-fx-1",
        as_of=T1,
        valid_from=T0,
        valid_to=T2,
        rates=tuple(rates),
    )


def fx_rate(base: str, quote: str, value: str) -> FxRate:
    return FxRate(
        base_currency=base,
        quote_currency=quote,
        rate=Decimal(value),
        observed_at=T0,
        source="independent-fixture",
        provenance_id=f"fixture:{base}/{quote}",
    )


def money(value: str, currency: str = "BBB") -> MoneyAmount:
    return MoneyAmount(Decimal(value), currency, "portfolio-fixture-v1")


def candidate(
    identifier: str,
    cost: str,
    gain: str,
    *,
    currency: str = "BBB",
    risk: str = "0",
    scenario_scores: tuple[str, ...] = (),
) -> PortfolioCandidateV2:
    return PortfolioCandidateV2(
        intervention_id=identifier,
        cost=money(cost, currency),
        continuity_gain=Decimal(gain),
        risk_score=Decimal(risk),
        scenario_scores=tuple(Decimal(value) for value in scenario_scores),
    )


def request(
    candidates: tuple[PortfolioCandidateV2, ...],
    budget: str,
    *,
    budget_currency: str = "BBB",
    fx: FxSnapshot | None = None,
    objective: PortfolioObjectiveV2 | None = None,
    fixed_overhead: MoneyAmount | None = None,
    scenario_ids: tuple[str, ...] = (),
) -> PortfolioRequestV2:
    return PortfolioRequestV2(
        budget=money(budget, budget_currency),
        currency_profile=currency_profile(),
        candidates=candidates,
        objective=objective or PortfolioObjectiveV2(kind="continuity_gain"),
        fx_snapshot=fx,
        fixed_overhead=fixed_overhead,
        scenario_ids=scenario_ids,
    )


def test_v2_optimizer_converts_native_currencies_before_budget_selection() -> None:
    result = optimize_portfolio_v2(
        request(
            (
                candidate("native-aaa", "5.00", "5", currency="AAA"),
                candidate("native-bbb", "4.00", "3"),
            ),
            "10.00",
            fx=fx_snapshot(fx_rate("AAA", "BBB", "2")),
        )
    )
    assert result.status == "optimal"
    assert result.reporting_currency_code == "BBB"
    assert result.selected_intervention_ids == ("native-aaa",)
    assert result.spent.amount == Decimal("10.00")
    converted = next(item for item in result.recommendations if item.intervention_id == "native-aaa")
    assert converted.reporting_cost.amount == Decimal("10.00")
    assert converted.conversion.fx_snapshot_id == "portfolio-fx-1"
    assert converted.conversion.fx_provenance_id == "fixture:AAA/BBB"


def test_exact_solver_finds_better_combination_than_greedy_choice() -> None:
    result = optimize_portfolio_v2(
        request(
            (
                candidate("a", "5.00", "8"),
                candidate("b", "7.00", "10"),
                candidate("c", "3.00", "5"),
            ),
            "8.00",
        )
    )
    assert result.status == "optimal"
    assert result.solver_mode == "exact_branch_and_bound"
    assert result.selected_intervention_ids == ("a", "c")
    assert result.spent.amount == Decimal("8.00")
    assert result.objective_value == Decimal(13)


def test_objective_ties_use_lexicographic_ids_deterministically() -> None:
    result = optimize_portfolio_v2(
        request((candidate("z", "1.00", "1"), candidate("a", "1.00", "1")), "1.00")
    )
    assert result.selected_intervention_ids == ("a",)


def test_positive_utility_zero_cost_candidate_is_selected() -> None:
    result = optimize_portfolio_v2(
        request((candidate("free", "0.00", "1"),), "0.00")
    )
    assert result.status == "optimal"
    assert result.selected_intervention_ids == ("free",)
    assert result.spent.amount == Decimal("0.00")
    assert result.total_committed.amount == Decimal("0.00")


def test_lower_tail_cvar_objective_uses_shared_scenario_order() -> None:
    result = optimize_portfolio_v2(
        request(
            (
                candidate("volatile", "1.00", "6", scenario_scores=("5", "1")),
                candidate("stable", "1.00", "6", scenario_scores=("4", "4")),
            ),
            "1.00",
            objective=PortfolioObjectiveV2(
                kind="lower_tail_cvar", cvar_alpha=Decimal("0.5")
            ),
            scenario_ids=("high", "low"),
        )
    )
    assert result.selected_intervention_ids == ("stable",)
    assert result.portfolio_cvar == Decimal(4)
    assert result.portfolio_robust_floor == Decimal(4)
    assert result.dominance_score == Decimal(1)


def test_fixed_overhead_above_budget_returns_explicit_infeasible_status() -> None:
    result = optimize_portfolio_v2(
        request(
            (candidate("small", "1.00", "1"),),
            "5.00",
            fixed_overhead=money("6.00"),
        )
    )
    assert result.status == "infeasible"
    assert result.solver_mode == "infeasible"
    assert result.selected_intervention_ids == ()
    assert result.total_committed.amount == Decimal("6.00")


def test_greedy_fallback_is_never_mislabeled_as_proven_optimal() -> None:
    items = tuple(candidate(f"item-{i:02d}", "1.00", str(i + 1)) for i in range(29))
    result = optimize_portfolio_v2(request(items, "29.00"))
    assert result.status == "feasible_not_proven_optimal"
    assert result.solver_mode == "greedy_fallback"
    assert len(result.selected_intervention_ids) == 29
    assert result.digest


def test_digest_is_independent_of_input_candidate_order() -> None:
    items = (candidate("z", "1.00", "2"), candidate("a", "1.00", "1"))
    first = optimize_portfolio_v2(request(items, "2.00"))
    second = optimize_portfolio_v2(request(tuple(reversed(items)), "2.00"))
    assert first.digest == second.digest
    assert first.selected_intervention_ids == second.selected_intervention_ids


def test_missing_fx_path_fails_instead_of_fetching_or_triangulating() -> None:
    fx = fx_snapshot(
        fx_rate("AAA", "BBB", "2"),
        fx_rate("BBB", "CCC", "3"),
    )
    with pytest.raises(ValueError, match="triangulation is disabled"):
        optimize_portfolio_v2(
            request((candidate("cross", "1.00", "1", currency="AAA"),), "10.00", fx=fx,
                    budget_currency="CCC")
        )


def test_request_rejects_scenario_score_length_mismatch() -> None:
    with pytest.raises(ValueError, match="one score per declared scenario"):
        request(
            (candidate("a", "1.00", "1", scenario_scores=("2",)),),
            "2.00",
            scenario_ids=("scenario-1", "scenario-2"),
        )


def test_infeasible_currency_profile_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="profile version"):
        PortfolioRequestV2(
            budget=money("10.00", "BBB"),
            currency_profile=currency_profile(),
            candidates=(
                PortfolioCandidateV2(
                    "bad",
                    MoneyAmount(Decimal("1.00"), "BBB", "other-profile"),
                    Decimal(1),
                ),
            ),
        )


def test_robust_floor_is_optimized_over_portfolio_scenario_totals() -> None:
    result = optimize_portfolio_v2(
        request(
            (
                candidate("left", "1.00", "5", scenario_scores=("10", "-2")),
                candidate("right", "1.00", "5", scenario_scores=("-2", "10")),
            ),
            "2.00",
            objective=PortfolioObjectiveV2(kind="robust_floor"),
            scenario_ids=("scenario-a", "scenario-b"),
        )
    )
    assert result.status == "optimal"
    assert result.selected_intervention_ids == ("left", "right")
    assert result.objective_value == Decimal(8)
    assert result.portfolio_robust_floor == Decimal(8)


def test_cvar_uses_combined_portfolio_scenarios_not_sum_of_item_cvar() -> None:
    result = optimize_portfolio_v2(
        request(
            (
                candidate("left", "1.00", "5", scenario_scores=("10", "-2")),
                candidate("right", "1.00", "5", scenario_scores=("-2", "10")),
            ),
            "2.00",
            objective=PortfolioObjectiveV2(
                kind="lower_tail_cvar", cvar_alpha=Decimal("0.5")
            ),
            scenario_ids=("scenario-a", "scenario-b"),
        )
    )
    assert result.status == "optimal"
    assert result.selected_intervention_ids == ("left", "right")
    assert result.objective_value == Decimal(8)
    assert result.portfolio_cvar == Decimal(8)


def test_tail_risk_objectives_require_explicit_scenario_ids() -> None:
    with pytest.raises(ValueError, match="require declared scenario scores"):
        request(
            (candidate("candidate", "1.00", "1"),),
            "2.00",
            objective=PortfolioObjectiveV2(kind="robust_floor"),
        )


def test_weighted_score_result_is_the_selected_portfolio_objective() -> None:
    result = optimize_portfolio_v2(
        request(
            (
                candidate("gain", "1000000.00", "3", risk="0"),
                candidate("risk", "1000000.00", "5", risk="1"),
            ),
            "1000000.00",
            objective=PortfolioObjectiveV2(
                kind="weighted_score",
                gain_weight=Decimal(1),
                cost_weight=Decimal(1),
                risk_weight=Decimal(1),
            ),
        )
    )
    assert result.selected_intervention_ids == ("risk",)
    assert result.objective_value == Decimal(3)
