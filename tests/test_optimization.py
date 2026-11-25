from __future__ import annotations

from dataclasses import dataclass
from math import inf, nan

import pytest

from qedty.optimization.objectives import cvar, efficiency
from qedty.optimization.portfolio import (
    MAX_EXACT_ITEMS,
    greedy_portfolio,
    knapsack_portfolio,
    select_portfolio,
)


@dataclass(frozen=True, slots=True)
class Item:
    intervention_id: str
    cost_usd: float
    efficiency: float


def test_efficiency() -> None:
    assert efficiency(0.5, 1_000_000) == 0.5


def test_cvar_and_portfolio() -> None:
    assert cvar([1.0, 2.0, 3.0], 0.9) == 1.0

    items = [
        Item("a", 4.0, 1.0),
        Item("b", 6.0, 2.0),
    ]

    chosen, spent = knapsack_portfolio(items, 6.0)

    assert spent == 6.0
    assert [item.intervention_id for item in chosen] == ["b"]


def test_exact_selection_reports_reference_optimality() -> None:
    items = [
        Item("a", 5.0, 10.0),
        Item("b", 7.0, 8.0),
        Item("c", 3.0, 10.0),
    ]

    result = select_portfolio(items, 8.0)

    assert result.solver_mode == "exact_branch_and_bound"
    assert result.status == "optimal_reference"
    assert result.is_optimal is True

    assert {item.intervention_id for item in result.selected_items} == {"a", "c"}

    assert result.spent_usd == 8.0
    assert result.total_cost_usd == 8.0
    assert result.objective_value == pytest.approx(80.0 / 1_000_000)


def test_exact_selection_respects_budget() -> None:
    items = [
        Item("a", 8.0, 10.0),
        Item("b", 7.0, 9.0),
        Item("c", 4.0, 5.0),
    ]

    result = select_portfolio(items, 11.0)

    assert result.spent_usd <= 11.0
    assert sum(item.cost_usd for item in result.selected_items) <= 11.0


def test_exact_selection_uses_total_objective_contribution() -> None:
    items = [
        Item("a", 5.0, 10.0),
        Item("b", 7.0, 8.0),
        Item("c", 3.0, 10.0),
    ]

    result = select_portfolio(items, 8.0)

    expected_value = (10.0 * 5.0 / 1_000_000) + (10.0 * 3.0 / 1_000_000)

    assert result.objective_value == pytest.approx(expected_value)


def test_exact_selection_keeps_legacy_zero_cost_semantics() -> None:
    free_candidate = Item(
        intervention_id="free-positive-efficiency",
        cost_usd=0.0,
        efficiency=5.0,
    )

    result = select_portfolio([free_candidate], 0.0)

    # The v1 exact objective contribution is efficiency * cost / 1e6.
    # Therefore this candidate contributes zero and is not selected.
    assert result.selected_items == ()
    assert result.spent_usd == 0.0
    assert result.objective_value == 0.0
    assert result.status == "optimal_reference"


def test_exact_selection_uses_deterministic_id_tie_breaking() -> None:
    items = [
        Item("b", 5.0, 10.0),
        Item("a", 5.0, 10.0),
    ]

    result = select_portfolio(items, 5.0)

    assert [item.intervention_id for item in result.selected_items] == ["a"]


def test_empty_portfolio_is_exact_and_feasible() -> None:
    result = select_portfolio([], 100.0)

    assert result.selected_items == ()
    assert result.spent_usd == 0.0
    assert result.objective_value == 0.0
    assert result.solver_mode == "exact_branch_and_bound"
    assert result.status == "optimal_reference"


def test_large_portfolio_uses_greedy_fallback() -> None:
    items = [
        Item(
            intervention_id=f"item-{index:02d}",
            cost_usd=1.0,
            efficiency=1.0,
        )
        for index in range(MAX_EXACT_ITEMS + 1)
    ]

    result = select_portfolio(items, 2.0)

    assert result.solver_mode == "greedy_fallback"
    assert result.status == "feasible_not_proven_optimal"
    assert result.is_optimal is False
    assert result.spent_usd == 2.0

    assert [item.intervention_id for item in result.selected_items] == ["item-00", "item-01"]


def test_greedy_portfolio_keeps_legacy_return_shape() -> None:
    items = [
        Item("a", 4.0, 1.0),
        Item("b", 6.0, 2.0),
    ]

    chosen, spent = greedy_portfolio(items, 6.0)

    assert isinstance(chosen, tuple)
    assert spent == 6.0
    assert [item.intervention_id for item in chosen] == ["b"]


@pytest.mark.parametrize(
    "budget",
    [
        -1.0,
        nan,
        inf,
    ],
)
def test_invalid_budget_is_rejected(budget: float) -> None:
    with pytest.raises(ValueError):
        select_portfolio([Item("a", 1.0, 1.0)], budget)


@pytest.mark.parametrize(
    ("cost_usd", "item_efficiency"),
    [
        (-1.0, 1.0),
        (1.0, -1.0),
        (inf, 1.0),
        (1.0, nan),
    ],
)
def test_invalid_candidate_values_are_rejected(
    cost_usd: float,
    item_efficiency: float,
) -> None:
    item = Item(
        intervention_id="invalid",
        cost_usd=cost_usd,
        efficiency=item_efficiency,
    )

    with pytest.raises(ValueError):
        select_portfolio([item], 10.0)


@pytest.mark.parametrize(
    "intervention_id",
    [
        "",
        "   ",
    ],
)
def test_blank_intervention_ids_are_rejected(
    intervention_id: str,
) -> None:
    item = Item(
        intervention_id=intervention_id,
        cost_usd=1.0,
        efficiency=1.0,
    )

    with pytest.raises(ValueError):
        select_portfolio([item], 10.0)


def test_duplicate_intervention_ids_are_rejected() -> None:
    items = [
        Item("duplicate", 1.0, 1.0),
        Item("duplicate", 2.0, 2.0),
    ]

    with pytest.raises(ValueError, match="duplicate intervention_id"):
        select_portfolio(items, 10.0)


def test_non_finite_objective_contribution_is_rejected() -> None:
    item = Item(
        intervention_id="overflow",
        cost_usd=1e308,
        efficiency=1e308,
    )

    with pytest.raises(ValueError):
        select_portfolio([item], 1e308)
