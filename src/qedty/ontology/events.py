"""Canonical world events with explicit temporal extent, impact and affected entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qedty.core.enums import EpistemicStatus, EventType
from qedty.core.hash import deterministic_id

from .schema import normalize_text
from .terms import EventPhase

if TYPE_CHECKING:
    from datetime import datetime

    from qedty.core.geometry import GeodeticPoint
    from qedty.core.types import TimeWindow


class WorldEvent(BaseModel):
    """World occurrence with explicit temporal extent, impact and affected entities."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    event_id: str = Field(min_length=1, max_length=256)
    event_type: EventType
    name: str = Field(min_length=1, max_length=512)
    time: TimeWindow
    severity: float = Field(ge=0, le=1)
    impact_fraction: float = Field(default=1.0, ge=0, le=1)
    source_entity_ids: tuple[str, ...] = ()
    affected_entity_ids: tuple[str, ...] = ()
    location: GeodeticPoint | None = None
    phase: EventPhase = EventPhase.UNKNOWN
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_normalized(cls, value: str) -> str:
        return normalize_text(value, max_length=512)

    @model_validator(mode="after")
    def identity(self) -> Self:
        expected = deterministic_id(
            "event",
            self.name,
            self.event_type.value,
            self.time.start.isoformat(),
            self.time.end.isoformat(),
            self.severity,
        )
        if self.event_id != expected:
            raise ValueError("event_id mismatch")
        return self

    @property
    def starts_at(self) -> datetime:
        return self.time.start

    @property
    def ends_at(self) -> datetime:
        return self.time.end

    def affects(self, entity_id: str) -> bool:
        return entity_id in self.affected_entity_ids
