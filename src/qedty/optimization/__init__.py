"""QEDTY deterministic resilience optimization layer."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .engine import ResilienceOptimizer
    from .models import OptimizationResult, RankedIntervention
    from .objectives import cvar, efficiency, weighted_score
    from .portfolio import greedy_portfolio, knapsack_portfolio
    from .robustness import cvar_score, robust_floor

__all__ = [
    "OptimizationResult",
    "RankedIntervention",
    "ResilienceOptimizer",
    "cvar",
    "cvar_score",
    "efficiency",
    "greedy_portfolio",
    "knapsack_portfolio",
    "robust_floor",
    "weighted_score",
]


def __getattr__(name: str) -> Any:
    if name == "ResilienceOptimizer":
        from .engine import ResilienceOptimizer

        return ResilienceOptimizer
    if name == "OptimizationResult":
        from .models import OptimizationResult

        return OptimizationResult
    if name == "RankedIntervention":
        from .models import RankedIntervention

        return RankedIntervention
    if name == "cvar":
        from .objectives import cvar

        return cvar
    if name == "efficiency":
        from .objectives import efficiency

        return efficiency
    if name == "weighted_score":
        from .objectives import weighted_score

        return weighted_score
    if name == "greedy_portfolio":
        from .portfolio import greedy_portfolio

        return greedy_portfolio
    if name == "knapsack_portfolio":
        from .portfolio import knapsack_portfolio

        return knapsack_portfolio
    if name == "cvar_score":
        from .robustness import cvar_score

        return cvar_score
    if name == "robust_floor":
        from .robustness import robust_floor

        return robust_floor
    raise AttributeError(name)
