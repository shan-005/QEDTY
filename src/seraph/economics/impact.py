from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .io import IOModel


def indirect_loss(io: IOModel, final_demand_loss: tuple[float, ...]) -> float:
    if not final_demand_loss:
        return 0.0
    if any(x < 0 for x in final_demand_loss):
        raise ValueError("final demand loss must be non-negative")
    induced_output_loss = io.total_output(final_demand_loss)
    direct = sum(final_demand_loss)
    return max(0.0, sum(induced_output_loss) - direct)


def production_loss(
    io: IOModel, baseline_demand: tuple[float, ...], loss_fraction: tuple[float, ...]
) -> float:
    if len(baseline_demand) != len(loss_fraction):
        raise ValueError("shock vector mismatch")
    if any(not 0 <= x <= 1 for x in loss_fraction):
        raise ValueError("loss fractions must be in [0,1]")
    base = sum(io.total_output(baseline_demand))
    stressed = sum(io.output_from_demand_shock(baseline_demand, loss_fraction))
    return max(0.0, base - stressed)
