"""SERAPH-PCI-X deterministic resilience optimization layer."""

from typing import Any

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
    if name in {"OptimizationResult", "RankedIntervention"}:
        from .models import OptimizationResult, RankedIntervention

        return {"OptimizationResult": OptimizationResult, "RankedIntervention": RankedIntervention}[
            name
        ]
    if name in {"cvar", "efficiency", "weighted_score"}:
        from .objectives import cvar, efficiency, weighted_score

        return {"cvar": cvar, "efficiency": efficiency, "weighted_score": weighted_score}[name]
    if name in {"greedy_portfolio", "knapsack_portfolio"}:
        from .portfolio import greedy_portfolio, knapsack_portfolio

        return {"greedy_portfolio": greedy_portfolio, "knapsack_portfolio": knapsack_portfolio}[
            name
        ]
    if name in {"cvar_score", "robust_floor"}:
        from .robustness import cvar_score, robust_floor

        return {"cvar_score": cvar_score, "robust_floor": robust_floor}[name]
    raise AttributeError(name)
