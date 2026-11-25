from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence


MAX_EXACT_ITEMS = 28


class PortfolioItem(Protocol):
    """Minimum interface required by the portfolio selection algorithms."""

    intervention_id: str
    cost_usd: float
    efficiency: float


@dataclass(frozen=True, slots=True)
class PortfolioSelection[T: PortfolioItem]:
    """Result of portfolio selection, including solver and optimality status."""

    selected_items: tuple[T, ...]
    spent_usd: float
    objective_value: float
    solver_mode: Literal["exact_branch_and_bound", "greedy_fallback"]
    status: Literal["optimal_reference", "feasible_not_proven_optimal"]

    @property
    def total_cost_usd(self) -> float:
        """Backward-friendly alias for the selected portfolio cost."""
        return self.spent_usd

    @property
    def total_value(self) -> float:
        """Backward-friendly alias for the objective value."""
        return self.objective_value

    @property
    def selected_intervention_ids(self) -> tuple[str, ...]:
        return tuple(item.intervention_id for item in self.selected_items)

    @property
    def is_optimal(self) -> bool:
        return self.status == "optimal_reference"


def _prepare[T: PortfolioItem](
    items: Sequence[T],
    budget_usd: float,
) -> tuple[tuple[tuple[T, str, float, float, float], ...], float]:
    """Validate and deterministically prepare portfolio candidates.

    Each record contains:
        (original item, intervention ID, cost, efficiency, objective contribution)

    Legacy objective contribution:
        max(0, efficiency * cost_usd / 1_000_000)
    """

    try:
        budget = float(budget_usd)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("budget_usd must be a finite number") from exc

    if not isfinite(budget):
        raise ValueError("budget_usd must be finite")

    if budget < 0:
        raise ValueError("budget must be non-negative")

    records: list[tuple[T, str, float, float, float]] = []
    seen_ids: set[str] = set()

    for item in items:
        intervention_id = item.intervention_id

        if not isinstance(intervention_id, str) or not intervention_id.strip():
            raise ValueError("intervention_id must be a non-empty string")

        if intervention_id in seen_ids:
            raise ValueError(f"duplicate intervention_id: {intervention_id}")

        seen_ids.add(intervention_id)

        try:
            cost_usd = float(item.cost_usd)
            efficiency = float(item.efficiency)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("cost_usd and efficiency must be finite numbers") from exc

        if not isfinite(cost_usd) or cost_usd < 0:
            raise ValueError("item cost must be finite and non-negative")

        if not isfinite(efficiency) or efficiency < 0:
            raise ValueError("efficiency must be finite and non-negative")

        objective_value = max(
            0.0,
            efficiency * cost_usd / 1_000_000.0,
        )

        if not isfinite(objective_value):
            raise ValueError("objective contribution must be finite")

        records.append(
            (
                item,
                intervention_id,
                cost_usd,
                efficiency,
                objective_value,
            )
        )

    # A fractional-knapsack upper bound is valid because objective
    # contribution per dollar is proportional to efficiency.
    records.sort(key=lambda record: (-record[3], record[1]))

    total_objective = sum(record[4] for record in records)

    if not isfinite(total_objective):
        raise ValueError("total objective contribution must be finite")

    return tuple(records), budget


def _greedy_selection[T: PortfolioItem](
    records: tuple[tuple[T, str, float, float, float], ...],
    budget: float,
) -> PortfolioSelection[T]:
    """Deterministic feasible greedy fallback.

    This does not claim global optimality.
    """

    chosen: list[T] = []
    spent = 0.0
    objective_value = 0.0

    for item, _, cost_usd, _, contribution in records:
        if spent + cost_usd <= budget:
            chosen.append(item)
            spent += cost_usd
            objective_value += contribution

    return PortfolioSelection(
        selected_items=tuple(chosen),
        spent_usd=spent,
        objective_value=objective_value,
        solver_mode="greedy_fallback",
        status="feasible_not_proven_optimal",
    )


def select_portfolio[T: PortfolioItem](
    items: Sequence[T],
    budget_usd: float,
) -> PortfolioSelection[T]:
    """Select a portfolio using the legacy v1 objective.

    For at most MAX_EXACT_ITEMS candidates, use deterministic exact
    branch-and-bound.

    Above that cutoff, use deterministic greedy selection and explicitly
    report that optimality has not been proven.

    Objective contribution per candidate:
        max(0, efficiency * cost_usd / 1_000_000)

    The public tuple-returning APIs remain available through
    greedy_portfolio() and knapsack_portfolio().
    """

    records, budget = _prepare(items, budget_usd)

    if len(records) > MAX_EXACT_ITEMS:
        return _greedy_selection(records, budget)

    best_value = float("-inf")
    best_indices: tuple[int, ...] = ()
    best_spent = 0.0

    def search(
        index: int,
        spent: float,
        value: float,
        chosen_indices: tuple[int, ...],
    ) -> None:
        nonlocal best_value, best_indices, best_spent

        if spent > budget:
            return

        if index == len(records):
            candidate_ids = tuple(records[position][1] for position in chosen_indices)
            best_ids = tuple(records[position][1] for position in best_indices)

            # Maximize objective value. For exact ties, choose the
            # lexicographically smaller deterministic ID sequence.
            if value > best_value or (value == best_value and candidate_ids < best_ids):
                best_value = value
                best_indices = chosen_indices
                best_spent = spent

            return

        # Fractional upper bound for branch-and-bound pruning.
        # Candidates are already ordered by descending efficiency.
        upper_bound = value
        remaining_budget = budget - spent

        for position in range(index, len(records)):
            _, _, cost_usd, _, contribution = records[position]

            if contribution == 0.0:
                continue

            if cost_usd <= remaining_budget:
                remaining_budget -= cost_usd
                upper_bound += contribution
            elif cost_usd > 0.0:
                upper_bound += contribution * (remaining_budget / cost_usd)
                break

        if upper_bound < best_value:
            return

        # Branch 1: do not select the current candidate.
        search(
            index + 1,
            spent,
            value,
            chosen_indices,
        )

        # Branch 2: select the current candidate if it remains feasible.
        current_cost = records[index][2]

        if current_cost <= budget - spent:
            search(
                index + 1,
                spent + current_cost,
                value + records[index][4],
                (*chosen_indices, index),
            )

    search(
        index=0,
        spent=0.0,
        value=0.0,
        chosen_indices=(),
    )

    selected_items = tuple(records[index][0] for index in best_indices)

    return PortfolioSelection(
        selected_items=selected_items,
        spent_usd=best_spent,
        objective_value=best_value,
        solver_mode="exact_branch_and_bound",
        status="optimal_reference",
    )


def greedy_portfolio[T: PortfolioItem](
    items: Sequence[T],
    budget_usd: float,
) -> tuple[tuple[T, ...], float]:
    """Legacy deterministic greedy selection API.

    Retains the original public return shape:
        (selected_items, spent_usd)
    """

    records, budget = _prepare(items, budget_usd)
    result = _greedy_selection(records, budget)

    return result.selected_items, result.spent_usd


def knapsack_portfolio[T: PortfolioItem](
    items: Sequence[T],
    budget_usd: float,
) -> tuple[tuple[T, ...], float]:
    """Legacy v1 portfolio selection API.

    Retains the original public return shape:
        (selected_items, spent_usd)

    Uses exact branch-and-bound up to the established 28-item cutoff,
    then deterministic greedy fallback.
    """

    result = select_portfolio(items, budget_usd)

    return result.selected_items, result.spent_usd
