from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True, slots=True)
class ImpactScore:
    structural: float
    continuity: float
    economic: float
    combined: float
    confidence: float = 1.0


def combine(
    structural: float, continuity: float, economic: float, *, confidence: float = 1.0
) -> ImpactScore:
    vals = (structural, continuity, economic)
    if any(v < 0 or not v == v for v in vals):
        raise ValueError("impact components must be non-negative and finite")
    if not 0 <= confidence <= 1:
        raise ValueError("confidence out of range")
    # Root-mean-square rewards large impacts but remains monotone in each component.
    combined = sqrt(sum(v * v for v in vals) / 3.0)
    return ImpactScore(*vals, combined, confidence)
