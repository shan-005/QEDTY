from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class PortfolioItem(Protocol):
    intervention_id: str
    cost_usd: float
    efficiency: float


def greedy_portfolio[T: PortfolioItem](
    items: Sequence[T], budget_usd: float
) -> tuple[tuple[T, ...], float]:
    chosen: list[T] = []
    spent = 0.0

    for item in sorted(items, key=lambda x: (-x.efficiency, x.intervention_id)):
        if spent + item.cost_usd <= budget_usd:
            chosen.append(item)
            spent += item.cost_usd

    return tuple(chosen), spent
