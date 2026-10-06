from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from seraph.core.enums import EpistemicStatus, RelationshipType
from seraph.core.hash import deterministic_id
from seraph.core.time import ensure_utc
from seraph.core.types import EntityRef


class Relationship(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    relationship_id: str = Field(min_length=1, max_length=256)
    source: EntityRef
    target: EntityRef
    relationship_type: RelationshipType
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime | None = None
    strength: float = Field(default=1.0, ge=0, le=1)
    capacity_fraction: float = Field(default=1.0, ge=0, le=1)
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    evidence_ids: tuple[str, ...] = ()
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_all(self):
        for name in ("valid_from", "valid_to", "observed_at"):
            v = getattr(self, name)
            if v is not None:
                object.__setattr__(self, name, ensure_utc(v))
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("invalid relationship interval")
        if (
            self.source.entity_id == self.target.entity_id
            and self.relationship_type != RelationshipType.MEMBER_OF
        ):
            raise ValueError("self relationship prohibited")
        expected = deterministic_id(
            "rel",
            self.source.entity_id,
            self.target.entity_id,
            self.relationship_type.value,
            self.valid_from.isoformat() if self.valid_from else None,
            self.valid_to.isoformat() if self.valid_to else None,
        )
        if self.relationship_id != expected:
            raise ValueError("relationship_id mismatch")
        return self
