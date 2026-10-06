from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from seraph.core.enums import EpistemicStatus
from seraph.core.hash import deterministic_id
from seraph.core.time import ensure_utc
from seraph.evidence.licensing import DEFAULT_UNKNOWN, LicensePolicy
from seraph.evidence.quality import DataQuality


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    evidence_id: str = Field(min_length=1, max_length=256)
    source_name: str = Field(min_length=1, max_length=256)
    source_uri: str = Field(min_length=1, max_length=4096)
    retrieved_at: datetime
    observed_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_type: str = Field(default="application/octet-stream", min_length=1, max_length=128)
    payload_size_bytes: int = Field(default=0, ge=0)
    parser_version: str = Field(default="1.0.0", min_length=1, max_length=64)
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    quality: DataQuality = Field(default_factory=DataQuality)
    license_policy: LicensePolicy = Field(default=DEFAULT_UNKNOWN)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_record(self) -> "EvidenceRecord":
        for name in ("retrieved_at", "observed_at", "valid_from", "valid_to"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, ensure_utc(value))
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        expected = deterministic_id(
            "evidence",
            self.source_uri,
            self.content_sha256,
            self.observed_at.isoformat() if self.observed_at else None,
        )
        if self.evidence_id != expected:
            raise ValueError("evidence_id does not match content/source identity")
        return self
