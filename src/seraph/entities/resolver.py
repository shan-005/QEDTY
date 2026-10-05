from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from seraph.core.enums import EntityType
from seraph.core.ids import canonicalize_text, deterministic_id
from seraph.entities.models import Entity


canonicalize_name = canonicalize_text


class EntityResolver:
    """Deterministic first-pass resolver; probabilistic resolution belongs above this contract."""

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._alias_index: dict[str, set[str]] = {}
        self._external_index: dict[tuple[str, str], str] = {}

    def make_entity(
        self,
        *,
        entity_type: EntityType,
        canonical_name: str,
        namespace: str = "seraph",
        aliases: Iterable[str] = (),
        external_ids: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> Entity:
        entity_id = deterministic_id("entity", namespace, entity_type.value, canonicalize_name(canonical_name))
        return Entity(
            entity_id=entity_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            namespace=namespace,
            aliases=tuple(dict.fromkeys(aliases)),
            external_ids=dict(external_ids or {}),
            **kwargs,
        )

    def upsert(self, entity: Entity) -> Entity:
        existing = self._entities.get(entity.entity_id)
        if existing is not None and existing != entity:
            raise ValueError(f"entity conflict for {entity.entity_id}")
        self._entities[entity.entity_id] = entity
        names = (entity.canonical_name, *entity.aliases)
        for name in names:
            key = canonicalize_name(name)
            self._alias_index.setdefault(key, set()).add(entity.entity_id)
        for system, external_id in entity.external_ids.items():
            key = (canonicalize_name(system), external_id.strip())
            previous = self._external_index.get(key)
            if previous is not None and previous != entity.entity_id:
                raise ValueError(f"external identity collision: {key}")
            self._external_index[key] = entity.entity_id
        return entity

    def resolve_name(self, name: str) -> tuple[Entity, ...]:
        ids = sorted(self._alias_index.get(canonicalize_name(name), set()))
        return tuple(self._entities[i] for i in ids)

    def resolve_external(self, system: str, external_id: str) -> Entity | None:
        entity_id = self._external_index.get((canonicalize_name(system), external_id.strip()))
        return self._entities.get(entity_id) if entity_id else None

    def get(self, entity_id: str) -> Entity:
        return self._entities[entity_id]

    def all(self) -> tuple[Entity, ...]:
        return tuple(sorted(self._entities.values(), key=lambda e: e.entity_id))
