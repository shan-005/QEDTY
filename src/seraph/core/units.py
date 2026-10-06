from __future__ import annotations
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
class Quantity(BaseModel):
    model_config=ConfigDict(frozen=True, extra="forbid", strict=True)
    value: Decimal
    unit: str=Field(min_length=1,max_length=64)
    def scaled(self,factor:int|float|Decimal)->"Quantity": return Quantity(value=self.value*Decimal(str(factor)),unit=self.unit)
