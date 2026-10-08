from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Money:
    value: float
    currency: str = "USD"

    def validate(self) -> None:
        if self.value < 0:
            raise ValueError("negative monetary amount")
        if len(self.currency) != 3:
            raise ValueError("currency must be ISO-4217-like three letters")

    def rounded(self, digits: int = 2) -> Money:
        self.validate()
        return Money(round(self.value, digits), self.currency)


def usd(value: float) -> float:
    if value < 0:
        raise ValueError("negative monetary amount")
    return round(value, 2)
