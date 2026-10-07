from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class Account:
    entity_id: str
    value_usd: float
    period: str
    measure: str
    source_id: str | None = None

    def validate(self) -> None:
        if self.value_usd < 0 or not isfinite(self.value_usd):
            raise ValueError("account value must be non-negative and finite")
        if not self.period.strip() or not self.measure.strip():
            raise ValueError("period and measure must not be blank")
