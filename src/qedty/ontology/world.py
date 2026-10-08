from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from qedty.core.enums import EpistemicStatus
from qedty.core.hash import sha256_hex
from qedty.core.types import ExternalIdentifier

from .assertions import Assertion
from .capabilities import Capability
from .entities import Entity, EntityResolution
from .events import WorldEvent
from .flows import Flow
from .relations import Relationship
from .schema import ONTOLOGY_PROFILE, WORLD_MODEL_SCHEMA
from .services import Service
from .terms import ResolutionDecision

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Iterator, Mapping

WorldRecord = (
    Entity | Relationship | WorldEvent | Capability | Service | Flow | Assertion | EntityResolution
)


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    """Immutable manifest of a world-model state."""

    version: int
    counts: Mapping[str, int]
    fingerprint: str


@dataclass
class WorldModel:
    """Thread-safe in-memory semantic world model with referential integrity."""

    entities: dict[str, Entity] = field(default_factory=dict)
    relationships: dict[str, Relationship] = field(default_factory=dict)
    events: dict[str, WorldEvent] = field(default_factory=dict)
    capabilities: dict[str, Capability] = field(default_factory=dict)
    services: dict[str, Service] = field(default_factory=dict)
    flows: dict[str, Flow] = field(default_factory=dict)
    assertions: dict[str, Assertion] = field(default_factory=dict)
    resolutions: dict[str, EntityResolution] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, repr=False, compare=False)
    _version: int = field(default=0, repr=False, compare=False)
    _relationships_by_entity: dict[str, set[str]] = field(
        default_factory=dict, repr=False, compare=False
    )
    _events_by_entity: dict[str, set[str]] = field(default_factory=dict, repr=False, compare=False)
    _external_index: dict[str, set[str]] = field(default_factory=dict, repr=False, compare=False)
    _resolution_index: dict[str, set[str]] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        with self._lock:
            self._rebuild_indexes_unlocked()
            self.validate_integrity()

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def add(self, item: WorldRecord) -> None:
        with self._lock:
            if isinstance(item, Entity):
                self.add_entity(item)
            elif isinstance(item, Relationship):
                self.add_relationship(item)
            elif isinstance(item, WorldEvent):
                self.add_event(item)
            elif isinstance(item, Capability):
                self.add_capability(item)
            elif isinstance(item, Service):
                self.add_service(item)
            elif isinstance(item, Flow):
                self.add_flow(item)
            elif isinstance(item, Assertion):
                self.add_assertion(item)
            else:
                # FIXED: Type checker knows 'item' must be EntityResolution here
                self.add_resolution(item)

    def _insert(self, store: dict[str, Any], key: str, value: Any, label: str) -> None:
        previous = store.get(key)
        if previous is not None and previous != value:
            raise ValueError(f"{label} collision: {key}")
        if previous is None:
            store[key] = value
            self._version += 1

    def add_entity(self, item: Entity) -> None:
        self._insert(self.entities, item.entity_id, item, "entity")
        self._index_entity(item)

    def add_relationship(self, item: Relationship) -> None:
        self._require_entities(item.source.entity_id, item.target.entity_id)
        self._insert(self.relationships, item.relationship_id, item, "relationship")
        self._relationships_by_entity.setdefault(item.source.entity_id, set()).add(
            item.relationship_id
        )
        self._relationships_by_entity.setdefault(item.target.entity_id, set()).add(
            item.relationship_id
        )

    def add_event(self, item: WorldEvent) -> None:
        self._require_entities(*item.source_entity_ids, *item.affected_entity_ids)
        self._insert(self.events, item.event_id, item, "event")
        for entity_id in (*item.source_entity_ids, *item.affected_entity_ids):
            self._events_by_entity.setdefault(entity_id, set()).add(item.event_id)

    def add_capability(self, item: Capability) -> None:
        self._require_entities(item.owner.entity_id)
        self._insert(self.capabilities, item.capability_id, item, "capability")

    def add_service(self, item: Service) -> None:
        self._require_entities(*item.provider_entity_ids, *item.geographic_scope)
        missing_caps = sorted(set(item.capability_ids) - self.capabilities.keys())
        if missing_caps:
            raise KeyError(f"service capability missing: {missing_caps}")
        missing_rels = sorted(set(item.dependency_relationship_ids) - self.relationships.keys())
        if missing_rels:
            raise KeyError(f"service relationships missing: {missing_rels}")
        self._insert(self.services, item.service_id, item, "service")

    def add_flow(self, item: Flow) -> None:
        self._require_entities(item.source.entity_id, item.target.entity_id)
        self._insert(self.flows, item.flow_id, item, "flow")

    def add_assertion(self, item: Assertion) -> None:
        self._require_entities(
            item.subject.entity_id, item.object_entity.entity_id if item.object_entity else None
        )
        self._insert(self.assertions, item.assertion_id, item, "assertion")

    def add_resolution(self, item: EntityResolution) -> None:
        if item.entity_id not in self.entities:
            raise KeyError(f"resolution entity missing: {item.entity_id}")
        key = f"{item.external_identifier.namespace}:{item.external_identifier.value}"
        if item.decision == ResolutionDecision.ACCEPTED:
            mapped = self._resolution_index.get(key, set()) - {item.entity_id}
            if mapped:
                raise ValueError(f"external identifier already resolves to another entity: {key}")
        previous = self.resolutions.get(item.resolution_id)
        self._insert(self.resolutions, item.resolution_id, item, "entity-resolution")
        if previous is None and item.decision == ResolutionDecision.ACCEPTED:
            self._resolution_index.setdefault(key, set()).add(item.entity_id)

    def _require_entities(self, *entity_ids: str | None) -> None:
        missing = sorted(
            {item for item in entity_ids if item is not None and item not in self.entities}
        )
        if missing:
            raise KeyError(f"entity endpoint missing: {missing}")

    def _index_entity(self, item: Entity) -> None:
        for identifier in item.external_identifiers:
            key = f"{identifier.namespace}:{identifier.value}"
            self._external_index.setdefault(key, set()).add(item.entity_id)

    def add_many(self, items: Iterable[WorldRecord]) -> None:
        with self.transaction():
            for item in items:
                self.add(item)

    def find_entity_by_external_identifier(self, namespace: str, value: str) -> tuple[str, ...]:
        identifier = ExternalIdentifier(namespace=namespace, value=value)
        key = f"{identifier.namespace}:{identifier.value}"
        with self._lock:
            resolved = self._resolution_index.get(key, set())
            ids = resolved or self._external_index.get(key, set())
            return tuple(sorted(ids))

    def relationships_for(self, entity_id: str) -> tuple[Relationship, ...]:
        with self._lock:
            ids = sorted(self._relationships_by_entity.get(entity_id, set()))
            return tuple(self.relationships[item] for item in ids)

    def events_for(self, entity_id: str) -> tuple[WorldEvent, ...]:
        with self._lock:
            ids = sorted(self._events_by_entity.get(entity_id, set()))
            return tuple(self.events[item] for item in ids)

    def get_entity(self, entity_id: str) -> Entity:
        with self._lock:
            return self.entities[entity_id]

    def contains(self, entity_id: str) -> bool:
        with self._lock:
            return entity_id in self.entities

    def remove_entity(self, entity_id: str, *, cascade: bool = False) -> None:
        with self._lock:
            if entity_id not in self.entities:
                raise KeyError(entity_id)
            relationship_ids = sorted(self._relationships_by_entity.get(entity_id, set()))
            event_ids = sorted(self._events_by_entity.get(entity_id, set()))
            capability_ids = sorted(
                item.capability_id
                for item in self.capabilities.values()
                if item.owner.entity_id == entity_id
            )
            service_ids = sorted(
                item.service_id
                for item in self.services.values()
                if entity_id in item.provider_entity_ids
                or entity_id in item.geographic_scope
                or bool(set(item.dependency_relationship_ids) & set(relationship_ids))
                or bool(set(item.capability_ids) & set(capability_ids))
            )
            flow_ids = sorted(
                item.flow_id
                for item in self.flows.values()
                if entity_id in {item.source.entity_id, item.target.entity_id}
            )
            assertion_ids = sorted(
                item.assertion_id
                for item in self.assertions.values()
                if entity_id in {item.subject.entity_id, item.object_id}
            )
            resolution_ids = sorted(
                item.resolution_id
                for item in self.resolutions.values()
                if item.entity_id == entity_id
            )
            dependent = (
                relationship_ids
                + event_ids
                + capability_ids
                + service_ids
                + flow_ids
                + assertion_ids
                + resolution_ids
            )
            if dependent and not cascade:
                raise ValueError(f"entity has {len(dependent)} dependent records; use cascade=True")
            for key in relationship_ids:
                self.relationships.pop(key, None)
            for key in event_ids:
                self.events.pop(key, None)
            for key in capability_ids:
                self.capabilities.pop(key, None)
            for key in service_ids:
                self.services.pop(key, None)
            for key in flow_ids:
                self.flows.pop(key, None)
            for key in assertion_ids:
                self.assertions.pop(key, None)
            for key in resolution_ids:
                self.resolutions.pop(key, None)
            self.entities.pop(entity_id)
            self._version += 1
            self._rebuild_indexes_unlocked()

    def validate_integrity(self) -> None:
        """Validate all foreign-key-like references and deterministic identities."""
        with self._lock:
            for relationship in self.relationships.values():
                self._require_entities(relationship.source.entity_id, relationship.target.entity_id)
            for event in self.events.values():
                self._require_entities(*event.source_entity_ids, *event.affected_entity_ids)
            for capability in self.capabilities.values():
                self._require_entities(capability.owner.entity_id)
            for service in self.services.values():
                self._require_entities(*service.provider_entity_ids, *service.geographic_scope)
                if set(service.capability_ids) - self.capabilities.keys():
                    raise KeyError(f"service {service.service_id} references missing capability")
                if set(service.dependency_relationship_ids) - self.relationships.keys():
                    raise KeyError(f"service {service.service_id} references missing relationship")
            for flow in self.flows.values():
                self._require_entities(flow.source.entity_id, flow.target.entity_id)
            for assertion in self.assertions.values():
                self._require_entities(
                    assertion.subject.entity_id,
                    assertion.object_entity.entity_id if assertion.object_entity else None,
                )
            accepted_resolution_map: dict[str, str] = {}
            for resolution in self.resolutions.values():
                self._require_entities(resolution.entity_id)
                if resolution.decision == ResolutionDecision.ACCEPTED:
                    key = f"{resolution.external_identifier.namespace}:{resolution.external_identifier.value}"
                    previous = accepted_resolution_map.get(key)
                    if previous is not None and previous != resolution.entity_id:
                        raise ValueError(
                            f"external identifier resolves to multiple entities: {key}"
                        )
                    accepted_resolution_map[key] = resolution.entity_id

    def _rebuild_indexes_unlocked(self) -> None:
        self._relationships_by_entity.clear()
        self._events_by_entity.clear()
        self._external_index.clear()
        self._resolution_index.clear()
        for entity in self.entities.values():
            self._index_entity(entity)
        for rel in self.relationships.values():
            self._relationships_by_entity.setdefault(rel.source.entity_id, set()).add(
                rel.relationship_id
            )
            self._relationships_by_entity.setdefault(rel.target.entity_id, set()).add(
                rel.relationship_id
            )
        for event in self.events.values():
            for entity_id in (*event.source_entity_ids, *event.affected_entity_ids):
                self._events_by_entity.setdefault(entity_id, set()).add(event.event_id)
        for resolution in self.resolutions.values():
            if resolution.decision == ResolutionDecision.ACCEPTED:
                key = f"{resolution.external_identifier.namespace}:{resolution.external_identifier.value}"
                self._resolution_index.setdefault(key, set()).add(resolution.entity_id)

    def iter_all(self) -> Iterator[WorldRecord]:
        with self._lock:
            records = (
                tuple(sorted(self.entities.values(), key=lambda item: item.entity_id))
                + tuple(sorted(self.relationships.values(), key=lambda item: item.relationship_id))
                + tuple(sorted(self.events.values(), key=lambda item: item.event_id))
                + tuple(sorted(self.capabilities.values(), key=lambda item: item.capability_id))
                + tuple(sorted(self.services.values(), key=lambda item: item.service_id))
                + tuple(sorted(self.flows.values(), key=lambda item: item.flow_id))
                + tuple(sorted(self.assertions.values(), key=lambda item: item.assertion_id))
                + tuple(sorted(self.resolutions.values(), key=lambda item: item.resolution_id))
            )
        yield from records

    def _to_dict_unlocked(self) -> dict[str, object]:
        return {
            "schema": WORLD_MODEL_SCHEMA,
            "ontology_profile": ONTOLOGY_PROFILE,
            "version": self._version,
            "entities": [
                item.model_dump(mode="json")
                for item in sorted(self.entities.values(), key=lambda value: value.entity_id)
            ],
            "relationships": [
                item.model_dump(mode="json")
                for item in sorted(
                    self.relationships.values(), key=lambda value: value.relationship_id
                )
            ],
            "events": [
                item.model_dump(mode="json")
                for item in sorted(self.events.values(), key=lambda value: value.event_id)
            ],
            "capabilities": [
                item.model_dump(mode="json")
                for item in sorted(
                    self.capabilities.values(), key=lambda value: value.capability_id
                )
            ],
            "services": [
                item.model_dump(mode="json")
                for item in sorted(self.services.values(), key=lambda value: value.service_id)
            ],
            "flows": [
                item.model_dump(mode="json")
                for item in sorted(self.flows.values(), key=lambda value: value.flow_id)
            ],
            "assertions": [
                item.model_dump(mode="json")
                for item in sorted(self.assertions.values(), key=lambda value: value.assertion_id)
            ],
            "resolutions": [
                item.model_dump(mode="json")
                for item in sorted(self.resolutions.values(), key=lambda value: value.resolution_id)
            ],
        }

    def to_dict(self) -> dict[str, object]:
        with self._lock:
            return self._to_dict_unlocked()

    def summary(self) -> dict[str, int]:
        with self._lock:
            return {
                "entities": len(self.entities),
                "relationships": len(self.relationships),
                "events": len(self.events),
                "capabilities": len(self.capabilities),
                "services": len(self.services),
                "flows": len(self.flows),
                "assertions": len(self.assertions),
                "resolutions": len(self.resolutions),
                "version": self._version,
            }

    def snapshot(self) -> WorldSnapshot:
        with self._lock:
            document = self._to_dict_unlocked()
            counts = {
                "entities": len(self.entities),
                "relationships": len(self.relationships),
                "events": len(self.events),
                "capabilities": len(self.capabilities),
                "services": len(self.services),
                "flows": len(self.flows),
                "assertions": len(self.assertions),
                "resolutions": len(self.resolutions),
                "version": self._version,
            }
            return WorldSnapshot(
                version=self._version,
                counts=MappingProxyType(counts),
                fingerprint=sha256_hex(document),
            )

    def unknown_entity_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(
                sorted(
                    item.entity_id
                    for item in self.entities.values()
                    if item.epistemic_status == EpistemicStatus.UNKNOWN
                )
            )

    @contextmanager
    # FIXED: Changed Iterator to Generator to satisfy contextmanager deprecation warning
    def transaction(self) -> Generator[WorldModel, None, None]:
        """Apply mutations atomically, restoring state on exceptions."""
        with self._lock:
            backup = (
                dict(self.entities),
                dict(self.relationships),
                dict(self.events),
                dict(self.capabilities),
                dict(self.services),
                dict(self.flows),
                dict(self.assertions),
                dict(self.resolutions),
                self._version,
            )
            try:
                yield self
                self.validate_integrity()
            except Exception:
                (
                    entities,
                    relationships,
                    events,
                    capabilities,
                    services,
                    flows,
                    assertions,
                    resolutions,
                    version,
                ) = backup
                self.entities = entities
                self.relationships = relationships
                self.events = events
                self.capabilities = capabilities
                self.services = services
                self.flows = flows
                self.assertions = assertions
                self.resolutions = resolutions
                self._version = version
                self._rebuild_indexes_unlocked()
                raise
