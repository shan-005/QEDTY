from __future__ import annotations

from enum import StrEnum
from threading import RLock

from pydantic import BaseModel, ConfigDict, Field

from seraph.pci.evidence.licensing import LicensePolicy


class SourceDomain(StrEnum):
    SPACE = "space"
    EARTH = "earth"
    ECONOMY = "economy"
    CROSS_DOMAIN = "cross_domain"


class SourceDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    source_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=300)
    domain: SourceDomain
    publisher: str = Field(min_length=1, max_length=300)
    homepage: str | None = None
    license_policy: LicensePolicy
    notes: str = ""


class SourceRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._sources: dict[str, SourceDefinition] = {}

    def register(self, source: SourceDefinition) -> SourceDefinition:
        with self._lock:
            existing = self._sources.get(source.source_id)
            if existing is not None and existing != source:
                raise ValueError(f"source conflict for {source.source_id}")
            self._sources[source.source_id] = source
            return source

    def get(self, source_id: str) -> SourceDefinition:
        return self._sources[source_id]

    def all(self) -> tuple[SourceDefinition, ...]:
        return tuple(self._sources[key] for key in sorted(self._sources))
