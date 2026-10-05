from __future__ import annotations

from dataclasses import dataclass, field

from seraph.pci.core.types import Relationship
from seraph.pci.entities.models import Entity
from seraph.pci.evidence.models import EvidenceRecord
from seraph.pci.graph.store import TemporalGraph


@dataclass(slots=True)
class GraphBuilder:
    graph: TemporalGraph = field(default_factory=TemporalGraph)
    evidence: dict[str, EvidenceRecord] = field(default_factory=dict)

    def add_evidence(self, record: EvidenceRecord) -> None:
        existing = self.evidence.get(record.evidence_id)
        if existing is not None and existing != record:
            raise ValueError(f"evidence collision: {record.evidence_id}")
        self.evidence[record.evidence_id] = record

    def add_entity(self, entity: Entity) -> None:
        missing = sorted(set(entity.evidence_ids) - self.evidence.keys())
        if missing:
            raise KeyError(f"entity references unknown evidence: {missing}")
        self.graph.add_entity(entity)

    def add_relationship(self, relationship: Relationship) -> None:
        missing = sorted(set(relationship.evidence_ids) - self.evidence.keys())
        if missing:
            raise KeyError(f"relationship references unknown evidence: {missing}")
        self.graph.add_relationship(relationship)

    def build(self) -> TemporalGraph:
        return self.graph
