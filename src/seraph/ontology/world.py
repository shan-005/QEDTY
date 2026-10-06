from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from threading import RLock

from seraph.core.enums import EpistemicStatus

from .assertions import Assertion
from .capabilities import Capability
from .entities import Entity
from .events import WorldEvent
from .flows import Flow
from .relations import Relationship
from .services import Service


@dataclass
class WorldModel:
    entities: dict[str, Entity] = field(default_factory=dict)
    relationships: dict[str, Relationship] = field(default_factory=dict)
    events: dict[str, WorldEvent] = field(default_factory=dict)
    capabilities: dict[str, Capability] = field(default_factory=dict)
    services: dict[str, Service] = field(default_factory=dict)
    flows: dict[str, Flow] = field(default_factory=dict)
    assertions: dict[str, Assertion] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def add_entity(self, x: Entity) -> None:
        with self._lock:
            prev = self.entities.get(x.entity_id)
            if prev and prev != x:
                raise ValueError(f"entity collision: {x.entity_id}")
            self.entities[x.entity_id] = x

    def add_relationship(self, x: Relationship) -> None:
        with self._lock:
            if x.source.entity_id not in self.entities or x.target.entity_id not in self.entities:
                raise KeyError("relationship endpoint missing")
            prev = self.relationships.get(x.relationship_id)
            if prev and prev != x:
                raise ValueError(f"relationship collision: {x.relationship_id}")
            self.relationships[x.relationship_id] = x

    def add_event(self, x: WorldEvent) -> None:
        prev = self.events.get(x.event_id)
        if prev and prev != x:
            raise ValueError(f"event collision: {x.event_id}")
        self.events[x.event_id] = x

    def add_many(self, items: Iterable[object]) -> None:
        for x in items:
            if isinstance(x, Entity):
                self.add_entity(x)
            elif isinstance(x, Relationship):
                self.add_relationship(x)
            elif isinstance(x, WorldEvent):
                self.add_event(x)
            elif isinstance(x, Capability):
                self.capabilities[x.capability_id] = x
            elif isinstance(x, Service):
                self.services[x.service_id] = x
            elif isinstance(x, Flow):
                self.flows[x.flow_id] = x
            elif isinstance(x, Assertion):
                self.assertions[x.assertion_id] = x
            else:
                raise TypeError(type(x).__name__)

    def summary(self) -> dict[str, int]:
        return {
            "entities": len(self.entities),
            "relationships": len(self.relationships),
            "events": len(self.events),
            "capabilities": len(self.capabilities),
            "services": len(self.services),
            "flows": len(self.flows),
            "assertions": len(self.assertions),
        }

    def unknown_entity_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                x.entity_id
                for x in self.entities.values()
                if x.epistemic_status == EpistemicStatus.UNKNOWN
            )
        )
