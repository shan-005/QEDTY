"""Temporal validity helpers for graph relationships."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from seraph.core.time import ensure_utc

if TYPE_CHECKING:
    from datetime import datetime

    from seraph.ontology.relations import Relationship


def active(edge: Relationship, at: datetime) -> bool:
    """Return whether a relationship is active at an instant."""

    instant = ensure_utc(at)
    if edge.valid_from is not None and instant < ensure_utc(edge.valid_from):
        return False
    return not (edge.valid_to is not None and instant >= ensure_utc(edge.valid_to))


def active_relationships(edges: tuple[Relationship, ...], at: datetime) -> tuple[Relationship, ...]:
    """Filter relationships to the half-open valid-time snapshot at ``at``."""

    return tuple(edge for edge in edges if active(edge, at))


def overlaps_window(
    edge: Relationship,
    start: datetime,
    end: datetime,
) -> bool:
    """Return whether the edge validity intersects a half-open time window."""

    s = ensure_utc(start)
    e = ensure_utc(end)
    if e <= s:
        raise ValueError("end must be after start")
    if edge.valid_to is not None and ensure_utc(edge.valid_to) <= s:
        return False
    return not (edge.valid_from is not None and ensure_utc(edge.valid_from) >= e)


def active_for_entire_window(
    edge: Relationship,
    start: datetime,
    end: datetime,
) -> bool:
    """Return whether an edge is valid for the entire half-open window."""

    s = ensure_utc(start)
    e = ensure_utc(end)
    if e <= s:
        raise ValueError("end must be after start")
    return (edge.valid_from is None or ensure_utc(edge.valid_from) <= s) and (
        edge.valid_to is None or ensure_utc(edge.valid_to) >= e
    )
