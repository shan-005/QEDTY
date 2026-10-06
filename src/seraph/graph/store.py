from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime

from seraph.core.enums import RelationshipType
from seraph.core.hash import sha256_hex
from seraph.ontology.entities import Entity
from seraph.ontology.relations import Relationship

from .model import GraphPath


class TemporalGraph:
    def __init__(self):
        self._entities = {}
        self._rels = {}
        self._out = defaultdict(set)
        self._in = defaultdict(set)

    def add_entity(self, e: Entity):
        p = self._entities.get(e.entity_id)
        if p and p != e:
            raise ValueError("entity collision")
        self._entities[e.entity_id] = e

    def add_relationship(self, r: Relationship):
        if r.source.entity_id not in self._entities or r.target.entity_id not in self._entities:
            raise KeyError("missing relationship endpoint")
        p = self._rels.get(r.relationship_id)
        if p and p != r:
            raise ValueError("relationship collision")
        self._rels[r.relationship_id] = r
        self._out[r.source.entity_id].add(r.relationship_id)
        self._in[r.target.entity_id].add(r.relationship_id)

    def entities(self):
        return tuple(sorted(self._entities.values(), key=lambda x: x.entity_id))

    def relationships(self):
        return tuple(sorted(self._rels.values(), key=lambda x: x.relationship_id))

    def edges_from(self, eid: str, at: datetime | None = None):
        out = []
        for rid in sorted(self._out.get(eid, ())):
            r = self._rels[rid]
            if at is not None and (
                (r.valid_from and at < r.valid_from) or (r.valid_to and at >= r.valid_to)
            ):
                continue
            out.append(r)
        return tuple(out)

    def edges_to(self, eid: str, at: datetime | None = None):
        out = []
        for rid in sorted(self._in.get(eid, ())):
            r = self._rels[rid]
            if at is not None and (
                (r.valid_from and at < r.valid_from) or (r.valid_to and at >= r.valid_to)
            ):
                continue
            out.append(r)
        return tuple(out)

    def shortest_paths(
        self,
        source: str,
        target: str,
        *,
        at: datetime | None = None,
        max_hops: int = 16,
        max_results: int = 10,
    ):
        if source not in self._entities or target not in self._entities:
            raise KeyError("graph endpoint missing")
        q = deque([(source, (source,), (), 1.0)])
        res = []
        best = {source: 1.0}
        while q and len(res) < max_results:
            node, nodes, rids, score = q.popleft()
            if len(rids) >= max_hops:
                continue
            for r in self.edges_from(node, at=at):
                if r.target.entity_id in nodes:
                    continue
                ns = score * r.strength * r.capacity_fraction
                nid = r.target.entity_id
                nn = (*nodes, nid)
                nr = (*rids, r.relationship_id)
                if nid == target:
                    res.append(GraphPath(nn, nr, ns))
                    continue
                if ns <= best.get(nid, -1):
                    continue
                best[nid] = ns
                q.append((nid, nn, nr, ns))
        return tuple(sorted(res, key=lambda p: (p.hops, -p.score, p.entity_ids)))

    def neighbors(
        self,
        eid: str,
        *,
        at: datetime | None = None,
        direction: str = "out",
        types: set[RelationshipType] | None = None,
    ):
        edges = self.edges_from(eid, at=at) if direction == "out" else self.edges_to(eid, at=at)
        result = []
        for r in edges:
            if types and r.relationship_type not in types:
                continue
            result.append(
                self._entities[r.target.entity_id if direction == "out" else r.source.entity_id]
            )
        return tuple(sorted({e.entity_id: e for e in result}.values(), key=lambda x: x.entity_id))

    def digest(self) -> str:
        return sha256_hex(
            {
                "entities": [e.model_dump(mode="json") for e in self.entities()],
                "relationships": [r.model_dump(mode="json") for r in self.relationships()],
            }
        )
