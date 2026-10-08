from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from collections.abc import Sequence


class PortfolioItem(Protocol):
    intervention_id: str
    cost_usd: float
    efficiency: float


T = TypeVar("T", bound=PortfolioItem)


def greedy_portfolio[T: PortfolioItem](
    items: Sequence[T], budget_usd: float
) -> tuple[tuple[T, ...], float]:
    if budget_usd < 0:
        raise ValueError("budget must be non-negative")
    chosen: list[T] = []
    spent = 0.0
    for item in sorted(items, key=lambda x: (-x.efficiency, x.intervention_id)):
        if item.cost_usd < 0:
            raise ValueError("negative item cost")
        if spent + item.cost_usd <= budget_usd:
            chosen.append(item)
            spent += item.cost_usd
    return tuple(chosen), spent


def knapsack_portfolio[T: PortfolioItem](
    items: Sequence[T], budget_usd: float
) -> tuple[tuple[T, ...], float]:
    """Exact 0/1 knapsack for the reference layer using deterministic branch-and-bound.

    Utility is ``efficiency * cost_millions`` so the optimizer can maximize total
    benefit while respecting a hard budget.  For large portfolios this function
    intentionally remains bounded by a deterministic item-count cutoff and falls
    back to the stable greedy solution.
    """
    if budget_usd < 0:
        raise ValueError("budget must be non-negative")
    ordered = tuple(sorted(items, key=lambda x: (-x.efficiency, x.intervention_id)))
    if len(ordered) > 28:
        return greedy_portfolio(ordered, budget_usd)
    best_value = -1.0
    best_indices: tuple[int, ...] = ()
    values = [max(0.0, float(x.efficiency * x.cost_usd / 1_000_000)) for x in ordered]
    costs = [float(x.cost_usd) for x in ordered]

    def search(i: int, spent: float, value: float, chosen: tuple[int, ...]) -> None:
        nonlocal best_value, best_indices
        if spent > budget_usd:
            return
        if i == len(ordered):
            ids = tuple(ordered[j].intervention_id for j in chosen)
            best_ids = tuple(ordered[j].intervention_id for j in best_indices)
            if value > best_value or (value == best_value and ids < best_ids):
                best_value, best_indices = value, chosen
            return
        # Simple fractional upper bound.
        bound = value
        remaining = budget_usd - spent
        for j in range(i, len(ordered)):
            if costs[j] <= remaining:
                remaining -= costs[j]
                bound += values[j]
            elif costs[j] > 0:
                bound += values[j] * remaining / costs[j]
                break
        if bound < best_value:
            return
        search(i + 1, spent, value, chosen)
        if costs[i] <= budget_usd - spent:
            search(i + 1, spent + costs[i], value + values[i], (*chosen, i))

    search(0, 0.0, 0.0, ())
    chosen = tuple(ordered[i] for i in best_indices)
    return chosen, sum(x.cost_usd for x in chosen)
