from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .base import SourceAdapter


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    source_id: str
    name: str
    domain: str
    adapter: SourceAdapter
    authority: str = ""
    license_scope: str = ""
    version: str = "1"
    aliases: tuple[str, ...] = ()


class SourceRegistry:
    def __init__(self) -> None:
        self._items: dict[str, SourceDefinition] = {}
        self._aliases: dict[str, str] = {}

    def register(self, d: SourceDefinition) -> None:
        if not d.source_id.strip():
            raise ValueError("source_id must not be blank")
        if d.source_id in self._items and self._items[d.source_id] != d:
            raise ValueError("source conflict")
        for alias in d.aliases:
            previous = self._aliases.get(alias)
            if previous and previous != d.source_id:
                raise ValueError(f"source alias conflict: {alias}")
            self._aliases[alias] = d.source_id
        self._items[d.source_id] = d

    def register_many(self, definitions: Iterable[SourceDefinition]) -> None:
        for d in definitions:
            self.register(d)

    def get(self, source_id: str) -> SourceDefinition:
        resolved = self._aliases.get(source_id, source_id)
        return self._items[resolved]

    def all(self) -> tuple[SourceDefinition, ...]:
        return tuple(self._items[k] for k in sorted(self._items))

    def domains(self) -> tuple[str, ...]:
        return tuple(sorted({d.domain for d in self._items.values()}))
