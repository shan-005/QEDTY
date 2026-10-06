from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from seraph.core.enums import EpistemicStatus, InterventionType


class Scenario(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    scenario_id: str
    name: str
    parent_scenario_id: str | None = None
    base_world_digest: str
    epistemic_status: EpistemicStatus = EpistemicStatus.MODELED
    assumptions: tuple[str, ...] = ()
    parameters: dict[str, float] = Field(default_factory=dict)
    capacities: dict[str, float] = Field(default_factory=dict)


class Intervention(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    intervention_id: str
    name: str
    intervention_type: InterventionType
    cost_usd: float = Field(ge=0)
    protected_entity_ids: tuple[str, ...] = ()
    transmission_reduction: float = Field(default=0, ge=0, le=1)
    capacity_gain: float = Field(default=0, ge=0, le=1)
    metadata: dict[str, str] = Field(default_factory=dict)
