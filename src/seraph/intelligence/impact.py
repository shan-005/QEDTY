from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImpactScore:
    structural: float
    continuity: float
    economic: float
    combined: float


def combine(structural: float, continuity: float, economic: float) -> ImpactScore:
    vals = (structural, continuity, economic)
    if any(v < 0 for v in vals):
        raise ValueError("impact components must be non-negative")
    return ImpactScore(*vals, (structural + continuity + economic) / 3)
