from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .models import EvidenceRecord

from qedty.core.hash import deterministic_id, sha256_hex
from qedty.core.time import ensure_utc


class AcquisitionMethod(StrEnum):
    HTTP = "http"
    HTTPS = "https"
    FILE = "file"
    OBJECT_STORE = "object_store"
    DATABASE = "database"
    API = "api"
    MANUAL = "manual"
    SENSOR = "sensor"
    OTHER = "other"


class AcquisitionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    method: AcquisitionMethod
    requested_uri: str = Field(min_length=1, max_length=4096)
    requested_at: datetime
    requester: str | None = Field(default=None, max_length=256)
    headers: tuple[tuple[str, str], ...] = ()

    @field_validator("requested_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @field_validator("headers")
    @classmethod
    def normalize_headers(cls, value: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]:
        normalized = tuple(sorted((name.strip().lower(), item.strip()) for name, item in value))
        if len({name for name, _ in normalized}) != len(normalized):
            raise ValueError("duplicate acquisition request header")
        return normalized

    @property
    def request_digest(self) -> str:
        return sha256_hex(self.model_dump(mode="json"))


class AcquisitionReceipt(BaseModel):
    """Immutable description of what was actually retrieved."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    acquisition_id: str = Field(min_length=1, max_length=256)
    method: AcquisitionMethod
    requested_uri: str = Field(min_length=1, max_length=4096)
    final_uri: str = Field(min_length=1, max_length=4096)
    retrieved_at: datetime
    status_code: int | None = Field(default=None, ge=100, le=599)
    response_media_type: str | None = Field(default=None, max_length=256)
    response_size_bytes: int = Field(default=0, ge=0)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    etag: str | None = Field(default=None, max_length=512)
    last_modified: str | None = Field(default=None, max_length=128)
    redirect_chain: tuple[str, ...] = ()
    response_headers: tuple[tuple[str, str], ...] = ()
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("retrieved_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def identity(self) -> AcquisitionReceipt:
        expected = deterministic_id(
            "acquisition",
            self.method.value,
            self.requested_uri,
            self.final_uri,
            self.retrieved_at.isoformat(),
            self.content_sha256,
            self.request_digest,
        )
        if self.acquisition_id != expected:
            raise ValueError("acquisition_id mismatch")
        return self


def make_receipt(
    request: AcquisitionRequest,
    *,
    final_uri: str,
    retrieved_at: datetime,
    content: bytes,
    status_code: int | None = None,
    response_media_type: str | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
    redirect_chain: tuple[str, ...] = (),
    response_headers: Mapping[str, str] | None = None,
) -> AcquisitionReceipt:
    import hashlib

    digest = hashlib.sha256(content).hexdigest()
    retrieved = ensure_utc(retrieved_at)
    normalized_headers = tuple(
        sorted((str(k).lower(), str(v).strip()) for k, v in (response_headers or {}).items())
    )
    identity = deterministic_id(
        "acquisition",
        request.method.value,
        request.requested_uri,
        final_uri,
        retrieved.isoformat(),
        digest,
        request.request_digest,
    )
    return AcquisitionReceipt(
        acquisition_id=identity,
        method=request.method,
        requested_uri=request.requested_uri,
        final_uri=final_uri,
        retrieved_at=retrieved,
        status_code=status_code,
        response_media_type=response_media_type,
        response_size_bytes=len(content),
        content_sha256=digest,
        etag=etag,
        last_modified=last_modified,
        redirect_chain=redirect_chain,
        response_headers=normalized_headers,
        request_digest=request.request_digest,
    )


class EvidenceAcquirer:
    """Reference acquisition recorder; transport is injected by callers."""

    def record_bytes(
        self,
        source_name: str,
        source_uri: str,
        payload: bytes,
        *,
        retrieved_at: datetime | None = None,
        content_type: str = "application/octet-stream",
        observed_at: datetime | None = None,
        method: AcquisitionMethod = AcquisitionMethod.OTHER,
        final_uri: str | None = None,
        status_code: int | None = None,
        headers: tuple[tuple[str, str], ...] = (),
        metadata: dict[str, str] | None = None,
    ) -> EvidenceRecord:
        from qedty.core.types import SourceRef

        from .models import EvidenceRecord

        retrieved = retrieved_at or datetime.now(UTC)
        request = AcquisitionRequest(
            method=method,
            requested_uri=source_uri,
            requested_at=retrieved,
            headers=headers,
        )
        receipt = make_receipt(
            request,
            final_uri=final_uri or source_uri,
            retrieved_at=retrieved,
            content=payload,
            status_code=status_code,
            response_media_type=content_type,
            response_headers=dict(headers),
        )
        return EvidenceRecord.from_content(
            source=SourceRef(source_id=source_name),
            source_uri=source_uri,
            content=payload,
            retrieved_at=retrieved,
            content_type=content_type,
            observed_at=observed_at,
            acquisition=receipt,
            metadata=metadata or {},
        )
