from __future__ import annotations

from .io import IOModel


def indirect_loss(io: IOModel, final_demand_loss: tuple[float, ...]) -> float:
    baseline = io.total_output(tuple(0 for _ in final_demand_loss))
    stressed = io.total_output(final_demand_loss)
    return max(0.0, sum(baseline) - sum(stressed))
