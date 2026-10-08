from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qedty.core.hash import canonical_json, deterministic_id
from qedty.core.time import ensure_utc

from .schema import normalize_iri, normalize_text
from .terms import AssertionKind

if TYPE_CHECKING:
    from datetime import datetime

    from qedty.core.enums import EpistemicStatus
    from qedty.core.types import EntityRef, SourceRef, TimeWindow


class Assertion(BaseModel):
    """Epistemically qualified semantic statement with explicit subject/object/value."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    assertion_id: str = Field(min_length=1, max_length=256)
    subject: EntityRef
    predicate: str = Field(min_length=1, max_length=1024)
    object_entity: EntityRef | None = None
    value: Any = None
    kind: AssertionKind
    asserted_at: datetime
    valid_time: TimeWindow | None = None
    epistemic_status: EpistemicStatus
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    source: SourceRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("predicate")
    @classmethod
    def predicate_valid(cls, value: str) -> str:
        candidate = normalize_text(value, max_length=1024)
        if candidate.startswith(("http://", "https://", "urn:")):
            return normalize_iri(candidate)
        if ":" in candidate and all(part.strip() for part in candidate.split(":", 1)):
            return candidate
        raise ValueError("predicate must be an absolute IRI or CURIE")

    @field_validator("asserted_at")
    @classmethod
    def asserted_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def semantic_shape(self) -> Self:
        if self.kind == AssertionKind.RELATIONSHIP and self.object_entity is None:
            raise ValueError("relationship assertions require object_entity")
        if self.kind != AssertionKind.RELATIONSHIP and self.object_entity is not None:
            raise ValueError("non-relationship assertions must not carry object_entity")
        value_token = canonical_json(self.value) if self.object_entity is None else None
        expected = deterministic_id(
            "assertion",
            self.subject.entity_id,
            self.predicate,
            self.object_entity.entity_id if self.object_entity else None,
            value_token,
            self.kind.value,
            self.valid_time.start.isoformat() if self.valid_time else None,
            self.valid_time.end.isoformat() if self.valid_time else None,
        )
        if self.assertion_id != expected:
            raise ValueError("assertion_id mismatch")
        return self

    @property
    def subject_id(self) -> str:
        return self.subject.entity_id

    @property
    def object_id(self) -> str | None:
        return None if self.object_entity is None else self.object_entity.entity_id
