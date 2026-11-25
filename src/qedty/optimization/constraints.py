from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qedty.scenarios.models import Intervention


def _valid_nonnegative(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False

    number = float(value)
    return isfinite(number) and number >= 0.0


@dataclass(frozen=True, slots=True)
class BudgetConstraint:
    budget_usd: float
    fixed_overhead_usd: float = 0.0

    def __post_init__(self) -> None:
        if not _valid_nonnegative(self.budget_usd):
            raise ValueError("budget must be finite and non-negative")

        if not _valid_nonnegative(self.fixed_overhead_usd):
            raise ValueError("fixed overhead must be finite and non-negative")

    def permits(self, cost_usd: float, spent_usd: float = 0.0) -> bool:
        if not all(_valid_nonnegative(value) for value in (cost_usd, spent_usd)):
            return False

        return spent_usd + cost_usd + self.fixed_overhead_usd <= self.budget_usd


def feasible(intervention: Intervention, budget_usd: float) -> bool:
    if not _valid_nonnegative(budget_usd):
        return False

    if not _valid_nonnegative(intervention.cost_usd):
        return False

    return intervention.cost_usd <= budget_usd
