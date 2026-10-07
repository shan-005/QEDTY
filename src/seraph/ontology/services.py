from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from seraph.core.enums import EpistemicStatus
from seraph.core.hash import deterministic_id
from seraph.core.time import ensure_utc
from seraph.core.types import EntityRef, TimeWindow

from .schema import normalize_text

if TYPE_CHECKING:
    from datetime import datetime


class Service(BaseModel):
    """Deliverable world function backed by providers and declared capabilities."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    service_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    namespace: str = Field(default="seraph", min_length=1, max_length=128)
    provider_entity_ids: tuple[str, ...] = ()
    capability_ids: tuple[str, ...] = ()
    dependency_relationship_ids: tuple[str, ...] = ()
    criticality: float = Field(default=0.5, ge=0, le=1)
    availability_target: float = Field(default=0.99, ge=0, le=1)
    geographic_scope: tuple[str, ...] = ()
    valid_time: TimeWindow | None = None
    observed_at: datetime | None = None
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "namespace")
    @classmethod
    def text_normalized(cls, value: str) -> str:
        return normalize_text(value, max_length=256)

    @field_validator("observed_at")
    @classmethod
    def observed_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @model_validator(mode="after")
    def identity(self) -> Self:
        if not self.provider_entity_ids and not self.capability_ids:
            raise ValueError("service must declare at least one provider or capability")
        expected = deterministic_id("service", self.namespace, self.name.casefold())
        if self.service_id != expected:
            raise ValueError("service_id mismatch")
        if len(self.provider_entity_ids) != len(set(self.provider_entity_ids)):
            raise ValueError("provider_entity_ids must be unique")
        if len(self.capability_ids) != len(set(self.capability_ids)):
            raise ValueError("capability_ids must be unique")
        return self

    @property
    def providers(self) -> tuple[EntityRef, ...]:
        return tuple(EntityRef(entity_id=item) for item in self.provider_entity_ids)

    @property
    def validity(self) -> TimeWindow | None:
        return self.valid_time
