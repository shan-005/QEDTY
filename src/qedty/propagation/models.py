"""Canonical propagation result models.

Propagation converts explicit scenario shocks plus a temporal dependency graph into
modelled downstream effects.  It does not assign probabilities and it does not
promote a modelled effect to an observation.
"""

from __future__ import annotations

from enum import StrEnum
from math import isfinite
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qedty.core.hash import deterministic_id, sha256_hex
from qedty.core.time import ensure_utc

if TYPE_CHECKING:
    from datetime import datetime

    from qedty.core.enums import EpistemicStatus


class PropagationAggregation(StrEnum):
    """How independent path contributions to the same entity are combined."""

    MAX = "max"
    SUM_CAP = "sum_cap"
    NOISY_OR = "noisy_or"


class PropagationStatus(StrEnum):
    COMPLETE = "complete"
    TRUNCATED = "truncated"
    NO_INITIAL_SIGNAL = "no_initial_signal"


class PropagationEvent(BaseModel):
    """Canonical per-entity propagation outcome.

    The first seven fields preserve the historical QEDTY propagation contract;
    additional fields expose timing, provenance and aggregation semantics.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    entity_id: str = Field(min_length=1, max_length=256)
    impairment: float = Field(ge=0, le=1)
    depth: int = Field(ge=0)
    path_entity_ids: tuple[str, ...]
    path_relationship_ids: tuple[str, ...]
    effective_at: datetime
    status: EpistemicStatus
    source_shock_ids: tuple[str, ...] = ()
    parent_entity_id: str | None = None
    parent_relationship_id: str | None = None
    contribution: float = Field(default=0.0, ge=0, le=1)
    aggregation: PropagationAggregation = PropagationAggregation.MAX
    arrival_delay_seconds: float = Field(default=0.0, ge=0)
    method: str = "time-respecting-graph-propagation"
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("effective_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @field_validator("path_entity_ids")
    @classmethod
    def entities_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not item.strip() for item in value):
            raise ValueError("path_entity_ids must contain nonblank ids")
        return value

    @field_validator("path_relationship_ids")
    @classmethod
    def relationships_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ValueError("path_relationship_ids must contain nonblank ids")
        return value

    @field_validator("metadata")
    @classmethod
    def metadata_valid(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not key.strip() for key in value):
            raise ValueError("metadata keys must be nonblank")
        return dict(sorted(value.items()))

    @model_validator(mode="after")
    def valid(self) -> Self:
        if len(self.path_entity_ids) != len(self.path_relationship_ids) + 1:
            raise ValueError("path entity/relationship lengths are inconsistent")
        if self.parent_entity_id is not None and self.parent_entity_id not in self.path_entity_ids:
            raise ValueError("parent_entity_id must occur on the path")
        if (
            self.parent_relationship_id is not None
            and self.parent_relationship_id not in self.path_relationship_ids
        ):
            raise ValueError("parent_relationship_id must occur on the path")
        if not isfinite(self.arrival_delay_seconds):
            raise ValueError("arrival_delay_seconds must be finite")
        if self.contribution > self.impairment + 1e-12:
            raise ValueError("contribution cannot exceed aggregate impairment")
        return self


class PropagationEvidence(BaseModel):
    """Auditable explanation for a propagated entity effect."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    entity_id: str
    reason: str
    input_ids: tuple[str, ...] = ()
    method: str
    contribution: float = Field(ge=0, le=1)
    rank: int = Field(ge=1)
    path_entity_ids: tuple[str, ...]
    path_relationship_ids: tuple[str, ...]


class PropagationSummary(BaseModel):
    """Deterministic aggregate metadata for one propagation execution."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    status: PropagationStatus
    aggregation: PropagationAggregation
    event_count: int = Field(ge=0)
    reached_entity_count: int = Field(ge=0)
    max_depth: int = Field(ge=0)
    maximum_impairment: float = Field(ge=0, le=1)
    source_shock_ids: tuple[str, ...] = ()
    started_at: datetime | None = None
    terminal_at: datetime | None = None
    processed_signals: int = Field(ge=0)
    generated_signals: int = Field(ge=0)
    truncated: bool = False
    termination_reason: str
    rule_digest: str

    @field_validator("started_at", "terminal_at")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)


class PropagationResult(BaseModel):
    """Complete propagation artifact: events, evidence and summary."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    result_id: str
    events: tuple[PropagationEvent, ...]
    evidence: tuple[PropagationEvidence, ...] = ()
    summary: PropagationSummary

    @property
    def digest(self) -> str:
        return sha256_hex(self.model_dump(mode="json"))

    @property
    def deterministic_key(self) -> str:
        return deterministic_id("propagation-result", self.digest)
