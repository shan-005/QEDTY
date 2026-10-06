from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Account:
    entity_id: str
    value_usd: float
    period: str
    measure: str

    def validate(self) -> None:
        if self.value_usd < 0:
            raise ValueError("account value must be non-negative")
