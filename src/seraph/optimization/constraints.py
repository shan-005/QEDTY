from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from seraph.scenarios.models import Intervention


@dataclass(frozen=True, slots=True)
class BudgetConstraint:
    budget_usd: float
    fixed_overhead_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.budget_usd < 0 or self.fixed_overhead_usd < 0:
            raise ValueError("budget and fixed overhead must be non-negative")

    def permits(self, cost_usd: float, spent_usd: float = 0.0) -> bool:
        if cost_usd < 0 or spent_usd < 0:
            return False
        return spent_usd + cost_usd + self.fixed_overhead_usd <= self.budget_usd


def feasible(intervention: Intervention, budget_usd: float) -> bool:
    if budget_usd < 0 or intervention.cost_usd < 0:
        return False
    return intervention.cost_usd <= budget_usd
