from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EconomicExposure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    entity_id: str
    reference_value_usd: float = Field(gt=0)
    reference_period_days: float = Field(gt=0)
    exposed_fraction: float = Field(ge=0, le=1)
    pass_through: float = Field(default=1, ge=0, le=2)


class EconomicImpact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    entity_id: str
    direct_loss_usd: float = Field(ge=0)
    indirect_loss_usd: float = Field(ge=0)
    total_loss_usd: float = Field(ge=0)
    methodology: str
    assumptions: tuple[str, ...] = ()
