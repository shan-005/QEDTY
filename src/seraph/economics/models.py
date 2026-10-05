from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EconomicExposure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    entity_id: str
    reference_value_usd: float = Field(gt=0.0)
    reference_period_days: float = Field(default=1.0, gt=0.0)
    exposed_fraction: float = Field(ge=0.0, le=1.0)
    transmission_elasticity: float = Field(default=1.0, ge=0.0)


class EconomicLoss(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    entity_id: str
    modeled_loss_usd: float = Field(ge=0.0)
    reference_exposure_usd: float = Field(ge=0.0)
    assumptions: tuple[str, ...]
