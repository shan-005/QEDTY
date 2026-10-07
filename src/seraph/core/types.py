from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import EpistemicStatus
from .errors import ContractError
from .hash import deterministic_id
from .time import ensure_utc, seconds

if TYPE_CHECKING:
    from datetime import datetime

    from .enums import EpistemicStatus

type Identifier = str
type CanonicalName = str


def _validate_nonblank(value: str, field_name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ContractError(f"{field_name} must not be blank")
    return normalized


class EntityRef(BaseModel):
    """Stable reference to a world-model entity."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    entity_id: str = Field(min_length=1, max_length=256)


class RelationshipRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    relationship_id: str = Field(min_length=1, max_length=256)


class EventRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    event_id: str = Field(min_length=1, max_length=256)


class EvidenceRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    evidence_id: str = Field(min_length=1, max_length=256)


class AssertionRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    assertion_id: str = Field(min_length=1, max_length=256)
    status: EpistemicStatus


class ClaimRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    claim_id: str = Field(min_length=1, max_length=256)


class ProvenanceRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    provenance_id: str = Field(min_length=1, max_length=256)


class RunRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    run_id: str = Field(min_length=1, max_length=256)


class SourceRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    source_id: str = Field(min_length=1, max_length=256)


class ScenarioRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    scenario_id: str = Field(min_length=1, max_length=256)


class ExternalIdentifier(BaseModel):
    """Identifier in an external namespace; never conflated with SERAPH ID."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    namespace: str = Field(min_length=1, max_length=256)
    value: str = Field(min_length=1, max_length=1024)

    @field_validator("namespace", "value", mode="before")
    @classmethod
    def normalize(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ContractError("external identifier components must not be blank")
        return normalized


class TimeWindow(BaseModel):
    """Strict UTC-normalized half-open interval ``[start, end)``."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end <= self.start:
            raise ContractError("end must be after start")
        return self

    @property
    def duration_seconds(self) -> float:
        return seconds(self.start, self.end)

    @property
    def duration_hours(self) -> float:
        return self.duration_seconds / 3600.0

    def contains(self, instant: datetime) -> bool:
        t = ensure_utc(instant)
        return self.start <= t < self.end

    def overlaps(self, other: TimeWindow) -> bool:
        return self.start < other.end and other.start < self.end

    def intersection(self, other: TimeWindow) -> TimeWindow | None:
        if not self.overlaps(other):
            return None
        return TimeWindow(start=max(self.start, other.start), end=min(self.end, other.end))

    def shift(self, seconds_delta: float) -> TimeWindow:
        from .time import add_seconds

        return TimeWindow(
            start=add_seconds(self.start, seconds_delta),
            end=add_seconds(self.end, seconds_delta),
        )


class DeterministicKey(BaseModel):
    """Explicit namespace/value pair used to construct stable identities."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    namespace: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=256)

    @field_validator("namespace", "value")
    @classmethod
    def normalize(cls, value: str) -> str:
        return _validate_nonblank(value, "key component")

    @property
    def id(self) -> str:
        return deterministic_id(self.namespace, self.value)
