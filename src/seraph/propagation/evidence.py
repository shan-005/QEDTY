"""Auditable evidence extraction for propagation results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import PropagationEvent, PropagationEvidence

if TYPE_CHECKING:
    from collections.abc import Iterable


def evidence_for_event(event: PropagationEvent, *, rank: int = 1) -> PropagationEvidence:
    inputs = tuple(
        dict.fromkeys(
            (
                *event.source_shock_ids,
                *event.path_relationship_ids,
            )
        )
    )
    return PropagationEvidence(
        entity_id=event.entity_id,
        reason=(
            f"entity reached along a {event.depth}-hop path with "
            f"contribution={event.contribution:.12g}"
        ),
        input_ids=inputs,
        method=event.method,
        contribution=event.contribution,
        rank=rank,
        path_entity_ids=event.path_entity_ids,
        path_relationship_ids=event.path_relationship_ids,
    )


def build_evidence(events: Iterable[PropagationEvent]) -> tuple[PropagationEvidence, ...]:
    ordered = sorted(events, key=lambda item: (-item.impairment, item.entity_id))
    return tuple(evidence_for_event(event, rank=index) for index, event in enumerate(ordered, 1))


def summarize_evidence(evidence: Iterable[PropagationEvidence]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in evidence:
        counts[item.method] = counts.get(item.method, 0) + 1
    return dict(sorted(counts.items()))
