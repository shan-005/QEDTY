from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class SnaMeasure:
    concept: str
    value: float
    currency: str
    period: str
    source_uri: str
    unit_scale: str = "1"
    evidence_id: str = ""

    def __post_init__(self) -> None:
        if not self.concept.strip() or not self.currency.strip() or not self.period.strip():
            raise ValueError("concept, currency and period are required")
        if not isfinite(self.value):
            raise ValueError("value must be finite")

    def normalized(self) -> dict[str, object]:
        return {
            "concept": self.concept,
            "value": self.value,
            "currency": self.currency.upper(),
            "period": self.period,
            "source_uri": self.source_uri,
            "unit_scale": self.unit_scale,
            "evidence_id": self.evidence_id,
        }
