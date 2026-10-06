from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GraphPath:
    entity_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    score: float

    @property
    def hops(self) -> int:
        return len(self.relationship_ids)
