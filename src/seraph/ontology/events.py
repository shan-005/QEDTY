from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from seraph.core.enums import EpistemicStatus, EventType
from seraph.core.hash import deterministic_id
from seraph.core.time import ensure_utc


class WorldEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    event_id: str = Field(min_length=1, max_length=256)
    event_type: EventType
    name: str = Field(min_length=1, max_length=512)
    starts_at: datetime
    ends_at: datetime | None = None
    severity: float = Field(ge=0, le=1)
    source_entity_ids: tuple[str, ...] = ()
    affected_entity_ids: tuple[str, ...] = ()
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid(self):
        object.__setattr__(self, "starts_at", ensure_utc(self.starts_at))
        if self.ends_at is not None:
            object.__setattr__(self, "ends_at", ensure_utc(self.ends_at))
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("event interval invalid")
        expected = deterministic_id(
            "event",
            self.name,
            self.event_type.value,
            self.starts_at.isoformat(),
            self.ends_at.isoformat() if self.ends_at else None,
            self.severity,
        )
        if self.event_id != expected:
            raise ValueError("event_id mismatch")
        return self
