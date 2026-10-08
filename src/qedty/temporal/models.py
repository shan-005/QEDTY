from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from qedty.core.enums import TimeScale
from qedty.core.hash import deterministic_id
from qedty.core.time import ensure_utc

if TYPE_CHECKING:
    from datetime import datetime

    from .intervals import TemporalExtent

T = TypeVar("T")


class TemporalInstant(BaseModel):
    """UTC-normalized instant with explicit source time-scale metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    at: datetime
    time_scale: TimeScale = TimeScale.UTC
    uncertainty_seconds: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def normalize(self) -> TemporalInstant:
        object.__setattr__(self, "at", ensure_utc(self.at))
        return self

    @property
    def unix_seconds(self) -> float:
        return self.at.timestamp()

    @classmethod
    def from_datetime(
        cls,
        at: datetime,
        *,
        time_scale: TimeScale = TimeScale.UTC,
        uncertainty_seconds: float = 0.0,
    ) -> TemporalInstant:
        return cls(at=at, time_scale=time_scale, uncertainty_seconds=uncertainty_seconds)


class TemporalWindow(BaseModel):
    """A query window with an explicit semantic purpose."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    extent: TemporalExtent
    purpose: str = Field(min_length=1, max_length=128)


class BitemporalExtent(BaseModel):
    """Orthogonal valid-time and transaction-time coordinates."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    valid_time: TemporalExtent
    transaction_time: TemporalExtent

    def contains(self, *, valid_at: datetime, transaction_at: datetime) -> bool:
        return self.valid_time.contains(valid_at) and self.transaction_time.contains(transaction_at)


class TemporalVersion[T](BaseModel):
    """Immutable version of a value in bitemporal coordinates."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    version_id: str = Field(min_length=1, max_length=256)
    record_key: str = Field(min_length=1, max_length=512)
    value: T
    valid_time: TemporalExtent
    transaction_time: TemporalExtent
    supersedes: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_identity(self) -> TemporalVersion[T]:
        expected = deterministic_id(
            "temporal-version",
            self.record_key,
            self.valid_time.model_dump(mode="json"),
            self.transaction_time.model_dump(mode="json"),
            self.value,
        )
        if self.version_id != expected:
            raise ValueError("version_id does not match canonical version identity")
        return self

    @classmethod
    def create(
        cls,
        record_key: str,
        value: T,
        *,
        valid_time: TemporalExtent,
        transaction_time: TemporalExtent,
        supersedes: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> TemporalVersion[T]:
        version_id = deterministic_id(
            "temporal-version",
            record_key,
            valid_time.model_dump(mode="json"),
            transaction_time.model_dump(mode="json"),
            value,
        )
        return cls(
            version_id=version_id,
            record_key=record_key,
            value=value,
            valid_time=valid_time,
            transaction_time=transaction_time,
            supersedes=supersedes,
            metadata={} if metadata is None else metadata,
        )
