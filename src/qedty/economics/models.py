from __future__ import annotations

from math import isfinite
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EconomicExposure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    entity_id: str
    reference_value_usd: float = Field(gt=0)
    reference_period_days: float = Field(gt=0)
    exposed_fraction: float = Field(ge=0, le=1)
    pass_through: float = Field(default=1, ge=0, le=2)
    value_added_ratio: float = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def finite(self) -> Self:
        if not all(
            isfinite(v)
            for v in (
                self.reference_value_usd,
                self.reference_period_days,
                self.exposed_fraction,
                self.pass_through,
                self.value_added_ratio,
            )
        ):
            raise ValueError("economic inputs must be finite")
        return self


class EconomicImpact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    entity_id: str
    direct_loss_usd: float = Field(ge=0)
    indirect_loss_usd: float = Field(ge=0)
    total_loss_usd: float = Field(ge=0)
    methodology: str
    assumptions: tuple[str, ...] = ()
    value_added_loss_usd: float = Field(default=0, ge=0)
    displaced_output_usd: float = Field(default=0, ge=0)
    reference_currency: str = "USD"
    model_digest: str | None = None
