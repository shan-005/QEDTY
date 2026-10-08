from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qedty.core.enums import EpistemicStatus, EvidenceStatus
from qedty.core.hash import canonical_json, deterministic_id
from qedty.core.time import ensure_utc
from qedty.core.types import EntityRef, EvidenceRef, ProvenanceRef, SourceRef, TimeWindow

from .licensing import DEFAULT_UNKNOWN, LicensePolicy
from .quality import DataQuality

if TYPE_CHECKING:
    from datetime import datetime

    from .acquisition import AcquisitionReceipt
    from .selectors import EvidenceSelector


class EvidenceKind(StrEnum):
    DATASET = "dataset"
    DOCUMENT = "document"
    API_RESPONSE = "api_response"
    DATABASE_EXPORT = "database_export"
    SENSOR_OBSERVATION = "sensor_observation"
    MEASUREMENT = "measurement"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    REPORT = "report"
    CODE_ARTIFACT = "code_artifact"
    MESSAGE = "message"
    OTHER = "other"


class EvidenceRecord(BaseModel):
    """Canonical immutable evidence descriptor; bytes live in a content-addressed store."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    evidence_id: str = Field(min_length=1, max_length=256)
    source: SourceRef
    source_uri: str = Field(min_length=1, max_length=4096)
    title: str | None = Field(default=None, max_length=1024)
    kind: EvidenceKind = EvidenceKind.OTHER
    status: EvidenceStatus = EvidenceStatus.ACQUIRED
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_type: str = Field(default="application/octet-stream", min_length=1, max_length=256)
    content_length_bytes: int = Field(default=0, ge=0)
    encoding: str | None = Field(default=None, max_length=128)
    retrieved_at: datetime
    observed_at: datetime | None = None
    valid_time: TimeWindow | None = None
    acquisition: AcquisitionReceipt | None = None
    quality: DataQuality = Field(default_factory=DataQuality)
    license_policy: LicensePolicy = Field(default=DEFAULT_UNKNOWN)
    about_entities: tuple[EntityRef, ...] = ()
    selectors: tuple[EvidenceSelector, ...] = ()
    provenance_ids: tuple[ProvenanceRef, ...] = ()
    parser_name: str | None = Field(default=None, max_length=256)
    parser_version: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("retrieved_at", "observed_at")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @model_validator(mode="after")
    def valid(self) -> Self:
        if (
            self.valid_time is not None
            and self.observed_at is not None
            and not self.valid_time.contains(self.observed_at)
        ):
            raise ValueError("observed_at must fall within valid_time")
        if self.acquisition is not None:
            if self.acquisition.content_sha256 != self.content_sha256:
                raise ValueError("acquisition/content digest mismatch")
            if self.acquisition.response_size_bytes != self.content_length_bytes:
                raise ValueError("acquisition/content length mismatch")
        expected = deterministic_id(
            "evidence",
            self.source_uri,
            self.content_sha256,
            self.content_type,
            self.content_length_bytes,
            self.observed_at.isoformat() if self.observed_at else None,
        )
        if self.evidence_id != expected:
            raise ValueError("evidence_id mismatch")
        return self

    @property
    def source_name(self) -> str:
        """Compatibility accessor for the source registry identifier."""
        return self.source.source_id

    @property
    def valid_from(self) -> datetime | None:
        return self.valid_time.start if self.valid_time is not None else None

    @property
    def valid_to(self) -> datetime | None:
        return self.valid_time.end if self.valid_time is not None else None

    @property
    def evidence_ref(self) -> EvidenceRef:
        return EvidenceRef(evidence_id=self.evidence_id)

    @property
    def content_address(self) -> str:
        return f"sha256:{self.content_sha256}"

    @property
    def is_reusable(self) -> bool:
        return self.status not in {EvidenceStatus.REJECTED, EvidenceStatus.DEPRECATED}

    def canonical_metadata(self) -> str:
        return canonical_json(self.model_dump(mode="json"))

    @classmethod
    def from_content(
        cls,
        *,
        source: SourceRef,
        source_uri: str,
        content: bytes,
        retrieved_at: datetime,
        content_type: str = "application/octet-stream",
        title: str | None = None,
        kind: EvidenceKind = EvidenceKind.OTHER,
        observed_at: datetime | None = None,
        valid_time: TimeWindow | None = None,
        acquisition: AcquisitionReceipt | None = None,
        quality: DataQuality | None = None,
        license_policy: LicensePolicy = DEFAULT_UNKNOWN,
        about_entities: tuple[EntityRef, ...] = (),
        selectors: tuple[EvidenceSelector, ...] = (),
        provenance_ids: tuple[ProvenanceRef, ...] = (),
        parser_name: str | None = None,
        parser_version: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Self:
        import hashlib

        digest = hashlib.sha256(content).hexdigest()
        normalized_observed = ensure_utc(observed_at) if observed_at else None
        return cls(
            evidence_id=deterministic_id(
                "evidence",
                source_uri,
                digest,
                content_type,
                len(content),
                normalized_observed.isoformat() if normalized_observed else None,
            ),
            source=source,
            source_uri=source_uri,
            title=title,
            kind=kind,
            content_sha256=digest,
            content_type=content_type,
            content_length_bytes=len(content),
            retrieved_at=ensure_utc(retrieved_at),
            observed_at=normalized_observed,
            valid_time=valid_time,
            acquisition=acquisition,
            quality=quality or DataQuality(),
            license_policy=license_policy,
            about_entities=about_entities,
            selectors=selectors,
            provenance_ids=provenance_ids,
            parser_name=parser_name,
            parser_version=parser_version,
            metadata=metadata or {},
        )
