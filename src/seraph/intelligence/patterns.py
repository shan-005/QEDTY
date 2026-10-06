from __future__ import annotations

from dataclasses import dataclass

from seraph.graph.store import TemporalGraph


@dataclass(frozen=True)
class Pattern:
    pattern_id: str
    name: str
    entity_ids: tuple[str, ...]
    score: float
    rationale: str


class PatternEngine:
    def single_point_dependencies(self, graph: TemporalGraph) -> tuple[Pattern, ...]:
        out = []
        for e in graph.entities():
            incoming = graph.edges_to(e.entity_id)
            if len(incoming) == 1:
                out.append(
                    Pattern(
                        f"spof:{e.entity_id}",
                        "single-upstream-dependency",
                        (e.entity_id, incoming[0].source.entity_id),
                        1.0,
                        "exactly one upstream relationship in current graph",
                    )
                )
        return tuple(sorted(out, key=lambda p: p.pattern_id))
