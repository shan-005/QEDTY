from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from qedty.core.hash import deterministic_id
from qedty.core.time import ensure_utc

from .models import TemporalInstant

if TYPE_CHECKING:
    from datetime import datetime


class SnapshotSelector(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    valid_at: TemporalInstant
    transaction_at: TemporalInstant | None = None

    @model_validator(mode="after")
    def normalize(self) -> SnapshotSelector:
        if self.transaction_at is None:
            return self
        if self.valid_at.time_scale != self.transaction_at.time_scale:
            raise ValueError("snapshot selector time scales must agree")
        return self

    @classmethod
    def at(cls, valid_at: datetime, transaction_at: datetime | None = None) -> SnapshotSelector:
        return cls(
            valid_at=TemporalInstant.from_datetime(valid_at),
            transaction_at=(
                None if transaction_at is None else TemporalInstant.from_datetime(transaction_at)
            ),
        )


class SnapshotMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    snapshot_id: str = Field(min_length=1, max_length=256)
    captured_at: datetime
    world_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = Field(min_length=1, max_length=128)
    selector: SnapshotSelector

    @model_validator(mode="after")
    def normalize_and_validate(self) -> SnapshotMeta:
        object.__setattr__(self, "captured_at", ensure_utc(self.captured_at))
        expected = self.build_id(
            world_digest=self.world_digest,
            schema_version=self.schema_version,
            selector=self.selector,
        )
        if self.snapshot_id != expected:
            raise ValueError("snapshot_id does not match canonical snapshot identity")
        return self

    @staticmethod
    def build_id(*, world_digest: str, schema_version: str, selector: SnapshotSelector) -> str:
        return deterministic_id(
            "snapshot",
            world_digest,
            schema_version,
            selector.model_dump(mode="json"),
        )

    @classmethod
    def create(
        cls,
        *,
        world_digest: str,
        schema_version: str,
        selector: SnapshotSelector,
        captured_at: datetime,
    ) -> SnapshotMeta:
        return cls(
            snapshot_id=cls.build_id(
                world_digest=world_digest,
                schema_version=schema_version,
                selector=selector,
            ),
            captured_at=captured_at,
            world_digest=world_digest,
            schema_version=schema_version,
            selector=selector,
        )
