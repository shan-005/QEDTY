from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Quantity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    value: Decimal
    unit: str = Field(min_length=1, max_length=64)

    def __mul__(self, factor: int | float | Decimal) -> "Quantity":
        return Quantity(value=self.value * Decimal(str(factor)), unit=self.unit)

    def __truediv__(self, factor: int | float | Decimal) -> "Quantity":
        if factor == 0:
            raise ZeroDivisionError("cannot divide a quantity by zero")
        return Quantity(value=self.value / Decimal(str(factor)), unit=self.unit)
