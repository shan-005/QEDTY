from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SubstituteOption:
    entity_id: str
    available_fraction: float = 1.0
    coverage_fraction: float = 1.0
    efficiency_fraction: float = 1.0

    def validate(self) -> None:
        for name in ("available_fraction", "coverage_fraction", "efficiency_fraction"):
            v = getattr(self, name)
            if not 0 <= v <= 1:
                raise ValueError(f"{name} must be in [0,1]")


def effective_capacity(
    base: float, substitutable_fraction: float, substitute_capacity: float
) -> float:
    if (
        not 0 <= base <= 1
        or not 0 <= substitutable_fraction <= 1
        or not 0 <= substitute_capacity <= 1
    ):
        raise ValueError("capacity inputs must be in [0,1]")
    return max(0.0, min(1.0, base + substitutable_fraction * substitute_capacity))


def portfolio_capacity(base: float, options: tuple[SubstituteOption, ...]) -> float:
    if not 0 <= base <= 1:
        raise ValueError("base must be in [0,1]")
    residual = 1.0 - base
    gain = 0.0
    for option in options:
        option.validate()
        gain += (
            residual
            * option.available_fraction
            * option.coverage_fraction
            * option.efficiency_fraction
        )
    return min(1.0, base + gain)
