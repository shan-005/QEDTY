from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from seraph.core.ids import deterministic_id
from seraph.core.time import ensure_utc
from seraph.evidence.licensing import DEFAULT_UNKNOWN_LICENSE, LicensePolicy
from seraph.evidence.quality import DataQuality


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    evidence_id: str = Field(min_length=1, max_length=256)
    source_name: str = Field(min_length=1, max_length=256)
    source_uri: str = Field(min_length=1, max_length=4096)
    source_record_id: str | None = None
    retrieved_at: datetime
    observed_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    content_type: str = Field(default="application/json", min_length=1, max_length=128)
    quality: DataQuality = Field(default_factory=DataQuality)
    license_policy: LicensePolicy = Field(default=DEFAULT_UNKNOWN_LICENSE)
    parser_version: str = Field(default="1", min_length=1, max_length=64)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("retrieved_at", "observed_at", "valid_from", "valid_to")
    @classmethod
    def _timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @model_validator(mode="after")
    def _identity(self) -> "EvidenceRecord":
        expected = deterministic_id("evidence", self.source_uri, self.source_record_id, self.content_sha256, self.observed_at.isoformat() if self.observed_at else None)
        if self.evidence_id != expected:
            raise ValueError("evidence_id does not match deterministic evidence identity")
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        return self
