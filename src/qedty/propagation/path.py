"""Path and ranking utilities for propagation outputs."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .models import PropagationEvent


def strongest(events: tuple[PropagationEvent, ...]) -> tuple[PropagationEvent, ...]:
    """Return one strongest event per entity, preserving the legacy API."""
    best: dict[str, PropagationEvent] = {}
    for event in events:
        current = best.get(event.entity_id)
        if current is None or _event_rank(event) < _event_rank(current):
            best[event.entity_id] = event
    return tuple(sorted(best.values(), key=lambda item: (item.depth, item.entity_id)))


def top_k(events: Iterable[PropagationEvent], k: int) -> tuple[PropagationEvent, ...]:
    if k <= 0:
        raise ValueError("k must be positive")
    return tuple(sorted(events, key=_event_rank)[:k])


def group_by_entity(
    events: Iterable[PropagationEvent],
) -> dict[str, tuple[PropagationEvent, ...]]:
    grouped: defaultdict[str, list[PropagationEvent]] = defaultdict(list)
    for event in events:
        grouped[event.entity_id].append(event)
    return {
        entity_id: tuple(sorted(items, key=_event_rank))
        for entity_id, items in sorted(grouped.items())
    }


def influence_score(event: PropagationEvent) -> float:
    """A deterministic descriptive score, not a probability or economic loss."""
    return event.impairment / max(1, event.depth + 1)


def critical_paths(
    events: Iterable[PropagationEvent], *, k: int = 10
) -> tuple[PropagationEvent, ...]:
    if k <= 0:
        raise ValueError("k must be positive")
    return tuple(
        sorted(
            events,
            key=lambda item: (-influence_score(item), item.effective_at, item.entity_id),
        )[:k]
    )


def path_signature(event: PropagationEvent) -> tuple[str, ...]:
    return (*event.path_entity_ids, "|", *event.path_relationship_ids)


def _event_rank(event: PropagationEvent) -> tuple[object, ...]:
    return (
        -event.impairment,
        event.depth,
        event.effective_at,
        event.entity_id,
        event.path_relationship_ids,
        event.path_entity_ids,
    )
