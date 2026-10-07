from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from seraph.graph.store import TemporalGraph


@dataclass(frozen=True, slots=True)
class Pattern:
    pattern_id: str
    name: str
    entity_ids: tuple[str, ...]
    score: float
    rationale: str
    severity: str = "info"


class PatternEngine:
    """Graph pattern detector with stable ordering and bounded topology scans."""

    def single_point_dependencies(self, graph: TemporalGraph) -> tuple[Pattern, ...]:
        out: list[Pattern] = []
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
                        "high",
                    )
                )
        return tuple(sorted(out, key=lambda p: p.pattern_id))

    def dependency_concentration(self, graph: TemporalGraph) -> tuple[Pattern, ...]:
        out: list[Pattern] = []
        for e in graph.entities():
            incoming = graph.edges_to(e.entity_id)
            if len(incoming) < 2:
                continue
            weights = [max(0.0, r.strength * r.capacity_fraction) for r in incoming]
            total = sum(weights)
            if total <= 0:
                continue
            concentration = max(weights) / total
            if concentration >= 0.8:
                out.append(
                    Pattern(
                        f"concentration:{e.entity_id}",
                        "upstream-concentration",
                        (e.entity_id, *tuple(sorted(r.source.entity_id for r in incoming))),
                        concentration,
                        "one upstream relationship carries at least 80% of available modeled support capacity",
                        "medium",
                    )
                )
        return tuple(sorted(out, key=lambda p: p.pattern_id))

    def run(self, graph: TemporalGraph) -> tuple[Pattern, ...]:
        detectors: tuple[Callable[[TemporalGraph], tuple[Pattern, ...]], ...] = (
            self.single_point_dependencies,
            self.dependency_concentration,
        )
        merged = [p for detector in detectors for p in detector(graph)]
        return tuple(sorted({p.pattern_id: p for p in merged}.values(), key=lambda p: p.pattern_id))
