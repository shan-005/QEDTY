from __future__ import annotations

from dataclasses import dataclass

from .base import SourceAdapter


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    name: str
    domain: str
    adapter: SourceAdapter


class SourceRegistry:
    def __init__(self):
        self._items = {}

    def register(self, d: SourceDefinition):
        if d.source_id in self._items and self._items[d.source_id] != d:
            raise ValueError("source conflict")
        self._items[d.source_id] = d

    def get(self, source_id: str) -> SourceDefinition:
        return self._items[source_id]

    def all(self) -> tuple[SourceDefinition, ...]:
        return tuple(self._items[k] for k in sorted(self._items))
