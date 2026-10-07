"""Canonical world entities and entity resolution contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from seraph.core.enums import EntityType, EpistemicStatus
from seraph.core.hash import deterministic_id
from seraph.core.time import ensure_utc
from seraph.core.types import EntityRef, ExternalIdentifier, TimeWindow

from .schema import normalize_iri, normalize_text
from .terms import EntityLifecycle, ResolutionDecision, ResolutionMethod

if TYPE_CHECKING:
    from datetime import datetime

    from seraph.core.geometry import GeodeticPoint


class Entity(BaseModel):
    """Canonical world entity with stable identity, lifecycle and provenance hooks."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    entity_id: str = Field(min_length=1, max_length=256)
    entity_type: EntityType
    canonical_name: str = Field(min_length=1, max_length=512)
    namespace: str = Field(default="seraph", min_length=1, max_length=128)
    aliases: tuple[str, ...] = ()
    external_identifiers: tuple[ExternalIdentifier, ...] = ()
    ontology_types: tuple[str, ...] = ()
    description: str | None = Field(default=None, max_length=4096)
    valid_time: TimeWindow | None = None
    observed_at: datetime | None = None
    location: GeodeticPoint | None = None
    latitude: float | None = None
    longitude: float | None = None
    lifecycle: EntityLifecycle = EntityLifecycle.UNKNOWN
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("canonical_name")
    @classmethod
    def canonical_name_normalized(cls, value: str) -> str:
        return normalize_text(value, max_length=512)

    @field_validator("namespace")
    @classmethod
    def namespace_normalized(cls, value: str) -> str:
        return normalize_text(value, max_length=128)

    @field_validator("aliases")
    @classmethod
    def aliases_normalized(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = {normalize_text(item, max_length=512) for item in value}
        return tuple(sorted(normalized, key=str.casefold))

    @field_validator("ontology_types")
    @classmethod
    def ontology_types_valid(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({normalize_iri(item) for item in value}))

    @field_validator("observed_at")
    @classmethod
    def observed_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        keys = [(item.namespace, item.value) for item in self.external_identifiers]
        if len(keys) != len(set(keys)):
            raise ValueError("external_identifiers must be unique")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        expected = deterministic_id(
            "entity",
            self.namespace,
            self.entity_type.value,
            self.canonical_name.casefold(),
        )
        if self.entity_id != expected:
            raise ValueError("entity_id does not match canonical identity")
        return self

    @property
    def external_id_keys(self) -> tuple[str, ...]:
        return tuple(sorted(f"{item.namespace}:{item.value}" for item in self.external_identifiers))

    @property
    def valid_from(self) -> datetime | None:
        return None if self.valid_time is None else self.valid_time.start

    @property
    def valid_to(self) -> datetime | None:
        return None if self.valid_time is None else self.valid_time.end

    def ref(self) -> EntityRef:
        return EntityRef(entity_id=self.entity_id)


class EntityResolution(BaseModel):
    """Evidence-qualified mapping from an external identifier to a canonical entity."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    resolution_id: str = Field(min_length=1, max_length=256)
    entity_id: str = Field(min_length=1, max_length=256)
    external_identifier: ExternalIdentifier
    method: ResolutionMethod
    decision: ResolutionDecision
    score: float = Field(ge=0, le=1)
    resolver: str = Field(min_length=1, max_length=256)
    resolved_at: datetime
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    rationale: str | None = Field(default=None, max_length=4096)

    @field_validator("resolved_at")
    @classmethod
    def resolved_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @field_validator("resolver")
    @classmethod
    def resolver_normalized(cls, value: str) -> str:
        return normalize_text(value, max_length=256)

    @model_validator(mode="after")
    def identity(self) -> Self:
        expected = deterministic_id(
            "entity-resolution",
            self.entity_id,
            self.external_identifier.namespace,
            self.external_identifier.value,
            self.method.value,
            self.decision.value,
        )
        if self.resolution_id != expected:
            raise ValueError("resolution_id does not match canonical identity")
        if self.decision == ResolutionDecision.ACCEPTED and self.score <= 0:
            raise ValueError("accepted resolutions require a positive score")
        return self
