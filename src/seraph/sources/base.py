from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceContext:
    source_id: str
    license_scope: str
    configuration_digest: str


class SourceAdapter(ABC):
    domain = "unknown"

    @abstractmethod
    def discover(self, context: SourceContext) -> tuple[object, ...]:
        """Discover normalized records under an explicit source contract."""
        raise NotImplementedError
